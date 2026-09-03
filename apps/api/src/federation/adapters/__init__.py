"""Adapter package: vendor adapters + registry wiring.

Importing this package registers every known adapter in the shared registry so
that :func:`get_adapter_registry().resolve(...)` can build the right adapter for
any supported vendor.
"""

from __future__ import annotations

from src.federation.adapters.base import (
    AdapterRegistry,
    CameraAdapter,
    DeviceCapabilities,
    DeviceHealth,
    get_adapter_registry,
)
from src.federation.adapters.onvif_rtsp import OnvifAdapter, RtspAdapter
from src.federation.adapters.vendors import ALL_VENDORS
from src.federation.models import Vendor


def register_default_adapters(registry: AdapterRegistry) -> None:
    """Register all built-in adapters onto a registry (idempotent)."""
    for vendor, cls in ALL_VENDORS.items():
        registry.register(vendor, cls)
    registry.register(Vendor.ONVIF, OnvifAdapter)
    registry.register(Vendor.RTSP, RtspAdapter)


# Wire the process-wide registry on import.
register_default_adapters(get_adapter_registry())


__all__ = [
    "AdapterRegistry",
    "CameraAdapter",
    "DeviceCapabilities",
    "DeviceHealth",
    "get_adapter_registry",
    "register_default_adapters",
    "ONVIF_AVAILABLE",
]


def _onvif_lib_available() -> bool:
    try:  # pragma: no cover - depends on runtime image
        import onvif  # noqa: F401
        return True
    except Exception:
        return False


ONVIF_AVAILABLE = _onvif_lib_available()
