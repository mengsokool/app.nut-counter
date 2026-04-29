import tempfile
import unittest
from pathlib import Path

from nut_counter.config import ModelConfig, default_config, load_config, parse_config, save_config
from nut_counter.hardware.inference import validate_model_config
from nut_counter.server import browse_files


class ConfigTests(unittest.TestCase):
    def test_default_config_uses_mock_model(self) -> None:
        config = default_config()
        self.assertFalse(config.safe_mode)
        self.assertEqual(config.model.engine, "mock")
        self.assertEqual(config.camera.source, "auto")
        self.assertEqual(config.camera.width, config.camera.height)

    def test_rejects_unknown_camera_source(self) -> None:
        with self.assertRaises(ValueError):
            parse_config({"camera": {"source": "usb"}})

    def test_rejects_unknown_model_engine(self) -> None:
        with self.assertRaises(ValueError):
            parse_config({"model": {"engine": "coreml"}})

    def test_v4l2_camera_source_requires_device(self) -> None:
        with self.assertRaises(ValueError):
            parse_config({"camera": {"source": "v4l2"}})

    def test_avfoundation_camera_source_requires_device(self) -> None:
        with self.assertRaises(ValueError):
            parse_config({"camera": {"source": "avfoundation"}})

    def test_rejects_invalid_idle_camera_fps(self) -> None:
        with self.assertRaises(ValueError):
            parse_config({"camera": {"fps": 10, "idle_fps": 20}})

    def test_ignores_unknown_config_keys_for_forward_compatibility(self) -> None:
        config = parse_config(
            {
                "camera": {
                    "source": "mock",
                    "future_camera_key": "ignored",
                },
                "future_root_key": "ignored",
            }
        )
        self.assertEqual(config.camera.source, "mock")

    def test_rejects_same_gpio_pins(self) -> None:
        with self.assertRaises(ValueError):
            parse_config(
                {
                    "gpio": {
                        "tray_sensor_pin": 17,
                        "relay_pin": 17,
                    }
                }
            )

    def test_save_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            config = parse_config(
                {
                    "camera": {
                        "flip_horizontal": True,
                        "flip_vertical": True,
                    }
                }
            )
            save_config(config, path)
            loaded = load_config(path)
            self.assertEqual(loaded.counting.selected_part_type, "nut")
            self.assertTrue(loaded.camera.flip_horizontal)
            self.assertTrue(loaded.camera.flip_vertical)

    def test_model_validation_checks_required_labels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            labels_path = Path(directory) / "labels.txt"
            labels_path.write_text("nut\n", encoding="utf-8")
            result = validate_model_config(
                ModelConfig(engine="onnx", model_path="/tmp/missing.onnx", labels_path=str(labels_path))
            )
        by_key = {check["key"]: check for check in result["checks"]}
        self.assertEqual(by_key["class_nut"]["status"], "ok")
        self.assertEqual(by_key["class_washer"]["status"], "error")

    def test_file_browser_marks_model_files_selectable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "model.onnx"
            model_path.write_bytes(b"")
            result = browse_files(directory, kind="model")
        entries = {entry["name"]: entry for entry in result["entries"]}
        self.assertTrue(entries["model.onnx"]["selectable"])


if __name__ == "__main__":
    unittest.main()
