"""Integrity checks for the deployed training-plan form script."""
import json
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).parent.parent
FORM_JS = (ROOT / "web" / "training-plans-form.js").read_text()
FORM_HTML = (ROOT / "web" / "training-plans-questionnaire.html").read_text()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


def _questionnaire_page(browser, questionnaire_date=None, index_available=True, width=1024):
    page = browser.new_page(viewport={"width": width, "height": 900})
    captured = []
    document = '<meta charset="utf-8">' + FORM_HTML + (
        '<script src="/wp-content/uploads/training-plans-form.js"></script>'
    )

    def serve(route):
        url = route.request.url
        if url == "https://questionnaire.test/?race=big-sugar":
            route.fulfill(status=200, content_type="text/html", body=document)
        elif url.endswith("/training-plans-form.js"):
            route.fulfill(status=200, content_type="application/javascript", body=FORM_JS)
        elif url.endswith("/race-index.json"):
            if index_available:
                route.fulfill(
                    status=200,
                    content_type="application/json",
                    body=json.dumps([{
                        "slug": "big-sugar",
                        "name": "Big Sugar Gravel",
                        **(
                            {"questionnaire_date": questionnaire_date}
                            if questionnaire_date is not None
                            else {}
                        ),
                    }]),
                )
            else:
                route.fulfill(status=503, body="unavailable")
        elif url.endswith("/api/create-checkout"):
            captured.append(json.loads(route.request.post_data or "{}"))
            route.fulfill(
                status=400,
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
                body=json.dumps({"error": "local test stop"}),
            )
        else:
            route.abort()

    page.route("**/*", serve)
    page.goto("https://questionnaire.test/?race=big-sugar")
    page.wait_for_function(
        "document.querySelector('[name=\"race_0_name\"]')?.value.length > 0"
    )
    return page, captured


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


def test_verified_race_date_prefills_and_serializes_to_checkout(browser):
    page, captured = _questionnaire_page(
        browser, "2099-10-17"
    )
    try:
        assert page.locator('[name="race_0_name"]').input_value() == "Big Sugar Gravel"
        assert page.locator('[name="race_0_date"]').input_value() == "2099-10-17"
        assert page.locator('[name="race_0_priority"]').input_value() == "A"
        assert "$" in page.locator(".gg-submit-btn").inner_text()

        page.locator('[name="travelDuringPlan"]').select_option("short")
        assert page.locator("#travelDatesGroup").is_visible()

        page.evaluate(
            "document.querySelector('#gg-training-form').dispatchEvent("
            "new Event('submit', {bubbles: true, cancelable: true}))"
        )
        page.wait_for_function("document.querySelector('#gg-form-message').textContent.length > 0")
        assert len(captured) == 1
        assert captured[0]["race_name"] == "Big Sugar Gravel"
        assert captured[0]["race_date"] == "2099-10-17"
        assert captured[0]["race_slug"] == "big-sugar"
        assert captured[0]["races"] == [{
            "name": "Big Sugar Gravel",
            "date": "2099-10-17",
            "distance": "",
            "goal": "",
            "priority": "A",
        }]
    finally:
        page.close()


def test_unknown_race_date_stays_blank(browser):
    page, _ = _questionnaire_page(browser)
    try:
        assert page.locator('[name="race_0_name"]').input_value() == "Big Sugar Gravel"
        assert page.locator('[name="race_0_date"]').input_value() == ""
        assert page.locator('[name="race_0_priority"]').input_value() == "A"
        assert page.locator(".gg-submit-btn").text_content() == "Submit & Pay"
    finally:
        page.close()


def test_race_index_failure_preserves_date_and_name_fallback(browser):
    page, _ = _questionnaire_page(
        browser,
        "2099-10-17",
        index_available=False,
    )
    try:
        assert page.locator('[name="race_0_name"]').input_value() == "Big Sugar"
        assert page.locator('[name="race_0_date"]').input_value() == ""
        assert page.locator('[name="race_0_priority"]').input_value() == "A"
    finally:
        page.close()


def test_past_race_date_stays_blank(browser):
    page, _ = _questionnaire_page(browser, "2020-10-17")
    try:
        assert page.locator('[name="race_0_name"]').input_value() == "Big Sugar Gravel"
        assert page.locator('[name="race_0_date"]').input_value() == ""
        assert page.locator(".gg-submit-btn").text_content() == "Submit & Pay"
    finally:
        page.close()
