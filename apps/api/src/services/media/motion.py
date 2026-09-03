"""Motion snapshot pipeline (OpenCV frame difference).

This is intentionally NOT AI: it performs a per-pixel Gaussian-blurred absolute
difference against a slowly adapting scene background and fires when a
fraction of the frame changes. Thresholds are configurable. If OpenCV is
unavailable at runtime the detector degrades to a no-op (motion stays off)
rather than fail the ingest pipeline.
"""

from dataclasses import dataclass
from typing import Any

from src.core.config import settings
from src.core.logging import log

try:  # pragma: no cover - runtime guard
    import cv2
    import numpy as np

    _CV2_OK = True
except ImportError:  # pragma: no cover - fallback path
    cv2 = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    _CV2_OK = False
    log.warning("motion.opencv_unavailable", fallback="disabled")


@dataclass(frozen=True)
class MotionResult:
    motion: bool
    score: float  # fraction of changed pixels (0..1)
    ready: bool  # True once the background reference has converged


class MotionDetector:
    def __init__(
        self,
        *,
        background_frames: int | None = None,
        percent_threshold: float | None = None,
        pixel_threshold: int | None = None,
        detect_fps: int | None = None,
    ) -> None:
        self._background_frames = background_frames or settings.MOTION_BACKGROUND_FRAMES
        self._percent_threshold = percent_threshold or settings.MOTION_PERCENT_THRESHOLD
        self._pixel_threshold = pixel_threshold or settings.MOTION_PIXEL_THRESHOLD
        self._detect_interval = 1.0 / max(1, detect_fps or settings.MOTION_DETECT_FPS)
        self._background: Any = None
        self._accumulator: Any = None
        self._ready_count = 0
        self._last_run = 0.0
        self._enabled = _CV2_OK and settings.MOTION_ENABLED

    @property
    def enabled(self) -> bool:
        return self._enabled

    def analyze(self, jpeg: bytes, now: float) -> MotionResult:
        """Decode and diff one JPEG frame. Safe to call on an executor thread."""
        if not self._enabled:
            return MotionResult(motion=False, score=0.0, ready=True)
        if now - self._last_run < self._detect_interval:
            return MotionResult(motion=False, score=0.0, ready=True)
        self._last_run = now
        try:  # motion analysis must degrade, never fail the pipeline
            img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_GRAYSCALE)  # type: ignore[union-attr]
            if img is None:
                return MotionResult(motion=False, score=0.0, ready=True)
            small = cv2.resize(img, (160, 90))  # cheap baseline for diffing
            small = cv2.GaussianBlur(small, (5, 5), 0)

            if self._background is None:
                self._accumulator = small.astype(np.float32)  # type: ignore[union-attr]
                self._background = small.copy()
                self._ready_count = 1
                return MotionResult(motion=False, score=0.0, ready=False)

            if self._ready_count < self._background_frames:
                self._accumulator += small.astype(np.float32)  # type: ignore[operator,union-attr]
                self._ready_count += 1
                if self._ready_count >= self._background_frames:
                    self._background = (self._accumulator / self._ready_count).astype(np.uint8)  # type: ignore[union-attr]
                return MotionResult(motion=False, score=0.0, ready=False)

            fc, _th = cv2.threshold(  # type: ignore[attr-defined]
                cv2.absdiff(small, self._background), self._pixel_threshold, 255, cv2.THRESH_BINARY
            )
            score = float(fc.mean() / 255.0)
            motion = score >= self._percent_threshold
            # Adapt the background only while the scene is quiet.
            if not motion:
                blended = (
                    self._background.astype(np.float32) * 0.95  # type: ignore[union-attr]
                    + small.astype(np.float32) * 0.05
                )
                self._background = np.clip(blended, 0.0, 255.0).astype(np.uint8)  # type: ignore[union-attr]
            return MotionResult(motion=motion, score=round(score, 4), ready=True)
        except Exception:
            return MotionResult(motion=False, score=0.0, ready=True)


__all__ = ["_CV2_OK", "MotionDetector", "MotionResult"]