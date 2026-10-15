"""Bina payment ke ONLINE orders cancel karo (stock wapas) aur ruke hue refunds Cashfree ko bhejo.
Cron / scheduler me har 5 minute par chalao:
    docker compose exec -T backend python -m app.jobs.expire_unpaid
"""
import asyncio

from app.core.database import SessionLocal
from app.services import payment


async def main() -> None:
    async with SessionLocal() as db:
        expired = await payment.expire_unpaid(db)
    async with SessionLocal() as db:
        sent = await payment.process_pending_refunds(db)
    print(f"expired={expired} refunds_sent={sent}")


if __name__ == "__main__":
    asyncio.run(main())