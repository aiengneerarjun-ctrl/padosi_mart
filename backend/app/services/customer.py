"""Customer ke addresses aur favourites."""
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import CustomerAddress, FavouriteProduct, FavouriteStore, Product, Seller, Store, User
from app.models.catalog import ProductStatus
from app.models.customer import MAX_ADDRESSES
from app.models.seller import SellerStatus
from app.schemas.customer import AddressCreate, AddressUpdate

# ---------------- Addresses ----------------


async def _get_own(db: AsyncSession, user: User, address_id: uuid.UUID) -> CustomerAddress:
    addr = await db.get(CustomerAddress, address_id)
    # Doosre ka (ya delete hua) address: 404, 403 nahi
    if addr is None or addr.user_id != user.id or not addr.is_active:
        raise api_error(404, "ADDRESS_NOT_FOUND", "Address nahi mila.")
    return addr


async def list_addresses(db: AsyncSession, user: User) -> list[CustomerAddress]:
    q = (
        select(CustomerAddress)
        .where(CustomerAddress.user_id == user.id, CustomerAddress.is_active.is_(True))
        .order_by(CustomerAddress.is_default.desc(), CustomerAddress.created_at.desc())
    )
    return list((await db.scalars(q)).all())


async def _unset_default(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(CustomerAddress)
        .where(CustomerAddress.user_id == user_id, CustomerAddress.is_default.is_(True), CustomerAddress.is_active.is_(True))
        .values(is_default=False)
    )


async def create_address(db: AsyncSession, user: User, body: AddressCreate) -> CustomerAddress:
    # Ek hi customer ke do request ek saath aaye to limit na tute: user row par lock
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    count = await db.scalar(
        select(func.count()).select_from(CustomerAddress).where(CustomerAddress.user_id == user.id, CustomerAddress.is_active.is_(True))
    )
    if count >= MAX_ADDRESSES:
        raise api_error(409, "ADDRESS_LIMIT_REACHED", "Aur address nahi jod sakte, pehle koi purana hatao.")
    make_default = body.make_default or count == 0  # pehla address apne aap default
    data = body.model_dump(exclude={"make_default"})
    if make_default:
        await _unset_default(db, user.id)
    addr = CustomerAddress(user_id=user.id, is_default=make_default, **data)
    db.add(addr)
    await db.commit()
    await db.refresh(addr)
    return addr


async def update_address(db: AsyncSession, user: User, address_id: uuid.UUID, body: AddressUpdate) -> CustomerAddress:
    addr = await _get_own(db, user, address_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None and field != "landmark":
            continue  # zaroori field ko khali nahi kar sakte
        setattr(addr, field, value)
    await db.commit()
    await db.refresh(addr)
    return addr


async def set_default_address(db: AsyncSession, user: User, address_id: uuid.UUID) -> CustomerAddress:
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    addr = await _get_own(db, user, address_id)
    if not addr.is_default:
        await _unset_default(db, user.id)
        addr.is_default = True
    await db.commit()
    await db.refresh(addr)
    return addr


async def delete_address(db: AsyncSession, user: User, address_id: uuid.UUID) -> None:
    await db.execute(select(User.id).where(User.id == user.id).with_for_update())
    addr = await _get_own(db, user, address_id)
    was_default = addr.is_default
    addr.is_active = False  # soft delete
    addr.is_default = False
    await db.flush()
    if was_default:  # sabse naya bacha hua address default ban jaata hai
        newest = await db.scalar(
            select(CustomerAddress)
            .where(CustomerAddress.user_id == user.id, CustomerAddress.is_active.is_(True))
            .order_by(CustomerAddress.created_at.desc())
            .limit(1)
        )
        if newest:
            newest.is_default = True
    await db.commit()


# ---------------- Favourites ----------------


async def add_favourite_store(db: AsyncSession, user: User, store_id: uuid.UUID) -> None:
    ok = await db.scalar(
        select(Store.id).join(Seller, Seller.id == Store.seller_id).where(Store.id == store_id, Seller.status == SellerStatus.ACTIVE)
    )
    if ok is None:
        raise api_error(404, "STORE_NOT_FOUND", "Dukaan nahi mili.")
    # Dobara add karna error nahi: chup-chaap ignore (idempotent)
    await db.execute(pg_insert(FavouriteStore).values(user_id=user.id, store_id=store_id).on_conflict_do_nothing())
    await db.commit()


async def remove_favourite_store(db: AsyncSession, user: User, store_id: uuid.UUID) -> None:
    await db.execute(FavouriteStore.__table__.delete().where(FavouriteStore.user_id == user.id, FavouriteStore.store_id == store_id))
    await db.commit()


async def add_favourite_product(db: AsyncSession, user: User, product_id: uuid.UUID) -> None:
    ok = await db.scalar(
        select(Product.id)
        .join(Store, Store.id == Product.store_id)
        .join(Seller, Seller.id == Store.seller_id)
        .where(
            Product.id == product_id,
            Product.status.in_([ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK]),  # approve ho chuka product
            Seller.status == SellerStatus.ACTIVE,
        )
    )
    if ok is None:
        raise api_error(404, "PRODUCT_NOT_FOUND", "Product nahi mila.")
    await db.execute(pg_insert(FavouriteProduct).values(user_id=user.id, product_id=product_id).on_conflict_do_nothing())
    await db.commit()


async def remove_favourite_product(db: AsyncSession, user: User, product_id: uuid.UUID) -> None:
    await db.execute(
        FavouriteProduct.__table__.delete().where(FavouriteProduct.user_id == user.id, FavouriteProduct.product_id == product_id)
    )
    await db.commit()