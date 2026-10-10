import asyncio
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.core.errors import api_error
from app.models import Seller
from app.models.catalog import Product, ProductImage, ProductStatus
from app.services.image_processing import ImageError, process_image
from app.services.product import _require_active, get_owned_product, load_product

MAX_IMAGES = 8  # PDF: general max 8


def _send_for_review(product: Product) -> None:
    """Primary photo badli to admin ko dobara dekhna padega (warna approve ke baad photo badal kar dhokha ho sakta hai)."""
    if product.status != ProductStatus.PENDING_APPROVAL:
        product.status = ProductStatus.PENDING_APPROVAL
        product.status_reason = None


async def _lock_and_load_images(db: AsyncSession, product_id: uuid.UUID) -> list[ProductImage]:
    """Product row lock: ek product par 2 upload/delete ek saath chalein to line se chalte hain."""
    await db.execute(select(Product.id).where(Product.id == product_id).with_for_update())
    q = select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.position)
    return list(await db.scalars(q.execution_options(populate_existing=True)))


async def add_image(db: AsyncSession, seller: Seller, product_id: uuid.UUID, data: bytes) -> Product:
    _require_active(seller)
    product = await get_owned_product(db, seller, product_id)

    try:  # CPU ka kaam alag thread me, taaki baaki requests na ruken
        processed = await asyncio.to_thread(process_image, data)
    except ImageError as exc:
        raise api_error(exc.status, exc.code, exc.message)

    images = await _lock_and_load_images(db, product.id)
    if len(images) >= MAX_IMAGES:
        raise api_error(409, "IMAGE_LIMIT_REACHED", "Ek product me 8 se zyada photo nahi lag sakti.")
    digest = hashlib.sha256(data).hexdigest()
    if any(i.sha256 == digest for i in images):
        raise api_error(409, "IMAGE_DUPLICATE", "Ye photo is product me pehle se hai.")

    image_id = uuid.uuid4()
    prefix = f"products/{product.id}/{image_id}"
    uploaded: list[str] = []
    try:
        for name, blob in processed.variants.items():
            key = f"{prefix}/{name}.webp"
            await storage.put_object(key, blob, "image/webp")
            uploaded.append(key)
    except storage.StorageError:
        await storage.delete_objects(uploaded)
        await db.rollback()
        raise api_error(503, "STORAGE_UNAVAILABLE", "Photo storage abhi available nahi hai, dobara try karo.")

    db.add(
        ProductImage(
            id=image_id, product_id=product.id, position=len(images), key_prefix=prefix, sha256=digest,
            width=processed.width, height=processed.height, size_bytes=len(data),
        )
    )
    if not images or product.status == ProductStatus.REJECTED:  # pehli (primary) photo, ya rejected product ka sudhaar
        _send_for_review(product)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        await storage.delete_objects(uploaded)  # DB me nahi ghusi to storage me bhi nahi rakhni
        raise
    return await load_product(db, product.id)


async def reorder_images(db: AsyncSession, seller: Seller, product_id: uuid.UUID, ordered_ids: list[uuid.UUID]) -> Product:
    _require_active(seller)
    product = await get_owned_product(db, seller, product_id)
    images = await _lock_and_load_images(db, product.id)
    if sorted(ordered_ids) != sorted(i.id for i in images):
        raise api_error(422, "IMAGE_ORDER_MISMATCH", "List me product ki har photo ek baar honi chahiye.")
    old_primary = images[0].id if images else None
    by_id = {i.id: i for i in images}
    for position, image_id in enumerate(ordered_ids):
        by_id[image_id].position = position
    if ordered_ids[0] != old_primary or product.status == ProductStatus.REJECTED:
        _send_for_review(product)
    await db.commit()
    return await load_product(db, product.id)


async def delete_image(db: AsyncSession, seller: Seller, product_id: uuid.UUID, image_id: uuid.UUID) -> Product:
    _require_active(seller)
    product = await get_owned_product(db, seller, product_id)
    images = await _lock_and_load_images(db, product.id)
    target = next((i for i in images if i.id == image_id), None)
    if target is None:
        raise api_error(404, "IMAGE_NOT_FOUND", "Photo nahi mili.")
    if len(images) == 1 and product.status in (ProductStatus.ACTIVE, ProductStatus.OUT_OF_STOCK):
        # Live product bina photo ke nahi rahega: pehle nayi photo daalo, phir purani hatao
        raise api_error(409, "PRODUCT_NEEDS_IMAGE", "Product me kam se kam ek photo zaroori hai.")

    was_primary = target.position == 0
    keys = [f"{target.key_prefix}/{name}.webp" for name in ("thumb", "medium", "large")]
    await db.delete(target)
    await db.flush()
    for position, image in enumerate(i for i in images if i.id != target.id):  # khali jagah bharo: 0,1,2...
        image.position = position
    if was_primary or product.status == ProductStatus.REJECTED:
        _send_for_review(product)
    await db.commit()
    await storage.delete_objects(keys)  # DB commit ke baad; fail ho to bas extra file bachti hai
    return await load_product(db, product.id)