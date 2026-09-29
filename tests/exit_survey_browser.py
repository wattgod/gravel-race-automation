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
PAGE_URL = "https://gravelgodcycling.com" + page_path("exit")
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


def submit_exit_survey(submission: dict | None = None, width: int = 390) -> dict:
    """Open the page from a personalised link, answer every question, submit.

    Returns the worker's JSON body, the FormSubmit backstop's raw body, the
    page errors, layout measurements taken before submitting, and the message
    the athlete saw.
    """
    from playwright.sync_api import sync_playwright

    submission = submission or load_submission()
    doc = generate_season_review_page("exit")
    captured: dict = {"worker": None, "formsubmit": None, "blocked": []}

    def handle(route):
        req = route.request
        if req.url.startswith(PAGE_URL):
            return route.fulfill(status=200, content_type="text/html; charset=utf-8", body=doc)
        for prefix, key, answer in ((LEAD_WORKER_URL, "worker", {"success": True}),
                                    (FORMSUBMIT_URL, "formsubmit", {"success": "true"})):
            if req.url.startswith(prefix):
                if req.method == "OPTIONS":
                    return route.fulfill(status=204, headers=CORS)
                captured[key] = json.loads(req.post_data) if key == "worker" else req.post_data
                return route.fulfill(status=200, headers={**CORS, "Content-Type": "application/json"},
                                     body=json.dumps(answer))
        captured["blocked"].append(req.url)
        return route.abort()

    link = PAGE_URL + "?" + urlencode({k: submission[k] for k in ("name", "email", "athlete")})
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            errors: list[str] = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.route("**/*", handle)
            page.goto(link)
            prefilled = {k: page.input_value(f"#{k}") for k in ("name", "email", "athlete")}
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
        "message": message,
        "message_class": message_class,
    }
