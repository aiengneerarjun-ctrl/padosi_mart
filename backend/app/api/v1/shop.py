import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.discovery import ProductCard, ProductDetail, StoreCard, StoreCategory, StoreDetail, Suggestions
from app.services import discovery

# Customer ke browse routes. Login ke bina bhi chalte hain (app khulte hi dukaanein dikhni chahiye).
# Har route ko customer ki location (lat, lng) chahiye: use sirf doori/eligibility nikalne me lete hain.
router = APIRouter(prefix="/shop", tags=["shop"])

Lat = Annotated[float, Query(ge=-90, le=90, description="Customer ka latitude (3 decimal tak round karke bhejna behtar)")]
Lng = Annotated[float, Query(ge=-180, le=180)]
Limit = Annotated[int, Query(ge=1, le=50)]
Offset = Annotated[int, Query(ge=0)]
StoreType = Literal["KIRANA", "RESTAURANT"]


@router.get("/stores", response_model=list[StoreCard])
async def nearby_stores(
    lat: Lat, lng: Lng, store_type: StoreType | None = None,
    q: Annotated[str | None, Query(min_length=1, max_length=60)] = None,
    limit: Limit = 20, offset: Offset = 0, db: AsyncSession = Depends(get_db),
):
    """Paas ki OPEN dukaanein/restaurants jo customer tak deliver karti hain, sabse paas wali pehle."""
    return await discovery.nearby_stores(db, lat, lng, store_type=store_type, q=q, limit=limit, offset=offset)


@router.get("/stores/{store_id}", response_model=StoreDetail)
async def store_detail(store_id: uuid.UUID, lat: Lat, lng: Lng, db: AsyncSession = Depends(get_db)):
    """Dukaan ka page. Band ho tab bhi dikhta hai (shop_status CLOSED), par can_order false hota hai."""
    return await discovery.store_detail(db, store_id, lat, lng)


@router.get("/stores/{store_id}/categories", response_model=list[StoreCategory])
async def store_categories(store_id: uuid.UUID, lat: Lat, lng: Lng, request: Request, db: AsyncSession = Depends(get_db)):
    return await discovery.store_categories(db, store_id, lat, lng, request.state.lang)


@router.get("/products", response_model=list[ProductCard])
async def products(
    request: Request, lat: Lat, lng: Lng,
    q: Annotated[str | None, Query(min_length=1, max_length=60, description="Search text (typo chalega)")] = None,
    category_id: uuid.UUID | None = None, brand_id: uuid.UUID | None = None, store_id: uuid.UUID | None = None,
    store_type: StoreType | None = None,
    min_price: Annotated[float | None, Query(ge=0)] = None, max_price: Annotated[float | None, Query(ge=0)] = None,
    sort: discovery.Sort = "relevance", limit: Limit = 20, offset: Offset = 0, db: AsyncSession = Depends(get_db),
):
    """Search + browse. Sirf wahi products jo abhi sach me khareede ja sakte hain."""
    return await discovery.list_products(
        db, lat, lng, request.state.lang, q=q, category_id=category_id, brand_id=brand_id, store_id=store_id,
        store_type=store_type, min_price=min_price, max_price=max_price, sort=sort, limit=limit, offset=offset,
    )


@router.get("/products/{product_id}", response_model=ProductDetail)
async def product_detail(product_id: uuid.UUID, lat: Lat, lng: Lng, request: Request, db: AsyncSession = Depends(get_db)):
    return await discovery.product_detail(db, product_id, lat, lng, request.state.lang)


@router.get("/suggest", response_model=Suggestions)
async def suggest(
    q: Annotated[str, Query(min_length=2, max_length=60)], lat: Lat, lng: Lng, request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Search box ke neeche autocomplete."""
    products_, stores = await discovery.suggest(db, lat, lng, request.state.lang, q)
    return Suggestions(products=products_, stores=stores)