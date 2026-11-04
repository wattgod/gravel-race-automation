"""The real race-page output must contain a safe, usable Endure Labs handoff."""

import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlencode, urlparse

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_neo_brutalist import generate_page, normalize_race_data, _extract_css_content
from race_calculator import ENDURE_CALCULATOR_URL, build_race_calculator, get_race_calculator_css, race_calculator_context
from brand_tokens import get_tokens_css
from shared_header import get_site_header_js
from slop_rules import check_text


class Tags(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def matching(self, tag):
        return [attrs for found, attrs in self.tags if found == tag]


def raw_race():
    data = json.loads((ROOT / "race-data" / "barry-roubaix.json").read_text())
    # Explicit fixture edition; no test depends on today's calendar year.
    data["race"]["vitals"]["date_specific"] = "2026: April 18"
    return data


def page(data=None, **kwargs):
    return generate_page(normalize_race_data(data or raw_race()), **kwargs)


def calculator(text):
    match = re.search(r'<section id="race-calculator"[\s\S]*?</section>', text)
    assert match, "production output omitted calculator"
    return match.group(0)


def handoff(text):
    tags = Tags(calculator(text))
    form = tags.matching("form")[0]
    values = {item["name"]: item["value"] for item in tags.matching("input") if item.get("name")}
    options = tags.matching("option")
    if options:
        values["distance"] = options[0]["value"]
    return form, values


def test_actual_page_mounts_calculator_in_deep_content_and_toc():
    text = page()
    assert text.index('id="race-calculator"') > text.index('id="deep-dive"')
    assert 'href="#race-calculator" data-toc-target="race-calculator"' in text
    assert 'id="prep-strip"' not in text
    assert text.count('id="race-calculator"') == 1


def test_actual_form_preserves_exact_primary_identity_without_health_values():
    form, values = handoff(page())
    assert form["action"] == ENDURE_CALCULATOR_URL
    assert form["method"] == "get"
    assert values == {"source": "gravel", "race": "barry-roubaix", "edition": "2026", "distance": "62-mile"}
    url = form["action"] + "?" + urlencode(values)
    assert urlparse(url).netloc == "endurelabs.app"
    assert parse_qs(urlparse(url).query)["distance"] == ["62-mile"]
    assert set(values) == {"source", "race", "edition", "distance"}
    assert not Tags(calculator(page())).matching("iframe")


def test_source_edition_is_used_even_when_a_different_year_appears_later():
    data = raw_race()
    data["race"]["vitals"]["date_specific"] = "2027: April 17; the 2026 edition already ran"
    assert handoff(page(data))[1]["edition"] == "2027"


@pytest.mark.parametrize("value", ["TBD", "Mid-April annually", "", None, "Next edition pending; 2025 was the previous race"])
def test_unknown_edition_is_not_replaced_with_current_year(value):
    data = raw_race()
    data["race"]["vitals"]["date_specific"] = value or ""
    assert "edition" not in handoff(page(data))[1]


def test_source_blocked_profile_does_not_handoff_its_historical_edition_or_distance():
    data = raw_race()
    data["race"]["vitals"]["course_status"] = "source_blocked"
    fragment = calculator(page(data))
    assert handoff(page(data))[1] == {"source": "gravel", "race": "barry-roubaix"}
    assert "Confirm this race&#x27;s edition and course file" in fragment


def test_card_exists_without_a_race_pack():
    data = raw_race()
    data["race"]["slug"] = "race-without-a-pack"
    text = page(data)
    assert handoff(text)[1]["race"] == "race-without-a-pack"
    assert 'id="race-calculator"' in text



def test_calculator_stays_available_when_training_marketing_is_suppressed():
    for condition in ("source_blocked", "taking_a_break", "ineligible"):
        rd = normalize_race_data(raw_race())
        if condition == "source_blocked":
            rd["vitals"]["course_status"] = "source_blocked"
        elif condition == "taking_a_break":
            rd["taking_a_break"] = {"label": "PAUSED", "line": "The next edition is unconfirmed."}
        else:
            rd["race_plan_eligible"] = False
        text = generate_page(rd)
        assert 'data-plan-marketing="suppressed"' in text
        assert 'data-toc-target="train-for-race"' not in text
        assert 'data-toc-target="race-calculator">08a Race Calculator</a>' in text
        assert handoff(text)[0]["action"] == ENDURE_CALCULATOR_URL


def test_structured_variant_keys_and_decimal_distances_survive_actual_generation():
    data = raw_race()
    data["race"]["distances"] = [
        {"key": "short-course", "name": "Short", "distance_mi": 18},
        {"key": "wafer", "name": "Wafer", "distance_mi": 66.5},
        {"key": "long-course", "name": "Long", "distance_mi": 100},
    ]
    fragment = calculator(page(data))
    assert [x["value"] for x in Tags(fragment).matching("option")] == ["short-course", "wafer", "long-course"]
    assert "66.5 mi" in fragment
    assert len(Tags(fragment).matching("select")) == 1


def test_secondary_variant_choice_is_native_form_state_not_a_fixed_link():
    data = raw_race()
    data["race"]["distances"] = [{"slug": "short", "distance_mi": 18}, {"slug": "long", "distance_mi": 100}]
    tags = Tags(calculator(page(data)))
    assert tags.matching("select")[0]["name"] == "distance"
    assert tags.matching("option")[1]["value"] == "long"
    assert tags.matching("button")[0]["type"] == "submit"
    assert not tags.matching("script")


def test_name_is_text_and_never_changes_the_destination():
    data = raw_race()
    data["race"]["display_name"] = 'Race </p><script>alert("name")</script><img src=x onerror=alert(1)>'
    fragment = calculator(page(data))
    assert "&lt;script&gt;" in fragment
    assert not Tags(fragment).matching("script")
    assert not Tags(fragment).matching("img")
    assert handoff(page(data))[0]["action"] == ENDURE_CALCULATOR_URL


@pytest.mark.parametrize("slug", ['other&power=300', '../other', 'race" autofocus', 'https://elsewhere.test', None])
def test_unsafe_slug_downgrades_to_generic_calculator_without_context(slug):
    fragment = build_race_calculator({"name": "Unknown", "slug": slug, "vitals": {"date_specific": "2026: April 18", "distance_mi": 62}})
    form, values = handoff(fragment)
    assert form["action"] == ENDURE_CALCULATOR_URL
    assert values == {"source": "gravel"}


def test_bad_distance_keys_and_labels_cannot_inject_markup_or_query_fields():
    data = raw_race()
    data["race"]["distances"] = [{"key": 'long&weight=100', "name": '</option><script>bad()</script>', "distance_mi": 100}]
    fragment = calculator(page(data))
    assert Tags(fragment).matching("option")[0]["value"] == "100-mile"
    assert not Tags(fragment).matching("script")
    assert "&lt;script&gt;" in fragment
    assert "weight" not in handoff(fragment)[1]


def test_unknown_or_prose_distances_are_not_guessed():
    context = race_calculator_context({"slug": "test", "vitals": {"distance_mi": "30-60"}, "distances": ["38.5, 25.8 and 13.6 miles in 2026", {}, None, 50]})
    assert context["distances"] == []
    form, values = handoff(build_race_calculator({"name": "Test", "calculator": context}))
    assert "distance" not in values
    assert form["action"] == ENDURE_CALCULATOR_URL


def test_explicit_units_work_without_converting_or_changing_source_keys():
    context = race_calculator_context({"slug": "test", "distances": [
        {"key": "alpine", "distance": 80, "unit": "miles"},
        {"key": "short-km", "distance_km": 37.5},
        {"distance": "250.3 miles"},
    ]})
    assert [item["key"] for item in context["distances"]] == ["alpine", "short-km", "250-3-mile"]
    assert "37.5 km" == context["distances"][1]["label"]


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, None, "unknown"])
def test_invalid_numeric_distances_do_not_become_choices(value):
    assert race_calculator_context({"slug": "test", "vitals": {"distance_mi": value}})["distances"] == []


def test_conflicting_duplicate_variant_keys_are_not_silently_selected():
    context = race_calculator_context({"slug": "test", "distances": [
        {"key": "long", "name": "One", "distance_mi": 100},
        {"key": "long", "name": "Different", "distance_mi": 110},
    ]})
    assert context["distances"] == []


def test_variant_input_is_bounded_and_source_is_not_mutated():
    data = {"slug": "test", "distances": [{"key": "course-" + str(i), "distance_mi": i + 1} for i in range(200)]}
    original = copy.deepcopy(data)
    context = race_calculator_context(data)
    assert len(context["distances"]) == 40
    assert data == original


def test_real_external_asset_pipeline_contains_scoped_css_and_reduced_motion():
    css = _extract_css_content()
    assert ".gg-neo-brutalist-page .gg-race-calculator" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "transition: transform 150ms ease" in css
    kicker = re.search(r"\.gg-neo-brutalist-page \.gg-race-calculator-kicker \{([^}]*)\}", css)
    assert kicker, "calculator brand kicker styling missing"
    assert not re.search(r"text-transform\s*:\s*uppercase", kicker.group(1))
    text = page(external_assets={"css_tag": '<link rel="stylesheet" href="/test.css">', "js_tag": '<script src="/test.js"></script>'})
    assert 'id="race-calculator"' in text
    assert 'href="/test.css"' in text
    assert "Sometype Mono" in text


def test_calculator_variables_exist_in_emitted_tokens_or_the_header_metric():
    # The generator consumes this sheet even when the separate upstream brand
    # checkout is absent. Upstream parity remains a separate preflight check.
    required = set(re.findall(r"var\((--gg-[a-z0-9-]+)", get_race_calculator_css()))
    declared = set(re.findall(r"(--gg-[a-z0-9-]+)\s*:", get_tokens_css()))
    # Header height is a runtime layout metric, not a brand token. Its
    # defining shared script is emitted on the same page; CSS has a fallback.
    declared.update(re.findall(r"setProperty\(['\"](--gg-[a-z0-9-]+)['\"]", get_site_header_js()))
    assert required
    assert required <= declared, "Missing calculator tokens: " + str(required - declared)


def test_calculator_anchor_accounts_for_the_sticky_header():
    css = get_race_calculator_css()
    assert "scroll-margin-top: calc(var(--gg-header-height, 80px) + var(--gg-spacing-4xl))" in css


def test_calculator_copy_has_no_fake_result_or_slop():
    fragment = calculator(page())
    assert not check_text(fragment)
    assert "Open in Endure Labs" in fragment
    assert "Choose the edition and course file in Endure Labs." in fragment
    assert "finish-range" not in fragment
    assert "confidence" not in fragment
