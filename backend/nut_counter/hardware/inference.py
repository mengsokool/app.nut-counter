from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..config import ModelConfig

if TYPE_CHECKING:
    import numpy as np


@dataclass(frozen=True)
class InferenceResult:
    count: int
    processing_ms: int
    detections: list[dict[str, object]]


class InferenceEngine(ABC):
    status = "missing"
    detail = "inference engine not initialized"

    @abstractmethod
    def detect_frame(self, bgr: "np.ndarray", part_type: str) -> dict[str, Any]:
        """Run inference on a 640x640 BGR ndarray.

        Returns: {"count": int, "detections": list[Detection]}
        Detections are in [0,1]-normalized coordinates of the input frame.
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


class MockInferenceEngine(InferenceEngine):
    status = "mock"
    detail = "mock inference active"

    def __init__(self, config: ModelConfig) -> None:
        self.config = config

    def detect_frame(self, bgr: "np.ndarray", part_type: str) -> dict[str, Any]:
        # Static fake count + a couple of demo bboxes so the overlay renders
        # something visible during development.
        from ..streaming.ai import Detection

        return {
            "count": 56,
            "detections": [
                Detection(label=part_type, confidence=0.92, x=0.20, y=0.20, w=0.18, h=0.18),
                Detection(label=part_type, confidence=0.87, x=0.55, y=0.40, w=0.18, h=0.18),
                Detection(label=part_type, confidence=0.81, x=0.30, y=0.65, w=0.18, h=0.18),
            ],
        }

    def close(self) -> None:
        return


class HailoYoloEngine(InferenceEngine):
    """Runs the configured `inference_command` per frame.

    The decoder command is expected to read a JPEG file path and emit a JSON
    payload with `{"count": int, "detections": [{label, confidence, bbox: [x,y,w,h]}]}`
    in the input image's pixel coordinates.
    """

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self.hef_path = Path(config.hef_path)
        self.labels_path = Path(config.labels_path)

        if config.engine == "mock":
            self.status = "mock"
            self.detail = "mock inference configured"
            return
        if not self.hef_path.exists():
            self.status = "missing"
            self.detail = f"HEF model not found: {self.hef_path}"
            return
        if shutil.which("hailortcli") is None:
            self.status = "missing"
            self.detail = "hailortcli not found"
            return
        if not config.inference_command:
            self.status = "missing"
            self.detail = "Hailo runtime detected, but YOLO decoder command is not configured"
            return

        self.status = "ready"
        self.detail = "Hailo command inference active"

    def detect_frame(self, bgr: "np.ndarray", part_type: str) -> dict[str, Any]:
        from ..streaming.ai import detections_from_bbox_payload

        if self.status != "ready":
            return MockInferenceEngine(self.config).detect_frame(bgr, part_type)

        try:
            import cv2  # noqa: WPS433
        except ImportError:
            return {"count": 0, "detections": []}

        ok, jpeg_buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not ok:
            return {"count": 0, "detections": []}

        with tempfile.NamedTemporaryFile(suffix=".jpg") as image_file:
            image_file.write(bytes(jpeg_buf))
            image_file.flush()
            command = [
                part.format(
                    image=image_file.name,
                    hef=str(self.hef_path),
                    labels=str(self.labels_path),
                    part_type=part_type,
                    confidence=self.config.confidence_threshold,
                    nms=self.config.nms_threshold,
                )
                for part in self.config.inference_command
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10,
                )
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                return {"count": 0, "detections": []}

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return {"count": 0, "detections": []}

        return {
            "count": int(payload.get("count", 0)),
            "detections": detections_from_bbox_payload(payload),
        }

    def close(self) -> None:
        return


class OnnxYoloEngine(InferenceEngine):
    """Runs a YOLO-style ONNX model with onnxruntime.

    Supported output layouts:
      * [1, boxes, 4 + classes]
      * [1, 4 + classes, boxes]

    Boxes are expected as center x/y/w/h in the 640x640 input space. If a labels
    file is present, detections are filtered to the selected part type.
    """

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        model_path = config.model_path or config.hef_path
        self.model_path = Path(model_path)
        self.labels = _load_labels(Path(config.labels_path))
        self.session: Any | None = None
        self.input_name = ""

        if not self.model_path.exists():
            self.status = "missing"
            self.detail = f"ONNX model not found: {self.model_path}"
            return
        try:
            import onnxruntime as ort  # noqa: WPS433
        except ImportError:
            self.status = "missing"
            self.detail = "onnxruntime not installed"
            return

        try:
            providers = ["CPUExecutionProvider"]
            self.session = ort.InferenceSession(str(self.model_path), providers=providers)
            self.input_name = self.session.get_inputs()[0].name
        except Exception as error:  # noqa: BLE001
            self.status = "error"
            self.detail = f"ONNX runtime error: {error}"
            return

        self.status = "ready"
        self.detail = f"ONNX runtime active: {self.model_path.name}"

    def detect_frame(self, bgr: "np.ndarray", part_type: str) -> dict[str, Any]:
        if self.status != "ready" or self.session is None:
            return MockInferenceEngine(self.config).detect_frame(bgr, part_type)

        try:
            import numpy as np  # noqa: WPS433

            rgb = bgr[:, :, ::-1]
            tensor = np.ascontiguousarray(
                rgb.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
            )
            outputs = self.session.run(None, {self.input_name: tensor})
            detections = self._decode(outputs[0], part_type, np)
        except Exception:  # noqa: BLE001
            return {"count": 0, "detections": []}

        return {"count": len(detections), "detections": detections}

    def _decode(self, output: Any, part_type: str, np: Any) -> list[Any]:
        from ..streaming.ai import Detection

        arr = np.asarray(output)
        if arr.ndim == 3:
            arr = arr[0]
        if arr.ndim != 2:
            return []
        if arr.shape[0] < arr.shape[1] and arr.shape[0] <= 256:
            arr = arr.T
        if arr.shape[1] < 5:
            return []

        boxes = arr[:, :4].astype(np.float32)
        scores_raw = arr[:, 4:].astype(np.float32)
        if self.labels and scores_raw.shape[1] == len(self.labels) + 1:
            objectness = scores_raw[:, 0]
            class_scores = scores_raw[:, 1:]
            class_ids = np.argmax(class_scores, axis=1)
            scores = objectness * class_scores[np.arange(class_scores.shape[0]), class_ids]
        elif scores_raw.shape[1] == 1:
            class_ids = np.zeros((scores_raw.shape[0],), dtype=np.intp)
            scores = scores_raw[:, 0]
        else:
            class_ids = np.argmax(scores_raw, axis=1)
            scores = scores_raw[np.arange(scores_raw.shape[0]), class_ids]

        keep = scores >= self.config.confidence_threshold
        boxes = boxes[keep]
        scores = scores[keep]
        class_ids = class_ids[keep]
        if boxes.size == 0:
            return []

        if np.max(boxes) <= 1.5:
            boxes = boxes * 640.0
        xyxy = _xywh_to_xyxy(boxes, np)
        keep_indices = _nms(xyxy, scores, self.config.nms_threshold, np)

        detections: list[Any] = []
        for index in keep_indices:
            class_id = int(class_ids[index])
            label = _label_for_class(self.labels, class_id, part_type)
            if self.labels and not _label_matches_part(label, part_type):
                continue
            x1, y1, x2, y2 = xyxy[index]
            x1 = float(np.clip(x1, 0, 640))
            y1 = float(np.clip(y1, 0, 640))
            x2 = float(np.clip(x2, 0, 640))
            y2 = float(np.clip(y2, 0, 640))
            if x2 <= x1 or y2 <= y1:
                continue
            detections.append(
                Detection(
                    label=label,
                    confidence=float(scores[index]),
                    x=x1 / 640.0,
                    y=y1 / 640.0,
                    w=(x2 - x1) / 640.0,
                    h=(y2 - y1) / 640.0,
                )
            )
        return detections

    def close(self) -> None:
        self.session = None


def _load_labels(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            payload = json.loads(text)
            if isinstance(payload, list):
                return [str(item) for item in payload]
            if isinstance(payload, dict):
                keys = sorted(payload, key=lambda item: (0, int(item)) if str(item).isdigit() else (1, str(item)))
                return [str(payload[key]) for key in keys]
        return [line.strip() for line in text.splitlines() if line.strip()]
    except Exception:  # noqa: BLE001
        return []


def validate_model_config(config: ModelConfig) -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    def add(key: str, label: str, status: str, detail: str) -> None:
        checks.append({"key": key, "label": label, "status": status, "detail": detail})

    if config.engine == "mock":
        add("engine", "Engine", "ok", "Mock model is available")
        return {"ok": True, "checks": checks}

    model_path = Path(config.model_path or config.hef_path)
    labels_path = Path(config.labels_path)

    if config.engine == "onnx":
        if not model_path.exists():
            add("model", "Model file", "error", f"ไม่พบไฟล์โมเดล: {model_path}")
        elif not model_path.is_file():
            add("model", "Model file", "error", f"path นี้ไม่ใช่ไฟล์: {model_path}")
        elif model_path.suffix.lower() != ".onnx":
            add("model", "Model file", "warn", f"ไฟล์ไม่ใช่ .onnx: {model_path.name}")
        else:
            add("model", "Model file", "ok", str(model_path))

        if importlib.util.find_spec("onnxruntime") is None:
            add("runtime", "ONNX Runtime", "error", "ยังไม่ได้ติดตั้ง onnxruntime")
        elif model_path.exists() and model_path.is_file():
            try:
                import onnxruntime as ort  # noqa: WPS433

                session = ort.InferenceSession(
                    str(model_path),
                    providers=["CPUExecutionProvider"],
                )
                inputs = ", ".join(
                    f"{item.name}{list(item.shape)}" for item in session.get_inputs()
                )
                outputs = ", ".join(
                    f"{item.name}{list(item.shape)}" for item in session.get_outputs()
                )
                add("runtime", "ONNX Runtime", "ok", f"input: {inputs}; output: {outputs}")
            except Exception as error:  # noqa: BLE001
                add("runtime", "ONNX Runtime", "error", f"โหลด ONNX ไม่สำเร็จ: {error}")

    elif config.engine in {"hailo", "external"}:
        if not model_path.exists():
            add("model", "Model file", "error", f"ไม่พบไฟล์โมเดล: {model_path}")
        elif not model_path.is_file():
            add("model", "Model file", "error", f"path นี้ไม่ใช่ไฟล์: {model_path}")
        else:
            add("model", "Model file", "ok", str(model_path))

        if config.engine == "hailo" and shutil.which("hailortcli") is None:
            add("runtime", "Hailo runtime", "error", "ไม่พบ hailortcli")
        elif config.engine == "external" and not config.inference_command:
            add("runtime", "External command", "error", "ยังไม่ได้ตั้ง inference_command")
        else:
            add("runtime", "Runtime", "ok", config.engine)
    else:
        add("engine", "Engine", "error", f"engine ไม่รองรับ: {config.engine}")

    labels = _load_labels(labels_path)
    if not config.labels_path:
        add("labels", "Labels file", "error", "ยังไม่ได้เลือกไฟล์ labels")
    elif not labels_path.exists():
        add("labels", "Labels file", "error", f"ไม่พบไฟล์ labels: {labels_path}")
    elif not labels:
        add("labels", "Labels file", "error", "อ่าน labels ไม่ได้หรือไฟล์ว่าง")
    else:
        add("labels", "Labels file", "ok", f"{len(labels)} classes")
        for part_type, label in (("nut", "Class nut"), ("washer", "Class washer")):
            if any(_label_matches_part(item, part_type) for item in labels):
                add(f"class_{part_type}", label, "ok", "พบใน labels")
            else:
                add(f"class_{part_type}", label, "error", "ไม่พบใน labels")

    return {
        "ok": all(item["status"] != "error" for item in checks),
        "checks": checks,
    }


def _label_for_class(labels: list[str], class_id: int, part_type: str) -> str:
    if 0 <= class_id < len(labels):
        return labels[class_id]
    return part_type


def _label_matches_part(label: str, part_type: str) -> bool:
    normalized = label.lower()
    if part_type == "washer":
        return "washer" in normalized or "แหวน" in normalized
    return "nut" in normalized or "น็อต" in normalized


def _xywh_to_xyxy(boxes: Any, np: Any) -> Any:
    xyxy = np.empty_like(boxes)
    xyxy[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
    xyxy[:, 1] = boxes[:, 1] - boxes[:, 3] / 2
    xyxy[:, 2] = boxes[:, 0] + boxes[:, 2] / 2
    xyxy[:, 3] = boxes[:, 1] + boxes[:, 3] / 2
    return xyxy


def _nms(boxes: Any, scores: Any, threshold: float, np: Any) -> list[int]:
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        current = int(order[0])
        keep.append(current)
        if order.size == 1:
            break

        rest = order[1:]
        x1 = np.maximum(boxes[current, 0], boxes[rest, 0])
        y1 = np.maximum(boxes[current, 1], boxes[rest, 1])
        x2 = np.minimum(boxes[current, 2], boxes[rest, 2])
        y2 = np.minimum(boxes[current, 3], boxes[rest, 3])
        inter = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
        area_current = (boxes[current, 2] - boxes[current, 0]) * (
            boxes[current, 3] - boxes[current, 1]
        )
        area_rest = (boxes[rest, 2] - boxes[rest, 0]) * (
            boxes[rest, 3] - boxes[rest, 1]
        )
        union = area_current + area_rest - inter
        iou = inter / np.maximum(union, 1e-6)
        order = rest[iou <= threshold]
    return keep
