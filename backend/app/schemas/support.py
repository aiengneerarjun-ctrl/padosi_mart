import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

RaisedAs = Literal["CUSTOMER", "SELLER", "DELIVERY_PARTNER"]
Category = Literal["ORDER_ISSUE", "PAYMENT", "DELIVERY", "ACCOUNT", "OTHER"]


def _strip(v: str) -> str:
    return (v or "").strip()


class TicketCreate(BaseModel):
    raised_as: RaisedAs = "CUSTOMER"  # kis roop me likh rahe ho (tumhare paas wo role hona chahiye)
    order_id: uuid.UUID | None = None  # kisi order ke baare me ho to
    category: Category
    subject: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("subject", "message", mode="before")
    @classmethod
    def _s(cls, v):
        return _strip(v) if isinstance(v, str) else v


class MessageBody(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body", mode="before")
    @classmethod
    def _s(cls, v):
        return _strip(v) if isinstance(v, str) else v


class TicketMessageOut(BaseModel):
    id: uuid.UUID
    author_type: str  # USER (ticket kholne wala) / ADMIN (Padosi support)
    body: str
    created_at: datetime


class TicketOut(BaseModel):
    id: uuid.UUID
    ticket_number: str  # TK1001
    raised_as: str
    category: str
    subject: str
    status: str  # OPEN (support ke jawab ka intezaar) / ANSWERED (support ne jawab diya) / CLOSED
    order_id: uuid.UUID | None
    order_number: str | None
    last_message: str  # list me dikhane ke liye (pehle 100 akshar)
    message_count: int
    created_at: datetime
    last_message_at: datetime
    closed_at: datetime | None


class TicketDetailOut(TicketOut):
    messages: list[TicketMessageOut]


class AdminTicketOut(TicketOut):
    user_id: uuid.UUID
    user_name: str | None
    user_phone: str


class AdminTicketDetailOut(AdminTicketOut):
    messages: list[TicketMessageOut]


class CloseBody(BaseModel):
    note: str | None = Field(default=None, max_length=300)  # admin ke liye optional (audit me jata hai)
