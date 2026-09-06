"""Synthetic ANPR ground-truth corpus generator.

This module produces a *controlled, reproducible* dataset on which the ANPR
pipeline's stages can be measured without any heavyweight model weights or real
video. Plates are rendered into frames with a real 5x7 pixel glyph font and a
known bounding box + ground-truth string, under a set of labeled capture
conditions (day / night / rain / low_light / blur / motion_blur).

Because both ground truth and the rendered appearance are fully deterministic,
precision / recall / character accuracy / word accuracy computed against this
corpus are *real measured values* in the controlled sense — not fabricated. They
describe "how well the sim backend recovers its own deterministic appearance."
Metrics that require real hardware (GPU util, real-world day/night video) are
reported separately and plainly marked "Not Measured" in the validation report
with instructions for measuring them.

The sim detector/OCR stages are *content-aware*: they recover the plate from the
actual rendered pixels, so the evaluation is meaningful rather than circular by
construction (the detector must still locate the band and ≥ the glyph block, and
the OCR must segment and read glyphs).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from src.anpr.glyphs import glyph as _glyph_rows, paint_glyph


@dataclass
class CaptureCondition:
    """A labeled photographic condition with a deterministic perturbation."""

    name: str  # day / night / rain / low_light / blur / motion_blur
    brightness: float = 1.0
    noise: float = 0.0
    blur_kernel: int = 0
    rain: bool = False
    motion: bool = False

    def apply(self, frame: np.ndarray, rng: random.Random) -> np.ndarray:
        img = frame.astype(np.float32)
        img *= self.brightness
        img = np.clip(img, 0, 255)
        if self.noise > 0:
            img += rng.gauss(0, 1) * self.noise
            img = np.clip(img, 0, 255)
        out = img.astype(np.uint8)
        if self.blur_kernel > 1:
            out = _gaussian_blur(out, self.blur_kernel)
        if self.motion:
            out = _motion_blur(out, 7)
        if self.rain:
            out = _add_rain(out, rng)
        return out


def conditions() -> list[str]:
    return ["day", "night", "rain", "low_light", "blur", "motion_blur"]


def make_condition(name: str) -> CaptureCondition:
    name = name.lower()
    table = {
        "day": CaptureCondition("day", brightness=1.0, noise=4.0),
        "night": CaptureCondition("night", brightness=0.55, noise=14.0),
        "rain": CaptureCondition("rain", brightness=0.85, noise=8.0, rain=True),
        "low_light": CaptureCondition("low_light", brightness=0.3, noise=18.0),
        "blur": CaptureCondition("blur", brightness=1.0, noise=6.0, blur_kernel=5),
        "motion_blur": CaptureCondition("motion_blur", brightness=1.0, noise=6.0, motion=True),
    }
    return table.get(name, table["day"])


@dataclass
class SyntheticSample:
    """One labeled ANPR sample: rendered frame + ground truth."""

    plate: str
    normalized_plate: str
    condition: str
    frame: np.ndarray  # HxWx3 BGR
    gx0: float
    gy0: float
    gx1: float
    gy1: float  # normalized bbox

    @property
    def trunc(self) -> np.ndarray:
        return self.frame


_STATES = ["GJ", "MH", "DL", "UP", "RJ", "TN", "KA", "MP", "PB", "HR"]


class SyntheticDataset:
    """Generate a deterministic corpus of labeled ANPR frames."""

    def __init__(self, seed: int = 2026) -> None:
        self._rng = random.Random(seed)

    def _plate_string(self) -> str:
        state = self._rng.choice(_STATES)
        rto = f"{self._rng.randint(1, 99):02d}"
        letters = "".join(self._rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(2))
        number = f"{self._rng.randint(1000, 9999)}"
        return f"{state}{rto}{letters}{number}"

    def generate(self, size: int = 200, width: int = 640, height: int = 360, condition: str = "day") -> list[SyntheticSample]:
        rng = self._rng
        cap = make_condition(condition)
        samples: list[SyntheticSample] = []
        for _ in range(size):
            plate = self._plate_string()
            frame, (bx0, by0, bx1, by1) = _render_plate_frame(
                width, height, plate, rng
            )
            frame = cap.apply(frame, rng)
            samples.append(
                SyntheticSample(
                    plate=plate,
                    normalized_plate="".join(c for c in plate if c.isalnum()).upper(),
                    condition=condition,
                    frame=frame,
                    gx0=bx0, gy0=by0, gx1=bx1, gy1=by1,
                )
            )
        return samples


def _render_plate_frame(
    width: int, height: int, plate: str, rng: random.Random
) -> tuple[np.ndarray, tuple[float, float, float, float]]:
    """Render a plate string into a frame; return (frame, normalized bbox)."""
    bg = np.full((height, width, 3), rng.randint(60, 110), dtype=np.uint8)
    # subtle ground texture
    for _ in range(400):
        x, y = rng.randint(0, width - 1), rng.randint(0, height - 1)
        bg[y, x] = min(255, int(bg[y, x]) + rng.randint(-20, 30))

    scale = rng.randint(3, 4)
    gap = max(1, scale // 2)
    margin = scale * 3
    text_w = sum((5 + 1) * scale for _ in plate) + gap * (len(plate) - 1)
    text_h = 7 * scale
    pw = text_w + margin * 2 + 10
    ph = text_h + margin * 2
    px = rng.randint(0, max(0, width - pw))
    py = rng.randint(int(height * 0.40), max(int(height * 0.40), height - ph - 10))

    # white plate body, dark border
    body = np.full((ph, pw, 3), 235, dtype=np.uint8)
    cv_paint_rect(body, 0, 0, pw, ph, (30, 30, 34), 2)

    # draw glyphs (near-black "printed" digits)
    xoff = margin + 5
    yoff = margin
    glyph_color = (24, 24, 26)
    for ch in plate:
        rows = _glyph_rows(ch)
        if rows:
            paint_glyph(body, rows, xoff, yoff, scale, glyph_color)
            xoff += 5 * scale + gap
        else:
            xoff += 5 * scale + gap
    bg[py : py + ph, px : px + pw] = body
    gt = (px / width, py / height, (px + pw) / width, (py + ph) / height)
    return bg, gt


def _paint_glyph(canvas, glyph, x0, y0, scale, color) -> None:
    for r, row in enumerate(glyph):
        for c, lit in enumerate(row):
            if lit == "1":
                canvas[y0 + r * scale : y0 + (r + 1) * scale,
                       x0 + c * scale : x0 + (c + 1) * scale] = color


def cv_paint_rect(img, x0, y0, x1, y1, color, thickness) -> None:
    import cv2

    cv2.rectangle(img, (x0, y0), (x1, y1), color, thickness)


def _gaussian_blur(img, k) -> np.ndarray:
    import cv2

    return cv2.GaussianBlur(img, (k, k), 0)


def _motion_blur(img, k) -> np.ndarray:
    import cv2

    kernel = np.zeros((k, k))
    kernel[int((k - 1) / 2), :] = 1.0 / k
    return cv2.filter2D(img, -1, kernel)


def _add_rain(img, rng) -> np.ndarray:
    import cv2

    out = img.copy()
    for _ in range(140):
        x0 = rng.randint(0, img.shape[1] - 1)
        y0 = rng.randint(0, img.shape[0] - 1)
        x1 = min(img.shape[1] - 1, x0 + rng.randint(5, 14))
        y1 = min(img.shape[0] - 1, y0 + rng.randint(12, 30))
        cv2.line(out, (x0, y0), (x1, y1), (200, 200, 210), 1)
    return out


__all__ = [
    "SyntheticDataset",
    "SyntheticSample",
    "CaptureCondition",
    "conditions",
    "make_condition",
]
