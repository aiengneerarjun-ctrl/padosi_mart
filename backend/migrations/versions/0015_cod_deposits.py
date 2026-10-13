"""cod_deposits (COD cash ka bahi-khaata: partner ne admin ko cash jama kiya)

Revision ID: 0015
Revises: 0014
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "cod_deposits",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("partner_id", UUID, sa.ForeignKey("delivery_partners.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("recorded_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount <> 0", name="ck_cod_deposits_amount"),
        # Sudhaar (negative) bina wajah ke nahi
        sa.CheckConstraint("amount > 0 OR (note IS NOT NULL AND length(btrim(note)) > 0)", name="ck_cod_deposits_note"),
    )
    op.create_index("ix_cod_deposits_partner", "cod_deposits", ["partner_id", "created_at"])
    # Bahi-khaata kabhi badla ya hataya nahi ja sakta (function block_update_delete migration 0010 se)
    op.execute(
        "CREATE TRIGGER trg_cod_deposits_immutable BEFORE UPDATE OR DELETE ON cod_deposits "
        "FOR EACH ROW EXECUTE FUNCTION block_update_delete()"
    )


def downgrade() -> None:
    op.drop_table("cod_deposits")