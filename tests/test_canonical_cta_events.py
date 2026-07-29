"""Canonical plan-intent CTA instrumentation regression tests."""

import importlib.util
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))

from generate_state_hubs import build_state_page


def _load_preflight_quality():
    path = PROJECT_ROOT / "scripts" / "preflight_quality.py"
    spec = importlib.util.spec_from_file_location("preflight_quality_cta_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_state_hub_has_canonical_cta_click():
    html = build_state_page("Testland", [], 0)

    assert 'href="/questionnaire/"' in html
    assert "gtag('event', 'cta_click'" in html
    assert "source: 'state_hub'" in html
    assert "cta_name: el.getAttribute('data-cta')" in html


def test_prefixed_cta_variants_removed_from_generators():
    forbidden = (
        "about_cta_click",
        "coaching_cta_click",
        "consulting_cta_click",
        "guide_cta_click",
        "sidebar_cta_click",
        "insights_cta_click",
        "configurator_cta_click",
        "tp_cta_click",
        "whitepaper_cta_click",
    )
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PROJECT_ROOT / "wordpress").glob("generate_*.py")
    )

    for event_name in forbidden:
        assert event_name not in sources


def test_preflight_fails_closed_on_bare_questionnaire_cta(tmp_path):
    page = tmp_path / "synthetic" / "index.html"
    page.parent.mkdir()
    page.write_text(
        '<a href="/questionnaire/">Build my plan</a>',
        encoding="utf-8",
    )

    preflight = _load_preflight_quality()
    assert preflight.plan_intent_pages_missing_cta_click(tmp_path) == [page]


def test_preflight_accepts_canonical_questionnaire_cta(tmp_path):
    page = tmp_path / "synthetic" / "index.html"
    page.parent.mkdir()
    page.write_text(
        """
        <a href="/questionnaire/">Build my plan</a>
        <script>
        gtag('event', 'cta_click', {source: 'state_hub', cta_name: 'build'});
        </script>
        """,
        encoding="utf-8",
    )

    preflight = _load_preflight_quality()
    assert preflight.plan_intent_pages_missing_cta_click(tmp_path) == []
