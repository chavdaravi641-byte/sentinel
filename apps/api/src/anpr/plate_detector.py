"""YOLO plate detector stage.

Wraps the shared `StageBackend`. When a real YOLO plate-detector ONNX export is
present it runs the forward pass and decodes a `1,4+nc,N` output; otherwise it
runs a *deterministic, image-driven* simulation: it analyses the supplied frame
and locates a bright, locally-uniform region (a synthetic license-plate body),
emitting one simulated detection for it. Detection depends only on the frame's
pixel content — never on its dimensions, RNG state or timestamps — so the same
frame always produces the same result and the whole pipeline stays reproducible
in Docker without model artifacts. Frames without a plate produce no detections.

Output boxes are normalised 0..1 relative to the frame.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from src.anpr.onnx_backend import StageBackend
from src.anpr.primitives import PlateBox


class PlateDetector:
    """Detects license-plate regions in a frame."""

    stage = "plate"

    def __init__(self, backend: StageBackend, min_confidence: float = 0.35) -> None:
        self._backend = backend
        self.min_confidence = min_confidence
        self._device = backend.detect_device()
        self._session, self.is_sim, self._device = backend.build(self.stage, "yolo_plate")

    # ------------------------------------------------------------------ #
    def detect(self, image: Any) -> list[PlateBox]:
        if self.is_sim:
            return self._detect_sim(image)
        return self._detect_onnx(image)

    def _detect_sim(self, image: Any) -> list[PlateBox]:
        """Image-driven simulation: locate a bright, uniform plate region.

        The detection is derived entirely from the pixel statistics of the
        supplied frame (smoothness + brightness), never from its dimensions,
        RNG state or timestamps. A license plate is a region that is both bright
        and locally uniform (a solid plate body), which distinguishes it from
        the textured/noisy background. The same frame always yields the same
        detection, so the entire pipeline is deterministic.

        A ``PlateBox`` is emitted only when such a region is actually present in
        the frame; frames without a plate return nothing (no fabricated
        detections).
        """
        import cv2

        h, w = image.shape[:2]
        if h == 0 or w == 0:
            return []
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float32)
        else:
            gray = image.astype(np.float32)

        # Locally-uniform plate body: |pixel - box blurred| ~ 0 AND bright.
        blurred = cv2.boxFilter(gray, -1, (9, 9))
        roughness = np.abs(gray - blurred)
        plate_mask = ((roughness < 8.0) & (gray > 120.0)).astype(np.uint8)

        _, labels, stats, _ = cv2.connectedComponentsWithStats(
            plate_mask, connectivity=8
        )
        candidates: list[tuple[float, int, int, int, int]] = []
        for i in range(1, len(stats)):
            x, y, bw, bh, area = stats[i]
            # Reject pixel dust; require a large enough plate-like region.
            if area < 400:
                continue
            if bh <= 0 or bw / bh < 2.0:
                continue
            candidates.append((float(area), int(x), int(y), int(bw), int(bh)))

        if not candidates:
            return []

        # Keep the dominant plastic plate region (largest uniform bright blob).
        candidates.sort(key=lambda t: t[0], reverse=True)
        _, x, y, bw, bh = candidates[0]

        # Confidence derived from image statistics: fraction of the region that
        # is a solid bright plate body (uniformity+fill), plus its brightness.
        roi = gray[y : y + bh, x : x + bw]
        fill = float(plate_mask[y : y + bh, x : x + bw].mean()) if roi.size else 0.0
        brightness = float(roi.mean()) / 255.0
        conf = 0.50 + 0.45 * fill + 0.02 * max(0.0, min(1.0, brightness))
        conf = float(np.clip(conf, self.min_confidence + 0.05, 0.97))
        if conf < self.min_confidence:
            return []

        return [
            PlateBox(
                confidence=round(conf, 4),
                x=round(x / w, 4),
                y=round(y / h, 4),
                w=round(bw / w, 4),
                h=round(bh / h, 4),
            )
        ]

    def _detect_onnx(self, image: Any) -> list[PlateBox]:
        sess = self._session
        try:
            resized, scale, pad_x, pad_y = _letterbox(image, (640, 640))
            blob = resized.astype(np.float32) / 255.0
            blob = blob.transpose(2, 0, 1)[None, ...]
            inputs = sess.get_inputs()
            names = [i.name for i in inputs]
            feeds = {names[0]: blob}
            out = sess.run(None, feeds)[0]
            return _decode_plate_out(out[0], scale, pad_x, pad_y, self.min_confidence)
        except Exception:  # noqa: BLE001 - fall back to sim on runtime error
            return self._detect_sim(image)


def _letterbox(image: Any, target: tuple[int, int]) -> tuple[Any, float, int, int]:
    import cv2

    h, w = image.shape[:2]
    tw, th = target
    r = min(th / h, tw / w)
    new_w, new_h = round(w * r), round(h * r)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((th, tw, 3), 114, dtype=image.dtype)
    pad_x = (tw - new_w) // 2
    pad_y = (th - new_h) // 2
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
    return canvas, r, pad_x, pad_y


def _decode_plate_out(out: Any, scale: float, pad_x: int, pad_y: int, thresh: float) -> list[PlateBox]:
    """Decode a YOLO-style `[1, 4+nc, N]` plate output back to normalized boxes."""
    if out.ndim == 3:
        out = out[0]
    channels, num = out.shape
    if channels < 5:
        return []
    box = out[0:4]
    scores = out[4:] if channels > 4 else np.zeros((1, num), dtype=np.float32)
    input_w, input_h = 640, 640
    results: list[PlateBox] = []
    for i in range(num):
        cls_id = int(np.argmax(scores[:, i])) if scores.shape[0] > 0 else 0
        conf = float(scores[cls_id, i]) if scores.shape[0] > 0 else 0.0
        if conf < thresh:
            continue
        cx = (float(box[0, i]) - pad_x) / scale / input_w
        cy = (float(box[1, i]) - pad_y) / scale / input_h
        bw = float(box[2, i]) / scale / input_w
        bh = float(box[3, i]) / scale / input_h
        results.append(
            PlateBox(
                confidence=conf,
                x=max(0.0, min(1.0, cx - bw / 2)),
                y=max(0.0, min(1.0, cy - bh / 2)),
                w=max(0.0, min(1.0, bw)),
                h=max(0.0, min(1.0, bh)),
            )
        )
    return results


def _frame_seed(w: int, h: int) -> int:  # pragma: no cover - retained for back-compat
    return (hash((w, h)) & 0x7FFFFFFF) or 1


__all__ = ["PlateDetector"]
