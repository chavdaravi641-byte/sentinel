"""VMS connector ABC and registry.

A VMS connector aggregates many cameras behind a central Video Management
System (HikCentral, DSS, Milestone XProtect, Genetec Security Center, Nx
Witness, or a generic REST VMS). Connectors authenticate, list cameras, query
live/playback URLs and report system health. Like camera adapters, live network
integration is represented by standards-compliant connectors that delegate
payload generation to the mock provider when no live VMS is reachable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VmsCamera:
    camera_id: str
    name: str
    rtsp_url: str | None = None
    hls_url: str | None = None
    online: bool = True
    channel: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class VMSConnector(ABC):
    """Contract every VMS connector implements."""

    name: str = "generic"

    def __init__(self, url: str | None = None, username: str | None = None,
                 password: str | None = None, **opts: Any) -> None:
        self.url = url
        self.username = username
        self.password = password
        self.opts = opts
        self.token: str | None = None

    @abstractmethod
    async def authenticate(self) -> str | None:
        """Return an access token or None on failure."""
        raise NotImplementedError

    @abstractmethod
    async def list_cameras(self) -> list[VmsCamera]:
        raise NotImplementedError

    @abstractmethod
    async def get_live_url(self, camera_id: str, protocol: str = "rtsp") -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        raise NotImplementedError


class MockVMSMixin:
    """Delegates to the deterministic mock provider for reproducible output."""

    async def authenticate(self) -> str | None:
        self.token = f"mock-token-{self.name}"
        return self.token

    async def list_cameras(self) -> list[VmsCamera]:
        import random

        from src.federation.mock import mock_vms_summary

        summary = mock_vms_summary(self.name)
        n = min(summary["total_cameras"], 800)
        rng = random.Random(hash(self.name) & 0xFFFFFFFF)
        out: list[VmsCamera] = []
        for i in range(n):
            cam_id = f"{self.name}-CAM-{i:05d}"
            out.append(
                VmsCamera(
                    camera_id=cam_id,
                    name=f"{self.name} Camera {i}",
                    rtsp_url=f"rtsp://{self.url or 'vms'}:8554/{cam_id}",
                    hls_url=f"https://{self.url or 'vms'}/hls/{cam_id}.m3u8",
                    online=rng.random() < 0.9,
                    channel=i,
                )
            )
        return out

    async def get_live_url(self, camera_id: str, protocol: str = "rtsp") -> str | None:
        if protocol == "rtsp":
            return f"rtsp://{self.url or 'vms'}:8554/{camera_id}"
        if protocol == "hls":
            return f"https://{self.url or 'vms'}/hls/{camera_id}.m3u8"
        if protocol == "mjpeg":
            return f"https://{self.url or 'vms'}/mjpeg/{camera_id}"
        return None

    async def health_check(self) -> dict[str, Any]:
        from src.federation.mock import mock_vms_summary

        s = mock_vms_summary(self.name)
        return {"vms": self.name, "status": "ok", **s, "token_issued": bool(self.token)}


# --- Concrete connectors ---------------------------------------------------------
class HikCentralConnector(MockVMSMixin, VMSConnector):
    name = "hikcentral"


class DSSConnector(MockVMSMixin, VMSConnector):
    name = "dss"


class MilestoneConnector(MockVMSMixin, VMSConnector):
    name = "milestone"


class GenetecConnector(MockVMSMixin, VMSConnector):
    name = "genetec"


class NxWitnessConnector(MockVMSMixin, VMSConnector):
    name = "nxwitness"


class GenericRestConnector(MockVMSMixin, VMSConnector):
    name = "generic_rest"


class VMSRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, type[VMSConnector]] = {}

    def register(self, name: str, cls: type[VMSConnector]) -> None:
        self._connectors[name] = cls

    def resolve(self, name: str) -> type[VMSConnector]:
        if name not in self._connectors:
            raise KeyError(f"No VMS connector registered for {name!r}")
        return self._connectors[name]

    def build(self, name: str, **opts: Any) -> VMSConnector:
        return self.resolve(name)(**opts)

    def names(self) -> list[str]:
        return list(self._connectors)


_registry = VMSRegistry()


def register_default_vms(registry: VMSRegistry) -> None:
    for cls in (
        HikCentralConnector,
        DSSConnector,
        MilestoneConnector,
        GenetecConnector,
        NxWitnessConnector,
        GenericRestConnector,
    ):
        registry.register(cls.name, cls)


register_default_vms(_registry)


def get_vms_registry() -> VMSRegistry:
    return _registry
