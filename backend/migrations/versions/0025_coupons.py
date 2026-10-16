"""coupons: coupons, coupon_redemptions + orders / store_orders me discount ke columns

Revision ID: 0025
Revises: 0024
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "coupons",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("title_hi", sa.String(120)),
        sa.Column("title_bho", sa.String(120)),
        sa.Column("discount_type", sa.String(15), nullable=False),  # FLAT / PERCENT / FREE_DELIVERY
        sa.Column("value", sa.Numeric(10, 2), nullable=False, server_default="0"),  # FLAT: rupaye, PERCENT: percent
        sa.Column("max_discount", sa.Numeric(10, 2)),  # sirf PERCENT: zyada se zyada itna discount
        sa.Column("min_order_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),  # saaman ke total par (delivery chhodkar)
        sa.Column("funded_by", sa.String(10), nullable=False, server_default="PLATFORM"),  # discount ka paisa kaun dega
        sa.Column("seller_id", UUID, sa.ForeignKey("sellers.id")),  # khali = sab dukaanon par; bhara = sirf us seller ke saaman par
        sa.Column("first_order_only", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.true()),  # app ki list me dikhe ya sirf code se
        sa.Column("per_user_limit", sa.Integer, nullable=False, server_default="1"),
        sa.Column("total_limit", sa.Integer),  # khali = koi limit nahi
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_coupons_code"),
        sa.CheckConstraint("code = upper(code) AND char_length(code) >= 3", name="ck_coupons_code"),
        sa.CheckConstraint("discount_type IN ('FLAT','PERCENT','FREE_DELIVERY')", name="ck_coupons_type"),
        sa.CheckConstraint("funded_by IN ('PLATFORM','SELLER')", name="ck_coupons_funded_by"),
        sa.CheckConstraint("funded_by = 'PLATFORM' OR seller_id IS NOT NULL", name="ck_coupons_seller_funded"),
        sa.CheckConstraint("discount_type <> 'FREE_DELIVERY' OR funded_by = 'PLATFORM'", name="ck_coupons_free_delivery_platform"),
        sa.CheckConstraint(
            "(discount_type = 'FLAT' AND value > 0) OR (discount_type = 'PERCENT' AND value > 0 AND value <= 100) "
            "OR (discount_type = 'FREE_DELIVERY' AND value = 0)",
            name="ck_coupons_value",
        ),
        sa.CheckConstraint("max_discount IS NULL OR (discount_type = 'PERCENT' AND max_discount > 0)", name="ck_coupons_max_discount"),
        sa.CheckConstraint("min_order_amount >= 0", name="ck_coupons_min_order"),
        sa.CheckConstraint("per_user_limit >= 1 AND (total_limit IS NULL OR total_limit >= 1)", name="ck_coupons_limits"),
        sa.CheckConstraint("expires_at > starts_at", name="ck_coupons_dates"),
    )

    # Coupon ka istemal (har order par ek). Order cancel ho to released_at lagta hai aur coupon dobara use ho sakta hai.
    op.create_table(
        "coupon_redemptions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("coupon_id", UUID, sa.ForeignKey("coupons.id"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("order_id", name="uq_coupon_redemptions_order"),
        sa.CheckConstraint("discount_amount > 0", name="ck_coupon_redemptions_amount"),
    )
    op.create_index("ix_coupon_redemptions_coupon_user", "coupon_redemptions", ["coupon_id", "user_id"], postgresql_where=sa.text("released_at IS NULL"))

    # orders: discount. total = items_subtotal + delivery_fee - discount_amount
    op.add_column("orders", sa.Column("coupon_id", UUID, sa.ForeignKey("coupons.id")))
    op.add_column("orders", sa.Column("coupon_code", sa.String(20)))
    op.add_column("orders", sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("original_discount", sa.Numeric(10, 2), nullable=False, server_default="0"))  # order bante waqt ka discount
    op.drop_constraint("ck_orders_money", "orders", type_="check")
    op.create_check_constraint(
        "ck_orders_money", "orders",
        "items_subtotal >= 0 AND delivery_fee >= 0 AND discount_amount >= 0 AND total = items_subtotal + delivery_fee - discount_amount",
    )

    # store_orders: is dukaan ke seller ke hisse ka discount (seller-funded coupon par). Seller ke payout se kat'ta hai.
    op.add_column("store_orders", sa.Column("seller_discount", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.create_check_constraint("ck_store_orders_seller_discount", "store_orders", "seller_discount >= 0 AND seller_discount <= items_subtotal")


def downgrade() -> None:
    op.drop_constraint("ck_store_orders_seller_discount", "store_orders", type_="check")
    op.drop_column("store_orders", "seller_discount")
    op.drop_constraint("ck_orders_money", "orders", type_="check")
    op.create_check_constraint("ck_orders_money", "orders", "items_subtotal >= 0 AND delivery_fee >= 0 AND total = items_subtotal + delivery_fee")
    op.drop_column("orders", "original_discount")
    op.drop_column("orders", "discount_amount")
    op.drop_column("orders", "coupon_code")
    op.drop_column("orders", "coupon_id")
    op.drop_table("coupon_redemptions")
    op.drop_table("coupons")
