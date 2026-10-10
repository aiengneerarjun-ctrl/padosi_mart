from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import engine
from app.core.redis import redis_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Check karta hai ki API, database aur redis teeno chal rahe hain ya nahi."""
    checks = {"api": "ok", "database": "down", "redis": "down"}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        pass
    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception:
        pass
    ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}
