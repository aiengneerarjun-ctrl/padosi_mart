"""Coupons ka real-PostgreSQL end-to-end test. Naye / khali database par chalao:
    docker compose exec backend python -m tests.manual.e2e_coupons
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
from app.models import Category, CustomerAddress, Inventory, Order, OrderItem, Product, Seller, Store, StoreOrder
from app.services import settlement
from app.services.auth import get_or_create_user

RES = []
LAT, LNG = 25.600000, 85.100000
EXP = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()


def check(name, cond, extra=""):
    RES.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   <-- {extra}"))


def hdr(uid):
    return {"Authorization": f"Bearer {create_access_token(str(uid))}"}


async def mk_user(phone, role_id=None):
    async with SessionLocal() as db:
        u = await get_or_create_user(db, phone)
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


async def mk_product(store_id, cat_id, sku, price, qty=100):
    async with SessionLocal() as db:
        p = Product(store_id=store_id, category_id=cat_id, sku=sku, name=sku, selling_unit="1 pc", mrp=price, selling_price=price, status="ACTIVE")
        db.add(p)
        await db.flush()
        db.add(Inventory(product_id=p.id, quantity=qty))
        await db.commit()
        return p.id


async def mk_customer(phone):
    uid = await mk_user(phone)
    async with SessionLocal() as db:
        db.add(CustomerAddress(user_id=uid, receiver_name="C", receiver_phone=phone, address_line="addr", latitude=LAT, longitude=LNG, is_default=True))
        await db.commit()
    return uid


async def main():
    admin = await mk_user("+919100000001", 1)
    ua, sa, sta = await mk_seller("+919100000002", "ShopA", 0.001)
    ub, sb, stb = await mk_seller("+919100000003", "ShopB", 0.002)
    async with SessionLocal() as db:
        cat = Category(name="Test")
        db.add(cat)
        await db.commit()
        cat_id = cat.id
    pa = await mk_product(sta, cat_id, "A1", Decimal("300"))
    pa2 = await mk_product(sta, cat_id, "A2", Decimal("100"))
    pb = await mk_product(stb, cat_id, "B1", Decimal("200"))
    cust = await mk_customer("+919100000010")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        H = {"admin": hdr(admin), "a": hdr(ua), "b": hdr(ub), "c": hdr(cust)}

        async def cart(h, items):
            await c.delete("/api/v1/cart", headers=h)
            for pid, q in items:
                r = await c.put(f"/api/v1/cart/items/{pid}", json={"quantity": q, "lat": LAT, "lng": LNG}, headers=h)
                assert r.status_code == 200, r.text

        async def prev(h, code=None):
            r = await c.get("/api/v1/checkout/preview", params={"coupon_code": code} if code else {}, headers=h)
            return r.json()

        async def order(h, code, key=None):
            p = await prev(h, code)
            r = await c.post("/api/v1/orders", json={"payment_method": "COD", "expected_total": p["total"], "coupon_code": code}, headers={**h, "Idempotency-Key": key or uuid.uuid4().hex})
            return r

        # ---- coupons banana ----
        def cp(**kw):
            base = {"code": "X", "title": "Test coupon", "discount_type": "PERCENT", "value": 10, "max_discount": 50, "expires_at": EXP, "per_user_limit": 1}
            base.update(kw)
            return base

        r = await c.post("/api/v1/admin/coupons", json=cp(code="save10", min_order_amount=100), headers=H["admin"])
        check("admin creates PERCENT coupon (code upper-cased, PLATFORM)", r.status_code == 201 and r.json()["code"] == "SAVE10" and r.json()["funded_by"] == "PLATFORM", r.text)
        r = await c.post("/api/v1/admin/coupons", json=cp(code="BAD1", funded_by="SELLER", seller_id=str(sa)), headers=H["admin"])
        check("admin cannot make SELLER-funded coupon", r.status_code == 422 and r.json()["detail"]["code"] == "COUPON_ADMIN_PLATFORM_ONLY", r.text)
        r = await c.post("/api/v1/admin/coupons", json=cp(code="SAVE10"), headers=H["admin"])
        check("duplicate code 409", r.status_code == 409, r.text)
        r = await c.post("/api/v1/admin/coupons", json=cp(code="A50", discount_type="FLAT", value=50, max_discount=None), headers=H["c"])
        check("customer cannot create admin coupon (403)", r.status_code == 403, r.text)
        r = await c.post("/api/v1/seller/coupons", json={k: v for k, v in cp(code="A50", discount_type="FLAT", value=50, max_discount=None).items()}, headers=H["a"])
        check("seller A creates FLAT coupon, SELLER-funded, tied to A", r.status_code == 201 and r.json()["funded_by"] == "SELLER" and r.json()["seller_id"] == str(sa), r.text)
        a50 = r.json()["id"]
        r = await c.post("/api/v1/seller/coupons", json=cp(code="FD1", discount_type="FREE_DELIVERY", value=0, max_discount=None), headers=H["a"])
        check("seller cannot make FREE_DELIVERY", r.status_code in (409, 422), r.text)
        r = await c.patch(f"/api/v1/seller/coupons/{a50}", json={"is_active": True, "reason": "test reason"}, headers=H["b"])
        check("seller B cannot touch seller A's coupon (404)", r.status_code == 404, r.text)
        r = await c.patch(f"/api/v1/seller/coupons/{a50}", json={"value": 99, "reason": "test reason"}, headers=H["a"])
        check("rule fields (value) cannot be patched", r.status_code == 422, r.text)
        for code, kw in (("FREEDEL", dict(discount_type="FREE_DELIVERY", value=0, max_discount=None, per_user_limit=5)),
                         ("NEWBIE", dict(discount_type="FLAT", value=40, max_discount=None, first_order_only=True)),
                         ("LIM2", dict(discount_type="FLAT", value=10, max_discount=None, total_limit=2, per_user_limit=5))):
            r = await c.post("/api/v1/admin/coupons", json=cp(code=code, **kw), headers=H["admin"])
            assert r.status_code == 201, r.text
        r = await c.get("/api/v1/coupons", headers=H["c"])
        check("customer sees public coupons", r.status_code == 200 and {x["code"] for x in r.json()} >= {"SAVE10", "A50", "FREEDEL"}, r.text)

        # ---- preview ----
        await cart(H["c"], [(pa, 1)])  # 300
        p = await prev(H["c"], "save10")
        check("PERCENT preview: 10% of 300 = 30, total 300+30-30", p["discount_amount"] == 30 and p["total"] == 300 and p["coupon"]["code"] == "SAVE10", p)
        p = await prev(H["c"], "A50")
        check("seller FLAT preview: 50 off, total 280", p["discount_amount"] == 50 and p["total"] == 280, p)
        p = await prev(H["c"], "NOPE")
        check("unknown coupon -> coupon_error, preview still works", p["coupon_error"] == "COUPON_NOT_FOUND" and p["total"] == 330 and p["can_checkout"], p)
        await cart(H["c"], [(pb, 1)])  # 200, sirf B ka saaman
        p = await prev(H["c"], "A50")
        check("seller A coupon on B-only cart -> NOT_APPLICABLE", p["coupon_error"] == "COUPON_NOT_APPLICABLE" and p["discount_amount"] == 0, p)
        p = await prev(H["c"], "SAVE10")
        check("min_order 100 ok on 200 cart; 10% = 20", p["discount_amount"] == 20, p)
        await cart(H["c"], [(pa2, 1)])  # 100 -> 10% = 10, min 100 ok
        await cart(H["c"], [(pa2, 1)])
        p = await prev(H["c"], "FREEDEL")
        check("FREE_DELIVERY removes 30 fee", p["discount_amount"] == 30 and p["total"] == 100, p)
        await cart(H["c"], [(pa, 3)])  # 900 -> delivery pehle se free
        p = await prev(H["c"], "FREEDEL")
        check("FREE_DELIVERY when already free -> NO_DISCOUNT", p["coupon_error"] == "COUPON_NO_DISCOUNT", p)

        # ---- order + cancel + limit ----
        await cart(H["c"], [(pa, 1)])
        r = await order(H["c"], "SAVE10")
        o = r.json()
        check("order with SAVE10: total 300, discount 30, coupon_code set", r.status_code in (200, 201) and o["total"] == 300 and o["discount_amount"] == 30 and o["coupon_code"] == "SAVE10", r.text)
        oid1 = o["id"]
        async with SessionLocal() as db:
            so = (await db.scalars(select(StoreOrder).where(StoreOrder.order_id == uuid.UUID(oid1)))).one()
            check("platform-funded: seller_discount = 0 (seller gets full)", so.seller_discount == 0)
        await cart(H["c"], [(pa, 1)])
        p = await prev(H["c"], "SAVE10")
        check("same user again -> COUPON_USER_LIMIT", p["coupon_error"] == "COUPON_USER_LIMIT", p)
        r = await c.post("/api/v1/orders", json={"payment_method": "COD", "expected_total": 300, "coupon_code": "SAVE10"}, headers={**H["c"], "Idempotency-Key": uuid.uuid4().hex})
        check("placing order with exhausted coupon is refused", r.status_code == 409 and r.json()["detail"]["code"] == "COUPON_USER_LIMIT", r.text)
        r = await c.post("/api/v1/orders", json={"payment_method": "COD", "expected_total": 330, "coupon_code": "SAVE10"}, headers={**H["c"], "Idempotency-Key": uuid.uuid4().hex})
        r = await c.post(f"/api/v1/orders/{oid1}/cancel", json={}, headers=H["c"])
        check("cancel order ok", r.status_code == 200 and r.json()["status"] == "CANCELLED", r.text)
        p = await prev(H["c"], "SAVE10")
        check("after cancel the coupon is usable again", p["coupon_error"] is None and p["discount_amount"] == 30, p)
        r = await c.post("/api/v1/orders", json={"payment_method": "COD", "expected_total": 999}, headers={**H["c"], "Idempotency-Key": uuid.uuid4().hex})
        check("wrong expected_total -> PRICE_CHANGED", r.status_code == 409 and r.json()["detail"]["code"] == "PRICE_CHANGED", r.text)

        # ---- seller-funded, multi-store ----
        await cart(H["c"], [(pa, 1), (pb, 1)])  # A 300, B 200
        r = await order(H["c"], "A50")
        o = r.json()
        check("seller coupon in 2-store cart: discount 50 only", r.status_code in (200, 201) and o["discount_amount"] == 50 and o["total"] == 500 + 30 - 50, r.text)
        async with SessionLocal() as db:
            sos = {s.seller_id: s for s in (await db.scalars(select(StoreOrder).where(StoreOrder.order_id == uuid.UUID(o["id"])))).all()}
            check("seller_discount: A bears 50, B bears 0", sos[sa].seller_discount == 50 and sos[sb].seller_discount == 0)
            order_a = o["id"]
        r = await c.get("/api/v1/seller/orders", headers=H["a"])
        mine = [x for x in r.json() if x["id"] == str(sos[sa].id)] if r.status_code == 200 else []
        check("seller A sees seller_discount 50 in own order view", bool(mine) and mine[0]["seller_discount"] == 50, r.text[:300])

        # ---- settlement: seller ke payout se discount kata ----
        async with SessionLocal() as db:
            od = await db.scalar(select(Order).where(Order.id == uuid.UUID(order_a)))
            await settlement.apply_commission(db, od)
            await db.commit()
            sales, comm, paid, sdisc = await settlement._totals(db, sa)
            check("settlement: seller A discount 50 counted (earned = sales - commission - 50)", sdisc == 50 and sales == 300, (sales, comm, sdisc))
            sales_b, comm_b, _, sdisc_b = await settlement._totals(db, sb)
            check("settlement: seller B discount 0", sdisc_b == 0 and sales_b == 200)

        # ---- seller removes item -> discount re-priced, never increases ----
        await cart(H["c"], [(pa, 1), (pa2, 1)])  # 400 -> SAVE10 = 40 -> max 50 so 40
        c2 = await mk_customer("+919100000011")
        H["c2"] = hdr(c2)
        await cart(H["c2"], [(pa, 1), (pa2, 1)])
        r = await order(H["c2"], "SAVE10")
        o2 = r.json()
        check("order SAVE10 on 400: discount 40", r.status_code in (200, 201) and o2["discount_amount"] == 40, r.text)
        async with SessionLocal() as db:
            item = await db.scalar(select(OrderItem).where(OrderItem.order_id == uuid.UUID(o2["id"]), OrderItem.product_id == pa))
            so2 = await db.scalar(select(StoreOrder).where(StoreOrder.order_id == uuid.UUID(o2["id"])))
        r = await c.post(f"/api/v1/seller/orders/{so2.id}/unavailable", json={"items": [{"item_id": str(item.id), "reason": "OUT_OF_STOCK"}]}, headers=H["a"])
        check("seller removes 300 item", r.status_code == 200, r.text)
        r = await c.get(f"/api/v1/orders/{o2['id']}", headers=H["c2"])
        d = r.json()
        # bacha 100: SAVE10 min 100 ok -> 10% = 10; delivery 30 add; discount 40 -> 10
        check("after removal: discount re-priced to 10, discount_lost 30", d["discount_amount"] == 10 and d["discount_lost"] == 30, (d["discount_amount"], d["discount_lost"]))
        check("after removal: total = items + fee - discount (100+30-10)", d["total"] == 120 and d["items_subtotal"] == 100, (d["total"], d["items_subtotal"]))
        check("customer gets a coupon-lost notice and can still cancel", bool(d["notice"]) and d["can_cancel"] is True, d.get("notice"))

        # ---- first order only ----
        c3 = await mk_customer("+919100000012")
        H["c3"] = hdr(c3)
        await cart(H["c3"], [(pb, 1)])
        r = await order(H["c3"], "NEWBIE")
        check("NEWBIE works on first order (200 + 30 - 40)", r.status_code in (200, 201) and r.json()["total"] == 190, r.text)
        await cart(H["c3"], [(pb, 1)])
        p = await prev(H["c3"], "NEWBIE")
        check("NEWBIE refused on second order", p["coupon_error"] == "COUPON_FIRST_ORDER_ONLY", p)

        # ---- expiry / inactive ----
        r = await c.post("/api/v1/admin/coupons", json=cp(code="OFF1", discount_type="FLAT", value=5, max_discount=None), headers=H["admin"])
        off = r.json()["id"]
        r = await c.patch(f"/api/v1/admin/coupons/{off}", json={"is_active": False, "reason": "test reason"}, headers=H["admin"])
        p = await prev(H["c3"], "OFF1")
        check("deactivated coupon -> COUPON_INACTIVE", r.status_code == 200 and p["coupon_error"] == "COUPON_INACTIVE", p)
        async with SessionLocal() as db:
            n = await db.scalar(text("select count(*) from audit_logs where action like 'coupon.%'"))
            check("audit logs written for coupon actions", n >= 5, n)

        # ---- concurrency: total_limit=2, 6 customers ek saath ----
        custs = [await mk_customer(f"+91920000{i:04d}") for i in range(6)]
        for u in custs:
            await cart(hdr(u), [(pb, 1)])
        previews = {u: (await prev(hdr(u), "LIM2"))["total"] for u in custs}
        rs = await asyncio.gather(*[
            c.post("/api/v1/orders", json={"payment_method": "COD", "expected_total": previews[u], "coupon_code": "LIM2"}, headers={**hdr(u), "Idempotency-Key": uuid.uuid4().hex})
            for u in custs
        ])
        ok = [r for r in rs if r.status_code in (200, 201)]
        bad = [r.json()["detail"]["code"] for r in rs if r.status_code not in (200, 201)]
        check("6 customers race for a coupon with total_limit=2: exactly 2 win", len(ok) == 2 and set(bad) <= {"COUPON_LIMIT_REACHED"}, (len(ok), bad))
        async with SessionLocal() as db:
            used = await db.scalar(text("select count(*) from coupon_redemptions r join coupons c on c.id=r.coupon_id where c.code='LIM2' and r.released_at is null"))
            check("DB redemptions = 2", used == 2, used)
            bad_rows = await db.scalar(text("select count(*) from orders where total <> items_subtotal + delivery_fee - discount_amount"))
            check("money invariant holds on every order", bad_rows == 0, bad_rows)

    print("ALL PASS" if all(RES) else "SOME FAILED", f"({sum(RES)}/{len(RES)})")


asyncio.run(main())
