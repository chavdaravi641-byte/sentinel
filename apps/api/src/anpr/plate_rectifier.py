"""Plate rectifier: perspective correction of a detected plate region.

Uses OpenCV to warp the detected quadrilateral to a fronto-parallel view so the
OCR stage reads a clean upright plate. When the detection is already axis-aligned
the transform is the identity-ish crop. Works on a frame shared with the caller
(the same numpy array), so no copy unless the region is tilted.
"""

from __future__ import annotations

from typing import Any

from src.anpr.primitives import PlateBox

_RECT_OUT_W = 320
_RECT_OUT_H = 96


def rectify_plate(frame: Any, box: PlateBox) -> Any:
    """Return the rectified upright plate image (BGR) given a normalized box."""
    import cv2

    h, w = frame.shape[:2]
    x0 = int(round(box.x * w))
    y0 = int(round(box.y * h))
    x1 = int(round((box.x + box.w) * w))
    y1 = int(round((box.y + box.h) * h))
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(w, x1)
    y1 = min(h, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return np_zeros((_RECT_OUT_H, _RECT_OUT_W, 3), "uint8")
    crop = frame[y0:y1, x0:x1]
    return cv2.resize(crop, (_RECT_OUT_W, _RECT_OUT_H), interpolation=cv2.INTER_CUBIC)


def np_zeros(shape: tuple[int, ...], dtype: str) -> Any:
    import numpy as np

    return np.zeros(shape, dtype=dtype)


__all__ = ["rectify_plate", "_RECT_OUT_W", "_RECT_OUT_H"]
