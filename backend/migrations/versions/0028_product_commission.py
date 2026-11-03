"""product-level flexible commission snapshots

Revision ID: 0028
Revises: 0027
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("commission_mode", sa.String(10), nullable=False, server_default="PERCENT"))
    op.add_column("products", sa.Column("commission_unit", sa.String(20), nullable=False, server_default="SALE_UNIT"))
    op.add_column("products", sa.Column("commission_value", sa.Numeric(10, 4), nullable=False, server_default="0"))
    op.add_column("products", sa.Column("commission_unit_quantity", sa.Numeric(12, 4), nullable=False, server_default="1"))
    op.create_check_constraint("ck_products_commission_mode", "products", "commission_mode IN ('PERCENT','FIXED')")
    op.create_check_constraint(
        "ck_products_commission_value", "products",
        "commission_value >= 0 AND (commission_mode <> 'PERCENT' OR commission_value <= 100) AND commission_unit_quantity > 0",
    )
    # Purane active products ko unka pehle wala store-type percent dekar migrate karo.
    op.execute("""
        UPDATE products AS p
        SET commission_mode = 'PERCENT', commission_unit = 'SALE_UNIT',
            commission_value = CASE WHEN s.store_type = 'RESTAURANT' THEN COALESCE(ss.restaurant_rate, 0) ELSE COALESCE(ss.kirana_rate, 0) END,
            commission_unit_quantity = 1
        FROM stores AS s LEFT JOIN settlement_settings AS ss ON ss.id = 1
        WHERE p.store_id = s.id
    """)

    op.add_column("order_items", sa.Column("commission_mode", sa.String(10), nullable=False, server_default="PERCENT"))
    op.add_column("order_items", sa.Column("commission_unit", sa.String(20), nullable=False, server_default="SALE_UNIT"))
    op.add_column("order_items", sa.Column("commission_value", sa.Numeric(10, 4), nullable=False, server_default="0"))
    op.add_column("order_items", sa.Column("commission_unit_quantity", sa.Numeric(12, 4), nullable=False, server_default="1"))
    op.create_check_constraint("ck_order_items_commission_mode", "order_items", "commission_mode IN ('PERCENT','FIXED')")
    op.create_check_constraint(
        "ck_order_items_commission_value", "order_items",
        "commission_value >= 0 AND (commission_mode <> 'PERCENT' OR commission_value <= 100) AND commission_unit_quantity > 0",
    )
    # Immutable order_items ko UPDATE nahi kar sakte. Purane orders ke liye sidecar snapshot banao.
    op.create_table(
        "order_item_commission_snapshots",
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("order_items.id"), primary_key=True),
        sa.Column("commission_mode", sa.String(10), nullable=False),
        sa.Column("commission_unit", sa.String(20), nullable=False),
        sa.Column("commission_value", sa.Numeric(10, 4), nullable=False),
        sa.Column("commission_unit_quantity", sa.Numeric(12, 4), nullable=False),
    )
    op.execute("""
        INSERT INTO order_item_commission_snapshots
            (order_item_id, commission_mode, commission_unit, commission_value, commission_unit_quantity)
        SELECT oi.id,
            CASE WHEN so.commission_amount IS NOT NULL THEN 'PERCENT' ELSE p.commission_mode END,
            CASE WHEN so.commission_amount IS NOT NULL THEN 'SALE_UNIT' ELSE p.commission_unit END,
            CASE WHEN so.commission_amount IS NOT NULL THEN COALESCE(so.commission_rate, 0) ELSE p.commission_value END,
            CASE WHEN so.commission_amount IS NOT NULL THEN 1 ELSE p.commission_unit_quantity END
        FROM order_items AS oi
        JOIN products AS p ON p.id = oi.product_id
        JOIN store_orders AS so ON so.id = oi.store_order_id
    """)
    op.execute(
        "CREATE TRIGGER trg_order_item_commission_snapshots_immutable "
        "BEFORE UPDATE OR DELETE ON order_item_commission_snapshots "
        "FOR EACH ROW EXECUTE FUNCTION block_update_delete()"
    )


def downgrade() -> None:
    op.drop_table("order_item_commission_snapshots")
    op.drop_constraint("ck_order_items_commission_value", "order_items", type_="check")
    op.drop_constraint("ck_order_items_commission_mode", "order_items", type_="check")
    op.drop_column("order_items", "commission_unit_quantity")
    op.drop_column("order_items", "commission_value")
    op.drop_column("order_items", "commission_unit")
    op.drop_column("order_items", "commission_mode")
    op.drop_constraint("ck_products_commission_value", "products", type_="check")
    op.drop_constraint("ck_products_commission_mode", "products", type_="check")
    op.drop_column("products", "commission_unit_quantity")
    op.drop_column("products", "commission_value")
    op.drop_column("products", "commission_unit")
    op.drop_column("products", "commission_mode")
