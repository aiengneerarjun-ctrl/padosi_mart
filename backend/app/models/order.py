import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Identity, Index, Integer, Numeric, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class OrderStatus(StrEnum):
    PLACED = "PLACED"
    CONFIRMED = "CONFIRMED"
    SELLER_ACCEPTED = "SELLER_ACCEPTED"
    PREPARING = "PREPARING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    DELIVERY_ASSIGNED = "DELIVERY_ASSIGNED"
    PICKED_UP = "PICKED_UP"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"
    RETURN_REQUESTED = "RETURN_REQUESTED"
    FAILED_DELIVERY = "FAILED_DELIVERY"


class StoreOrderStatus(StrEnum):
    """Ek dukaan ke hisse ka status (seller isi ko aage badhata hai)."""

    PLACED = "PLACED"
    SELLER_ACCEPTED = "SELLER_ACCEPTED"
    PREPARING = "PREPARING"
    READY_FOR_PICKUP = "READY_FOR_PICKUP"
    PICKED_UP = "PICKED_UP"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class RemovalReason(StrEnum):
    """Seller ne item kyun hataya (customer ko apni bhasha me dikhta hai)."""

    OUT_OF_STOCK = "OUT_OF_STOCK"
    QUALITY_ISSUE = "QUALITY_ISSUE"
    SHOP_CLOSING = "SHOP_CLOSING"
    OTHER = "OTHER"

class PaymentMethod(StrEnum):
    COD = "COD"
    ONLINE = "ONLINE"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"
    NOT_REQUIRED = "NOT_REQUIRED"  # jaise cancelled COD order


def _in(enum_cls) -> str:
    return ", ".join(f"'{m.value}'" for m in enum_cls)


class Order(Base):
    """Customer ka ek order (ek checkout = ek order). Isme alag-alag dukaanon ke hisse StoreOrder me hote hain.

    Address yahin copy (snapshot) hota hai, taaki customer baad me address badle to purana order na badle.
    """

    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_idempotency"),
        CheckConstraint(f"status IN ({_in(OrderStatus)})", name="ck_orders_status"),
        CheckConstraint(f"payment_method IN ({_in(PaymentMethod)})", name="ck_orders_payment_method"),
        CheckConstraint(f"payment_status IN ({_in(PaymentStatus)})", name="ck_orders_payment_status"),
        CheckConstraint(
            "items_subtotal >= 0 AND delivery_fee >= 0 AND discount_amount >= 0 AND total = items_subtotal + delivery_fee - discount_amount",
            name="ck_orders_money",
        ),
        Index("ix_orders_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_no: Mapped[int] = mapped_column(BigInteger, unique=True, server_default=text("nextval('order_no_seq')"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.PLACED, server_default="PLACED", index=True)
    payment_method: Mapped[str] = mapped_column(String(10))
    payment_status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.PENDING, server_default="PENDING")
    # Address snapshot
    receiver_name: Mapped[str] = mapped_column(String(100))
    receiver_phone: Mapped[str] = mapped_column(String(15))
    address_line: Mapped[str] = mapped_column(String(300))
    landmark: Mapped[str | None] = mapped_column(String(150))
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    # Paisa (Decimal, kabhi float nahi)
    items_subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Order jis haal me bana tha. Seller ne kuch items hataye to items_subtotal/total ghatte hain, ye dono nahi badalte.
    original_items_subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    original_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Coupon: discount_amount seller ke items hatne par ghat sakta hai (badhta nahi). original_discount order bante waqt ka.
    coupon_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("coupons.id"))
    coupon_code: Mapped[str | None] = mapped_column(String(20))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), server_default="0")
    original_discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), server_default="0")
    note: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    store_orders: Mapped[list["StoreOrder"]] = relationship(lazy="selectin", order_by="StoreOrder.created_at")
    removals: Mapped[list["OrderItemRemoval"]] = relationship(lazy="selectin", order_by="OrderItemRemoval.created_at")

    @property
    def order_number(self) -> str:
        return f"PD{self.order_no}"


class StoreOrder(Base):
    """Order ka ek dukaan wala hissa. Seller ko sirf yahi dikhega, aur seller ka paisa isi se banega.
    Delivery boy ke liye: is dukaan se ye items uthane hain (store_name/store_address yahin snapshot hain).
    """

    __tablename__ = "store_orders"
    __table_args__ = (
        UniqueConstraint("order_id", "store_id", name="uq_store_orders_order_store"),
        CheckConstraint(f"status IN ({_in(StoreOrderStatus)})", name="ck_store_orders_status"),
        CheckConstraint("items_subtotal >= 0", name="ck_store_orders_subtotal"),
        CheckConstraint("seller_discount >= 0 AND seller_discount <= items_subtotal", name="ck_store_orders_seller_discount"),
        CheckConstraint(
            "(commission_rate IS NULL AND commission_amount IS NULL) OR "
            "(commission_rate BETWEEN 0 AND 100 AND commission_amount >= 0 AND commission_amount <= items_subtotal)",
            name="ck_store_orders_commission",
        ),
        Index("ix_store_orders_store_status", "store_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id"))
    seller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sellers.id"))
    status: Mapped[str] = mapped_column(String(20), default=StoreOrderStatus.PLACED, server_default="PLACED")
    store_name: Mapped[str] = mapped_column(String(150))
    store_address: Mapped[str] = mapped_column(String(300))
    store_latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    store_longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    items_subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # is dukaan ke saaman ka total
    seller_discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), server_default="0")  # seller-funded coupon me seller ka hissa (payout se kat'ta hai)
    commission_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # percent; delivery poori hone par fix (None = abhi nahi)
    commission_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # platform ka hissa; seller ko milega items_subtotal - ye
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items: Mapped[list["OrderItem"]] = relationship(lazy="selectin", order_by="OrderItem.created_at")


class OrderItem(Base):
    """Order ki ek line. Naam/price yahin copy hoti hai: baad me product badle to purana order nahi badlega. Badli nahi jaati."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0 AND unit_price >= 0 AND line_total = unit_price * quantity", name="ck_order_items_money"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), index=True)
    store_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store_orders.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    name_hi: Mapped[str | None] = mapped_column(String(200))
    name_bho: Mapped[str | None] = mapped_column(String(200))
    selling_unit: Mapped[str] = mapped_column(String(50))
    mrp: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int] = mapped_column(Integer)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderStatusHistory(Base):
    """Har status badlav ka record. Sirf judta hai, badla/hataya nahi jaata (database trigger bhi rokta hai)."""

    __tablename__ = "order_status_history"
    __table_args__ = (Index("ix_order_status_history_order", "order_id", "seq"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)  # likhne ka sahi kram (created_at ek hi transaction me same hota hai)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    store_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("store_orders.id"))  # None = poore order ka badlav
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_role: Mapped[str] = mapped_column(String(20))  # CUSTOMER / SELLER / DELIVERY_PARTNER / SUPER_ADMIN / SYSTEM
    note: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class OrderItemRemoval(Base):
    """Seller ne order ka ek item hataya ("saaman nahi hai"). order_items ki line jaisi thi waisi hi rehti hai,
    hatane ka record yahan judta hai. Badla/hataya nahi jaata (database trigger bhi rokta hai)."""

    __tablename__ = "order_item_removals"
    __table_args__ = (
        CheckConstraint(f"reason_code IN ({_in(RemovalReason)})", name="ck_order_item_removals_reason"),
        CheckConstraint(
            "(kept_quantity IS NULL AND kept_item_id IS NULL) OR (kept_quantity > 0 AND kept_item_id IS NOT NULL)",
            name="ck_order_item_removals_kept",
        ),
        Index("ix_order_item_removals_order", "order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"))
    store_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("store_orders.id"))
    order_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("order_items.id"), unique=True)  # ek item ek hi baar hatega
    reason_code: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(200))  # seller ka likha karan (customer ko dikhta hai)
    line_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # kitne ka saaman hata (aadha saaman me sirf hata hua hissa)
    kept_quantity: Mapped[int | None] = mapped_column(Integer)  # aadha saaman: dukaan ne itne piece de diye (None = poora item hata)
    kept_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("order_items.id"))  # bache hue piece ki nayi line
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())