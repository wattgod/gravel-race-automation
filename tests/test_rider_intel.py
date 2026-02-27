"""Tests for rider intel extraction — schema validation, callout rendering, normalize passthrough.

Covers:
  - rider_intel schema validation across enriched profiles
  - Callout rendering (empty → no output, XSS safety, correct section placement)
  - normalize_race_data passthrough of rider_intel
  - Additional quotes merge into youtube_quotes (cap 4, dedup)
  - validate_rider_intel() function correctness
"""

import json
import re
import sys
from pathlib import Path

import pytest

# Ensure wordpress/ and scripts/ are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generate_neo_brutalist import (
    _build_riders_report,
    _merge_youtube_quotes,
    build_course_route,
    build_logistics_section,
    build_training,
    esc,
    normalize_race_data,
)
from youtube_validate import validate_rider_intel
from youtube_extract_intel import normalize_intel

RACE_DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"

VIDEO_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')
HTML_RE = re.compile(r'<[a-z][^>]*>', re.IGNORECASE)


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def minimal_race():
    """Minimal race data without youtube_data."""
    return {
        "race": {
            "name": "Test Race",
            "slug": "test-race",
            "display_name": "Test Race",
            "vitals": {
                "distance_mi": 50,
                "elevation_ft": 3000,
                "location": "Somewhere, Colorado",
                "date": "July annually",
                "date_specific": "2026: July 10",
                "field_size": "200",
            },
            "gravel_god_rating": {
                "overall_score": 55,
                "tier": 3,
                "tier_label": "TIER 3",
                "logistics": 3, "length": 3, "technicality": 2,
                "elevation": 3, "climate": 2, "altitude": 2, "adventure": 2,
                "prestige": 2, "race_quality": 3, "experience": 3,
                "community": 2, "field_depth": 2, "value": 3, "expenses": 3,
                "discipline": "gravel",
            },
            "biased_opinion": {"verdict": "OK", "summary": "Fine."},
            "biased_opinion_ratings": {},
            "course_description": {
                "character": "A rolling gravel course through the hills.",
                "suffering_zones": [
                    {"mile": "15", "label": "Big Hill", "desc": "Steep climb."},
                ],
                "signature_challenge": "The final ridge.",
            },
            "logistics": {
                "airport": "Denver International Airport",
                "lodging_strategy": "Book early in town.",
                "food": "Local restaurants downtown.",
                "packet_pickup": "Friday evening at venue.",
                "parking": "Free parking at start.",
                "official_site": "https://example.com",
            },
        }
    }


@pytest.fixture
def race_with_intel(minimal_race):
    """Race data with full rider_intel block."""
    minimal_race["race"]["youtube_data"] = {
        "researched_at": "2026-02-23",
        "videos": [
            {
                "video_id": "vKCSt1e392M",
                "title": "Test Video 1",
                "channel": "Test Channel",
                "view_count": 68980,
                "upload_date": "20250904",
                "duration_string": "15:31",
                "curated": True,
                "curation_reason": "Good race recap",
                "display_order": 1,
            },
        ],
        "quotes": [
            {
                "text": "The landscapes here are harsh and beautiful.",
                "source_video_id": "vKCSt1e392M",
                "source_channel": "Test Channel",
                "source_view_count": 68980,
                "category": "race_atmosphere",
                "curated": True,
            },
        ],
        "rider_intel": {
            "extracted_at": "2026-02-23",
            "key_challenges": [
                {
                    "name": "Kaw Reserve Road",
                    "mile_marker": "45",
                    "description": "Rocky technical section that shakes your bike apart.",
                    "source_video_ids": ["vKCSt1e392M"],
                },
                {
                    "name": "Wind Alley",
                    "mile_marker": "",
                    "description": "Brutal headwind section on exposed ridge.",
                    "source_video_ids": ["vKCSt1e392M"],
                },
            ],
            "terrain_notes": [
                {
                    "text": "First 30 miles hardpack, then chunky limestone after mile 40.",
                    "source_video_ids": ["vKCSt1e392M"],
                },
            ],
            "gear_mentions": [
                {
                    "text": "Multiple riders recommend 42mm or wider tires for the rocky sections.",
                    "source_video_ids": ["vKCSt1e392M"],
                },
            ],
            "race_day_tips": [
                {
                    "text": "Start conservative — headwind on the return will cost you.",
                    "source_video_ids": ["vKCSt1e392M"],
                },
                {
                    "text": "Fill bottles at every aid station, spacing is tight.",
                    "source_video_ids": ["vKCSt1e392M"],
                },
            ],
            "additional_quotes": [
                {
                    "text": "Aid stations well-stocked but spacing was tight between miles 60-90.",
                    "source_video_id": "vKCSt1e392M",
                    "source_channel": "Test Channel",
                    "source_view_count": 68980,
                    "category": "logistics",
                    "curated": True,
                },
            ],
            "search_text": "Riders describe this race as a challenging gravel event through the Kansas Flint Hills. The first 30 miles feature smooth hardpack gravel before transitioning to chunky limestone. Key challenges include the rocky Kaw Reserve Road section around mile 45 and a brutal headwind section on an exposed ridge. Multiple riders recommend 42mm or wider tires. Pacing is critical as the headwind on the return leg is energy-sapping. Aid stations are well-stocked but spacing between miles 60 and 90 is tight, so riders should fill bottles at every opportunity. The atmosphere combines raw Midwest grit with surprisingly beautiful prairie landscapes.",
        },
    }
    return minimal_race


@pytest.fixture
def race_without_intel(minimal_race):
    """Race with youtube_data but no rider_intel."""
    minimal_race["race"]["youtube_data"] = {
        "researched_at": "2026-02-23",
        "videos": [
            {
                "video_id": "vKCSt1e392M",
                "title": "Test Video",
                "channel": "Test",
                "view_count": 1000,
                "curated": True,
                "curation_reason": "Good",
                "display_order": 1,
            },
        ],
        "quotes": [],
    }
    return minimal_race


# ── Normalize Passthrough ─────────────────────────────────────

class TestNormalizeRiderIntelPassthrough:
    """Test that normalize_race_data correctly passes through rider_intel."""

    def test_no_youtube_data_produces_empty_intel(self, minimal_race):
        rd = normalize_race_data(minimal_race)
        assert rd['rider_intel'] == {}

    def test_rider_intel_passed_through(self, race_with_intel):
        rd = normalize_race_data(race_with_intel)
        assert rd['rider_intel']['extracted_at'] == '2026-02-23'
        assert len(rd['rider_intel']['key_challenges']) == 2
        assert len(rd['rider_intel']['terrain_notes']) == 1
        assert len(rd['rider_intel']['gear_mentions']) == 1
        assert len(rd['rider_intel']['race_day_tips']) == 2

    def test_no_rider_intel_produces_empty_dict(self, race_without_intel):
        rd = normalize_race_data(race_without_intel)
        assert rd['rider_intel'] == {}


# ── Quote Merging ─────────────────────────────────────────────

class TestQuoteMerge:
    """Test _merge_youtube_quotes merges additional_quotes correctly."""

    def test_curated_quotes_only_when_no_intel(self):
        yt = {
            "quotes": [
                {"text": "Existing quote 1.", "curated": True},
                {"text": "Existing quote 2.", "curated": True},
            ],
        }
        result = _merge_youtube_quotes(yt)
        assert len(result) == 2
        assert result[0]["text"] == "Existing quote 1."

    def test_additional_quotes_fill_remaining_slots(self):
        yt = {
            "quotes": [
                {"text": "Existing quote.", "curated": True},
            ],
            "rider_intel": {
                "additional_quotes": [
                    {"text": "New logistics quote.", "category": "logistics", "curated": True},
                    {"text": "New training quote.", "category": "training", "curated": True},
                ],
            },
        }
        result = _merge_youtube_quotes(yt)
        assert len(result) == 3
        assert result[0]["text"] == "Existing quote."
        assert result[1]["text"] == "New logistics quote."
        assert result[2]["text"] == "New training quote."

    def test_cap_at_4_total(self):
        yt = {
            "quotes": [
                {"text": f"Existing {i}.", "curated": True}
                for i in range(3)
            ],
            "rider_intel": {
                "additional_quotes": [
                    {"text": "New 1.", "curated": True},
                    {"text": "New 2.", "curated": True},
                    {"text": "New 3.", "curated": True},
                ],
            },
        }
        result = _merge_youtube_quotes(yt)
        assert len(result) == 4

    def test_dedup_by_text(self):
        yt = {
            "quotes": [
                {"text": "Duplicate quote.", "curated": True},
            ],
            "rider_intel": {
                "additional_quotes": [
                    {"text": "Duplicate quote.", "curated": True},
                    {"text": "Unique quote.", "curated": True},
                ],
            },
        }
        result = _merge_youtube_quotes(yt)
        texts = [q["text"] for q in result]
        assert texts.count("Duplicate quote.") == 1
        assert "Unique quote." in texts

    def test_uncurated_quotes_excluded(self):
        yt = {
            "quotes": [
                {"text": "Curated.", "curated": True},
                {"text": "Not curated.", "curated": False},
            ],
        }
        result = _merge_youtube_quotes(yt)
        assert len(result) == 1
        assert result[0]["text"] == "Curated."

    def test_empty_youtube_data(self):
        result = _merge_youtube_quotes({})
        assert result == []

    def test_normalize_caps_at_4_with_merge(self, race_with_intel):
        """Full integration: normalize produces max 4 quotes with merge."""
        # Add more existing curated quotes to race
        race_with_intel["race"]["youtube_data"]["quotes"] = [
            {"text": f"Quote {i}.", "source_video_id": "vKCSt1e392M",
             "source_channel": "Test", "source_view_count": 1000,
             "category": "race_atmosphere", "curated": True}
            for i in range(5)
        ]
        rd = normalize_race_data(race_with_intel)
        assert len(rd['youtube_quotes']) <= 4


# ── Callout Builder ───────────────────────────────────────────

class TestBuildRidersReport:
    """Test _build_riders_report callout helper.

    Signature: _build_riders_report(groups: list[tuple[list[dict], str]]) -> str
    Each group is (items, item_type) where item_type is "named" or "text".
    One badge per callout, regardless of how many groups.
    """

    def test_empty_groups_returns_empty(self):
        assert _build_riders_report([]) == ''

    def test_all_groups_empty_returns_empty(self):
        assert _build_riders_report([([], "named"), ([], "text")]) == ''

    def test_named_items_include_badge(self):
        items = [{"name": "Test Section", "description": "Hard climb.", "mile_marker": "25"}]
        html = _build_riders_report([(items, "named")])
        assert 'RIDERS REPORT' in html
        assert 'gg-riders-report-badge' in html

    def test_named_items_include_name_and_desc(self):
        items = [{"name": "Test Section", "description": "Hard climb."}]
        html = _build_riders_report([(items, "named")])
        assert 'Test Section' in html
        assert 'Hard climb.' in html

    def test_named_items_with_mile_marker(self):
        items = [{"name": "Ridge", "description": "Steep.", "mile_marker": "42"}]
        html = _build_riders_report([(items, "named")])
        assert 'MI 42' in html

    def test_named_items_without_mile_marker(self):
        items = [{"name": "Ridge", "description": "Steep.", "mile_marker": ""}]
        html = _build_riders_report([(items, "named")])
        assert 'gg-riders-report-mile' not in html

    def test_text_items_include_text(self):
        items = [{"text": "The surface is chunky limestone."}]
        html = _build_riders_report([(items, "text")])
        assert 'chunky limestone' in html

    def test_xss_safety_named(self):
        items = [{"name": '<script>alert("xss")</script>', "description": '<img onerror=alert(1)>'}]
        html = _build_riders_report([(items, "named")])
        assert '<script>' not in html
        assert '<img' not in html
        assert '&lt;script&gt;' in html

    def test_xss_safety_text(self):
        items = [{"text": '<div onmouseover="alert(1)">Hover me</div>'}]
        html = _build_riders_report([(items, "text")])
        # The injected <div onmouseover=...> must be entity-escaped so browser ignores it
        desc_match = re.search(r'gg-riders-report-desc">(.*?)</div>', html)
        assert desc_match, "Expected a desc element"
        desc_content = desc_match.group(1)
        assert '<div' not in desc_content
        assert '&lt;div' in desc_content

    def test_single_badge_for_combined_groups(self):
        """Course section passes challenges + terrain as two groups — only one badge."""
        challenges = [{"name": "Ridge", "description": "Steep climb."}]
        terrain = [{"text": "Loose gravel surface."}]
        html = _build_riders_report([(challenges, "named"), (terrain, "text")])
        assert html.count('gg-riders-report-badge') == 1
        assert 'Ridge' in html
        assert 'Loose gravel surface' in html

    def test_combined_groups_skips_empty(self):
        """One empty group, one populated — only populated renders, still one badge."""
        html = _build_riders_report([
            ([], "named"),
            ([{"text": "The only content."}], "text"),
        ])
        assert html.count('gg-riders-report-badge') == 1
        assert 'The only content.' in html

    def test_mile_marker_zero_renders(self):
        """mile_marker '0' (start line) must render — bool('0') is True, bool(0) is False."""
        items = [{"name": "Start Line", "description": "Chaos.", "mile_marker": "0"}]
        html = _build_riders_report([(items, "named")])
        assert 'MI 0' in html

    def test_mile_marker_none_no_render(self):
        """mile_marker None must not produce MI badge."""
        items = [{"name": "Somewhere", "description": "Hard.", "mile_marker": None}]
        html = _build_riders_report([(items, "named")])
        assert 'gg-riders-report-mile' not in html


# ── Section Injection ─────────────────────────────────────────

class TestCourseRouteWithIntel:
    """Test that rider intel injects into course section correctly."""

    def test_course_section_includes_challenges(self, race_with_intel):
        rd = normalize_race_data(race_with_intel)
        html = build_course_route(rd)
        assert 'Kaw Reserve Road' in html
        assert 'RIDERS REPORT' in html

    def test_course_section_includes_terrain_notes(self, race_with_intel):
        rd = normalize_race_data(race_with_intel)
        html = build_course_route(rd)
        assert 'hardpack' in html

    def test_course_without_intel_unchanged(self, race_without_intel):
        rd = normalize_race_data(race_without_intel)
        html = build_course_route(rd)
        assert 'RIDERS REPORT' not in html

    def test_course_without_youtube_data_unchanged(self, minimal_race):
        rd = normalize_race_data(minimal_race)
        html = build_course_route(rd)
        assert 'RIDERS REPORT' not in html


class TestTrainingWithIntel:
    """Test that gear mentions inject into training section."""

    def test_training_includes_gear_mentions(self, race_with_intel):
        rd = normalize_race_data(race_with_intel)
        html = build_training(rd)
        assert '42mm' in html
        assert 'RIDERS REPORT' in html

    def test_training_without_intel_unchanged(self, race_without_intel):
        rd = normalize_race_data(race_without_intel)
        html = build_training(rd)
        assert 'RIDERS REPORT' not in html


class TestLogisticsWithIntel:
    """Test that race day tips inject into logistics section."""

    def test_logistics_includes_tips(self, race_with_intel):
        rd = normalize_race_data(race_with_intel)
        html = build_logistics_section(rd)
        assert 'headwind' in html
        assert 'RIDERS REPORT' in html

    def test_logistics_without_intel_unchanged(self, race_without_intel):
        rd = normalize_race_data(race_without_intel)
        html = build_logistics_section(rd)
        assert 'RIDERS REPORT' not in html


# ── Validation Function ───────────────────────────────────────

class TestValidateRiderIntel:
    """Test validate_rider_intel() correctness."""

    def test_valid_intel_passes(self):
        intel = {
            "extracted_at": "2026-02-23",
            "key_challenges": [
                {"name": "Ridge", "description": "Hard.", "source_video_ids": ["vKCSt1e392M"]},
            ],
            "terrain_notes": [
                {"text": "Chunky gravel.", "source_video_ids": ["vKCSt1e392M"]},
            ],
            "gear_mentions": [],
            "race_day_tips": [
                {"text": "Start easy.", "source_video_ids": ["vKCSt1e392M"]},
            ],
            "additional_quotes": [
                {"text": "Great aid stations.", "source_video_id": "vKCSt1e392M",
                 "source_channel": "Test", "source_view_count": 1000,
                 "category": "logistics", "curated": True},
            ],
            "search_text": " ".join(["word"] * 100),
        }
        errors = validate_rider_intel("test.json", intel, {"vKCSt1e392M"})
        assert errors == []

    def test_html_in_description_fails(self):
        intel = {
            "key_challenges": [
                {"name": "Test", "description": "<b>Bold</b>", "source_video_ids": []},
            ],
            "terrain_notes": [],
            "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [],
            "search_text": " ".join(["word"] * 100),
        }
        errors = validate_rider_intel("test.json", intel, set())
        assert any("HTML" in e for e in errors)

    def test_invalid_video_id_reference_fails(self):
        intel = {
            "key_challenges": [
                {"name": "Test", "description": "OK.", "source_video_ids": ["NONEXISTENT"]},
            ],
            "terrain_notes": [],
            "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [],
            "search_text": " ".join(["word"] * 100),
        }
        errors = validate_rider_intel("test.json", intel, {"vKCSt1e392M"})
        assert any("unknown video_id" in e for e in errors)

    def test_invalid_quote_category_fails(self):
        intel = {
            "key_challenges": [],
            "terrain_notes": [],
            "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [
                {"text": "Quote.", "source_video_id": "vKCSt1e392M",
                 "category": "invalid_cat", "curated": True},
            ],
            "search_text": " ".join(["word"] * 100),
        }
        errors = validate_rider_intel("test.json", intel, {"vKCSt1e392M"})
        assert any("invalid category" in e for e in errors)

    def test_search_text_too_short_fails(self):
        intel = {
            "key_challenges": [],
            "terrain_notes": [],
            "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [],
            "search_text": "Too short.",
        }
        errors = validate_rider_intel("test.json", intel, set())
        assert any("too short" in e for e in errors)

    def test_search_text_too_long_fails(self):
        intel = {
            "key_challenges": [],
            "terrain_notes": [],
            "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [],
            "search_text": " ".join(["word"] * 600),
        }
        errors = validate_rider_intel("test.json", intel, set())
        assert any("too long" in e for e in errors)

    def test_html_in_search_text_fails(self):
        intel = {
            "key_challenges": [],
            "terrain_notes": [],
            "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [],
            "search_text": "This has <script>alert(1)</script> in it " + " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test.json", intel, set())
        assert any("HTML" in e for e in errors)

    def test_invalid_extracted_at_fails(self):
        intel = {
            "extracted_at": "not-a-date",
            "key_challenges": [],
            "terrain_notes": [],
            "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [],
            "search_text": " ".join(["word"] * 100),
        }
        errors = validate_rider_intel("test.json", intel, set())
        assert any("extracted_at" in e for e in errors)


# ── Schema Validation (across live profiles) ──────────────────

class TestRiderIntelSchemaAcrossProfiles:
    """Validate rider_intel structure in any enriched race profiles."""

    @pytest.fixture
    def intel_profiles(self):
        """Collect all race profiles that have rider_intel."""
        if not RACE_DATA_DIR.exists():
            pytest.skip("race-data directory not found")
        profiles = []
        for f in RACE_DATA_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                race = data.get("race", data)
                yt = race.get("youtube_data", {})
                if yt.get("rider_intel"):
                    video_ids = {v.get("video_id") for v in yt.get("videos", [])}
                    profiles.append((f.name, yt["rider_intel"], video_ids))
            except (json.JSONDecodeError, IOError):
                continue
        return profiles

    def test_all_rider_intel_valid(self, intel_profiles):
        """All rider_intel blocks must pass validation."""
        all_errors = []
        for fname, intel, video_ids in intel_profiles:
            errors = validate_rider_intel(fname, intel, video_ids)
            all_errors.extend(errors)
        assert not all_errors, "\n".join(all_errors)

    def test_search_text_has_no_html(self, intel_profiles):
        violations = []
        for fname, intel, _ in intel_profiles:
            st = intel.get("search_text", "")
            if HTML_RE.search(st):
                violations.append(f"{fname}: search_text contains HTML")
        assert not violations, "\n".join(violations)

    def test_all_text_fields_have_no_html(self, intel_profiles):
        violations = []
        for fname, intel, _ in intel_profiles:
            for field in ("key_challenges", "terrain_notes", "gear_mentions", "race_day_tips"):
                for item in intel.get(field, []):
                    for key in ("text", "description", "name"):
                        val = item.get(key, "")
                        if val and HTML_RE.search(val):
                            violations.append(f"{fname}: {field}.{key} contains HTML")
        assert not violations, "\n".join(violations)


# ── Edge Cases: normalize_intel ──────────────────────────────

class TestNormalizeIntel:
    """Test normalize_intel type coercion — catching LLM output instability."""

    def test_mile_marker_int_coerced_to_string(self):
        """LLM returns mile_marker as int 45 instead of string '45'."""
        intel = {
            "key_challenges": [
                {"name": "Ridge", "mile_marker": 45, "description": "Hard.",
                 "source_video_ids": ["abc12345678"]},
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": "OK.",
        }
        result = normalize_intel(intel)
        assert result["key_challenges"][0]["mile_marker"] == "45"
        assert isinstance(result["key_challenges"][0]["mile_marker"], str)

    def test_mile_marker_zero_coerced_to_string_zero(self):
        """int 0 must become '0' not '' — bool(0) is False but '0' is truthy."""
        intel = {
            "key_challenges": [
                {"name": "Start", "mile_marker": 0, "description": "Chaos.",
                 "source_video_ids": []},
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": "OK.",
        }
        result = normalize_intel(intel)
        assert result["key_challenges"][0]["mile_marker"] == "0"

    def test_mile_marker_none_coerced_to_empty_string(self):
        intel = {
            "key_challenges": [
                {"name": "Somewhere", "mile_marker": None, "description": "Hard.",
                 "source_video_ids": []},
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": "OK.",
        }
        result = normalize_intel(intel)
        assert result["key_challenges"][0]["mile_marker"] == ""

    def test_source_video_ids_string_coerced_to_list(self):
        """LLM returns single string instead of array."""
        intel = {
            "key_challenges": [],
            "terrain_notes": [
                {"text": "Gravel.", "source_video_ids": "abc12345678"},
            ],
            "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": "OK.",
        }
        result = normalize_intel(intel)
        assert result["terrain_notes"][0]["source_video_ids"] == ["abc12345678"]

    def test_source_video_ids_empty_string_coerced_to_empty_list(self):
        intel = {
            "key_challenges": [],
            "terrain_notes": [
                {"text": "Gravel.", "source_video_ids": ""},
            ],
            "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": "OK.",
        }
        result = normalize_intel(intel)
        assert result["terrain_notes"][0]["source_video_ids"] == []

    def test_source_video_ids_int_coerced_to_empty_list(self):
        """Pathological: LLM returns a number."""
        intel = {
            "key_challenges": [
                {"name": "X", "description": "Y.", "source_video_ids": 1},
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": "OK.",
        }
        result = normalize_intel(intel)
        assert result["key_challenges"][0]["source_video_ids"] == []

    def test_non_list_field_coerced_to_empty(self):
        """LLM returns a string where an array is expected."""
        intel = {
            "key_challenges": "none",
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": "OK.",
        }
        result = normalize_intel(intel)
        assert result["key_challenges"] == []

    def test_additional_quotes_non_list_coerced(self):
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [], "additional_quotes": "none", "search_text": "OK.",
        }
        result = normalize_intel(intel)
        assert result["additional_quotes"] == []

    def test_search_text_non_string_coerced(self):
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [], "additional_quotes": [], "search_text": 12345,
        }
        result = normalize_intel(intel)
        assert result["search_text"] == "12345"
        assert isinstance(result["search_text"], str)


# ── Edge Cases: validate_intel ───────────────────────────────

class TestValidateRiderIntelAllEdgeCases:
    """Edge cases for validate_rider_intel() — single source of truth."""

    def test_source_video_ids_not_a_list_fails(self):
        intel = {
            "key_challenges": [
                {"name": "X", "description": "Y.", "source_video_ids": "abc12345678"},
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, {"abc12345678"})
        assert any("must be a list" in e for e in errors)

    def test_additional_quote_missing_source_channel(self):
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [
                {"text": "Good.", "source_video_id": "abc12345678",
                 "source_view_count": 1000, "category": "logistics", "curated": True},
            ],
            "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, {"abc12345678"})
        assert any("source_channel" in e for e in errors)

    def test_additional_quote_missing_source_view_count(self):
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [
                {"text": "Good.", "source_video_id": "abc12345678",
                 "source_channel": "Test", "category": "logistics", "curated": True},
            ],
            "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, {"abc12345678"})
        assert any("source_view_count" in e for e in errors)

    def test_empty_search_text_fails(self):
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [], "additional_quotes": [], "search_text": "",
        }
        errors = validate_rider_intel("test", intel, set())
        assert any("empty" in e for e in errors)

    def test_too_many_challenges_fails(self):
        intel = {
            "key_challenges": [
                {"name": f"C{i}", "description": "Hard.", "source_video_ids": []}
                for i in range(7)
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, set())
        assert any("too many key_challenges" in e for e in errors)

    def test_too_many_additional_quotes_fails(self):
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [
                {"text": f"Q{i}.", "source_video_id": "abc12345678",
                 "source_channel": "T", "source_view_count": 1, "category": "logistics", "curated": True}
                for i in range(6)
            ],
            "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, {"abc12345678"})
        assert any("too many additional_quotes" in e for e in errors)

    def test_valid_intel_passes_clean(self):
        """Comprehensive valid intel with all fields — 0 errors expected."""
        intel = {
            "key_challenges": [
                {"name": "Ridge", "mile_marker": "45", "description": "Hard climb.",
                 "source_video_ids": ["abc12345678"]},
            ],
            "terrain_notes": [
                {"text": "Chunky limestone.", "source_video_ids": ["abc12345678"]},
            ],
            "gear_mentions": [
                {"text": "42mm tires.", "source_video_ids": ["abc12345678"]},
            ],
            "race_day_tips": [
                {"text": "Start slow.", "source_video_ids": ["abc12345678"]},
            ],
            "additional_quotes": [
                {"text": "Great community.", "source_video_id": "abc12345678",
                 "source_channel": "Test Channel", "source_view_count": 5000,
                 "category": "community", "curated": True},
            ],
            "search_text": " ".join(["word"] * 100),
        }
        errors = validate_rider_intel("test", intel, {"abc12345678"})
        assert errors == [], f"Expected no errors, got: {errors}"


# ── Edge Cases: Quote Merge ──────────────────────────────────

class TestQuoteMergeEdgeCases:
    """Edge cases for _merge_youtube_quotes."""

    def test_case_insensitive_dedup(self):
        """Duplicate detection should be case-insensitive."""
        yt = {
            "quotes": [
                {"text": "The course is beautiful.", "curated": True},
            ],
            "rider_intel": {
                "additional_quotes": [
                    {"text": "the course is beautiful.", "curated": True},
                ],
            },
        }
        result = _merge_youtube_quotes(yt)
        assert len(result) == 1

    def test_whitespace_insensitive_dedup(self):
        """Leading/trailing whitespace should not prevent dedup."""
        yt = {
            "quotes": [
                {"text": "  Great race.  ", "curated": True},
            ],
            "rider_intel": {
                "additional_quotes": [
                    {"text": "Great race.", "curated": True},
                ],
            },
        }
        result = _merge_youtube_quotes(yt)
        assert len(result) == 1

    def test_no_rider_intel_key(self):
        """youtube_data with no rider_intel key at all."""
        yt = {"quotes": [{"text": "Solo.", "curated": True}]}
        result = _merge_youtube_quotes(yt)
        assert len(result) == 1


# ── Edge Cases: Validation Boundary Conditions ───────────────

class TestValidationBoundaryConditions:
    """Boundary conditions that stress the validate_rider_intel() function.

    Catches regressions from the consolidation of validate_intel → validate_rider_intel.
    """

    def test_exactly_6_challenges_passes(self):
        """6 is the max — must pass."""
        intel = {
            "key_challenges": [
                {"name": f"C{i}", "description": "Hard.", "source_video_ids": []}
                for i in range(6)
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, set())
        assert not any("too many key_challenges" in e for e in errors)

    def test_exactly_5_quotes_passes(self):
        """5 is the max — must pass."""
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [
                {"text": f"Q{i}.", "source_video_id": "abc12345678",
                 "source_channel": "T", "source_view_count": 1, "category": "logistics", "curated": True}
                for i in range(5)
            ],
            "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, {"abc12345678"})
        assert not any("too many additional_quotes" in e for e in errors)

    def test_search_text_exactly_30_words_passes(self):
        """30 words is the minimum — must pass."""
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [], "additional_quotes": [],
            "search_text": " ".join(["word"] * 30),
        }
        errors = validate_rider_intel("test", intel, set())
        assert not any("too short" in e for e in errors)

    def test_search_text_29_words_fails(self):
        """29 words is below minimum — must fail."""
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [], "additional_quotes": [],
            "search_text": " ".join(["word"] * 29),
        }
        errors = validate_rider_intel("test", intel, set())
        assert any("too short" in e for e in errors)

    def test_search_text_exactly_500_words_passes(self):
        """500 words is the max — must pass."""
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [], "additional_quotes": [],
            "search_text": " ".join(["word"] * 500),
        }
        errors = validate_rider_intel("test", intel, set())
        assert not any("too long" in e for e in errors)

    def test_search_text_501_words_fails(self):
        """501 words exceeds max — must fail."""
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [], "additional_quotes": [],
            "search_text": " ".join(["word"] * 501),
        }
        errors = validate_rider_intel("test", intel, set())
        assert any("too long" in e for e in errors)

    def test_missing_search_text_key_entirely(self):
        """No search_text key at all — must report missing."""
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [], "additional_quotes": [],
        }
        errors = validate_rider_intel("test", intel, set())
        assert any("empty" in e or "missing" in e for e in errors)

    def test_challenge_missing_name(self):
        intel = {
            "key_challenges": [
                {"description": "Hard.", "source_video_ids": []},
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, set())
        assert any("missing 'name'" in e for e in errors)

    def test_challenge_missing_description(self):
        intel = {
            "key_challenges": [
                {"name": "Ridge", "source_video_ids": []},
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, set())
        assert any("missing 'description'" in e for e in errors)

    def test_terrain_note_missing_text(self):
        intel = {
            "key_challenges": [],
            "terrain_notes": [{"source_video_ids": []}],
            "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, set())
        assert any("missing 'text'" in e for e in errors)

    def test_html_in_challenge_name(self):
        intel = {
            "key_challenges": [
                {"name": '<script>alert("xss")</script>', "description": "OK.",
                 "source_video_ids": []},
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, set())
        assert any("HTML" in e for e in errors)

    def test_html_in_additional_quote_text(self):
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [
                {"text": '<b>Bold</b> stuff.', "source_video_id": "abc12345678",
                 "source_channel": "T", "source_view_count": 1, "category": "logistics"},
            ],
            "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, {"abc12345678"})
        assert any("HTML" in e for e in errors)

    def test_invalid_extracted_at_date_format(self):
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [], "additional_quotes": [],
            "search_text": " ".join(["word"] * 50),
            "extracted_at": "02-23-2026",  # MM-DD-YYYY instead of YYYY-MM-DD
        }
        errors = validate_rider_intel("test", intel, set())
        assert any("extracted_at" in e for e in errors)

    def test_valid_extracted_at_passes(self):
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [], "additional_quotes": [],
            "search_text": " ".join(["word"] * 50),
            "extracted_at": "2026-02-23",
        }
        errors = validate_rider_intel("test", intel, set())
        assert not any("extracted_at" in e for e in errors)

    def test_source_video_ids_references_nonexistent_video(self):
        """Cross-reference check: source_video_ids must reference real videos."""
        intel = {
            "key_challenges": [
                {"name": "X", "description": "Y.",
                 "source_video_ids": ["NONEXISTENT"]},
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, {"abc12345678"})
        assert any("unknown video_id" in e for e in errors)

    def test_additional_quote_invalid_category(self):
        intel = {
            "key_challenges": [], "terrain_notes": [], "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [
                {"text": "Good.", "source_video_id": "abc12345678",
                 "source_channel": "T", "source_view_count": 1,
                 "category": "race_philosophy"},  # LLM-invented category
            ],
            "search_text": " ".join(["word"] * 50),
        }
        errors = validate_rider_intel("test", intel, {"abc12345678"})
        assert any("invalid category" in e for e in errors)


# ── Edge Cases: Normalize + Validate Pipeline ────────────────

class TestNormalizeValidatePipeline:
    """Test that normalize_intel fixes types so validate_rider_intel passes.

    This catches the real-world scenario: LLM returns wonky types, normalize
    fixes them, then validation runs clean.
    """

    def test_normalize_then_validate_passes(self):
        """Simulates actual extraction pipeline: normalize → validate → pass."""
        raw_intel = {
            "key_challenges": [
                {"name": "Ridge", "mile_marker": 45,  # int, not str
                 "description": "Hard.", "source_video_ids": "abc12345678"},  # str, not list
            ],
            "terrain_notes": [
                {"text": "Chunky.", "source_video_ids": ["abc12345678"]},
            ],
            "gear_mentions": [],
            "race_day_tips": [],
            "additional_quotes": [],
            "search_text": " ".join(["word"] * 100),
        }
        normalized = normalize_intel(raw_intel)
        errors = validate_rider_intel("test", normalized, {"abc12345678"})
        assert errors == [], f"Expected 0 errors after normalize, got: {errors}"

    def test_normalize_cannot_fix_missing_text(self):
        """normalize_intel can't add missing required fields — validation should catch."""
        raw_intel = {
            "key_challenges": [
                {"name": "Ridge", "source_video_ids": []},  # missing description
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": " ".join(["word"] * 50),
        }
        normalized = normalize_intel(raw_intel)
        errors = validate_rider_intel("test", normalized, set())
        assert any("missing 'description'" in e for e in errors)

    def test_normalize_cannot_fix_html(self):
        """normalize_intel doesn't strip HTML — validation should catch."""
        raw_intel = {
            "key_challenges": [
                {"name": "Ridge", "description": "<b>Bold</b> text.",
                 "source_video_ids": []},
            ],
            "terrain_notes": [], "gear_mentions": [], "race_day_tips": [],
            "additional_quotes": [], "search_text": " ".join(["word"] * 50),
        }
        normalized = normalize_intel(raw_intel)
        errors = validate_rider_intel("test", normalized, set())
        assert any("HTML" in e for e in errors)


# ── Edge Cases: XSS in Callout Rendering ─────────────────────

class TestCalloutXSSDefense:
    """Verify esc() prevents XSS in all rider intel text paths."""

    def test_script_tag_in_challenge_name_escaped(self):
        items = [{"name": '<script>alert(1)</script>', "description": "OK."}]
        html = _build_riders_report([(items, "named")])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_event_handler_in_description_escaped(self):
        items = [{"name": "X", "description": 'onload="fetch(evil)"'}]
        html = _build_riders_report([(items, "named")])
        assert 'onload=' not in html or '&quot;' in html

    def test_angle_brackets_in_text_items_escaped(self):
        items = [{"text": '<img src=x onerror=alert(1)>'}]
        html = _build_riders_report([(items, "text")])
        assert "<img" not in html
        assert "&lt;img" in html

    def test_ampersand_in_text_preserved(self):
        items = [{"text": "Rock & roll terrain."}]
        html = _build_riders_report([(items, "text")])
        assert "&amp;" in html
        assert "& roll" not in html  # must be escaped

    def test_mile_marker_with_html_escaped(self):
        items = [{"name": "X", "description": "Y.", "mile_marker": '<script>1</script>'}]
        html = _build_riders_report([(items, "named")])
        assert "<script>" not in html
