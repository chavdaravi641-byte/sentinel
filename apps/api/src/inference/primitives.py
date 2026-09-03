"""Core data types shared across the Phase 3 inference engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    import numpy as np
except ImportError:  # pragma: no cover - numpy is a hard dep via opencv
    np = None  # type: ignore[assignment]


@dataclass
class BoxResult:
    """A single detection: class + confidence + normalized bbox (0..1)."""

    class_name: str
    confidence: float
    x: float  # top-left x
    y: float  # top-left y
    w: float
    h: float

    @property
    def cx(self) -> float:
        return self.x + self.w / 2.0

    @property
    def cy(self) -> float:
        return self.y + self.h / 2.0

    @property
    def area(self) -> float:
        return max(self.w, 0.0) * max(self.h, 0.0)

    def iou(self, other: BoxResult) -> float:
        inter_x0 = max(self.x, other.x)
        inter_y0 = max(self.y, other.y)
        inter_x1 = min(self.x + self.w, other.x + other.w)
        inter_y1 = min(self.y + self.h, other.y + other.h)
        inter = max(0.0, inter_x1 - inter_x0) * max(0.0, inter_y1 - inter_y0)
        union = self.area + other.area - inter
        if union <= 0:
            return 0.0
        return inter / union

    def to_dict(self, *, include_cxcy: bool = True) -> dict[str, Any]:
        payload = {
            "class_name": self.class_name,
            "confidence": round(float(self.confidence), 4),
            "x": round(float(self.x), 4),
            "y": round(float(self.y), 4),
            "w": round(float(self.w), 4),
            "h": round(float(self.h), 4),
        }
        if include_cxcy:
            payload["cx"] = round(float(self.cx), 4)
            payload["cy"] = round(float(self.cy), 4)
        return payload

    def __repr__(self) -> str:
        return f"<Box {self.class_name} conf={self.confidence:.2f} ({self.x:.2f},{self.y:.2f},{self.w:.2f}x{self.h:.2f})>"


@dataclass
class InferItem:
    """One frame submitted for inference with optional per-frame context."""

    image: Any  # np.ndarray BGR uint8 (H, W, 3)
    ctx: dict[str, Any] | None = None  # e.g. {"camera_id", "frame_seq", "seed"}


@dataclass
class DeviceInfo:
    """Runtime device/provider selection for the inference backend."""

    accelerator: str = "cpu"  # "cuda" | "cpu"
    device_name: str = "cpu"
    providers: list[str] = field(default_factory=list)
    gpu: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "accelerator": self.accelerator,
            "device_name": self.device_name,
            "providers": list(self.providers),
            "gpu": self.gpu,
        }


@dataclass
class Timings:
    """Preprocess / inference / postprocess timings for one run."""

    pre_ms: float = 0.0
    infer_ms: float = 0.0
    post_ms: float = 0.0

    @property
    def total_ms(self) -> float:
        return self.pre_ms + self.infer_ms + self.post_ms


@dataclass
class RunRecord:
    """Everything produced from analyzing one frame (ready for storage + WS)."""

    camera_id: str
    model_name: str
    model_version: str
    model_generation: int
    frame_seq: int
    width: int
    height: int
    timings: Timings
    batch_size: int
    fps: float
    accelerator: str
    backend: str
    detections: list[BoxResult]
    detections_tracked: list[tuple[int, BoxResult]] = field(default_factory=list)


__all__ = [
    "BoxResult",
    "DeviceInfo",
    "InferItem",
    "RunRecord",
    "Timings",
]