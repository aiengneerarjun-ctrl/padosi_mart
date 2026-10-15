from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_seller
from app.core.database import get_db
from app.models import Seller
from app.schemas.settlement import SettlementSummaryOut
from app.services import settlement as service

router = APIRouter(prefix="/seller/earnings", tags=["seller-earnings"])


@router.get("", response_model=SettlementSummaryOut)
async def my_earnings(seller: Seller = Depends(get_current_seller), db: AsyncSession = Depends(get_db)):
    """Meri kamai: kul bikri, platform ka commission, admin se mila hua paisa, abhi baaki kitna, aur haal ke orders / payouts."""
    return await service.my_summary(db, seller)