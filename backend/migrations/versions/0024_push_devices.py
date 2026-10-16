"""push notification: device_tokens (kis phone par push bhejna hai) + notifications.pushed_at

Revision ID: 0024
Revises: 0023
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "device_tokens",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.Text, nullable=False),  # FCM token. Ek token ek hi phone ka, isliye unique
        sa.Column("platform", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("token", name="uq_device_tokens_token"),
        sa.CheckConstraint("platform IN ('android','ios','web')", name="ck_device_tokens_platform"),
    )
    op.create_index("ix_device_tokens_user", "device_tokens", ["user_id"])

    # pushed_at khali = push abhi bheji nahi gayi. Purani notifications par push nahi bhejni, isliye unhe "bheji hui" maan lo.
    op.add_column("notifications", sa.Column("pushed_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE notifications SET pushed_at = now()")
    op.create_index("ix_notifications_unpushed", "notifications", ["created_at"], postgresql_where=sa.text("pushed_at IS NULL"))


def downgrade() -> None:
    op.drop_index("ix_notifications_unpushed", table_name="notifications")
    op.drop_column("notifications", "pushed_at")
    op.drop_table("device_tokens")
