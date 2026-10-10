"""Customer ko kya dikhega: sirf eligible store/product.

Eligible product = admin-approved (ACTIVE) + seller ACTIVE + dukaan OPEN + stock > 0
                   + category active + customer dukaan ke delivery radius ke andar.
"""
import math
import uuid
from typing import Literal

from sqlalchemy import Float, case, cast, exists, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.core.errors import api_error
from app.core.i18n import localized
from app.models import FavouriteProduct, FavouriteStore, Seller, Store
from app.models.catalog import Brand, Category, Inventory, Product, ProductStatus
from app.models.seller import SellerStatus, ShopStatus
from app.schemas.discovery import ProductCard, ProductDetail, StoreBrief, StoreCard, StoreCategory, StoreDetail
from app.schemas.product import image_out

EARTH_RADIUS_KM = 6371.0
PREP_MINUTES = {"KIRANA": 8, "RESTAURANT": 20}  # dukaan taiyaari ka andaaza
MINUTES_PER_KM = 4  # ~15 km/h shehar ki delivery
LOW_STOCK_NOTICE = 5  # itne ya kam bache to "only_left" dikhao

Sort = Literal["relevance", "price_asc", "price_desc", "distance", "newest"]


def estimate_eta(store_type: str, distance_km: float) -> int:
    return PREP_MINUTES.get(store_type, 10) + math.ceil(distance_km * MINUTES_PER_KM)


def distance_km_expr(lat: float, lng: float):
    """Haversine formula SQL me: customer (lat,lng) se dukaan ki doori km me."""
    s_lat = cast(Store.latitude, Float)
    s_lng = cast(Store.longitude, Float)
    c_lat = literal(lat, type_=Float)
    c_lng = literal(lng, type_=Float)
    a = func.power(func.sin(func.radians(s_lat - c_lat) / 2), 2) + func.cos(func.radians(c_lat)) * func.cos(
        func.radians(s_lat)
    ) * func.power(func.sin(func.radians(s_lng - c_lng) / 2), 2)
    return 2 * EARTH_RADIUS_KM * func.asin(func.sqrt(func.least(1.0, a)))


def _brief(store: Store) -> StoreBrief:
    return StoreBrief(id=store.id, name=store.name, store_type=store.store_type, cuisine=store.cuisine)


def _store_card(store: Store, distance: float) -> dict:
    d = round(float(distance), 1)
    return dict(
        id=store.id, name=store.name, store_type=store.store_type, cuisine=store.cuisine,
        description=store.description, distance_km=d, eta_minutes=estimate_eta(store.store_type, d),
        min_order_amount=float(store.min_order_amount),
    )


def _has_sellable_product():
    return exists().where(
        Product.store_id == Store.id, Product.status == ProductStatus.ACTIVE, Product.inventory.has(Inventory.quantity > 0)
    )


# ---------------- Stores ----------------


async def nearby_stores(
        db: AsyncSession, lat: float, lng: float, *, store_type: str | None, q: str | None, limit: int, offset: int,
    favourite_of: uuid.UUID | None = None,
) -> list[StoreCard]:
    dist = distance_km_expr(lat, lng)
    query = (
        select(Store, dist.label("distance_km"))
        .join(Seller, Seller.id == Store.seller_id)
        .where(
            Store.shop_status == ShopStatus.OPEN,
            Seller.status == SellerStatus.ACTIVE,
            dist <= cast(Store.delivery_radius_km, Float),
            _has_sellable_product(),
        )
    )
    if store_type:
        query = query.where(Store.store_type == store_type)
    if favourite_of:  # sirf is customer ki pasandida dukaanein
        query = query.where(Store.id.in_(select(FavouriteStore.store_id).where(FavouriteStore.user_id == favourite_of)))
    if q:
        query = query.where(
            or_(Store.name.icontains(q, autoescape=True), Store.cuisine.icontains(q, autoescape=True),
                func.word_similarity(q, Store.name) >= 0.45)
        )
    rows = (await db.execute(query.order_by(dist, Store.id).limit(limit).offset(offset))).all()
    return [StoreCard(**_store_card(store, d)) for store, d in rows]


async def store_detail(db: AsyncSession, store_id: uuid.UUID, lat: float, lng: float) -> StoreDetail:
    dist = distance_km_expr(lat, lng)
    row = (
        await db.execute(
            select(Store, Seller.status, dist.label("distance_km"))
            .join(Seller, Seller.id == Store.seller_id)
            .where(Store.id == store_id)
        )
    ).first()
    # Active seller ki hi dukaan dikhti hai; baaki ke liye 404 (pending/suspended seller ki dukaan chhupi rehti hai)
    if row is None or row[1] != SellerStatus.ACTIVE:
        raise api_error(404, "STORE_NOT_FOUND", "Dukaan nahi mili.")
    store, _, d = row
    deliverable = float(d) <= float(store.delivery_radius_km)
    return StoreDetail(
        **_store_card(store, d),
        address=store.address,
        shop_status=store.shop_status,
        deliverable=deliverable,
        can_order=deliverable and store.shop_status == ShopStatus.OPEN,
    )


# ---------------- Products ----------------


def _eligible_products(lat: float, lng: float):
    dist = distance_km_expr(lat, lng)
    query = (
        select(Product, Store, Brand.name.label("brand_name"), dist.label("distance_km"))
        .join(Store, Store.id == Product.store_id)
        .join(Seller, Seller.id == Store.seller_id)
        .join(Product.inventory)
        .join(Category, Category.id == Product.category_id)
        .outerjoin(Brand, Brand.id == Product.brand_id)
        .options(contains_eager(Product.inventory))
        .where(
            Product.status == ProductStatus.ACTIVE,
            Inventory.quantity > 0,
            Store.shop_status == ShopStatus.OPEN,
            Seller.status == SellerStatus.ACTIVE,
            Category.is_active.is_(True),
            dist <= cast(Store.delivery_radius_km, Float),
        )
    )
    return query, dist


def _match_condition(q: str):
    """Naam (English/Hindi/Bhojpuri) ya brand me text milta ho, ya thoda galat spelling (typo) ho."""
    return or_(
        Product.name.icontains(q, autoescape=True),
        Product.name_hi.icontains(q, autoescape=True),
        Product.name_bho.icontains(q, autoescape=True),
        Brand.name.icontains(q, autoescape=True),
        func.word_similarity(q, Product.name) >= 0.45,
        func.similarity(Product.name, q) >= 0.3,
    )


def _relevance(q: str):
    sim = func.greatest(
        func.word_similarity(q, Product.name),
        func.coalesce(func.word_similarity(q, Product.name_hi), 0.0),
        func.coalesce(func.word_similarity(q, Product.name_bho), 0.0),
        func.coalesce(func.word_similarity(q, Brand.name), 0.0) * 0.8,
    )
    prefix = case((Product.name.istartswith(q, autoescape=True), 3.0), (Product.name.icontains(q, autoescape=True), 2.0), else_=0.0)
    return prefix + sim


def _card_data(product: Product, store: Store, brand_name: str | None, distance: float, lang: str) -> dict:
    d = round(float(distance), 1)
    mrp, price = float(product.mrp), float(product.selling_price)
    primary = product.images[0] if product.images else None
    img = image_out(primary) if primary else None
    qty = product.inventory.quantity
    return dict(
        id=product.id, name=localized(product, lang), selling_unit=product.selling_unit, mrp=mrp, selling_price=price,
        discount_percent=int(round((mrp - price) / mrp * 100)) if mrp else 0,
        image_thumb_url=img.thumb_url if img else None, image_medium_url=img.medium_url if img else None,
        brand_name=brand_name, only_left=qty if qty <= LOW_STOCK_NOTICE else None,
        distance_km=d, eta_minutes=estimate_eta(store.store_type, d), store=_brief(store),
    )


async def list_products(
    db: AsyncSession, lat: float, lng: float, lang: str, *,
    q: str | None, category_id: uuid.UUID | None, brand_id: uuid.UUID | None, store_id: uuid.UUID | None,
    store_type: str | None, min_price: float | None, max_price: float | None, sort: Sort, limit: int, offset: int,
) -> list[ProductCard]:
    query, dist = _eligible_products(lat, lng)
    if store_id:
        query = query.where(Product.store_id == store_id)
    if store_type:
        query = query.where(Store.store_type == store_type)
    if favourite_of:  # sirf is customer ke pasandida products
        query = query.where(Product.id.in_(select(FavouriteProduct.product_id).where(FavouriteProduct.user_id == favourite_of)))
    if brand_id:
        query = query.where(Product.brand_id == brand_id)
    if category_id:  # main category chuni to uski sub-categories ke products bhi aayenge
        family = select(Category.id).where(or_(Category.id == category_id, Category.parent_id == category_id))
        query = query.where(Product.category_id.in_(family))
    if min_price is not None:
        query = query.where(Product.selling_price >= min_price)
    if max_price is not None:
        query = query.where(Product.selling_price <= max_price)
    if q:
        query = query.where(_match_condition(q))

    if sort == "price_asc":
        order = [Product.selling_price.asc(), dist.asc()]
    elif sort == "price_desc":
        order = [Product.selling_price.desc(), dist.asc()]
    elif sort == "newest":
        order = [Product.created_at.desc()]
    elif sort == "relevance" and q:
        order = [_relevance(q).desc(), dist.asc()]
    else:  # distance (ya bina search ke relevance): paas wali dukaan pehle
        order = [dist.asc(), Product.name.asc()]
    rows = (await db.execute(query.order_by(*order, Product.id).limit(limit).offset(offset))).all()
    return [ProductCard(**_card_data(p, s, b, d, lang)) for p, s, b, d in rows]


async def product_detail(db: AsyncSession, product_id: uuid.UUID, lat: float, lng: float, lang: str) -> ProductDetail:
    query, _ = _eligible_products(lat, lng)
    row = (await db.execute(query.where(Product.id == product_id))).first()
    if row is None:  # band dukaan / out of stock / door / approve nahi - customer ke liye ye product hai hi nahi
        raise api_error(404, "PRODUCT_NOT_FOUND", "Product nahi mila.")
    product, store, brand_name, d = row
    return ProductDetail(
        **_card_data(product, store, brand_name, d, lang),
        description=product.description, category_id=product.category_id,
        images=[image_out(i) for i in product.images],
    )


async def store_categories(db: AsyncSession, store_id: uuid.UUID, lat: float, lng: float, lang: str) -> list[StoreCategory]:
    """Dukaan ke menu ki categories (jaise Starters, Main Course) aur har me kitne products bik sakte hain."""
    query, _ = _eligible_products(lat, lng)
    sub = query.where(Product.store_id == store_id).with_only_columns(Product.category_id).subquery()
    rows = (
        await db.execute(
            select(Category, func.count().label("n"))
            .join(sub, sub.c.category_id == Category.id)
            .group_by(Category.id)
            .order_by(Category.sort_order, Category.name)
        )
    ).all()
    return [StoreCategory(id=c.id, name=localized(c, lang), product_count=n) for c, n in rows]


async def suggest(db: AsyncSession, lat: float, lng: float, lang: str, q: str) -> tuple[list[str], list[StoreBrief]]:
    """Search box ke neeche autocomplete: kuch product naam + kuch dukaan."""
    query, dist = _eligible_products(lat, lng)
    rows = (await db.execute(query.where(_match_condition(q)).order_by(_relevance(q).desc(), dist.asc(), Product.id).limit(40))).all()
    names: list[str] = []
    for product, _, _, _ in rows:
        n = localized(product, lang)
        if n not in names:
            names.append(n)
        if len(names) == 8:
            break
    stores = await nearby_stores(db, lat, lng, store_type=None, q=q, limit=3, offset=0)
    return names, [StoreBrief(id=s.id, name=s.name, store_type=s.store_type, cuisine=s.cuisine) for s in stores]