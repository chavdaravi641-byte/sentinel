"""GPU scheduler: device/provider selection + batch planning for inference.

The engine asks the scheduler for the active device and, each drain window, for
a batch plan. On accelerators it packs frames from multiple cameras into a
single forward pass (`AI_BATCH_SIZE`); on CPU it always runs single-frame to
keep latency predictable.
"""

from __future__ import annotations

from time import monotonic
from typing import Any

from src.core.logging import log
from src.inference.primitives import DeviceInfo


def _ort() -> Any:
    try:
        import onnxruntime as ort  # type: ignore[import-not-found]

        return ort
    except Exception:  # noqa: BLE001 - optional dependency
        return None


class GpuScheduler:
    """Selects the best available accelerator and sizes inference batches."""

    def __init__(
        self,
        accel_mode: str = "auto",
        batch_size: int = 4,
        batch_window_ms: float = 15.0,
    ) -> None:
        self.mode = accel_mode.lower()
        self.batch_size = max(1, int(batch_size))
        self.window_ms = float(batch_window_ms)
        self._device: DeviceInfo | None = None
        self._detected_ts: float = 0.0

    @property
    def device(self) -> DeviceInfo:
        if self._device is None or monotonic() - self._detected_ts > 60:
            self._device = self._detect()
            self._detected_ts = monotonic()
        return self._device

    def _detect(self) -> DeviceInfo:
        ort = _ort()
        providers: list[str] = []
        if ort is None:
            log.info("ai.device", accelerator="cpu", reason="onnxruntime not installed")
            return DeviceInfo(accelerator="cpu", device_name="cpu (no ONNX runtime)", providers=[])

        available = []
        try:
            available = list(ort.get_available_providers() or [])
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("ai.ort_providers_failed", error=str(exc))

        has_cuda = "CUDAExecutionProvider" in available
        if self.mode == "cuda" and not has_cuda:
            log.warning("ai.accel.forced_cuda_unavailable", fallback="cpu")
            self.mode = "auto"

        if self.mode == "cpu" or not has_cuda:
            providers = ["CPUExecutionProvider"] if "CPUExecutionProvider" in available else []
            return DeviceInfo(
                accelerator="cpu",
                device_name=f"cpu ({available[0] if available else 'onnxruntime'})",
                providers=providers,
            )

        # CUDA preferred. onnxruntime silently drops providers that cannot
        # initialize (e.g. missing CUDA DLLs) and falls through to the next —
        # this is the automatic CPU fallback path for GPU-less hosts. The real
        # session build in the ModelLoader confirms which providers actually
        # load and reconciles the DeviceInfo afterwards.
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        return DeviceInfo(
            accelerator="cuda",
            device_name="cuda:0",
            providers=providers,
        )

    @staticmethod
    def reconcile(device: DeviceInfo, active_providers: list[str]) -> DeviceInfo:
        """Correct the device after a session build reports active providers."""
        if not active_providers:
            device.providers = ["CPUExecutionProvider"]
            device.accelerator = "cpu"
            device.device_name = "cpu (no providers)"
        else:
            device.providers = list(active_providers)
            if "CUDAExecutionProvider" in active_providers:
                device.accelerator = "cuda"
                device.device_name = "cuda:0"
            else:
                device.accelerator = "cpu"
                device.device_name = f"cpu ({', '.join(active_providers)})"
        return device

    def batch_plan(self, pending: int) -> list[int]:
        """Split `pending` items into one batch of <= `batch_size` (greedy)."""
        if pending <= 0:
            return []
        if self.device.accelerator == "cpu" or self.batch_size <= 1:
            return [1] * pending
        chunks: list[int] = []
        remaining = pending
        while remaining > 0:
            size = min(self.batch_size, remaining)
            chunks.append(size)
            remaining -= size
        return chunks

    def gpu_usage(self) -> dict[str, Any] | None:
        """NVML utilization snapshot (optional pynvml); None when unavailable."""
        try:
            import pynvml  # type: ignore[import-not-found]
        except Exception:  # noqa: BLE001 - optional dependency
            return None
        try:
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return {
                "name": name.decode() if isinstance(name, bytes) else str(name),
                "utilization_pct": int(util.gpu),
                "memory_used_mb": round(mem.used / (1024 * 1024), 1),
                "memory_total_mb": round(mem.total / (1024 * 1024), 1),
            }
        except Exception as exc:  # pragma: no cover - host NVML access is optional
            log.warning("ai.nvml_failed", error=str(exc))
            return None
        finally:
            try:
                pynvml.nvmlShutdown()
            except Exception:  # noqa: BLE001, S110 - best effort shutdown
                pass


__all__ = ["GpuScheduler"]