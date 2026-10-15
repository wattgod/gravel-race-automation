"""Subscription terms stay separate from the existing purchased-product ladder."""
import importlib.util
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "wordpress/endure_offer.py"
spec = importlib.util.spec_from_file_location("endure_offer", MODULE)
offer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(offer)

def test_signup_has_source_campaign_and_no_entitlement_bypass():
    url = urlparse(offer.SIGNUP_URL)
    assert url.scheme == "https" and url.netloc == "endurelabs.app"
    assert url.path == "/sign-up"
    query = parse_qs(url.query)
    assert query["utm_campaign"] == ["endure_trial"]
    assert query["utm_medium"] == ["referral"]
    assert set(query) == {"utm_source", "utm_medium", "utm_campaign", "utm_content"}

def test_offer_discloses_card_conversion_cancellation_and_eligibility():
    text = offer.get_endure_offer_html()
    for disclosure in ["Card required.", "bills automatically unless you cancel", "Cancel online", "eligible new subscribers", "https://endurelabs.app/help"]:
        assert disclosure in text
    assert 'aria-label="Endure training app"' in text
    assert "min-height:44px" in text
    assert "focus-visible" in text
    assert "&amp;utm_medium" in text

def test_generators_emit_offer_without_replacing_purchased_product_links():
    import sys
    sys.path.insert(0, str(ROOT / "wordpress"))
    from shared_footer import get_mega_footer_html
    footer = get_mega_footer_html()
    assert footer.count('class="endure-trial-offer"') == 1
    assert "Custom Training Plans" in footer
    assert "Coaching" in footer
