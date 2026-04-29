import unittest

from nut_counter.config import CameraConfig, default_config, parse_config
from nut_counter.hardware import create_hardware_stack
from nut_counter.streaming import (
    ffmpeg_flip_filter,
    scan_camera_sources,
    square_frame_size,
)


class HardwareFactoryTests(unittest.TestCase):
    def test_non_pi_uses_mock_hardware_without_linux_dependencies(self) -> None:
        stack = create_hardware_stack(default_config())
        try:
            self.assertIn(stack.gpio.status, {"mock", "ready", "error"})
            self.assertIn(stack.frame_source.status, {"mock", "ready", "missing", "error"})
            self.assertIn(stack.inference.status, {"mock", "ready", "missing"})
        finally:
            stack.close()

    def test_mock_camera_source_forces_mock_camera(self) -> None:
        stack = create_hardware_stack(parse_config({"camera": {"source": "mock"}}))
        try:
            self.assertIn(stack.frame_source.status, {"mock", "missing"})
        finally:
            stack.close()

    def test_onnx_engine_reports_missing_model_file(self) -> None:
        stack = create_hardware_stack(
            parse_config(
                {
                    "camera": {"source": "mock"},
                    "model": {"engine": "onnx", "model_path": "/tmp/missing.onnx"},
                }
            )
        )
        try:
            self.assertEqual(stack.inference.status, "missing")
            self.assertIn("ONNX model not found", stack.inference.detail)
        finally:
            stack.close()

    def test_camera_output_is_center_square(self) -> None:
        self.assertEqual(square_frame_size(CameraConfig(width=1280, height=720)), (720, 720))
        self.assertEqual(square_frame_size(CameraConfig(width=1080, height=1080)), (1080, 1080))

    def test_camera_flip_filter_matches_config(self) -> None:
        self.assertIsNone(ffmpeg_flip_filter(CameraConfig()))
        self.assertEqual(
            ffmpeg_flip_filter(CameraConfig(flip_horizontal=True)),
            "hflip",
        )
        self.assertEqual(
            ffmpeg_flip_filter(CameraConfig(flip_horizontal=True, flip_vertical=True)),
            "hflip,vflip",
        )

    def test_camera_scan_always_includes_auto_and_mock(self) -> None:
        source_ids = {source["id"] for source in scan_camera_sources()}
        self.assertIn("auto", source_ids)
        self.assertIn("mock", source_ids)


if __name__ == "__main__":
    unittest.main()
