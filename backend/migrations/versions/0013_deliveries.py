"""deliveries (order delivery partner ko milna: accept / release)

Revision ID: 0013
Revises: 0012
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
STATUSES = ("ASSIGNED", "PICKED_UP", "OUT_FOR_DELIVERY", "DELIVERED", "RELEASED", "FAILED")


def upgrade() -> None:
    op.create_table(
        "deliveries",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("partner_id", UUID, sa.ForeignKey("delivery_partners.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ASSIGNED"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("release_reason", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN (" + ", ".join(f"'{s}'" for s in STATUSES) + ")", name="ck_deliveries_status"),
    )
    op.create_index("ix_deliveries_partner", "deliveries", ["partner_id", "status"])
    # Database level rule 1: ek order ki ek hi "zinda" delivery (chhodi hui ginti me nahi) -> do partner ek order nahi le sakte
    op.create_index(
        "uq_deliveries_order_live", "deliveries", ["order_id"], unique=True, postgresql_where=sa.text("status <> 'RELEASED'")
    )
    # Database level rule 2: ek partner ke paas ek samay me ek hi chalta hua order.
    # (Baad me ek se zyada order dene ho to bas ye index hatana hai.)
    op.create_index(
        "uq_deliveries_partner_active", "deliveries", ["partner_id"], unique=True,
        postgresql_where=sa.text("status IN ('ASSIGNED', 'PICKED_UP', 'OUT_FOR_DELIVERY')"),
    )


def downgrade() -> None:
    op.drop_table("deliveries")