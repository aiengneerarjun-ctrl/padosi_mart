import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.seller import SellerType


class SellerApply(BaseModel):
    seller_type: SellerType
    business_name: str = Field(min_length=2, max_length=150)
    owner_name: str = Field(min_length=2, max_length=100)


class SellerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    seller_type: str
    business_name: str
    owner_name: str
    status: str
    status_reason: str | None
    created_at: datetime


class AdminSellerOut(SellerOut):
    user_id: uuid.UUID
    phone: str


class ReasonBody(BaseModel):
    reason: str = Field(min_length=3, max_length=500)