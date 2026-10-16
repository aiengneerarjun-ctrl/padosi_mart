import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class NotificationOut(BaseModel):
    id: uuid.UUID
    code: str  # app isse icon / rang tay kar sakta hai
    title: str  # user ki bhasha me
    body: str
    order_id: uuid.UUID | None  # hai to tap par wo order khulna chahiye
    is_read: bool
    created_at: datetime
    read_at: datetime | None


class UnreadCountOut(BaseModel):
    unread: int


class MarkedOut(BaseModel):
    marked: int  # kitni notifications 'padhi' hui ho gayin


class DeviceIn(BaseModel):
    token: str = Field(min_length=20, max_length=1024)  # Firebase se mila FCM token
    platform: Literal["android", "ios", "web"] = "android"

    @field_validator("token")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 20 or any(c.isspace() for c in v):
            raise ValueError("token galat hai")
        return v


class DeviceOut(BaseModel):
    registered: bool


class DeviceRemovedOut(BaseModel):
    removed: int  # 0 ya 1 (pehle se hata hua ho to 0, error nahi)
