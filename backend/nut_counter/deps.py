from __future__ import annotations

import fcntl
import importlib.util
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Iterator


class Dep(ABC):
    def __init__(
        self,
        key: str,
        label: str,
        description: str,
        apt_packages: list[str],
    ) -> None:
        self.key = key
        self.label = label
        self.description = description
        self.apt_packages = apt_packages

    @abstractmethod
    def is_installed(self) -> bool: ...

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "installed": self.is_installed(),
            "apt_packages": self.apt_packages,
        }


class BinaryDep(Dep):
    def __init__(
        self,
        key: str,
        label: str,
        description: str,
        binary: str,
        apt_packages: list[str],
    ) -> None:
        super().__init__(key, label, description, apt_packages)
        self.binary = binary

    def is_installed(self) -> bool:
        return shutil.which(self.binary) is not None


class PythonDep(Dep):
    def __init__(
        self,
        key: str,
        label: str,
        description: str,
        module: str,
        apt_packages: list[str],
    ) -> None:
        super().__init__(key, label, description, apt_packages)
        self.module = module

    def is_installed(self) -> bool:
        return importlib.util.find_spec(self.module) is not None


# ── Dependency registry ───────────────────────────────────────────────────────
# Only packages listed here can ever be installed through this interface.
DEPENDENCIES: list[Dep] = [
    BinaryDep(
        key="ffmpeg",
        label="FFmpeg",
        description="Video encoding for camera streaming",
        binary="ffmpeg",
        apt_packages=["ffmpeg"],
    ),
    PythonDep(
        key="picamera2",
        label="picamera2",
        description="Raspberry Pi camera library",
        module="picamera2",
        apt_packages=["python3-picamera2"],
    ),
    PythonDep(
        key="aiortc",
        label="aiortc",
        description="Backend-owned WebRTC video transport",
        module="aiortc",
        apt_packages=["python3-aiortc"],
    ),
    PythonDep(
        key="pyav",
        label="PyAV",
        description="Video frame encoding for WebRTC video tracks",
        module="av",
        apt_packages=["python3-av"],
    ),
    PythonDep(
        key="numpy",
        label="NumPy",
        description="Frame buffer arrays for the streaming pipeline",
        module="numpy",
        apt_packages=["python3-numpy"],
    ),
    PythonDep(
        key="onnxruntime",
        label="ONNX Runtime",
        description="ONNX model inference engine",
        module="onnxruntime",
        apt_packages=["python3-onnxruntime"],
    ),
    PythonDep(
        key="opencv",
        label="OpenCV",
        description="Frame resize / JPEG encode for AI + streaming",
        module="cv2",
        apt_packages=["python3-opencv"],
    ),
]

_BY_KEY: dict[str, Dep] = {d.key: d for d in DEPENDENCIES}

# ── Sentinels emitted by stream_install ──────────────────────────────────────
DONE = "__done__"
ERROR_PREFIX = "__error__ "


def check_all() -> list[dict[str, object]]:
    return [dep.as_dict() for dep in DEPENDENCIES]


def is_apt_available() -> bool:
    return shutil.which("apt-get") is not None


def sudo_needs_password() -> bool:
    """True when sudo requires a password on this system."""
    if not shutil.which("sudo"):
        return False
    try:
        r = subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=5)
        return r.returncode != 0
    except (subprocess.TimeoutExpired, OSError):
        return True


def _apt_is_locked() -> bool:
    """True when another process holds the dpkg/apt lock."""
    lock_paths = [
        "/var/lib/dpkg/lock-frontend",
        "/var/lib/apt/lists/lock",
    ]
    fuser_bin = shutil.which("fuser")
    for path in lock_paths:
        if not os.path.exists(path):
            continue
        if fuser_bin:
            try:
                # fuser exits 0 when at least one process holds the file
                r = subprocess.run([fuser_bin, path], capture_output=True, timeout=3)
                if r.returncode == 0:
                    return True
            except (subprocess.TimeoutExpired, OSError):
                pass
        else:
            # Fallback: attempt a non-blocking exclusive lock
            try:
                with open(path) as f:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(f, fcntl.LOCK_UN)
            except OSError:
                return True
    return False


def stream_install(keys: list[str], sudo_password: str | None) -> Iterator[str]:
    """
    Install the packages for the given dependency keys via apt-get.

    Yields log lines from apt-get stdout/stderr merged, then one sentinel:
      DONE               → success
      "__error__ <msg>"  → failure
    """
    # ── Whitelist enforcement ─────────────────────────────────────────────────
    packages: list[str] = []
    for key in keys:
        dep = _BY_KEY.get(key)
        if dep is None:
            yield f"{ERROR_PREFIX}Unknown dependency key: {key!r}"
            return
        packages.extend(dep.apt_packages)

    if not packages:
        yield f"{ERROR_PREFIX}No packages selected"
        return

    if not is_apt_available():
        yield f"{ERROR_PREFIX}apt-get not found — only Debian/Ubuntu-based systems are supported"
        return

    if _apt_is_locked():
        yield "System is currently busy (apt is locked). Waiting up to 2 minutes..."

    # ── Build command ─────────────────────────────────────────────────────────
    has_sudo = bool(shutil.which("sudo"))
    cmd: list[str] = []

    if has_sudo:
        if sudo_password is not None:
            cmd = ["sudo", "-S", "--"]
        else:
            # NOPASSWD path — fail fast if a password is actually required
            cmd = ["sudo", "-n", "--"]

    cmd += [
        "apt-get",
        "-o", "DPkg::Lock::Timeout=120",
        "install", "-y", "--no-install-recommends", *packages
    ]

    env = {
        **os.environ,
        "DEBIAN_FRONTEND": "noninteractive",
        "APT_LISTCHANGES_FRONTEND": "none",
    }

    # ── Spawn process ─────────────────────────────────────────────────────────
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if (has_sudo and sudo_password is not None) else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # merge stderr into stdout for a single log stream
            env=env,
            text=True,
            bufsize=1,  # line-buffered so output arrives in real time
        )
    except FileNotFoundError as exc:
        yield f"{ERROR_PREFIX}Cannot start installer: {exc}"
        return
    except PermissionError as exc:
        yield f"{ERROR_PREFIX}Permission denied: {exc}"
        return

    # ── Send sudo password ────────────────────────────────────────────────────
    if has_sudo and sudo_password is not None and proc.stdin is not None:
        try:
            proc.stdin.write(f"{sudo_password}\n")
            proc.stdin.flush()
            proc.stdin.close()
        except OSError:
            pass

    # ── Stream output ─────────────────────────────────────────────────────────
    assert proc.stdout is not None
    try:
        for raw in proc.stdout:
            line = raw.rstrip()
            if line:
                yield line
    except OSError:
        pass

    # ── Wait and report result ────────────────────────────────────────────────
    try:
        proc.wait(timeout=300)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        yield f"{ERROR_PREFIX}Installation timed out after 5 minutes"
        return

    if proc.returncode == 0:
        yield DONE
    else:
        yield f"{ERROR_PREFIX}apt-get exited with code {proc.returncode}"
