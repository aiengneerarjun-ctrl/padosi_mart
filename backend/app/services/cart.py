"""Cart: ek cart me alag-alag dukaanein, par sab ek-doosre se MAX_STORE_GAP_KM ke andar.

Kyun: ek delivery partner ek trip me saari dukaanon se saaman utha sake.
Cart me price save nahi hoti; dikhate waqt hamesha product ki abhi ki price aur stock lagta hai.
"""
import math
import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.core.i18n import localized
from app.models import Cart, CartItem, Product, Seller, Store, User
from app.models.cart import MAX_CART_ITEMS, MAX_STORE_GAP_KM
from app.models.catalog import Category, ProductStatus
from app.models.seller import SellerStatus, ShopStatus
from app.schemas.cart import CartItemOut, CartOut, CartStoreGroup
from app.schemas.product import image_out
from app.services import discovery

EARTH_RADIUS_KM = 6371.0


def km_between(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Do jagah ke beech ki doori km me (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, a)))


async def _lock_user(db: AsyncSession, user: User) -> None:
    # Ek hi customer ke do request ek saath aaye to limit/rules na tutein: user row par lock
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())


async def _get_or_create_cart(db: AsyncSession, user: User) -> Cart:
    await db.execute(pg_insert(Cart).values(id=uuid.uuid4(), user_id=user.id).on_conflict_do_nothing(index_elements=["user_id"]))
    return await db.scalar(select(Cart).where(Cart.user_id == user.id))


async def _check_store_gap(db: AsyncSession, cart: Cart, new_store: Store) -> None:
    """Naya store cart ke har purane store se MAX_STORE_GAP_KM ke andar hona chahiye."""
    others = (
        await db.scalars(
            select(Store).where(Store.id.in_(select(CartItem.store_id).where(CartItem.cart_id == cart.id)), Store.id != new_store.id)
        )
    ).all()
    for s in others:
        gap = km_between(float(new_store.latitude), float(new_store.longitude), float(s.latitude), float(s.longitude))
        if gap > MAX_STORE_GAP_KM:
            raise api_error(
                409, "CART_STORE_TOO_FAR",
                "Ye dukaan aapke cart ki dukaanon se door hai. Aapko do alag order karne padenge aur do delivery charge lagenge.",
            )


async def set_item(db: AsyncSession, user: User, product_id: uuid.UUID, quantity: int, lat: float, lng: float, lang: str) -> CartOut:
    await _lock_user(db, user)
    # Sirf wahi product jo customer ko abhi sach me mil sakta hai (approved, OPEN shop, stock, delivery radius)
    query, _ = discovery._eligible_products(lat, lng)
    row = (await db.execute(query.where(Product.id == product_id))).first()
    if row is None:
        raise api_error(404, "PRODUCT_NOT_FOUND", "Product nahi mila.")
    product, store, _brand, _dist = row
    if quantity > product.inventory.quantity:
        raise api_error(409, "CART_STOCK_LOW", "Itna stock available nahi hai.")

    cart = await _get_or_create_cart(db, user)
    item = await db.scalar(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id))
    if item is None:
        count = await db.scalar(select(func.count()).select_from(CartItem).where(CartItem.cart_id == cart.id))
        if count >= MAX_CART_ITEMS:
            raise api_error(409, "CART_FULL", "Cart me aur items nahi aa sakte.")
        await _check_store_gap(db, cart, store)
        db.add(CartItem(cart_id=cart.id, product_id=product_id, store_id=store.id, quantity=quantity))
    else:
        item.quantity = quantity
    await db.commit()
    return await build_cart(db, user, lat, lng, lang)


async def remove_item(db: AsyncSession, user: User, product_id: uuid.UUID, lat: float, lng: float, lang: str) -> CartOut:
    await _lock_user(db, user)
    cart = await db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is not None:
        item = await db.scalar(select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product_id))
        if item is not None:  # item nahi hai to bhi theek (dobara delete error nahi deta)
            await db.delete(item)
            await db.commit()
    return await build_cart(db, user, lat, lng, lang)


async def clear_cart(db: AsyncSession, user: User) -> None:
    await _lock_user(db, user)
    cart = await db.scalar(select(Cart).where(Cart.user_id == user.id))
    if cart is not None:
        await db.execute(CartItem.__table__.delete().where(CartItem.cart_id == cart.id))
        await db.commit()


def _problem(product: Product, store: Store, seller_status: str, category_active: bool, distance: float, qty: int) -> str | None:
    """Item customer ke liye abhi kyun nahi chal sakta (None = sab theek)."""
    if product.status not in (ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK) or not category_active:
        return "PRODUCT_INACTIVE"
    if seller_status != SellerStatus.ACTIVE:
        return "SELLER_INACTIVE"
    if store.shop_status != ShopStatus.OPEN:
        return "STORE_CLOSED"
    if distance > float(store.delivery_radius_km):
        return "NOT_DELIVERABLE"
    stock = product.inventory.quantity if product.inventory else 0
    if stock <= 0:
        return "OUT_OF_STOCK"
    if qty > stock:
        return "LOW_STOCK"
    return None


async def build_cart(db: AsyncSession, user: User, lat: float, lng: float, lang: str) -> CartOut:
    dist = discovery.distance_km_expr(lat, lng)
    rows = (
        await db.execute(
            select(CartItem, Product, Store, Seller.status, Category.is_active, dist.label("distance_km"))
            .join(Cart, Cart.id == CartItem.cart_id)
            .join(Product, Product.id == CartItem.product_id)
            .join(Store, Store.id == CartItem.store_id)
            .join(Seller, Seller.id == Store.seller_id)
            .join(Category, Category.id == Product.category_id)
            .where(Cart.user_id == user.id)
            .order_by(dist, Store.id, CartItem.created_at)
        )
    ).all()

    groups: dict[uuid.UUID, dict] = {}
    for item, product, store, seller_status, cat_active, d in rows:
        g = groups.setdefault(store.id, dict(store=store, distance=round(float(d), 1), items=[], subtotal=Decimal("0")))
        problem = _problem(product, store, seller_status, cat_active, float(d), item.quantity)
        available = problem is None
        line = product.selling_price * item.quantity
        if available:
            g["subtotal"] += line
        img = image_out(product.images[0]) if product.images else None
        g["items"].append(
            CartItemOut(
                product_id=product.id, name=localized(product, lang), selling_unit=product.selling_unit,
                mrp=float(product.mrp), selling_price=float(product.selling_price), quantity=item.quantity,
                line_total=float(line), image_thumb_url=img.thumb_url if img else None, available=available,
                unavailable_reason=problem, stock_left=product.inventory.quantity if product.inventory else 0,
            )
        )

    out_groups, total, count, problems = [], Decimal("0"), 0, False
    for g in groups.values():
        s = g["store"]
        total += g["subtotal"]
        count += sum(i.quantity for i in g["items"] if i.available)
        problems = problems or any(not i.available for i in g["items"])
        out_groups.append(
            CartStoreGroup(
                store_id=s.id, store_name=s.name, store_type=s.store_type, store_address=s.address,
                distance_km=g["distance"], items=g["items"], subtotal=float(g["subtotal"]),
        
            )
        )
    return CartOut(
        stores=out_groups, item_count=count, subtotal=float(total), max_store_gap_km=MAX_STORE_GAP_KM, has_problems=problems
    )