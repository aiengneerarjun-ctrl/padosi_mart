import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.i18n import localized
from app.schemas.catalog import BrandOut, CategoryOut
from app.services import catalog as catalog_service

# Public: login ke bina bhi dikhta hai (app khulte hi categories chahiye)
router = APIRouter(tags=["catalog"])


@router.get("/categories", response_model=list[CategoryOut])
async def categories(request: Request, parent_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db)):
    """Naam Accept-Language ki bhasha me aata hai (en / hi / bho)."""
    rows = await catalog_service.list_categories(db, only_active=True, parent_id=parent_id)
    lang = request.state.lang
    return [CategoryOut(id=c.id, parent_id=c.parent_id, name=localized(c, lang), sort_order=c.sort_order) for c in rows]


@router.get("/brands", response_model=list[BrandOut])
async def brands(db: AsyncSession = Depends(get_db)):
    return await catalog_service.list_brands(db, only_active=True)