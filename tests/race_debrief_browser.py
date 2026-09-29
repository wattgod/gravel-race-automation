"""Drive /race-debrief/ in a real browser, the way a plan buyer would.

Shared by tests/test_race_debrief_playwright.py (the page on a 390px phone)
and mission_control/tests/test_plan_debrief.py (the same submission carried
through the worker into Mission Control). Nothing leaves the machine: the
page is served from memory and every outbound request is intercepted.

The answers come from tests/fixtures/race_debrief_submission.json, which
holds an obviously fake rider and a made-up planId. This repo is public.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_season_review import (  # noqa: E402
    FORMSUBMIT_URL,
    LEAD_WORKER_URL,
    generate_season_review_page,
    page_path,
)
from season_review_variants import VARIANTS  # noqa: E402
from tests.exit_survey_browser import CORS, GTAG_URL, has_playwright  # noqa: E402,F401

FIXTURE = ROOT / "tests" / "fixtures" / "race_debrief_submission.json"
SITE = "https://gravelgodcycling.com"
PAGE_URL = SITE + page_path("race_debrief")
GTAG_STUB = "window.__gaLoaded = true;"


def load_submission() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def debrief_fields() -> list[dict]:
    """Every field on the debrief form, pairs flattened, in page order."""
    out = []
    for sec in VARIANTS["race_debrief"]["sections"]:
        for field in sec["fields"]:
            out.extend(field["fields"] if field["kind"] == "pair" else [field])
    return out


def fill(page, answers: dict) -> None:
    """Answer every question the way a rider would; the 0-10 scale by the
    keyboard only."""
    for field in debrief_fields():
        name, kind = field.get("name"), field["kind"]
        if kind in ("hidden", "note"):
            continue
        if kind == "checks":
            for key, _ in field["options"]:
                if answers.get(key) == "yes":
                    page.click(f'label.gg-apply-checkbox-option:has(input[name="{key}"])')
            continue
        value = answers.get(name)
        if value is None:
            continue
        if kind == "scale":
            page.focus(f'input[name="{name}"][value="0"]')
            for _ in range(int(value)):
                page.keyboard.press("ArrowRight")
        elif kind == "radio":
            page.click(f'label.gg-apply-radio-option:has(input[name="{name}"][value="{value}"])')
        elif kind == "select":
            page.select_option(f"#{name}", value)
        else:
            page.fill(f"#{name}", value)


LAYOUT_JS = """() => {
  const rects = (sel) => [...document.querySelectorAll(sel)].map((el) => el.getBoundingClientRect());
  const scale = rects('.gg-sr-scale-option');
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
    recommendPicked: picked ? picked.value : null,
  };
}"""

# Every gtag("event", ...) the page made, as [name, params].
EVENTS_JS = """() => (window.dataLayer || [])
  .map((a) => Array.prototype.slice.call(a))
  .filter((a) => a[0] === 'event')
  .map((a) => [a[1], a[2] || {}])"""

RATING_JS = """() => {
  const p = document.getElementById('tp-rating');
  const a = document.getElementById('tp-rating-link');
  return p ? { hidden: p.hidden, visible: !!(p.offsetWidth || p.offsetHeight), text: p.textContent,
               href: a.getAttribute('href') } : null;
}"""


def run_debrief(query: str = "", submission: dict | None = None, width: int = 390, *,
                worker_status: int = 200, answers: dict | None = None) -> dict:
    """Open the page at PAGE_URL + query, answer everything (or just
    `answers`), submit.

    Returns the worker's JSON body, whether FormSubmit was called, the page
    errors, the layout before submitting, the GA4 events, the rating line and
    the message the rider saw.
    """
    from playwright.sync_api import sync_playwright

    submission = submission or load_submission()
    doc = generate_season_review_page("race_debrief")
    page_url = PAGE_URL
    cors = CORS
    captured: dict = {"worker": None, "formsubmit": False, "blocked": []}

    def handle(route):
        req = route.request
        if req.url.startswith(page_url):
            return route.fulfill(status=200, content_type="text/html; charset=utf-8", body=doc)
        if req.url.startswith(GTAG_URL):
            return route.fulfill(status=200, content_type="text/javascript", body=GTAG_STUB)
        if req.url.startswith(FORMSUBMIT_URL):
            captured["formsubmit"] = True
            return route.abort()
        if req.url.startswith(LEAD_WORKER_URL):
            if req.method == "OPTIONS":
                return route.fulfill(status=204, headers=cors)
            captured["worker"] = json.loads(req.post_data)
            return route.fulfill(status=worker_status, headers={**cors, "Content-Type": "application/json"},
                                 body=json.dumps({"success": worker_status == 200}))
        captured["blocked"].append(req.url)
        return route.abort()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            errors: list[str] = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.route("**/*", handle)
            page.goto(page_url + query)
            events_before = page.evaluate(EVENTS_JS)
            hidden = page.evaluate("() => ({plan: (document.getElementById('plan') || {}).value,"
                                   " ref: (document.getElementById('ref') || {}).value})")
            page.fill("#name", submission["name"])
            page.fill("#email", submission["email"])
            # typing past the 4000 the worker and Mission Control keep is stopped
            page.fill("#last_word", "x" * 4100)
            capped = len(page.input_value("#last_word"))
            page.fill("#last_word", "")
            fill(page, submission["goal_answers"] if answers is None else answers)
            layout = page.evaluate(LAYOUT_JS)
            page.click("form button[type=submit]")
            page.wait_for_function(
                "() => { const m = document.getElementById('message');"
                " return m.classList.contains('success') || m.classList.contains('error'); }",
                timeout=15000,
            )
            message = page.inner_text("#message")
            message_class = page.get_attribute("#message", "class")
            rating = page.evaluate(RATING_JS)
            events = page.evaluate(EVENTS_JS)
            href = page.evaluate("() => window.location.href")
        finally:
            browser.close()
    return {
        "worker": captured["worker"],
        "formsubmit": captured["formsubmit"],
        "errors": errors,
        "layout": layout,
        "hidden": hidden,
        "capped_len": capped,
        "events_before": events_before,
        "events": events,
        "rating": rating,
        "href": href,
        "message": message,
        "message_class": message_class,
    }
