"""Add store categories and store images.

Revision ID: 0030
Revises: 0029
"""
import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

CATEGORIES = (
    "GROCERY", "RESTAURANT", "HARDWARE", "MEDICAL", "CLOTHING", "MOBILE_ELECTRONICS",
    "FOOTWEAR", "FRUITS_VEGETABLES", "DAIRY", "BAKERY", "STATIONERY", "BEAUTY_COSMETICS",
    "HOME_FURNITURE", "ELECTRICAL", "AUTO_PARTS", "PET_SUPPLIES", "BOOKS_GIFTS", "SPORTS",
    "AGRICULTURE", "OTHER",
)


def upgrade() -> None:
    op.add_column("stores", sa.Column("store_category", sa.String(32), nullable=False, server_default="GROCERY"))
    op.add_column("stores", sa.Column("image_key", sa.String(300), nullable=True))
    op.execute("UPDATE stores SET store_category = 'RESTAURANT' WHERE store_type = 'RESTAURANT'")
    op.create_check_constraint(
        "ck_stores_store_category", "stores", "store_category IN (" + ", ".join(f"'{v}'" for v in CATEGORIES) + ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_stores_store_category", "stores", type_="check")
    op.drop_column("stores", "image_key")
    op.drop_column("stores", "store_category")
