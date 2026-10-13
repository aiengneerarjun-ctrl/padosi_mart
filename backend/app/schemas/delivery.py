import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.delivery import DeliveryPartner


class DeliveryPartnerOut(BaseModel):
    """Partner ko apna profile. ID photo ki key / link kabhi nahi bhejte, sirf ye ki photo di hai."""

    id: uuid.UUID
    full_name: str
    phone: str
    vehicle_type: str
    vehicle_number: str | None
    id_type: str
    has_licence_photo: bool
    status: str
    status_reason: str | None
    is_online: bool
    created_at: datetime


class AdminDeliveryPartnerOut(DeliveryPartnerOut):
    user_id: uuid.UUID


def partner_out(p: DeliveryPartner, phone: str) -> DeliveryPartnerOut:
    return DeliveryPartnerOut(**_fields(p, phone))


def admin_partner_out(p: DeliveryPartner, phone: str) -> AdminDeliveryPartnerOut:
    return AdminDeliveryPartnerOut(**_fields(p, phone), user_id=p.user_id)


def _fields(p: DeliveryPartner, phone: str) -> dict:
    return dict(
        id=p.id,
        full_name=p.full_name,
        phone=phone,
        vehicle_type=p.vehicle_type,
        vehicle_number=p.vehicle_number,
        id_type=p.id_type,
        has_licence_photo=p.licence_photo_key is not None,
        status=p.status,
        status_reason=p.status_reason,
        is_online=p.is_online,
        created_at=p.created_at,
    )