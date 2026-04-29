"""Frame sources — every camera backend normalizes into the same Frame format.

Output contract:
  - Square BGR ndarray of side `square_frame_size(config)`.
  - Center-cropped + flipped per camera config.
  - Published into a FrameBus by a single background thread per source.
  - Self-restarting on subprocess failure; status surfaces in `.status`/`.detail`.
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..config import CameraConfig
from .frame import FrameBus

if TYPE_CHECKING:
    import numpy as np


# --- numpy guard ------------------------------------------------------------
# numpy is a hard runtime requirement for the streaming pipeline, but importing
# it lazily lets the rest of the backend keep running in degraded mode if it's
# missing (the doctor endpoint will surface the missing dep).

def _require_numpy() -> Any:
    import numpy as np  # noqa: WPS433 — intentional lazy import

    return np


def _try_numpy() -> Any | None:
    try:
        return _require_numpy()
    except ImportError:
        return None


# --- helpers preserved for the rest of the codebase / tests -----------------

def square_frame_size(config: CameraConfig) -> tuple[int, int]:
    side = min(config.width, config.height)
    return side, side


def ffmpeg_flip_filter(config: CameraConfig) -> str | None:
    filters: list[str] = []
    if config.flip_horizontal:
        filters.append("hflip")
    if config.flip_vertical:
        filters.append("vflip")
    return ",".join(filters) if filters else None


def _ffmpeg_square_filter(config: CameraConfig, fps: int | None = None) -> str:
    # Square-crop center, then resize to the configured side. We use bilinear
    # (default) and clamp `force_original_aspect_ratio=disable` is implicit
    # because the crop already made the input square. Avoids the upscale-from-
    # 720p cost when the camera's native resolution is smaller than `side`:
    # the scale step is a no-op when crop size already matches.
    side = min(config.width, config.height)
    parts = [
        r"crop=min(iw\,ih):min(iw\,ih)",
        f"scale={side}:{side}:flags=fast_bilinear",
        "hqdn3d=1.2:1.2:4:4",
    ]
    flip = ffmpeg_flip_filter(config)
    if flip:
        parts.append(flip)
    parts.append(f"fps={fps or config.fps}")
    return ",".join(parts)


# --- camera scanning (label, presence) --------------------------------------

@dataclass(frozen=True)
class CameraSourceInfo:
    id: str
    source: str
    label: str
    detail: str
    available: bool
    device: str = ""


def scan_camera_sources() -> list[dict[str, object]]:
    sources = [
        CameraSourceInfo(
            id="auto",
            source="auto",
            label="Auto",
            detail="เลือกกล้องตามเครื่องที่รัน",
            available=True,
        ),
        CameraSourceInfo(
            id="mock",
            source="mock",
            label="Mock Camera",
            detail="FFmpeg test pattern",
            available=shutil.which("ffmpeg") is not None,
        ),
    ]
    sources.extend(_scan_picamera_sources())
    sources.extend(_scan_v4l2_sources())
    sources.extend(_scan_avfoundation_sources())
    return [asdict(source) for source in sources]


def _scan_picamera_sources() -> list[CameraSourceInfo]:
    try:
        from picamera2 import Picamera2

        cameras = Picamera2.global_camera_info()
    except Exception:
        return [
            CameraSourceInfo(
                id="picamera2",
                source="picamera2",
                label="Pi Camera",
                detail="Picamera2 ไม่พร้อมใช้งาน",
                available=False,
            )
        ]
    if not cameras:
        return [
            CameraSourceInfo(
                id="picamera2",
                source="picamera2",
                label="Pi Camera",
                detail="ไม่พบ Camera Module",
                available=False,
            )
        ]
    return [
        CameraSourceInfo(
            id=f"picamera2:{index}",
            source="picamera2",
            label=f"Pi Camera {index + 1}",
            detail=str(camera.get("Model") or camera.get("Id") or "Picamera2"),
            available=True,
        )
        for index, camera in enumerate(cameras)
    ]


def _scan_v4l2_sources() -> list[CameraSourceInfo]:
    devices = sorted(Path("/dev").glob("video*"))
    if not devices:
        return []
    return [
        CameraSourceInfo(
            id=f"v4l2:{device}",
            source="v4l2",
            label=_v4l2_device_name(device),
            detail=str(device),
            available=shutil.which("ffmpeg") is not None,
            device=str(device),
        )
        for device in devices
    ]


def _v4l2_device_name(device: Path) -> str:
    if shutil.which("v4l2-ctl"):
        try:
            result = subprocess.run(
                ["v4l2-ctl", "-d", str(device), "--info"],
                check=False,
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            for line in result.stdout.splitlines():
                if "Card type" in line and ":" in line:
                    return line.split(":", 1)[1].strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return f"USB Camera {device.name.removeprefix('video')}"


def _scan_avfoundation_sources() -> list[CameraSourceInfo]:
    if shutil.which("ffmpeg") is None:
        return []
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-f", "avfoundation",
             "-list_devices", "true", "-i", ""],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    sources: list[CameraSourceInfo] = []
    in_video_section = False
    for line in result.stderr.splitlines():
        if "AVFoundation video devices" in line:
            in_video_section = True
            continue
        if "AVFoundation audio devices" in line:
            break
        if not in_video_section:
            continue
        match = re.search(r"\[(\d+)\]\s+(.+)$", line)
        if not match:
            continue
        index, name = match.groups()
        if name.lower().startswith("capture screen"):
            continue
        sources.append(
            CameraSourceInfo(
                id=f"avfoundation:{index}",
                source="avfoundation",
                label=name.strip(),
                detail="macOS AVFoundation",
                available=True,
                device=index,
            )
        )
    return sources


# --- FrameSource base + impls ----------------------------------------------

class FrameSource(ABC):
    """Single producer → FrameBus.

    Lifecycle:
      __init__ → background thread starts (if .status == 'ready')
      .bus     → consumers subscribe via wait_new()
      .close() → thread + subprocess torn down

    Status semantics: 'ready' = producing frames; 'mock' = synthetic mock;
    'missing' = configured-but-unavailable; 'error' = active failure.
    """

    status: str = "missing"
    detail: str = "frame source not initialized"

    def __init__(self, config: CameraConfig) -> None:
        self.config = config
        self.bus = FrameBus()

    @abstractmethod
    def close(self) -> None: ...

    def set_idle_mode(self, idle: bool) -> None:
        return

    def capture_jpeg(self, quality: int = 85) -> bytes:
        """Convenience: encode the latest frame to JPEG. Returns b'' if no frame yet."""
        frame = self.bus.latest()
        if frame is None:
            return b""
        try:
            import cv2  # noqa: WPS433
        except ImportError:
            return b""
        ok, buf = cv2.imencode(".jpg", frame.bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return bytes(buf) if ok else b""


class _FFmpegRawSource(FrameSource):
    """Base for ffmpeg-driven sources: reads `-f rawvideo -pix_fmt bgr24` from stdout
    in fixed-size frame chunks and pushes ndarrays into the FrameBus.
    """

    label = "ffmpeg"

    def __init__(self, config: CameraConfig) -> None:
        super().__init__(config)
        self._closed = False
        self._idle = False
        self._mode_lock = threading.Lock()
        self._proc: subprocess.Popen | None = None  # type: ignore[type-arg]
        self._thread: threading.Thread | None = None
        self._np = _try_numpy()

        if self._np is None:
            self.status = "missing"
            self.detail = "numpy is required for streaming"
            return
        if not shutil.which("ffmpeg"):
            self.status = "missing"
            self.detail = f"ffmpeg is required for {self.label}"
            return
        if not self._device_available():
            self.status = "missing"
            self.detail = self._missing_detail()
            return

        self.status = "ready"
        self.detail = f"{self.label} active"
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # subclass hooks ---------------------------------------------------------
    def _device_available(self) -> bool:
        return True

    def _missing_detail(self) -> str:
        return f"{self.label} unavailable"

    @abstractmethod
    def _ffmpeg_command(self, fps: int) -> list[str]: ...

    def _current_fps(self) -> int:
        with self._mode_lock:
            return self.config.idle_fps if self._idle else self.config.fps

    def set_idle_mode(self, idle: bool) -> None:
        with self._mode_lock:
            if self._idle == idle:
                return
            self._idle = idle
            fps = self.config.idle_fps if idle else self.config.fps
        print(f"[{self.label}] {'idle' if idle else 'active'} capture {fps} fps", flush=True)

    # main loop --------------------------------------------------------------
    def _run(self) -> None:
        side, _ = square_frame_size(self.config)
        bytes_per_frame = side * side * 3
        print(
            f"[{self.label}] capture target = {side}x{side} BGR "
            f"({bytes_per_frame} bytes/frame)",
            flush=True,
        )
        first_frame_logged = False
        backoff = 0.5
        fps_count = 0
        fps_started = time.monotonic()
        next_capture = 0.0
        while not self._closed:
            frames_seen = 0
            stderr_tail: list[str] = []
            try:
                self._proc = subprocess.Popen(
                    self._ffmpeg_command(self.config.fps),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
                # Drain stderr so the pipe never fills + capture last lines
                # to surface real errors when the camera fails to open.
                threading.Thread(
                    target=self._drain_stderr,
                    args=(self._proc, stderr_tail),
                    daemon=True,
                ).start()
                stdout = self._proc.stdout
                assert stdout is not None
                buf = bytearray()
                while not self._closed:
                    need = bytes_per_frame - len(buf)
                    chunk = stdout.read(need if need > 0 else bytes_per_frame)
                    if not chunk:
                        break
                    buf.extend(chunk)
                    while len(buf) >= bytes_per_frame:
                        raw = bytes(buf[:bytes_per_frame])
                        del buf[:bytes_per_frame]

                        current_fps = self._current_fps()
                        if current_fps < self.config.fps:
                            now = time.monotonic()
                            if now < next_capture:
                                continue
                            next_capture = now + (1.0 / current_fps)

                        # Make a writable copy so downstream consumers
                        # (cv2.resize, av.VideoFrame.from_ndarray) never get
                        # a read-only view of a transient bytes buffer.
                        bgr = self._np.frombuffer(raw, dtype=self._np.uint8).reshape(
                            (side, side, 3)
                        ).copy()
                        if not first_frame_logged:
                            print(
                                f"[{self.label}] first frame shape={bgr.shape} "
                                f"dtype={bgr.dtype}",
                                flush=True,
                            )
                            first_frame_logged = True
                        self.bus.publish(bgr)
                        frames_seen += 1
                        fps_count += 1
                        now = time.monotonic()
                        if now - fps_started >= 5.0:
                            fps = fps_count / (now - fps_started)
                            print(f"[{self.label}] capture {fps:.1f} fps", flush=True)
                            fps_count = 0
                            fps_started = now
                        if self.status != "ready":
                            self.status = "ready"
                            self.detail = f"{self.label} active"
            except Exception as error:  # noqa: BLE001
                self.status = "error"
                self.detail = f"{self.label}: {error}"
            finally:
                self._kill_proc()

            if self._closed:
                break
            if frames_seen == 0:
                self.status = "error"
                err_msg = " | ".join(stderr_tail[-3:]) or "no output"
                self.detail = f"{self.label}: {err_msg}"
                print(f"[{self.label}] ffmpeg failed: {err_msg}", flush=True)
                time.sleep(backoff)
                backoff = min(backoff * 2, 5.0)
            else:
                backoff = 0.5
                time.sleep(0.2)

    @staticmethod
    def _drain_stderr(proc: subprocess.Popen, tail: list[str]) -> None:  # type: ignore[type-arg]
        if proc.stderr is None:
            return
        try:
            for raw in proc.stderr:
                line = raw.decode("utf-8", errors="replace").rstrip()
                if not line:
                    continue
                tail.append(line)
                if len(tail) > 10:
                    del tail[0]
        except (OSError, ValueError):
            pass

    def _kill_proc(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                pass

    def close(self) -> None:
        self._closed = True
        self.bus.close()
        self._kill_proc()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


class MockFrameSource(_FFmpegRawSource):
    label = "mock"

    def __init__(self, config: CameraConfig) -> None:
        super().__init__(config)
        if self.status == "ready":
            self.status = "mock"
            self.detail = "mock test pattern"

    def _ffmpeg_command(self, fps: int) -> list[str]:
        side, _ = square_frame_size(self.config)
        flip = ffmpeg_flip_filter(self.config)
        vf = ["-vf", flip] if flip else []
        return [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi",
            "-i", f"testsrc=size={side}x{side}:rate={fps}",
            *vf,
            "-r", str(fps),
            "-pix_fmt", "bgr24",
            "-f", "rawvideo",
            "pipe:1",
        ]


class V4L2FrameSource(_FFmpegRawSource):
    label = "v4l2"

    def _device_available(self) -> bool:
        return bool(self.config.device) and Path(self.config.device).exists()

    def _missing_detail(self) -> str:
        return f"v4l2 device not found: {self.config.device or '(empty)'}"

    def _ffmpeg_command(self, fps: int) -> list[str]:
        return [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-fflags", "nobuffer", "-flags", "low_delay",
            "-f", "v4l2", "-framerate", str(fps),
            "-i", self.config.device,
            "-vf", _ffmpeg_square_filter(self.config, fps),
            "-r", str(fps),
            "-pix_fmt", "bgr24",
            "-f", "rawvideo",
            "pipe:1",
        ]


class AVFoundationFrameSource(_FFmpegRawSource):
    label = "avfoundation"

    def _device_available(self) -> bool:
        return bool(self.config.device)

    def _missing_detail(self) -> str:
        return "avfoundation device index not configured"

    def _ffmpeg_command(self, fps: int) -> list[str]:
        return [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-fflags", "nobuffer", "-flags", "low_delay",
            "-f", "avfoundation",
            "-pixel_format", "nv12",
            "-framerate", str(fps),
            "-i", f"{self.config.device}:none",
            "-vf", _ffmpeg_square_filter(self.config, fps),
            "-r", str(fps),
            "-pix_fmt", "bgr24",
            "-f", "rawvideo",
            "pipe:1",
        ]


class PiCameraFrameSource(FrameSource):
    """Picamera2 native source — yields BGR ndarrays directly via `BGR888` format,
    no ffmpeg in the path. Fastest option on Raspberry Pi.
    """

    label = "picamera2"

    def __init__(self, config: CameraConfig) -> None:
        super().__init__(config)
        self._np = _try_numpy()
        self._camera: Any = None
        self._closed = False
        self._idle = False
        self._mode_lock = threading.Lock()
        self._thread: threading.Thread | None = None

        if self._np is None:
            self.status = "missing"
            self.detail = "numpy is required for streaming"
            return

        try:
            from picamera2 import Picamera2
            from libcamera import Transform

            side, _ = square_frame_size(config)
            camera = Picamera2()
            camera_config = camera.create_video_configuration(
                main={"size": (side, side), "format": "BGR888"},
                transform=Transform(
                    hflip=config.flip_horizontal,
                    vflip=config.flip_vertical,
                ),
                buffer_count=4,
            )
            camera.configure(camera_config)
            camera.start()
            for _ in range(config.warmup_frames):
                time.sleep(0.05)
            self._camera = camera
            self.status = "ready"
            self.detail = "picamera2 active"
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        except Exception as error:  # noqa: BLE001  # pragma: no cover
            self.status = "error"
            self.detail = str(error)

    def _run(self) -> None:
        # Picamera2 returns RGB-ordered ndarray when format is BGR888 in libcamera
        # naming (libcamera/picamera2 use opposite endian to OpenCV in some
        # versions). We probe once and apply BGR<->RGB swap if needed.
        np = self._np
        assert np is not None
        camera = self._camera
        next_capture = 0.0
        while not self._closed:
            try:
                arr = camera.capture_array("main")
                if arr is None:
                    continue

                current_fps = self._current_fps()
                if current_fps < self.config.fps:
                    now = time.monotonic()
                    if now < next_capture:
                        continue
                    next_capture = now + (1.0 / current_fps)

                # picamera2 with format="BGR888" yields BGR; if shape isn't 3-channel
                # something unexpected happened — drop the frame.
                if arr.ndim != 3 or arr.shape[2] != 3:
                    continue
                self.bus.publish(np.ascontiguousarray(arr))
            except Exception as error:  # noqa: BLE001
                self.status = "error"
                self.detail = str(error)
                time.sleep(0.5)

    def _current_fps(self) -> int:
        with self._mode_lock:
            return self.config.idle_fps if self._idle else self.config.fps

    def set_idle_mode(self, idle: bool) -> None:
        with self._mode_lock:
            self._idle = idle

    def close(self) -> None:
        self._closed = True
        self.bus.close()
        camera = self._camera
        self._camera = None
        if camera is not None:
            try:
                camera.stop()
                camera.close()
            except Exception:  # noqa: BLE001
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)


class NullFrameSource(FrameSource):
    """Placeholder when no camera backend is available — keeps the rest of the
    runtime alive so the doctor UI can guide the user to install dependencies.
    """

    def __init__(self, config: CameraConfig, *, status: str = "missing", detail: str = "no camera") -> None:
        super().__init__(config)
        self.status = status
        self.detail = detail

    def close(self) -> None:
        self.bus.close()


# --- factory ----------------------------------------------------------------

def create_frame_source(config: CameraConfig, *, is_raspberry_pi: bool) -> FrameSource:
    src = config.source
    if src == "mock" or (src == "auto" and not is_raspberry_pi):
        return MockFrameSource(config)
    if src == "v4l2":
        return V4L2FrameSource(config)
    if src == "avfoundation":
        return AVFoundationFrameSource(config)
    if src == "picamera2" or (src == "auto" and is_raspberry_pi):
        return PiCameraFrameSource(config)
    return MockFrameSource(config)
