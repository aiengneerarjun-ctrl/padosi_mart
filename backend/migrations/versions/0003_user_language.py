"""users.language (en / hi / bho)

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("language", sa.String(5), nullable=False, server_default="en"))
    op.create_check_constraint("ck_users_language", "users", "language IN ('en','hi','bho')")


def downgrade() -> None:
    op.drop_constraint("ck_users_language", "users", type_="check")
    op.drop_column("users", "language")