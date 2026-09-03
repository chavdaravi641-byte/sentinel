"""User data access."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password
from src.models.user import User, UserRole
from src.schemas.user import UserCreate, UserUpdate


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    user = User(
        email=data.email.lower(),
        full_name=data.full_name,
        role=data.role,
        password_hash=hash_password(data.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user: User, data: UserUpdate) -> User:
    payload = data.model_dump(exclude_unset=True, exclude_none=True)
    role = payload.pop("role", None)
    if role is not None:
        user.role = UserRole(role)
    for key, value in payload.items():
        setattr(user, key, value)
    await db.commit()
    await db.refresh(user)
    return user


async def set_last_login(db: AsyncSession, user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    # The UPDATE re-populates updated_at server-side; refresh it inside the
    # async context so response serialization never triggers a lazy load.
    await db.refresh(user)


async def update_password(db: AsyncSession, user: User, new_password: str) -> None:
    user.password_hash = hash_password(new_password)
    await db.commit()