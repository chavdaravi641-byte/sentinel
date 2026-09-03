"""Model loader: weight discovery + ONNX session construction.

Resolves model weights under the configured weights directory and builds an
onnxruntime session against the scheduler's chosen providers. When onnxruntime
is unavailable, a model file is missing, or the device reports no usable
provider, the loader returns a *null backend* — plugins then fall back to their
deterministic simulation path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.logging import log
from src.inference.cpu_fallback import CPUFallback
from src.inference.gpu import GpuScheduler
from src.inference.primitives import DeviceInfo


def _ort() -> Any:
    try:
        import onnxruntime as ort  # type: ignore[import-not-found]

        return ort
    except Exception:  # noqa: BLE001 - optional dependency
        return None


class ModelLoader:
    """Resolves and loads model weights into an onnxruntime session."""

    def __init__(self, weights_dir: str, accel_mode: str = "auto") -> None:
        self.weights_dir = Path(weights_dir)
        self.accel_mode = accel_mode.lower()
        self._scheduler = GpuScheduler(accel_mode=accel_mode)
        self.weights_dir.mkdir(parents=True, exist_ok=True)

    @property
    def scheduler(self) -> GpuScheduler:
        return self._scheduler

    def detect_device(self) -> DeviceInfo:
        device = self._scheduler.device
        return CPUFallback.ensure(device)

    def resolve_weights(self, model_name: str) -> Path | None:
        """Return the first onnx weights file for `model_name`, or None."""
        candidates = [
            self.weights_dir / model_name / f"{model_name}.onnx",
            self.weights_dir / model_name / f"{model_name.lower()}.onnx",
            self.weights_dir / f"{model_name}.onnx",
        ]
        model_dir = self.weights_dir / model_name
        try:
            candidates += sorted(
                (p for p in model_dir.glob("*.onnx") if p.is_file()),
                key=lambda p: p.name.lower(),
            )
        except OSError:
            pass
        accepted = (".onnx",)
        for candidate in candidates:
            if candidate.is_file() and candidate.suffix in accepted:
                return candidate
        return None

    def build_session(
        self, weights: Path, providers: list[str] | None = None
    ) -> tuple[Any, DeviceInfo]:
        """Build an onnxruntime session; reconcile device against reality."""
        ort = _ort()
        if ort is None:
            raise RuntimeError("onnxruntime is not installed.")
        device = self.detect_device()
        if not providers:
            providers = device.providers or ["CPUExecutionProvider"]
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess = ort.InferenceSession(str(weights), sess_options=opts, providers=providers)
        device = GpuScheduler.reconcile(device, list(sess.get_providers()))
        log.info(
            "ai.session_built",
            model=str(weights),
            providers=device.providers,
            accelerator=device.accelerator,
        )
        return sess, device


__all__ = ["ModelLoader"]