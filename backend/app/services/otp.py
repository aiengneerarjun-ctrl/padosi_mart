from app.core.config import settings
from app.core.errors import api_error
from app.core.redis import redis_client
from app.core.security import generate_otp, hash_otp, safe_equal
from app.services.sms import get_sms_provider

MAX_REQUESTS = 3
REQUEST_WINDOW = 600
MAX_ATTEMPTS = 5


async def request_otp(phone: str) -> None:
    key = f"otp_req:{phone}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, REQUEST_WINDOW)
    if count > MAX_REQUESTS:
        raise api_error(429, "OTP_RATE_LIMITED", "Bahut zyada OTP requests. Thodi der baad try karo.")

    otp = generate_otp()
    await redis_client.set(f"otp:{phone}", hash_otp(phone, otp), ex=settings.otp_ttl_seconds)
    await redis_client.delete(f"otp_try:{phone}")
    await get_sms_provider().send_otp(phone, otp)


async def verify_otp(phone: str, otp: str) -> None:
    tries_key = f"otp_try:{phone}"
    tries = await redis_client.incr(tries_key)
    if tries == 1:
        await redis_client.expire(tries_key, settings.otp_ttl_seconds)
    if tries > MAX_ATTEMPTS:
        await redis_client.delete(f"otp:{phone}")
        raise api_error(429, "OTP_TOO_MANY_ATTEMPTS", "Bahut zyada galat try. Naya OTP mangao.")

    stored = await redis_client.get(f"otp:{phone}")
    if stored is None or not safe_equal(stored, hash_otp(phone, otp)):
        raise api_error(400, "OTP_INVALID", "OTP galat hai ya expire ho gaya.")

    await redis_client.delete(f"otp:{phone}", tries_key)