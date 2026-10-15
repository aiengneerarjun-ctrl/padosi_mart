"""seller ka hisaab: store_orders.commission_*, settlement_settings (rate), seller_payouts (admin ne seller ko paisa diya)

Revision ID: 0022
Revises: 0021
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)

# SHURUAATI COMMISSION (placeholder, percent). Abhi dono 0 hain: admin PATCH /admin/seller-settlements/rates se tay karega.
# Chaho to migration chalane se pehle yahan ke do number badal do.
KIRANA_RATE = "0.00"
RESTAURANT_RATE = "0.00"


def upgrade() -> None:
    # 1) Har dukaan-hisse par commission (delivery poori hone par likhi jaati hai; NULL = abhi deliver nahi hua / hisaab me nahi)
    op.add_column("store_orders", sa.Column("commission_rate", sa.Numeric(5, 2)))
    op.add_column("store_orders", sa.Column("commission_amount", sa.Numeric(10, 2)))
    op.create_check_constraint(
        "ck_store_orders_commission", "store_orders",
        "(commission_rate IS NULL AND commission_amount IS NULL) OR "
        "(commission_rate BETWEEN 0 AND 100 AND commission_amount >= 0 AND commission_amount <= items_subtotal)",
    )

    # 2) Rate: sirf ek row (dukaan ke type ke hisaab se)
    op.create_table(
        "settlement_settings",
        sa.Column("id", sa.SmallInteger, primary_key=True),
        sa.Column("kirana_rate", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("restaurant_rate", sa.Numeric(5, 2), nullable=False, server_default="0.00"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.CheckConstraint("id = 1", name="ck_settlement_settings_single"),
        sa.CheckConstraint(
            "kirana_rate BETWEEN 0 AND 100 AND restaurant_rate BETWEEN 0 AND 100", name="ck_settlement_settings_rates"
        ),
    )
    op.execute(f"INSERT INTO settlement_settings (id, kirana_rate, restaurant_rate) VALUES (1, {KIRANA_RATE}, {RESTAURANT_RATE})")

    # 3) Seller payout bahi-khaata (partner_payouts jaisa, badalta nahi)
    op.create_table(
        "seller_payouts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("seller_id", UUID, sa.ForeignKey("sellers.id"), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("note", sa.String(300)),
        sa.Column("recorded_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount <> 0", name="ck_seller_payouts_amount"),
        sa.CheckConstraint("amount > 0 OR (note IS NOT NULL AND length(btrim(note)) > 0)", name="ck_seller_payouts_note"),
    )
    op.create_index("ix_seller_payouts_seller", "seller_payouts", ["seller_id", "created_at"])
    op.execute(
        "CREATE TRIGGER trg_seller_payouts_immutable BEFORE UPDATE OR DELETE ON seller_payouts "
        "FOR EACH ROW EXECUTE FUNCTION block_update_delete()"
    )


def downgrade() -> None:
    op.drop_table("seller_payouts")
    op.drop_table("settlement_settings")
    op.drop_constraint("ck_store_orders_commission", "store_orders")
    op.drop_column("store_orders", "commission_amount")
    op.drop_column("store_orders", "commission_rate")