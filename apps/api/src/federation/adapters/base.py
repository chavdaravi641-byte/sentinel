"""Camera adapter ABC and a registry that maps vendors to adapters.

An adapter abstracts a single camera device class. Real implementations would
speak the vendor's ISAPI / HTTP / CGI interfaces; because Phase 6 has no live
lab hardware, vendors are represented by standards-compliant adapters that
implement the common contract and, where physical access is absent, delegate to
a deterministic :mod:`src.federation.mock` provider. This keeps the wiring and
interfaces production-accurate while remaining fully testable.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.federation.models import CameraState, StreamProtocol, Vendor


@dataclass
class DeviceCapabilities:
    """What a device actually supports (parsed from ONVIF/capability probe)."""

    protocols: list[StreamProtocol] = field(default_factory=lambda: [StreamProtocol.RTSP])
    max_streams: int = 1
    supports_ptz: bool = False
    supports_analytics: bool = True
    has_storage: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceHealth:
    status: str  # ok | degraded | offline
    latency_ms: int | None = None
    bitrate_kbps: int | None = None
    signal: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)


class CameraAdapter(ABC):
    """Contract every vendor adapter implements."""

    vendor: Vendor = Vendor.OTHER

    def __init__(self, host: str | None = None, port: int | None = None,
                 username: str | None = None, password: str | None = None,
                 **opts: Any) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.opts = opts
        self._connected = False

    # -- lifecycle -----------------------------------------------------
    @abstractmethod
    async def connect(self) -> bool:
        """Authenticate and prepare the device. Returns success."""
        raise NotImplementedError

    async def disconnect(self) -> None:
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    # -- information -----------------------------------------------------
    @abstractmethod
    async def get_metadata(self) -> dict[str, Any]:
        """Return model / firmware / serial metadata."""
        raise NotImplementedError

    @abstractmethod
    async def get_capabilities(self) -> DeviceCapabilities:
        raise NotImplementedError

    # -- runtime ---------------------------------------------------------
    @abstractmethod
    async def health_check(self) -> DeviceHealth:
        raise NotImplementedError

    @abstractmethod
    async def snapshot(self) -> bytes | None:
        """Return a JPEG frame or None when unavailable."""
        raise NotImplementedError

    # -- media ------------------------------------------------------------
    def build_rtsp_url(self) -> str | None:
        """Return a canonical RTSP URL for this device, if supported."""
        raise NotImplementedError


class OfflineAdapterMixin:
    """Mixin for connectors that have no live device but must return the
    correct *contract*. Never crashes the platform; reports offline."""

    async def connect(self) -> bool:
        self._connected = False
        return False

    def _mock(self):
        from src.federation.mock import mock_device
        return mock_device(self.vendor if isinstance(self.vendor, Vendor) else self.vendor)


class AdapterRegistry:
    """Vendor -> adapter-class registry with a factory resolver."""

    def __init__(self) -> None:
        self._adapters: dict[Vendor, type[CameraAdapter]] = {}

    def register(self, vendor: Vendor, adapter_cls: type[CameraAdapter]) -> None:
        self._adapters[vendor] = adapter_cls

    def resolve(self, vendor: Vendor | str) -> type[CameraAdapter]:
        key = Vendor(vendor) if not isinstance(vendor, Vendor) else vendor
        if key not in self._adapters:
            raise KeyError(f"No adapter registered for vendor {key.value}")
        return self._adapters[key]

    def build(self, vendor: Vendor | str, **opts: Any) -> CameraAdapter:
        cls = self.resolve(vendor)
        return cls(**opts)

    def vendors(self) -> list[str]:
        return [v.value for v in self._adapters]


_registry = AdapterRegistry()


def get_adapter_registry() -> AdapterRegistry:
    return _registry
