"""Shared FastAPI dependencies: auth, role guard, request context."""

import ipaddress
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.core.security import decode_access_token
from src.crud import user as user_crud
from src.models.user import User, UserRole
from src.services.tokens import is_access_blacklisted

bearer_scheme = HTTPBearer(auto_error=False)

DBDep = Annotated[AsyncSession, Depends(get_db)]


def _unauthorized(detail: str = "Could not validate credentials.") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    db: DBDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Resolve the authenticated user from a valid non-blacklisted access token."""
    if credentials is None:
        raise _unauthorized()
    claims = decode_access_token(credentials.credentials)
    if claims is None:
        raise _unauthorized("Access token expired or invalid.")

    jti = claims.get("jti")
    if jti and await is_access_blacklisted(str(jti)):
        raise _unauthorized("Token has been revoked.")

    try:
        user_id = UUID(str(claims.get("sub")))
    except (TypeError, ValueError):
        raise _unauthorized()

    user_obj = await user_crud.get_by_id(db, user_id)
    if user_obj is None:
        raise _unauthorized("User account no longer exists.")
    if not user_obj.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )
    return user_obj


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):
    """Factory for a dependency that restricts access to the given roles."""

    def _guard(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this operation.",
            )
        return user

    return _guard


AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
StaffUser = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR))]


def get_request_meta(request: Request) -> tuple[str | None, str | None]:
    """Extract user-agent and client IP for session auditing."""
    user_agent = request.headers.get("user-agent")
    peer = request.client.host if request.client else None
    ip = peer
    forwarded_headers = request.headers.getlist("x-forwarded-for")
    if peer and forwarded_headers:
        if len(forwarded_headers) != 1:
            return user_agent, ip
        try:
            peer_address = ipaddress.ip_address(peer)
        except ValueError:
            peer_address = None
        if peer_address and any(
            peer_address in network for network in settings.trusted_proxy_networks
        ):
            forwarded = [
                value.strip()
                for value in forwarded_headers[0].split(",")
                if value.strip()
            ]
            try:
                forwarded_addresses = [ipaddress.ip_address(value) for value in forwarded]
            except ValueError:
                return user_agent, ip
            for forwarded_address in reversed(forwarded_addresses):
                try:
                    is_trusted = any(
                    forwarded_address in network
                    for network in settings.trusted_proxy_networks
                    )
                except TypeError:
                    return user_agent, ip
                if not is_trusted:
                    ip = str(forwarded_address)
                    break
    return user_agent, ip