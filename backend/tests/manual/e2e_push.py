"""Push (FCM) ka real-PostgreSQL test. FCM ko nakli server se badla hai. Naye / khali database par chalao:
    docker compose exec backend python -m tests.manual.e2e_push
"""
import asyncio

import httpx
from sqlalchemy import func, select, text

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models import DeviceToken, Notification
from app.services import push
from app.services.auth import get_or_create_user

OK_ = []


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    OK_.append(bool(cond))


def tok(n):
    return f"tok-{n}-" + "z" * 40


async def main():
    async with SessionLocal() as db:
        a = await get_or_create_user(db, "+919000000001", "hi")
        b = await get_or_create_user(db, "+919000000002", "en")
        await db.commit()
        ua, ub = a.id, b.id
    ha = {"Authorization": f"Bearer {create_access_token(str(ua))}"}
    hb = {"Authorization": f"Bearer {create_access_token(str(ub))}"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/notifications/devices", json={"token": tok(1), "platform": "android"}, headers=ha)
        check("register 200", r.status_code == 200 and r.json() == {"registered": True})
        r = await c.post("/api/v1/notifications/devices", json={"token": tok(1)}, headers=ha)
        check("same token again = still 1 row", r.status_code == 200)
        async with SessionLocal() as db:
            check("1 row", await db.scalar(select(func.count()).select_from(DeviceToken)) == 1)
        r = await c.post("/api/v1/notifications/devices", json={"token": tok(1)}, headers=hb)
        async with SessionLocal() as db:
            row = (await db.scalars(select(DeviceToken))).one()
            check("token moves to new user on same phone", row.user_id == ub)
        r = await c.post("/api/v1/notifications/devices/unregister", json={"token": tok(1)}, headers=ha)
        check("other user cannot remove my token (removed=0)", r.json() == {"removed": 0})
        for i in range(2, 15):  # 13 aur token: cap 10
            await c.post("/api/v1/notifications/devices", json={"token": tok(i)}, headers=ha)
        async with SessionLocal() as db:
            check("cap 10 per user", await db.scalar(select(func.count()).select_from(DeviceToken).where(DeviceToken.user_id == ua)) == 10)
        r = await c.post("/api/v1/notifications/devices", json={"token": "short"}, headers=ha)
        check("bad token 422", r.status_code == 422)
        r = await c.post("/api/v1/notifications/devices/unregister", json={"token": tok(14)}, headers=ha)
        check("unregister own = 1", r.json() == {"removed": 1})
        r = await c.post("/api/v1/notifications/devices/unregister", json={"token": tok(14)}, headers=ha)
        check("unregister twice = 0, no error", r.status_code == 200 and r.json() == {"removed": 0})

    # --- push bhejna ---
    async with SessionLocal() as db:
        await db.execute(text("DELETE FROM device_tokens"))
        db.add(DeviceToken(user_id=ua, token=tok(100), platform="android"))
        db.add(DeviceToken(user_id=ua, token=tok(101), platform="ios"))  # ye wala "mara hua" hoga
        db.add(DeviceToken(user_id=ub, token=tok(200), platform="android"))
        db.add(Notification(user_id=ua, code="ORDER_DELIVERED", params={"order_no": "PD1001"}))
        db.add(Notification(user_id=ub, code="SELLER_PAYOUT_RECEIVED", params={"amount": "500"}))
        db.add(Notification(user_id=ub, code="ORDER_DELIVERED", params={"order_no": "PD9"}))
        await db.flush()
        old = Notification(user_id=ub, code="ORDER_DELIVERED", params={"order_no": "PD_OLD"})
        db.add(old)
        await db.flush()
        await db.execute(text("UPDATE notifications SET created_at = now() - interval '2 hours' WHERE params->>'order_no' = 'PD_OLD'"))
        await db.commit()

    sent = []

    def handler(request: httpx.Request):
        import json
        m = json.loads(request.content)["message"]
        sent.append(m)
        if m["token"] == tok(101):
            return httpx.Response(404, json={"error": {"details": [{"errorCode": "UNREGISTERED"}]}})
        return httpx.Response(200, json={})

    client = push.FcmClient(http=httpx.AsyncClient(transport=httpx.MockTransport(handler)), project_id="demo", token_provider=lambda: "x")
    async with SessionLocal() as db:
        claimed, ok, removed = await push.push_pending(db, client)
    check("3 fresh notifications claimed (old one skipped)", claimed == 3)
    check("push sent to 4 tokens: 2 for ua x1 notif (1 dead), 1 each for 2 ub notifs", len(sent) == 4 and ok == 3 and removed == 1)
    hindi = [m for m in sent if m["token"] == tok(100)][0]
    check("Hindi user gets Hindi text", "PD1001" in hindi["notification"]["body"] and "ऑर्डर" in hindi["notification"]["title"] + hindi["notification"]["body"])
    english = [m for m in sent if m["token"] == tok(200) and m["data"]["code"] == "ORDER_DELIVERED"][0]
    check("English user gets English text", "PD9" in english["notification"]["body"] and english["data"]["notification_id"])
    async with SessionLocal() as db:
        left = set(await db.scalars(select(DeviceToken.token)))
        check("dead token removed, good ones stay", left == {tok(100), tok(200)})
        check("old notification left unpushed", await db.scalar(select(func.count()).select_from(Notification).where(Notification.pushed_at.is_(None))) == 1)
    n_before = len(sent)
    async with SessionLocal() as db:
        again = await push.push_pending(db, client)
    check("second run sends nothing (no double push)", again == (0, 0, 0) and len(sent) == n_before)

    # --- do job ek saath: ek notification ek hi baar ---
    async with SessionLocal() as db:
        for i in range(30):
            db.add(Notification(user_id=ub, code="ORDER_DELIVERED", params={"order_no": f"PD{i}"}))
        await db.commit()
    sent.clear()

    async def run():
        async with SessionLocal() as db:
            return await push.push_pending(db, client)

    res = await asyncio.gather(run(), run(), run())
    check("3 parallel jobs: 30 notifications sent exactly once", sum(r[0] for r in res) == 30 and len(sent) == 30)
    await client.close()
    print("ALL PASS" if all(OK_) else "SOME FAILED", len(OK_))


asyncio.run(main())
