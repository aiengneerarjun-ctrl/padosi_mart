"""orders, store_orders, order_items, order_status_history

Revision ID: 0010
Revises: 0009
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
ORDER_STATUSES = (
    "PLACED", "CONFIRMED", "SELLER_ACCEPTED", "PREPARING", "READY_FOR_PICKUP", "DELIVERY_ASSIGNED", "PICKED_UP",
    "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED", "PAYMENT_FAILED", "REFUND_PENDING", "REFUNDED", "RETURN_REQUESTED",
    "FAILED_DELIVERY",
)
STORE_ORDER_STATUSES = ("PLACED", "SELLER_ACCEPTED", "PREPARING", "READY_FOR_PICKUP", "PICKED_UP", "CANCELLED", "REJECTED")
PAYMENT_STATUSES = ("PENDING", "PAID", "FAILED", "REFUND_PENDING", "REFUNDED", "NOT_REQUIRED")


def _in(values) -> str:
    return ", ".join(f"'{v}'" for v in values)


def upgrade() -> None:
    op.execute("CREATE SEQUENCE order_no_seq START 1001")

    op.create_table(
        "orders",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_no", sa.BigInteger, nullable=False, unique=True, server_default=sa.text("nextval('order_no_seq')")),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PLACED"),
        sa.Column("payment_method", sa.String(10), nullable=False),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("receiver_name", sa.String(100), nullable=False),
        sa.Column("receiver_phone", sa.String(15), nullable=False),
        sa.Column("address_line", sa.String(300), nullable=False),
        sa.Column("landmark", sa.String(150)),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("items_subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("delivery_fee", sa.Numeric(10, 2), nullable=False),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_idempotency"),
        sa.CheckConstraint(f"status IN ({_in(ORDER_STATUSES)})", name="ck_orders_status"),
        sa.CheckConstraint("payment_method IN ('COD', 'ONLINE')", name="ck_orders_payment_method"),
        sa.CheckConstraint(f"payment_status IN ({_in(PAYMENT_STATUSES)})", name="ck_orders_payment_status"),
        sa.CheckConstraint("items_subtotal >= 0 AND delivery_fee >= 0 AND total = items_subtotal + delivery_fee", name="ck_orders_money"),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_user_created", "orders", ["user_id", "created_at"])

    op.create_table(
        "store_orders",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("store_id", UUID, sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("seller_id", UUID, sa.ForeignKey("sellers.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PLACED"),
        sa.Column("store_name", sa.String(150), nullable=False),
        sa.Column("store_address", sa.String(300), nullable=False),
        sa.Column("store_latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("store_longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("items_subtotal", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("order_id", "store_id", name="uq_store_orders_order_store"),
        sa.CheckConstraint(f"status IN ({_in(STORE_ORDER_STATUSES)})", name="ck_store_orders_status"),
        sa.CheckConstraint("items_subtotal >= 0", name="ck_store_orders_subtotal"),
    )
    op.create_index("ix_store_orders_order_id", "store_orders", ["order_id"])
    op.create_index("ix_store_orders_store_status", "store_orders", ["store_id", "status", "created_at"])

    op.create_table(
        "order_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("store_order_id", UUID, sa.ForeignKey("store_orders.id"), nullable=False),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_hi", sa.String(200)),
        sa.Column("name_bho", sa.String(200)),
        sa.Column("selling_unit", sa.String(50), nullable=False),
        sa.Column("mrp", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity > 0 AND unit_price >= 0 AND line_total = unit_price * quantity", name="ck_order_items_money"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_store_order_id", "order_items", ["store_order_id"])
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])

    op.create_table(
        "order_status_history",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("seq", sa.BigInteger, sa.Identity(), nullable=False, unique=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("store_order_id", UUID, sa.ForeignKey("store_orders.id")),
        sa.Column("from_status", sa.String(20)),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("actor_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("actor_role", sa.String(20), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_order_status_history_order", "order_status_history", ["order_id", "seq"])

    # Itihaas aur order ki lines kabhi badli/hataayi nahi jaa sakti (database khud rokta hai)
    op.execute(
        """
        CREATE FUNCTION block_update_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% table me badlav ya delete allowed nahi hai', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in ("order_status_history", "order_items"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION block_update_delete()"
        )


def downgrade() -> None:
    op.drop_table("order_status_history")
    op.drop_table("order_items")
    op.drop_table("store_orders")
    op.drop_table("orders")
    op.execute("DROP FUNCTION block_update_delete()")
    op.execute("DROP SEQUENCE order_no_seq")