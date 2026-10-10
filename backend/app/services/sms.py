import logging

from app.core.config import settings

logger = logging.getLogger("padosi.sms")


class ConsoleSmsProvider:
    """SIRF development ke liye: OTP terminal me print hota hai."""

    async def send_otp(self, phone: str, otp: str) -> None:
        logger.warning("DEV OTP for %s: %s", phone, otp)


def get_sms_provider():
    if settings.sms_provider == "console":
        if settings.app_env != "development":
            raise RuntimeError("Production me console SMS provider allowed nahi hai. Real SMS provider lagao.")
        return ConsoleSmsProvider()
    raise RuntimeError(f"Unknown SMS provider: {settings.sms_provider}")