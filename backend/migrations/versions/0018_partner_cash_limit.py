"""delivery_partners.cash_limit (admin har partner ki COD cash limit tay karta hai, default 3000)

Revision ID: 0018
Revises: 0017
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delivery_partners", sa.Column("cash_limit", sa.Numeric(10, 2), nullable=False, server_default="3000.00"))
    op.create_check_constraint("ck_delivery_partners_cash_limit", "delivery_partners", "cash_limit > 0")


def downgrade() -> None:
    op.drop_constraint("ck_delivery_partners_cash_limit", "delivery_partners")
    op.drop_column("delivery_partners", "cash_limit")