"""deliveries: failed_at, fail_reason (delivery fail hone ka record)

Revision ID: 0016
Revises: 0015
"""
import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deliveries", sa.Column("failed_at", sa.DateTime(timezone=True)))
    op.add_column("deliveries", sa.Column("fail_reason", sa.String(300)))


def downgrade() -> None:
    op.drop_column("deliveries", "fail_reason")
    op.drop_column("deliveries", "failed_at")