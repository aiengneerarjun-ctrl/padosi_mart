import re

from pydantic import BaseModel, field_validator

_PHONE_RE = re.compile(r"(\+91|91|0)?[6-9]\d{9}")


def normalize_phone(value: str) -> str:
    v = value.strip().replace(" ", "").replace("-", "")
    if not _PHONE_RE.fullmatch(v):
        raise ValueError("Valid 10 digit Indian mobile number daalo")
    return "+91" + v[-10:]


class OtpRequest(BaseModel):
    phone: str

    _norm = field_validator("phone")(normalize_phone)


class OtpVerify(BaseModel):
    phone: str
    otp: str

    _norm = field_validator("phone")(normalize_phone)

    @field_validator("otp")
    @classmethod
    def six_digits(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("OTP 6 digit ka hota hai")
        return v


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int