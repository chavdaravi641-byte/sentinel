"""CPU fallback wrapper for the inference engine.

Guarantees the engine always has a usable compute path: when GPU acceleration
is requested but unavailable the scheduler reconciles to CPU, and when a plugin
has no hardware runtime at all the deterministic simulation backend takes over
so downstream systems (tracking, event bus, detection store, alert engine) can
be exercised end-to-end without a model payload present.
"""

from __future__ import annotations

from typing import Any

from src.inference.primitives import DeviceInfo


class CPUFallback:
    """Reusable fallback helpers used across the inference stack."""

    @staticmethod
    def ensure(device: DeviceInfo) -> DeviceInfo:
        """Downgrade an unusable or explicitly overridden accelerator to CPU."""
        if device is None:
            return DeviceInfo(accelerator="cpu", device_name="cpu", providers=["CPUExecutionProvider"])
        if device.accelerator != "cpu" and not device.providers:
            device.accelerator = "cpu"
            device.device_name = "cpu (fallback)"
            device.providers = ["CPUExecutionProvider"]
        return device

    @staticmethod
    def provider_names(device: DeviceInfo) -> list[str]:
        return list(device.providers or [])

    @staticmethod
    def describe(device: DeviceInfo) -> dict[str, Any]:
        return device.to_dict()


__all__ = ["CPUFallback"]