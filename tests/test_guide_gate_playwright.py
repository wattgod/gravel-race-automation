"""The gravel guide's chapter gate in a real browser.

FormSubmit stopped delivering (2026-09-29), so the gate posts the email to the
lead worker and unlocks the chapter only once the worker has it. The page is
the real gate markup and the real cluster script, served from memory; every
outbound request is intercepted. Skipped without Playwright.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from guide_configs import LEAD_INTAKE_WORKER_URL  # noqa: E402


def _has_playwright() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(not _has_playwright(), reason="playwright not installed")

PAGE_URL = "https://gravelgodcycling.com/guide/workout-execution/"
CORS = {
    "Access-Control-Allow-Origin": "https://gravelgodcycling.com",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _page_html() -> str:
    from generate_guide_cluster import build_chapter_gate, build_cluster_js
    gate = build_chapter_gate({"title": "Workout Execution", "id": "workout-execution", "number": 4})
    return f"""<!doctype html><html><head><meta charset="utf-8"></head><body>
{gate}
<div class="gg-cluster-gated-content" style="display:none"><p id="chapter">The chapter.</p></div>
<script>{build_cluster_js()}</script>
</body></html>"""


def _submit(worker_status: int = 200, honeypot: bool = False) -> dict:
    from playwright.sync_api import sync_playwright

    doc = _page_html()
    seen: dict = {"worker": [], "other": []}

    def handle(route):
        req = route.request
        if req.url == PAGE_URL:
            return route.fulfill(status=200, content_type="text/html; charset=utf-8", body=doc)
        if req.url.startswith(LEAD_INTAKE_WORKER_URL):
            if req.method == "OPTIONS":
                return route.fulfill(status=204, headers=CORS)
            seen["worker"].append(json.loads(req.post_data))
            body = {"success": True} if worker_status < 400 else {"error": "Invalid email format"}
            return route.fulfill(status=worker_status, headers={**CORS, "Content-Type": "application/json"},
                                 body=json.dumps(body))
        seen["other"].append(f"{req.method} {req.url}")
        return route.abort()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.route("**/*", handle)
            page.goto(PAGE_URL)
            page.fill("input[name=email]", "test.reader@example.com")
            if honeypot:
                page.evaluate("() => { document.querySelector('#gg-cluster-gate-form [name=website]').value = 'x'; }")
            page.click("#gg-cluster-gate-form button[type=submit]")
            if honeypot:
                page.wait_for_timeout(500)
            else:
                page.wait_for_function(
                    "() => document.getElementById('gg-guide-gate').style.display === 'none'"
                    " || !!document.getElementById('gg-cluster-gate-error')", timeout=10000)
            error = page.query_selector("#gg-cluster-gate-error")
            state = {
                "url": page.url,
                "gate_hidden": page.evaluate("() => document.getElementById('gg-guide-gate').style.display === 'none'"),
                "chapter_visible": page.is_visible("#chapter"),
                "unlocked": page.evaluate("() => localStorage.getItem('gg_guide_unlocked')"),
                "error": error.inner_text() if error and error.is_visible() else None,
                "button_disabled": page.is_disabled("#gg-cluster-gate-form button[type=submit]"),
            }
        finally:
            browser.close()
    return {**seen, **state, "errors": errors}


def test_the_worker_gets_the_lead_and_the_chapter_unlocks_in_place():
    run = _submit()
    assert run["worker"] == [{"email": "test.reader@example.com", "source": "training_guide",
                              "website": "", "guide_chapter": "Workout Execution"}]
    assert run["gate_hidden"] and run["chapter_visible"] and run["unlocked"] == "1"
    assert run["url"] == PAGE_URL  # no redirect through a form service
    assert run["other"] == [] and run["errors"] == []


def test_a_failed_submit_never_unlocks_and_says_so():
    run = _submit(worker_status=400)
    assert len(run["worker"]) == 1
    assert not run["gate_hidden"] and not run["chapter_visible"] and run["unlocked"] is None
    assert run["error"] == "That did not go through. Check your connection and try again."
    assert not run["button_disabled"]  # they can try again
    assert run["other"] == [] and run["errors"] == []


def test_a_filled_honeypot_sends_nothing_and_unlocks_nothing():
    run = _submit(honeypot=True)
    assert run["worker"] == []
    assert not run["gate_hidden"] and run["unlocked"] is None
    assert run["other"] == [] and run["errors"] == []
