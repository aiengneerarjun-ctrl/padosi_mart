import asyncio
import uuid

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.errors import api_error
from app.models import DeliveryPartner, Role, User
from app.models.delivery import PartnerStatus
from app.services import delivery_assignment
from app.services.audit import write_audit
from app.services.delivery_rules import NEEDS_VEHICLE_NUMBER, TRANSITIONS, can_move, normalize_vehicle_number
from app.services.image_processing import ImageError, process_document_image


# ---------------- partner khud ----------------


async def _load(db: AsyncSession, partner_id: uuid.UUID, *, lock: bool = False) -> DeliveryPartner | None:
    q = select(DeliveryPartner).where(DeliveryPartner.id == partner_id).execution_options(populate_existing=True)
    if lock:
        q = q.with_for_update()
    return await db.scalar(q)


async def get_mine(db: AsyncSession, user: User) -> DeliveryPartner:
    partner = await db.scalar(select(DeliveryPartner).where(DeliveryPartner.user_id == user.id))
    if partner is None:
        raise api_error(403, "NOT_A_PARTNER", "Pehle delivery partner ke liye apply karo.")
    return partner


async def _process(data: bytes) -> bytes:
    try:  # CPU ka kaam alag thread me
        return await asyncio.to_thread(process_document_image, data)
    except ImageError as exc:
        raise api_error(exc.status, exc.code, exc.message)


async def apply(
    db: AsyncSession,
    user: User,
    *,
    full_name: str,
    vehicle_type: str,
    vehicle_number: str | None,
    id_type: str,
    id_photo: bytes,
    licence_photo: bytes | None,
) -> DeliveryPartner:
    # 1) Gaadi ka number: bike/scooter ke liye zaroori, cycle ke liye nahi
    try:
        number = normalize_vehicle_number(vehicle_number)
    except ValueError:
        raise api_error(422, "VEHICLE_NUMBER_INVALID", "Gaadi ka number sahi nahi hai.")
    if vehicle_type in NEEDS_VEHICLE_NUMBER and number is None:
        raise api_error(422, "VEHICLE_NUMBER_REQUIRED", "Gaadi ka number likhna zaroori hai.")
    if vehicle_type not in NEEDS_VEHICLE_NUMBER:
        number = None

    name = full_name.strip()
    if len(name) < 2:
        raise api_error(422, "VALIDATION_ERROR", "Naam bahut chhota hai.")

    # 2) Pehle se application hai? (REJECTED ke baad dobara apply kar sakte hain, wahi row dobara PENDING hoti hai)
    existing = await db.scalar(
        select(DeliveryPartner).where(DeliveryPartner.user_id == user.id).with_for_update().execution_options(populate_existing=True)
    )
    if existing and existing.status != PartnerStatus.REJECTED:
        raise api_error(409, "PARTNER_EXISTS", "Aapki delivery partner application pehle se maujood hai.")

    # 3) Photos check karo (bekaar file par storage me kuch nahi likhte)
    id_blob = await _process(id_photo)
    licence_blob = await _process(licence_photo) if licence_photo else None

    # 4) PRIVATE storage me rakho
    partner_id = existing.id if existing else uuid.uuid4()
    id_key = f"delivery-kyc/{partner_id}/id-{uuid.uuid4().hex}.webp"
    licence_key = f"delivery-kyc/{partner_id}/licence-{uuid.uuid4().hex}.webp" if licence_blob else None
    uploaded: list[str] = []
    try:
        await storage.put_private_object(id_key, id_blob, "image/webp")
        uploaded.append(id_key)
        if licence_blob and licence_key:
            await storage.put_private_object(licence_key, licence_blob, "image/webp")
            uploaded.append(licence_key)
    except storage.StorageError:
        await storage.delete_private_objects(uploaded)
        await db.rollback()
        raise api_error(503, "STORAGE_UNAVAILABLE", "Photo storage abhi available nahi hai, dobara try karo.")

    old_keys: list[str] = []
    if existing is None:
        partner = DeliveryPartner(id=partner_id, user_id=user.id)
        db.add(partner)
    else:
        partner = existing
        old_keys = [k for k in (existing.id_photo_key, existing.licence_photo_key) if k]
    partner.full_name = name
    partner.vehicle_type = vehicle_type
    partner.vehicle_number = number
    partner.id_type = id_type
    partner.id_photo_key = id_key
    partner.licence_photo_key = licence_key
    partner.status = PartnerStatus.PENDING
    partner.status_reason = None
    partner.is_online = False

    try:
        await db.commit()
    except IntegrityError:  # do request ek saath aayi aur dusri jeet gayi
        await db.rollback()
        await storage.delete_private_objects(uploaded)
        raise api_error(409, "PARTNER_EXISTS", "Aapki delivery partner application pehle se maujood hai.")
    except Exception:
        await db.rollback()
        await storage.delete_private_objects(uploaded)  # DB me nahi gayi to storage me bhi nahi rakhni
        raise
    await storage.delete_private_objects(old_keys)  # purani (rejected) application ki photo hatao
    return await _load(db, partner_id)


async def set_online(db: AsyncSession, user: User, online: bool) -> DeliveryPartner:
    mine = await get_mine(db, user)
    pid = mine.id
    partner = await _load(db, pid, lock=True)  # admin suspend aur online/offline ek saath chalein to line se chalein
    if partner.status != PartnerStatus.ACTIVE:
        raise api_error(403, "PARTNER_NOT_ACTIVE", "Aapka delivery partner account abhi active nahi hai.")
    if not online and await delivery_assignment.has_live_delivery(db, partner.id):
        raise api_error(409, "PARTNER_ON_DELIVERY", "Chalta hua order poora karo, tab offline ho sakte ho.")
    if partner.is_online != online:  # same baar dobara bhejo to kuch nahi badalta (idempotent)
        partner.is_online = online
        await db.commit()
    return await _load(db, pid)

# ---------------- Super Admin ----------------


async def list_partners(db: AsyncSession, status: str | None, limit: int, offset: int):
    q = (
        select(DeliveryPartner, User.phone)
        .join(User, User.id == DeliveryPartner.user_id)
        .order_by(DeliveryPartner.created_at.desc())
    )
    if status:
        q = q.where(DeliveryPartner.status == status)
    return (await db.execute(q.limit(limit).offset(offset))).all()


async def get_with_phone(db: AsyncSession, partner_id: uuid.UUID) -> tuple[DeliveryPartner, str]:
    partner = await _load(db, partner_id)
    if partner is None:
        raise api_error(404, "PARTNER_NOT_FOUND", "Delivery partner nahi mila.")
    user = await db.get(User, partner.user_id)
    return partner, user.phone


async def transition(
    db: AsyncSession, admin: User, request: Request, partner_id: uuid.UUID, action: str, reason: str | None
) -> tuple[DeliveryPartner, str]:
    partner = await _load(db, partner_id, lock=True)
    if partner is None:
        raise api_error(404, "PARTNER_NOT_FOUND", "Delivery partner nahi mila.")
    if not can_move(action, partner.status):
        raise api_error(409, "INVALID_STATE", f"Partner abhi {partner.status} hai, ye kaam ab nahi ho sakta.")

    target = TRANSITIONS[action][1]
    old = {"status": str(partner.status), "status_reason": partner.status_reason, "is_online": partner.is_online}
    partner.status = target
    partner.status_reason = reason
    if target != PartnerStatus.ACTIVE:
        partner.is_online = False  # suspend hote hi offline (DB rule bhi yahi kehta hai)
    elif action == "reactivate":
        partner.is_online = False  # wapas aane par khud online hona hoga
    if action == "suspend":  # pickup se pehle wale orders wapas free (koi aur partner le sakta hai)
        await delivery_assignment.release_assigned(db, partner.id, admin)
    write_audit(
        db, actor=admin, action=f"delivery_partner.{action}", target_type="delivery_partner", target_id=partner.id,
        old=old, new={"status": str(target), "status_reason": reason, "is_online": partner.is_online},
        reason=reason, request=request,
    )

    user = await db.get(User, partner.user_id)
    if action == "approve":  # Approve hone par DELIVERY_PARTNER role milta hai
        role = await db.scalar(select(Role).where(Role.name == "DELIVERY_PARTNER"))
        if role not in user.roles:
            user.roles.append(role)
    await db.commit()
    return await _load(db, partner_id), user.phone


async def read_kyc_photo(
    db: AsyncSession, admin: User, request: Request, partner_id: uuid.UUID, which: str
) -> bytes:
    """Sirf Super Admin. Har baar dekhne ka audit record banta hai."""
    partner = await _load(db, partner_id)
    if partner is None:
        raise api_error(404, "PARTNER_NOT_FOUND", "Delivery partner nahi mila.")
    key = partner.id_photo_key if which == "id" else partner.licence_photo_key
    if not key:
        raise api_error(404, "PARTNER_PHOTO_NOT_FOUND", "Ye photo maujood nahi hai.")
    try:
        data = await storage.get_private_object(key)
    except storage.StorageNotFound:
        raise api_error(404, "PARTNER_PHOTO_NOT_FOUND", "Ye photo maujood nahi hai.")
    except storage.StorageError:
        raise api_error(503, "STORAGE_UNAVAILABLE", "Photo storage abhi available nahi hai, dobara try karo.")
    write_audit(
        db, actor=admin, action="delivery_partner.view_kyc", target_type="delivery_partner", target_id=partner.id,
        new={"photo": which}, request=request,
    )
    await db.commit()
    return data