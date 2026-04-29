"""Backward-compat re-exports.

The streaming pipeline now owns the camera lifecycle (see `..streaming`).
This module exists only so older imports of the helpers keep working.
"""

from ..streaming.sources import (
    CameraSourceInfo,
    ffmpeg_flip_filter,
    scan_camera_sources,
    square_frame_size,
)

__all__ = [
    "CameraSourceInfo",
    "ffmpeg_flip_filter",
    "scan_camera_sources",
    "square_frame_size",
]
