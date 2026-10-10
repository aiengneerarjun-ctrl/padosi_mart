import uuid

from fastapi import Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import Role, Seller, Store, User
from app.models.seller import SellerStatus, SellerType, ShopStatus
from app.schemas.seller import SellerApply
from app.services.audit import write_audit


async def apply(db: AsyncSession, user: User, body: SellerApply) -> Seller:
    seller = await db.scalar(select(Seller).where(Seller.user_id == user.id))
    if seller and seller.status != SellerStatus.REJECTED:
        raise api_error(409, "SELLER_EXISTS", "Aapki seller application pehle se maujood hai.")
    if seller is None:
        seller = Seller(user_id=user.id)
        db.add(seller)
    # Reject hone ke baad dobara apply kar sakte hain (wahi row dobara PENDING hoti hai)
    seller.seller_type = body.seller_type.value
    seller.business_name = body.business_name.strip()
    seller.owner_name = body.owner_name.strip()
    seller.status = SellerStatus.PENDING
    seller.status_reason = None
    await db.commit()
    await db.refresh(seller)
    return seller


async def _get_seller(db: AsyncSession, seller_id: uuid.UUID) -> Seller:
    seller = await db.get(Seller, seller_id)
    if seller is None:
        raise api_error(404, "SELLER_NOT_FOUND", "Seller nahi mila.")
    return seller


async def _transition(
    db: AsyncSession,
    admin: User,
    request: Request,
    seller_id: uuid.UUID,
    *,
    allowed_from: set[str],
    to: SellerStatus,
    action: str,
    reason: str | None,
) -> Seller:
    seller = await _get_seller(db, seller_id)
    if seller.status not in allowed_from:
        raise api_error(409, "INVALID_STATE", f"Seller abhi {seller.status} hai, ye kaam ab nahi ho sakta.")
    old = {"status": str(seller.status), "status_reason": seller.status_reason}
    seller.status = to
    seller.status_reason = reason
    write_audit(
        db,
        actor=admin,
        action=action,
        target_type="seller",
        target_id=seller.id,
        old=old,
        new={"status": str(to), "status_reason": reason},
        reason=reason,
        request=request,
    )
    return seller


async def approve(db: AsyncSession, admin: User, request: Request, seller_id: uuid.UUID) -> Seller:
    seller = await _transition(
        db, admin, request, seller_id,
        allowed_from={SellerStatus.PENDING}, to=SellerStatus.ACTIVE, action="seller.approve", reason=None,
    )
    # Approve hone par user ko SELLER ya RESTAURANT role milta hai
    role_name = "RESTAURANT" if seller.seller_type == SellerType.RESTAURANT else "SELLER"
    role = await db.scalar(select(Role).where(Role.name == role_name))
    user = await db.get(User, seller.user_id)
    if role not in user.roles:
        user.roles.append(role)
    await db.commit()
    return seller


async def reject(db: AsyncSession, admin: User, request: Request, seller_id: uuid.UUID, reason: str) -> Seller:
    seller = await _transition(
        db, admin, request, seller_id,
        allowed_from={SellerStatus.PENDING}, to=SellerStatus.REJECTED, action="seller.reject", reason=reason,
    )
    await db.commit()
    return seller


async def suspend(db: AsyncSession, admin: User, request: Request, seller_id: uuid.UUID, reason: str) -> Seller:
    seller = await _transition(
        db, admin, request, seller_id,
        allowed_from={SellerStatus.ACTIVE}, to=SellerStatus.SUSPENDED, action="seller.suspend", reason=reason,
    )
    # Suspend hote hi seller ki saari dukaanein band (products delete nahi hote, sirf unavailable)
    await db.execute(update(Store).where(Store.seller_id == seller.id).values(shop_status=ShopStatus.CLOSED))
    await db.commit()
    return seller


async def reactivate(db: AsyncSession, admin: User, request: Request, seller_id: uuid.UUID) -> Seller:
    seller = await _transition(
        db, admin, request, seller_id,
        allowed_from={SellerStatus.SUSPENDED}, to=SellerStatus.ACTIVE, action="seller.reactivate", reason=None,
    )
    # Dukaanein band hi rehti hain; seller ko khud manually OPEN karni hongi (locked rule: manual shop status)
    await db.commit()
    return seller
