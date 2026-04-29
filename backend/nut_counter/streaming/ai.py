"""Continuous AI inference worker.

Pulls latest frames from the FrameBus, downsizes to the model input size
(default 640x640), runs the inference engine, and broadcasts detection results
to subscribers (SSE consumers in `server.py`, plus the count_once aggregator).

Pacing: capped at `target_fps` (default 5). If the engine takes longer than
the budget, the next iteration starts immediately — we never queue stale work.
"""

from __future__ import annotations

import queue
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Iterable

from .frame import FrameBus

if TYPE_CHECKING:
    from ..hardware.inference import InferenceEngine


AI_INPUT_SIZE = 640


@dataclass(frozen=True)
class Detection:
    """Normalized to [0, 1] in the AI input coordinate space (which is square,
    so it overlays cleanly on the streaming video at any resolution)."""

    label: str
    confidence: float
    x: float
    y: float
    w: float
    h: float


@dataclass
class DetectionResult:
    seq: int
    ts: float
    count: int
    processing_ms: int
    detections: list[Detection] = field(default_factory=list)
    part_type: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "ts": self.ts,
            "count": self.count,
            "processingMs": self.processing_ms,
            "partType": self.part_type,
            "detections": [
                {
                    "label": d.label,
                    "confidence": d.confidence,
                    "x": d.x,
                    "y": d.y,
                    "w": d.w,
                    "h": d.h,
                }
                for d in self.detections
            ],
        }


class DetectionBus:
    """Pub/sub for detection results. Subscribers receive a small bounded queue;
    on overflow we drop the oldest item (preview consumers care about latest)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subs: list[queue.Queue[DetectionResult | None]] = []
        self._latest: DetectionResult | None = None

    def latest(self) -> DetectionResult | None:
        with self._lock:
            return self._latest

    def publish(self, result: DetectionResult) -> None:
        with self._lock:
            self._latest = result
            for q in self._subs:
                try:
                    q.put_nowait(result)
                except queue.Full:
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        q.put_nowait(result)
                    except queue.Full:
                        pass

    def subscribe(self) -> queue.Queue[DetectionResult | None]:
        q: queue.Queue[DetectionResult | None] = queue.Queue(maxsize=4)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[DetectionResult | None]) -> None:
        with self._lock:
            try:
                self._subs.remove(q)
            except ValueError:
                pass
        try:
            q.put_nowait(None)
        except queue.Full:
            pass


class AIWorker:
    """Background thread: bus → resize → engine → DetectionBus.

    `get_part_type` is a callable so the worker reflects config changes without
    needing to be restarted.
    """

    def __init__(
        self,
        frame_bus: FrameBus,
        engine: "InferenceEngine",
        get_part_type: Callable[[], str],
        *,
        target_fps: float = 5.0,
        input_size: int = AI_INPUT_SIZE,
    ) -> None:
        self.frame_bus = frame_bus
        self.engine = engine
        self.get_part_type = get_part_type
        self.target_fps = target_fps
        self.input_size = input_size
        self.detections = DetectionBus()
        self._closed = False
        self._history: deque[DetectionResult] = deque(maxlen=16)
        self._history_lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._closed = True
        self._thread.join(timeout=2.0)

    def recent(self, n: int) -> list[DetectionResult]:
        with self._history_lock:
            return list(self._history)[-n:]

    def _run(self) -> None:
        try:
            import numpy as np  # noqa: WPS433
        except ImportError:
            np = None  # type: ignore[assignment]

        last_seq = 0
        budget = 1.0 / self.target_fps if self.target_fps > 0 else 0.2

        while not self._closed:
            cycle_start = time.monotonic()
            frame = self.frame_bus.wait_new(last_seq, timeout=2.0)
            if frame is None:
                if self.frame_bus.closed:
                    break
                continue
            last_seq = frame.seq

            if np is not None and (
                frame.bgr.shape[0] != self.input_size
                or frame.bgr.shape[1] != self.input_size
            ):
                bgr = _resize_nearest(frame.bgr, self.input_size, np)
            else:
                bgr = frame.bgr

            part_type = self.get_part_type()
            started = time.perf_counter()
            try:
                result = self.engine.detect_frame(bgr, part_type)
            except Exception as error:  # noqa: BLE001
                # Don't kill the loop on a single inference failure.
                result = _empty_result(error)

            payload = DetectionResult(
                seq=frame.seq,
                ts=frame.ts,
                count=result["count"],
                processing_ms=max(1, int((time.perf_counter() - started) * 1000)),
                detections=list(result["detections"]),
                part_type=part_type,
            )
            self.detections.publish(payload)
            with self._history_lock:
                self._history.append(payload)

            elapsed = time.monotonic() - cycle_start
            if elapsed < budget:
                time.sleep(budget - elapsed)


def _empty_result(error: Exception) -> dict[str, Any]:
    return {"count": 0, "detections": []}


def _resize_nearest(bgr: Any, size: int, np: Any) -> Any:
    src_h, src_w = bgr.shape[:2]
    y_idx = np.linspace(0, src_h - 1, size).astype(np.intp)
    x_idx = np.linspace(0, src_w - 1, size).astype(np.intp)
    return np.ascontiguousarray(bgr[y_idx][:, x_idx])


def detections_from_bbox_payload(
    payload: dict[str, Any], *, input_size: int = AI_INPUT_SIZE
) -> list[Detection]:
    """Normalize raw bbox dicts (in pixel coords of the AI input) to [0,1]."""
    out: list[Detection] = []
    for raw in payload.get("detections", []) or []:
        bbox: Iterable[float] | None = raw.get("bbox") or raw.get("box")
        if bbox is None:
            x, y, w, h = (
                float(raw.get("x", 0)),
                float(raw.get("y", 0)),
                float(raw.get("w", 0)),
                float(raw.get("h", 0)),
            )
        else:
            x, y, w, h = (float(v) for v in bbox)
        out.append(
            Detection(
                label=str(raw.get("label", "")),
                confidence=float(raw.get("confidence", raw.get("score", 0.0))),
                x=max(0.0, min(1.0, x / input_size)),
                y=max(0.0, min(1.0, y / input_size)),
                w=max(0.0, min(1.0, w / input_size)),
                h=max(0.0, min(1.0, h / input_size)),
            )
        )
    return out
