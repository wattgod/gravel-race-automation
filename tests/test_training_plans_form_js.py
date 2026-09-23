"""Static integrity checks for the deployed training-plan form script."""
from pathlib import Path


FORM_JS = (
    Path(__file__).parent.parent / "web" / "training-plans-form.js"
).read_text()


def test_checkout_carries_consent_gated_ga4_attribution():
    assert "analyticsConsentGranted" in FORM_JS
    assert "gtag('get', measurementId, field" in FORM_JS
    assert "workerData.ga4_client_id" in FORM_JS
    assert "workerData.ga4_session_id" in FORM_JS
    assert "workerData.analytics_consent" in FORM_JS


def test_ga4_lookup_cannot_indefinitely_block_checkout():
    assert "GA_ATTRIBUTION_TIMEOUT_MS = 500" in FORM_JS
    assert "setTimeout(function()" in FORM_JS


def test_form_script_does_not_emit_purchase():
    assert "gtag('event', 'purchase'" not in FORM_JS


def test_every_event_carries_entry_surface_and_form_version():
    """Funnel attribution (Sep 2026): every tp_*/begin_checkout event is stamped
    with the questionnaire entry surface and the form version, so arrivals can be
    split by race profile / race plan page / product page in GA4."""
    assert "var FORM_VERSION = document.getElementById('gg-plan-total')" in FORM_JS
    assert "entry_surface: ENTRY_SURFACE" in FORM_JS
    assert "form_version: FORM_VERSION" in FORM_JS
    assert "sessionStorage.setItem(ENTRY_SURFACE_KEY" in FORM_JS  # survives Stripe back-nav
    assert "ENTRY_SURFACE_RE.test(fromUrl)" in FORM_JS   # src= is validated, never echoed raw
    assert "ENTRY_SURFACE_RE.test(stored)" in FORM_JS    # ...and so is the stored copy
    assert "refOrigin !== window.location.origin" in FORM_JS  # origin compare, not substring
    assert "getElementById('gg-plan-total') ? '2026-09-10-terms' : '2026-09-10'" in FORM_JS


def test_purchase_total_mirrors_into_terms_block_when_present():
    assert "getElementById('gg-plan-total')" in FORM_JS
    assert "' for ' + pricing.weeks + ' weeks'" in FORM_JS


def test_saved_form_survives_stripe_back_navigation():
    """Backing out of Stripe Checkout must land on a restored form."""
    start = FORM_JS.index("if (result.checkout_url)")
    end = FORM_JS.index("window.location.href = result.checkout_url")
    assert "clearSaved();" not in FORM_JS[start:end]
    assert "_savedAt" in FORM_JS
    assert "_raceSlug" in FORM_JS


def test_offer_variant_is_captured_and_validated_like_entry_surface():
    """goals-2027-funnel-spec.md: a /goals/ offer click can carry
    ?offer_variant=A/B/C to the plan form. Mirrors ENTRY_SURFACE's own
    validate-on-read, validate-on-restore, session-survives-Stripe pattern."""
    assert "OFFER_VARIANT_RE = /^[A-Z]$/" in FORM_JS
    assert "OFFER_VARIANT_RE.test(fromUrl)" in FORM_JS
    assert "OFFER_VARIANT_RE.test(stored)" in FORM_JS
    assert "sessionStorage.setItem(OFFER_VARIANT_KEY" in FORM_JS


def test_offer_variant_rides_into_ga4_events_when_present():
    assert "if (OFFER_VARIANT) { payload.offer_variant = OFFER_VARIANT; }" in FORM_JS


def test_entry_surface_and_offer_variant_forwarded_to_checkout_payload():
    """Task: entry src and offer variant must travel into checkout metadata
    if feasible. This repo's part is forwarding them on the /create-checkout
    POST body; the Railway checkout server (a separate repo) still has to
    read workerData.entry_surface / workerData.offer_variant and write them
    into the Stripe Checkout Session metadata for a purchase to be
    attributable back to a variant."""
    start = FORM_JS.index("var workerData = mapToWorkerFormat(data);")
    end = FORM_JS.index("var response = await fetch(API_URL")
    block = FORM_JS[start:end]
    assert "workerData.entry_surface = ENTRY_SURFACE;" in block
    assert "if (OFFER_VARIANT) { workerData.offer_variant = OFFER_VARIANT; }" in block
