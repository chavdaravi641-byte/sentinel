"""Password hashing and JWT primitives.

- Passwords are hashed with bcrypt directly (avoiding the deprecated passlib
  adapter for bcrypt >= 4.1).
- Access tokens are JWT HS256 with a `jti` claim used for revocation via Redis.
- Refresh tokens are opaque cryptographically random strings; only their
  SHA-256 digest is persisted so a DB leak cannot be replayed.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from src.core.config import settings


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given password."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    """Constant-time compare of a plaintext against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, str, datetime]:
    """Create a signed JWT. Returns (token, jti, expires_at)."""
    jti = str(uuid4())
    now = datetime.now(timezone.utc)
    expires = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "jti": jti,
        "type": "access",
        "iat": now,
        "exp": expires,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expires


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate an access token. Returns claims or None."""
    try:
        claims = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None
    if claims.get("type") != "access":
        return None
    return claims


def generate_refresh_token() -> str:
    """Return a new opaque refresh token (URL-safe, 64 bytes)."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """Return the SHA-256 digest used to persist/compare refresh tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def default_refresh_ttl() -> timedelta:
    return timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)