import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _module():
    path = Path(__file__).resolve().parent.parent / "scripts" / "reconcile_xc_goal_purchase.py"
    spec = importlib.util.spec_from_file_location("reconcile_xc_goal_purchase", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dependencies(email="rider@example.com", paid="paid"):
    token = "private-xc-token"
    ref = hashlib.sha256(token.encode()).hexdigest()
    stripe = MagicMock()
    stripe.checkout.Session.retrieve.return_value = SimpleNamespace(
        payment_status=paid, metadata={}, customer_details={"email": email},
        customer_email=None)
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.range.return_value = chain
    chain.execute.return_value = SimpleNamespace(data=[{
        "source": "goal_2027", "contact_email": "rider@example.com",
        "source_data": {"brand": "xcskilabs", "poster_token": token,
                        "entry_src": "race", "offer_variant": "C"},
    }])
    db = MagicMock()
    db._table.return_value = chain
    return ref, stripe, db


def test_paid_matching_buyer_is_joined():
    mod = _module()
    ref, stripe, db = _dependencies()
    assert mod.reconcile("cs_live_123abc", ref, stripe_api=stripe,
                         db=db, api_key="test-key") == "cs_live_123abc"
    metadata = stripe.checkout.Session.modify.call_args.kwargs["metadata"]
    assert metadata == {"goal_ref": ref, "brand": "xcskilabs",
                        "entry_src": "race", "offer_variant": "C"}


def test_paid_review_on_later_page_is_joined():
    mod = _module()
    ref, stripe, db = _dependencies()
    chain = db._table.return_value
    matching_row = chain.execute.return_value.data[0]
    unrelated = {"source": "goal_2027", "contact_email": "rider@example.com",
                 "source_data": {"brand": "xcskilabs", "poster_token": "unrelated"}}
    chain.execute.side_effect = [
        SimpleNamespace(data=[unrelated] * 1000),
        SimpleNamespace(data=[matching_row]),
    ]
    mod.reconcile("cs_live_123abc", ref, stripe_api=stripe, db=db, api_key="test-key")
    assert chain.range.call_count == 2
    assert chain.range.call_args_list[1].args == (1000, 1999)
    stripe.checkout.Session.modify.assert_called_once()


@pytest.mark.parametrize("email,paid", [
    ("different@example.com", "paid"), ("rider@example.com", "unpaid")])
def test_mismatch_or_unpaid_order_never_changes_metadata(email, paid):
    mod = _module()
    ref, stripe, db = _dependencies(email=email, paid=paid)
    with pytest.raises(ValueError):
        mod.reconcile("cs_live_123abc", ref, stripe_api=stripe,
                      db=db, api_key="test-key")
    stripe.checkout.Session.modify.assert_not_called()
