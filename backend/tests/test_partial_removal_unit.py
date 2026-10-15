import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.i18n import MESSAGES
from app.schemas.seller_order import UnavailableBody, UnavailableItem
from app.services.seller_order import _clean_picks


def _item(**kw):
    return UnavailableItem(item_id=kw.pop("item_id", uuid.uuid4()), **kw)


def test_default_is_whole_item_removed():
    assert UnavailableItem(item_id=uuid.uuid4()).available_quantity == 0


@pytest.mark.parametrize("qty,ok", [(0, True), (1, True), (100000, True), (-1, False), (100001, False)])
def test_available_quantity_bounds(qty, ok):
    if ok:
        assert UnavailableItem(item_id=uuid.uuid4(), available_quantity=qty).available_quantity == qty
    else:
        with pytest.raises(ValidationError):
            UnavailableItem(item_id=uuid.uuid4(), available_quantity=qty)


def test_clean_picks_returns_kept_quantity():
    a, b = uuid.uuid4(), uuid.uuid4()
    picks = _clean_picks([_item(item_id=a, available_quantity=2), _item(item_id=b)], {a: 3, b: 1})
    assert picks[a] == ("OUT_OF_STOCK", None, 2)
    assert picks[b] == ("OUT_OF_STOCK", None, 0)


@pytest.mark.parametrize("ordered,available", [(3, 3), (3, 4), (1, 1), (2, 5)])
def test_available_must_be_less_than_ordered(ordered, available):
    a = uuid.uuid4()
    with pytest.raises(HTTPException) as e:
        _clean_picks([_item(item_id=a, available_quantity=available)], {a: ordered})
    assert e.value.status_code == 422 and e.value.detail["code"] == "AVAILABLE_QUANTITY_TOO_HIGH"


def test_unknown_item_still_404():
    with pytest.raises(HTTPException) as e:
        _clean_picks([_item()], {uuid.uuid4(): 2})
    assert e.value.status_code == 404


def test_other_reason_still_needs_note_even_for_partial():
    a = uuid.uuid4()
    with pytest.raises(HTTPException) as e:
        _clean_picks([_item(item_id=a, reason="OTHER", available_quantity=1)], {a: 3})
    assert e.value.detail["code"] == "REMOVAL_NOTE_REQUIRED"


def test_duplicate_items_still_rejected():
    a = uuid.uuid4()
    with pytest.raises(ValidationError):
        UnavailableBody(items=[{"item_id": a}, {"item_id": a, "available_quantity": 1}])


def test_message_in_all_languages():
    assert all(MESSAGES["AVAILABLE_QUANTITY_TOO_HIGH"].get(lang) for lang in ("en", "hi", "bho"))