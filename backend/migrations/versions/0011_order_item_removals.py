"""order_item_removals + orders.original_items_subtotal / original_total

Revision ID: 0011
Revises: 0010
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
REASONS = ("OUT_OF_STOCK", "QUALITY_ISSUE", "SHOP_CLOSING", "OTHER")


def upgrade() -> None:
    # Order ka original hisaab alag rakhte hain (seller item hataye to total ghatta hai, original nahi)
    op.add_column("orders", sa.Column("original_items_subtotal", sa.Numeric(10, 2)))
    op.add_column("orders", sa.Column("original_total", sa.Numeric(10, 2)))
    op.execute("UPDATE orders SET original_items_subtotal = items_subtotal, original_total = total")
    op.alter_column("orders", "original_items_subtotal", nullable=False)
    op.alter_column("orders", "original_total", nullable=False)

    op.create_table(
        "order_item_removals",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("store_order_id", UUID, sa.ForeignKey("store_orders.id"), nullable=False),
        sa.Column("order_item_id", UUID, sa.ForeignKey("order_items.id"), nullable=False, unique=True),
        sa.Column("reason_code", sa.String(20), nullable=False),
        sa.Column("note", sa.String(200)),
        sa.Column("line_total", sa.Numeric(10, 2), nullable=False),
        sa.Column("actor_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("reason_code IN (" + ", ".join(f"'{r}'" for r in REASONS) + ")", name="ck_order_item_removals_reason"),
    )
    op.create_index("ix_order_item_removals_order", "order_item_removals", ["order_id"])
    # Hatane ka record kabhi badla/hataya nahi jaa sakta (block_update_delete() migration 0010 me bana tha)
    op.execute(
        "CREATE TRIGGER trg_order_item_removals_immutable BEFORE UPDATE OR DELETE ON order_item_removals "
        "FOR EACH ROW EXECUTE FUNCTION block_update_delete()"
    )


def downgrade() -> None:
    op.drop_table("order_item_removals")
    op.drop_column("orders", "original_total")
    op.drop_column("orders", "original_items_subtotal")