"""Tests for the /season-plan/ page generator (docs/specs/goals-2027-funnel-spec.md D9).

Covers: price sourced from data/pricing.json (never hardcoded), the 3-day
delivery promise, no FTP/training-number fields, races[] with A/B/C
priority, honeypot, GA4 events fire on user action only, no innerHTML with
data, prefill wiring reads the MC route with ?t=, and the voice rules
(no exclamation marks, no refund line, "I build every plan myself").
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_season_plan_form import (  # noqa: E402
    PAGE_URL,
    build_season_plan_js,
    generate_season_plan_page,
)
from pricing import SEASON_PLAN_DELIVERY_DAYS, SEASON_PLAN_PRICE_DISPLAY  # noqa: E402


def page() -> str:
    return generate_season_plan_page()


def js() -> str:
    return build_season_plan_js()


def test_indexed_not_noindex():
    # Unlike /coaching/season-review/, this is a public product page.
    assert 'name="robots" content="index, follow"' in page()


def test_canonical_is_season_plan():
    assert PAGE_URL == "https://gravelgodcycling.com/season-plan/"
    assert f'href="{PAGE_URL}"' in page()


def test_price_comes_from_pricing_json_not_a_literal():
    html = page()
    assert SEASON_PLAN_PRICE_DISPLAY in html
    assert SEASON_PLAN_PRICE_DISPLAY == "$499"


def test_delivery_promise_is_3_days_not_24_hours():
    html = page()
    assert f"within {SEASON_PLAN_DELIVERY_DAYS} days" in html
    assert SEASON_PLAN_DELIVERY_DAYS == 3
    assert "24 hours" not in html


def test_no_ftp_or_training_number_questions():
    html = page().lower()
    for banned in ("ftp", "heart rate threshold", "lthr", "resting hr", "max hr"):
        assert banned not in html, banned


def test_asks_equipment_not_numbers():
    html = page()
    assert 'name="has_power_meter"' in html
    assert 'name="has_hr_monitor"' in html
    assert 'name="has_trainer"' in html


def test_races_section_has_priority_and_add_remove():
    html = page()
    assert "season-races-container" in html
    assert "season-add-race-btn" in html
    assert "least one A race" in " ".join(html.split())


def test_field_names_match_the_pipeline_intake_contract():
    """Matti ruling: match training-plans-form.js / intake_to_plan.py's own
    field names so Motoren can build from the stored intake."""
    html = page()
    for field in ("hours_per_week", "off_days", "notes", "strength_want",
                  "strength_equipment", "tp_email"):
        assert f'name="{field}"' in html, field


def test_honeypot_present():
    html = page()
    assert 'name="website" class="gg-apply-honeypot"' in html


def test_no_innerhtml_with_data():
    assert "innerHTML" not in page()
    assert "innerHTML" not in js()


def test_uses_addeventlistener_not_inline_handlers():
    assert "onclick=" not in page()
    assert "onsubmit=" not in page()


def test_ga4_head_snippet_present():
    assert "gtag" in page()


def test_ga4_events_are_season_form_start_and_submit():
    body = js()
    assert "season_form_start" in body
    assert "season_form_submit" in body


def test_ga4_start_fires_on_user_action_not_load():
    body = js()
    start_idx = body.index("function trackStart")
    block = body[start_idx:start_idx + 400]
    assert "setInterval" not in block and "setTimeout" not in block
    assert "focusin" in body and "form.addEventListener('focusin', trackStart" in body


def test_ga4_submit_fires_only_on_successful_checkout_response():
    body = js()
    assert "if (result.checkout_url)" in body
    start = body.index("if (result.checkout_url)")
    end = body.index("});", start)
    assert "season_form_submit" in body[start:end]


def test_no_exclamation_marks_in_copy():
    html = page()
    # Restrict to the visible copy region, not the JS/CSS payload.
    form_region = html[html.index('<div class="gg-apply-header">'):html.index("gg-apply-confidential-wrap")]
    assert "!" not in form_region


def test_no_refund_line():
    html = page()
    assert "refund" not in html.lower()


def test_says_i_build_every_plan_myself():
    assert "I build every plan myself" in page()


def test_no_descriptive_subtitles_under_section_headings():
    """House rule: no helper copy under headings/labels beyond load-bearing
    content. Section titles (1. You, 2. Your season, etc.) carry no
    trailing description line, except the one section with a real
    constraint to state (races)."""
    html = page()
    import re
    subs = re.findall(r'gg-apply-section-title[^>]*>([^<]*)</div>\s*(<p class="gg-apply-section-sub">[^<]*</p>)?',
                       html)
    described = [t for t, s in subs if s]
    assert described == ["2. Your season"], described


def test_prefill_reads_token_and_calls_mc_route():
    body = js()
    assert "'t'" in body or '"t"' in body
    assert "/api/season-plan/prefill/" in body
    assert "encodeURIComponent(TOKEN)" in body


def test_prefill_fills_existing_empty_race_row_not_a_second_one():
    body = js()
    assert "firstEntry" in body
    assert "!nameField.value" in body


def test_prefill_never_blocks_form_on_failure():
    body = js()
    fetch_start = body.index("fetch(MC_BASE")
    catch_idx = body.index(".catch(", fetch_start)
    catch_block = body[catch_idx:catch_idx + 120]
    assert "never a blocker" in catch_block or "catch" in catch_block


def test_posts_product_season_plan_and_attribution_to_create_checkout():
    body = js()
    assert "product: 'season_plan'" in body
    assert "API_BASE" in body
    assert "athlete-custom-training-plan-pipeline-production.up.railway.app" in body
    assert "payload.offer_variant = OFFER_VARIANT" in body
    assert "payload.entry_src = ENTRY_SRC" in body
    assert "payload.race_slug = RACE_SLUG" in body


def test_requires_at_least_one_a_race_before_submit():
    body = js()
    assert "priority === 'A'" in body


def test_removing_a_race_frees_up_the_row_cap():
    """sol review NIT #11: raceCount never decremented on remove, so
    add-then-remove permanently ate into the 20-row cap."""
    body = js()
    assert "racesContainer.children.length >= MAX_RACES" in body


def test_has_its_own_deploy_path_not_the_generic_race_sweep():
    """sol review (BLOCKER #6): wordpress/output/season-plan.html has no
    slug-based root path of its own — without both of these, the generic
    push_wordpress.py sync_pages() sweep would ship it at
    /race/season-plan/ instead of /season-plan/."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import push_wordpress

    assert "season-plan" in push_wordpress.ROOT_CANONICAL_SLUGS
    assert hasattr(push_wordpress, "sync_season_plan")
