"""Camera connectivity test.

Phase 1 performs a TCP liveness + latency probe against the RTSP endpoint.
A future phase replaces this with a real RTSP handshake / stream validation.
"""

import asyncio
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

from src.models.camera import Camera, CameraStatus

DEFAULT_RTSP_PORT = 554
SUPPORTED_SCHEMES = {"rtsp", "rtsps", "rtmp", "http", "https", "hls"}


def parse_rtsp(rtsp_url: str) -> tuple[str, int] | None:
    """Extract (host, port) from an RTSP/stream URL, or None if invalid."""
    parsed = urlparse(rtsp_url)
    scheme = parsed.scheme.lower()
    if scheme not in SUPPORTED_SCHEMES:
        return None
    host = parsed.hostname
    if not host:
        return None
    port = parsed.port
    if port is None:
        port = DEFAULT_RTSP_PORT if scheme.startswith("rtsp") else (443 if scheme == "rtsps" else 80)
    return host, port


async def probe_stream(rtsp_url: str, timeout: float) -> dict:
    """Run the network probe. Returns a normalized result dict."""
    target = parse_rtsp(rtsp_url)
    if target is None:
        return {
            "ok": False,
            "reachable": False,
            "host": None,
            "port": None,
            "latency_ms": None,
            "rtt_ms": None,
            "message": "Invalid stream URL: expected rtsp/rtsps/rtmp/http(s) with a host.",
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }

    host, port = target
    start = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        rtt_ms = round((time.perf_counter() - start) * 1000, 2)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return {
            "ok": True,
            "reachable": True,
            "host": host,
            "port": port,
            "latency_ms": rtt_ms,
            "rtt_ms": rtt_ms,
            "message": f"Endpoint reachable over TCP ({host}:{port}) in {rtt_ms} ms.",
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }
    except asyncio.TimeoutError:
        return {
            "ok": False,
            "reachable": False,
            "host": host,
            "port": port,
            "latency_ms": None,
            "rtt_ms": None,
            "message": f"Connection timed out after {timeout:.0f}s to {host}:{port}.",
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }
    except OSError as exc:
        return {
            "ok": False,
            "reachable": False,
            "host": host,
            "port": port,
            "latency_ms": None,
            "rtt_ms": None,
            "message": f"Could not reach {host}:{port}: {exc.strerror or str(exc)}.",
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }


async def test_camera(camera: Camera, timeout: float) -> dict:
    """Run a probe for a camera and return the structured result."""
    result = await probe_stream(camera.rtsp_url, timeout)
    result["id"] = str(camera.id)
    result["name"] = camera.name
    return result


def apply_probe_status(camera: Camera, result: dict) -> CameraStatus:
    """Derive the persisted camera status from the latest probe."""
    return CameraStatus.ONLINE if result["reachable"] else CameraStatus.OFFLINE


__all__ = ["DEFAULT_RTSP_PORT", "probe_stream", "test_camera", "parse_rtsp", "UUID"]