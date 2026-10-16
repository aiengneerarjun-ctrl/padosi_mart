"""reviews (dukaan + delivery partner) aur rating_summaries

Revision ID: 0026
Revises: 0025
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),  # review dene wala customer
        sa.Column("target_type", sa.String(10), nullable=False),  # STORE / PARTNER
        sa.Column("store_id", UUID, sa.ForeignKey("stores.id")),
        sa.Column("seller_id", UUID, sa.ForeignKey("sellers.id")),  # STORE review me: us dukaan ka seller (seller ki list ke liye)
        sa.Column("partner_id", UUID, sa.ForeignKey("delivery_partners.id")),
        sa.Column("rating", sa.SmallInteger, nullable=False),
        sa.Column("comment", sa.String(500)),
        sa.Column("status", sa.String(10), nullable=False, server_default="VISIBLE"),  # VISIBLE / HIDDEN (admin chhupa sakta hai)
        sa.Column("hidden_reason", sa.String(300)),
        sa.Column("hidden_by", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("hidden_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating"),
        sa.CheckConstraint("status IN ('VISIBLE','HIDDEN')", name="ck_reviews_status"),
        sa.CheckConstraint(
            "(target_type = 'STORE' AND store_id IS NOT NULL AND seller_id IS NOT NULL AND partner_id IS NULL) OR "
            "(target_type = 'PARTNER' AND partner_id IS NOT NULL AND store_id IS NULL AND seller_id IS NULL)",
            name="ck_reviews_target",
        ),
    )
    # Ek order me ek dukaan ka ek hi review, aur ek order me delivery partner ka ek hi review
    op.create_index("uq_reviews_order_store", "reviews", ["order_id", "store_id"], unique=True, postgresql_where=sa.text("target_type = 'STORE'"))
    op.create_index("uq_reviews_order_partner", "reviews", ["order_id"], unique=True, postgresql_where=sa.text("target_type = 'PARTNER'"))
    op.create_index("ix_reviews_store_created", "reviews", ["store_id", sa.text("created_at DESC")], postgresql_where=sa.text("target_type = 'STORE'"))
    op.create_index("ix_reviews_seller_created", "reviews", ["seller_id", sa.text("created_at DESC")], postgresql_where=sa.text("target_type = 'STORE'"))
    op.create_index("ix_reviews_partner_created", "reviews", ["partner_id", sa.text("created_at DESC")], postgresql_where=sa.text("target_type = 'PARTNER'"))
    op.create_index("ix_reviews_user_created", "reviews", ["user_id", sa.text("created_at DESC")])
    op.create_index("ix_reviews_admin", "reviews", ["status", sa.text("created_at DESC")])

    # Har dukaan / partner ke star ki ginti (sirf VISIBLE reviews). Average isse nikalta hai, har baar sab reviews nahi gintne padte.
    op.create_table(
        "rating_summaries",
        sa.Column("target_type", sa.String(10), nullable=False),
        sa.Column("target_id", UUID, nullable=False),
        *[sa.Column(f"star{i}", sa.Integer, nullable=False, server_default="0") for i in range(1, 6)],
        sa.PrimaryKeyConstraint("target_type", "target_id"),
        sa.CheckConstraint("target_type IN ('STORE','PARTNER')", name="ck_rating_summaries_type"),
        sa.CheckConstraint("star1 >= 0 AND star2 >= 0 AND star3 >= 0 AND star4 >= 0 AND star5 >= 0", name="ck_rating_summaries_nonneg"),
    )


def downgrade() -> None:
    op.drop_table("rating_summaries")
    op.drop_table("reviews")
