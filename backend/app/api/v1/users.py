from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.user import UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def _out(user: User) -> UserOut:
        return UserOut(id=user.id, phone=user.phone, name=user.name, email=user.email, roles=user.role_names, language=user.language)

@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return _out(user)


@router.patch("/me", response_model=UserOut)
async def update_me(body: UserUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.name is not None:
        user.name = body.name.strip()[:100]
    if body.email is not None:
        user.email = body.email.strip()[:255]
    if body.language is not None:
        user.language = body.language
    await db.commit()
    return _out(user)