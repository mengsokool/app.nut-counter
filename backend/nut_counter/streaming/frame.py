from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class Frame:
    """A camera frame in canonical format.

    bgr   : ndarray (H, W, 3) uint8 in BGR order — every source normalizes here.
    seq   : monotonically increasing per-source counter; consumers track this
            to detect new frames without reprocessing.
    ts    : monotonic seconds when the frame was captured.
    """

    bgr: "np.ndarray"
    seq: int
    ts: float


class FrameBus:
    """Latest-only frame slot with condition-variable wakeups.

    Producer overwrites the slot atomically. Consumers either grab the latest
    or block until a frame newer than `last_seq` arrives. Slow consumers drop
    intermediate frames by design — keeps memory bounded and prevents backlog
    that would otherwise compound into stalls.
    """

    def __init__(self) -> None:
        self._cv = threading.Condition()
        self._latest: Frame | None = None
        self._closed = False

    def publish(self, bgr: "np.ndarray") -> Frame:
        with self._cv:
            seq = (self._latest.seq + 1) if self._latest is not None else 1
            frame = Frame(bgr=bgr, seq=seq, ts=time.monotonic())
            self._latest = frame
            self._cv.notify_all()
            return frame

    def latest(self) -> Frame | None:
        with self._cv:
            return self._latest

    def wait_new(self, last_seq: int, timeout: float = 2.0) -> Frame | None:
        """Block until a frame with seq > last_seq is available, or timeout/close."""
        with self._cv:
            self._cv.wait_for(
                lambda: self._closed
                or (self._latest is not None and self._latest.seq > last_seq),
                timeout=timeout,
            )
            if self._closed:
                return None
            return self._latest

    def close(self) -> None:
        with self._cv:
            self._closed = True
            self._cv.notify_all()

    @property
    def closed(self) -> bool:
        return self._closed
