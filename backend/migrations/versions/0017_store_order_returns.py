"""store_order_returns (fail hui delivery ka saaman dukaan ko wapas: record + stock wapas)

Revision ID: 0017
Revises: 0016
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "store_order_returns",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("store_order_id", UUID, sa.ForeignKey("store_orders.id"), nullable=False, unique=True),  # ek dukaan ka hissa ek hi baar lautega
        sa.Column("delivery_id", UUID, sa.ForeignKey("deliveries.id"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="PENDING"),
        sa.Column("was_picked_up", sa.Boolean, nullable=False),  # True = partner dukaan se utha chuka tha, False = saaman dukaan me hi tha
        sa.Column("restocked", sa.Boolean, nullable=False, server_default="false"),  # stock wapas judaa ya nahi
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("received_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("received_role", sa.String(20)),  # SELLER / SUPER_ADMIN
        sa.Column("note", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('PENDING', 'RECEIVED')", name="ck_store_order_returns_status"),
        # RECEIVED ho to kab aur kisne likha hona chahiye; PENDING me ye khali
        sa.CheckConstraint(
            "(status = 'PENDING' AND received_at IS NULL AND NOT restocked) OR (status = 'RECEIVED' AND received_at IS NOT NULL)",
            name="ck_store_order_returns_received",
        ),
    )
    op.create_index("ix_store_order_returns_status", "store_order_returns", ["status", "created_at"])
    op.create_index("ix_store_order_returns_order", "store_order_returns", ["order_id"])

    # Jo deliveries pehle hi FAIL ho chuki hain, unke dukaan-hisse bhi wapas aane ki list me aayein
    op.execute(
        """
        INSERT INTO store_order_returns (id, order_id, store_order_id, delivery_id, status, was_picked_up, restocked)
        SELECT gen_random_uuid(), so.order_id, so.id, d.id, 'PENDING', so.status = 'PICKED_UP', false
        FROM deliveries d
        JOIN store_orders so ON so.order_id = d.order_id
        WHERE d.status = 'FAILED' AND so.status NOT IN ('REJECTED', 'CANCELLED')
        """
    )


def downgrade() -> None:
    op.drop_table("store_order_returns")