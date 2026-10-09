"""Tests for season roundup generator."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_season_roundup import (
    MONTH_NAMES,
    MONTH_NUMBERS,
    REGIONS,
    SEASONS,
    TIER_NAMES,
    build_race_card_html,
    build_roundup_stats,
    classify_blog_slug,
    filter_by_month,
    filter_by_region,
    filter_by_tier,
    generate_roundup_html,
    load_race_index,
)


@pytest.fixture
def race_index():
    """Load the real race-index.json for integration tests."""
    return load_race_index()


@pytest.fixture
def sample_races():
    """Minimal set of fake races for unit tests."""
    return [
        {"slug": "race-a", "name": "Race A", "month": "June", "region": "West",
         "tier": 1, "overall_score": 90, "location": "CO", "distance_mi": 200,
         "tagline": "The best race."},
        {"slug": "race-b", "name": "Race B", "month": "June", "region": "South",
         "tier": 2, "overall_score": 70, "location": "TX", "distance_mi": 100},
        {"slug": "race-c", "name": "Race C", "month": "March", "region": "South",
         "tier": 3, "overall_score": 55, "location": "GA", "distance_mi": 60},
        {"slug": "race-d", "name": "Race D", "month": "September", "region": "Europe",
         "tier": 1, "overall_score": 85, "location": "UK", "distance_mi": 150},
        {"slug": "race-e", "name": "Race E", "month": "March", "region": "West",
         "tier": 4, "overall_score": 40, "location": "CA", "distance_mi": 50},
    ]


# ── classify_blog_slug ──


def test_classify_roundup_slug():
    assert classify_blog_slug("roundup-march-2026") == "roundup"


def test_classify_recap_slug():
    assert classify_blog_slug("unbound-200-recap") == "recap"


def test_classify_preview_slug():
    assert classify_blog_slug("unbound-200") == "preview"


def test_classify_roundup_tier_slug():
    assert classify_blog_slug("roundup-tier-1-2026") == "roundup"


# ── filter_by_month ──


def test_filter_by_month_matches(sample_races):
    result = filter_by_month(sample_races, 2026, 6)
    assert len(result) == 2
    slugs = {r["slug"] for r in result}
    assert slugs == {"race-a", "race-b"}


def test_filter_by_month_no_matches(sample_races):
    result = filter_by_month(sample_races, 2026, 12)
    assert result == []


def test_filter_by_month_invalid():
    assert filter_by_month([], 2026, 0) == []
    assert filter_by_month([], 2026, 13) == []


def test_filter_by_month_case_insensitive(sample_races):
    """Month matching should be case-insensitive."""
    races = [{"slug": "x", "month": "JUNE"}]
    result = filter_by_month(races, 2026, 6)
    assert len(result) == 1


# ── filter_by_region ──


def test_filter_by_region_southeast(sample_races):
    result = filter_by_region(sample_races, "southeast")
    assert len(result) == 2
    slugs = {r["slug"] for r in result}
    assert slugs == {"race-b", "race-c"}


def test_filter_by_region_europe(sample_races):
    result = filter_by_region(sample_races, "europe")
    assert len(result) == 1
    assert result[0]["slug"] == "race-d"


def test_filter_by_region_invalid(sample_races):
    result = filter_by_region(sample_races, "nonexistent")
    assert result == []


def test_filter_by_region_west(sample_races):
    result = filter_by_region(sample_races, "west")
    assert len(result) == 2


# ── filter_by_tier ──


def test_filter_by_tier_1(sample_races):
    result = filter_by_tier(sample_races, 1)
    assert len(result) == 2
    slugs = {r["slug"] for r in result}
    assert slugs == {"race-a", "race-d"}


def test_filter_by_tier_4(sample_races):
    result = filter_by_tier(sample_races, 4)
    assert len(result) == 1
    assert result[0]["slug"] == "race-e"


def test_filter_by_tier_empty(sample_races):
    result = filter_by_tier(sample_races, 99)
    assert result == []


# ── build_roundup_stats ──


def test_stats_count(sample_races):
    stats = build_roundup_stats(sample_races)
    assert stats["count"] == 5


def test_stats_avg_score(sample_races):
    stats = build_roundup_stats(sample_races)
    expected = round((90 + 70 + 55 + 85 + 40) / 5)
    assert stats["avg_score"] == expected


def test_stats_tier_breakdown(sample_races):
    stats = build_roundup_stats(sample_races)
    assert stats["tier_breakdown"][1] == 2
    assert stats["tier_breakdown"][2] == 1
    assert stats["tier_breakdown"][3] == 1
    assert stats["tier_breakdown"][4] == 1


def test_stats_empty():
    stats = build_roundup_stats([])
    assert stats["count"] == 0
    assert stats["avg_score"] == 0
    assert stats["tier_breakdown"] == {}


# ── build_race_card_html ──


def test_card_contains_name(sample_races):
    html = build_race_card_html(sample_races[0])
    assert "Race A" in html


def test_card_contains_tier(sample_races):
    html = build_race_card_html(sample_races[0])
    assert "T1" in html
    assert "The Icons" in html


def test_card_contains_score(sample_races):
    html = build_race_card_html(sample_races[0])
    assert "90/100" in html


def test_card_contains_profile_link(sample_races):
    html = build_race_card_html(sample_races[0])
    assert "/race/race-a/" in html


def test_card_contains_tagline(sample_races):
    html = build_race_card_html(sample_races[0])
    assert "The best race." in html


def test_card_without_tagline(sample_races):
    html = build_race_card_html(sample_races[1])
    assert "gg-roundup-tagline" not in html


# ── generate_roundup_html ──


def test_roundup_has_doctype(sample_races):
    html = generate_roundup_html(
        "Test Title", "Test Subtitle", "Intro text.",
        sample_races, "roundup-test", "Test Category"
    )
    assert "<!DOCTYPE html>" in html


def test_roundup_has_title(sample_races):
    html = generate_roundup_html(
        "March 2026 Calendar", "12 Races", "Intro.",
        sample_races, "roundup-march-2026", "Monthly Calendar"
    )
    assert "March 2026 Calendar" in html


def test_roundup_has_jsonld(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Cat"
    )
    assert "application/ld+json" in html
    assert '"@type":"Article"' in html


def test_roundup_has_og_tags(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Cat"
    )
    assert "og:title" in html
    assert "og:description" in html
    assert "og:url" in html


def test_roundup_has_canonical(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Cat"
    )
    assert 'rel="canonical"' in html
    assert "/blog/roundup-test/" in html


def test_roundup_has_stats_bar(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Cat"
    )
    assert "gg-roundup-stats-bar" in html
    assert "5 Races" in html


def test_roundup_has_race_cards(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Cat"
    )
    assert "gg-roundup-card" in html
    # All 5 races should have cards
    for r in sample_races:
        assert r["name"] in html


def test_roundup_has_cta(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Cat"
    )
    # Phase 2 of the Matti-approved road migration changes the catalog from
    # 733 to 370 entries. The CTA intentionally stays count-free so future
    # approved catalog changes cannot leave stale promotional copy behind.
    assert "Explore All Races" in html
    assert "/gravel-races/" in html


def test_roundup_has_category_tag(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Monthly Calendar"
    )
    assert "Monthly Calendar" in html


def test_roundup_tracks_plan_intent_with_canonical_event(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Monthly Calendar"
    )
    assert "gtag('event', 'cta_click'" in html
    assert "source: 'editorial'" in html


def test_roundup_escapes_html():
    """Verify HTML special chars are escaped."""
    races = [{"slug": "x", "name": "Race <script>", "tier": 1, "overall_score": 50,
              "location": "CO", "month": "June"}]
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", races, "roundup-test", "Cat"
    )
    assert "&lt;script&gt;" in html
    assert "Race <script>" not in html


# ── Integration: load_race_index ──


def test_load_race_index_returns_list(race_index):
    assert isinstance(race_index, list)
    assert len(race_index) > 300


def test_race_index_has_required_fields(race_index):
    r = race_index[0]
    assert "slug" in r
    assert "name" in r
    assert "tier" in r
    assert "month" in r
    assert "region" in r


# ── Integration: filter on real data ──


def test_filter_by_month_june_real(race_index):
    result = filter_by_month(race_index, 2026, 6)
    assert len(result) >= 3, "Expected at least 3 races in June"


def test_filter_by_tier_1_real(race_index):
    result = filter_by_tier(race_index, 1)
    assert len(result) >= 3, "Expected at least 3 T1 races"


def test_filter_by_region_west_real(race_index):
    result = filter_by_region(race_index, "west")
    assert len(result) >= 3, "Expected at least 3 West races"


# ── Slug format validation ──


def test_monthly_slug_format():
    """Monthly slugs should be roundup-{month}-{year}."""
    slug = f"roundup-{MONTH_NAMES[3].lower()}-2026"
    assert slug == "roundup-march-2026"
    assert classify_blog_slug(slug) == "roundup"


def test_regional_slug_format():
    slug = "roundup-southeast-spring-2026"
    assert classify_blog_slug(slug) == "roundup"


def test_tier_slug_format():
    slug = "roundup-tier-1-2026"
    assert classify_blog_slug(slug) == "roundup"


# ── Editorial shell (re-skin keeps every element) ──


def _render(races, slug="roundup-test"):
    return generate_roundup_html(
        "August 2026 Gravel Calendar", "5 Races to Watch", "Intro text.",
        races, slug, "Monthly Calendar",
    )


def test_roundup_renders_on_editorial_shell(sample_races):
    html = _render(sample_races)
    assert 'id="article"' in html
    assert 'class="gg-site-header"' in html
    assert 'class="foot"' in html


def test_roundup_robots_follow_indexable_allowlist(sample_races):
    from generate_season_roundup import INDEXABLE_ROUNDUPS
    indexable = sorted(INDEXABLE_ROUNDUPS)[0]
    assert '<meta name="robots" content="index, follow">' in _render(sample_races, indexable)
    assert '<meta name="robots" content="noindex, follow">' in _render(sample_races, "roundup-tier-1-2026")


def test_roundup_never_fires_article_events(sample_races):
    """Indexable roundups must not feed the article funnel."""
    from generate_season_roundup import INDEXABLE_ROUNDUPS
    html = _render(sample_races, sorted(INDEXABLE_ROUNDUPS)[0])
    assert "article_scroll_depth" not in html
    assert "article_deep_read" not in html
    assert "gtag('event', 'article_cta_click'" not in html


def test_roundup_has_no_read_time_and_no_ladder(sample_races):
    html = _render(sample_races)
    assert "min read" not in html
    assert 'class="ladder"' not in html


def test_roundup_title_and_meta_unchanged(sample_races):
    html = _render(sample_races, "roundup-test")
    assert "<title>August 2026 Gravel Calendar: 5 Races to Watch — Gravel God</title>" in html
    assert ('content="August 2026 Gravel Calendar: 5 Races to Watch. '
            '5 races rated and ranked by Gravel God."') in html
    assert 'og:description" content="5 gravel races rated and ranked. Average score: 68/100."' in html
    assert '"datePublished":"' in html  # compact JSON-LD, read by generate_blog_index


def test_roundup_hero_keeps_category_count_subtitle_date(sample_races):
    from datetime import date
    html = generate_roundup_html("T", "Sub Line", "Intro.", sample_races, "roundup-x",
                                 "Regional Roundup", publish_date=date(2026, 9, 1))
    assert "Regional Roundup · 5 Races" in html
    assert "Sub Line" in html
    assert "September 1, 2026" in html


def test_roundup_contents_lists_tiers(sample_races):
    html = _render(sample_races)
    assert 'class="toc"' in html
    for label in ("T1 The Icons", "T2 Elite", "T3 Solid", "T4 Grassroots"):
        assert f">{label}</a></li>" in html


def test_single_tier_roundup_has_no_contents(sample_races):
    html = _render(filter_by_tier(sample_races, 1))
    assert 'class="toc"' not in html
    assert "<h2" not in html


def test_roundup_cards_keep_every_field(sample_races):
    html = _render(sample_races)
    assert html.count('class="gg-roundup-card"') == len(sample_races)
    assert "/race/race-a/prep-kit/" in html
    assert "Free Prep Kit" in html and "Race Profile" in html
    assert 'class="gg-roundup-vitals">200 mi &middot; June' in html
    assert "background:#59473c" in html  # tier colour still encodes the tier


def test_roundup_scripts_not_duplicated(sample_races):
    html = _render(sample_races)
    assert html.count("source: 'editorial'") == 1
    assert html.count('id="gg-consent-banner"') <= 1
    assert html.count("gtag('config'") <= 1


def test_roundup_heading_text_has_no_tier_n_for_blog_index(sample_races):
    """generate_blog_index reads `Tier N` as the entry tier; monthly roundups must stay tier 0."""
    import re
    assert not re.search(r"Tier\s+\d", _render(sample_races))


# ── "In short" (IN_SHORT_SPEC.md, Roundup section) ──

import re as _re

from generate_season_roundup import (  # noqa: E402
    BANNED_CLAIM_RE,
    MAX_CLAIM_WORDS,
    RACES_ID,
    build_in_short_claims,
    generate_all,
)


def _in_short_block(page):
    m = _re.search(r'<aside class="inshort".*?</aside>', page, _re.S)
    return m.group(0) if m else None


def _claims_in(page):
    block = _in_short_block(page)
    if not block:
        return []
    return _re.findall(r'<li data-sec="\d+"><p>(.*?)</p><a class="ev" href="#([^"]+)"', block)


def _plain(text_html):
    import html as _html
    return _html.unescape(_re.sub(r"<[^>]+>", "", text_html))


def test_in_short_claims_from_fixture(sample_races):
    claims = build_in_short_claims(sample_races, "June 2026")
    assert [c.text_html for c in claims] == [
        "5 races rated, June 2026.",
        "Race A rates highest at 90/100 (T1 The Icons).",
        "By tier: 2 T1, 1 T2, 1 T3 and 1 T4.",
    ]
    assert [c.href for c in claims] == ["#t1-the-icons"] * 3
    assert [c.section for c in claims] == [0, 0, 0]
    assert claims[0].link_label == "See T1 The Icons · §01"


def test_in_short_top_race_links_to_its_own_tier(sample_races):
    races = [dict(r) for r in sample_races]
    races[1]["overall_score"] = 95  # Race B, T2
    top = build_in_short_claims(races, "June 2026")[1]
    assert top.text_html == "Race B rates highest at 95/100 (T2 Elite)."
    assert (top.href, top.section, top.link_label) == ("#t2-elite", 1, "See T2 Elite · §02")


def test_in_short_ties_are_not_called_a_single_winner(sample_races):
    races = [dict(r) for r in sample_races]
    races[3]["overall_score"] = 90  # Race D ties Race A
    assert build_in_short_claims(races, "x")[1].text_html == (
        "Race A and Race D share the highest rating, 90/100.")
    races[1]["overall_score"] = 90
    assert build_in_short_claims(races, "x")[1].text_html == (
        "3 races share the highest rating, 90/100.")


def test_in_short_single_tier_links_to_race_grid(sample_races):
    t1 = filter_by_tier(sample_races, 1)
    claims = build_in_short_claims(t1, "T1 The Icons")
    assert [c.text_html for c in claims] == [
        "2 races rated, T1 The Icons.",
        "Race A rates highest at 90/100 (T1 The Icons).",
    ]  # no tier split on a one-tier page
    assert {c.href for c in claims} == {f"#{RACES_ID}"}
    page = _render(t1)
    assert f'id="{RACES_ID}"' in page and "<h2" not in page


def test_in_short_skips_missing_data(sample_races):
    no_scores = [dict(r, overall_score=0) for r in sample_races]
    claims = build_in_short_claims(no_scores, "June 2026")
    assert [c.text_html for c in claims] == [
        "5 races rated, June 2026.", "By tier: 2 T1, 1 T2, 1 T3 and 1 T4."]
    assert [c.text_html for c in build_in_short_claims(sample_races, "")][0].startswith("Race A")
    assert build_in_short_claims([], "June 2026") is None


def test_in_short_fewer_than_two_claims_renders_nothing(sample_races):
    t1 = [dict(r, overall_score=0) for r in filter_by_tier(sample_races, 1)]
    assert build_in_short_claims(t1, "T1 The Icons") is None  # scope only
    page = generate_roundup_html("T", "S", "Intro.", t1, "roundup-x", "Cat", scope="T1 The Icons")
    assert 'class="inshort"' not in page


def test_in_short_quotes_names_but_skips_overlong(sample_races):
    # A race name is data: its own dash, "!" or "We" doesn't drop the claim.
    for name in ("Race — The Sequel", "Go Race!", "We Ride Gravel"):
        races = [dict(r) for r in sample_races]
        races[0]["name"] = name
        texts = [_plain(c.text_html) for c in build_in_short_claims(races, "June 2026")]
        assert any(t.startswith(f"{name} rates highest") for t in texts), name
    races = [dict(r) for r in sample_races]
    races[0]["name"] = " ".join(["Long"] * 20)
    texts = [c.text_html for c in build_in_short_claims(races, "June 2026")]
    assert not any("rates highest" in t for t in texts)
    races = [dict(r) for r in sample_races]
    races[0]["name"] = "UCI Gravel Worlds"  # "I " inside a word is not first person
    assert "UCI Gravel Worlds rates highest" in build_in_short_claims(races, "x")[1].text_html


def test_in_short_never_uses_prose_fields(sample_races):
    """Truncation guard: no tagline (the only prose field) ever reaches a claim."""
    races = [dict(r, tagline="A sentence cut off mid-wo") for r in sample_races]
    assert "mid-wo" not in (_in_short_block(_render(races)) or "")


def test_in_short_escapes_race_names(sample_races):
    races = [dict(r) for r in sample_races]
    races[0]["name"] = "<script>x</script> & Co"
    block = _in_short_block(_render(races))
    assert "&lt;script&gt;x&lt;/script&gt; &amp; Co rates highest" in block
    assert "<script>" not in block


def test_in_short_is_deterministic(sample_races):
    assert _render(sample_races) == _render(list(reversed(sample_races)))


def test_in_short_keeps_roundups_out_of_article_funnel_and_blog_tier(sample_races):
    from generate_season_roundup import INDEXABLE_ROUNDUPS
    page = generate_roundup_html("A", "B", "Intro.", sample_races, sorted(INDEXABLE_ROUNDUPS)[0],
                                 "Monthly Calendar", scope="June 2026")
    assert 'class="inshort"' in page
    assert "article_scroll_depth" not in page and "article_deep_read" not in page
    assert not _re.search(r"Tier\s+\d", page)  # generate_blog_index tier stays 0


def test_every_generated_roundup_in_short_is_valid(race_index, tmp_path):
    """All roundups from the real index: targets exist, ≤25 words, no banned patterns."""
    slugs = generate_all(race_index, 2026, tmp_path)
    assert slugs
    race_names = sorted({r["name"] for r in race_index if r.get("name")}, key=len, reverse=True)
    with_in_short = 0
    for slug in slugs:
        page = (tmp_path / f"{slug}.html").read_text()
        claims = _claims_in(page)
        if not claims:
            continue
        with_in_short += 1
        assert 2 <= len(claims) <= 4, slug
        ids = set(_re.findall(r'\bid="([^"]+)"', page))
        for text_html, target in claims:
            text = _plain(text_html)
            assert target in ids, (slug, target)
            assert len(text.split()) <= MAX_CLAIM_WORDS, (slug, text)
            # Banned patterns apply to the template; race names are quoted data.
            template = text
            for name in race_names:
                if name in template:
                    template = template.replace(name, "Race")
            assert not BANNED_CLAIM_RE.search(template), (slug, text)
            for banned in ("!", " — "):
                assert banned not in template, (slug, text)
            assert not _re.search(r"(?<![A-Za-z])(I|we) ", template), (slug, text)
    assert with_in_short == len(slugs)


def test_em_dash_in_race_name_does_not_drop_claim():
    races = [
        {"name": "Tour of Thekkady \u2014 Kerala Gran Fondo", "slug": "thekkady", "tier": 2,
         "overall_score": 70},
        {"name": "Other Gravel", "slug": "other", "tier": 3, "overall_score": 50},
    ]
    texts = [_plain(c.text_html) for c in build_in_short_claims(races, "March 2026")]
    assert "Tour of Thekkady \u2014 Kerala Gran Fondo rates highest at 70/100 (T2 Elite)." in texts
    # Two names, one with an em dash: still kept.
    races[1]["overall_score"] = 70
    races[1]["tier"] = 2
    texts = [_plain(c.text_html) for c in build_in_short_claims(races, "March 2026")]
    assert any(t.endswith("share the highest rating, 70/100.") for t in texts)


def test_template_text_is_still_checked():
    from generate_season_roundup import _claim_ok

    assert not _claim_ok("Race rates highest \u2014 by far.")
    assert not _claim_ok("We rate Race highest.")
    assert _claim_ok("A \u2014 B rates highest.", "Race rates highest.")
    assert not _claim_ok("word " * 26, "Race.")  # the word cap counts the names


def test_real_march_2026_roundup_names_top_rated(race_index, tmp_path):
    march = [r for r in race_index if "Thekkady" in (r.get("name") or "")]
    if not march:
        pytest.skip("Tour of Thekkady not in the race index")
    generate_all(race_index, 2026, tmp_path)
    page = (tmp_path / "roundup-march-2026.html").read_text()
    texts = [_plain(t) for t, _ in _claims_in(page)]
    assert any("rates highest" in t or "share the highest rating" in t for t in texts), texts
