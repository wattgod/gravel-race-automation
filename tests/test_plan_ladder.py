"""SITE-SYNC S2 — race-page "Train for this race" plan ladder block.

build_plan_ladder() renders the race's TP-SKU ladder from
../gravel-god-training-plans/db/plans.json (race_slug keyed):
- published + a live marketplace_url -> buy CTA
- everything else (private-ready, or published with no marketplace_url yet
  — the real state of every row as of this writing, S1 hasn't backfilled a
  single URL) -> email-gate "notify me" capture tagged with race_slug + tier
- no plans for the race -> '' (no empty shell)

Tests inject fixture data via monkeypatch on the module-level
_PLANS_BY_SLUG_CACHE dict instead of touching db/plans.json.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

import generate_neo_brutalist as gnb
from generate_neo_brutalist import build_inline_js, build_plan_ladder, get_page_css


def _rd(slug="test-race", name="Test Race"):
    return {"slug": slug, "name": name}


def _set_plans(monkeypatch, slug, plans):
    monkeypatch.setattr(gnb, "_PLANS_BY_SLUG_CACHE", {slug: plans})


def _plan(**overrides):
    base = {
        "tier": "Finisher",
        "length_wk": 8,
        "price": 79,
        "status": "private-ready",
        "marketplace_url": "",
    }
    base.update(overrides)
    return base


class TestNoPlans:
    def test_renders_nothing_when_no_plans_for_slug(self, monkeypatch):
        monkeypatch.setattr(gnb, "_PLANS_BY_SLUG_CACHE", {})
        html = build_plan_ladder(_rd(slug="no-such-race-plans-xyz"))
        assert html == ""

    def test_renders_nothing_when_db_missing(self, monkeypatch):
        """A missing/unreadable db/plans.json must degrade to no block,
        never crash the generator."""
        monkeypatch.setattr(gnb, "_PLANS_BY_SLUG_CACHE", None)
        monkeypatch.setattr(gnb, "PLANS_DB_PATH", Path("/nonexistent/plans.json"))
        html = build_plan_ladder(_rd(slug="whatever"))
        assert html == ""

    def test_disabled_by_config_flag(self, monkeypatch):
        _set_plans(monkeypatch, "test-race", [_plan()])
        monkeypatch.setattr(gnb, "PLAN_LADDER_ENABLED", False)
        html = build_plan_ladder(_rd())
        assert html == ""


class TestPublishedLinkCase:
    def test_published_with_url_renders_buy_cta(self, monkeypatch):
        _set_plans(monkeypatch, "test-race", [
            _plan(status="published", marketplace_url="https://www.trainingpeaks.com/plan/12345"),
        ])
        html = build_plan_ladder(_rd())
        assert 'id="plan-ladder"' in html
        assert 'href="https://www.trainingpeaks.com/plan/12345"' in html
        assert "Get the plan" in html
        assert 'data-cta="plan_ladder_buy"' in html
        assert 'target="_blank"' in html and 'rel="noopener"' in html
        # No email-gate form for this row
        assert "gg-plan-ladder-form" not in html

    def test_tier_length_price_rendered(self, monkeypatch):
        _set_plans(monkeypatch, "test-race", [
            _plan(status="published", marketplace_url="https://tp.example/x",
                  tier="Compete", length_wk=12, price=99),
        ])
        html = build_plan_ladder(_rd())
        assert "Compete" in html
        assert "12 wk" in html
        assert "$99" in html


class TestEmailGateCase:
    def test_private_plan_renders_notify_form(self, monkeypatch):
        _set_plans(monkeypatch, "test-race", [
            _plan(status="private-ready", marketplace_url=""),
        ])
        html = build_plan_ladder(_rd())
        assert 'class="gg-plan-ladder-form"' in html
        assert "Get notified" in html
        assert 'name="email"' in html
        # No buy CTA
        assert 'data-cta="plan_ladder_buy"' not in html

    def test_notify_payload_tagged_with_race_slug_and_tier(self, monkeypatch):
        _set_plans(monkeypatch, "big-sugar", [
            _plan(status="private-ready", tier="Save My Race"),
        ])
        html = build_plan_ladder(_rd(slug="big-sugar", name="Big Sugar Gravel"))
        assert '<input type="hidden" name="race_slug" value="big-sugar">' in html
        assert '<input type="hidden" name="tier" value="Save My Race">' in html
        assert '<input type="hidden" name="source" value="race_plan_ladder">' in html

    def test_honeypot_field_present(self, monkeypatch):
        _set_plans(monkeypatch, "test-race", [_plan()])
        html = build_plan_ladder(_rd())
        assert '<input type="hidden" name="website" value="">' in html


class TestMarketplaceUrlEmptyFallsBack:
    def test_published_without_marketplace_url_falls_back_to_email_gate(self, monkeypatch):
        """Real current state of every row in db/plans.json: status is
        'published' but S1 (browser backfill) hasn't landed a single
        marketplace_url yet. Must NOT render a dead/empty buy link."""
        _set_plans(monkeypatch, "test-race", [
            _plan(status="published", marketplace_url=""),
        ])
        html = build_plan_ladder(_rd())
        assert 'data-cta="plan_ladder_buy"' not in html
        assert 'href=""' not in html
        assert "gg-plan-ladder-form" in html
        assert "Get notified" in html

    def test_published_with_whitespace_only_url_falls_back(self, monkeypatch):
        _set_plans(monkeypatch, "test-race", [
            _plan(status="published", marketplace_url="   "),
        ])
        html = build_plan_ladder(_rd())
        assert 'data-cta="plan_ladder_buy"' not in html
        assert "Get notified" in html


class TestMultiRowLadder:
    def test_mixed_published_and_private_rows(self, monkeypatch):
        _set_plans(monkeypatch, "gunni-grinder", [
            _plan(tier="Finisher", length_wk=8, price=79,
                  status="published", marketplace_url="https://tp.example/finisher"),
            _plan(tier="Time-Crunched", length_wk=8, price=79,
                  status="private-ready", marketplace_url=""),
            _plan(tier="Save My Race", length_wk=6, price=69,
                  status="published", marketplace_url=""),
        ])
        html = build_plan_ladder(_rd(slug="gunni-grinder", name="Gunnison Growler Gravel Grinder"))
        assert html.count('class="gg-plan-ladder-row"') == 3
        assert html.count('data-cta="plan_ladder_buy"') == 1
        assert html.count('class="gg-plan-ladder-form"') == 2

    def test_sorted_longest_plan_first(self, monkeypatch):
        _set_plans(monkeypatch, "test-race", [
            _plan(tier="Save My Race", length_wk=6, price=69),
            _plan(tier="Finisher", length_wk=12, price=99),
            _plan(tier="Finisher", length_wk=8, price=79),
        ])
        html = build_plan_ladder(_rd())
        first_row = html.split('class="gg-plan-ladder-row"')[1]
        assert "12 wk" in first_row


class TestSafety:
    def test_no_inline_handlers(self, monkeypatch):
        _set_plans(monkeypatch, "test-race", [_plan()])
        html = build_plan_ladder(_rd())
        assert "onclick=" not in html
        assert "onsubmit=" not in html

    def test_race_name_and_tier_escaped(self, monkeypatch):
        _set_plans(monkeypatch, "test-race", [
            _plan(tier='Evil <script>alert(1)</script>'),
        ])
        html = build_plan_ladder(_rd(name='Evil "Race" <script>alert(1)</script>'))
        assert "<script>" not in html.replace("</script>", "")
        assert "&lt;script&gt;" in html

    def test_malformed_row_skipped_not_crashed(self, monkeypatch):
        _set_plans(monkeypatch, "test-race", [
            {"tier": "Finisher", "length_wk": "not-a-number", "price": 79,
             "status": "private-ready", "marketplace_url": ""},
            _plan(tier="Time-Crunched"),
        ])
        html = build_plan_ladder(_rd())
        assert html.count('class="gg-plan-ladder-row"') == 1
        assert "Time-Crunched" in html


class TestJsAndCssPresent:
    def test_css_uses_tokens_only(self):
        css = get_page_css()
        assert ".gg-plan-ladder-row" in css
        assert ".gg-plan-ladder-btn" in css

    def test_js_targets_form_class_and_worker(self):
        js = build_inline_js()
        assert "gg-plan-ladder-form" in js
        assert "fueling-lead-intake.gravelgodcoaching.workers.dev" in js

    def test_js_uses_addeventlistener(self):
        js = build_inline_js()
        # The plan-ladder handler block specifically
        idx = js.index("gg-plan-ladder-form")
        snippet = js[idx:idx + 1200]
        assert "addEventListener('submit'" in snippet


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
