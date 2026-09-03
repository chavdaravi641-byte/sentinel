"""Signed URL authentication for streaming media.

Media endpoints are consumed by <video>/<img> elements (hls.js, MJPEG) which
cannot attach an Authorization header, and by the legacy outlook for embedded
displays. We issue short-lived HMAC-SHA256 tokens binding a camera and a media
kind; the same token also accepts Bearer auth for programmatic consumers.
"""

import hashlib
import hmac
import time
from dataclasses import dataclass
from uuid import UUID

from src.core.config import settings

# Media kinds that can be addressed with a signed token.
KIND_SNAPSHOT = "snapshot"
KIND_MJPEG = "mjpeg"
KIND_HLS = "hls"
KIND_WHEP = "whep"
KIND_RECORDING = "recording"
_ALLOWED_KINDS = {KIND_SNAPSHOT, KIND_MJPEG, KIND_HLS, KIND_WHEP, KIND_RECORDING}


@dataclass(frozen=True)
class MediaToken:
    exp: int
    token: str

    def query(self) -> str:
        return f"exp={self.exp}&t={self.token}"


def _sign(camera_id: UUID, kind: str, exp: int) -> str:
    message = f"{camera_id}:{kind}:{exp}".encode("utf-8")
    digest = hmac.new(settings.SECRET_KEY.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return digest


def create_media_token(camera_id: UUID, kind: str, *, ttl: int | None = None) -> MediaToken:
    if kind not in _ALLOWED_KINDS:
        raise ValueError(f"Unsupported media kind: {kind}")
    ttl = ttl if ttl is not None else settings.STREAM_AUTH_TTL_SECONDS
    exp = int(time.time()) + ttl
    return MediaToken(exp=exp, token=_sign(camera_id, kind, exp))


def verify_media_token(camera_id: UUID, kind: str, token: str | None, exp: int | None) -> bool:
    if kind not in _ALLOWED_KINDS:
        return False
    if not token or not exp:
        return False
    if exp < int(time.time()):
        return False
    expected = _sign(camera_id, kind, exp)
    return hmac.compare_digest(expected, token)


__all__ = [
    "KIND_SNAPSHOT",
    "KIND_MJPEG",
    "KIND_HLS",
    "KIND_WHEP",
    "KIND_RECORDING",
    "create_media_token",
    "verify_media_token",
    "MediaToken",
]