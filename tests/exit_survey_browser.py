"""Drive /coaching/exit/ in a real browser, the way an athlete would.

Shared by tests/test_exit_survey_playwright.py (the page on a 390px phone)
and mission_control/tests/test_athlete_exit.py (the same submission carried
through the worker into Mission Control). Nothing leaves the machine: the
page is served from memory and every outbound request is intercepted.

The answers come from tests/fixtures/exit_survey_submission.json, which holds
an obviously fake rider. This repo is public; keep it that way.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_season_review import (  # noqa: E402
    FORMSUBMIT_URL,
    LEAD_WORKER_URL,
    generate_season_review_page,
    page_path,
)
from season_review_variants import VARIANTS  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "exit_survey_submission.json"
SITE = "https://gravelgodcycling.com"
PAGE_URL = SITE + page_path("exit")
GTAG_URL = "https://www.googletagmanager.com/gtag/js"
# Stands in for gtag.js: records the address GA4 would send as page_location.
GTAG_STUB = "window.__gaPageLocation = window.location.href;"
# A personalised link with the attribution params around it, in mixed order,
# plus a hash: the page must remove name/email/athlete and keep the rest.
EXTRA_PARAMS = [("src", "exit_link"), ("utm_source", "coach_email"), ("utm_campaign", "fall%20exit")]
HASH = "#top"
ORIGIN = "https://gravelgodcycling.com"
CORS = {
    "Access-Control-Allow-Origin": ORIGIN,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Accept",
}


def has_playwright() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


def load_submission() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def personal_link(page_url: str, identity: dict) -> tuple[str, str]:
    """(the link Matti sends, the address that must remain after load)."""
    ident = [(k, urlencode({k: identity[k]}).split("=", 1)[1]) for k in ("name", "email", "athlete")]
    mixed = [EXTRA_PARAMS[0], ident[0], EXTRA_PARAMS[1], ident[1], ident[2], EXTRA_PARAMS[2]]
    query = "&".join(f"{k}={v}" for k, v in mixed)
    kept = "&".join(f"{k}={v}" for k, v in EXTRA_PARAMS)
    return f"{page_url}?{query}{HASH}", f"{page_url}?{kept}{HASH}"


def open_personal_link(slug: str, identity: dict) -> dict:
    """Open any season-review variant from a personalised link. Returns what
    the address bar and GA4 saw, and what the form was prefilled with."""
    from playwright.sync_api import sync_playwright

    url = SITE + page_path(slug)
    link, expected = personal_link(url, identity)
    doc = generate_season_review_page(slug)

    def handle(route):
        if route.request.url.startswith(url):
            return route.fulfill(status=200, content_type="text/html; charset=utf-8", body=doc)
        if route.request.url.startswith(GTAG_URL):
            return route.fulfill(status=200, content_type="text/javascript", body=GTAG_STUB)
        return route.abort()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            errors: list[str] = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.route("**/*", handle)
            page.goto(link)
            page.wait_for_function("() => window.__gaPageLocation !== undefined", timeout=10000)
            return {
                "expected": expected,
                "href": page.evaluate("() => window.location.href"),
                "ga_page_location": page.evaluate("() => window.__gaPageLocation"),
                "prefilled": {k: page.input_value(f"#{k}") for k in ("name", "email", "athlete")},
                "errors": errors,
            }
        finally:
            browser.close()


def exit_fields() -> list[dict]:
    """Every field on the exit form, pairs flattened, in page order."""
    out = []
    for sec in VARIANTS["exit"]["sections"]:
        for field in sec["fields"]:
            out.extend(field["fields"] if field["kind"] == "pair" else [field])
    return out


def _fill(page, answers: dict) -> None:
    for field in exit_fields():
        name, kind = field.get("name"), field["kind"]
        if kind in ("hidden", "note") or name in ("name", "email"):
            continue  # identity comes from the personalised link
        if kind == "checks":
            for key, _ in field["options"]:
                if answers.get(key) == "yes":
                    page.click(f'label.gg-apply-checkbox-option:has(input[name="{key}"])')
            continue
        value = answers.get(name)
        if value is None:
            continue
        if kind == "scale":
            # Keyboard only: Tab lands on the group, the arrows move along it.
            page.focus(f'input[name="{name}"][value="0"]')
            for _ in range(int(value)):
                page.keyboard.press("ArrowRight")
        elif kind == "radio":
            page.click(f'label.gg-apply-radio-option:has(input[name="{name}"][value="{value}"])')
        elif kind == "select":
            page.select_option(f"#{name}", value)
        else:
            page.fill(f"#{name}", value)


_LAYOUT_JS = """() => {
  const rects = (sel) => [...document.querySelectorAll(sel)].map((el) => el.getBoundingClientRect());
  const scale = rects('.gg-sr-scale-option');
  const share = rects('[data-radio="share_as"] .gg-apply-radio-option');
  const picked = document.querySelector('input[name="recommend"]:checked');
  return {
    innerWidth: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    scaleCount: scale.length,
    scaleTops: scale.map((r) => Math.round(r.top)),
    scaleLeft: Math.min(...scale.map((r) => r.left)),
    scaleRight: Math.max(...scale.map((r) => r.right)),
    scaleMinWidth: Math.min(...scale.map((r) => r.width)),
    scaleMinHeight: Math.min(...scale.map((r) => r.height)),
    shareLefts: share.map((r) => Math.round(r.left)),
    shareTops: share.map((r) => Math.round(r.top)),
    shareRight: Math.max(...share.map((r) => r.right)),
    // only the arrow keys ever touched the scale, so this proves them
    recommendPicked: picked ? picked.value : null,
  };
}"""


def submit_exit_survey(submission: dict | None = None, width: int = 390,
                       worker_status: int = 200) -> dict:
    """Open the page from a personalised link, answer every question, submit.

    Returns the worker's JSON body, anything posted to FormSubmit (the page
    is worker-only now, so that should be None), the page errors, layout
    measurements taken before submitting, and the message the athlete saw.
    worker_status is what the worker answers, to test a failed submit.
    """
    from playwright.sync_api import sync_playwright

    submission = submission or load_submission()
    doc = generate_season_review_page("exit")
    captured: dict = {"worker": None, "formsubmit": None, "blocked": []}

    def handle(route):
        req = route.request
        if req.url.startswith(PAGE_URL):
            return route.fulfill(status=200, content_type="text/html; charset=utf-8", body=doc)
        if req.url.startswith(GTAG_URL):
            return route.fulfill(status=200, content_type="text/javascript", body=GTAG_STUB)
        for prefix, key, status, answer in (
                (LEAD_WORKER_URL, "worker", worker_status,
                 {"success": True} if worker_status < 400 else {"error": "Storage unavailable"}),
                (FORMSUBMIT_URL, "formsubmit", 200, {"success": "true"})):
            if req.url.startswith(prefix):
                if req.method == "OPTIONS":
                    return route.fulfill(status=204, headers=CORS)
                captured[key] = json.loads(req.post_data) if key == "worker" else req.post_data
                return route.fulfill(status=status, headers={**CORS, "Content-Type": "application/json"},
                                     body=json.dumps(answer))
        captured["blocked"].append(req.url)
        return route.abort()

    link, expected_href = personal_link(PAGE_URL, submission)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            errors: list[str] = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.route("**/*", handle)
            page.goto(link)
            prefilled = {k: page.input_value(f"#{k}") for k in ("name", "email", "athlete")}
            page.wait_for_function("() => window.__gaPageLocation !== undefined", timeout=10000)
            address = {"expected": expected_href, "href": page.evaluate("() => window.location.href"),
                       "ga_page_location": page.evaluate("() => window.__gaPageLocation")}
            # typing past the 4000 the worker and Mission Control keep is stopped
            page.fill("#last_word", "x" * 4100)
            capped_len = len(page.input_value("#last_word"))
            _fill(page, submission["goal_answers"])
            layout = page.evaluate(_LAYOUT_JS)
            page.click("#submit-btn")
            page.wait_for_function(
                "() => document.getElementById('message').classList.contains('success')"
                " || document.getElementById('message').classList.contains('error')",
                timeout=15000,
            )
            message = page.inner_text("#message")
            message_class = page.get_attribute("#message", "class")
        finally:
            browser.close()
    return {
        "worker": captured["worker"],
        "formsubmit": captured["formsubmit"],
        "errors": errors,
        "layout": layout,
        "prefilled": prefilled,
        "address": address,
        "capped_len": capped_len,
        "message": message,
        "message_class": message_class,
    }
