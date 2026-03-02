"""Tests for generate_llms_txt.py.

Includes v2 edge case tests for markdown table escaping,
generation timestamps, T3/T4 discipline column, and enriched T1/T2 summaries.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts.generate_llms_txt import (
    generate_llms_txt,
    generate_llms_full_txt,
    _md_escape,
    _fmt_dist,
    _fmt_elev,
    _num,
    _race_summary,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_FILE = PROJECT_ROOT / "web" / "race-index.json"
RACE_DATA_DIR = PROJECT_ROOT / "race-data"


@pytest.fixture
def index():
    return json.loads(INDEX_FILE.read_text())


class TestLlmsTxt:
    def test_starts_with_heading(self, index):
        txt = generate_llms_txt(index)
        assert txt.startswith("# Gravel God Race Database")

    def test_has_race_count(self, index):
        txt = generate_llms_txt(index)
        assert "328" in txt

    def test_has_tier_breakdown(self, index):
        txt = generate_llms_txt(index)
        assert "Tier 1" in txt
        assert "Tier 4" in txt

    def test_has_machine_readable_links(self, index):
        txt = generate_llms_txt(index)
        assert "llms-full.txt" in txt
        assert "race-index.json" in txt
        assert "api/v1/docs" in txt
        assert "feed/races.xml" in txt

    def test_has_contact(self, index):
        txt = generate_llms_txt(index)
        assert "matt@gravelgodcycling.com" in txt

    def test_reasonable_size(self, index):
        txt = generate_llms_txt(index)
        assert 500 < len(txt) < 5000

    def test_has_generation_timestamp(self, index):
        """v2: llms.txt should include a generation date."""
        txt = generate_llms_txt(index)
        assert "Generated:" in txt or "generated:" in txt.lower() or "Last generated:" in txt


class TestLlmsFullTxt:
    def test_starts_with_heading(self, index):
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)
        assert txt.startswith("# Gravel God Race Database")

    def test_has_scoring_methodology(self, index):
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)
        assert "Scoring Methodology" in txt
        assert "14 dimensions" in txt

    def test_has_t1_t2_section(self, index):
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)
        assert "Tier 1 & Tier 2 Races" in txt

    def test_has_t3_t4_table(self, index):
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)
        assert "Tier 3 & Tier 4 Races" in txt
        assert "| Name |" in txt

    def test_has_unbound_summary(self, index):
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)
        assert "Unbound" in txt

    def test_has_data_schema(self, index):
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)
        assert "Data Schema" in txt
        assert "race.vitals" in txt

    def test_all_t1_t2_races_present(self, index):
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)
        t1_t2 = [r for r in index if r.get("tier", 4) <= 2]
        for r in t1_t2:
            assert r["name"] in txt, f"Missing T1/T2 race: {r['name']}"

    def test_reasonable_size(self, index):
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)
        # Should be substantial but not huge
        assert 50_000 < len(txt) < 500_000

    def test_t1_before_t2(self, index):
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)
        # Tour Divide (T1, 94) should appear before a T2 race
        t1_pos = txt.index("Tour Divide")
        # Find first T2-only race
        t2_races = [r for r in index if r.get("tier") == 2]
        if t2_races:
            t2_name = t2_races[0]["name"]
            if t2_name in txt:
                t2_pos = txt.index(t2_name)
                assert t1_pos < t2_pos

    def test_t3_t4_table_has_discipline_column(self, index):
        """v2: T3/T4 table must include a Discipline column."""
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)
        # Find the T3/T4 table header row
        assert "| Discipline |" in txt

    def test_has_generation_timestamp(self, index):
        """v2: llms-full.txt should include a generation date."""
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)
        assert "Generated:" in txt or "generated:" in txt.lower()


# ---------------------------------------------------------------------------
# v2 edge case tests: markdown escaping
# ---------------------------------------------------------------------------

class TestMarkdownEscaping:
    def test_md_escape_pipe_char(self):
        """Pipe chars in table cells must be escaped to prevent table breakage."""
        assert _md_escape("hello | world") == "hello \\| world"

    def test_md_escape_newline(self):
        """Newlines in table cells must be replaced with spaces."""
        assert _md_escape("line1\nline2") == "line1 line2"

    def test_md_escape_none(self):
        """None should render as em-dash."""
        assert _md_escape(None) == "—"

    def test_md_escape_normal_text(self):
        """Normal text should pass through unchanged."""
        assert _md_escape("Emporia, Kansas") == "Emporia, Kansas"

    def test_md_escape_combined(self):
        """Multiple special chars in one string."""
        assert _md_escape("a|b\nc") == "a\\|b c"

    def test_pipe_in_race_name_doesnt_break_table(self, index):
        """If any race has | in name/location, the table should still be valid markdown."""
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)
        for line in txt.splitlines():
            if line.startswith("|") and "|" in line[1:]:
                # Count pipe separators (unescaped pipes)
                # An escaped pipe \| should not count as a cell separator
                unescaped = line.replace("\\|", "XX")
                # Every table row should have consistent column count
                # Just verify no completely broken lines
                assert unescaped.count("|") >= 2


# ---------------------------------------------------------------------------
# Helper edge cases
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    def test_num_none(self):
        assert _num(None) == 0

    def test_num_zero(self):
        assert _num(0) == 0.0

    def test_num_comma_string(self):
        assert _num("11,000") == 11000.0

    def test_num_garbage(self):
        assert _num("N/A") == 0

    def test_fmt_dist_zero(self):
        assert _fmt_dist(0) == "—"

    def test_fmt_dist_integer(self):
        assert _fmt_dist(200) == "200 mi"

    def test_fmt_dist_fractional(self):
        assert _fmt_dist(134.5) == "134.5 mi"

    def test_fmt_elev_zero(self):
        assert _fmt_elev(0) == "—"

    def test_fmt_elev_normal(self):
        assert _fmt_elev(11000) == "11,000 ft"

    def test_fmt_elev_comma_string(self):
        assert _fmt_elev("11,000") == "11,000 ft"

    def test_num_negative(self):
        assert _num(-5) == -5.0

    def test_num_empty_string(self):
        assert _num("") == 0

    def test_num_bool(self):
        assert _num(True) == 1.0


# ---------------------------------------------------------------------------
# Empty/edge case inputs
# ---------------------------------------------------------------------------

class TestEmptyInputs:
    """Generators must handle empty or minimal inputs without crashing."""

    def test_llms_txt_empty_index(self):
        txt = generate_llms_txt([])
        assert "# Gravel God Race Database" in txt
        assert "0 races" in txt or "0" in txt

    def test_llms_full_txt_empty_index(self, tmp_path):
        txt = generate_llms_full_txt([], tmp_path)
        assert "# Gravel God Race Database" in txt
        assert "0 races" in txt.split("\n")[2] or "0" in txt[:200]

    def test_llms_full_txt_all_t4(self, tmp_path):
        """Index with only T4 races should produce a table, no T1/T2 section content."""
        index = [
            {"slug": "test", "name": "Test Race", "tier": 4, "overall_score": 30,
             "distance_mi": 50, "elevation_ft": 1000, "location": "Here",
             "month": "June", "discipline": "gravel"},
        ]
        txt = generate_llms_full_txt(index, tmp_path)
        assert "Tier 1 & Tier 2 Races (0 races)" in txt
        assert "Tier 3 & Tier 4 Races (1 races)" in txt


# ---------------------------------------------------------------------------
# _race_summary edge cases (silent failure detection)
# ---------------------------------------------------------------------------

class TestRaceSummary:
    """_race_summary silently returns '' on failure — test it directly."""

    def test_missing_profile_returns_empty(self, tmp_path):
        result = _race_summary("nonexistent-slug", tmp_path)
        assert result == ""

    def test_corrupt_json_returns_empty(self, tmp_path):
        (tmp_path / "bad.json").write_text("{{{invalid")
        result = _race_summary("bad", tmp_path)
        assert result == ""

    def test_profile_missing_all_fields_returns_empty(self, tmp_path):
        """Profile with no verdict, course, or opinion should return empty."""
        (tmp_path / "minimal.json").write_text('{"race": {}}')
        result = _race_summary("minimal", tmp_path)
        assert result == ""

    def test_profile_with_verdict_returns_content(self, tmp_path):
        profile = {"race": {"final_verdict": {"one_liner": "Go ride it."}}}
        (tmp_path / "good.json").write_text(json.dumps(profile))
        result = _race_summary("good", tmp_path)
        assert "Go ride it." in result

    def test_t1_t2_races_have_summaries(self):
        """SILENT FAILURE CHECK: T1/T2 races in llms-full.txt should have actual
        summary content, not just headers. If _race_summary silently returns ''
        for all races, we'd produce valid-looking but content-empty output."""
        index = json.loads(INDEX_FILE.read_text())
        t1_t2 = [r for r in index if r.get("tier", 4) <= 2]
        txt = generate_llms_full_txt(index, RACE_DATA_DIR)

        # Check that at least 80% of T1/T2 races have non-empty summaries
        races_with_summaries = 0
        for r in t1_t2:
            slug = r["slug"]
            name = r.get("name", slug)
            # Find the section for this race and check it has paragraph text
            pos = txt.find(f"### {name}")
            if pos >= 0:
                # Get the text after the header line until the next ### or ##
                after_header = txt[pos:]
                lines = after_header.split("\n")
                # Skip header, vitals line, profile URL line, empty lines
                content_lines = [
                    l for l in lines[3:10]
                    if l.strip() and not l.startswith("###") and not l.startswith("##")
                ]
                if content_lines:
                    races_with_summaries += 1

        pct = races_with_summaries / len(t1_t2) if t1_t2 else 0
        assert pct >= 0.80, (
            f"Only {races_with_summaries}/{len(t1_t2)} ({pct:.0%}) T1/T2 races "
            f"have summaries. _race_summary may be silently failing."
        )
