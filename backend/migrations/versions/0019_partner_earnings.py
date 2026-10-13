"""partner ki kamai: deliveries.earning, delivery_pay_settings (rate), partner_payouts (admin ne paisa diya)

Revision ID: 0019
Revises: 0018
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)

# SHURUAATI RATE (placeholder). Abhi dono 0 hain: admin PATCH /admin/delivery-earnings/rates se tay karega.
# Chaho to migration chalane se pehle yahan ke do number badal do.
NORMAL_RATE = "0.00"  # customer ne delivery fee diya
FREE_DELIVERY_RATE = "0.00"  # customer ka delivery fee 0 (Rs 799 se upar wala order)


def upgrade() -> None:
    # 1) Har delivery par partner ki kamai (delivery poori hone par likhi jaati hai; purani deliveries par NULL = 0 maani jaati hai)
    op.add_column("deliveries", sa.Column("earning", sa.Numeric(10, 2)))
    op.create_check_constraint("ck_deliveries_earning", "deliveries", "earning IS NULL OR earning >= 0")

    # 2) Rate: sirf ek row
    op.create_table(
        "delivery_pay_settings",
        sa.Column("id", sa.SmallInteger, primary_key=True),
        sa.Column("normal_rate", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("free_delivery_rate", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.CheckConstraint("id = 1", name="ck_delivery_pay_settings_single"),
        sa.CheckConstraint("normal_rate >= 0 AND free_delivery_rate >= 0", name="ck_delivery_pay_settings_rates"),
    )
    op.execute(f"INSERT INTO delivery_pay_settings (id, normal_rate, free_delivery_rate) VALUES (1, {NORMAL_RATE}, {FREE_DELIVERY_RATE})")

    # 3) Payout bahi-khaata (cod_deposits jaisa, badalta nahi)
    op.create_table(
        "partner_payouts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("partner_id", UUID, sa.ForeignKey("delivery_partners.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("recorded_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount <> 0", name="ck_partner_payouts_amount"),
        sa.CheckConstraint("amount > 0 OR (note IS NOT NULL AND length(btrim(note)) > 0)", name="ck_partner_payouts_note"),
    )
    op.create_index("ix_partner_payouts_partner", "partner_payouts", ["partner_id", "created_at"])
    op.execute(
        "CREATE TRIGGER trg_partner_payouts_immutable BEFORE UPDATE OR DELETE ON partner_payouts "
        "FOR EACH ROW EXECUTE FUNCTION block_update_delete()"
    )


def downgrade() -> None:
    op.drop_table("partner_payouts")
    op.drop_table("delivery_pay_settings")
    op.drop_constraint("ck_deliveries_earning", "deliveries")
    op.drop_column("deliveries", "earning")