from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
import queue
import statistics
import threading
import time
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import deps as deps_mod
from .config import (
    DEFAULT_CONFIG_PATH,
    config_to_dict,
    load_config,
    parse_config,
    save_config,
)
from .hardware import HardwareStack, create_hardware_stack
from .hardware.factory import create_gpio_controller, create_inference_engine
from .hardware.inference import validate_model_config
from .streaming import (
    AIWorker,
    DetectionBus,
    StreamingWebRTC,
    WebRTCUnavailable,
    scan_camera_sources,
)
from .state import SystemState


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_UI_DIR = Path(os.environ.get("NUT_COUNTER_UI_DIR", PROJECT_ROOT / "dist/ui"))
MODEL_BROWSER_ROOTS = [
    Path("/var/lib/nut-counter/models"),
    PROJECT_ROOT,
    Path.home(),
]


class NutCounterRuntime:
    """Owns the hardware stack, the streaming pipeline, and the SSE fan-out.

    Lifecycle pieces:
      * `hardware`         — gpio, frame source, inference engine
      * `ai_worker`        — pulls frames at ~5 fps, publishes detections
      * `webrtc`           — single H.264 encoder, fanned to N peers via MediaRelay
      * `_async_loop`      — dedicated asyncio thread for aiortc
      * `_state_subs`      — SSE subscribers for `/api/events`
    """

    def __init__(self, ui_dir: Path, config_path: Path) -> None:
        self.ui_dir = ui_dir
        self.config_path = config_path
        self.config = load_config(config_path)
        self.hardware = create_hardware_stack(self.config)

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._sub_lock = threading.Lock()
        self._state_subs: list[queue.Queue[dict[str, object] | None]] = []
        self._tray_override: bool | None = None

        self._async_loop = asyncio.new_event_loop()
        self._async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._async_thread.start()

        self.webrtc = StreamingWebRTC(self.hardware.frame_source.bus, self._async_loop)

        self.state = SystemState(
            safeMode=self._should_enable_safe_mode(self.hardware),
            selectedPartType=self.config.counting.selected_part_type,
            camera=self.hardware.frame_source.status,
            model=self.hardware.inference.status,
            gpio=self.hardware.gpio.status,
        )

        self.ai_worker = AIWorker(
            frame_bus=self.hardware.frame_source.bus,
            engine=self.hardware.inference,
            get_part_type=lambda: self.config.counting.selected_part_type,
            should_process=lambda: self.status()["trayPresent"],
            target_fps=5.0,
        )
        self.ai_worker.start()

        self.hardware.gpio.set_light(False)
        self._worker = threading.Thread(target=self._poll_hardware, daemon=True)
        self._worker.start()

    # --- async loop ---------------------------------------------------------
    def _run_async_loop(self) -> None:
        asyncio.set_event_loop(self._async_loop)
        self._async_loop.run_forever()

    # --- safe mode ----------------------------------------------------------
    def _should_enable_safe_mode(self, hardware: HardwareStack) -> bool:
        if self.config.safe_mode:
            return True
        critical = {hardware.gpio.status, hardware.frame_source.status}
        if self.config.model.engine != "mock":
            critical.add(hardware.inference.status)
        return any(s in {"missing", "error"} for s in critical)

    # --- state SSE ----------------------------------------------------------
    def subscribe_state(self) -> queue.Queue[dict[str, object] | None]:
        q: queue.Queue[dict[str, object] | None] = queue.Queue(maxsize=8)
        with self._sub_lock:
            self._state_subs.append(q)
        return q

    def unsubscribe_state(self, q: queue.Queue[dict[str, object] | None]) -> None:
        with self._sub_lock:
            try:
                self._state_subs.remove(q)
            except ValueError:
                pass

    def _broadcast_state(self, payload: dict[str, object]) -> None:
        with self._sub_lock:
            for q in list(self._state_subs):
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    pass

    # --- detections SSE -----------------------------------------------------
    def detection_bus(self) -> DetectionBus:
        return self.ai_worker.detections

    # --- status / config ----------------------------------------------------
    def status(self) -> dict[str, object]:
        with self._lock:
            return self.state.as_dict()

    def update_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        config = parse_config(payload)
        save_config(config, self.config_path)
        camera_changed = config.camera != self.config.camera
        gpio_changed = config.gpio != self.config.gpio
        model_changed = config.model != self.config.model

        # Tear the hot path down before swapping hardware so peers don't pull
        # frames from a stale FrameBus.
        self._close_webrtc_sync()
        self.ai_worker.close()

        old_hardware = self.hardware
        old_hardware.gpio.set_light(False)

        if camera_changed:
            old_hardware.close()
            new_hardware = create_hardware_stack(config)
        else:
            new_hardware = old_hardware
            if gpio_changed:
                old_hardware.gpio.close()
                new_hardware = replace(
                    new_hardware,
                    gpio=create_gpio_controller(config.gpio, old_hardware.platform),
                )
            if model_changed:
                old_hardware.inference.close()
                new_hardware = replace(
                    new_hardware,
                    inference=create_inference_engine(config.model),
                )
        new_hardware.gpio.set_light(False)

        with self._lock:
            self.config = config
            self.hardware = new_hardware
            self.state.safeMode = self._should_enable_safe_mode(self.hardware)
            self.state.selectedPartType = config.counting.selected_part_type
            self.state.camera = self.hardware.frame_source.status
            self.state.model = self.hardware.inference.status
            self.state.gpio = self.hardware.gpio.status
            self.state.lightOn = False
            snapshot = self.state.as_dict()

        # Rebuild streaming pipeline pointing at the (possibly new) FrameBus.
        self.webrtc = StreamingWebRTC(
            self.hardware.frame_source.bus, self._async_loop
        )
        self.ai_worker = AIWorker(
            frame_bus=self.hardware.frame_source.bus,
            engine=self.hardware.inference,
            get_part_type=lambda: self.config.counting.selected_part_type,
            should_process=lambda: self.status()["trayPresent"],
            target_fps=5.0,
        )
        self.ai_worker.start()

        self._broadcast_state(snapshot)
        return config_to_dict(config)

    # --- counting -----------------------------------------------------------
    def count_once(self) -> dict[str, object]:
        with self._lock:
            if self.state.safeMode:
                return {"success": False, "error": "ระบบอยู่ใน safe mode", **self.state.as_dict()}
            if not self.state.trayPresent:
                return {"success": False, "error": "ยังไม่พบถาดวางชิ้นส่วน", **self.state.as_dict()}
            stable_n = max(1, self.config.counting.stable_frames)

        # Wait for enough fresh detection results to median over.
        deadline = time.monotonic() + self.config.counting.timeout_ms / 1000.0
        while time.monotonic() < deadline:
            recent = self.ai_worker.recent(stable_n)
            if len(recent) >= stable_n:
                break
            time.sleep(0.05)

        recent = self.ai_worker.recent(stable_n)
        if not recent:
            return {"success": False, "error": "ยังไม่มีผลตรวจจากกล้อง", **self.status()}

        count = int(statistics.median(r.count for r in recent))
        duration_ms = max(r.processing_ms for r in recent)

        with self._lock:
            self.state.count = count
            self.state.processingMs = duration_ms
            snapshot = self.state.as_dict()
        self._broadcast_state(snapshot)
        return {"success": True, **snapshot}

    def set_light_override(self, enabled: bool) -> bool:
        with self._lock:
            if self.state.safeMode:
                self.hardware.gpio.set_light(False)
                self.state.lightOn = False
            else:
                self.hardware.gpio.set_light(enabled)
                self.state.lightOn = enabled
            result = self.state.lightOn
            snapshot = self.state.as_dict()
        self._broadcast_state(snapshot)
        return result

    def set_tray_override(self, present: bool) -> dict[str, object]:
        with self._lock:
            self._tray_override = present
            self.state.trayPresent = present
            should_light = present and not self.state.safeMode
            self.state.lightOn = should_light
            snapshot = self.state.as_dict()
        self.hardware.gpio.set_light(should_light)
        self._broadcast_state(snapshot)
        return snapshot

    def set_selected_part_type(self, part_type: str) -> dict[str, object]:
        part_type = part_type.strip()
        if part_type not in {"nut", "washer"}:
            raise ValueError("partType must be nut or washer")
        with self._lock:
            config = replace(
                self.config,
                counting=replace(
                    self.config.counting,
                    selected_part_type=part_type,
                ),
            )
            save_config(config, self.config_path)
            self.config = config
            self.state.selectedPartType = part_type
            snapshot = self.state.as_dict()
        self._broadcast_state(snapshot)
        return snapshot

    # --- webrtc helpers -----------------------------------------------------
    def create_webrtc_answer(self, offer: dict[str, Any]) -> dict[str, str]:
        future = asyncio.run_coroutine_threadsafe(
            self.webrtc.create_answer(offer), self._async_loop
        )
        return future.result(timeout=10)

    def _close_webrtc_sync(self) -> None:
        if not self._async_loop.is_running():
            return
        future = asyncio.run_coroutine_threadsafe(
            self.webrtc.close_all(), self._async_loop
        )
        try:
            future.result(timeout=5)
        except (FutureTimeoutError, RuntimeError):
            pass

    # --- hardware polling ---------------------------------------------------
    def _poll_hardware(self) -> None:
        while not self._stop_event.is_set():
            tray_present = (
                self._tray_override
                if self._tray_override is not None
                else self.hardware.gpio.read_tray_present()
            )
            self.hardware.frame_source.set_idle_mode(not tray_present)
            latest_detection = self.ai_worker.detections.latest()
            with self._lock:
                prev = self.state.as_dict()
                self.state.trayPresent = tray_present
                self.state.camera = self.hardware.frame_source.status
                self.state.model = self.hardware.inference.status
                self.state.gpio = self.hardware.gpio.status
                if tray_present and latest_detection is not None:
                    self.state.count = latest_detection.count
                    self.state.processingMs = latest_detection.processing_ms
                elif not tray_present:
                    self.state.count = 0
                    self.state.processingMs = 0
                should_light = tray_present and not self.state.safeMode
                self.state.lightOn = should_light
                snapshot = self.state.as_dict()
            self.hardware.gpio.set_light(should_light)
            if snapshot != prev:
                self._broadcast_state(snapshot)
            self._stop_event.wait(0.1)

    # --- shutdown -----------------------------------------------------------
    def close(self) -> None:
        self._stop_event.set()
        self.hardware.gpio.set_light(False)
        self._close_webrtc_sync()
        self.ai_worker.close()
        self.hardware.close()
        if self._async_loop.is_running():
            self._async_loop.call_soon_threadsafe(self._async_loop.stop)
            self._async_thread.join(timeout=2)


def create_handler(runtime: NutCounterRuntime) -> type[BaseHTTPRequestHandler]:
    class NutCounterHandler(BaseHTTPRequestHandler):
        server_version = "NutCounter/0.2"

        # --- routing ---------------------------------------------------------
        def do_GET(self) -> None:
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/status":
                self.send_json(runtime.status())
                return
            if path == "/api/config":
                self.send_json(config_to_dict(runtime.config))
                return
            if path == "/api/camera/sources":
                self.send_json({"sources": scan_camera_sources()})
                return
            if path == "/api/doctor":
                self.send_json(build_doctor_report(runtime))
                return
            if path == "/api/files":
                query = parse_qs(parsed.query)
                self.send_json(
                    browse_files(
                        query.get("path", [""])[0],
                        kind=query.get("kind", ["model"])[0],
                    )
                )
                return
            if path == "/api/events":
                self.send_state_sse()
                return
            if path == "/api/detections":
                self.send_detections_sse()
                return
            self.send_static(path, runtime.ui_dir)

        def do_PUT(self) -> None:
            from urllib.parse import urlparse
            if urlparse(self.path).path != "/api/config":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                payload = self.read_json()
                config = runtime.update_config(payload)
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            except PermissionError:
                self.send_json(
                    {"error": f"ไม่สามารถบันทึก config ได้: ไม่มีสิทธิ์เขียน {runtime.config_path}"},
                    HTTPStatus.FORBIDDEN,
                )
                return
            except OSError as error:
                self.send_json(
                    {"error": f"ไม่สามารถบันทึก config ได้: {error}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return
            self.send_json(config)

        def do_POST(self) -> None:
            from urllib.parse import urlparse
            path = urlparse(self.path).path
            if path == "/api/count/start":
                result = runtime.count_once()
                status = HTTPStatus.OK if result.get("success") else HTTPStatus.CONFLICT
                self.send_json(result, status)
                return
            if path == "/api/counting/part-type":
                try:
                    payload = self.read_json(default={})
                    part_type = payload.get("partType", "")
                    if not isinstance(part_type, str):
                        raise ValueError("partType must be a string")
                    self.send_json(runtime.set_selected_part_type(part_type))
                except (json.JSONDecodeError, TypeError, ValueError) as error:
                    self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                except PermissionError:
                    self.send_json(
                        {"error": f"ไม่สามารถบันทึก config ได้: ไม่มีสิทธิ์เขียน {runtime.config_path}"},
                        HTTPStatus.FORBIDDEN,
                    )
                except OSError as error:
                    self.send_json(
                        {"error": f"ไม่สามารถบันทึก config ได้: {error}"},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                return
            if path == "/api/hardware/light":
                payload = self.read_json(default={})
                light_on = runtime.set_light_override(bool(payload.get("lightOn", False)))
                self.send_json({"success": light_on == bool(payload.get("lightOn", False)), "lightOn": light_on})
                return
            if path == "/api/hardware/tray":
                payload = self.read_json(default={})
                present = bool(payload.get("present", False))
                self.send_json({"success": True, **runtime.set_tray_override(present)})
                return
            if path == "/api/model/validate":
                try:
                    payload = self.read_json(default={})
                    model_payload = payload.get("model", payload)
                    if not isinstance(model_payload, dict):
                        raise ValueError("model must be an object")
                    config = parse_config({"model": model_payload})
                    self.send_json(validate_model_config(config.model))
                except (json.JSONDecodeError, TypeError, ValueError) as error:
                    self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            if path in {"/api/system/shutdown", "/api/system/reboot"}:
                self.send_json({"success": False, "needsAuth": True})
                return
            if path == "/api/doctor/install":
                self.send_install_stream()
                return
            if path == "/api/camera/webrtc/offer":
                self.handle_webrtc_offer()
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        # --- helpers ---------------------------------------------------------
        def send_json(
            self,
            payload: dict[str, Any],
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def handle_webrtc_offer(self) -> None:
            try:
                payload = self.read_json()
                answer = runtime.create_webrtc_answer(payload)
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            except WebRTCUnavailable as error:
                self.send_json({"error": str(error)}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            except FutureTimeoutError:
                self.send_json({"error": "WebRTC answer timed out"}, HTTPStatus.GATEWAY_TIMEOUT)
                return
            self.send_json(answer)

        def send_state_sse(self) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            def emit(payload: dict[str, object]) -> None:
                self.wfile.write(
                    f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
                )
                self.wfile.flush()

            q = runtime.subscribe_state()
            try:
                emit(runtime.status())
                while True:
                    try:
                        payload = q.get(timeout=15.0)
                    except queue.Empty:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
                        continue
                    if payload is None:
                        break
                    emit(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                runtime.unsubscribe_state(q)

        def send_detections_sse(self) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            bus = runtime.detection_bus()
            q = bus.subscribe()
            try:
                latest = bus.latest()
                if latest is not None:
                    self._emit_event(latest.as_dict())
                while True:
                    try:
                        item = q.get(timeout=15.0)
                    except queue.Empty:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
                        continue
                    if item is None:
                        break
                    self._emit_event(item.as_dict())
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                bus.unsubscribe(q)

        def _emit_event(self, payload: dict[str, Any]) -> None:
            self.wfile.write(
                f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
            )
            self.wfile.flush()

        def send_install_stream(self) -> None:
            try:
                body = self.read_json(default={})
                raw_keys = body.get("keys", [])
                sudo_password: str | None = body.get("sudoPassword") or None
                if not isinstance(raw_keys, list) or not all(
                    isinstance(k, str) for k in raw_keys
                ):
                    self.send_json({"error": "invalid keys"}, HTTPStatus.BAD_REQUEST)
                    return
                keys: list[str] = raw_keys
            except (json.JSONDecodeError, TypeError, KeyError):
                self.send_json({"error": "invalid request body"}, HTTPStatus.BAD_REQUEST)
                return

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            def emit(line: str) -> None:
                self.wfile.write(
                    f"data: {json.dumps(line, ensure_ascii=False)}\n\n".encode("utf-8")
                )
                self.wfile.flush()

            try:
                for line in deps_mod.stream_install(keys, sudo_password):
                    emit(line)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def send_static(self, request_path: str, ui_dir: Path) -> None:
            if request_path in {"", "/"}:
                candidate = ui_dir / "index.html"
            else:
                candidate = (ui_dir / request_path.lstrip("/")).resolve()
                if not candidate.is_relative_to(ui_dir.resolve()) or not candidate.exists():
                    candidate = ui_dir / "index.html"
            if not candidate.exists() or not candidate.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type, _ = mimetypes.guess_type(candidate.name)
            body = candidate.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_json(self, default: dict[str, Any] | None = None) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0 and default is not None:
                return default
            body = self.rfile.read(length)
            return json.loads(body.decode("utf-8"))

        def log_message(self, format: str, *args: object) -> None:
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
            print(f"{timestamp} {self.address_string()} {format % args}")

    return NutCounterHandler


def browse_files(raw_path: str, *, kind: str) -> dict[str, object]:
    suffixes = {
        "model": {".onnx", ".hef"},
        "labels": {".txt", ".json", ".yaml", ".yml", ".names"},
    }.get(kind, {".onnx", ".hef", ".txt", ".json"})
    current = _browse_path(raw_path)
    if current.is_file():
        current = current.parent
    entries: list[dict[str, object]] = []
    error = ""
    try:
        children = sorted(
            current.iterdir(),
            key=lambda item: (not item.is_dir(), item.name.lower()),
        )
        for item in children[:300]:
            if item.name.startswith("."):
                continue
            is_dir = item.is_dir()
            selectable = item.is_file() and item.suffix.lower() in suffixes
            if not is_dir and not selectable:
                continue
            entries.append(
                {
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if is_dir else "file",
                    "selectable": selectable,
                    "size": item.stat().st_size if item.is_file() else None,
                }
            )
    except OSError as exc:
        error = str(exc)

    roots = [
        {"label": _root_label(root), "path": str(root)}
        for root in MODEL_BROWSER_ROOTS
        if root.exists()
    ]
    return {
        "path": str(current),
        "parent": str(current.parent) if current.parent != current else "",
        "roots": roots,
        "entries": entries,
        "error": error,
    }


def _browse_path(raw_path: str) -> Path:
    if raw_path:
        return Path(raw_path).expanduser().resolve()
    for root in MODEL_BROWSER_ROOTS:
        if root.exists():
            return root.resolve()
    return Path.home().resolve()


def _root_label(path: Path) -> str:
    if path == Path.home():
        return "Home"
    if path == PROJECT_ROOT:
        return "Project"
    return path.name or str(path)


def build_doctor_report(runtime: NutCounterRuntime) -> dict[str, object]:
    return {
        "ok": not runtime.state.safeMode,
        "safeMode": runtime.state.safeMode,
        "platform": runtime.hardware.platform.__dict__,
        "aptAvailable": deps_mod.is_apt_available(),
        "sudoNeedsPassword": deps_mod.sudo_needs_password(),
        "deps": deps_mod.check_all(),
        "checks": [
            {"name": "config", "ok": True, "detail": str(runtime.config_path)},
            {
                "name": "camera",
                "ok": runtime.hardware.frame_source.status in {"ready", "mock"},
                "status": runtime.hardware.frame_source.status,
                "detail": runtime.hardware.frame_source.detail,
            },
            {
                "name": "gpio",
                "ok": runtime.hardware.gpio.status in {"ready", "mock"},
                "status": runtime.hardware.gpio.status,
                "detail": runtime.hardware.gpio.detail,
            },
            {
                "name": "model",
                "ok": runtime.hardware.inference.status in {"ready", "mock"},
                "status": runtime.hardware.inference.status,
                "detail": runtime.hardware.inference.detail,
            },
        ],
    }


def run_server(host: str, port: int, ui_dir: Path, config_path: Path) -> None:
    runtime = NutCounterRuntime(ui_dir=ui_dir, config_path=config_path)
    handler = create_handler(runtime)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Nut Counter backend listening on http://{host}:{port}")
    try:
        server.serve_forever()
    finally:
        runtime.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Nut Counter backend")
    parser.add_argument("--host", default=os.environ.get("NUT_COUNTER_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("NUT_COUNTER_PORT", "8787")))
    parser.add_argument("--ui-dir", type=Path, default=DEFAULT_UI_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args()
    run_server(args.host, args.port, args.ui_dir, args.config)


if __name__ == "__main__":
    main()
