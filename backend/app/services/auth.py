import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, generate_refresh_token, hash_token
from app.models import RefreshToken, Role, User
from app.schemas.auth import TokenPair


async def get_or_create_user(db: AsyncSession, phone: str, language: str = "en") -> User:
    user = await db.scalar(select(User).where(User.phone == phone))
    if user:
        return user
    customer_role = await db.scalar(select(Role).where(Role.name == "CUSTOMER"))
    user = User(phone=phone, language=language, roles=[customer_role])
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        return await db.scalar(select(User).where(User.phone == phone))
    return user


async def issue_tokens(db: AsyncSession, user: User, user_agent: str | None) -> TokenPair:
    refresh = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days),
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    await db.commit()
    return TokenPair(
        access_token=create_access_token(str(user.id)),
        refresh_token=refresh,
        expires_in=settings.access_token_minutes * 60,
    )


async def revoke_all_tokens(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()
