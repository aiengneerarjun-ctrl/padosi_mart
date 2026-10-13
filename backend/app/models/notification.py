import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Notification(Base):
    """Kisi user (customer / seller / partner) ke liye ek notification. Text yahan save nahi hota: code + params save hote hain,
    text padhte waqt user ki bhasha me banta hai (core/i18n.py me NOTIF_<CODE>_TITLE / _BODY)."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(40))
    params: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())