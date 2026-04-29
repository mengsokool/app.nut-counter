from __future__ import annotations

import platform
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePlatform:
    system: str
    machine: str
    model: str

    @property
    def is_linux(self) -> bool:
        return self.system.lower() == "linux"

    @property
    def is_raspberry_pi(self) -> bool:
        return self.is_linux and "raspberry pi" in self.model.lower()


def detect_platform() -> RuntimePlatform:
    model = ""
    model_path = Path("/proc/device-tree/model")
    if model_path.exists():
        try:
            model = model_path.read_text(encoding="utf-8").replace("\x00", "").strip()
        except OSError:
            model = ""

    return RuntimePlatform(
        system=platform.system(),
        machine=platform.machine(),
        model=model,
    )
