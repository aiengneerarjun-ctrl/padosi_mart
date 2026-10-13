"""notifications (har user ka inbox: customer / seller / delivery partner sabke liye ek hi table)

Revision ID: 0020
Revises: 0019
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),  # kaun si notification (text user ki bhasha me padhte waqt banta hai)
        sa.Column("params", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),  # text ke khali jagah: order_no, count...
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id")),  # app me seedha order khulne ke liye
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", sa.text("created_at DESC")])
    # "kitni padhi nahi" jaldi gin'ne ke liye
    op.create_index("ix_notifications_unread", "notifications", ["user_id"], postgresql_where=sa.text("read_at IS NULL"))


def downgrade() -> None:
    op.drop_table("notifications")