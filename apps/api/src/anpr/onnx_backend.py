"""ANPR ONNX backend: session construction with automatic CPU fallback.

Mirrors the Phase 3 `GpuScheduler`/`ModelLoader` split but stays independent —
Phase 4 does not modify Phase 1/2/3 code. Provides:

* device detection (auto -> CUDA when available, else CPU)
* building onnxruntime sessions against the chosen providers
* a `sim` (deterministic simulation) backend used whenever onnxruntime or the
  required weight files are absent, so the whole pipeline runs in Docker even
  without model artifacts.

`StageBackend` is a tiny wrapper exposing `build(model_name)` and `sim` flags so
each ANPR stage (plate / ocr / vehicle) shares one code path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.core.logging import log


def _ort() -> Any:
    try:
        import onnxruntime as ort  # type: ignore[import-not-found]

        return ort
    except Exception:  # noqa: BLE001 - optional dependency
        return None


def _detect_providers(mode: str) -> tuple[str, list[str], str]:
    """Return (accelerator, providers, device_name). CPU-falls-back automatically."""
    ort = _ort()
    if ort is None:
        return "cpu", [], "cpu (no ONNX runtime)"
    available = []
    try:
        available = list(ort.get_available_providers() or [])
    except Exception:  # pragma: no cover - defensive
        available = []
    has_cuda = "CUDAExecutionProvider" in available
    mode = (mode or "auto").lower()
    if mode == "cuda" and not has_cuda:
        mode = "auto"
    if mode == "cpu" or not has_cuda:
        providers = ["CPUExecutionProvider"] if "CPUExecutionProvider" in available else []
        name = f"cpu ({available[0] if available else 'onnxruntime'})"
        return "cpu", providers, name
    # CUDA preferred; onnxruntime silently drops providers that cannot init and
    # falls back to CPU — the automatic CPU fallback for GPU-less hosts.
    return "cuda", ["CUDAExecutionProvider", "CPUExecutionProvider"], "cuda:0"


class StageBackend:
    """Builds an onnxruntime session for an ANPR stage, else reports `sim`."""

    def __init__(self, weights_dir: str, accel_mode: str = "auto") -> None:
        self.weights_dir = Path(weights_dir)
        self.accel_mode = accel_mode.lower()
        self._device: tuple[str, list[str], str] | None = None
        self._cache: dict[str, tuple[Any, str]] = {}

    # -- device --------------------------------------------------------- #
    def detect_device(self) -> dict[str, Any]:
        if self._device is None:
            self._device = _detect_providers(self.accel_mode)
        accelerator, providers, name = self._device
        return {
            "accelerator": accelerator,
            "providers": list(providers),
            "device_name": name,
        }

    # -- asset resolution ------------------------------------------------ #
    def resolve(self, stage: str, names: list[str]) -> Path | None:
        """Find the first existing ONNX asset for `stage` under the weights dir."""
        stage_dir = self.weights_dir / stage
        candidates = [self.weights_dir / n for n in names]
        candidates += [stage_dir / n for n in names]
        try:
            candidates += sorted(
                (p for p in stage_dir.glob("*.onnx") if p.is_file()),
                key=lambda p: p.name.lower(),
            )
        except OSError:
            pass
        for c in candidates:
            if c.is_file() and c.suffix == ".onnx":
                return c
        return None

    # -- session --------------------------------------------------------- #
    def build(self, stage: str, name: str) -> tuple[Any | None, bool, dict[str, Any]]:
        """Build a session for `stage`/`name`.

        Returns ``(session, is_sim, device)``. When onnxruntime or the asset is
        missing, returns ``(None, True, device)`` so callers use their sim path.
        """
        ort = _ort()
        dev = self.detect_device()
        if ort is None:
            return None, True, dev
        asset = self.resolve(stage, [f"{name}.onnx"])
        if asset is None:
            return None, True, dev
        try:
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess = ort.InferenceSession(
                str(asset),
                sess_options=opts,
                providers=dev["providers"] or ["CPUExecutionProvider"],
            )
            active = list(sess.get_providers())
            if "CUDAExecutionProvider" in active:
                dev["accelerator"] = "cuda"
                dev["device_name"] = "cuda:0"
                dev["providers"] = active
            else:
                dev["accelerator"] = "cpu"
                dev["device_name"] = f"cpu ({', '.join(active) if active else 'onnxruntime'})"
                dev["providers"] = active or ["CPUExecutionProvider"]
            self._cache[stage] = (sess, dev["accelerator"])
            log.info("anpr.session_built", stage=stage, model=asset.name, accelerator=dev["accelerator"])
            return sess, False, dev
        except Exception as exc:  # noqa: BLE001 - fall through to sim on load failure
            log.warning("anpr.session_failed", stage=stage, error=str(exc), fallback="sim")
            return None, True, dev

    def session(self, stage: str) -> Any | None:
        entry = self._cache.get(stage)
        return entry[0] if entry else None

    def accelerator(self, stage: str | None = None) -> str:
        if stage and stage in self._cache:
            return self._cache[stage][1]
        return self.detect_device()["accelerator"]


__all__ = ["StageBackend", "_ort"]
