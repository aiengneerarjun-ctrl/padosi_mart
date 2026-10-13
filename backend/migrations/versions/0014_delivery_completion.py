"""deliveries: delivered_at, cod_collected, OTP ki galat koshish ginti + lock

Revision ID: 0014
Revises: 0013
"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deliveries", sa.Column("delivered_at", sa.DateTime(timezone=True)))
    op.add_column("deliveries", sa.Column("cod_collected", sa.Numeric(10, 2)))
    op.add_column("deliveries", sa.Column("otp_attempts", sa.SmallInteger, nullable=False, server_default="0"))
    op.add_column("deliveries", sa.Column("otp_locked_until", sa.DateTime(timezone=True)))
    op.create_check_constraint("ck_deliveries_cod_collected", "deliveries", "cod_collected IS NULL OR cod_collected >= 0")
    op.create_check_constraint("ck_deliveries_otp_attempts", "deliveries", "otp_attempts >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_deliveries_otp_attempts", "deliveries")
    op.drop_constraint("ck_deliveries_cod_collected", "deliveries")
    op.drop_column("deliveries", "otp_locked_until")
    op.drop_column("deliveries", "otp_attempts")
    op.drop_column("deliveries", "cod_collected")
    op.drop_column("deliveries", "delivered_at")