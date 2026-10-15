"""online payments (Cashfree): payments, refunds, payment_events

Revision ID: 0023
Revises: 0022
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # Ek order ka ek hi payment (Cashfree order). Customer wahi order par kai baar koshish kar sakta hai.
    op.create_table(
        "payments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id"), nullable=False, unique=True),
        sa.Column("provider", sa.String(20), nullable=False, server_default="CASHFREE"),
        sa.Column("provider_order_id", sa.String(45), nullable=False, unique=True),  # Cashfree me hamara order_id
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="CREATED"),
        sa.Column("cf_order_id", sa.String(40)),
        sa.Column("cf_payment_id", sa.String(40)),
        sa.Column("payment_session_id", sa.Text),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount"),
        sa.CheckConstraint("status IN ('CREATED', 'PAID')", name="ck_payments_status"),
        sa.CheckConstraint("(status = 'PAID') = (paid_at IS NOT NULL)", name="ck_payments_paid_at"),
    )

    op.create_table(
        "refunds",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("payment_id", UUID, sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("refund_id", sa.String(40), nullable=False, unique=True),  # Cashfree me hamara refund_id
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="PENDING"),
        sa.Column("reason_code", sa.String(30), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("cf_refund_id", sa.String(40)),
        sa.Column("provider_status", sa.String(30)),
        sa.Column("actor_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="ck_refunds_amount"),
        sa.CheckConstraint("status IN ('PENDING', 'SUCCESS', 'FAILED')", name="ck_refunds_status"),
    )
    op.create_index("ix_refunds_order", "refunds", ["order_id"])
    op.create_index("ix_refunds_status", "refunds", ["status", "created_at"])

    # Webhook ek se zyada baar aa sakta hai: event_key se pehchankar dobara nahi chalate
    op.create_table(
        "payment_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("event_key", sa.String(160), nullable=False, unique=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("payment_events")
    op.drop_table("refunds")
    op.drop_table("payments")