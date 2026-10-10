"""sellers, stores, audit_logs

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sellers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("seller_type", sa.String(20), nullable=False),
        sa.Column("business_name", sa.String(150), nullable=False),
        sa.Column("owner_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("status_reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("seller_type IN ('KIRANA','RESTAURANT')", name="ck_sellers_type"),
        sa.CheckConstraint("status IN ('PENDING','ACTIVE','REJECTED','SUSPENDED')", name="ck_sellers_status"),
    )
    op.create_index("ix_sellers_user_id", "sellers", ["user_id"], unique=True)
    op.create_index("ix_sellers_status", "sellers", ["status"])

    op.create_table(
        "stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sellers.id"), nullable=False),
        sa.Column("store_type", sa.String(20), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("cuisine", sa.String(100)),
        sa.Column("address", sa.String(300), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("delivery_radius_km", sa.Numeric(4, 1), nullable=False, server_default="3"),
        sa.Column("min_order_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("shop_status", sa.String(10), nullable=False, server_default="CLOSED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("shop_status IN ('OPEN','CLOSED')", name="ck_stores_shop_status"),
    )
    op.create_index("ix_stores_seller_id", "stores", ["seller_id"])
    op.create_index("ix_stores_shop_status", "stores", ["shop_status"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("old_value", postgresql.JSONB),
        sa.Column("new_value", postgresql.JSONB),
        sa.Column("reason", sa.String(500)),
        sa.Column("request_id", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_target", "audit_logs", ["target_type", "target_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("stores")
    op.drop_table("sellers")