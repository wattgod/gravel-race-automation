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
