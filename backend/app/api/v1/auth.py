from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import api_error
from app.core.security import hash_token
from app.models import RefreshToken, User
from app.schemas.auth import OtpRequest, OtpVerify, RefreshRequest, TokenPair
from app.services import auth as auth_service
from app.services import otp as otp_service
from app.core.i18n import t

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/request")
async def request_otp(body: OtpRequest, request: Request):
    await otp_service.request_otp(body.phone)
    return {"message": t("OTP_SENT", request)}

@router.post("/otp/verify", response_model=TokenPair)
async def verify_otp(body: OtpVerify, request: Request, db: AsyncSession = Depends(get_db)):
    await otp_service.verify_otp(body.phone, body.otp)
    user = await auth_service.get_or_create_user(db, body.phone)
    if not user.is_active:
        raise api_error(403, "ACCOUNT_DISABLED", "Ye account active nahi hai.")
    return await auth_service.issue_tokens(db, user, request.headers.get("user-agent"))


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    token = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(body.refresh_token)))
    now = datetime.now(timezone.utc)
    if token is None or token.expires_at < now:
        raise api_error(401, "INVALID_REFRESH_TOKEN", "Dobara login karo.")
    if token.revoked_at is not None:
        await auth_service.revoke_all_tokens(db, token.user_id)
        raise api_error(401, "INVALID_REFRESH_TOKEN", "Dobara login karo.")
    user = await db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise api_error(401, "ACCOUNT_DISABLED", "Ye account active nahi hai.")
    token.revoked_at = now
    return await auth_service.issue_tokens(db, user, request.headers.get("user-agent"))


@router.post("/logout")
async def logout(body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    token = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(body.refresh_token)))
    if token and token.revoked_at is None:
        token.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    return {"message": t("LOGGED_OUT", request)}