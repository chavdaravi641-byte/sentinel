"""Camera / frame self-diagnostics.

Detects common image-quality degradations that reduce ANPR accuracy:

* **blur**        — overall out-of-focus / Gaussian blur (low high-frequency energy)
* **motion_blur** — directional smear (anisotropic energy drop)
* **low_light**   — mean luma well below a healthy range
* **over_exposure** — a large saturated-white fraction / very high mean luma
* **under_exposure** — a large near-black fraction with low dynamic range
* **dirty_lens**  — a persistent translucent smudge across a broad central region

Each metric runs in pure OpenCV/numpy and returns a structured diagnosis with a
0..1 severity and a human recommendation. Diagnostics are best-effort heuristics
(clearly labeled), not a substitute for real hardware QA.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass
class DiagnosisItem:
    name: str
    severity: float  # 0..1 (1 = worst)
    ok: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "severity": round(self.severity, 3),
            "ok": self.ok,
            "detail": self.detail,
        }


class FrameDiagnostics:
    """Analyze a single frame for capture-quality problems."""

    def analyze(self, image: Any) -> list[DiagnosisItem]:
        img = np.asarray(image)
        if img.ndim == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        h, w = gray.shape
        if h < 16 or w < 16:
            return [DiagnosisItem("blur", 1.0, False, "frame too small to analyze")]

        return [
            self._blur(gray),
            self._motion_blur(gray),
            self._light(gray),
            self._over_exposure(gray),
            self._under_exposure(gray),
            self._dirty_lens(gray, h, w),
        ]

    @staticmethod
    def _variance_of_laplacian(gray) -> float:
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def _blur(self, gray) -> DiagnosisItem:
        var = self._variance_of_laplacian(gray)
        # Healthy frames sit above ~100; sharpen the mapping around 100.
        severity = max(0.0, min(1.0, (400.0 - var) / 400.0)) if var < 400 else 0.0
        ok = var >= 100
        return DiagnosisItem("blur", severity, ok,
                             f"Laplacian variance={var:.1f} (>=100 healthy)")

    def _motion_blur(self, gray) -> DiagnosisItem:
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        ex = float(np.abs(gx).mean())
        ey = float(np.abs(gy).mean())
        ratio = ex / max(ey, 1e-6)
        # Strongly anisotropic gradients indicate directional motion smear.
        severity = max(0.0, min(1.0, (max(ratio, 1.0 / max(ratio, 1e-6)) - 1.5) / 4.0))
        ok = 0.4 <= ratio <= 2.5
        return DiagnosisItem("motion_blur", severity, ok,
                             f"gradient anisotropy x/y={ratio:.2f} (0.4..2.5 ok)")

    def _light(self, gray) -> DiagnosisItem:
        mean = float(gray.mean())
        severity = 0.0
        if mean < 40:
            severity = (40 - mean) / 40.0
        elif mean > 230:
            severity = (mean - 230) / 25.0
        ok = 40 <= mean <= 230
        return DiagnosisItem("low_light", severity, ok,
                             f"mean luma={mean:.1f} (40..230 healthy)")

    def _over_exposure(self, gray) -> DiagnosisItem:
        sat = float((gray > 245).mean())
        severity = max(0.0, min(1.0, (sat - 0.02) / 0.30))
        ok = sat < 0.02
        return DiagnosisItem("over_exposure", severity, ok,
                             f"saturated fraction={sat:.3f} (<0.02 ok)")

    def _under_exposure(self, gray) -> DiagnosisItem:
        dark = float((gray < 12).mean())
        dv = float(gray.std())
        severity = max(0.0, min(1.0, (dark - 0.05) / 0.50))
        ok = dark < 0.05 and dv >= 10
        return DiagnosisItem("under_exposure", severity, ok,
                             f"near-black fraction={dark:.3f}, std={dv:.1f} (ok: <0.05 & std>=10)")

    def _dirty_lens(self, gray, h, w) -> DiagnosisItem:
        # A lens smudge is a broad, low-gradient region in the central band.
        center = gray[int(h * 0.2) : int(h * 0.8), int(w * 0.2) : int(w * 0.8)]
        local_var = float(center.var())
        severity = max(0.0, min(1.0, (0.0008 - local_var) / 0.0008)) if local_var < 0.0008 else 0.0
        ok = local_var >= 0.0008 or (center.std() >= 8)
        return DiagnosisItem("dirty_lens", severity, ok,
                             f"central variance={local_var:.6f} (smudge if ~0)")

    def summarize(self, image: Any, threshold: float = 0.5) -> dict[str, Any]:
        items = self.analyze(image)
        flagged = [i for i in items if i.severity >= threshold]
        return {
            "ok": len(flagged) == 0,
            "severity": round(max((i.severity for i in items), default=0.0), 3),
            "issues": [i.to_dict() for i in flagged],
            "all": [i.to_dict() for i in items],
        }


__all__ = ["FrameDiagnostics", "DiagnosisItem"]
