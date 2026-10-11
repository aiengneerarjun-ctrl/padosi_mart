import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.cart import CartItemSet, CartOut
from app.services import cart

# Customer ka cart. Login zaroori. lat/lng = customer ki delivery location (eligibility aur doori ke liye).
router = APIRouter(prefix="/cart", tags=["cart"])

Lat = Annotated[float, Query(ge=-90, le=90)]
Lng = Annotated[float, Query(ge=-180, le=180)]


@router.get("", response_model=CartOut)
async def view_cart(request: Request, lat: Lat, lng: Lng, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Cart dukaan-wise group me. Har group = ek dukaan jahan se delivery boy ko saaman uthana hai."""
    return await cart.build_cart(db, user, lat, lng, request.state.lang)


@router.put("/items/{product_id}", response_model=CartOut)
async def set_item(
    product_id: uuid.UUID, body: CartItemSet, request: Request,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Product add karo ya uski quantity badlo (dono yahi). Dobara bhejne se quantity double nahi hoti, set hoti hai."""
    return await cart.set_item(db, user, product_id, body.quantity, body.lat, body.lng, request.state.lang)


@router.delete("/items/{product_id}", response_model=CartOut)
async def remove_item(
    product_id: uuid.UUID, request: Request, lat: Lat, lng: Lng,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await cart.remove_item(db, user, product_id, lat, lng, request.state.lang)


@router.delete("", status_code=204)
async def clear_cart(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await cart.clear_cart(db, user)
    return Response(status_code=204)