from __future__ import annotations

from dataclasses import dataclass

from ..config import AppConfig
from ..config import GpioConfig, ModelConfig
from ..streaming import FrameSource, create_frame_source
from .gpio import GpioController, GpioZeroController, MockGpioController
from .inference import (
    HailoYoloEngine,
    InferenceEngine,
    MockInferenceEngine,
    OnnxYoloEngine,
)
from .platform import RuntimePlatform, detect_platform


@dataclass
class HardwareStack:
    gpio: GpioController
    frame_source: FrameSource
    inference: InferenceEngine
    platform: RuntimePlatform

    # Backward-compat alias used by older tests / callers.
    @property
    def camera(self) -> FrameSource:
        return self.frame_source

    def close(self) -> None:
        self.gpio.close()
        self.frame_source.close()
        self.inference.close()


def create_hardware_stack(config: AppConfig) -> HardwareStack:
    platform = detect_platform()

    gpio = create_gpio_controller(config.gpio, platform)
    inference = create_inference_engine(config.model)
    frame_source = create_frame_source(
        config.camera, is_raspberry_pi=platform.is_raspberry_pi
    )

    return HardwareStack(
        gpio=gpio,
        frame_source=frame_source,
        inference=inference,
        platform=platform,
    )


def create_gpio_controller(
    config: GpioConfig,
    platform: RuntimePlatform,
) -> GpioController:
    if platform.is_raspberry_pi:
        return GpioZeroController(config)
    return MockGpioController(config)


def create_inference_engine(config: ModelConfig) -> InferenceEngine:
    if config.engine == "onnx":
        return OnnxYoloEngine(config)
    if config.engine in {"hailo", "external"}:
        return HailoYoloEngine(config)
    return MockInferenceEngine(config)
