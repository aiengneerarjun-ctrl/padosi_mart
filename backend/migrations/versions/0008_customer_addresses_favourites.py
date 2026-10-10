"""customer addresses + favourites

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_addresses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("label", sa.String(10), nullable=False, server_default="HOME"),
        sa.Column("receiver_name", sa.String(100), nullable=False),
        sa.Column("receiver_phone", sa.String(15), nullable=False),
        sa.Column("address_line", sa.String(300), nullable=False),
        sa.Column("landmark", sa.String(150)),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("label IN ('HOME','WORK','OTHER')", name="ck_customer_addresses_label"),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180", name="ck_customer_addresses_geo"),
    )
    op.create_index("ix_customer_addresses_user_id", "customer_addresses", ["user_id"])
    op.create_index(
        "uq_customer_one_default_address", "customer_addresses", ["user_id"], unique=True,
        postgresql_where=sa.text("is_default AND is_active"),
    )

    op.create_table(
        "favourite_stores",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_favourite_stores_store_id", "favourite_stores", ["store_id"])

    op.create_table(
        "favourite_products",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_favourite_products_product_id", "favourite_products", ["product_id"])


def downgrade() -> None:
    op.drop_table("favourite_products")
    op.drop_table("favourite_stores")
    op.drop_table("customer_addresses")