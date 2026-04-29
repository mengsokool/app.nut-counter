from __future__ import annotations

import os
from abc import ABC, abstractmethod

from ..config import GpioConfig


class GpioController(ABC):
    status = "missing"
    detail = "GPIO controller not initialized"

    @abstractmethod
    def read_tray_present(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def set_light(self, enabled: bool) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


class MockGpioController(GpioController):
    status = "mock"
    detail = "mock GPIO active"

    def __init__(self, config: GpioConfig) -> None:
        self.config = config
        self._tray_present = False
        self._light_on = False

    def read_tray_present(self) -> bool:
        return self._tray_present

    def set_light(self, enabled: bool) -> None:
        self._light_on = enabled

    def close(self) -> None:
        self._light_on = False


class GpioZeroController(GpioController):
    def __init__(self, config: GpioConfig) -> None:
        self.config = config
        self._sensor = None
        self._relay = None
        os.environ.setdefault("GPIOZERO_PIN_FACTORY", "lgpio")

        try:
            from gpiozero import DigitalInputDevice, OutputDevice

            bounce_time = config.debounce_ms / 1000 if config.debounce_ms else None
            active_state = False if config.active_low else True
            self._sensor = DigitalInputDevice(
                config.tray_sensor_pin,
                pull_up=True,
                active_state=active_state,
                bounce_time=bounce_time,
            )
            self._relay = OutputDevice(
                config.relay_pin,
                active_high=not config.active_low,
                initial_value=False,
            )
            self.status = "ready"
            self.detail = "gpiozero/lgpio active"
        except Exception as error:  # pragma: no cover - requires Raspberry Pi GPIO
            self.status = "error"
            self.detail = str(error)

    def read_tray_present(self) -> bool:
        if self._sensor is None:
            return False
        return bool(self._sensor.is_active)

    def set_light(self, enabled: bool) -> None:
        if self._relay is None:
            return
        if enabled:
            self._relay.on()
        else:
            self._relay.off()

    def close(self) -> None:
        if self._relay is not None:
            self._relay.off()
            self._relay.close()
        if self._sensor is not None:
            self._sensor.close()
