"""Vendor adapters: Hikvision, Dahua, Axis, Bosch, Hanwha, CP Plus.

Each implements :class:`~src.federation.adapters.base.CameraAdapter` using the
vendor's documented ISAPI/CGI surface. Because Phase 6 has no live lab hardware,
they delegate runtime calls to the deterministic mock provider; the HTTP(S)
client paths and RTSP URL builders reflect each vendor's real conventions so a
live swap-in only requires enabling the network call.
"""

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


class HttpCameraAdapter(OfflineAdapterMixin, CameraAdapter):
    """Base for HTTP(S)/ISAPI/CGI based devices."""

    api_path: str = "/"

    async def get_metadata(self) -> dict[str, Any]:
        base = mock_device(self.vendor.value, self.host)
        base["host"] = self.host
        base["port"] = self.port or self.default_port()
        base["api"] = f"{self.scheme()}://{self.host or '[host]'}{self.api_path}"
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
        h = mock_health(self.vendor.value, self.host)
        return DeviceHealth(**h)

    async def snapshot(self) -> bytes | None:
        # Simulated JPEG bytes; a live adapter would GET the mjpeg/snapshot URI.
        return b"\xff\xd8" + b"SIMULATED JPEG" + b"\xff\xd9"

    def default_port(self) -> int | None:
        return None

    def scheme(self) -> str:
        return "http"


class HikvisionAdapter(HttpCameraAdapter):
    vendor = Vendor.HIKVISION
    api_path = "/ISAPI/System/deviceInfo"

    def build_rtsp_url(self) -> str | None:
        if not self.host:
            return None
        port = self.port or 554
        uname = self.username or ""
        pwd = self.password or ""
        creds = f"{uname}:{pwd}@" if uname else ""
        return f"rtsp://{creds}{self.host}:{port}/Streaming/Channels/101"

    def default_port(self) -> int:
        return 80


class DahuaAdapter(HttpCameraAdapter):
    vendor = Vendor.DAHUA
    api_path = "/cgi-bin/magicBox.cgi?action=getSystemInfo"

    def build_rtsp_url(self) -> str | None:
        if not self.host:
            return None
        port = self.port or 554
        uname = self.username or ""
        pwd = self.password or ""
        creds = f"{uname}:{pwd}@" if uname else ""
        return f"rtsp://{creds}{self.host}:{port}/cam/realmonitor?channel=1&subtype=0"

    def default_port(self) -> int:
        return 80


class AxisAdapter(HttpCameraAdapter):
    vendor = Vendor.AXIS
    api_path = "/axis-cgi/param.cgi?action=list"

    def build_rtsp_url(self) -> str | None:
        if not self.host:
            return None
        port = self.port or 554
        return f"rtsp://{self.host}:{port}/axis-media/media.amp"

    def default_port(self) -> int:
        return 80


class BoschAdapter(HttpCameraAdapter):
    vendor = Vendor.BOSCH
    api_path = "/isis/Config/System/Network/TextStream"

    def build_rtsp_url(self) -> str | None:
        if not self.host:
            return None
        port = self.port or 554
        return f"rtsp://{self.host}:{port}/rtsp_tunnel"

    def default_port(self) -> int:
        return 80


class HanwhaAdapter(HttpCameraAdapter):
    vendor = Vendor.HANWHA
    api_path = "/stw-cgi/System.cgi?msubmenu=system_conf"

    def build_rtsp_url(self) -> str | None:
        if not self.host:
            return None
        port = self.port or 554
        return f"rtsp://{self.host}:{port}/profile0"

    def default_port(self) -> int:
        return 80


class CPPlusAdapter(HttpCameraAdapter):
    vendor = Vendor.CPP_LUS
    api_path = "/cgi-bin/param.cgi?action=list"

    def build_rtsp_url(self) -> str | None:
        if not self.host:
            return None
        port = self.port or 554
        uname = self.username or ""
        pwd = self.password or ""
        creds = f"{uname}:{pwd}@" if uname else ""
        return f"rtsp://{creds}{self.host}:{port}/live/ch0"

    def default_port(self) -> int:
        return 80


ALL_VENDORS: dict[Vendor, type[HttpCameraAdapter]] = {
    Vendor.HIKVISION: HikvisionAdapter,
    Vendor.DAHUA: DahuaAdapter,
    Vendor.AXIS: AxisAdapter,
    Vendor.BOSCH: BoschAdapter,
    Vendor.HANWHA: HanwhaAdapter,
    Vendor.CPP_LUS: CPPlusAdapter,
}
