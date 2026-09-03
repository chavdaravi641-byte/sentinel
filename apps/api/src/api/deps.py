"""Shared FastAPI dependencies: auth, role guard, request context."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

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
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None
    return user_agent, ip