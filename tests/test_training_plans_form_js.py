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
