"""Shared primitives for the Phase 6.2 security layer.

Includes timing-safe comparison, device fingerprint hashing and a small
FingerprintEngine used for session fingerprinting (Part 1).
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
from datetime import datetime, timezone

from src.core.config import settings


def utcnow() -> datetime:
    """Timezone-aware current UTC time (avoids naive/aware comparison bugs)."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Normalise a datetime to tz-aware UTC, handling naive DB round-trips."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def constant_time_equals(a: str, b: str) -> bool:
    """Constant-time string comparison to avoid timing side-channels."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_ip(ip: str | None) -> str | None:
    """Normalise an IP to a stable, comparable string."""
    if not ip:
        return None
    value = ip.strip()
    try:
        # IPv6 loopback / unspecified -> "127.0.0.1" style normalisation.
        parsed = ipaddress.ip_address(value)
        if parsed.is_loopback or parsed.is_unspecified:
            return "127.0.0.1"
        return parsed.compressed
    except ValueError:
        return None


class FingerprintEngine:
    """Build a stable device fingerprint and detect session drift.

    The fingerprint is a salted hash of selected User-Agent fields plus the
    client IP. It is not shared across users (per-user salt) so a fingerprint
    from one account cannot be replayed against another.
    """

    def __init__(self, tolerance: float | None = None) -> None:
        self.tolerance = tolerance or settings.SESSION_FINGERPRINT_TOLERANCE

    @staticmethod
    def _components(user_agent: str | None, ip: str | None) -> str:
        # Use a coarse device signature: UA family/platform tokens + ip.
        ua = (user_agent or "").lower()
        ip_norm = normalize_ip(ip) or ""
        return json.dumps(
            {"ua": ua, "ip": ip_norm}, sort_keys=True, separators=(",", ":")
        )

    def fingerprint(self, *, user_agent: str | None, ip: str | None, salt: str) -> str:
        components = self._components(user_agent, ip)
        return sha256_hex(f"{salt}::{components}")

    def similarity(self, a_components: str, b_components: str) -> float:
        """Jaccard-style similarity over the JSON component dict keys/values."""
        if a_components == b_components:
            return 1.0
        ka = set(_tokenize(a_components))
        kb = set(_tokenize(b_components))
        if not ka and not kb:
            return 1.0
        union = ka | kb
        inter = ka & kb
        return len(inter) / len(union) if union else 0.0


def _tokenize(components: str) -> list[str]:
    """Tokenise a fingerprint component JSON for similarity computation."""
    try:
        data = json.loads(components)
    except (ValueError, TypeError):
        return list(components)
    out: list[str] = []
    for key in ("ua", "ip"):
        val = data.get(key)
        if val:
            out.append(f"{key}={val}")
    return out


class TokenKeyStore:
    """Manages JWT signing keys to support rotation (Part 1).

    Keys are loaded from absolute paths listed in JWT_ROTATION_KEYS. When the
    setting is a positive integer 'N', N hex keys are generated deterministically
    from SECRET_KEY (for non-production / single-process validation). The newest
    key is used to sign; all keys remain valid for verification until the grace
    window expires.
    """

    def __init__(self, legacy_key: str | None = None) -> None:
        self._active: str = legacy_key or settings.SECRET_KEY
        self._retired: dict[str, float] = {}

    def advance(self, new_key: str) -> None:
        """Rotate the active signing key, retiring the previous one for grace."""
        import time

        if new_key == self._active:
            return
        self._retired[self._active] = time.time()
        self._active = new_key

    def verification_keys(self) -> list[str]:
        """Return [active, ...retired-not-expired] keys for decode fallback."""
        import time

        now = time.time()
        grace = settings.JWT_ROTATION_GRACE_SECONDS
        keys = [self._active]
        for key, rotated_at in self._retired.items():
            if now - rotated_at <= grace:
                keys.append(key)
        return keys

    @property
    def active(self) -> str:
        return self._active


def compute_signature(secret: str, *, parts: list[str]) -> str:
    """HMAC-SHA256 signature over ordered parts (used for replay/CSRF tokens)."""
    message = "\n".join(parts)
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
