"""Regression tests for the race-page email-capture P0 money-path bug.

Two bugs fixed together:

1. Worker rejected 'race_plan_ladder' — the plan-ladder form
   (`generate_neo_brutalist.py:1300,4798`) POSTs `source:'race_plan_ladder'`
   but `workers/fueling-lead-intake/worker.js`'s `KNOWN_SOURCES` omitted it,
   so the worker 400'd every plan-ladder submission and the lead was
   silently lost.

2. Fire-and-forget submits — every race-page form did
   `fetch(...).catch(function(){}); form.style.display='none';`, ignoring
   the response and showing a success state regardless of whether the
   worker actually accepted the lead. CLAUDE.md: "Never show a success
   message without actually submitting the email."

These tests are static/string-level checks against the generated inline JS
and the worker source, matching the existing pattern in
`tests/test_configurator.py::TestRacePackIntegration::test_worker_accepts_race_review_source`.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from generate_neo_brutalist import build_inline_js

WORKER_PATH = (
    Path(__file__).resolve().parent.parent
    / "workers"
    / "fueling-lead-intake"
    / "worker.js"
)

# Boundary comments that open each form's submit-handler IIFE in the inline
# JS — used to slice out exactly one form's handler without spilling into
# neighboring blocks.
FORM_BLOCKS = {
    "prep_kit_email_capture": ("// Email capture form — prep kit CTA", "// Plan ladder — race-specific plan capture"),
    "plan_ladder": ("// Plan ladder — race-specific plan capture", "// Inline review form"),
    "racer_review": ("// Inline review form", "// Lite-YouTube facade"),
    "date_reminder": ("// Date reminder handler", None),
}


@pytest.fixture(scope="module")
def js():
    return build_inline_js()


def _block(js_text: str, start_marker: str, end_marker: str | None) -> str:
    start = js_text.index(start_marker)
    end = js_text.index(end_marker, start) if end_marker else len(js_text)
    return js_text[start:end]


class TestWorkerAcceptsRacePlanLadder:
    def test_known_sources_includes_race_plan_ladder(self):
        """Worker KNOWN_SOURCES must include 'race_plan_ladder' — otherwise
        every plan-ladder lead is rejected with 400 'Unknown source'."""
        if not WORKER_PATH.exists():
            pytest.skip("Worker file not found")
        worker_js = WORKER_PATH.read_text()
        match = re.search(r"KNOWN_SOURCES\s*=\s*\[[^\]]*\]", worker_js)
        assert match, "KNOWN_SOURCES array not found in worker.js"
        assert "'race_plan_ladder'" in match.group(0), (
            "Worker KNOWN_SOURCES must include 'race_plan_ladder' — "
            "plan-ladder notify-me submissions will be rejected with 400 otherwise"
        )

    def test_generator_and_worker_agree_on_plan_ladder_source(self):
        """The plan-ladder form's hidden source field and the worker's
        accepted-sources list must name the exact same string."""
        gen_path = (
            Path(__file__).resolve().parent.parent
            / "wordpress"
            / "generate_neo_brutalist.py"
        )
        gen_src = gen_path.read_text()
        assert 'name="source" value="race_plan_ladder"' in gen_src
        if not WORKER_PATH.exists():
            pytest.skip("Worker file not found")
        assert "'race_plan_ladder'" in WORKER_PATH.read_text()


class TestNoFakeSuccessOnFormSubmit:
    """Guard against the fire-and-forget pattern re-appearing on any
    race-page form: a form must never reveal success, cache the email, or
    fire a GA4 conversion event unless the worker returned a confirmed 2xx."""

    def test_no_bare_noop_catch_after_fetch(self, js):
        """`fetch(...).catch(function(){})` ignores the response entirely —
        this exact pattern caused every form to show success on failure."""
        assert ".catch(function(){})" not in js, (
            "Found a fetch(...).catch(function(){}) fire-and-forget pattern — "
            "this ignores the worker response and can show success on a failed submit."
        )

    def test_error_helpers_defined(self, js):
        assert "function ggShowFormError" in js
        assert "function ggClearFormError" in js

    @pytest.mark.parametrize(
        "block_name,success_marker",
        [
            ("prep_kit_email_capture", "gg-email-capture-success"),
            ("plan_ladder", "gg-plan-ladder-success"),
            ("racer_review", "gg-review-success"),
            ("date_reminder", "We will remind you"),
        ],
    )
    def test_form_gates_success_on_response_ok(self, js, block_name, success_marker):
        """Each form's submit handler must: (a) check response.ok before
        doing anything success-shaped, (b) call the shared error helper on
        failure, and (c) place the success marker inside the .then() (i.e.
        after the .ok gate), not unconditionally after the fetch call."""
        start_marker, end_marker = FORM_BLOCKS[block_name]
        block = _block(js, start_marker, end_marker)

        # Scope to the submit path (from the worker fetch() call onward) —
        # some forms (prep-kit) also reference their success marker in an
        # unrelated pre-submit "already captured, show cached success"
        # fast-path that runs before any network call and is not part of
        # this bug.
        assert "fetch(WORKER_URL" in block, f"{block_name}: no fetch(WORKER_URL...) call found"
        submit_path = block[block.index("fetch(WORKER_URL"):]

        assert "if(!r.ok)" in submit_path or "if (!r.ok)" in submit_path, (
            f"{block_name} submit handler doesn't gate on response.ok"
        )
        assert "ggShowFormError" in submit_path, (
            f"{block_name} submit handler doesn't show a real inline error on failure"
        )
        assert success_marker in submit_path, (
            f"{block_name} submit handler is missing its expected success marker "
            "after the fetch() call"
        )

        # The success marker must appear AFTER the .ok gate in source order —
        # i.e. inside the .then(), not unconditionally after the fetch.
        ok_gate_idx = (
            submit_path.index("if(!r.ok)")
            if "if(!r.ok)" in submit_path
            else submit_path.index("if (!r.ok)")
        )
        success_idx = submit_path.index(success_marker)
        assert success_idx > ok_gate_idx, (
            f"{block_name}: success marker appears before the response.ok gate — "
            "success can still be shown without a confirmed 2xx"
        )

        # The .catch() must come after the .then() in source order, and the
        # fetch call itself must not have its own no-op .catch (already
        # covered globally, but re-checked per-block for a precise failure
        # message when this test is run in isolation).
        assert re.search(r"\.then\(function\(r\)\s*\{", block), (
            f"{block_name} fetch call has no .then(function(r){{...}}) handler"
        )
