"""Camera source normalization.

Phase 2 supports the same URL classes Phase 1 validated (RTSP, RTMP, HTTP(S),
HLS) plus USB/webcam devices and, behind a feature flag, synthetic lavfi test
patterns used exclusively by the validation suite.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from src.core.config import settings
from src.models.camera import Camera

_SCHEME_RE = re.compile(r"^([a-z][a-z0-9+\-.]*)://", re.IGNORECASE)


@dataclass(frozen=True)
class CameraSource:
    kind: str  # rtsp | ip | usb | test
    input: str  # ffmpeg -i value
    scheme: str | None
    host: str | None
    port: int | None

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "input": self.input,
            "scheme": self.scheme,
            "host": self.host,
            "port": self.port,
        }


def resolve_source(camera: Camera) -> CameraSource:
    """Normalize a Camera row into a concrete ffmpeg input descriptor."""
    raw = (camera.rtsp_url or "").strip()

    # USB / webcam device (e.g. /dev/video0)
    if raw.startswith("/dev/"):
        return CameraSource(kind="usb", input=raw, scheme="device", host=None, port=None)

    # Synthetic lavfi test source (validation only)
    if settings.STREAM_ALLOW_TEST_SOURCES and raw.startswith("lavfi://"):
        pattern = raw.removeprefix("lavfi://") or "testsrc2=size=1280x720:rate=25"
        return CameraSource(kind="test", input=f"lavfi:{pattern}", scheme="test", host=None, port=None)

    match = _SCHEME_RE.match(raw)
    if not match:
        return CameraSource(kind="usb", input=raw, scheme=None, host=None, port=None)

    scheme = match.group(1).lower()
    parsed = urlparse(raw)
    host = parsed.hostname
    if scheme == "rtsp" or scheme == "rtsps":
        return CameraSource(
            kind="rtsp",
            input=raw,
            scheme=scheme,
            host=host,
            port=parsed.port or (554 if scheme == "rtsp" else 322),
        )
    if scheme in {"rtmp", "udp", "srt"}:
        return CameraSource(kind="ip", input=raw, scheme=scheme, host=host, port=parsed.port)
    if scheme in {"http", "https"} and (".m3u8" in raw.lower() or "hls" in raw.lower()):
        return CameraSource(kind="ip", input=raw, scheme="hls", host=host, port=parsed.port)
    if scheme in {"http", "https"}:
        return CameraSource(kind="ip", input=raw, scheme=scheme, host=host, port=parsed.port)
    if scheme == "hls":
        return CameraSource(kind="ip", input=raw, scheme="hls", host=host, port=parsed.port)
    return CameraSource(kind="ip", input=raw, scheme=scheme, host=host, port=parsed.port)


def is_test_source(camera: Camera) -> bool:
    raw = (camera.rtsp_url or "").strip()
    return settings.STREAM_ALLOW_TEST_SOURCES and raw.startswith("lavfi://")


__all__ = ["CameraSource", "resolve_source", "is_test_source"]