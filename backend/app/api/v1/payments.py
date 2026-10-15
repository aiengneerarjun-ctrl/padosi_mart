from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services import payment as service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/cashfree/webhook", include_in_schema=True)
async def cashfree_webhook(
    request: Request,
    x_webhook_signature: str | None = Header(default=None),
    x_webhook_timestamp: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Cashfree yahan payment / refund ki khabar bhejta hai. Login nahi, signature se pehchan (RAW body par).
    Ye URL Cashfree dashboard me Webhooks ke andar daalna hai (aur .env ka PAYMENT_NOTIFY_URL bhi yahi)."""
    raw = await request.body()
    result = await service.handle_cashfree_webhook(db, raw, x_webhook_timestamp, x_webhook_signature)
    return {"status": result}