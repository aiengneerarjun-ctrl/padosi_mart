import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.order import OrderCancel, OrderCreate, OrderOut, OrderSummary
from app.schemas.payment import PaymentSessionOut
from app.services import order as order_service
from app.services import payment as payment_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201)
async def place_order(
    body: OrderCreate, request: Request, response: Response,
    idempotency_key: Annotated[str, Header(min_length=8, max_length=64, description="Har naye order ke liye nayi random key (UUID). Retry me wahi key.")],
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Cart ka order banao. Wahi Idempotency-Key dobara bhejne par naya order nahi banta; purana order wapas milta hai (200)."""
    order, created = await order_service.place_order(db, user, body, idempotency_key, request.state.lang)
    if not created:
        response.status_code = 200
    return order


@router.get("", response_model=list[OrderSummary])
async def my_orders(
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await order_service.list_orders(db, user, limit, offset)


@router.get("/{order_id}", response_model=OrderOut)
async def order_detail(order_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await order_service.get_order(db, user, order_id, request.state.lang)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: uuid.UUID, request: Request, body: OrderCancel | None = None,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Jab tak koi seller order accept na kare, customer cancel kar sakta hai. Stock wapas aa jaata hai."""
    return await order_service.cancel_order(db, user, order_id, body.reason if body else None, request.state.lang)
@router.post("/{order_id}/pay", response_model=PaymentSessionOut)
async def pay_order(order_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """ONLINE order ka payment shuru karo: Cashfree ka payment_session_id milta hai (app ka SDK isse payment kholta hai).
    Wahi order dobara bulane par wahi session milta hai. Payment ka samay (payment_expires_at) nikal gaya to 409 PAYMENT_EXPIRED."""
    return await payment_service.start_payment(db, user, order_id)
