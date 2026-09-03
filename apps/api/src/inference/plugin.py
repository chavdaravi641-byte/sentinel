"""Abstract inference plugin contract + YOLO output decoding helpers.

A `ModelPlugin` is the unit of modularity for the AI inference engine. Each
plugin exposes the lifecycle contract used by the engine: load / warmup /
health / shutdown / reload, plus a batch inference path so a GPU scheduler can
pack frames from multiple cameras into one forward pass.

The decoding helpers (`decode_yolo`, `nms`, `letterbox`) are written for the
classic YOLO-family ONNX export (`[1, 4 + nc, num_preds]`) and are shared with
any provider plugin that produces that layout.
"""

from __future__ import annotations

import abc
import time
from typing import Any, ClassVar

from src.inference.primitives import (
    BoxResult,
    DeviceInfo,
    InferItem,
    Timings,
)

_LETTERBOX_COLOR = 114


def letterbox(
    image: Any,
    target: tuple[int, int],
) -> tuple[Any, float, float, float]:
    """Resize keeping aspect ratio with gray padding; returns scaled uint8."""
    import cv2

    if image.shape[0] == target[1] and image.shape[1] == target[0]:
        return image, 1.0, 0.0, 0.0
    h, w = image.shape[:2]
    r = min(target[1] / h, target[0] / w)
    new_w, new_h = round(w * r), round(h * r)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np_full((target[1], target[0], 3), _LETTERBOX_COLOR, image.dtype)
    pad_x = (target[0] - new_w) // 2
    pad_y = (target[1] - new_h) // 2
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
    return canvas, r, pad_x, pad_y


def np_full(shape: tuple[int, ...], value: int, dtype: Any) -> Any:
    import numpy as np

    return np.full(shape, value, dtype=dtype)


def nms(boxes: list[BoxResult], iou_threshold: float = 0.45) -> list[BoxResult]:
    """Greedy *class-aware* NMS over a list of already-filtered boxes.

    Suppression only applies to boxes of the same class, so an overlapping
    object of a different class class survives (e.g. a person on a bike).
    """

    if not boxes:
        return []
    keep: list[BoxResult] = []
    items = sorted(boxes, key=lambda b: -b.confidence)
    while items:
        best = items.pop(0)
        keep.append(best)
        items = [
            b for b in items if b.class_name != best.class_name or b.iou(best) <= iou_threshold
        ]
    return keep


def decode_yolo(
    output: Any,
    class_map: dict[int, str] | list[str],
    conf_threshold: float = 0.25,
    input_size: tuple[int, int] = (640, 640),
) -> list[BoxResult]:
    """Decode a YOLOv8/12-style ONNX output `[1, 4 + nc, num_preds]`.

    When a `class_map` is a dict, only mapped indices are kept (this is how the
    engine enforces the allowed class set). Coordinates are normalized to 0..1
    relative to `input_size`.
    """
    import numpy as np

    if output.ndim == 3:
        output = output[0]  # (channels, num_preds)
    channels, num = output.shape
    classes = class_map.values() if isinstance(class_map, dict) else class_map
    num_classes = channels - 4
    if num_classes < len(classes):
        raise ValueError(f"Unexpected YOLO channel count {channels} (need 4+{len(classes)}).")

    if isinstance(class_map, dict):
        class_inv: dict[int, str] = class_map
    else:
        class_inv = {i: name for i, name in enumerate(class_map)}

    box = output[0:4, :]  # cx, cy, w, h in input_size coords
    scores = output[4:, :]
    w_in, h_in = input_size
    results: list[BoxResult] = []
    for i in range(num):
        score_row = scores[:, i]
        cls_id = int(np.argmax(score_row))
        conf = float(score_row[cls_id])
        if conf < conf_threshold:
            continue
        name = class_inv.get(cls_id)
        if name is None:
            continue
        cx = float(box[0, i]) / w_in
        cy = float(box[1, i]) / h_in
        bw = float(box[2, i]) / w_in
        bh = float(box[3, i]) / h_in
        results.append(
            BoxResult(
                class_name=name,
                confidence=conf,
                x=max(0.0, min(1.0, cx - bw / 2)),
                y=max(0.0, min(1.0, cy - bh / 2)),
                w=max(0.0, min(1.0, bw)),
                h=max(0.0, min(1.0, bh)),
            )
        )
    return nms(results)


class ModelPlugin(abc.ABC):
    """Contract implemented by every inference plugin (YOLOv12, custom, ...)."""

    name: str = "model"
    version: str = "0.0.0"
    classes: ClassVar[list[str]] = []
    input_size: tuple[int, int] = (640, 640)
    backend: str = "sim"

    def __init__(self, device: DeviceInfo, conf_threshold: float = 0.4) -> None:
        self.device = device
        self.conf_threshold = conf_threshold
        self._generation: int = 0
        self._loaded_at: float | None = None
        self._error: str | None = None

    # -- lifecycle -------------------------------------------------------- #
    def load(self) -> None:
        """Load weights / build the runtime. Must be idempotent-safe."""
        self._generation += 1
        self._loaded_at = time.time()
        self._error = None

    def warmup(self) -> None:
        """Run a dummy inference to stabilise JIT/EP memory allocations."""
        import numpy as np

        self.infer_batch(
            [InferItem(image=np.zeros((self.input_size[1], self.input_size[0], 3), dtype=np.uint8))]
        )

    def unload(self) -> None:
        """Release runtime resources (sessions, GPU memory)."""
        self._generation = 0
        self._loaded_at = None

    def reload(self) -> None:
        """Re-load weights and bump the generation (dynamic reload)."""
        self.unload()
        self.load()
        self.warmup()

    def health(self) -> dict[str, Any]:
        dev = self.device.to_dict() if self.device else {}
        return {
            "name": self.name,
            "version": self.version,
            "backend": self.backend,
            "classes": list(self.classes),
            "conf_threshold": self.conf_threshold,
            "generation": self._generation,
            "loaded": self._generation > 0,
            "loaded_at": self._loaded_at,
            "accelerator": dev.get("accelerator"),
            "device_name": dev.get("device_name"),
            "providers": dev.get("providers"),
            "error": self._error,
        }

    # -- inference -------------------------------------------------------- #
    @abc.abstractmethod
    def infer_batch(
        self, items: list[InferItem]
    ) -> tuple[list[list[BoxResult]], Timings]:
        """Run a batch of frames; return results + split timings.

        Returns `(per_item_results, timings)` where `timings.pre_ms` covers
        preprocess/letterbox, `infer_ms` the runtime forward pass and
        `post_ms` decode + NMS.
        """
        raise NotImplementedError


__all__ = [
    "ModelPlugin",
    "decode_yolo",
    "letterbox",
    "nms",
]