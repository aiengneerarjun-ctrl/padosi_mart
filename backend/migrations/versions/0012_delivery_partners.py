"""delivery_partners (onboarding + KYC + admin approval + online/offline)

Revision ID: 0012
Revises: 0011
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "delivery_partners",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("vehicle_type", sa.String(10), nullable=False),
        sa.Column("vehicle_number", sa.String(12)),
        sa.Column("id_type", sa.String(10), nullable=False),
        sa.Column("id_photo_key", sa.String(255), nullable=False),
        sa.Column("licence_photo_key", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("status_reason", sa.String(500)),
        sa.Column("is_online", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(_in("status", ("PENDING", "ACTIVE", "REJECTED", "SUSPENDED")), name="ck_delivery_partners_status"),
        sa.CheckConstraint(_in("vehicle_type", ("BICYCLE", "BIKE", "SCOOTER")), name="ck_delivery_partners_vehicle_type"),
        sa.CheckConstraint(_in("id_type", ("AADHAAR", "PAN")), name="ck_delivery_partners_id_type"),
        # Gaadi (bike/scooter) ka number zaroori; cycle ka nahi hota
        sa.CheckConstraint(
            "vehicle_type = 'BICYCLE' OR vehicle_number IS NOT NULL", name="ck_delivery_partners_vehicle_number"
        ),
        # Database level rule: online sirf ACTIVE partner ho sakta hai
        sa.CheckConstraint("NOT is_online OR status = 'ACTIVE'", name="ck_delivery_partners_online_only_active"),
    )
    op.create_index("ix_delivery_partners_status", "delivery_partners", ["status"])
    # Aage assignment ke time "abhi online partners" jaldi chahiye honge
    op.create_index(
        "ix_delivery_partners_online", "delivery_partners", ["id"], postgresql_where=sa.text("is_online")
    )


def downgrade() -> None:
    # Note: jin users ko DELIVERY_PARTNER role mil chuka hai wo role downgrade me nahi hatta.
    op.drop_table("delivery_partners")