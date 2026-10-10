"""categories, brands, products, inventory, inventory_transactions

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("parent_id", UUID, sa.ForeignKey("categories.id")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_hi", sa.String(100)),
        sa.Column("name_bho", sa.String(100)),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])

    op.create_table(
        "brands",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "products",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("store_id", UUID, sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("category_id", UUID, sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("brand_id", UUID, sa.ForeignKey("brands.id")),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("barcode", sa.String(64)),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_hi", sa.String(200)),
        sa.Column("name_bho", sa.String(200)),
        sa.Column("description", sa.String(2000)),
        sa.Column("selling_unit", sa.String(50), nullable=False),
        sa.Column("mrp", sa.Numeric(10, 2), nullable=False),
        sa.Column("selling_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING_APPROVAL"),
        sa.Column("status_reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("store_id", "sku", name="uq_products_store_sku"),
        sa.CheckConstraint(
            "status IN ('PENDING_APPROVAL','ACTIVE','OUT_OF_STOCK','INACTIVE','REJECTED')", name="ck_products_status"
        ),
        sa.CheckConstraint("mrp > 0 AND selling_price > 0 AND selling_price <= mrp", name="ck_products_price"),
    )
    op.create_index("ix_products_store_id", "products", ["store_id"])
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_barcode", "products", ["barcode"])
    op.create_index("ix_products_status", "products", ["status"])

    op.create_table(
        "inventory",
        sa.Column("product_id", UUID, sa.ForeignKey("products.id"), primary_key=True),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("low_stock_threshold", sa.Integer, nullable=False, server_default="5"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_quantity_non_negative"),
        sa.CheckConstraint("low_stock_threshold >= 0", name="ck_inventory_threshold_non_negative"),
    )

    op.create_table(
        "inventory_transactions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("product_id", UUID, sa.ForeignKey("products.id"), nullable=False),
        sa.Column("change", sa.Integer, nullable=False),
        sa.Column("quantity_after", sa.Integer, nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("actor_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("change <> 0", name="ck_inv_txn_change_nonzero"),
        sa.CheckConstraint(
            "reason IN ('INITIAL','STOCK_IN','ADJUSTMENT','DAMAGED','ORDER','ORDER_CANCEL','RETURN')",
            name="ck_inv_txn_reason",
        ),
    )
    op.create_index("ix_inventory_transactions_product_id", "inventory_transactions", ["product_id"])
    op.create_index("ix_inventory_transactions_created_at", "inventory_transactions", ["created_at"])


def downgrade() -> None:
    op.drop_table("inventory_transactions")
    op.drop_table("inventory")
    op.drop_table("products")
    op.drop_table("brands")
    op.drop_table("categories")
    