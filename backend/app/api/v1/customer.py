import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import User
from app.schemas.customer import AddressCreate, AddressOut, AddressUpdate
from app.schemas.discovery import ProductCard, StoreCard
from app.services import customer, discovery

# Customer ke apne addresses aur favourites. Sab kuch login user ka hi dikhta hai (user_id token se aata hai).
router = APIRouter(prefix="/users/me", tags=["customer"])

Lat = Annotated[float, Query(ge=-90, le=90)]
Lng = Annotated[float, Query(ge=-180, le=180)]
Limit = Annotated[int, Query(ge=1, le=50)]
Offset = Annotated[int, Query(ge=0)]


# ---------- Addresses ----------


@router.get("/addresses", response_model=list[AddressOut])
async def my_addresses(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await customer.list_addresses(db, user)


@router.post("/addresses", response_model=AddressOut, status_code=201)
async def add_address(body: AddressCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await customer.create_address(db, user, body)


@router.patch("/addresses/{address_id}", response_model=AddressOut)
async def edit_address(
    address_id: uuid.UUID, body: AddressUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    return await customer.update_address(db, user, address_id, body)


@router.post("/addresses/{address_id}/default", response_model=AddressOut)
async def make_default(address_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await customer.set_default_address(db, user, address_id)


@router.delete("/addresses/{address_id}", status_code=204)
async def remove_address(address_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await customer.delete_address(db, user, address_id)
    return Response(status_code=204)


# ---------- Favourites ----------


@router.get("/favourites/stores", response_model=list[StoreCard])
async def favourite_stores(
    lat: Lat, lng: Lng, limit: Limit = 20, offset: Offset = 0,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Pasandida dukaanein. Jo abhi band/door hain wo yahan nahi dikhtin (hat'ti nahi, wapas aane par dikhengi)."""
    return await discovery.nearby_stores(db, lat, lng, store_type=None, q=None, limit=limit, offset=offset, favourite_of=user.id)


@router.put("/favourites/stores/{store_id}", status_code=204)
async def add_favourite_store(store_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await customer.add_favourite_store(db, user, store_id)
    return Response(status_code=204)


@router.delete("/favourites/stores/{store_id}", status_code=204)
async def remove_favourite_store(store_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await customer.remove_favourite_store(db, user, store_id)
    return Response(status_code=204)


@router.get("/favourites/products", response_model=list[ProductCard])
async def favourite_products(
    request: Request, lat: Lat, lng: Lng, limit: Limit = 20, offset: Offset = 0,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    return await discovery.list_products(
        db, lat, lng, request.state.lang, q=None, category_id=None, brand_id=None, store_id=None, store_type=None,
        min_price=None, max_price=None, sort="distance", limit=limit, offset=offset, favourite_of=user.id,
    )


@router.put("/favourites/products/{product_id}", status_code=204)
async def add_favourite_product(product_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await customer.add_favourite_product(db, user, product_id)
    return Response(status_code=204)


@router.delete("/favourites/products/{product_id}", status_code=204)
async def remove_favourite_product(product_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await customer.remove_favourite_product(db, user, product_id)
    return Response(status_code=204)