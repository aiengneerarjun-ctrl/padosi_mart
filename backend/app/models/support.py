import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SupportTicket(Base):
    """Customer / seller / delivery partner ki shikayat ya sawaal, Super Admin ke naam. Ek ticket = ek baatcheet (sandesho ki list)."""

    __tablename__ = "support_tickets"
    __table_args__ = (
        CheckConstraint("raised_as IN ('CUSTOMER','SELLER','DELIVERY_PARTNER')", name="ck_support_tickets_raised_as"),
        CheckConstraint("category IN ('ORDER_ISSUE','PAYMENT','DELIVERY','ACCOUNT','OTHER')", name="ck_support_tickets_category"),
        CheckConstraint("status IN ('OPEN','ANSWERED','CLOSED')", name="ck_support_tickets_status"),
        CheckConstraint("(status = 'CLOSED') = (closed_at IS NOT NULL)", name="ck_support_tickets_closed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_no: Mapped[int] = mapped_column(BigInteger, unique=True, server_default=text("nextval('ticket_no_seq')"))

    @property
    def ticket_number(self) -> str:
        return f"TK{self.ticket_no}"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    raised_as: Mapped[str] = mapped_column(String(20))
    order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orders.id"))
    category: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(10), default="OPEN", server_default="OPEN")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SupportMessage(Base):
    """Ticket ka ek sandesha. Bhejne ke baad badalta / hatta nahi (database trigger)."""

    __tablename__ = "support_messages"
    __table_args__ = (CheckConstraint("author_type IN ('USER','ADMIN')", name="ck_support_messages_author_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("support_tickets.id"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    author_type: Mapped[str] = mapped_column(String(5))  # USER / ADMIN
    body: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
