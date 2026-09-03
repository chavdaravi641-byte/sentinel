"""ONVIF device discovery.

Implements WS-Discovery (SOAP-over-UDP multicast probe) for ONVIF Profile-S
network video transmitters, plus an optional static probe list for devices that
do not answer multicast. Discovery is a *network* operation — the responses are
parsed for XAddrs (device service endpoints) and a lightweight HTTP reachability
probe narrows the list to live devices.
"""

import asyncio
import socket
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import httpx

from src.core.config import settings
from src.core.logging import log

WS_DISCOVERY_ADDR = ("239.255.255.250", 3702)
_PROBE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
 xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
 xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
 <e:Header>
  <w:MessageID>urn:uuid:{message_id}</w:MessageID>
  <w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
  <w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
 </e:Header>
 <e:Body>
  <d:Probe>
   <d:Types>dn:NetworkVideoTransmitter</d:Types>
  </d:Probe>
 </e:Body>
</e:Envelope>"""


@dataclass(frozen=True)
class OnvifDevice:
    address: str
    xaddrs: str | None
    types: str | None
    scopes: str | None
    reachable: bool = False
    message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        host = urlparse(self.xaddrs or self.address).hostname or self.address
        return {
            "address": self.address,
            "host": host,
            "xaddrs": self.xaddrs,
            "types": self.types,
            "scopes": self.scopes,
            "reachable": self.reachable,
            "message": self.message,
        }


async def _http_reachable(url: str, timeout: float = 2.0) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url.rstrip("/") + "/onvif/device_service")
            return resp.status_code < 500
    except Exception:
        return False


async def ws_discover(timeout: float | None = None) -> list[OnvifDevice]:
    """Send a WS-Discovery Probe and collect device answers on the multicast group."""
    timeout = timeout or settings.ONVIF_DISCOVERY_TIMEOUT
    loop = asyncio.get_running_loop()
    devices = await loop.run_in_executor(None, _probe_blocking, timeout)
    return list(devices.values())


def _probe_blocking(timeout: float) -> dict[str, OnvifDevice]:
    """Blocking WS-Discovery probe.

    uvicorn runs the app on uvloop, which does not implement the asyncio
    ``sock_sendto``/``sock_recvfrom`` loop methods, so the datagram exchange
    runs on a worker thread with a plain blocking socket instead.
    """
    devices: dict[str, OnvifDevice] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    sock.settimeout(0.5)
    probe = _PROBE_TEMPLATE.format(message_id=str(uuid.uuid4()))
    try:
        try:
            sock.sendto(probe.encode("utf-8"), WS_DISCOVERY_ADDR)
        except OSError:
            return devices  # no multicast route on this network - nothing to discover
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(min(0.5, remaining))
            try:
                data, addr = sock.recvfrom(65536)
            except TimeoutError:
                continue
            except OSError:
                break
            source = f"{addr[0]}:{addr[1]}"
            parsed = _parse_probe_response(data)
            if parsed:
                devices[source] = parsed
    finally:
        sock.close()

    return devices


def _parse_probe_response(data: bytes) -> OnvifDevice | None:
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    ns = {
        "d": "http://schemas.xmlsoap.org/ws/2005/04/discovery",
        "a": "http://schemas.xmlsoap.org/ws/2004/08/addressing",
    }
    xaddrs = _find_text(root, ".//d:XAddrs", ns)
    types = _find_text(root, ".//d:Types", ns)
    scopes = _find_text(root, ".//d:Scopes", ns)
    addr = _find_text(root, ".//a:Address", ns)
    if not xaddrs and not addr:
        return None
    return OnvifDevice(
        address=addr or "",
        xaddrs=xaddrs,
        types=types,
        scopes=scopes,
    )


def _find_text(root: ET.Element, path: str, ns: dict[str, str]) -> str | None:
    node = root.find(path, ns)
    if node is not None and node.text:
        return node.text.strip()
    return None


async def discover(timeout: float | None = None) -> dict[str, Any]:
    """Full discovery: multicast probe + static candidates + reachability pass."""
    start = time.perf_counter()
    devices = await ws_discover(timeout)
    candidates: list[OnvifDevice] = list(devices)

    static = [u.strip() for u in settings.ONVIF_PROBE_URLS.split(",") if u.strip()]
    for url in static:
        if not any(d.xaddrs == url for d in candidates):
            candidates.append(OnvifDevice(address=url, xaddrs=url, types=None, scopes=None))

    unique: dict[str, OnvifDevice] = {}
    for device in candidates:
        key = device.xaddrs or device.address
        unique[key] = device

    # Reachability pass (HTTP to the device service endpoint).
    enriched: list[OnvifDevice] = []
    for device in unique.values():
        target = device.xaddrs or device.address
        reachable = await _http_reachable(target) if target else False
        message = "Device service responded." if reachable else ("Discovery response only." if device.xaddrs else "Unreachable.")
        enriched.append(
            OnvifDevice(
                address=device.address,
                xaddrs=device.xaddrs,
                types=device.types,
                scopes=device.scopes,
                reachable=reachable,
                message=message,
            )
        )

    enriched.sort(key=lambda d: (not d.reachable, d.address))
    log.info("onvif.discover_complete", count=len(enriched), duration_ms=round((time.perf_counter() - start) * 1000))
    return {
        "mode": "ws-discovery",
        "devices": [d.as_dict() for d in enriched],
        "count": len(enriched),
        "reachable": sum(1 for d in enriched if d.reachable),
        "duration_ms": round((time.perf_counter() - start) * 1000),
    }


__all__ = ["OnvifDevice", "discover", "ws_discover"]