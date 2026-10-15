"""Cashfree Payment Gateway ka chhota client (sirf wahi jo chahiye): order banana, order dekhna, refund, webhook signature.

Docs: https://www.cashfree.com/docs/api-reference/payments/latest (version header x-api-version)
- Base: sandbox https://sandbox.cashfree.com/pg , production https://api.cashfree.com/pg
- Auth: headers x-client-id, x-client-secret
- Webhook signature: base64( HMAC-SHA256( client_secret, x-webhook-timestamp + RAW body ) ), header x-webhook-signature
"""
import base64
import hashlib
import hmac
import logging
import re
from datetime import datetime
from decimal import Decimal

import httpx

from app.core.config import settings

log = logging.getLogger("padosi.cashfree")
BASES = {"sandbox": "https://sandbox.cashfree.com/pg", "production": "https://api.cashfree.com/pg"}
TIMEOUT = 15.0

# Sirf jaanch (tests) ke liye: nakli Cashfree. Asli chalne me None rehta hai.
_transport: httpx.AsyncBaseTransport | None = None


class CashfreeError(Exception):
    def __init__(self, message: str, status: int | None = None, body: dict | None = None):
        super().__init__(message)
        self.status = status
        self.body = body or {}


def enabled() -> bool:
    return settings.payments_enabled


def _headers(idempotency_key: str | None = None) -> dict:
    h = {
        "x-client-id": settings.cashfree_client_id,
        "x-client-secret": settings.cashfree_client_secret,
        "x-api-version": settings.cashfree_api_version,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if idempotency_key:
        h["x-idempotency-key"] = idempotency_key
    return h


async def _call(method: str, path: str, *, json: dict | None = None, idempotency_key: str | None = None) -> dict:
    url = BASES.get(settings.cashfree_env, BASES["sandbox"]) + path
    try:
        async with httpx.AsyncClient(transport=_transport, timeout=TIMEOUT) as c:
            r = await c.request(method, url, json=json, headers=_headers(idempotency_key))
    except httpx.HTTPError as e:  # network / timeout
        raise CashfreeError(f"Cashfree se baat nahi ho paayi: {e.__class__.__name__}") from e
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code >= 400:
        log.warning("cashfree %s %s -> %s %s", method, path, r.status_code, body)
        raise CashfreeError(str(body.get("message") or f"HTTP {r.status_code}"), r.status_code, body)
    return body


def customer_phone(phone: str) -> str:
    """Cashfree ko 10 ank ka number chahiye: aakhri 10 ank."""
    return re.sub(r"\D", "", phone)[-10:]


async def create_order(
    *, order_id: str, amount: Decimal, customer_id: str, phone: str, name: str | None, expires_at: datetime, note: str
) -> dict:
    """Cashfree me order banao. Jawab me payment_session_id aata hai (app ka SDK isse payment kholta hai).
    order_id hi idempotency key hai, to retry par wahi jawab milta hai."""
    meta: dict = {"notify_url": settings.payment_notify_url}
    if settings.payment_return_url:
        meta["return_url"] = settings.payment_return_url
    customer = {"customer_id": customer_id, "customer_phone": customer_phone(phone)}
    if name and len(name.strip()) >= 3:
        customer["customer_name"] = name.strip()[:100]
    return await _call(
        "POST", "/orders", idempotency_key=order_id,
        json={
            "order_id": order_id, "order_amount": float(amount), "order_currency": "INR", "customer_details": customer,
            "order_meta": meta, "order_expiry_time": expires_at.isoformat(), "order_note": note[:200],
        },
    )


async def get_order(order_id: str) -> dict:
    return await _call("GET", f"/orders/{order_id}")


async def create_refund(*, order_id: str, refund_id: str, amount: Decimal, note: str) -> dict:
    """Refund shuru karo. refund_id hamara hai (hamesha wahi, retry me bhi)."""
    return await _call(
        "POST", f"/orders/{order_id}/refunds", idempotency_key=refund_id,
        json={"refund_amount": float(amount), "refund_id": refund_id, "refund_note": note[:100], "refund_speed": "STANDARD"},
    )


def sign(secret: str, timestamp: str, raw_body: bytes) -> str:
    return base64.b64encode(hmac.new(secret.encode(), timestamp.encode() + raw_body, hashlib.sha256).digest()).decode()


def verify_signature(timestamp: str | None, raw_body: bytes, signature: str | None, secret: str | None = None) -> bool:
    """Webhook sachmuch Cashfree se aaya hai? RAW body par hi, bina badle."""
    secret = secret if secret is not None else settings.cashfree_client_secret
    if not (timestamp and signature and secret):
        return False
    return hmac.compare_digest(sign(secret, timestamp, raw_body), signature)