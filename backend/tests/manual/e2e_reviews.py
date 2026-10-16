"""Reviews ka real-PostgreSQL end-to-end test. Naye / khali database par chalao:
    docker compose exec backend python -m tests.manual.e2e_reviews
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
    admin = await mk_user("+919200000001", 1)
    ua, sa, sta = await mk_seller("+919200000002", "ShopA", 0.001)
    ub, sb, stb = await mk_seller("+919200000003", "ShopB", 0.002)
    up = await mk_user("+919200000004", None, "Raju Partner")
    async with SessionLocal() as db:
        cat = Category(name="Test")
        db.add(cat)
        partner = DeliveryPartner(user_id=up, full_name="Raju Kumar", vehicle_type="BIKE", vehicle_number="BR01AB1234", id_type="AADHAAR", id_photo_key="k", status="ACTIVE")
        db.add(partner)
        await db.commit()
        cat_id, partner_id = cat.id, partner.id
    pa = await mk_product(sta, cat_id, "A1", Decimal("300"))
    pb = await mk_product(stb, cat_id, "B1", Decimal("200"))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        async def place(uid, items):
            h = hdr(uid)
            await c.delete("/api/v1/cart", headers=h)
            for pid, q in items:
                r = await c.put(f"/api/v1/cart/items/{pid}", json={"quantity": q, "lat": LAT, "lng": LNG}, headers=h)
                assert r.status_code == 200, r.text
            p = (await c.get("/api/v1/checkout/preview", headers=h)).json()
            r = await c.post("/api/v1/orders", json={"payment_method": "COD", "expected_total": p["total"]}, headers={**h, "Idempotency-Key": uuid.uuid4().hex})
            assert r.status_code in (200, 201), r.text
            return r.json()["id"]

        async def deliver(order_id, days_ago=0):
            """Order ko DELIVERED bana do (delivery pipeline ka test yahan nahi, review ka hai)."""
            async with SessionLocal() as db:
                when = datetime.now(timezone.utc) - timedelta(days=days_ago)
                await db.execute(text("UPDATE orders SET status='DELIVERED' WHERE id=:i"), {"i": order_id})
                db.add(Delivery(order_id=uuid.UUID(order_id), partner_id=partner_id, status="DELIVERED", delivered_at=when))
                await db.commit()

        async def review(uid, order_id, target, rating, store_id=None, comment=None):
            body = {"order_id": order_id, "target": target, "rating": rating, "comment": comment}
            if store_id:
                body["store_id"] = str(store_id)
            return await c.post("/api/v1/reviews", json=body, headers=hdr(uid))

        cust = await mk_customer("+919200000010", "Ramesh Kumar Singh")
        other = await mk_customer("+919200000011", "Sita Devi")
        o1 = await place(cust, [(pa, 1), (pb, 1)])

        # ---- delivery se pehle ----
        r = await c.get(f"/api/v1/orders/{o1}/reviewable", headers=hdr(cust))
        check("before delivery: can_review false, REVIEW_ORDER_NOT_DELIVERED", r.status_code == 200 and not r.json()["can_review"] and r.json()["reason"] == "REVIEW_ORDER_NOT_DELIVERED", r.text)
        r = await review(cust, o1, "STORE", 5, sta)
        check("review before delivery refused (409)", r.status_code == 409 and r.json()["detail"]["code"] == "REVIEW_ORDER_NOT_DELIVERED", r.text)

        await deliver(o1)
        r = await c.get(f"/api/v1/orders/{o1}/reviewable", headers=hdr(cust))
        d = r.json()
        check("after delivery: can_review, 2 stores + 1 partner target", d["can_review"] and len(d["targets"]) == 3 and {t["target"] for t in d["targets"]} == {"STORE", "PARTNER"}, d)
        check("partner shown by first name only", [t["name"] for t in d["targets"] if t["target"] == "PARTNER"] == ["Raju"], d)
        r = await c.get(f"/api/v1/orders/{o1}/reviewable", headers=hdr(other))
        check("other customer cannot see my order (404)", r.status_code == 404, r.text)

        # ---- review dena ----
        r = await review(cust, o1, "STORE", 5, sta, "Bahut badhiya saaman")
        check("review store A (5 star)", r.status_code == 201 and r.json()["rating"] == 5 and r.json()["name"] == "ShopA", r.text)
        ra = r.json()["id"]
        r = await review(cust, o1, "STORE", 2, stb, "Der se diya")
        check("review store B (2 star)", r.status_code == 201, r.text)
        rb = r.json()["id"]
        r = await review(cust, o1, "PARTNER", 4)
        check("review delivery partner (4 star)", r.status_code == 201 and r.json()["name"] == "Raju", r.text)
        rp = r.json()["id"]
        r = await review(cust, o1, "STORE", 1, sta)
        check("duplicate store review -> REVIEW_ALREADY_EXISTS", r.status_code == 409 and r.json()["detail"]["code"] == "REVIEW_ALREADY_EXISTS", r.text)
        r = await review(cust, o1, "PARTNER", 1)
        check("duplicate partner review refused", r.status_code == 409, r.text)
        r = await review(other, o1, "STORE", 5, sta)
        check("another customer cannot review my order (404)", r.status_code == 404, r.text)
        r = await review(cust, o1, "STORE", 5, uuid.uuid4())
        check("store not in this order -> REVIEW_TARGET_NOT_FOUND", r.status_code == 404 and r.json()["detail"]["code"] == "REVIEW_TARGET_NOT_FOUND", r.text)
        r = await c.post("/api/v1/reviews", json={"order_id": o1, "target": "STORE", "rating": 5}, headers=hdr(cust))
        check("STORE without store_id -> 422", r.status_code == 422, r.text)
        r = await review(cust, o1, "PARTNER", 6)
        check("rating 6 -> 422", r.status_code == 422, r.text)
        r = await c.get(f"/api/v1/orders/{o1}/reviewable", headers=hdr(cust), )
        check("reviewable now shows all 3 as reviewed", all(t["reviewed"] for t in r.json()["targets"]), r.text)

        # ---- 5 request ek saath wahi review: sirf ek ----
        cust2 = await mk_customer("+919200000012", "Gita")
        o2 = await place(cust2, [(pa, 1)])
        await deliver(o2)
        rs = await asyncio.gather(*[review(cust2, o2, "STORE", 3, sta) for _ in range(5)])
        codes = sorted(r.status_code for r in rs)
        check("5 parallel identical reviews: exactly one 201, rest 409", codes == [201, 409, 409, 409, 409], codes)

        # ---- time limit ----
        cust3 = await mk_customer("+919200000013", None)
        o3 = await place(cust3, [(pa, 1)])
        await deliver(o3, days_ago=8)
        r = await review(cust3, o3, "STORE", 5, sta)
        check("8 days after delivery -> REVIEW_WINDOW_OVER", r.status_code == 409 and r.json()["detail"]["code"] == "REVIEW_WINDOW_OVER", r.text)
        o4 = await place(cust3, [(pa, 1)])
        await deliver(o4, days_ago=6)
        r = await review(cust3, o4, "STORE", 5, sta)
        check("6 days after delivery still ok; unnamed customer shows as 'Customer'", r.status_code == 201, r.text)

        # ---- public dukaan reviews ----
        r = await c.get(f"/api/v1/shop/stores/{sta}/reviews", headers=hdr(other))
        d = r.json()
        check("store A summary: 5, 3, 5 -> avg 4.33, count 3", d["summary"]["count"] == 3 and d["summary"]["average"] == 4.33, d["summary"])
        check("reviewer shown by first name only", "Ramesh" in {x["reviewer_name"] for x in d["reviews"]} and "Customer" in {x["reviewer_name"] for x in d["reviews"]}, d["reviews"])
        check("star breakdown {5:2, 3:1}", d["summary"]["stars"] == {"1": 0, "2": 0, "3": 1, "4": 0, "5": 2}, d["summary"]["stars"])
        r = await c.get(f"/api/v1/shop/stores/{uuid.uuid4()}/reviews", headers=hdr(other))
        check("unknown store -> 404", r.status_code == 404, r.text)

        # ---- seller / partner ----
        r = await c.get("/api/v1/seller/reviews", headers=hdr(ua))
        d = r.json()
        check("seller A sees own 3 reviews with order number", r.status_code == 200 and len(d["reviews"]) == 3 and d["reviews"][0]["order_number"].startswith("PD"), r.text[:300])
        r = await c.get("/api/v1/seller/reviews", params={"max_rating": 3}, headers=hdr(ua))
        check("seller max_rating=3 filter", len(r.json()["reviews"]) == 1 and r.json()["reviews"][0]["rating"] == 3, r.text[:300])
        r = await c.get("/api/v1/seller/reviews", params={"store_id": str(sta)}, headers=hdr(ub))
        check("seller B cannot read seller A's store reviews (404)", r.status_code == 404, r.text)
        r = await c.get("/api/v1/seller/reviews", headers=hdr(ub))
        check("seller B sees only own store B review (2 star)", len(r.json()["reviews"]) == 1 and r.json()["summary"]["average"] == 2.0, r.text[:300])
        r = await c.get("/api/v1/delivery/reviews", headers=hdr(up))
        d = r.json()
        check("partner sees own review + avg 4.0, no customer name", r.status_code == 200 and d["summary"]["average"] == 4.0 and "reviewer_name" not in d["reviews"][0], r.text[:300])
        r = await c.get("/api/v1/delivery/reviews", headers=hdr(cust))
        check("non-partner -> 403", r.status_code == 403, r.text)
        r = await c.get("/api/v1/reviews/mine", headers=hdr(cust))
        check("customer 'my reviews' lists 3", r.status_code == 200 and len(r.json()) == 3, r.text[:200])

        # ---- admin ----
        r = await c.get("/api/v1/admin/reviews", params={"max_rating": 2}, headers=hdr(admin))
        check("admin lists low-rated reviews", r.status_code == 200 and [x["rating"] for x in r.json()] == [2], r.text[:300])
        r = await c.post(f"/api/v1/admin/reviews/{rb}/hide", json={"reason": "gali wali bhasha"}, headers=hdr(cust))
        check("customer cannot hide (403)", r.status_code == 403, r.text)
        r = await c.post(f"/api/v1/admin/reviews/{rb}/hide", json={"reason": "x"}, headers=hdr(admin))
        check("hide needs a real reason (422)", r.status_code == 422, r.text)
        r = await c.post(f"/api/v1/admin/reviews/{rb}/hide", json={"reason": "jhooti review"}, headers=hdr(admin))
        check("admin hides review", r.status_code == 200 and r.json()["status"] == "HIDDEN" and r.json()["hidden_reason"] == "jhooti review", r.text)
        r = await c.post(f"/api/v1/admin/reviews/{rb}/hide", json={"reason": "jhooti review"}, headers=hdr(admin))
        check("hide twice is harmless", r.status_code == 200, r.text)
        r = await c.get(f"/api/v1/shop/stores/{stb}/reviews", headers=hdr(other))
        check("hidden review gone from store B; average empty", r.json()["reviews"] == [] and r.json()["summary"]["count"] == 0 and r.json()["summary"]["average"] is None, r.text)
        r = await c.get("/api/v1/reviews/mine", headers=hdr(cust))
        check("customer still sees own hidden review flagged is_hidden", any(x["id"] == rb and x["is_hidden"] for x in r.json()), r.text[:300])
        r = await c.post(f"/api/v1/admin/reviews/{rb}/unhide", headers=hdr(admin))
        check("admin unhides", r.status_code == 200 and r.json()["status"] == "VISIBLE", r.text)
        r = await c.get(f"/api/v1/shop/stores/{stb}/reviews", headers=hdr(other))
        check("unhidden review back, average 2.0", r.json()["summary"]["count"] == 1 and r.json()["summary"]["average"] == 2.0, r.text)
        r = await c.post(f"/api/v1/admin/reviews/{uuid.uuid4()}/hide", json={"reason": "test reason"}, headers=hdr(admin))
        check("hide unknown review -> 404", r.status_code == 404, r.text)

        # ---- DB sachchai: star ki ginti = VISIBLE reviews ----
        async with SessionLocal() as db:
            bad = await db.scalar(text("""
                select count(*) from (
                  select r.target_type, coalesce(r.store_id, r.partner_id) tid,
                         count(*) filter (where r.rating=1 and r.status='VISIBLE') s1, count(*) filter (where r.rating=2 and r.status='VISIBLE') s2,
                         count(*) filter (where r.rating=3 and r.status='VISIBLE') s3, count(*) filter (where r.rating=4 and r.status='VISIBLE') s4,
                         count(*) filter (where r.rating=5 and r.status='VISIBLE') s5
                  from reviews r group by 1, 2) x
                left join rating_summaries s on s.target_type = x.target_type and s.target_id = x.tid
                where s.target_id is null or (s.star1, s.star2, s.star3, s.star4, s.star5) <> (x.s1, x.s2, x.s3, x.s4, x.s5)"""))
            check("rating_summaries match VISIBLE reviews exactly", bad == 0, bad)
            n = await db.scalar(text("select count(*) from audit_logs where action in ('review.hide','review.unhide')"))
            check("audit: 1 hide + 1 unhide (repeat hide wrote nothing)", n == 2, n)

    print("ALL PASS" if all(RES) else "SOME FAILED", f"({sum(RES)}/{len(RES)})")


asyncio.run(main())
