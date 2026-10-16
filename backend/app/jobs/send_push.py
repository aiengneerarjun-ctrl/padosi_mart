"""Nayi notifications ko phone par push bhejo (Firebase FCM).
Hamesha chalne wala:   python -m app.jobs.send_push --loop     (docker compose me `pusher` service yahi chalati hai)
Ek baar chalana:        docker compose exec -T backend python -m app.jobs.send_push
"""
import asyncio
import logging
import sys

from app.core.config import settings
from app.core.database import SessionLocal
from app.services import push

INTERVAL_SECONDS = 3
logger = logging.getLogger("padosi.push")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    loop = "--loop" in sys.argv
    if not settings.push_enabled:
        print("FCM_SERVICE_ACCOUNT_FILE set nahi hai ya file nahi mili: push band hai.")
        while loop:  # compose me crash-loop na ho, isliye chup-chap ruko
            await asyncio.sleep(3600)
        return

    client = push.FcmClient(settings.fcm_service_account_file)
    try:
        while True:
            claimed = 0
            try:
                async with SessionLocal() as db:
                    claimed, sent, removed = await push.push_pending(db, client)
                if claimed:
                    logger.info("push: notifications=%s sent=%s bad_tokens_removed=%s", claimed, sent, removed)
            except Exception:
                logger.exception("push job me gadbad")  # job band nahi hoti, agli baar phir koshish
            if not loop:
                return
            if claimed < push.BATCH_SIZE:  # bacha hua kaam ho to turant agla batch
                await asyncio.sleep(INTERVAL_SECONDS)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
