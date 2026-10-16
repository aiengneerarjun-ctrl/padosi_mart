"""support tickets: support_tickets + support_messages (customer / seller / delivery partner -> Super Admin)

Revision ID: 0027
Revises: 0026
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.execute("CREATE SEQUENCE ticket_no_seq START 1001")
    op.create_table(
        "support_tickets",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("ticket_no", sa.BigInteger, nullable=False, unique=True, server_default=sa.text("nextval('ticket_no_seq')")),  # TK1001
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("raised_as", sa.String(20), nullable=False),  # CUSTOMER / SELLER / DELIVERY_PARTNER
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id")),  # kisi order ke baare me ho to
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(120), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="OPEN"),  # OPEN = support ke jawab ka intezaar, ANSWERED = user ke, CLOSED
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("raised_as IN ('CUSTOMER','SELLER','DELIVERY_PARTNER')", name="ck_support_tickets_raised_as"),
        sa.CheckConstraint("category IN ('ORDER_ISSUE','PAYMENT','DELIVERY','ACCOUNT','OTHER')", name="ck_support_tickets_category"),
        sa.CheckConstraint("status IN ('OPEN','ANSWERED','CLOSED')", name="ck_support_tickets_status"),
        sa.CheckConstraint("(status = 'CLOSED') = (closed_at IS NOT NULL)", name="ck_support_tickets_closed_at"),
    )
    op.create_index("ix_support_tickets_user", "support_tickets", ["user_id", sa.text("created_at DESC")])
    op.create_index("ix_support_tickets_queue", "support_tickets", ["status", "last_message_at"])
    op.create_index("ix_support_tickets_order", "support_tickets", ["order_id"], postgresql_where=sa.text("order_id IS NOT NULL"))

    op.create_table(
        "support_messages",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("ticket_id", UUID, sa.ForeignKey("support_tickets.id"), nullable=False),
        sa.Column("author_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("author_type", sa.String(5), nullable=False),  # USER / ADMIN
        sa.Column("body", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("author_type IN ('USER','ADMIN')", name="ck_support_messages_author_type"),
        sa.CheckConstraint("char_length(btrim(body)) >= 1", name="ck_support_messages_body"),
    )
    op.create_index("ix_support_messages_ticket", "support_messages", ["ticket_id", "created_at"])
    # Bheja hua sandesha badalta / hatta nahi (block_update_delete() migration 0010 me bana tha)
    op.execute(
        "CREATE TRIGGER trg_support_messages_immutable BEFORE UPDATE OR DELETE ON support_messages "
        "FOR EACH ROW EXECUTE FUNCTION block_update_delete()"
    )


def downgrade() -> None:
    op.drop_table("support_messages")
    op.drop_table("support_tickets")
    op.execute("DROP SEQUENCE ticket_no_seq")
