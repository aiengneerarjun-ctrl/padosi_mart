import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_seller, get_current_user
from app.core.database import get_db
from app.models import Seller, User
from app.models.order import StoreOrderStatus
from app.schemas.seller_order import RejectBody, SellerOrderOut, UnavailableBody
from app.services import seller_order

router = APIRouter(prefix="/seller/orders", tags=["seller-orders"])

StatusFilter = Literal["PLACED", "SELLER_ACCEPTED", "PREPARING", "READY_FOR_PICKUP", "PICKED_UP", "CANCELLED", "REJECTED"]


@router.get("", response_model=list[SellerOrderOut])
async def my_orders(
    request: Request, status: StatusFilter | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0,
    seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db),
):
    """Meri dukaanon ke orders (sabse naye pehle). status=PLACED se sirf naye orders."""
    return await seller_order.list_orders(db, seller, status, limit, offset, request.state.lang)


@router.get("/{store_order_id}", response_model=SellerOrderOut)
async def order_detail(store_order_id: uuid.UUID, request: Request, seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)):
    return await seller_order.get_order(db, seller, store_order_id, request.state.lang)


@router.post("/{store_order_id}/accept", response_model=SellerOrderOut)
async def accept(
    store_order_id: uuid.UUID, request: Request, seller: Seller = Depends(get_current_seller),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await seller_order.move(db, seller, user, store_order_id, StoreOrderStatus.SELLER_ACCEPTED, request.state.lang)


@router.post("/{store_order_id}/preparing", response_model=SellerOrderOut)
async def preparing(
    store_order_id: uuid.UUID, request: Request, seller: Seller = Depends(get_current_seller),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await seller_order.move(db, seller, user, store_order_id, StoreOrderStatus.PREPARING, request.state.lang)


@router.post("/{store_order_id}/ready", response_model=SellerOrderOut)
async def ready(
    store_order_id: uuid.UUID, request: Request, seller: Seller = Depends(get_current_seller),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Saaman pack ho gaya, delivery boy ke uthane ke liye taiyar."""
    return await seller_order.move(db, seller, user, store_order_id, StoreOrderStatus.READY_FOR_PICKUP, request.state.lang)


@router.post("/{store_order_id}/unavailable", response_model=SellerOrderOut)
async def unavailable(
    store_order_id: uuid.UUID, body: UnavailableBody, request: Request, seller: Seller = Depends(get_current_seller),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Kuch items dukaan me nahi hain: unhe hatao (karan ke saath), baaki order chalta rahega.
    Customer ko hataya gaya item, karan aur naya total dikhta hai. Ready hone se pehle tak kar sakte ho."""
    return await seller_order.mark_unavailable(db, seller, user, store_order_id, body.items, request.state.lang)


@router.post("/{store_order_id}/reject", response_model=SellerOrderOut)
async def reject(
    store_order_id: uuid.UUID, body: RejectBody, request: Request, seller: Seller = Depends(get_current_seller),
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Poora order lene se mana (accept karne se pehle). Karan likhna zaroori. Stock wapas aa jaata hai."""
    return await seller_order.reject(db, seller, user, store_order_id, body.reason, body.reason_code, request.state.lang)