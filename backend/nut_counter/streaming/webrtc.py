"""WebRTC streaming pipeline.

A single source `VideoStreamTrack` reads from the FrameBus, downsizes to
1080x1080 BGR, and hands frames to aiortc. Multiple peers attach via
`MediaRelay.subscribe(...)` so the encoder runs once regardless of viewer count.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING, Any

from .frame import FrameBus

if TYPE_CHECKING:
    pass


STREAM_SIZE = 1080
VIDEO_BITRATE = 6_000_000


class WebRTCUnavailable(RuntimeError):
    pass


def _ensure_modules() -> tuple[Any, Any, Any, Any, Any]:
    try:
        import av
        from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
        from aiortc.contrib.media import MediaRelay
        from aiortc.codecs import h264, vpx
    except ImportError as error:
        raise WebRTCUnavailable(
            "WebRTC backend requires python modules: aiortc and av"
        ) from error
    h264.DEFAULT_BITRATE = VIDEO_BITRATE
    h264.MAX_BITRATE = VIDEO_BITRATE
    vpx.DEFAULT_BITRATE = VIDEO_BITRATE
    vpx.MAX_BITRATE = VIDEO_BITRATE
    return av, RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, MediaRelay


class StreamingWebRTC:
    """Owns the source track + MediaRelay + peer registry. Lives on the runtime
    asyncio loop so all aiortc operations stay on a single thread.
    """

    def __init__(self, frame_bus: FrameBus, loop: asyncio.AbstractEventLoop) -> None:
        self.frame_bus = frame_bus
        self.loop = loop
        self._lock = threading.Lock()
        self._peers: set[Any] = set()
        self._source_track: Any = None
        self._relay: Any = None
        self._modules: tuple[Any, ...] | None = None

    # --- module loading -----------------------------------------------------
    def _modules_or_raise(self) -> tuple[Any, ...]:
        if self._modules is None:
            self._modules = _ensure_modules()
        return self._modules

    def _ensure_source(self) -> tuple[Any, Any]:
        if self._source_track is not None and self._relay is not None:
            return self._source_track, self._relay
        av, _, _, VideoStreamTrack, MediaRelay = self._modules_or_raise()
        self._source_track = _BusVideoTrack(av, self.frame_bus, STREAM_SIZE, VideoStreamTrack)
        self._relay = MediaRelay()
        return self._source_track, self._relay

    # --- public API ---------------------------------------------------------
    async def create_answer(self, offer: dict[str, Any]) -> dict[str, str]:
        if not isinstance(offer.get("sdp"), str) or not isinstance(offer.get("type"), str):
            raise ValueError("WebRTC offer must include sdp and type")

        _, RTCPeerConnection, RTCSessionDescription, _, _ = self._modules_or_raise()
        source, relay = self._ensure_source()

        pc = RTCPeerConnection()
        with self._lock:
            self._peers.add(pc)

        @pc.on("connectionstatechange")
        async def on_state() -> None:  # noqa: WPS430
            if pc.connectionState in {"failed", "closed", "disconnected"}:
                with self._lock:
                    self._peers.discard(pc)
                try:
                    await pc.close()
                except Exception:  # noqa: BLE001
                    pass

        try:
            pc.addTrack(relay.subscribe(source))
            await pc.setRemoteDescription(
                RTCSessionDescription(sdp=offer["sdp"], type=offer["type"])
            )
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            await _wait_ice(pc)
            return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        except Exception:
            with self._lock:
                self._peers.discard(pc)
            try:
                await pc.close()
            except Exception:  # noqa: BLE001
                pass
            raise

    async def close_all(self) -> None:
        with self._lock:
            peers = list(self._peers)
            self._peers.clear()
        await asyncio.gather(*(_safe_close(p) for p in peers), return_exceptions=True)
        source = self._source_track
        self._source_track = None
        self._relay = None
        if source is not None:
            try:
                source.stop()
            except Exception:  # noqa: BLE001
                pass


async def _safe_close(pc: Any) -> None:
    try:
        await pc.close()
    except Exception:  # noqa: BLE001
        pass


async def _wait_ice(pc: Any) -> None:
    if pc.iceGatheringState == "complete":
        return
    done = asyncio.Event()

    @pc.on("icegatheringstatechange")
    def _on_change() -> None:  # noqa: WPS430
        if pc.iceGatheringState == "complete":
            done.set()

    try:
        await asyncio.wait_for(done.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        pass


def _BusVideoTrack(av: Any, frame_bus: FrameBus, target_size: int, base: Any) -> Any:
    """Build a VideoStreamTrack subclass at call time so we can capture the
    aiortc base class without importing it at module top-level (keeps the
    backend importable on systems without aiortc)."""

    class BusVideoTrack(base):  # type: ignore[misc, valid-type]
        kind = "video"

        def __init__(self) -> None:
            super().__init__()
            import time as _time
            self._frame_bus = frame_bus
            self._last_seq = 0
            self._fps_count = 0
            self._fps_started = _time.monotonic()
            try:
                import numpy as np  # noqa: WPS433
                self._np = np
            except ImportError:
                self._np = None

        async def recv(self) -> Any:
            pts, time_base = await self.next_timestamp()
            loop = asyncio.get_running_loop()
            bgr = await loop.run_in_executor(None, self._next_bgr)
            vf = av.VideoFrame.from_ndarray(bgr, format="bgr24")
            vf.pts = pts
            vf.time_base = time_base
            self._fps_tick()
            return vf

        def _next_bgr(self) -> Any:
            # Wait for a strictly-newer frame so the encoder always sees fresh
            # content. Returning duplicates makes H.264 emit skip-only frames
            # which the browser renders as a frozen image. If the camera is
            # slow, the encoder paces with it (visible as lower fps but still
            # moving). If the camera dies, we fall back to a black frame so
            # the WebRTC stream doesn't hang and the client's stall detector
            # can reconnect.
            frame = self._frame_bus.wait_new(self._last_seq, timeout=2.0)
            if frame is None or frame.seq <= self._last_seq:
                if self._np is not None:
                    return self._np.zeros((target_size, target_size, 3), dtype=self._np.uint8)
                raise RuntimeError("numpy unavailable")
            self._last_seq = frame.seq
            bgr = frame.bgr
            if self._np is None:
                raise RuntimeError("numpy unavailable")
            if bgr.shape[0] != target_size or bgr.shape[1] != target_size:
                bgr = self._resize_nearest(bgr)
            return self._np.ascontiguousarray(bgr)

        def _resize_nearest(self, bgr: Any) -> Any:
            assert self._np is not None
            src_h, src_w = bgr.shape[:2]
            y_idx = self._np.linspace(0, src_h - 1, target_size).astype(self._np.intp)
            x_idx = self._np.linspace(0, src_w - 1, target_size).astype(self._np.intp)
            return bgr[y_idx][:, x_idx]

        def _fps_tick(self) -> None:
            import time as _time
            self._fps_count += 1
            now = _time.monotonic()
            if now - self._fps_started >= 5.0:
                fps = self._fps_count / (now - self._fps_started)
                print(f"[webrtc] encoded {fps:.1f} fps", flush=True)
                self._fps_count = 0
                self._fps_started = now

    return BusVideoTrack()
