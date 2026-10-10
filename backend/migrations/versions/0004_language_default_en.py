"""users.language ka default en karo

Revision ID: 0004
Revises: 0003
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "language", server_default="en")


def downgrade() -> None:
    op.alter_column("users", "language", server_default="hi")