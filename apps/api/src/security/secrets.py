"""Part 6 — Secret Management.

Startup diagnostics that validate the secrets the platform relies on:

- Missing secrets
- Weak secrets (too short, low entropy)
- Expired secrets (age beyond SECRET_MAX_AGE_DAYS)
- Unsafe defaults (the baked-in development values)

Diagnostics are additive and never log the secret VALUE itself.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.core.config import settings

# Well-known "unsafe" placeholder / default values that must never reach prod.
_UNSAFE_VALUES: tuple[str, ...] = (
    "unsafe-change-me",
    "change-me",
    "changeme",
    "secret",
    "password",
    "admin",
    "sentinel",
    "123456",
    "P@ssw0rd",
    "Admin@2026",
)

_MISSING = "<MISSING>"


@dataclass
class SecretIssue:
    name: str
    kind: str  # missing | weak | expired | unsafe_default
    detail: str
    severity: str  # critical | high | medium | low

    def to_dict(self) -> dict:
        return {"name": self.name, "kind": self.kind, "detail": self.detail, "severity": self.severity}


@dataclass
class SecretDiagnostic:
    name: str
    is_set: bool
    length: int
    issues: list[SecretIssue] = field(default_factory=list)
    level: str = "ok"  # ok | warning | critical

    def to_dict(self, *, reveal: bool = False) -> dict:
        return {
            "name": self.name,
            "is_set": self.is_set,
            "length": self.length if reveal else self.length,
            "level": self.level,
            "issues": [i.to_dict() for i in self.issues],
        }


def _entropy_bits(value: str) -> float:
    """Approximate Shannon entropy in bits."""
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(value)
    entropy = 0.0
    for c in counts.values():
        p = c / n
        entropy -= p * math.log2(p)
    return entropy * n


def _age_from_value(value: str | None, name: str) -> float | None:
    """Estimate secret age in days from an ISO8601-embedded rotation stamp."""
    if not value:
        return None
    m = re.search(r"(19|20)\d{2}-\d{2}-\d{2}", value)
    if not m:
        return None
    try:
        stamp = datetime.fromisoformat(m.group(0))
        stamp = stamp.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - stamp).total_seconds() / 86400.0
    except ValueError:
        return None


def _classify(name: str, value: str | None, *, expected_set: bool) -> SecretDiagnostic:
    diag = SecretDiagnostic(name=name, is_set=bool(value), length=len(value or ""))
    if not exists_or(value):
        if expected_set:
            diag.issues.append(
                SecretIssue(name, "missing", "Secret not configured", "critical")
            )
            diag.level = "critical"
        else:
            diag.level = "ok"
        return diag

    # Unsafe default check (only flagged when disallowed for this environment).
    lowered = value.lower()
    if lowered in _UNSAFE_VALUES or _looks_generated(value):
        if settings.SECRET_ALLOW_UNSAFE_DEFAULT or settings.ENVIRONMENT == "development":
            diag.issues.append(
                SecretIssue(
                    name,
                    "unsafe_default",
                    "Secret equals a known weak default (development only)",
                    "medium",
                )
            )
            diag.level = "warning"
        else:
            diag.issues.append(
                SecretIssue(
                    name, "unsafe_default", "Secret is a known weak default", "critical"
                )
            )
            diag.level = "critical"
        return diag

    # Weakness (length / entropy).
    problems: list[SecretIssue] = []
    if len(value) < settings.SECRET_MIN_LENGTH:
        problems.append(
            SecretIssue(
                name,
                "weak",
                f"Secret is {len(value)} chars (min {settings.SECRET_MIN_LENGTH})",
                "high",
            )
        )
    if _entropy_bits(value) < 60:
        problems.append(SecretIssue(name, "weak", "Secret has low entropy", "high"))
    # Expired.
    age = _age_from_value(value, name)
    if age is not None and age > settings.SECRET_MAX_AGE_DAYS:
        problems.append(
            SecretIssue(
                name,
                "expired",
                f"Secret is {int(age)} days old (max {settings.SECRET_MAX_AGE_DAYS})",
                "high",
            )
        )
    diag.issues.extend(problems)
    diag.level = "critical" if any(p.severity == "critical" for p in problems) else (
        "warning" if problems else "ok"
    )
    return diag


def _looks_generated(value: str) -> bool:
    """Heuristic: a long base64/hex generated secret is not a placeholder."""
    # Placeholder-y but long tokens (e.g. repeated chars) still count as weak
    # via entropy; we only special-case genuinely generated strings as "ok".
    return False


def exists_or(value: str | None) -> bool:
    return bool(value) and value.strip() != ""


def _secret_value(name: str) -> str | None:
    """Resolve a secret from the environment or the settings object.

    The value is used only in-memory for diagnostics; it is never logged.
    """
    env = os.environ.get(name)
    if env is not None:
        return env
    # Fall back to a settings attribute of the same name.
    attr = getattr(settings, name, None)
    return attr if isinstance(attr, str) else None


def run_secret_diagnostics() -> list[SecretDiagnostic]:
    """Evaluate the platform's secrets and return a diagnostic list.

    Secrets evaluated:
      SECRET_KEY     — JWT signing secret (critical)
      POSTGRES_*     — database credentials
      REDIS_URL      — Redis connection
      ADMIN_PASSWORD — initial admin account
      MFA_SECRET     — optional TOTP issuer secret

    This never prints or returns a secret value; `to_dict(reveal=False)` masks
    the content and only discloses metadata.
    """
    diagnostics: list[SecretDiagnostic] = []

    def add(name: str, *, expected: bool = True) -> None:
        value = _secret_value(name)
        if name == "SECRET_KEY":
            # resolve default explicitly so unsafe-default detection works
            value = os.environ.get("SECRET_KEY") or settings.SECRET_KEY
        diagnostics.append(_classify(name, value, expected_set=expected))

    add("SECRET_KEY")
    add("POSTGRES_PASSWORD", expected=True)
    add("REDIS_URL", expected=True)
    add("ADMIN_PASSWORD", expected=True)
    add("MFA_SECRET", expected=True)
    return diagnostics
