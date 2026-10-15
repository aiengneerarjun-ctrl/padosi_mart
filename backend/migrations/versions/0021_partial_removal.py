"""order_item_removals.kept_quantity / kept_item_id (aadha saaman: 3 maange, 2 hi hain)

Revision ID: 0021
Revises: 0020
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # Aadha saaman: purani line poori 'hatayi' jaati hai, aur bache hue piece ki NAYI line judti hai.
    # Hatane ke record me likha rehta hai ki kitne piece bache aur wo nayi line kaunsi hai.
    op.add_column("order_item_removals", sa.Column("kept_quantity", sa.Integer))
    op.add_column("order_item_removals", sa.Column("kept_item_id", UUID, sa.ForeignKey("order_items.id")))
    op.create_check_constraint(
        "ck_order_item_removals_kept", "order_item_removals",
        "(kept_quantity IS NULL AND kept_item_id IS NULL) OR (kept_quantity > 0 AND kept_item_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_order_item_removals_kept", "order_item_removals")
    op.drop_column("order_item_removals", "kept_item_id")
    op.drop_column("order_item_removals", "kept_quantity")