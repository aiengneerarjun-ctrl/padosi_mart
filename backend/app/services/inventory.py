import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import api_error
from app.models import User
from app.models.catalog import Inventory, InventoryTransaction, Product, ProductStatus, StockReason


async def adjust_stock(
    db: AsyncSession,
    product_id: uuid.UUID,
    change: int,
    reason: StockReason,
    actor: User | None = None,
    note: str | None = None,
) -> int:
    """Stock badalne ka EKLAUTA rasta. Order wale step me bhi yahi function use hoga.

    Ek hi SQL me "check + badlav" hota hai, isliye 2 log ek saath aakhri piece khareedein to
    sirf ek ko milta hai (overselling nahi). COMMIT caller karta hai.
    """
    result = await db.execute(
        update(Inventory)
        .where(Inventory.product_id == product_id, Inventory.quantity + change >= 0)
        .values(quantity=Inventory.quantity + change)
        .returning(Inventory.quantity)
        .execution_options(synchronize_session=False)
    )
    new_qty = result.scalar_one_or_none()
    if new_qty is None:
        raise api_error(409, "NOT_ENOUGH_STOCK", "Stock zero se neeche nahi jaa sakta.")

    db.add(
        InventoryTransaction(
            product_id=product_id,
            change=change,
            quantity_after=new_qty,
            reason=reason.value,
            note=note,
            actor_id=actor.id if actor else None,
        )
    )
    # Status apne aap: stock 0 -> OUT_OF_STOCK, wapas aaya -> ACTIVE (INACTIVE/PENDING ko nahi chhedte)
    if new_qty == 0:
        await db.execute(
            update(Product)
            .where(Product.id == product_id, Product.status == ProductStatus.ACTIVE)
            .values(status=ProductStatus.OUT_OF_STOCK)
            .execution_options(synchronize_session=False)
        )
    else:
        await db.execute(
            update(Product)
            .where(Product.id == product_id, Product.status == ProductStatus.OUT_OF_STOCK)
            .values(status=ProductStatus.ACTIVE)
            .execution_options(synchronize_session=False)
        )
    return new_qty


async def stock_history(db: AsyncSession, product_id: uuid.UUID, limit: int, offset: int) -> list[InventoryTransaction]:
    q = (
        select(InventoryTransaction)
        .where(InventoryTransaction.product_id == product_id)
        .order_by(InventoryTransaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(await db.scalars(q))