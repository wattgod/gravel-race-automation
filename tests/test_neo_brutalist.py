"""Tests for wordpress/generate_neo_brutalist.py — race page generator."""

import json
import re
import sys
from pathlib import Path

import pytest

# Ensure wordpress/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from generate_neo_brutalist import (
    ALL_DIMS,
    COUNTRY_CODES,
    COURSE_DIMS,
    DIM_LABELS,
    FAQ_PRIORITY,
    FAQ_TEMPLATES,
    MONTH_NUMBERS,
    OPINION_DIMS,
    US_STATES,
    _build_race_name_map,
    build_accordion_html,
    build_course_overview,
    build_course_route,
    build_email_capture,
    build_footer,
    build_hero,
    build_history,
    build_logistics_section,
    build_nav_header,
    build_news_section,
    build_pullquote,
    build_radar_charts,
    build_ratings,
    build_similar_races,
    build_sports_event_jsonld,
    build_faq_jsonld,
    build_sticky_cta,
    build_toc,
    build_training,
    build_verdict,
    build_visible_faq,
    build_webpage_jsonld,
    detect_country,
    esc,
    generate_page,
    linkify_alternatives,
    normalize_race_data,
    score_bar_color,
)


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def sample_race_data():
    """Minimal but complete race data for testing."""
    return {
        "race": {
            "name": "Test Gravel 100",
            "slug": "test-gravel-100",
            "display_name": "Test Gravel 100",
            "tagline": "A test gravel race for unit testing purposes.",
            "vitals": {
                "distance_mi": 100,
                "elevation_ft": 5000,
                "location": "Emporia, Kansas",
                "location_badge": "EMPORIA, KS",
                "date": "June annually",
                "date_specific": "2026: June 15",
                "terrain_types": ["Gravel roads", "Dirt paths"],
                "field_size": "~500 riders",
                "start_time": "6:00 AM",
                "registration": "Online. Cost: $150-250",
                "aid_stations": "3 aid stations",
                "cutoff_time": "12 hours",
            },
            "climate": {
                "primary": "Hot and humid",
                "description": "Summer heat in Kansas.",
                "challenges": ["Heat", "Humidity"],
            },
            "terrain": {
                "primary": "Mixed gravel",
                "surface": "Limestone and dirt",
                "technical_rating": 3,
                "features": ["Rolling hills"],
            },
            "gravel_god_rating": {
                "overall_score": 72,
                "tier": 2,
                "tier_label": "TIER 2",
                "logistics": 3, "length": 4, "technicality": 3,
                "elevation": 3, "climate": 3, "altitude": 1, "adventure": 3,
                "prestige": 3, "race_quality": 4, "experience": 4,
                "community": 3, "field_depth": 3, "value": 4, "expenses": 3,
                "discipline": "gravel",
            },
            "biased_opinion": {
                "verdict": "Solid Mid-Tier Gravel",
                "summary": "A well-organized gravel race with good community vibes.",
                "strengths": ["Good organization", "Scenic course"],
                "weaknesses": ["Limited field depth", "Remote location"],
                "bottom_line": "Worth it for Kansas gravel lovers.",
            },
            "biased_opinion_ratings": {
                dim: {"score": 3, "explanation": f"Test explanation for {dim}."}
                for dim in ALL_DIMS
            },
            "final_verdict": {
                "score": "72 / 100",
                "one_liner": "A solid Kansas gravel event.",
                "should_you_race": "Yes if you like gravel.",
                "alternatives": "For bigger events: Unbound Gravel, Mid South. For similar: Gravel Worlds.",
            },
            "course_description": {
                "character": "Rolling Kansas gravel through the Flint Hills.",
                "suffering_zones": [
                    {"mile": 30, "label": "The Wall", "desc": "First big climb."},
                    {"mile": 70, "label": "The Grind", "desc": "Heat hits hard."},
                ],
                "signature_challenge": "Heat and wind on exposed roads.",
                "ridewithgps_id": "12345678",
                "ridewithgps_name": "Test Gravel Route",
            },
            "history": {
                "founded": 2018,
                "founder": "Jim Smith",
                "origin_story": "Founded by local cyclists who wanted a proper gravel challenge in the heartland.",
                "notable_moments": ["2020: First year with 500 riders."],
                "reputation": "Growing regional event.",
            },
            "logistics": {
                "airport": "Wichita (ICT) — 90 minutes",
                "lodging_strategy": "Book early in Emporia.",
                "food": "Local restaurants and BBQ.",
                "packet_pickup": "Friday afternoon.",
                "parking": "Free lots near start.",
                "official_site": "https://testgravel100.com",
            },
        }
    }


@pytest.fixture
def normalized_data(sample_race_data):
    """Pre-normalized race data."""
    return normalize_race_data(sample_race_data)


@pytest.fixture
def sample_race_index():
    """Minimal race index for testing."""
    return [
        {"slug": "test-gravel-100", "name": "Test Gravel 100",
         "tier": 2, "overall_score": 72, "region": "Midwest",
         "location": "Emporia, Kansas"},
        {"slug": "unbound-200", "name": "Unbound Gravel 200",
         "tier": 1, "overall_score": 80, "region": "Midwest",
         "location": "Emporia, Kansas"},
        {"slug": "mid-south", "name": "Mid South",
         "tier": 1, "overall_score": 83, "region": "South",
         "location": "Stillwater, Oklahoma"},
        {"slug": "gravel-worlds", "name": "Gravel Worlds",
         "tier": 1, "overall_score": 79, "region": "Midwest",
         "location": "Lincoln, Nebraska"},
    ]


@pytest.fixture
def stub_race_data():
    """Stub profile with minimal/placeholder content."""
    return {
        "race": {
            "name": "Stub Race",
            "slug": "stub-race",
            "display_name": "Stub Race",
            "tagline": "A stub race.",
            "vitals": {
                "distance_mi": 50,
                "elevation_ft": 2000,
                "location": "Stubtown, Michigan",
                "date": "TBD",
                "field_size": "TBD",
                "registration": "Online",
            },
            "gravel_god_rating": {
                "overall_score": 40,
                "tier": 4,
                "tier_label": "TIER 4",
                "logistics": 2, "length": 2, "technicality": 2,
                "elevation": 2, "climate": 2, "altitude": 1, "adventure": 2,
                "prestige": 2, "race_quality": 2, "experience": 2,
                "community": 2, "field_depth": 2, "value": 2, "expenses": 2,
                "discipline": "gravel",
            },
            "biased_opinion_ratings": {
                dim: {"score": 2, "explanation": f"Stub explanation for {dim}."}
                for dim in ALL_DIMS
            },
            "biased_opinion": {"summary": "", "strengths": [], "weaknesses": []},
            "final_verdict": {},
            "history": {
                "founder": "Michigan organizers",
                "origin_story": "Michigan gravel event.",
            },
            "logistics": {
                "airport": "Check Michigan cycling calendars",
                "lodging_strategy": "Check Stubtown lodging",
                "official_site": "Check Stub Race website",
            },
        }
    }


# ── Constants ─────────────────────────────────────────────────

class TestConstants:
    def test_all_dims_is_14(self):
        assert len(ALL_DIMS) == 14

    def test_dims_split_7_7(self):
        assert len(COURSE_DIMS) == 7
        assert len(OPINION_DIMS) == 7

    def test_dim_labels_complete(self):
        for dim in ALL_DIMS:
            assert dim in DIM_LABELS

    def test_faq_templates_complete(self):
        for dim in ALL_DIMS:
            assert dim in FAQ_TEMPLATES

    def test_month_numbers_complete(self):
        assert len(MONTH_NUMBERS) == 12
        assert MONTH_NUMBERS["january"] == "01"
        assert MONTH_NUMBERS["december"] == "12"


# ── Country Detection ─────────────────────────────────────────

class TestCountryDetection:
    def test_us_state_full_name(self):
        assert detect_country("Emporia, Kansas") == "US"

    def test_us_state_abbreviation(self):
        assert detect_country("Denver, CO") == "US"

    def test_sweden(self):
        assert detect_country("Halmstad, Sweden") == "SE"

    def test_uk(self):
        assert detect_country("London, UK") == "GB"

    def test_england(self):
        assert detect_country("Bristol, England") == "GB"

    def test_iceland(self):
        assert detect_country("Reykjavik, Southern Iceland") == "IS"

    def test_australia_state(self):
        assert detect_country("Melbourne, Victoria") == "AU"

    def test_canada(self):
        assert detect_country("Calgary, Canada") == "CA"

    def test_british_columbia(self):
        assert detect_country("Vancouver, British Columbia") == "CA"

    def test_italy(self):
        assert detect_country("Siena, Italy") == "IT"

    def test_spain(self):
        assert detect_country("Girona, Spain") == "ES"

    def test_parenthetical_state(self):
        assert detect_country("Pisgah, North Carolina (Pisgah National Forest)") == "US"

    def test_empty_location(self):
        assert detect_country("") == "US"

    def test_dash_location(self):
        assert detect_country("--") == "US"

    def test_default_unknown(self):
        assert detect_country("Unknown Place, Nowhere") == "US"


# ── normalize_race_data ───────────────────────────────────────

class TestNormalize:
    def test_basic_fields(self, normalized_data):
        assert normalized_data["name"] == "Test Gravel 100"
        assert normalized_data["slug"] == "test-gravel-100"
        assert normalized_data["overall_score"] == 72
        assert normalized_data["tier"] == 2

    def test_vitals_parsed(self, normalized_data):
        v = normalized_data["vitals"]
        assert v["distance"] == "100 mi"
        assert "5,000" in v["elevation"]
        assert v["location"] == "Emporia, Kansas"

    def test_date_formatted(self, normalized_data):
        assert "June 15, 2026" in normalized_data["vitals"]["date"]

    def test_entry_cost_extracted(self, normalized_data):
        assert normalized_data["vitals"]["entry_cost"] == "$150-250"

    def test_explanations_populated(self, normalized_data):
        for dim in ALL_DIMS:
            assert dim in normalized_data["explanations"]
            assert "score" in normalized_data["explanations"][dim]
            assert "explanation" in normalized_data["explanations"][dim]

    def test_course_profile_total(self, normalized_data):
        expected = sum(normalized_data["rating"].get(d, 0) for d in COURSE_DIMS)
        assert normalized_data["course_profile"] == expected


# ── Hero ──────────────────────────────────────────────────────

class TestHero:
    def test_hero_shows_real_score(self, normalized_data):
        html = build_hero(normalized_data)
        # Score innerHTML should be the actual number, not "0"
        assert 'data-target="72">72</div>' in html

    def test_hero_has_tier_label(self, normalized_data):
        html = build_hero(normalized_data)
        assert "TIER 2" in html

    def test_hero_has_tagline(self, normalized_data):
        html = build_hero(normalized_data)
        assert "test gravel race" in html.lower()

    def test_hero_has_race_name(self, normalized_data):
        html = build_hero(normalized_data)
        assert "Test Gravel 100" in html


# ── JSON-LD ───────────────────────────────────────────────────

class TestJsonLD:
    def test_sports_event_type(self, normalized_data):
        jsonld = build_sports_event_jsonld(normalized_data)
        assert jsonld["@type"] == "SportsEvent"

    def test_sports_event_country_us(self, normalized_data):
        jsonld = build_sports_event_jsonld(normalized_data)
        addr = jsonld["location"]["address"]
        assert addr["addressCountry"] == "US"

    def test_sports_event_country_international(self, sample_race_data):
        sample_race_data["race"]["vitals"]["location"] = "Girona, Spain"
        rd = normalize_race_data(sample_race_data)
        jsonld = build_sports_event_jsonld(rd)
        addr = jsonld["location"]["address"]
        assert addr["addressCountry"] == "ES"

    def test_sports_event_start_date(self, normalized_data):
        jsonld = build_sports_event_jsonld(normalized_data)
        assert jsonld["startDate"] == "2026-06-15"

    def test_sports_event_has_review(self, normalized_data):
        jsonld = build_sports_event_jsonld(normalized_data)
        assert jsonld["review"]["@type"] == "Review"
        assert jsonld["review"]["reviewRating"]["ratingValue"] == "72"

    def test_faq_jsonld_has_questions(self, normalized_data):
        faq = build_faq_jsonld(normalized_data)
        assert faq is not None
        assert faq["@type"] == "FAQPage"
        assert len(faq["mainEntity"]) >= 1

    def test_organizer_real_founder(self, normalized_data):
        jsonld = build_sports_event_jsonld(normalized_data)
        assert jsonld["organizer"]["name"] == "Jim Smith"

    def test_organizer_suppressed_generic(self, stub_race_data):
        rd = normalize_race_data(stub_race_data)
        jsonld = build_sports_event_jsonld(rd)
        assert "organizer" not in jsonld

    def test_webpage_jsonld(self, normalized_data):
        jsonld = build_webpage_jsonld(normalized_data)
        assert jsonld["@type"] == "WebPage"
        assert "speakable" in jsonld


# ── Sections ──────────────────────────────────────────────────

class TestSections:
    def test_toc_has_7_links(self):
        html = build_toc()
        assert html.count("<a ") == 7

    def test_course_overview_has_map(self, normalized_data):
        html = build_course_overview(normalized_data)
        assert "ridewithgps.com" in html

    def test_course_overview_has_stat_cards(self, normalized_data):
        html = build_course_overview(normalized_data)
        assert "gg-stat-card" in html

    def test_course_overview_has_difficulty(self, normalized_data):
        html = build_course_overview(normalized_data)
        assert "gg-difficulty-gauge" in html

    def test_history_renders_real_content(self, normalized_data):
        html = build_history(normalized_data)
        assert "Founded by local cyclists" in html

    def test_history_suppresses_stub(self, stub_race_data):
        rd = normalize_race_data(stub_race_data)
        html = build_history(rd)
        assert html == ""

    def test_history_suppresses_generic_founder(self, sample_race_data):
        sample_race_data["race"]["history"]["founder"] = "Kansas organizers"
        rd = normalize_race_data(sample_race_data)
        html = build_history(rd)
        assert "Kansas organizers" not in html

    def test_course_route_has_zones(self, normalized_data):
        html = build_course_route(normalized_data)
        assert "gg-suffering-zone" in html
        assert "The Wall" in html

    def test_ratings_has_accordions(self, normalized_data):
        html = build_ratings(normalized_data)
        assert "gg-accordion" in html

    def test_ratings_has_radar_charts(self, normalized_data):
        html = build_ratings(normalized_data)
        assert "gg-radar-pair" in html

    def test_verdict_has_race_skip(self, normalized_data):
        html = build_verdict(normalized_data)
        assert "Race This If" in html
        assert "Skip This If" in html

    def test_verdict_linkifies_alternatives(self, normalized_data):
        index = [
            {"slug": "unbound-200", "name": "Unbound Gravel"},
            {"slug": "mid-south", "name": "Mid South"},
            {"slug": "gravel-worlds", "name": "Gravel Worlds"},
        ]
        html = build_verdict(normalized_data, race_index=index)
        assert 'href="/race/mid-south/"' in html

    def test_pullquote_renders(self, normalized_data):
        html = build_pullquote(normalized_data)
        assert "gg-pullquote" in html
        assert "well-organized" in html

    def test_pullquote_empty_summary(self, stub_race_data):
        rd = normalize_race_data(stub_race_data)
        html = build_pullquote(rd)
        assert html == ""

    def test_training_has_countdown(self, normalized_data):
        html = build_training(normalized_data, "https://example.com")
        assert "gg-countdown" in html
        assert "2026-06-15" in html

    def test_visible_faq_renders(self, normalized_data):
        html = build_visible_faq(normalized_data)
        assert "gg-faq-item" in html

    def test_email_capture_has_substack(self, normalized_data):
        html = build_email_capture(normalized_data)
        assert "substack.com/embed" in html

    def test_similar_races(self, normalized_data, sample_race_index):
        html = build_similar_races(normalized_data, sample_race_index)
        assert "gg-similar-card" in html

    def test_news_section_has_ticker(self, normalized_data):
        html = build_news_section(normalized_data)
        assert "gg-news-ticker" in html


# ── Logistics Placeholder Suppression ─────────────────────────

class TestLogisticsFiltering:
    def test_filters_check_website(self, stub_race_data):
        rd = normalize_race_data(stub_race_data)
        html = build_logistics_section(rd)
        assert "Check Michigan" not in html
        assert "Check Stubtown" not in html

    def test_keeps_real_logistics(self, normalized_data):
        html = build_logistics_section(normalized_data)
        assert "Wichita (ICT)" in html
        assert "Book early" in html

    def test_empty_logistics_returns_empty(self):
        rd = normalize_race_data({"race": {
            "name": "Empty", "slug": "empty",
            "gravel_god_rating": {"overall_score": 30, "tier": 4, "tier_label": "TIER 4"},
            "logistics": {},
        }})
        assert build_logistics_section(rd) == ""

    def test_official_site_link_rendered(self, normalized_data):
        html = build_logistics_section(normalized_data)
        assert 'href="https://testgravel100.com"' in html

    def test_non_url_official_site_no_link(self, stub_race_data):
        rd = normalize_race_data(stub_race_data)
        html = build_logistics_section(rd)
        assert "OFFICIAL SITE" not in html


# ── Linkify Alternatives ──────────────────────────────────────

class TestLinkify:
    def test_links_from_index(self):
        index = [
            {"slug": "unbound-200", "name": "Unbound Gravel 200"},
            {"slug": "mid-south", "name": "Mid South"},
        ]
        result = linkify_alternatives("Try Unbound Gravel 200 or Mid South.", index)
        assert 'href="/race/unbound-200/"' in result
        assert 'href="/race/mid-south/"' in result

    def test_aliases_work(self):
        result = linkify_alternatives("Try Unbound for a bigger field.", [])
        assert 'href="/race/unbound-200/"' in result

    def test_empty_text(self):
        assert linkify_alternatives("", []) == ""

    def test_no_match(self):
        result = linkify_alternatives("A random race with no known names.", [])
        assert "<a " not in result

    def test_build_race_name_map(self, sample_race_index):
        name_map = _build_race_name_map(sample_race_index)
        assert name_map["Unbound Gravel 200"] == "unbound-200"
        assert name_map["Mid South"] == "mid-south"


# ── Footer ────────────────────────────────────────────────────

class TestFooter:
    def test_footer_has_nav(self):
        html = build_footer()
        assert "gg-footer-nav" in html

    def test_footer_has_all_races_link(self):
        html = build_footer()
        assert "/gravel-races/" in html

    def test_footer_has_methodology_link(self):
        html = build_footer()
        assert "/race/methodology/" in html

    def test_footer_has_newsletter_link(self):
        html = build_footer()
        assert "substack.com" in html

    def test_footer_has_disclaimer(self):
        html = build_footer()
        assert "produced independently" in html


# ── Nav ───────────────────────────────────────────────────────

class TestNav:
    def test_nav_has_brand(self, normalized_data):
        html = build_nav_header(normalized_data, [])
        assert "GRAVEL GOD" in html

    def test_nav_has_breadcrumb(self, normalized_data):
        html = build_nav_header(normalized_data, [])
        assert "gg-breadcrumb" in html
        assert "Test Gravel 100" in html


# ── Accordion & Radar ─────────────────────────────────────────

class TestAccordion:
    def test_accordion_14_items(self, normalized_data):
        course = build_accordion_html(COURSE_DIMS, normalized_data["explanations"])
        opinion = build_accordion_html(OPINION_DIMS, normalized_data["explanations"], idx_offset=7)
        assert course.count("gg-accordion-item") == 7
        assert opinion.count("gg-accordion-item") == 7

    def test_accordion_has_scores(self, normalized_data):
        html = build_accordion_html(COURSE_DIMS, normalized_data["explanations"])
        assert "3/5" in html

    def test_radar_charts_render(self, normalized_data):
        html = build_radar_charts(normalized_data["explanations"],
                                  normalized_data["course_profile"],
                                  normalized_data["opinion_total"])
        assert "gg-radar-pair" in html
        assert "<svg" in html


# ── Full Page Assembly ────────────────────────────────────────

class TestFullPage:
    def test_generates_valid_html(self, normalized_data):
        html = generate_page(normalized_data)
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_has_favicon(self, normalized_data):
        html = generate_page(normalized_data)
        assert "data:image/svg+xml" in html

    def test_has_skip_link(self, normalized_data):
        html = generate_page(normalized_data)
        assert "gg-skip-link" in html

    def test_title_format(self, normalized_data):
        html = generate_page(normalized_data)
        assert "Gravel God Race Rating" in html
        assert "Race Profile" not in html

    def test_has_og_image(self, normalized_data):
        html = generate_page(normalized_data)
        assert "og:image" in html

    def test_has_twitter_card(self, normalized_data):
        html = generate_page(normalized_data)
        assert "twitter:card" in html

    def test_has_canonical(self, normalized_data):
        html = generate_page(normalized_data)
        assert 'rel="canonical"' in html

    def test_has_jsonld(self, normalized_data):
        html = generate_page(normalized_data)
        assert "application/ld+json" in html

    def test_score_not_zero_in_html(self, normalized_data):
        html = generate_page(normalized_data)
        assert 'data-target="72">72</div>' in html

    def test_has_all_sections(self, normalized_data):
        html = generate_page(normalized_data)
        assert 'id="course"' in html
        assert 'id="history"' in html
        assert 'id="route"' in html
        assert 'id="ratings"' in html
        assert 'id="verdict"' in html
        assert 'id="training"' in html
        assert 'id="logistics"' in html

    def test_js_has_fetch_timeout(self, normalized_data):
        html = generate_page(normalized_data)
        assert "fetchWithTimeout" in html

    def test_js_score_animation_starts_from_zero(self, normalized_data):
        html = generate_page(normalized_data)
        assert "el.textContent = '0'" in html

    def test_no_inline_margin_styles(self, normalized_data):
        index = [
            {"slug": "test-gravel-100", "name": "Test Gravel 100",
             "tier": 2, "overall_score": 72, "region": "Midwest",
             "location": "Emporia, Kansas"},
        ]
        html = generate_page(normalized_data, index)
        # Check no leftover inline margin-top styles
        assert 'style="margin-top:16px"' not in html
        assert 'style="margin-top:20px"' not in html

    def test_tablet_breakpoint(self, normalized_data):
        html = generate_page(normalized_data)
        assert "max-width: 1024px" in html

    def test_skip_link_css(self, normalized_data):
        html = generate_page(normalized_data)
        assert "gg-skip-link" in html
        assert ":focus" in html


# ── Utility Functions ─────────────────────────────────────────

class TestUtilities:
    def test_esc_html(self):
        assert esc("<script>") == "&lt;script&gt;"
        assert esc("Flint & Hills") == "Flint &amp; Hills"
        assert esc(None) == ""

    def test_score_bar_color(self):
        from generate_neo_brutalist import COLORS
        assert score_bar_color(5) == COLORS["teal"]
        assert score_bar_color(4) == COLORS["gold"]
        assert score_bar_color(1) == COLORS["tan"]
