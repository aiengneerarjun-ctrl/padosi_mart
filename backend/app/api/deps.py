import uuid

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import api_error
from app.core.security import decode_access_token
from app.models import Seller, User

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise api_error(401, "NOT_AUTHENTICATED", "Login karo.")
    try:
        payload = decode_access_token(creds.credentials)
        user = await db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        raise api_error(401, "INVALID_TOKEN", "Session expire ho gayi, dobara login karo.")
    if user is None or not user.is_active:
        raise api_error(401, "ACCOUNT_DISABLED", "Ye account active nahi hai.")
    return user


def require_roles(*allowed: str):
    """Server-side permission check. SUPER_ADMIN ko hamesha poora access."""

    async def checker(user: User = Depends(get_current_user)) -> User:
        names = set(user.role_names)
        if "SUPER_ADMIN" in names or names & set(allowed):
            return user
        raise api_error(403, "FORBIDDEN", "Is kaam ki permission nahi hai.")

    return checker


# Sirf Super Admin (koi allowed role nahi, sirf SUPER_ADMIN pass hota hai)
require_super_admin = require_roles()


async def get_current_seller(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Seller:
    """Login user ki seller application/account (kisi bhi status me)."""
    seller = await db.scalar(select(Seller).where(Seller.user_id == user.id))
    if seller is None:
        raise api_error(403, "NOT_A_SELLER", "Pehle seller ke liye apply karo.")
    return seller