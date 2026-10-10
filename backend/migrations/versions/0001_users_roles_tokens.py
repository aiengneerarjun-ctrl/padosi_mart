"""users, roles, user_roles, refresh_tokens

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

# Sirf ek SUPER_ADMIN (id=1) hota hai; ADMIN / SUB_ADMIN ka concept nahi hai.
ROLES = [
    {"id": 1, "name": "SUPER_ADMIN"},
    {"id": 2, "name": "CUSTOMER"},
    {"id": 3, "name": "SELLER"},
    {"id": 4, "name": "RESTAURANT"},
    {"id": 5, "name": "DELIVERY_PARTNER"},
]


def upgrade() -> None:
    roles = op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone", sa.String(15), nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column("email", sa.String(255)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)
    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), primary_key=True),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.bulk_insert(roles, ROLES)
    op.execute("SELECT setval(pg_get_serial_sequence('roles', 'id'), 100)")
    # Database level rule: role_id=1 (SUPER_ADMIN) sirf ek user ko mil sakta hai
    op.create_index("uq_single_super_admin", "user_roles", ["role_id"], unique=True, postgresql_where=sa.text("role_id = 1"))


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")