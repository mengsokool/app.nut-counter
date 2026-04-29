"""Unified streaming pipeline.

Single camera process produces raw BGR frames into a latest-only FrameBus.
Two consumers branch off:
  - AI pipeline: resize 640x640, run inference at low FPS, publish detections.
  - Stream pipeline: resize 1080x1080, encode H.264 once via aiortc + MediaRelay,
    fan out to all WebRTC peers.

Frame standard: numpy ndarray, shape (H, W, 3), dtype uint8, BGR.
"""

from .frame import Frame, FrameBus
from .sources import (
    FrameSource,
    create_frame_source,
    scan_camera_sources,
    ffmpeg_flip_filter,
    square_frame_size,
)
from .ai import AIWorker, Detection, DetectionResult, DetectionBus
from .webrtc import StreamingWebRTC, WebRTCUnavailable

__all__ = [
    "Frame",
    "FrameBus",
    "FrameSource",
    "create_frame_source",
    "scan_camera_sources",
    "ffmpeg_flip_filter",
    "square_frame_size",
    "AIWorker",
    "Detection",
    "DetectionResult",
    "DetectionBus",
    "StreamingWebRTC",
    "WebRTCUnavailable",
]
