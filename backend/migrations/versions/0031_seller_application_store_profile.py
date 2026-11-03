"""Collect store category and photo during seller application.

Revision ID: 0031
Revises: 0030
"""
import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None

CATEGORIES = (
    "GROCERY", "RESTAURANT", "HARDWARE", "MEDICAL", "CLOTHING", "MOBILE_ELECTRONICS",
    "FOOTWEAR", "FRUITS_VEGETABLES", "DAIRY", "BAKERY", "STATIONERY", "BEAUTY_COSMETICS",
    "HOME_FURNITURE", "ELECTRICAL", "AUTO_PARTS", "PET_SUPPLIES", "BOOKS_GIFTS", "SPORTS",
    "AGRICULTURE", "OTHER",
)


def upgrade() -> None:
    op.add_column("sellers", sa.Column("store_category", sa.String(32), nullable=False, server_default="GROCERY"))
    op.add_column("sellers", sa.Column("store_image_key", sa.String(300), nullable=True))
    op.execute("UPDATE sellers SET store_category = 'RESTAURANT' WHERE seller_type = 'RESTAURANT'")
    op.create_check_constraint(
        "ck_sellers_store_category", "sellers", "store_category IN (" + ", ".join(f"'{v}'" for v in CATEGORIES) + ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sellers_store_category", "sellers", type_="check")
    op.drop_column("sellers", "store_image_key")
    op.drop_column("sellers", "store_category")
