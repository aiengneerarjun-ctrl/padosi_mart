"""Allow delivery partners to carry multiple active orders.

Revision ID: 0029
Revises: 0028
"""
import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_deliveries_partner_active", table_name="deliveries")


def downgrade() -> None:
    op.create_index(
        "uq_deliveries_partner_active", "deliveries", ["partner_id"], unique=True,
        postgresql_where=sa.text("status IN ('ASSIGNED', 'PICKED_UP', 'OUT_FOR_DELIVERY')"),
    )
