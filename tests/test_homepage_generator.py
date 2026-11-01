"""Tests for the Gravel God homepage generator.

The page is four things (homepage cut, Nov 2026): the 2027 goals poster
wall, the race database band, one band of four doors, and the footer.
"""
import json
import re
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_homepage import (
    CURRENT_YEAR,
    DOORS,
    RANKINGS_URL,
    RATING_DIMS,
    SERIES_UMBRELLA_SLUGS,
    TOP_RATED_COUNT,
    build_doors,
    build_footer,
    build_goal_hero,
    build_hero,
    build_homepage_css,
    build_homepage_js,
    build_jsonld,
    build_nav,
    build_top_bar,
    build_top_rated,
    compute_stats,
    generate_homepage,
    get_top_rated,
    load_race_index,
)
from brand_tokens import GA_MEASUREMENT_ID

ROOT = Path(__file__).parent.parent


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def race_index():
    return load_race_index()


@pytest.fixture(scope="module")
def stats(race_index):
    return compute_stats(race_index)


@pytest.fixture(scope="module")
def homepage_html(race_index):
    return generate_homepage(race_index)


def _body(html: str) -> str:
    return html[html.index("<body"):]


# ── Data ─────────────────────────────────────────────────────


class TestData:
    def test_race_index_loads(self, race_index):
        assert len(race_index) > 100
        assert all("slug" in r for r in race_index)

    def test_stats_keys(self, stats):
        for key in ("race_count", "dimensions", "t1_count", "t2_count", "region_count"):
            assert key in stats
        assert stats["dimensions"] == len(RATING_DIMS) == 15

    def test_stats_counts_match_index(self, race_index, stats):
        assert stats["race_count"] == len(race_index)
        assert stats["t1_count"] == sum(1 for r in race_index if r.get("tier") == 1)


class TestTopRated:
    def test_count(self, race_index):
        assert len(get_top_rated(race_index)) == TOP_RATED_COUNT

    def test_sorted_by_score(self, race_index):
        scores = [r.get("overall_score", 0) for r in get_top_rated(race_index)]
        assert scores == sorted(scores, reverse=True)

    def test_gravel_only(self, race_index):
        for race in get_top_rated(race_index):
            assert (race.get("discipline") or "gravel") == "gravel", race["slug"]

    def test_excludes_series_umbrellas(self):
        fake = [
            {"slug": "grinduro", "name": "Grinduro", "overall_score": 99, "discipline": "gravel"},
            {"slug": "real-race", "name": "Real", "overall_score": 80, "discipline": "gravel"},
            {"slug": "mtb-race", "name": "MTB", "overall_score": 98, "discipline": "mtb"},
        ]
        assert [r["slug"] for r in get_top_rated(fake)] == ["real-race"]
        assert "grinduro" in SERIES_UMBRELLA_SLUGS

    def test_excludes_profiles_whose_vitals_say_road(self, tmp_path):
        """race-index.json can label a road race gravel; the profile wins."""
        (tmp_path / "road-fondo.json").write_text(json.dumps({"race": {"vitals": {"discipline": "road"}}}))
        fake = [
            {"slug": "road-fondo", "overall_score": 95},
            {"slug": "dirt-race", "overall_score": 80},
        ]
        assert [r["slug"] for r in get_top_rated(fake, race_data_dir=tmp_path)] == ["dirt-race"]

    def test_real_top_rated_has_no_road_profiles(self, race_index):
        for race in get_top_rated(race_index):
            profile = json.loads((ROOT / "race-data" / f'{race["slug"]}.json').read_text())
            vitals = profile.get("race", profile).get("vitals", {})
            assert (vitals.get("discipline") or "gravel") == "gravel", race["slug"]

    def test_rows_link_to_race_pages(self, race_index):
        html = build_top_rated(race_index)
        for race in get_top_rated(race_index):
            assert f'/race/{race["slug"]}/' in html
        assert html.count('class="gg-hp-top-row"') == TOP_RATED_COUNT
        assert html.count('data-ga="ranking_click"') == TOP_RATED_COUNT

    def test_links_to_full_rankings(self, race_index):
        html = build_top_rated(race_index)
        assert RANKINGS_URL in html
        assert f"/race/power-rankings-{CURRENT_YEAR}/" in RANKINGS_URL

    def test_empty_index(self):
        html = build_top_rated([])
        assert "gg-hp-top-row" not in html
        assert "TOP RATED" in html


# ── Header / footer ──────────────────────────────────────────


class TestChrome:
    def test_nav_has_logo_and_links(self):
        nav = build_nav()
        assert "gg-logo-mark" in nav
        for path in ("/gravel-races/", "/coaching/", "/articles/", "/about/", "/guide/"):
            assert path in nav
        assert "breadcrumb" not in nav.lower()

    def test_top_bar_is_decorative(self):
        assert 'aria-hidden="true"' in build_top_bar()

    def test_footer_carries_newsletter(self):
        html = build_footer()
        assert "NEWSLETTER" in html
        assert "SUBSCRIBE" in html
        assert "substack" in html.lower()
        assert "/products/training-plans/" in html


# ── Goal poster wall (owner-ruled, goals-2027-funnel D5) ─────


class TestGoalHero:
    def test_fixed_headline_and_button(self):
        hero = build_goal_hero()
        assert "It&rsquo;s dreaming season. Most of it stays a dream." in hero
        assert "MAKE MINE" in hero
        assert 'href="https://gravelgodcycling.com/goals/?src=home"' in hero
        assert 'data-ga="goal_hero_click"' in hero
        assert 'data-ga-label="home"' in hero

    def test_no_subtitle(self):
        """House rule: the only <p> is the eyebrow kicker."""
        hero = build_goal_hero()
        assert hero.count("<p") == 1
        assert 'class="gg-hp-hero-kicker"' in hero

    def test_headline_is_h2_not_h1(self):
        hero = build_goal_hero()
        assert "<h1" not in hero
        assert hero.count("<h2") == 1

    def test_three_posters(self):
        hero = build_goal_hero()
        assert hero.count('class="gg-hp-poster gg-hp-poster--') == 3
        for i in range(3):
            assert f"gg-goal-poster-{i}" in hero

    def test_owns_skip_link_target(self):
        assert 'id="main"' in build_goal_hero()

    def test_poster_js_never_uses_a_timer(self, homepage_html):
        idx = homepage_html.index("Goal poster wall")
        end = homepage_html.index(")();", idx)
        script = homepage_html[idx:end]
        assert "setInterval" not in script
        assert "setTimeout" not in script
        assert "SAMPLE" in script

    def test_poster_click_reshuffles(self, homepage_html):
        assert "addEventListener('click'" in homepage_html
        assert 'id="gg-poster-wall"' in homepage_html

    def test_poster_matches_real_layout_rows(self, homepage_html):
        idx = homepage_html.index("Goal poster wall")
        end = homepage_html.index(")();", idx)
        script = homepage_html[idx:end]
        assert '"EVERY DAY"' in script
        assert '"ALSO EVERY DAY"' in script
        assert '"WATCH FOR"' in script
        assert "pad + 200" in script

    def test_poster_samples_are_complete_and_invented(self, homepage_html):
        idx = homepage_html.index("var SAMPLES = [")
        end = homepage_html.index("];", idx)
        samples_src = homepage_html[idx:end]
        for field in ("goal:", "why:", "habit:", "habit_when:", "inner_obstacle:"):
            assert samples_src.count(field) >= 5, field
        assert "habit_2:" in samples_src
        assert not re.search(r"\d+%|\bPRs?\b", samples_src)


# ── Race database band ───────────────────────────────────────


class TestRaceBand:
    def test_single_h1(self, stats, race_index):
        hero = build_hero(stats, race_index)
        assert len(re.findall(r"<h1[\s>]", hero)) == 1
        assert "Every gravel race, rated." in hero

    def test_search_form(self, stats, race_index):
        hero = build_hero(stats, race_index)
        assert 'role="search"' in hero
        assert 'action="https://gravelgodcycling.com/gravel-races/"' in hero
        assert 'name="q"' in hero

    def test_chips(self, stats, race_index):
        hero = build_hero(stats, race_index)
        for label in ("gravel", "bikepacking", "mtb", "tier1"):
            assert f'data-ga-label="{label}"' in hero
        assert "/race/methodology/" in hero

    def test_numbers_once(self, stats, race_index, homepage_html):
        hero = build_hero(stats, race_index)
        assert f"<dd>{stats['race_count']}</dd>" in hero
        assert f"<dd>{stats['region_count']}</dd>" in hero
        assert f"<dd>{stats['dimensions']}</dd>" in hero
        assert _body(homepage_html).count(f"<dd>{stats['race_count']}</dd>") == 1

    def test_includes_top_rated(self, stats, race_index):
        assert "gg-hp-top-list" in build_hero(stats, race_index)

    def test_section_id(self, stats, race_index):
        assert 'id="race-database"' in build_hero(stats, race_index)


# ── Four doors ───────────────────────────────────────────────


class TestDoors:
    def test_four_doors(self):
        html = build_doors()
        assert len(DOORS) == 4
        assert html.count('<article class="gg-hp-door ') == 4

    def test_destinations(self):
        html = build_doors()
        for path in ("/guide/", "/surge-check/", "/training-plans/start/", "/coaching/"):
            assert path in html, path

    def test_one_title_one_button_each(self):
        html = build_doors()
        assert html.count('class="gg-hp-door-title"') == 4
        assert html.count('class="gg-hp-door-btn"') == 4

    def test_no_helper_copy(self):
        """Only the plan door carries a line under its title: the A/B price target."""
        html = build_doors()
        assert html.count("<p") == 1
        assert 'data-ab="training_price"' in html

    def test_ab_targets_present_once(self, homepage_html):
        body = _body(homepage_html)
        assert body.count('data-ab="training_price"') == 1
        assert body.count('data-ab="training_cta_btn"') == 1

    def test_ab_targets_match_live_experiments(self):
        experiments = json.loads((ROOT / "web" / "ab" / "experiments.json").read_text())
        selectors = {e["selector"] for e in experiments["experiments"] if "/" in e["pages"]}
        assert "[data-ab='training_price']" in selectors
        assert "[data-ab='training_cta_btn']" in selectors

    def test_art_is_responsive_and_lazy(self):
        html = build_doors()
        for _, _, _, _, art, _ in DOORS:
            assert f"/guide/media/gg-art-{art}-1x.webp" in html
            assert f"/guide/media/gg-art-{art}-2x.webp 1920w" in html
            assert (ROOT / "guide" / "art" / f"gg-art-{art}-1x.webp").exists(), art
            assert (ROOT / "guide" / "art" / f"gg-art-{art}-2x.webp").exists(), art
        assert html.count('loading="lazy"') == 4
        assert html.count('width="960" height="640"') == 4

    def test_paid_doors_fire_cta_click(self):
        html = build_doors()
        assert 'data-ga="cta_click" data-ga-label="door_plan"' in html
        assert 'data-ga="cta_click" data-ga-label="door_coaching"' in html
        assert 'data-ga="door_click" data-ga-label="door_handbook"' in html
        assert 'data-ga="door_click" data-ga-label="door_surge_check"' in html


# ── CSS / JS ─────────────────────────────────────────────────


class TestCSS:
    def test_style_tag(self):
        css = build_homepage_css()
        assert css.startswith("<style>")
        assert css.endswith("</style>")

    def test_breakpoints(self):
        css = build_homepage_css()
        for bp in ("1100px", "900px", "600px"):
            assert f"@media (max-width: {bp})" in css

    def test_brand_guide_compliance(self):
        """No rounded corners, drop shadows or gradients; brand fonts."""
        css = build_homepage_css()
        css_no_tokens = re.sub(r"--gg-border-radius:\s*0", "", css)
        assert "border-radius" not in css_no_tokens
        assert "box-shadow" not in css
        assert "linear-gradient" not in css
        assert "radial-gradient" not in css
        assert "Source Serif 4" in css
        assert "Sometype Mono" in css
        assert "filter:" not in css

    def test_new_sections_use_tokens_not_hex(self):
        css = build_homepage_css()
        start = css.index("/* ── Shared type + buttons")
        end = css.index("/* ── Wide desktop")
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css[start:end])

    def test_cut_sections_gone(self):
        css = build_homepage_css()
        for cls in ("gg-hp-ticker", "gg-hp-ladder", "gg-hp-stats-stripe", "gg-hp-bento",
                    "gg-hp-sidebar", "gg-hp-take", "gg-hp-how-it-works", "gg-hp-guide",
                    "gg-hp-featured-in", "gg-hp-email", "gg-hp-gw", "gg-hp-hv-"):
            assert cls not in css, cls


class TestJS:
    def test_script_tag(self):
        js = build_homepage_js()
        assert js.startswith("<script>")
        assert js.endswith("</script>")

    def test_ga4_tracking(self):
        js = build_homepage_js()
        assert "data-ga" in js
        assert "gtag" in js
        assert "source: 'homepage'" in js

    def test_no_inner_html(self):
        assert "innerHTML" not in build_homepage_js()

    def test_no_timers_or_banned_motion(self):
        js = build_homepage_js()
        assert "setInterval" not in js
        assert "translateY" not in js
        assert "scale(" not in js


# ── JSON-LD ──────────────────────────────────────────────────


class TestJSONLD:
    def test_blocks_are_valid(self, stats):
        jsonld = build_jsonld(stats)
        blocks = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', jsonld, re.DOTALL)
        assert len(blocks) == 2
        types = {json.loads(b)["@type"] for b in blocks}
        assert types == {"Organization", "WebSite"}
        assert '"SearchAction"' in jsonld


# ── Full page ────────────────────────────────────────────────


class TestFullPage:
    def test_html_structure(self, homepage_html):
        assert homepage_html.startswith("<!DOCTYPE html>")
        assert '<html lang="en">' in homepage_html
        assert homepage_html.rstrip().endswith("</html>")

    def test_head(self, homepage_html):
        assert "<title>" in homepage_html and "Gravel God" in homepage_html
        assert 'name="description"' in homepage_html
        assert 'rel="canonical" href="https://gravelgodcycling.com/"' in homepage_html
        for tag in ('property="og:title"', 'property="og:image"', 'name="twitter:image"', 'rel="icon"'):
            assert tag in homepage_html
        assert "application/rss+xml" in homepage_html

    def test_fonts_self_hosted(self, homepage_html):
        assert "@font-face" in homepage_html
        assert "fonts.googleapis.com" not in homepage_html

    def test_ga4_and_consent(self, homepage_html):
        assert GA_MEASUREMENT_ID in homepage_html
        assert "googletagmanager.com/gtag/js" in homepage_html
        assert "gg-consent" in homepage_html

    def test_section_order(self, homepage_html):
        body = _body(homepage_html)
        order = ['class="gg-site-header', 'id="main"', 'id="race-database"', 'id="start"', "gg-mega-footer"]
        positions = [body.index(marker) for marker in order]
        assert positions == sorted(positions)

    def test_exactly_one_h1(self, homepage_html):
        assert len(re.findall(r"<h1[\s>]", homepage_html)) == 1

    def test_skip_link(self, homepage_html):
        assert 'class="gg-hp-skip"' in homepage_html
        assert 'href="#main"' in homepage_html
        assert _body(homepage_html).count('id="main"') == 1

    def test_cut_sections_absent(self, homepage_html):
        body = _body(homepage_html)
        for marker in ("gg-hp-ticker", "gg-hp-ladder", "gg-hp-stats-stripe", "gg-hp-content-grid",
                       "gg-hp-latest-takes", "gg-hp-how-it-works", "gg-hp-training-cta-full",
                       "gg-hp-featured-in", 'id="newsletter"', 'id="gravel-weekly"',
                       'data-viz="hero-radar"', "substack.com/embed"):
            assert marker not in body, marker

    def test_no_svg_circles(self, homepage_html):
        assert "<circle" not in homepage_html

    def test_no_inline_styles_in_sections(self, stats, race_index):
        for html in (build_goal_hero(), build_hero(stats, race_index), build_doors()):
            assert "style=" not in html

    def test_no_template_leaks(self, homepage_html):
        assert "{race_count}" not in homepage_html
        assert "__POSTER_JS__" not in homepage_html

    def test_size_budget(self, homepage_html):
        size_kb = len(homepage_html) / 1024
        assert 20 < size_kb < 100, f"Homepage is {size_kb:.1f}KB"

    def test_no_defensive_copy(self, homepage_html):
        assert not re.search(r"not an AI|not a spreadsheet|honestly rated|unbiased", homepage_html, re.I)
