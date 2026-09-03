"""Generic ONVIF and plain-RTSP adapters for Profile-S / Profile-T devices
that are not matched by a dedicated vendor adapter."""

from __future__ import annotations

from typing import Any

from src.federation.adapters.base import (
    CameraAdapter,
    DeviceCapabilities,
    DeviceHealth,
    OfflineAdapterMixin,
)
from src.federation.mock import mock_device, mock_health
from src.federation.models import StreamProtocol, Vendor


class OnvifAdapter(OfflineAdapterMixin, CameraAdapter):
    """ONVIF Profile-S / Profile-T transmitter (discovery vs. live profile)."""

    vendor = Vendor.ONVIF

    async def get_device_service(self) -> str:
        return f"http://{self.host or '[host]'}:{self.port or 80}/onvif/device_service"

    async def get_media_profile(self) -> dict[str, Any]:
        meta = await self.get_metadata()
        return {
            "profile_token": "MainStream",
            "video_encoder": meta.get("model"),
            "rtsp_url": self.build_rtsp_url(),
        }

    async def get_metadata(self) -> dict[str, Any]:
        base = mock_device("onvif", self.host)
        base["onvif_xaddr"] = await self.get_device_service()
        return base

    async def get_capabilities(self) -> DeviceCapabilities:
        meta = await self.get_metadata()
        return DeviceCapabilities(
            protocols=[StreamProtocol(p) for p in meta["protocols"]],
            max_streams=meta["max_streams"],
            supports_ptz=meta["supports_ptz"],
            supports_analytics=meta["supports_analytics"],
            has_storage=meta["has_storage"],
        )

    async def health_check(self) -> DeviceHealth:
        h = mock_health("onvif", self.host)
        return DeviceHealth(**h)

    async def snapshot(self) -> bytes | None:
        return b"\xff\xd8" + b"ONVIF JPEG" + b"\xff\xd9"

    def build_rtsp_url(self) -> str | None:
        if not self.host:
            return None
        port = self.port or 554
        return f"rtsp://{self.host}:{port}/onvif1"


class RtspAdapter(OfflineAdapterMixin, CameraAdapter):
    """A bare RTSP endpoint with no management API (e.g. an edge recorder)."""

    vendor = Vendor.RTSP

    def __init__(self, rtsp_url: str | None = None, **opts: Any) -> None:
        super().__init__(**opts)
        self.custom_rtsp = rtsp_url

    async def get_metadata(self) -> dict[str, Any]:
        base = mock_device("rtsp", self.host)
        base["rtsp_url"] = self.build_rtsp_url()
        return base

    async def get_capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            protocols=[StreamProtocol.RTSP],
            max_streams=1,
            supports_ptz=False,
            supports_analytics=False,
            has_storage=False,
        )

    async def health_check(self) -> DeviceHealth:
        h = mock_health("rtsp", self.host)
        return DeviceHealth(**h)

    async def snapshot(self) -> bytes | None:
        return b"\xff\xd8" + b"RTSP JPEG" + b"\xff\xd9"

    def build_rtsp_url(self) -> str | None:
        return self.custom_rtsp
