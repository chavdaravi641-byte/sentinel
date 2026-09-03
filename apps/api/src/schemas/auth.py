"""Authentication request/response schemas."""

from pydantic import BaseModel, EmailStr, Field

from src.schemas.user import UserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(
        default=None,
        description="Optional; falls back to the httpOnly cookie.",
    )


class TokenPair(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead