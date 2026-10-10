import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AddressLabel = Literal["HOME", "WORK", "OTHER"]


class AddressBase(BaseModel):
    label: AddressLabel = "HOME"
    receiver_name: str = Field(min_length=2, max_length=100)
    receiver_phone: str = Field(min_length=10, max_length=15, pattern=r"^\+?\d{10,14}$")
    address_line: str = Field(min_length=5, max_length=300)
    landmark: str | None = Field(default=None, max_length=150)
    latitude: Decimal = Field(ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal = Field(ge=-180, le=180, max_digits=9, decimal_places=6)

    @field_validator("receiver_name", "address_line", "landmark")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


class AddressCreate(AddressBase):
    make_default: bool = False


class AddressUpdate(BaseModel):
    label: AddressLabel | None = None
    receiver_name: str | None = Field(default=None, min_length=2, max_length=100)
    receiver_phone: str | None = Field(default=None, pattern=r"^\+?\d{10,14}$")
    address_line: str | None = Field(default=None, min_length=5, max_length=300)
    landmark: str | None = Field(default=None, max_length=150)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180, max_digits=9, decimal_places=6)


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    receiver_name: str
    receiver_phone: str
    address_line: str
    landmark: str | None
    latitude: float
    longitude: float
    is_default: bool