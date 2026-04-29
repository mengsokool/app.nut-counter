from __future__ import annotations

import json
import os
import platform
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def default_config_path() -> Path:
    configured_path = os.environ.get("NUT_COUNTER_CONFIG")
    if configured_path:
        return Path(configured_path)
    if platform.system().lower() == "linux":
        return Path("/etc/nut-counter/config.json")
    return PROJECT_ROOT / ".nut-counter" / "config.json"


DEFAULT_CONFIG_PATH = default_config_path()


@dataclass(frozen=True)
class GpioConfig:
    tray_sensor_pin: int = 17
    relay_pin: int = 27
    active_low: bool = False
    debounce_ms: int = 80


@dataclass(frozen=True)
class CameraConfig:
    source: str = "auto"
    device: str = ""
    width: int = 1280
    height: int = 1280
    warmup_frames: int = 5
    exposure_mode: str = "auto"
    flip_horizontal: bool = False
    flip_vertical: bool = False


@dataclass(frozen=True)
class ModelConfig:
    engine: str = "mock"
    model_path: str = ""
    hef_path: str = "/var/lib/nut-counter/models/yolo11n.hef"
    labels_path: str = "/var/lib/nut-counter/models/labels.json"
    inference_command: list[str] = field(default_factory=list)
    confidence_threshold: float = 0.45
    nms_threshold: float = 0.5


@dataclass(frozen=True)
class CountingConfig:
    stable_frames: int = 5
    timeout_ms: int = 2500
    selected_part_type: str = "nut"


@dataclass(frozen=True)
class KioskConfig:
    browser: str = "firefox-esr"
    url: str = "http://127.0.0.1:8787"
    profile_path: str = "/var/lib/nut-counter/firefox-profile"


@dataclass(frozen=True)
class AppConfig:
    gpio: GpioConfig = field(default_factory=GpioConfig)
    camera: CameraConfig = field(default_factory=CameraConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    counting: CountingConfig = field(default_factory=CountingConfig)
    kiosk: KioskConfig = field(default_factory=KioskConfig)
    safe_mode: bool = False


def default_config() -> AppConfig:
    return AppConfig()


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return default_config()

    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    return parse_config(raw)


def save_config(config: AppConfig, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(config), ensure_ascii=False, indent=2)

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        handle.write(payload)
        handle.write("\n")
        temp_path = Path(handle.name)

    temp_path.replace(path)


def dataclass_kwargs(dataclass_type: type[Any], raw: dict[str, Any]) -> dict[str, Any]:
    allowed = {item.name for item in fields(dataclass_type)}
    return {key: value for key, value in raw.items() if key in allowed}


def parse_config(raw: dict[str, Any]) -> AppConfig:
    config = AppConfig(
        gpio=GpioConfig(**dataclass_kwargs(GpioConfig, raw.get("gpio", {}))),
        camera=CameraConfig(**dataclass_kwargs(CameraConfig, raw.get("camera", {}))),
        model=ModelConfig(**dataclass_kwargs(ModelConfig, raw.get("model", {}))),
        counting=CountingConfig(**dataclass_kwargs(CountingConfig, raw.get("counting", {}))),
        kiosk=KioskConfig(**dataclass_kwargs(KioskConfig, raw.get("kiosk", {}))),
        safe_mode=bool(raw.get("safe_mode", True)),
    )
    validate_config(config)
    return config


def validate_config(config: AppConfig) -> None:
    if config.gpio.tray_sensor_pin == config.gpio.relay_pin:
        raise ValueError("GPIO tray sensor pin and relay pin must differ")
    if config.gpio.debounce_ms < 0 or config.gpio.debounce_ms > 5000:
        raise ValueError("GPIO debounce_ms must be between 0 and 5000")
    if config.camera.width < 320 or config.camera.height < 240:
        raise ValueError("Camera resolution is too small")
    if config.camera.source not in {"auto", "mock", "picamera2", "v4l2", "avfoundation"}:
        raise ValueError("Camera source must be auto, mock, picamera2, v4l2, or avfoundation")
    if config.camera.source in {"v4l2", "avfoundation"} and not config.camera.device:
        raise ValueError(f"Camera device is required for {config.camera.source} source")
    if config.model.engine not in {"mock", "hailo", "external", "onnx"}:
        raise ValueError("Model engine must be mock, hailo, external, or onnx")
    if config.counting.stable_frames < 1:
        raise ValueError("Counting stable_frames must be at least 1")
    if config.counting.timeout_ms < 100:
        raise ValueError("Counting timeout_ms must be at least 100")
    if not 0 <= config.model.confidence_threshold <= 1:
        raise ValueError("Model confidence_threshold must be between 0 and 1")
    if not 0 <= config.model.nms_threshold <= 1:
        raise ValueError("Model nms_threshold must be between 0 and 1")
    if not isinstance(config.model.inference_command, list):
        raise ValueError("Model inference_command must be a list of command arguments")


def config_to_dict(config: AppConfig) -> dict[str, Any]:
    return asdict(config)
