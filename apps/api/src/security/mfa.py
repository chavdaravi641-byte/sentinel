"""Part 3 — Multi-Factor Authentication (TOTP).

Additive MFA support for core-auth users:

- TOTP secret provisioning (HMAC-SHA1 RFC 6238, 30s step).
- TOTP verification with drift window.
- One-time recovery codes and backup codes (stored as hashes).
- Trusted-device binding so a verified device can skip re-challenge.

MFA is opt-in and does not change the password-only flow until enabled.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import pyotp

from src.core.config import settings
from src.models.security import MfaRecoveryCode, TrustedDevice, UserSecurity
from src.security.core import ensure_utc, sha256_hex

_utcnow = lambda: datetime.now(timezone.utc)  # noqa: E731


def generate_totp_secret() -> str:
    return pyotp.random_base32()


async def provision_totp(db: AsyncSession, user_id) -> str:
    """Create (or keep) a TOTP secret and return it to the caller.

    The secret is stored on the user's security record so verification can
    take place after provisioning; MFA is not enabled until it is confirmed.
    """
    sec = await _get_or_create(db, user_id)
    if not sec.mfa_secret:
        sec.mfa_secret = generate_totp_secret()
        await db.commit()
    return sec.mfa_secret


def totp_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=email, issuer_name=settings.MFA_ISSUER
    )


def verify_totp(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(
        code.strip(), valid_window=settings.MFA_TOTP_WINDOW
    )


async def confirm_and_enable_mfa(
    db: AsyncSession, user_id, *, code: str
) -> bool:
    """Enable MFA after confirming a valid TOTP code."""
    sec = await _get_or_create(db, user_id)
    if not sec.mfa_secret:
        return False
    if not verify_totp(sec.mfa_secret, code):
        return False
    sec.mfa_enabled = True
    await db.commit()
    return True


async def disable_mfa(
    db: AsyncSession, user_id, *, current_password_ok: bool
) -> bool:
    if not current_password_ok:
        return False
    sec = await _get_or_create(db, user_id)
    sec.mfa_enabled = False
    sec.mfa_secret = None
    await db.execute(
        delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id)
    )
    await db.execute(
        delete(TrustedDevice).where(TrustedDevice.user_id == user_id)
    )
    await db.commit()
    return True


async def mfa_required(db: AsyncSession, user_id) -> bool:
    sec = await _get_or_create(db, user_id)
    return bool(sec.mfa_enabled)


async def generate_recovery_codes(db: AsyncSession, user_id) -> list[str]:
    """Generate and persist a fresh batch of one-time recovery codes."""
    await db.execute(
        delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id)
    )
    codes = [
        secrets.token_urlsafe(8).upper().replace("-", "").replace("_", "")
        for _ in range(settings.MFA_RECOVERY_CODE_COUNT)
    ]
    for code in codes:
        db.add(
            MfaRecoveryCode(user_id=user_id, code_hash=sha256_hex(code))
        )
    await db.commit()
    return codes


async def consume_recovery_code(db: AsyncSession, user_id, code: str) -> bool:
    """Validate and consume a single recovery code (one-time use)."""
    hashed = sha256_hex(code.strip().upper())
    stmt = (
        select(MfaRecoveryCode)
        .where(MfaRecoveryCode.user_id == user_id)
        .where(MfaRecoveryCode.code_hash == hashed)
        .where(MfaRecoveryCode.used_at.is_(None))
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return False
    await db.execute(
        update(MfaRecoveryCode)
        .where(MfaRecoveryCode.id == row.id)
        .values(used_at=_utcnow())
    )
    await db.commit()
    return True


async def backup_codes_remaining(db: AsyncSession, user_id) -> int:
    stmt = select(MfaRecoveryCode).where(
        MfaRecoveryCode.user_id == user_id, MfaRecoveryCode.used_at.is_(None)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return len(rows)


async def is_device_trusted(
    db: AsyncSession, user_id, fingerprint: str
) -> bool:
    if not fingerprint:
        return False
    stmt = select(TrustedDevice).where(
        TrustedDevice.user_id == user_id,
        TrustedDevice.fingerprint == fingerprint,
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return False
    expires = ensure_utc(row.expires_at)
    if expires is not None and expires < _utcnow():
        return False
    return True


async def trust_device(
    db: AsyncSession, user_id, fingerprint: str, label: str | None = None
) -> None:
    if not fingerprint:
        return
    existing = (
        await db.execute(
            select(TrustedDevice).where(
                TrustedDevice.user_id == user_id,
                TrustedDevice.fingerprint == fingerprint,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            TrustedDevice(
                user_id=user_id,
                fingerprint=fingerprint,
                label=label,
                expires_at=_utcnow()
                + timedelta(days=settings.MFA_TRUSTED_DEVICE_TTL_DAYS),
            )
        )
        await db.commit()


async def revoke_trusted_device(
    db: AsyncSession, user_id, fingerprint: str
) -> bool:
    result = await db.execute(
        delete(TrustedDevice).where(
            TrustedDevice.user_id == user_id,
            TrustedDevice.fingerprint == fingerprint,
        )
    )
    await db.commit()
    return (result.rowcount or 0) > 0


async def _get_or_create(db: AsyncSession, user_id) -> UserSecurity:
    sec = (
        await db.execute(
            select(UserSecurity).where(UserSecurity.user_id == user_id)
        )
    ).scalar_one_or_none()
    if sec is None:
        sec = UserSecurity(user_id=user_id)
        db.add(sec)
        await db.flush()
    return sec
