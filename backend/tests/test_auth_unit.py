import jwt
import pytest

from app.core.security import create_access_token, decode_access_token, generate_otp, hash_otp, hash_token
from app.schemas.auth import normalize_phone


@pytest.mark.parametrize("raw", ["9876543210", "09876543210", "+91 98765 43210", "919876543210", "98765-43210"])
def test_phone_normalized(raw):
    assert normalize_phone(raw) == "+919876543210"


@pytest.mark.parametrize("raw", ["12345", "5876543210", "abcdefghij", "+1 4155550100"])
def test_phone_rejected(raw):
    with pytest.raises(ValueError):
        normalize_phone(raw)


def test_otp_is_six_digits_and_hashed():
    otp = generate_otp()
    assert len(otp) == 6 and otp.isdigit()
    assert hash_otp("+919876543210", otp) != otp
    assert hash_otp("+919876543210", otp) != hash_otp("+919000000000", otp)


def test_access_token_roundtrip():
    assert decode_access_token(create_access_token("user-123"))["sub"] == "user-123"


def test_tampered_token_rejected():
    token = create_access_token("user-123")
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token[:-2] + "xx")


def test_refresh_hash_is_stable():
    assert hash_token("abc") == hash_token("abc")