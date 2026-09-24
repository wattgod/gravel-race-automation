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
    validate-on-read, validate-on-restore, session-survives-Stripe pattern.

    sol review: the regex accepted any single uppercase letter (A-Z), not
    just the three real offer variants — restricted to A/B/C."""
    assert "OFFER_VARIANT_RE = /^[ABC]$/" in FORM_JS
    assert "OFFER_VARIANT_RE = /^[A-Z]$/" not in FORM_JS
    assert "OFFER_VARIANT_RE.test(fromUrl)" in FORM_JS
    assert "OFFER_VARIANT_RE.test(stored)" in FORM_JS
    assert "sessionStorage.setItem(OFFER_VARIANT_KEY" in FORM_JS


def test_offer_variant_rides_into_ga4_events_when_present():
    assert "if (OFFER_VARIANT) { payload.offer_variant = OFFER_VARIANT; }" in FORM_JS


def test_checkout_pending_marker_is_the_only_thing_that_can_revive_stored_attribution():
    """sol review, round 2: gating the stored fallback on ENTRY_SURFACE ===
    'goals' wasn't enough, because ENTRY_SURFACE itself could re-hydrate
    "goals" from sessionStorage on a later, unrelated visit with no ?src=
    at all (e.g. a bookmark or the header nav) — there was nothing in that
    branch to tell "genuine Stripe bounce" apart from "same tab, days
    later." IS_CHECKOUT_RETURN is read once, from a marker set only in the
    instant before redirecting to Stripe, and removed immediately — so it
    can only ever be true on the one pageload that is a real return."""
    assert "var CHECKOUT_PENDING_KEY = 'gg_tp_checkout_pending';" in FORM_JS
    assert "IS_CHECKOUT_RETURN = sessionStorage.getItem(CHECKOUT_PENDING_KEY) === '1';" in FORM_JS
    assert "sessionStorage.removeItem(CHECKOUT_PENDING_KEY);" in FORM_JS

    # ENTRY_SURFACE's own stored-value fallback is gated on it
    surface_fn_start = FORM_JS.index("function resolveEntrySurface()")
    surface_fn_end = FORM_JS.index("var ENTRY_SURFACE = resolveEntrySurface();")
    assert "if (IS_CHECKOUT_RETURN) {" in FORM_JS[surface_fn_start:surface_fn_end]

    # ...and so are offer_variant and entry_src, the same rule everywhere
    variant_fn_start = FORM_JS.index("function resolveOfferVariant()")
    variant_fn_end = FORM_JS.index("var OFFER_VARIANT = resolveOfferVariant();")
    assert "if (!IS_CHECKOUT_RETURN) { return ''; }" in FORM_JS[variant_fn_start:variant_fn_end]

    src_fn_start = FORM_JS.index("function resolveEntrySrc()")
    src_fn_end = FORM_JS.index("var ENTRY_SRC = resolveEntrySrc();")
    assert "if (!IS_CHECKOUT_RETURN) { return ''; }" in FORM_JS[src_fn_start:src_fn_end]


def test_checkout_pending_marker_is_set_right_before_the_stripe_redirect():
    start = FORM_JS.index("if (result.checkout_url)")
    end = FORM_JS.index("window.location.href = result.checkout_url")
    block = FORM_JS[start:end]
    assert "sessionStorage.setItem(CHECKOUT_PENDING_KEY, '1');" in block


def test_entry_src_is_captured_distinct_from_entry_surface():
    """The /goals/ page's own entry surface (home/race) rides in as
    ?entry_src=, kept separate from ENTRY_SURFACE (always "goals" for a
    goals-funnel arrival here) so neither overwrites the other."""
    assert "ENTRY_SRC_KEY = 'gg_tp_entry_src'" in FORM_JS
    assert "ENTRY_SRC_RE = /^[a-z_]{1,24}$/" in FORM_JS
    assert "get('entry_src')" in FORM_JS
    assert "if (ENTRY_SRC) { payload.entry_src = ENTRY_SRC; }" in FORM_JS


def test_entry_surface_offer_variant_and_entry_src_forwarded_to_checkout_payload():
    """Task: entry src and offer variant must travel into checkout metadata
    if feasible. This repo's part is forwarding them on the /create-checkout
    POST body; the Railway checkout server (a separate repo) still has to
    read workerData.entry_surface / workerData.offer_variant /
    workerData.entry_src and write them into the Stripe Checkout Session
    metadata for a purchase to be attributable back to a variant."""
    start = FORM_JS.index("var workerData = mapToWorkerFormat(data);")
    end = FORM_JS.index("var response = await fetch(API_URL")
    block = FORM_JS[start:end]
    assert "workerData.entry_surface = ENTRY_SURFACE;" in block
    assert "if (OFFER_VARIANT) { workerData.offer_variant = OFFER_VARIANT; }" in block
    assert "if (ENTRY_SRC) { workerData.entry_src = ENTRY_SRC; }" in block
