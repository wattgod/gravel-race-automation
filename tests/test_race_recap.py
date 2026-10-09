"""Tests for race recap generator and results extractor."""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from brand_tokens import get_ga4_head_snippet
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
        head = html_content.split("<head>", 1)[1].split("</head>", 1)[0]
        assert get_ga4_head_snippet() in head
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
        assert "gtag('event', 'cta_click'" in html_content
        assert "source: 'editorial'" in html_content
    finally:
        recap_mod.RACE_DATA_DIR = orig_dir


# ── Editorial shell (Gravel God x Endure Glyph) ──


@pytest.fixture
def shell_recap(tmp_path, monkeypatch):
    """A full recap rendered on the editorial shell from a temp race JSON."""
    import generate_race_recap as recap_mod

    race_data = {
        "race": {
            "name": "Test Race",
            "vitals": {"location": "Test, CO", "distance_mi": 200, "elevation_ft": 15000,
                       "date_specific": "2024: June 1"},
            "gravel_god_rating": {"tier": 1, "overall_score": 85},
            "results": {"years": {"2024": {
                "winner_male": "John Doe", "winner_female": "Jane Smith",
                "winning_time_male": "8:30:00", "conditions": "Cool and dry",
                "field_size_actual": 2000, "finisher_count": 1700, "dnf_rate_pct": 15,
                "key_takeaways": ["New course record"],
            }}},
        }
    }
    race_dir = tmp_path / "race-data"
    race_dir.mkdir()
    (race_dir / "test-race.json").write_text(json.dumps(race_data))
    monkeypatch.setattr(recap_mod, "RACE_DATA_DIR", race_dir)
    return recap_mod.generate_recap_html("test-race", 2024)


def _head(page):
    return page.split("<head>", 1)[1].split("</head>", 1)[0]


def test_shell_keeps_head_contract(shell_recap):
    head = _head(shell_recap)
    url = "https://gravelgodcycling.com/blog/test-race-recap/"
    assert '<meta name="robots" content="noindex, follow">' in head
    assert "<title>Test Race 2024 Race Recap — Gravel God</title>" in head
    assert f'<link rel="canonical" href="{url}">' in head
    assert f'<meta property="og:url" content="{url}">' in head
    assert '<meta property="og:image" content="https://gravelgodcycling.com/og/test-race.jpg">' in head
    assert ('content="Test Race 2024 recap: John Doe Takes the Win. '
            'Tier 1 The Icons rated 85/100."') in head
    assert 'og:description" content="John Doe Takes the Win. Tier 1 The Icons gravel race."' in head
    # JSON-LD policy unchanged: one compact Article block with the SportsEvent.
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', head, re.S)
    assert len(blocks) == 1
    ld = json.loads(blocks[0])
    assert ld["@type"] == "Article"
    assert ld["datePublished"] == "2024-06-01"
    assert ld["about"]["url"] == "https://gravelgodcycling.com/race/test-race/"


def test_shell_hero_is_text_only_without_read_time(shell_recap):
    # The share card repeats title/tier/score, so the hero carries no image.
    hero = shell_recap.split('<div class="frame hero', 1)[1].split("</div>\n  </div>", 1)[0]
    assert shell_recap.count('<div class="frame hero no-img gg-blog-hero">') == 1
    assert "<img" not in hero and 'class="hero-img' not in shell_recap
    assert "Race Recap · Tier 1 The Icons · Test, CO" in shell_recap
    assert "<h1>Test Race 2024 Recap</h1>" in shell_recap
    assert '<p class="dek">John Doe Takes the Win</p>' in shell_recap
    assert "Gravel God &middot; June 1, 2024</p>" in shell_recap
    assert "min read" not in shell_recap


def test_shell_share_card_is_body_image_after_winners(shell_recap):
    img = ('<img class="gg-blog-hero-img" src="https://gravelgodcycling.com/og/test-race.jpg" '
           'alt="Test Race 2024 race recap" width="1200" height="630" loading="lazy">')
    assert shell_recap.count(img) == 1
    body = shell_recap.split("<h2", 1)[1]
    winners_end = body.index("</section>")
    assert winners_end < body.index('<div class="gg-article-img-inline">') < body.index(">Conditions</h2>")
    assert '<div class="gg-article-img-inline">\n      ' + img in shell_recap


def test_shell_sections_feed_contents(shell_recap):
    heads = re.findall(r"<h2 id=\"([\w-]+)\" data-toc>([^<]+)</h2>", shell_recap)
    assert [h for _, h in heads] == ["Winners", "Conditions", "Key Stats", "Key Takeaways"]
    assert shell_recap.count('<section class="gg-blog-section">') == 4
    assert 'class="rail"' in shell_recap and 'id="tocm"' in shell_recap
    for label in ("Men's Winner", "Women's Winner", "Miles", "Ft Elevation",
                  "Starters", "Finishers", "DNF Rate"):
        assert label in shell_recap
    assert "John Doe (8:30:00)" in shell_recap
    assert "15,000" in shell_recap and "2,000" in shell_recap and "15%" in shell_recap


def test_shell_keeps_race_ctas_and_no_ladder(shell_recap):
    cta = shell_recap.split('<div class="gg-blog-cta">', 1)[1].split("</div>", 1)[0]
    assert 'href="https://gravelgodcycling.com/race/test-race/"' in cta
    assert 'href="https://gravelgodcycling.com/race/test-race/prep-kit/"' in cta
    assert "Full Race Profile" in cta and "Free Prep Kit" in cta
    # No generic plans/coaching block existed, so no shell ladder is added.
    assert 'data-cta="custom_plan"' not in shell_recap


def test_shell_tracking_is_plan_intent_only(shell_recap):
    assert shell_recap.count("source: 'editorial'") == 1
    # noindex blog pages stay out of the article funnel
    assert "article_scroll_depth" not in shell_recap
    assert "article_deep_read" not in shell_recap
    assert shell_recap.count("gg-consent-banner") >= 1


def test_single_section_recap_has_no_contents(monkeypatch, tmp_path):
    """One h2 is below the shell's MIN_CONTENTS_HEADINGS, so no rail or bar."""
    import generate_race_recap as recap_mod

    race_data = {"race": {
        "name": "Solo Race",
        "vitals": {"location": "Test, CO", "date_specific": "2024: June 1"},
        "gravel_god_rating": {"tier": 2, "overall_score": 70},
        "results": {"years": {"2024": {"winner_male": "John Doe"}}},
    }}
    race_dir = tmp_path / "race-data"
    race_dir.mkdir()
    (race_dir / "solo-race.json").write_text(json.dumps(race_data))
    monkeypatch.setattr(recap_mod, "RACE_DATA_DIR", race_dir)
    page = recap_mod.generate_recap_html("solo-race", 2024)
    assert page.count("data-toc>") == 1
    assert 'class="rail"' not in page and 'id="tocm"' not in page
    # The share card still follows the one section.
    assert page.index("</section>") < page.index("gg-blog-hero-img")


# ── Newest results year wins (one URL per race) ──


def _write_race(race_dir, slug, race):
    race_dir.mkdir(exist_ok=True)
    (race_dir / f"{slug}.json").write_text(json.dumps({"race": race}))


@pytest.mark.parametrize("order", [("2024", "2025"), ("2025", "2024")])
def test_all_recaps_newest_year_wins(order, tmp_path, monkeypatch):
    """Two results years share {slug}-recap.html; the newest must win in any key order."""
    import generate_race_recap as recap_mod

    years = {"2024": {"winner_male": "Old Winner"}, "2025": {"winner_male": "New Winner"}}
    race = {"name": "Two Year Race", "vitals": {}, "gravel_god_rating": {"tier": 2},
            "results": {"years": {y: years[y] for y in order}}}
    race_dir = tmp_path / "race-data"
    _write_race(race_dir, "two-year-race", race)
    monkeypatch.setattr(recap_mod, "RACE_DATA_DIR", race_dir)

    cands = recap_mod.find_recap_candidates()
    assert [(c["slug"], c["year"]) for c in cands] == [("two-year-race", 2025)]
    # An explicit --year still lists that year.
    assert [c["year"] for c in recap_mod.find_recap_candidates(2024)] == [2024]

    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["generate_race_recap.py", "--all", "--output-dir", str(out)])
    recap_mod.main()
    page = (out / "two-year-race-recap.html").read_text()
    assert "Two Year Race 2025 Recap" in page and "New Winner" in page
    assert "Old Winner" not in page
    assert [p.name for p in out.iterdir()] == ["two-year-race-recap.html"]


def test_newest_results_year_ignores_years_without_winner():
    from generate_race_recap import newest_results_year

    race = {"results": {"years": {"2025": {"conditions": "Wet."},
                                  "2024": {"winner_female": "A Rider"}}}}
    assert newest_results_year(race) == 2024
    assert newest_results_year({"results": {"years": {}}}) is None


# ── Stable publish date (never today) ──


@pytest.mark.parametrize("year_data,vitals,year,expected", [
    ({"date_completed": "2024-06-02"}, {"date_specific": "2026: June 6"}, 2024, "2024-06-02"),
    ({}, {"date_specific": "2024: June 1"}, 2024, "2024-06-01"),
    ({}, {"date_specific": "2026: Aug 19-23 (festival week)"}, 2026, "2026-08-23"),
    ({}, {"date_specific": "2026: September 26–27"}, 2026, "2026-09-27"),
    # The next edition's date is not the results year's date.
    ({}, {"date_specific": "2026: September 12"}, 2024, "2024-12-31"),
    ({}, {"date_specific": "Status: CANCELLED for 2026"}, 2024, "2024-12-31"),
    ({"date_completed": "2023-06-02"}, {}, 2024, "2024-12-31"),
    ({"date_completed": "June 2"}, {}, 2024, "2024-12-31"),
    ({}, {}, 2025, "2025-12-31"),
])
def test_recap_publish_date(year_data, vitals, year, expected):
    from generate_race_recap import recap_publish_date

    assert recap_publish_date(year_data, vitals, year).isoformat() == expected


def test_recap_date_never_reads_today(tmp_path, monkeypatch):
    """Rebuilding on another day gives the same page (the old date was capped at today)."""
    import datetime as dt
    import generate_race_recap as recap_mod

    race = {"name": "Future Date Race", "vitals": {"date_specific": "2027: May 1"},
            "gravel_god_rating": {"tier": 3},
            "results": {"years": {"2025": {"winner_male": "A Rider"}}}}
    race_dir = tmp_path / "race-data"
    _write_race(race_dir, "future-date-race", race)
    monkeypatch.setattr(recap_mod, "RACE_DATA_DIR", race_dir)

    first = recap_mod.generate_recap_html("future-date-race", 2025)

    class NoToday(dt.date):
        @classmethod
        def today(cls):
            raise AssertionError("recap dates must not depend on today")

    monkeypatch.setattr(recap_mod, "date", NoToday)
    second = recap_mod.generate_recap_html("future-date-race", 2025)
    assert first == second
    assert '"datePublished":"2025-12-31"' in first
    # The Dec 31 stand-in stays in JSON-LD only; the byline shows the year.
    byline = first.split('<p class="by">', 1)[1].split("</p>", 1)[0]
    assert "2025 results" in byline
    assert "December" not in byline and "Dec" not in byline and "31" not in byline


def test_recap_byline_shows_real_date_when_known(tmp_path, monkeypatch):
    import generate_race_recap as recap_mod

    race = {"name": "Known Date Race", "vitals": {"date_specific": "2025: June 7"},
            "gravel_god_rating": {"tier": 3},
            "results": {"years": {"2025": {"winner_male": "A Rider"}}}}
    race_dir = tmp_path / "race-data"
    _write_race(race_dir, "known-date-race", race)
    monkeypatch.setattr(recap_mod, "RACE_DATA_DIR", race_dir)
    html = recap_mod.generate_recap_html("known-date-race", 2025)
    byline = html.split('<p class="by">', 1)[1].split("</p>", 1)[0]
    assert "results" not in byline and "June" in byline
    assert '"datePublished":"2025-06-07"' in html


def test_recap_date_parts_flags_fallback():
    from generate_race_recap import recap_date_parts

    assert recap_date_parts({"date_completed": "2024-06-02"}, {}, 2024)[1] is True
    assert recap_date_parts({}, {"date_specific": "2024: June 1"}, 2024)[1] is True
    assert recap_date_parts({}, {"date_specific": "2026: June 1"}, 2024)[1] is False


# ── "In short" ──


FULL_YEAR = {
    "winner_male": "John Doe", "winner_female": "Jane Smith",
    "winning_time_male": "8:30:00", "winning_time_female": "9:45:00",
    "conditions": "Cool and dry at the start. Wind built after noon.",
    "field_size_actual": 2000, "finisher_count": 1700, "dnf_rate_pct": 15,
    "key_takeaways": ["The new course added 12 miles of gravel. Times were slower."],
}
ALL_SECTIONS = {"winners": (0, "Winners"), "conditions": (1, "Conditions"),
                "key-stats": (2, "Key Stats"), "key-takeaways": (3, "Key Takeaways")}
BANNED = ("I ", "we ", "We ", "!", " — ")


def _texts(claims):
    import html as html_mod
    return [html_mod.unescape(c.text_html) for c in claims]


def test_in_short_claims_from_fixture():
    from generate_race_recap import build_in_short

    claims = build_in_short(FULL_YEAR, ALL_SECTIONS)
    assert _texts(claims) == [
        "John Doe won the men's race in 8:30:00 and Jane Smith won the women's race in 9:45:00.",
        "Cool and dry at the start.",
        "2,000 riders started, 1,700 finished and the DNF rate was 15%.",
        "The new course added 12 miles of gravel.",
    ]
    assert [c.href for c in claims] == ["#winners", "#conditions", "#key-stats", "#key-takeaways"]
    assert [c.section for c in claims] == [0, 1, 2, 3]
    assert claims[2].link_label == "Key Stats · §03"
    for text in _texts(claims):
        assert len(text.split()) <= 25
        assert not any(b in text for b in BANNED)
    # Deterministic: same data, same claims.
    assert build_in_short(FULL_YEAR, ALL_SECTIONS) == claims


@pytest.mark.parametrize("year_data,expected", [
    ({"winner_male": "A"}, "A won the men's race."),
    ({"winner_female": "B", "winning_time_female": "5:00:00"}, "B won the women's race in 5:00:00."),
    ({"winner_male": "Same Name", "winner_female": "Same Name"}, None),
])
def test_in_short_winners_template(year_data, expected):
    from generate_race_recap import winners_claim

    assert winners_claim(year_data) == expected


@pytest.mark.parametrize("year_data,expected", [
    ({"dnf_rate_pct": 30}, "The DNF rate was 30%."),
    ({"finisher_count": 900}, "900 riders finished."),
    ({"field_size_actual": 1500}, "1,500 riders started."),
    ({"field_size_actual": 800, "dnf_rate_pct": 30}, "800 riders started and the DNF rate was 30%."),
    ({"winning_time_male": "8:00:00"}, None),
    ({"field_size_actual": "lots"}, None),
])
def test_in_short_stat_template(year_data, expected):
    from generate_race_recap import stat_claim

    assert stat_claim(year_data) == expected


@pytest.mark.parametrize("text,expected", [
    ("The start in St. George was cold. Then it warmed.", "The start in St. George was cold."),
    ("Riders from the U.S. Open field rode well. Others did not.",
     "Riders from the U.S. Open field rode well."),
    ("J. Smith attacked on Mt. Hood early. The field split.", "J. Smith attacked on Mt. Hood early."),
    ("Wind came at 2 p.m. and stayed. Then rain.", "Wind came at 2 p.m. and stayed."),
    ("Mud near St. George", None),  # still cut off: no sentence end at all
])
def test_first_sentence_skips_abbreviations(text, expected):
    from generate_race_recap import first_sentence

    assert first_sentence(text) == expected


@pytest.mark.parametrize("text", [
    "Finishing under 12 hours is more common (one year saw 1538 finishers[trainright",  # no end
    "If you can arrive early, you will go into the red more quickly at 7,000+ f",       # mid-word
    "a rider from Boston noted they came on Thursday.",                                 # starts mid-sentence
    "- Historical weather incidents: Mud logjam in 2024.",                              # bullet
    "",
    None,
])
def test_in_short_truncated_source_has_no_sentence(text):
    from generate_race_recap import first_sentence

    assert first_sentence(text) is None


@pytest.mark.parametrize("conditions", [
    "We rode through mud for hours.",
    "If you can arrive early, do.",
    "Wind was brutal!",
    "Wind built after noon — riders suffered.",
    "Riders waited... then the rain came.",
    "Riders waited\u2026 then the rain came.",
    "It was not the heat, but the wind that decided it.",
    "One two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty twenty-one "
    "twenty-two twenty-three twenty-four twenty-five twenty-six.",
])
def test_in_short_skips_claims_breaking_voice_rules(conditions):
    from generate_race_recap import build_in_short

    claims = build_in_short({"winner_male": "A", "conditions": conditions}, ALL_SECTIONS)
    assert [c.href for c in claims] == ["#winners"]


def test_in_short_skips_claims_whose_section_is_missing():
    from generate_race_recap import build_in_short

    claims = build_in_short(FULL_YEAR, {"winners": (0, "Winners"), "key-stats": (1, "Key Stats")})
    assert [c.href for c in claims] == ["#winners", "#key-stats"]
    assert [c.section for c in claims] == [0, 1]


def test_in_short_escapes_data():
    from generate_race_recap import build_in_short

    claims = build_in_short({"winner_male": "<b>A&B</b>", "dnf_rate_pct": 5}, ALL_SECTIONS)
    assert "<b>" not in claims[0].text_html and "&lt;b&gt;A&amp;B&lt;/b&gt;" in claims[0].text_html


def _render(tmp_path, monkeypatch, year_data, slug="in-short-race"):
    import generate_race_recap as recap_mod

    race = {"name": "In Short Race", "vitals": {"distance_mi": 100, "date_specific": "2024: May 4"},
            "gravel_god_rating": {"tier": 2, "overall_score": 70},
            "results": {"years": {"2024": year_data}}}
    race_dir = tmp_path / "race-data"
    _write_race(race_dir, slug, race)
    monkeypatch.setattr(recap_mod, "RACE_DATA_DIR", race_dir)
    return recap_mod.generate_recap_html(slug, 2024)


def test_in_short_renders_and_every_link_target_exists(tmp_path, monkeypatch):
    page = _render(tmp_path, monkeypatch, FULL_YEAR)
    aside = page.split('<aside class="inshort"', 1)[1].split("</aside>", 1)[0]
    hrefs = re.findall(r'class="ev" href="#([\w-]+)"', aside)
    assert hrefs == ["winners", "conditions", "key-stats", "key-takeaways"]
    for target in hrefs:
        assert page.count(f'id="{target}"') == 1
    # data-sec matches each target's h2 position on the page.
    h2_ids = re.findall(r'<h2 id="([\w-]+)" data-toc>', page)
    secs = [int(s) for s in re.findall(r'<li data-sec="(\d+)">', aside)]
    assert [h2_ids[s] for s in secs] == hrefs
    # In short sits before the first section.
    assert page.index('class="inshort"') < page.index('<h2 id="winners"')


def test_in_short_absent_with_fewer_than_two_claims(tmp_path, monkeypatch):
    # Winner only; truncated conditions and takeaway are skipped.
    page = _render(tmp_path, monkeypatch, {
        "winner_male": "John Doe",
        "conditions": "a rider noted the headwinds",
        "key_takeaways": ["If you can arrive early, be prepared at 7,000+ f"],
    })
    assert "John Doe" in page
    assert 'class="inshort"' not in page and 'data-slot="summary"' not in page


def test_shell_recap_in_short_from_fixture(shell_recap):
    """Fixture strings 'Cool and dry' / 'New course record' have no full stop: skipped."""
    aside = shell_recap.split('<aside class="inshort"', 1)[1].split("</aside>", 1)[0]
    assert re.findall(r'href="#([\w-]+)"', aside) == ["winners", "key-stats"]
    assert "2,000 riders started, 1,700 finished and the DNF rate was 15%." in aside
