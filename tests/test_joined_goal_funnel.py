import hashlib
import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).resolve().parent.parent / "scripts" / "joined_goal_funnel.py"
    spec = importlib.util.spec_from_file_location("joined_goal_funnel", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_paid_session_joins_only_matching_brand_and_live_ref():
    mod = _module()
    token = "private-token-value-for-test"
    ref = hashlib.sha256(token.encode()).hexdigest()
    enrollments = [{"source": "goal_2027", "source_data": {
        "brand": "roadielabs", "poster_token": token,
        "entry_src": "race", "offer_variant": "B"}}]
    sessions = [
        {"id": "cs_test_probe", "metadata": {"goal_ref": ref, "brand": "roadielabs"},
         "payment_status": "paid"},
        {"id": "cs_live_wrong_brand", "metadata": {"goal_ref": ref, "brand": "xcskilabs"},
         "payment_status": "paid"},
        {"id": "cs_live_buyer", "metadata": {"goal_ref": ref, "brand": "roadielabs"},
         "payment_status": "paid"},
    ]
    result = mod.join_funnel(enrollments, sessions)
    assert result["rows"] == [{"brand": "roadielabs", "entry_src": "race",
                              "offer_variant": "B", "reviews": 1, "checkouts": 1,
                              "buyers": 1, "buyer_rate": 1.0}]
    assert result["unmatched_paid_sessions"] == 1
    assert token not in str(result) and ref not in str(result)


def test_xc_manual_session_can_join_by_client_reference_id():
    mod = _module()
    token = "xc-private-token"
    ref = hashlib.sha256(token.encode()).hexdigest()
    result = mod.join_funnel(
        [{"source": "goal_2027", "source_data": {
            "brand": "xcskilabs", "poster_token": token}}],
        [{"id": "cs_live_xc", "client_reference_id": ref,
          "metadata": {"brand": "xcskilabs"}, "payment_status": "paid"}],
    )
    assert result["rows"][0]["buyers"] == 1


def test_stripe_session_conversion_supports_current_and_older_sdks():
    mod = _module()

    class CurrentSession:
        def to_dict(self):
            return {"id": "cs_live_current", "metadata": {"goal_ref": "a" * 64}}

    class OlderSession:
        def to_dict_recursive(self):
            return {"id": "cs_live_old", "metadata": {"goal_ref": "b" * 64}}

    assert mod._session_dict(CurrentSession())["id"] == "cs_live_current"
    assert mod._session_dict(OlderSession())["id"] == "cs_live_old"
