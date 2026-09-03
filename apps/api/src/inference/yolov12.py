"""YOLOv12 plugin — the first model in the Sentinel AI inference engine.

Two backends, selected automatically at load time:

* ``onnx`` — the production path. Loads ``{AI_WEIGHTS_DIR}/yolov12/yolov12*.onnx``
  (any YOLOv8/v9/v12-family export producing ``[1, 4 + nc, N]``) and runs it
  through onnxruntime with the scheduler's chosen providers (CUDA with
  automatic CPU fallback). Only the six approved classes are emitted:
  ``person, car, bike, bus, truck, bicycle``. Plate/face/OCR/weapon/fire/fight
  categories are excluded by construction at decode time.
* ``sim`` — deterministic validation/demo backend used when ONNX weights (or
  onnxruntime itself) are absent. Objects move smoothly so IoU tracking,
  overlays, storage and alerts can be exercised end-to-end without shipping
  model weights.

The sim backend is a *test fixture*, clearly labelled in health()/config
output (`backend: sim`) so operators never mistake it for production inference.
"""

from __future__ import annotations

import math
from time import perf_counter
from typing import Any

import cv2
import numpy as np
from src.core.logging import log
from src.inference.loader import ModelLoader
from src.inference.plugin import (
    ModelPlugin,
    decode_yolo,
    letterbox,
)
from src.inference.primitives import BoxResult, DeviceInfo, InferItem, Timings

# Allowed class set exactly as specified for Phase 3. COCO ids: person 0,
# bicycle 1, car 2, motorcycle 3, bus 5, truck 7.
SENTINEL_CLASSES = ["person", "car", "bike", "bus", "truck", "bicycle"]
COCO_TO_SENTINEL: dict[int, str] = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "bike",
    5: "bus",
    7: "truck",
}

DEFAULT_WEIGHTS = "yolov12s.onnx"


class YoloV12Plugin(ModelPlugin):
    name = "yolov12"
    version = "0.0.1"
    classes = SENTINEL_CLASSES
    input_size = (640, 640)
    backend = "sim"

    def __init__(
        self,
        loader: ModelLoader,
        device: DeviceInfo,
        conf_threshold: float = 0.4,
    ) -> None:
        super().__init__(device, conf_threshold)
        self._loader = loader
        self._session: Any = None
        self._weights_path: str | None = None
        self._input_name: str | None = None
        self._shape_hw: tuple[int, int] | None = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def load(self) -> None:
        super().load()
        self._session = None
        self._weights_path = None
        self._input_name = None
        self._shape_hw = None
        self.backend = "sim"

        weights = self._loader.resolve_weights(self.name)
        if weights is None:
            log.info("ai.yolov12.sim", reason="weights absent", hint=f"drop {DEFAULT_WEIGHTS} in weights dir")
        else:
            try:
                self._session, self.device = self._loader.build_session(weights)
                self._weights_path = str(weights)
                self._input_name = self._session.get_inputs()[0].name
                if len(self._session.get_inputs()[0].shape) == 4:
                    _, _, hw_h, hw_w = tuple(int(v if v is not None else -1) for v in self._session.get_inputs()[0].shape)
                    if hw_h > 0 and hw_w > 0:
                        self._shape_hw = (hw_h, hw_w)
                        self.input_size = (hw_w, hw_h)
                self.backend = "onnx"
                log.info(
                    "ai.yolov12.loaded",
                    weights=str(weights),
                    providers=self.device.providers,
                    accelerator=self.device.accelerator,
                )
            except Exception as exc:  # noqa: BLE001 - degrade to sim, never crash the engine
                self._error = str(exc)
                self.backend = "sim"
                log.warning("ai.yolov12.onnx_failed", fallback="sim", error=str(exc))
        self.warmup()

    def warmup(self) -> None:
        if self._session is None:
            return
        dummy = np.zeros((self.input_size[1], self.input_size[0], 3), dtype=np.uint8)
        try:
            self.infer_batch([InferItem(image=dummy, ctx={"frame_seq": 0, "seed": 0})])
        except Exception as exc:  # noqa: BLE001
            log.warning("ai.yolov12.warmup_failed", error=str(exc))

    def unload(self) -> None:
        super().unload()
        self._session = None
        self._weights_path = None
        self._input_name = None
        self._shape_hw = None

    def reload(self) -> None:
        self._generation = 0
        self.load()

    # ------------------------------------------------------------------ #
    # Inference
    # ------------------------------------------------------------------ #
    def infer_batch(
        self, items: list[InferItem]
    ) -> tuple[list[list[BoxResult]], Timings]:
        if self._session is not None:
            return self._infer_onnx(items)
        return self._infer_sim(items)

    def _infer_onnx(self, items: list[InferItem]) -> tuple[list[list[BoxResult]], Timings]:
        t_pre = perf_counter()
        w_in, h_in = self.input_size
        batch: list[np.ndarray] = []
        metas: list[tuple[int, int, float, float, float]] = []  # (w, h, scale, pad_x, pad_y)
        for item in items:
            frame = item.image
            h, w = frame.shape[:2]
            canvas, scale, pad_x, pad_y = letterbox(frame, (w_in, h_in))
            rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
            blob = rgb.astype(np.float32) / 255.0
            blob = np.transpose(blob, (2, 0, 1))
            batch.append(blob)
            metas.append((w, h, scale, pad_x, pad_y))
        pre_ms = (perf_counter() - t_pre) * 1000.0

        t_infer = perf_counter()
        arr = np.stack(batch, axis=0).astype(np.float32)
        outputs = self._session.run(None, {self._input_name: arr})
        infer_ms = (perf_counter() - t_infer) * 1000.0

        t_post = perf_counter()
        results: list[list[BoxResult]] = []
        for i, item in enumerate(items):
            decoded = decode_yolo(
                outputs[0],
                class_map=COCO_TO_SENTINEL,
                conf_threshold=self.conf_threshold,
                input_size=self.input_size,
            )
            w, h, scale, pad_x, pad_y = metas[i]
            # map 640-space (letterboxed) coords back to the source frame.
            boxes = [
                BoxResult(
                    class_name=b.class_name,
                    confidence=b.confidence,
                    x=max(0.0, min(1.0, ((b.x * w_in - pad_x) / scale) / w)),
                    y=max(0.0, min(1.0, ((b.y * h_in - pad_y) / scale) / h)),
                    w=max(0.0, min(1.0, (b.w * w_in / scale) / w)),
                    h=max(0.0, min(1.0, (b.h * h_in / scale) / h)),
                )
                for b in decoded
            ]
            results.append(boxes)
        post_ms = (perf_counter() - t_post) * 1000.0
        return results, Timings(pre_ms=pre_ms, infer_ms=infer_ms, post_ms=post_ms)

    def _infer_sim(self, items: list[InferItem]) -> tuple[list[list[BoxResult]], Timings]:
        t_pre = perf_counter()
        t_post = perf_counter()
        results: list[list[BoxResult]] = []
        for item in items:
            h, w = item.image.shape[:2]
            ctx = item.ctx or {}
            seed = int(ctx.get("seed", 1))
            frame_seq = int(ctx.get("frame_seq", 0))
            results.append(_sim_boxes(seed, frame_seq, w, h, self.conf_threshold))
        timings = Timings(pre_ms=(t_post - t_pre) * 1000.0, post_ms=(t_post - t_pre) * 1000.0)
        return results, timings


# ---------------------------------------------------------------------- #
# Deterministic simulation backend
# ---------------------------------------------------------------------- #
_SIM_BASE_SIZE = {
    "person": (0.05, 0.16),
    "bike": (0.06, 0.13),
    "car": (0.18, 0.11),
    "bus": (0.32, 0.16),
    "truck": (0.28, 0.15),
    "bicycle": (0.05, 0.12),
}


def _hash(seed: int) -> int:
    return (seed * 2654435761) & 0xFFFFFFFF


def _sim_boxes(
    seed: int,
    frame_seq: int,
    frame_w: int,
    frame_h: int,
    conf_threshold: float,
) -> list[BoxResult]:
    base = _hash(int(seed))
    count = 2 + (base % 3)  # 2..4 moving objects
    selected: list[BoxResult] = []
    for i in range(count):
        class_name = SENTINEL_CLASSES[(base >> (i * 3)) % len(SENTINEL_CLASSES)]
        phase_x = ((base >> (i * 5 + 2)) % 100) / 50.0 * math.pi
        phase_y = ((base >> (i * 7 + 3)) % 100) / 50.0 * math.pi
        speed = 1 + ((base >> (i * 3 + 1)) % 5)

        cx = 0.15 + 0.7 * (0.5 + 0.5 * math.sin(frame_seq / (60.0 / speed) + phase_x))
        cy = 0.15 + 0.7 * (0.5 + 0.5 * math.cos(frame_seq / (83.0 / speed) + phase_y))
        bw, bh = _SIM_BASE_SIZE[class_name]
        wobble = 1.0 + 0.08 * math.sin(frame_seq / 37.0 + i)
        bw *= wobble
        bh *= wobble

        conf = 0.58 + 0.30 * abs(math.sin(frame_seq / 41.0 + i * 1.7 + base % 7))
        conf = max(conf, conf_threshold + 0.02)
        conf = min(0.96, conf)

        # A "present window" per object keeps the parade dynamic over time.
        window = (frame_seq // 120) % 3
        hide = (i == count - 1) and ((base >> (i + 1)) % 3) == 0 and window == ((base + i) % 3)
        if hide:
            continue

        selected.append(
            BoxResult(
                class_name=class_name,
                confidence=round(conf, 4),
                x=round(min(0.9, max(0.0, cx - bw / 2)), 4),
                y=round(min(0.85, max(0.0, cy - bh / 2)), 4),
                w=round(min(bw, 1.0), 4),
                h=round(min(bh, 1.0), 4),
            )
        )
    return selected


__all__ = ["COCO_TO_SENTINEL", "SENTINEL_CLASSES", "YoloV12Plugin"]