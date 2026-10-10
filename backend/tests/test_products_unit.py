import uuid
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.i18n import localized
from app.schemas.product import ProductCreate, StockAdjust, product_out


def _create(**over):
    base = dict(sku="SUG1", category_id=uuid.uuid4(), name="Sugar", selling_unit="1 kg", mrp="50", selling_price="45.50")
    return ProductCreate(**{**base, **over})


def test_price_cannot_exceed_mrp():
    with pytest.raises(ValidationError):
        _create(mrp="50", selling_price="60")


def test_price_must_be_positive_and_two_decimals():
    with pytest.raises(ValidationError):
        _create(selling_price="0")
    with pytest.raises(ValidationError):
        _create(selling_price="45.555")
    assert _create().selling_price == Decimal("45.50")


def test_stock_change_cannot_be_zero():
    with pytest.raises(ValidationError):
        StockAdjust(change=0)
    assert StockAdjust(change=-3, reason="DAMAGED").change == -3


def test_localized_falls_back_to_english():
    item = SimpleNamespace(name="Sugar", name_hi="चीनी", name_bho=None)
    assert localized(item, "en") == "Sugar"
    assert localized(item, "hi") == "चीनी"
    assert localized(item, "bho") == "Sugar"  # Bhojpuri naam khali -> English


def test_product_out_computes_stock_and_discount():
    p = SimpleNamespace(
        id=uuid.uuid4(), store_id=uuid.uuid4(), category_id=uuid.uuid4(), brand_id=None, sku="S", barcode=None,
        name="Sugar", name_hi=None, name_bho=None, description=None, selling_unit="1 kg",
        mrp=Decimal("50.00"), selling_price=Decimal("40.00"), status="ACTIVE", status_reason=None,
        inventory=SimpleNamespace(quantity=3, low_stock_threshold=5),  images=[], created_at=datetime.now(),
    )
    out = product_out(p)
    assert out.discount_percent == 20 and out.stock == 3 and out.low_stock is True