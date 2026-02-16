"""Tests for race recap generator and results extractor."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_race_recap import (
    find_recap_candidates,
    generate_recap_html,
    has_results,
    load_race,
)
from extract_results import (
    extract_conditions,
    extract_dnf_rate,
    extract_field_size_actual,
    extract_key_takeaways,
    extract_winner,
    extract_winning_time,
)


# ── has_results ──


def test_has_results_with_winner():
    race = {
        "results": {
            "years": {
                "2024": {"winner_male": "Test Winner"}
            }
        }
    }
    assert has_results(race, 2024) is True


def test_has_results_with_female_winner():
    race = {
        "results": {
            "years": {
                "2024": {"winner_female": "Test Winner"}
            }
        }
    }
    assert has_results(race, 2024) is True


def test_has_results_no_results():
    race = {"name": "Test Race"}
    assert has_results(race, 2024) is False


def test_has_results_wrong_year():
    race = {
        "results": {
            "years": {
                "2023": {"winner_male": "Test"}
            }
        }
    }
    assert has_results(race, 2024) is False


def test_has_results_empty_year():
    race = {
        "results": {
            "years": {
                "2024": {}
            }
        }
    }
    assert has_results(race, 2024) is False


# ── extract_winner ──


# Format 1: Unbound style — bold inline names with year prefix
DUMP_UNBOUND = """
**RESULTS & DNF DATA**

**Recent Winners & Times:**
*2024:* **Cameron Jones** (USA) in **8:34:39** – a new men's course record.
**Karolina Sowa Migon** (POL) won women in **10:27:00** after a sprint finish.

*2023:* **Keegan Swenson** (USA) won the men's race in 9:15:42.
**Rosa Klöser** won the women's field in 10:52:18.
"""

# Format 2: BWR style — list items with "Men:/Women:" labels
DUMP_BWR = """
## HISTORICAL RESULTS

**2023 Winners:**
- Men: Payson McElveen (5:48:32) [Athlinks] (https://www.athlinks.com)
- Women: Alexey Vermeulen (6:22:14) [Athlinks] (https://www.athlinks.com)

**2019:** Ted King (men), Krista Doebel-Hickok (women)
"""

# Format 3: Grinduro style — list with "Men's Pro:/Women:" and optional team info
DUMP_GRINDURO = """
### Notable Winners & Participants

**2024 (Pennsylvania):**
- Women: Meredith Miller (Shimano) - fresh from Unbound category win
- Men: Gordon Wadsworth (Revel)

**2022 (Mt. Shasta, CA):**
- Men: Michael van den Ham (Canadian champion) - 41:43.65
- Women: Caitlin Bernstein (Easton Overland, cyclocross pro) - 48:22.02
"""


# ── extract_winner: Format 1 (Unbound) ──


def test_extract_winner_unbound_male():
    winner = extract_winner(DUMP_UNBOUND, "test", "male", 2024)
    assert winner == "Cameron Jones"


def test_extract_winner_unbound_female():
    winner = extract_winner(DUMP_UNBOUND, "test", "female", 2024)
    assert winner == "Karolina Sowa Migon"


# ── extract_winner: Format 2 (BWR list) ──


def test_extract_winner_bwr_male():
    winner = extract_winner(DUMP_BWR, "test", "male", 2023)
    assert winner == "Payson McElveen"


def test_extract_winner_bwr_female():
    winner = extract_winner(DUMP_BWR, "test", "female", 2023)
    assert winner == "Alexey Vermeulen"


# ── extract_winner: Format 3 (Grinduro list) ──


def test_extract_winner_grinduro_male():
    winner = extract_winner(DUMP_GRINDURO, "test", "male", 2024)
    assert winner == "Gordon Wadsworth"


def test_extract_winner_grinduro_female():
    winner = extract_winner(DUMP_GRINDURO, "test", "female", 2024)
    assert winner == "Meredith Miller"


# ── extract_winner: Edge cases ──


def test_extract_winner_empty_dump():
    assert extract_winner("", "test", "male", 2024) == ""


def test_extract_winner_no_year():
    assert extract_winner(DUMP_UNBOUND, "test", "male", 2020) == ""


# ── extract_winning_time ──


def test_extract_time_unbound_male():
    time = extract_winning_time(DUMP_UNBOUND, "test", "male", 2024)
    assert time == "8:34:39"


def test_extract_time_bwr_male():
    time = extract_winning_time(DUMP_BWR, "test", "male", 2023)
    assert time == "5:48:32"


def test_extract_time_bwr_female():
    time = extract_winning_time(DUMP_BWR, "test", "female", 2023)
    assert time == "6:22:14"


def test_extract_time_grinduro_male():
    time = extract_winning_time(DUMP_GRINDURO, "test", "male", 2022)
    assert time == "41:43.65"


def test_extract_time_empty():
    assert extract_winning_time("", "test", "male", 2024) == ""


# ── extract_conditions ──


WEATHER_DUMP = """
The 2024 race saw cool and dry conditions, ideal for racing with temperatures around 65F.
The 2023 edition was hit by brutal mud and rain, making it the hardest year in history.
"""


def test_extract_conditions_found():
    result = extract_conditions(WEATHER_DUMP, "test", 2024)
    assert result != ""
    assert any(kw in result.lower() for kw in ["cool", "dry", "ideal"])


def test_extract_conditions_empty():
    assert extract_conditions("", "test", 2024) == ""


def test_extract_conditions_no_year():
    assert extract_conditions(WEATHER_DUMP, "test", 2020) == ""


# ── extract_field_size_actual ──


FIELD_DUMP = """
In 2024, approximately 4,000 riders participated across all distances.
The 2023 event attracted ~3,500 participants despite bad weather.
"""


def test_extract_field_size():
    result = extract_field_size_actual(FIELD_DUMP, "test", 2024)
    assert result == 4000


def test_extract_field_size_empty():
    assert extract_field_size_actual("", "test", 2024) is None


# ── extract_dnf_rate ──


DNF_DUMP = """
2024 saw a 15% DNF rate with ideal conditions.
2023 had over 40% DNF due to mud and rain.
"""


def test_extract_dnf_found():
    result = extract_dnf_rate(DNF_DUMP, "test", 2024)
    assert result == 15


def test_extract_dnf_empty():
    assert extract_dnf_rate("", "test", 2024) is None


# ── extract_key_takeaways ──


TAKEAWAY_DUMP = """
*2024:* Cameron Jones set a **new course record** with 8:34:39.
The 2024 field was the **largest field ever** with 4,000 riders.
Women's race had the **closest sprint finish** in history.
"""


def test_extract_takeaways():
    result = extract_key_takeaways(TAKEAWAY_DUMP, "test", 2024)
    assert isinstance(result, list)
    assert len(result) >= 1


def test_extract_takeaways_empty():
    assert extract_key_takeaways("", "test", 2024) == []


def test_extract_takeaways_max_five():
    long_dump = "\n".join(
        f"2024: Record number {i} set a new course record."
        for i in range(10)
    )
    result = extract_key_takeaways(long_dump, "test", 2024)
    assert len(result) <= 5


# ── find_recap_candidates ──


def test_find_candidates_returns_list():
    candidates = find_recap_candidates()
    assert isinstance(candidates, list)


def test_find_candidates_have_required_keys():
    candidates = find_recap_candidates()
    if candidates:
        c = candidates[0]
        assert "slug" in c
        assert "name" in c
        assert "year" in c
        assert "tier" in c


# ── generate_recap_html ──


def test_generate_recap_with_results(tmp_path):
    """Test recap generation with a mock race that has results."""
    import generate_race_recap as recap_mod

    # Create a temporary race JSON with results
    race_data = {
        "race": {
            "name": "Test Race",
            "vitals": {"location": "Test, CO", "distance_mi": 200, "elevation_ft": 15000},
            "gravel_god_rating": {"tier": 1, "overall_score": 85},
            "results": {
                "years": {
                    "2024": {
                        "winner_male": "John Doe",
                        "winner_female": "Jane Smith",
                        "winning_time_male": "8:30:00",
                        "winning_time_female": "9:45:00",
                        "conditions": "Cool and dry",
                        "field_size_actual": 2000,
                        "dnf_rate_pct": 15,
                        "key_takeaways": ["New course record", "Largest field ever"]
                    }
                },
                "latest_year": "2024"
            }
        }
    }

    # Write temp JSON
    race_dir = tmp_path / "race-data"
    race_dir.mkdir()
    (race_dir / "test-race.json").write_text(json.dumps(race_data))

    # Patch RACE_DATA_DIR
    orig_dir = recap_mod.RACE_DATA_DIR
    recap_mod.RACE_DATA_DIR = race_dir

    try:
        html_content = recap_mod.generate_recap_html("test-race", 2024)
        assert html_content is not None
        assert "<!DOCTYPE html>" in html_content
        assert "Test Race" in html_content
        assert "2024" in html_content
        assert "John Doe" in html_content
        assert "Jane Smith" in html_content
        assert "8:30:00" in html_content
        assert "Cool and dry" in html_content
        assert "New course record" in html_content
        assert "Largest field ever" in html_content
        assert "og:title" in html_content
        assert "application/ld+json" in html_content
        assert "gg-blog-hero" in html_content
        assert "gg-blog-cta" in html_content
        assert "Race Recap" in html_content
        assert "Full Race Profile" in html_content
        assert "Free Prep Kit" in html_content
    finally:
        recap_mod.RACE_DATA_DIR = orig_dir


def test_generate_recap_nonexistent():
    html = generate_recap_html("nonexistent-race-12345", 2024)
    assert html is None


# ── Integration: real dump extraction ──


def test_extract_real_unbound_winner_male():
    """Extract winner from actual Unbound research dump."""
    from extract_results import load_dump
    dump = load_dump("unbound-200")
    if not dump:
        pytest.skip("unbound-200 research dump not available")
    winner = extract_winner(dump, "unbound-200", "male", 2024)
    assert winner == "Cameron Jones", f"Got: {winner!r}"


def test_extract_real_unbound_winner_female():
    """Extract female winner from actual Unbound research dump."""
    from extract_results import load_dump
    dump = load_dump("unbound-200")
    if not dump:
        pytest.skip("unbound-200 research dump not available")
    winner = extract_winner(dump, "unbound-200", "female", 2024)
    assert winner == "Karolina Sowa Migon", f"Got: {winner!r}"


def test_extract_real_bwr_winner_male():
    """Extract winner from actual BWR research dump."""
    from extract_results import load_dump
    dump = load_dump("bwr-california")
    if not dump:
        pytest.skip("bwr-california research dump not available")
    winner = extract_winner(dump, "bwr-california", "male", 2023)
    assert winner == "Payson McElveen", f"Got: {winner!r}"


def test_extract_real_grinduro_winner_male():
    """Extract winner from actual Grinduro research dump."""
    from extract_results import load_dump
    dump = load_dump("grinduro")
    if not dump:
        pytest.skip("grinduro research dump not available")
    winner = extract_winner(dump, "grinduro", "male", 2024)
    assert winner == "Gordon Wadsworth", f"Got: {winner!r}"


# ── Takeaway cleaning helpers ──


from extract_results import _clean_takeaway, _truncate_at_word_boundary


def test_clean_takeaway_strips_bare_urls():
    text = "Set a new record https://example.com/results#:~:text=fast in 2024"
    result = _clean_takeaway(text)
    assert "https://" not in result
    assert "#:~:text=" not in result
    assert "new record" in result


def test_clean_takeaway_strips_markdown_links():
    text = "Won the race [Athlinks] (https://www.athlinks.com/foo) easily"
    result = _clean_takeaway(text)
    assert "https://" not in result
    assert "Athlinks" in result
    assert "easily" in result


def test_clean_takeaway_strips_spaced_markdown_links():
    text = "Result confirmed [source] (https://example.com) by officials"
    result = _clean_takeaway(text)
    assert "https://" not in result
    assert "source" in result


def test_clean_takeaway_strips_citation_brackets():
    text = "First ever sub-9 hour finish [4] in ideal conditions [12]"
    result = _clean_takeaway(text)
    assert "[4]" not in result
    assert "[12]" not in result
    assert "sub-9 hour finish" in result


def test_clean_takeaway_strips_html_tags():
    text = "Big buckle for <u>sub-9 finishers</u> since 2019"
    result = _clean_takeaway(text)
    assert "<u>" not in result
    assert "</u>" not in result
    assert "sub-9 finishers" in result


def test_clean_takeaway_strips_url_fragments():
    text = "com/dispatches/#:~:text=8,the%20finish are deafening"
    result = _clean_takeaway(text)
    assert "#:~:text=" not in result


def test_clean_takeaway_strips_bold_asterisks():
    text = "**Cameron Jones** set a **new course record**"
    result = _clean_takeaway(text)
    assert "**" not in result
    assert "Cameron Jones" in result


def test_truncate_at_word_boundary_no_mid_word():
    text = "This is a very long sentence that needs to be truncated at a word boundary to avoid mid-word cuts that look terrible in rendered HTML output on the page"
    result = _truncate_at_word_boundary(text, 50)
    assert len(result) <= 50
    assert not result.endswith("boun")  # Should not cut mid-word
    assert result.endswith(" ") is False  # Should not end with space
    # Should end at a complete word
    assert result == text[:50].rsplit(' ', 1)[0]


def test_truncate_at_word_boundary_short_text():
    text = "Short text"
    result = _truncate_at_word_boundary(text, 150)
    assert result == "Short text"


# ── Hero image in recaps ──


def test_recap_has_hero_image(tmp_path):
    """Recap articles should have an OG hero image."""
    import generate_race_recap as recap_mod

    race_data = {
        "race": {
            "name": "Test Race",
            "vitals": {"location": "Test, CO"},
            "gravel_god_rating": {"tier": 1, "overall_score": 85},
            "results": {
                "years": {
                    "2024": {
                        "winner_male": "John Doe",
                        "conditions": "Cool and dry",
                    }
                },
                "latest_year": "2024"
            }
        }
    }

    race_dir = tmp_path / "race-data"
    race_dir.mkdir()
    (race_dir / "test-race.json").write_text(json.dumps(race_data))

    orig_dir = recap_mod.RACE_DATA_DIR
    recap_mod.RACE_DATA_DIR = race_dir
    try:
        html_content = recap_mod.generate_recap_html("test-race", 2024)
        assert html_content is not None
        assert "gg-blog-hero-img" in html_content
        assert "/og/test-race.jpg" in html_content
        assert 'alt="' in html_content
    finally:
        recap_mod.RACE_DATA_DIR = orig_dir
