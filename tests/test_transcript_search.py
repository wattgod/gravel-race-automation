"""Tests for transcript search — index st field validation + search integration.

Covers:
  - generate_index adds st field from rider_intel.search_text
  - Fallback: st from curated quote text when no rider_intel
  - No st field when no transcripts or quotes
  - st field has no HTML
  - st field is reasonable length
"""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generate_index import build_index_entry_from_profile

HTML_RE = re.compile(r'<[a-z][^>]*>', re.IGNORECASE)
RACE_DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def base_race():
    """Base race data for index entry generation."""
    return {
        "race": {
            "name": "Test Race",
            "display_name": "Test Race",
            "slug": "test-race",
            "vitals": {
                "location": "Emporia, Kansas",
                "date": "June annually",
                "distance_mi": 100,
                "elevation_ft": 5000,
            },
            "gravel_god_rating": {
                "overall_score": 75,
                "tier": 2,
                "tier_label": "TIER 2",
                "logistics": 3, "length": 3, "technicality": 3,
                "elevation": 3, "climate": 3, "altitude": 2, "adventure": 3,
                "prestige": 4, "race_quality": 4, "experience": 4,
                "community": 4, "field_depth": 4, "value": 3, "expenses": 3,
                "discipline": "gravel",
            },
            "tagline": "The original gravel race.",
        }
    }


# ── Index st Field ────────────────────────────────────────────

class TestIndexSearchTextField:
    """Test st field generation in index entries."""

    def test_st_from_rider_intel_search_text(self, base_race):
        base_race["race"]["youtube_data"] = {
            "rider_intel": {
                "search_text": "Riders describe this as a challenging race with rocky terrain and headwinds.",
            },
            "quotes": [],
            "videos": [],
        }
        entry = build_index_entry_from_profile("test-race", base_race)
        assert entry["st"] == "Riders describe this as a challenging race with rocky terrain and headwinds."

    def test_st_fallback_to_curated_quotes(self, base_race):
        base_race["race"]["youtube_data"] = {
            "quotes": [
                {"text": "The mud was insane.", "curated": True},
                {"text": "Beautiful scenery throughout.", "curated": True},
                {"text": "Not curated.", "curated": False},
            ],
            "videos": [],
        }
        entry = build_index_entry_from_profile("test-race", base_race)
        assert "st" in entry
        assert "mud was insane" in entry["st"]
        assert "Beautiful scenery" in entry["st"]
        assert "Not curated" not in entry["st"]

    def test_no_st_when_no_youtube_data(self, base_race):
        entry = build_index_entry_from_profile("test-race", base_race)
        assert "st" not in entry

    def test_no_st_when_empty_youtube_data(self, base_race):
        base_race["race"]["youtube_data"] = {
            "quotes": [],
            "videos": [],
        }
        entry = build_index_entry_from_profile("test-race", base_race)
        assert "st" not in entry

    def test_st_prefers_rider_intel_over_quotes(self, base_race):
        base_race["race"]["youtube_data"] = {
            "rider_intel": {
                "search_text": "Intel search text with specific details.",
            },
            "quotes": [
                {"text": "Quote text.", "curated": True},
            ],
            "videos": [],
        }
        entry = build_index_entry_from_profile("test-race", base_race)
        assert entry["st"] == "Intel search text with specific details."
        assert "Quote text" not in entry["st"]


# ── Schema Validation (across live index) ─────────────────────

class TestSearchTextAcrossProfiles:
    """Validate st field quality across all profiled races."""

    @pytest.fixture
    def index_entries_with_st(self):
        """Build index entries for all profiled races and return those with st."""
        if not RACE_DATA_DIR.exists():
            pytest.skip("race-data directory not found")
        entries = []
        for f in RACE_DATA_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                entry = build_index_entry_from_profile(f.stem, data)
                if "st" in entry:
                    entries.append((f.name, entry))
            except (json.JSONDecodeError, IOError):
                continue
        return entries

    def test_st_field_has_no_html(self, index_entries_with_st):
        violations = []
        for fname, entry in index_entries_with_st:
            if HTML_RE.search(entry["st"]):
                violations.append(f"{fname}: st field contains HTML")
        assert not violations, "\n".join(violations)

    def test_st_field_reasonable_length(self, index_entries_with_st):
        """st field should be between 10 and 2000 characters."""
        violations = []
        for fname, entry in index_entries_with_st:
            length = len(entry["st"])
            if length < 10:
                violations.append(f"{fname}: st field too short ({length} chars)")
            elif length > 2000:
                violations.append(f"{fname}: st field too long ({length} chars)")
        assert not violations, "\n".join(violations)
