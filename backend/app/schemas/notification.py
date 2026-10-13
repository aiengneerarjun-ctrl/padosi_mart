import uuid
from datetime import datetime

from pydantic import BaseModel


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