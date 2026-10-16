"""Support tickets ka real-PostgreSQL end-to-end test. Naye / khali database par chalao:
    docker compose exec backend python -m tests.manual.e2e_support
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select, text

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models import Category, CustomerAddress, Delivery, DeliveryPartner, Inventory, Order, Product, Seller, Store
from app.services.auth import get_or_create_user

RES = []
LAT, LNG = 25.600000, 85.100000


def check(name, cond, extra=""):
    RES.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   <-- {extra}"))


def hdr(uid):
    return {"Authorization": f"Bearer {create_access_token(str(uid))}"}


async def mk_user(phone, role_id=None, name=None):
    async with SessionLocal() as db:
        u = await get_or_create_user(db, phone)
        if name:
            u.name = name
        if role_id:
            await db.execute(text("INSERT INTO user_roles(user_id, role_id) VALUES (:u, :r) ON CONFLICT DO NOTHING"), {"u": u.id, "r": role_id})
        await db.commit()
        return u.id


async def mk_seller(phone, name, lat_off):
    uid = await mk_user(phone, 3)
    async with SessionLocal() as db:
        s = Seller(user_id=uid, seller_type="KIRANA", business_name=name, owner_name=name, status="ACTIVE")
        db.add(s)
        await db.flush()
        st = Store(seller_id=s.id, store_type="KIRANA", name=name, address="x", latitude=LAT + lat_off, longitude=LNG, delivery_radius_km=5, shop_status="OPEN")
        db.add(st)
        await db.commit()
        return uid, s.id, st.id


async def mk_product(store_id, cat_id, sku, price):
    async with SessionLocal() as db:
        p = Product(store_id=store_id, category_id=cat_id, sku=sku, name=sku, selling_unit="1 pc", mrp=price, selling_price=price, status="ACTIVE")
        db.add(p)
        await db.flush()
        db.add(Inventory(product_id=p.id, quantity=1000))
        await db.commit()
        return p.id


async def mk_customer(phone, name=None):
    uid = await mk_user(phone, None, name)
    async with SessionLocal() as db:
        db.add(CustomerAddress(user_id=uid, receiver_name="C", receiver_phone=phone, address_line="addr", latitude=LAT, longitude=LNG, is_default=True))
        await db.commit()
    return uid


async def main():
    admin = await mk_user("+919300000001", 1)
    ua, sa, sta = await mk_seller("+919300000002", "ShopA", 0.001)
    up = await mk_user("+919300000004", None, "Raju Partner")
    async with SessionLocal() as db:
        cat = Category(name="Test")
        db.add(cat)
        await db.execute(text("INSERT INTO user_roles(user_id, role_id) VALUES (:u, 5) ON CONFLICT DO NOTHING"), {"u": up})
        partner = DeliveryPartner(user_id=up, full_name="Raju Kumar", vehicle_type="BIKE", vehicle_number="BR01AB1234", id_type="AADHAAR", id_photo_key="k", status="ACTIVE")
        db.add(partner)
        await db.commit()
        cat_id, partner_id = cat.id, partner.id
    pa = await mk_product(sta, cat_id, "A1", Decimal("300"))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        async def place(uid):
            h = hdr(uid)
            await c.delete("/api/v1/cart", headers=h)
            r = await c.put(f"/api/v1/cart/items/{pa}", json={"quantity": 1, "lat": LAT, "lng": LNG}, headers=h)
            p = (await c.get("/api/v1/checkout/preview", headers=h)).json()
            r = await c.post("/api/v1/orders", json={"payment_method": "COD", "expected_total": p["total"]}, headers={**h, "Idempotency-Key": uuid.uuid4().hex})
            assert r.status_code in (200, 201), r.text
            return r.json()["id"]

        async def tk(uid, **kw):
            body = {"raised_as": "CUSTOMER", "category": "ORDER_ISSUE", "subject": "Kuch gadbad hai", "message": "Meri madad karo"}
            body.update(kw)
            return await c.post("/api/v1/support/tickets", json=body, headers=hdr(uid))

        cust = await mk_customer("+919300000010", "Ramesh")
        async with SessionLocal() as db:
            await db.execute(text("UPDATE users SET language='hi' WHERE id=:i"), {"i": cust})
            await db.commit()
        other = await mk_customer("+919300000011", "Sita")
        o_cust = await place(cust)
        o_other = await place(other)
        async with SessionLocal() as db:
            db.add(Delivery(order_id=uuid.UUID(o_cust), partner_id=partner_id, status="ASSIGNED"))
            await db.commit()

        # ---- ticket kholna ----
        r = await tk(cust, order_id=o_cust)
        d = r.json()
        check("customer opens ticket linked to own order", r.status_code == 201 and d["ticket_number"].startswith("TK") and d["status"] == "OPEN" and d["order_number"].startswith("PD") and len(d["messages"]) == 1, r.text)
        t1 = d["id"]
        check("first message is from USER", d["messages"][0]["author_type"] == "USER" and d["messages"][0]["body"] == "Meri madad karo", d)
        r = await tk(cust, raised_as="SELLER")
        check("customer cannot raise as SELLER (403)", r.status_code == 403 and r.json()["detail"]["code"] == "TICKET_ROLE_NOT_ALLOWED", r.text)
        r = await tk(cust, order_id=o_other)
        check("cannot link someone else's order (404)", r.status_code == 404, r.text)
        r = await tk(cust, subject="ab")
        check("subject too short (422)", r.status_code == 422, r.text)

        r = await tk(ua, raised_as="SELLER", order_id=o_cust, category="DELIVERY")
        check("seller opens ticket on an order containing their store", r.status_code == 201 and r.json()["raised_as"] == "SELLER", r.text)
        ts = r.json()["id"]
        async with SessionLocal() as db:  # doosre seller ka order: ek aur seller + uska order
            pass
        r = await tk(up, raised_as="DELIVERY_PARTNER", order_id=o_cust, category="DELIVERY")
        check("delivery partner opens ticket on own delivery", r.status_code == 201, r.text)
        r = await tk(up, raised_as="DELIVERY_PARTNER", order_id=o_other)
        check("partner cannot link an order he did not deliver (404)", r.status_code == 404, r.text)
        r = await tk(cust, raised_as="DELIVERY_PARTNER")
        check("customer cannot raise as DELIVERY_PARTNER (403)", r.status_code == 403, r.text)

        # ---- limit ----
        n_ok = 1
        for i in range(6):
            r = await tk(cust, subject=f"Aur ek ticket {i}")
            n_ok += r.status_code == 201
        check("limit: 5 open tickets, next -> TICKET_LIMIT", n_ok == 5 and r.status_code == 409 and r.json()["detail"]["code"] == "TICKET_LIMIT", (n_ok, r.text))
        racer = await mk_customer("+919300000012", "Racer")
        rs = await asyncio.gather(*[tk(racer, subject=f"Race {i}") for i in range(8)])
        check("8 parallel creates by one user: exactly 5 succeed", sorted(r.status_code for r in rs) == [201] * 5 + [409] * 3, [r.status_code for r in rs])

        # ---- visibility ----
        for method, path, kw in (("get", f"/api/v1/support/tickets/{t1}", {}), ("post", f"/api/v1/support/tickets/{t1}/messages", {"json": {"body": "hi"}}), ("post", f"/api/v1/support/tickets/{t1}/close", {})):
            r = await getattr(c, method)(path, headers=hdr(other), **kw)
            check(f"other user cannot {method} {path.rsplit('/', 1)[-1] if method == 'post' else 'ticket'} (404)", r.status_code == 404, r.text)
        r = await c.get("/api/v1/support/tickets", headers=hdr(cust))
        check("customer lists only own tickets (5)", r.status_code == 200 and len(r.json()) == 5 and all(x["raised_as"] == "CUSTOMER" for x in r.json()), r.text[:200])
        r = await c.get("/api/v1/support/tickets", headers=hdr(cust), params={"status": "ANSWERED"})
        check("status filter works (none answered yet)", r.json() == [], r.text)

        # ---- admin queue ----
        r = await c.get("/api/v1/admin/support/tickets", headers=hdr(cust))
        check("customer cannot use admin queue (403)", r.status_code == 403, r.text)
        r = await c.get("/api/v1/admin/support/tickets", params={"limit": 100}, headers=hdr(admin))
        q = r.json()
        check("admin queue: all OPEN, oldest waiting first", r.status_code == 200 and len(q) == 5 + 5 + 2 and all(x["status"] == "OPEN" for x in q) and [x["last_message_at"] for x in q] == sorted(x["last_message_at"] for x in q), [x["status"] for x in q])
        check("admin sees user name + phone", q[0]["user_phone"].startswith("+91") and "user_name" in q[0], q[0])
        r = await c.get("/api/v1/admin/support/tickets", params={"raised_as": "SELLER"}, headers=hdr(admin))
        check("admin filter raised_as=SELLER", len(r.json()) == 1 and r.json()[0]["id"] == ts, r.text[:200])

        # ---- jawab ----
        r = await c.post(f"/api/v1/admin/support/tickets/{t1}/messages", json={"body": "  Dekh rahe hain  "}, headers=hdr(admin))
        d = r.json()
        check("admin reply: ANSWERED, 2 messages, body trimmed", r.status_code == 200 and d["status"] == "ANSWERED" and len(d["messages"]) == 2 and d["messages"][1]["author_type"] == "ADMIN" and d["messages"][1]["body"] == "Dekh rahe hain", r.text[:300])
        r = await c.get("/api/v1/notifications", headers={**hdr(cust), "Accept-Language": "hi"})
        codes = [x["code"] for x in r.json()]
        tt = [x for x in r.json() if x["code"] == "TICKET_REPLIED"]
        check("customer got TICKET_REPLIED notification (Hindi text, ticket no)", "TICKET_REPLIED" in codes and "पड़ोसी" in tt[0]["title"] and "TK" in tt[0]["body"], r.text[:300])
        r = await c.get("/api/v1/admin/support/tickets", params={"limit": 100}, headers=hdr(admin))
        check("answered ticket moved below the OPEN ones", [x["status"] for x in r.json()][-1] == "ANSWERED", [x["status"] for x in r.json()])
        r = await c.post(f"/api/v1/support/tickets/{t1}/messages", json={"body": "Shukriya, abhi tak nahi aaya"}, headers=hdr(cust))
        check("customer replies -> back to OPEN, 3 messages", r.status_code == 200 and r.json()["status"] == "OPEN" and len(r.json()["messages"]) == 3, r.text[:200])

        # ---- band / dobara ----
        r = await c.post(f"/api/v1/admin/support/tickets/{t1}/close", json={"note": "hal ho gaya"}, headers=hdr(admin))
        check("admin closes ticket", r.status_code == 200 and r.json()["status"] == "CLOSED" and r.json()["closed_at"], r.text[:200])
        r = await c.post(f"/api/v1/admin/support/tickets/{t1}/close", headers=hdr(admin))
        check("closing twice is harmless", r.status_code == 200, r.text[:100])
        r = await c.get("/api/v1/notifications", headers=hdr(cust))
        check("exactly one TICKET_CLOSED notification (not two)", [x["code"] for x in r.json()].count("TICKET_CLOSED") == 1, [x["code"] for x in r.json()])
        r = await c.post(f"/api/v1/support/tickets/{t1}/messages", json={"body": "ek aur baat"}, headers=hdr(cust))
        check("reply on closed ticket -> TICKET_CLOSED", r.status_code == 409 and r.json()["detail"]["code"] == "TICKET_CLOSED", r.text)
        r = await c.post(f"/api/v1/admin/support/tickets/{t1}/messages", json={"body": "ek aur baat"}, headers=hdr(admin))
        check("admin reply on closed ticket refused", r.status_code == 409, r.text)
        r = await c.post(f"/api/v1/admin/support/tickets/{t1}/reopen", headers=hdr(admin))
        check("admin reopens -> OPEN, closed_at cleared", r.status_code == 200 and r.json()["status"] == "OPEN" and r.json()["closed_at"] is None, r.text[:200])
        r = await c.post(f"/api/v1/admin/support/tickets/{t1}/reopen", headers=hdr(admin))
        check("reopen twice is harmless", r.status_code == 200 and r.json()["status"] == "OPEN", r.text[:100])
        r = await c.post(f"/api/v1/support/tickets/{t1}/close", headers=hdr(cust))
        check("customer closes own ticket", r.status_code == 200 and r.json()["status"] == "CLOSED", r.text[:200])
        r = await c.post(f"/api/v1/support/tickets/{t1}/close", headers=hdr(cust))
        check("customer closes twice: same state, no error", r.status_code == 200 and r.json()["status"] == "CLOSED", r.text[:100])
        r = await tk(cust, subject="Ab jagah khali hui")
        check("closing frees a slot: new ticket allowed again", r.status_code == 201, r.text)

        # ---- sandesha limit + badal na sake ----
        async with SessionLocal() as db:
            tid = uuid.UUID(ts)
            await db.execute(text("INSERT INTO support_messages(id, ticket_id, author_id, author_type, body) SELECT gen_random_uuid(), :t, :u, 'USER', 'x' FROM generate_series(1, 99)"), {"t": tid, "u": ua})
            await db.commit()
        r = await c.post(f"/api/v1/support/tickets/{ts}/messages", json={"body": "101vaan"}, headers=hdr(ua))
        check("100 messages max -> TICKET_MESSAGE_LIMIT", r.status_code == 409 and r.json()["detail"]["code"] == "TICKET_MESSAGE_LIMIT", r.text)
        async with SessionLocal() as db:
            try:
                await db.execute(text("UPDATE support_messages SET body='badla' WHERE ticket_id=:t"), {"t": tid})
                await db.commit()
                check("messages cannot be edited (trigger)", False, "update went through")
            except Exception as e:
                await db.rollback()
                check("messages cannot be edited (trigger)", "support_messages" in str(e) or "immutable" in str(e).lower() or "not allowed" in str(e).lower(), str(e)[:200])
        async with SessionLocal() as db:
            try:
                await db.execute(text("DELETE FROM support_messages WHERE ticket_id=:t"), {"t": tid})
                await db.commit()
                check("messages cannot be deleted (trigger)", False, "delete went through")
            except Exception:
                await db.rollback()
                check("messages cannot be deleted (trigger)", True)
            n = await db.scalar(text("select count(*) from audit_logs where action in ('support.close','support.reopen')"))
            check("audit: 1 close + 1 reopen (repeats wrote nothing)", n == 2, n)

    print("ALL PASS" if all(RES) else "SOME FAILED", f"({sum(RES)}/{len(RES)})")


asyncio.run(main())
