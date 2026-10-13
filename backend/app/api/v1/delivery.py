import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.errors import api_error
from app.models import User
from app.models.delivery import KycIdType, VehicleType
from app.schemas.delivery import DeliveryPartnerOut, partner_out
from app.schemas.delivery_cash import CashSummaryOut
from app.schemas.delivery_assignment import AvailableOrderOut, DeliveredOut, DeliverBody, MyDeliveryOut, ReleasedOut
from app.services import delivery_partner as service
from app.services import delivery_assignment, delivery_cash, delivery_progress
from app.services.image_processing import MAX_UPLOAD_BYTES

# Delivery partner khud ke liye. (Order milna / accept karna agle step me aayega.)
router = APIRouter(prefix="/delivery", tags=["delivery"])


async def _read_photo(file: UploadFile | None) -> bytes | None:
    if file is None:
        return None
    data = await file.read(MAX_UPLOAD_BYTES + 1)  # itna hi padhte hain, aage ki file memory me nahi lete
    if len(data) > MAX_UPLOAD_BYTES:
        raise api_error(413, "IMAGE_TOO_LARGE", "Photo bahut badi hai (max 5 MB).")
    return data or None  # khali file = photo nahi di


@router.post("/apply", response_model=DeliveryPartnerOut, status_code=201)
async def apply(
    full_name: str = Form(..., min_length=2, max_length=100),
    vehicle_type: VehicleType = Form(...),
    vehicle_number: str | None = Form(None, max_length=20),
    id_type: KycIdType = Form(...),
    id_photo: UploadFile = File(...),
    licence_photo: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """multipart/form-data. ID photo (Aadhaar/PAN) zaroori; licence photo option; bike/scooter ka number zaroori."""
    id_data = await _read_photo(id_photo)
    if id_data is None:
        raise api_error(422, "VALIDATION_ERROR", "ID photo zaroori hai.")
    licence_data = await _read_photo(licence_photo)
    partner = await service.apply(
        db, user,
        full_name=full_name, vehicle_type=vehicle_type.value, vehicle_number=vehicle_number,
        id_type=id_type.value, id_photo=id_data, licence_photo=licence_data,
    )
    return partner_out(partner, user.phone)


@router.get("/me", response_model=DeliveryPartnerOut)
async def my_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return partner_out(await service.get_mine(db, user), user.phone)


@router.post("/me/online", response_model=DeliveryPartnerOut)
async def go_online(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return partner_out(await service.set_online(db, user, True), user.phone)


@router.post("/me/offline", response_model=DeliveryPartnerOut)
async def go_offline(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return partner_out(await service.set_online(db, user, False), user.phone)


# ---------------- orders ----------------


@router.get("/orders/available", response_model=list[AvailableOrderOut])
async def available_orders(
    request: Request,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Aapke area ke SAARE open orders (customer ke order karte hi se), paas wale pehle.
    lat/lng = partner ki abhi ki location (zaroori). Sirf ACTIVE + ONLINE partner."""
    return await delivery_assignment.list_available(db, user, lat, lng, limit, offset, request.state.lang)


@router.get("/orders/current", response_model=MyDeliveryOut)
async def current_order(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Mera chalta hua order (customer ka address / phone ke saath)."""
    return await delivery_assignment.current(db, user, request.state.lang)


@router.post("/orders/{order_id}/accept", response_model=MyDeliveryOut)
async def accept_order(
    order_id: uuid.UUID,
    request: Request,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Order accept karo (lat/lng = aapki location). Jo pehle accept kare use milta hai; dusre ko 409 ORDER_NOT_AVAILABLE.
    Area se bahar ka order 409 ORDER_TOO_FAR."""
    return await delivery_assignment.accept(db, user, order_id, lat, lng, request.state.lang)


@router.post("/orders/{order_id}/release", response_model=ReleasedOut)
async def release_order(order_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Pickup se pehle order chhod do; wo wapas sabko dikhega."""
    return ReleasedOut(order_id=await delivery_assignment.release(db, user, order_id))


@router.post("/orders/{order_id}/stores/{store_order_id}/pickup", response_model=MyDeliveryOut)
async def pickup_store(
    order_id: uuid.UUID, store_order_id: uuid.UUID, request: Request,
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    """Is dukaan se saaman utha liya. Sirf tab jab dukaan READY_FOR_PICKUP ho; saari dukaanon se uthne par order PICKED_UP."""
    return await delivery_progress.pickup_store(db, user, order_id, store_order_id, request.state.lang)


@router.post("/orders/{order_id}/start", response_model=MyDeliveryOut)
async def start_delivery(order_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Saari dukaanon se saaman ho gaya, customer ke liye nikal pada (OUT_FOR_DELIVERY)."""
    return await delivery_progress.start_delivery(db, user, order_id, request.state.lang)


@router.post("/orders/{order_id}/deliver", response_model=DeliveredOut)
async def deliver_order(order_id: uuid.UUID, body: DeliverBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Customer se 4 ank ka OTP lekar delivery poori karo. COD me cash mil gaya maana jaayega (payment_status PAID).
    Galat OTP: 422 OTP_INVALID; 5 galat ke baad 10 minute ke liye 429 OTP_LOCKED."""
    return await delivery_progress.complete_delivery(db, user, order_id, body.otp)


@router.get("/me/cash", response_model=CashSummaryOut)
async def my_cash(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Mere paas COD ka kitna cash hai (jo customers se liya - jo admin ko jama kiya), aur haal ka hisaab."""
    return await delivery_cash.my_summary(db, user)