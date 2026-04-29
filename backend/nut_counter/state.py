from __future__ import annotations

import time
from dataclasses import asdict, dataclass


@dataclass
class SystemState:
    safeMode: bool = True
    trayPresent: bool = False
    lightOn: bool = False
    selectedPartType: str = "nut"
    count: int = 0
    processingMs: int = 0
    camera: str = "mock"
    model: str = "mock"
    gpio: str = "mock"
    updatedAt: float = time.time()

    def as_dict(self) -> dict[str, object]:
        self.updatedAt = time.time()
        return asdict(self)
