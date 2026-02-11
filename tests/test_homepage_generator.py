"""Tests for the Gravel God homepage generator."""
import json
import re
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_homepage import (
    load_race_index,
    compute_stats,
    get_featured_races,
    load_editorial_one_liners,
    load_upcoming_races,
    fetch_substack_posts,
    load_guide_chapters,
    generate_homepage,
    build_nav,
    build_ticker,
    build_hero,
    build_stats_bar,
    build_featured_races,
    build_coming_up,
    build_how_it_works,
    build_guide_preview,
    build_featured_in,
    build_training_cta,
    build_email_capture,
    build_footer,
    build_homepage_css,
    build_homepage_js,
    build_jsonld,
    _tier_badge_class,
    FEATURED_SLUGS,
    FEATURED_ARTICLES,
    GA4_MEASUREMENT_ID,
)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def race_index():
    return load_race_index()


@pytest.fixture(scope="module")
def stats(race_index):
    return compute_stats(race_index)


@pytest.fixture(scope="module")
def one_liners():
    return load_editorial_one_liners()


@pytest.fixture(scope="module")
def upcoming():
    return load_upcoming_races()


@pytest.fixture(scope="module")
def chapters():
    return load_guide_chapters()


@pytest.fixture(scope="module")
def homepage_html(race_index):
    return generate_homepage(race_index)


# ── Data Loading ─────────────────────────────────────────────


class TestDataLoading:
    def test_race_index_loads(self, race_index):
        assert isinstance(race_index, list)
        assert len(race_index) > 0

    def test_race_index_has_required_fields(self, race_index):
        for race in race_index[:5]:
            assert "slug" in race
            assert "name" in race
            assert "tier" in race
            assert "overall_score" in race

    def test_stats_race_count(self, stats, race_index):
        assert stats["race_count"] == len(race_index)

    def test_stats_dimensions(self, stats):
        assert stats["dimensions"] == 14

    def test_stats_t1_count(self, stats, race_index):
        expected = sum(1 for r in race_index if r.get("tier") == 1)
        assert stats["t1_count"] == expected

    def test_stats_tier_levels(self, stats):
        assert stats["tier_levels"] == 4


# ── Featured Races ───────────────────────────────────────────


class TestFeaturedRaces:
    def test_returns_six_races(self, race_index):
        featured = get_featured_races(race_index)
        assert len(featured) == 6

    def test_featured_slugs_present(self, race_index):
        featured = get_featured_races(race_index)
        slugs = {r["slug"] for r in featured}
        by_slug = {r["slug"] for r in race_index}
        for s in FEATURED_SLUGS:
            if s in by_slug:
                assert s in slugs, f"Expected {s} in featured races"

    def test_featured_have_required_fields(self, race_index):
        featured = get_featured_races(race_index)
        for race in featured:
            assert "name" in race
            assert "slug" in race
            assert "tier" in race
            assert "overall_score" in race

    def test_fallback_fills_slots(self):
        """If curated slugs aren't found, fallback to top T1 races."""
        minimal_index = [
            {"slug": "test-race-1", "name": "Test 1", "tier": 1, "overall_score": 90},
            {"slug": "test-race-2", "name": "Test 2", "tier": 1, "overall_score": 85},
            {"slug": "test-race-3", "name": "Test 3", "tier": 1, "overall_score": 80},
            {"slug": "test-race-4", "name": "Test 4", "tier": 1, "overall_score": 75},
            {"slug": "test-race-5", "name": "Test 5", "tier": 1, "overall_score": 70},
            {"slug": "test-race-6", "name": "Test 6", "tier": 1, "overall_score": 65},
        ]
        featured = get_featured_races(minimal_index)
        assert len(featured) == 6


# ── Dynamic Data Loading ─────────────────────────────────────


class TestEditorialOneLIners:
    def test_loads_one_liners(self, one_liners):
        assert len(one_liners) > 0

    def test_only_t1_t2(self, one_liners):
        for ol in one_liners:
            assert ol["tier"] <= 2, f'{ol["name"]} is T{ol["tier"]}, expected T1 or T2'

    def test_has_required_fields(self, one_liners):
        for ol in one_liners[:5]:
            assert "name" in ol
            assert "slug" in ol
            assert "text" in ol
            assert len(ol["text"]) > 0


class TestUpcomingRaces:
    def test_loads_upcoming(self, upcoming):
        assert isinstance(upcoming, list)

    def test_sorted_by_date(self, upcoming):
        if len(upcoming) > 1:
            dates = [r["date"] for r in upcoming]
            assert dates == sorted(dates)

    def test_has_required_fields(self, upcoming):
        for r in upcoming[:5]:
            assert "name" in r
            assert "slug" in r
            assert "date" in r
            assert "days" in r
            assert "tier" in r

    def test_within_date_range(self, upcoming):
        for r in upcoming:
            assert -14 <= r["days"] <= 60, f'{r["name"]} is {r["days"]} days out'


class TestGuideChapters:
    def test_loads_chapters(self, chapters):
        assert len(chapters) == 8

    def test_chapter_numbers_sequential(self, chapters):
        numbers = [ch["number"] for ch in chapters]
        assert numbers == list(range(1, 9))

    def test_first_three_free(self, chapters):
        for ch in chapters[:3]:
            assert ch["gated"] is False

    def test_last_five_gated(self, chapters):
        for ch in chapters[3:]:
            assert ch["gated"] is True


# ── Section Builders ─────────────────────────────────────────


class TestSectionBuilders:
    def test_nav_has_logo(self):
        nav = build_nav()
        assert "cropped-Gravel-God-logo" in nav
        assert "<img" in nav

    def test_nav_has_links(self):
        nav = build_nav()
        assert "/gravel-races/" in nav
        assert "/coaching/" in nav
        assert "/articles/" in nav
        assert "/about/" in nav

    def test_nav_no_breadcrumb(self):
        nav = build_nav()
        assert "breadcrumb" not in nav.lower()

    def test_ticker_has_content(self, one_liners, upcoming):
        substack = fetch_substack_posts()
        ticker = build_ticker(one_liners, substack, upcoming)
        assert "gg-hp-ticker" in ticker
        assert "gg-ticker-scroll" in build_homepage_css()

    def test_ticker_has_editorial_quotes(self, one_liners, upcoming):
        ticker = build_ticker(one_liners, [], upcoming)
        assert "&ldquo;" in ticker  # Has quoted one-liners

    def test_ticker_empty_input(self):
        ticker = build_ticker([], [], [])
        assert ticker == ""

    def test_coming_up_section(self, upcoming):
        html = build_coming_up(upcoming)
        if upcoming:
            assert "COMING UP" in html
            assert "gg-hp-cal-item" in html
        else:
            assert html == ""

    def test_guide_preview_section(self, chapters):
        html = build_guide_preview(chapters)
        assert "GRAVEL TRAINING GUIDE" in html
        assert html.count("gg-hp-guide-ch") == 8
        assert "FREE" in html
        assert "EMAIL TO UNLOCK" in html
        assert "READ FREE CHAPTERS" in html
        assert "The deal:" in html

    def test_guide_preview_empty(self):
        html = build_guide_preview([])
        assert html == ""

    def test_hero_has_h1(self, stats):
        hero = build_hero(stats)
        assert "<h1" in hero
        assert "EVERY GRAVEL RACE. RATED. RANKED." in hero

    def test_hero_has_race_count_badge(self, stats):
        hero = build_hero(stats)
        assert f'{stats["race_count"]} RACES RATED' in hero

    def test_hero_has_ctas(self, stats):
        hero = build_hero(stats)
        assert "FIND YOUR NEXT RACE" in hero
        assert "HOW WE RATE" in hero

    def test_stats_bar_four_stats(self, stats):
        bar = build_stats_bar(stats)
        assert bar.count("gg-hp-stat-number") == 4

    def test_stats_bar_has_values(self, stats):
        bar = build_stats_bar(stats)
        assert str(stats["race_count"]) in bar
        assert str(stats["dimensions"]) in bar
        assert str(stats["t1_count"]) in bar
        assert str(stats["tier_levels"]) in bar

    def test_featured_races_section(self, race_index):
        html = build_featured_races(race_index)
        assert "FEATURED RACES" in html
        assert "gg-hp-race-card" in html
        assert "VIEW ALL" in html

    def test_featured_races_has_six_cards(self, race_index):
        html = build_featured_races(race_index)
        assert html.count("gg-hp-race-card") >= 6

    def test_how_it_works_three_steps(self):
        html = build_how_it_works()
        assert "01" in html
        assert "02" in html
        assert "03" in html
        assert "BROWSE RACES" in html
        assert "READ THE RATINGS" in html
        assert "TRAIN" in html

    def test_featured_in_section(self):
        html = build_featured_in()
        assert "AS FEATURED IN" in html
        assert "TrainingPeaks" in html
        assert "gg-hp-feat-logo" in html

    def test_training_cta_has_both_options(self):
        html = build_training_cta()
        assert "Training Plans" in html
        assert "1:1 Coaching" in html
        assert "BUILD MY PLAN" in html
        assert "APPLY" in html

    def test_training_cta_links(self):
        html = build_training_cta()
        assert "/training-plans/" in html
        assert "wattgod.com/apply" in html

    def test_email_capture_has_content(self):
        html = build_email_capture()
        assert "Slow, Mid, 38s" in html
        assert "substack.com/embed" in html
        assert "gg-hp-email" in html

    def test_email_capture_with_articles(self):
        posts = [
            {"title": "Test Article", "url": "https://example.com/test", "snippet": "A test snippet."},
            {"title": "Another Post", "url": "https://example.com/another", "snippet": "More content."},
        ]
        html = build_email_capture(posts)
        assert "gg-hp-article-carousel" in html
        assert "Test Article" in html
        assert 'data-ga="article_click"' in html

    def test_email_capture_no_articles(self):
        html = build_email_capture([])
        assert "gg-hp-article-carousel" not in html

    def test_footer_has_links(self):
        html = build_footer()
        assert "/gravel-races/" in html
        assert "/coaching/" in html
        assert "/articles/" in html
        assert "/about/" in html
        assert "substack" in html.lower()

    def test_footer_has_copyright(self):
        html = build_footer()
        assert "GRAVEL GOD CYCLING" in html
        assert "2026" in html

    def test_footer_has_structure(self):
        html = build_footer()
        assert "EXPLORE" in html
        assert "NEWSLETTER" in html
        assert "SUBSCRIBE" in html


# ── CSS ──────────────────────────────────────────────────────


class TestCSS:
    def test_css_has_style_tag(self):
        css = build_homepage_css()
        assert css.startswith("<style>")
        assert css.endswith("</style>")

    def test_css_has_hero_styles(self):
        css = build_homepage_css()
        assert ".gg-hp-hero" in css

    def test_css_has_responsive_breakpoint(self):
        css = build_homepage_css()
        assert "@media (max-width: 768px)" in css

    def test_css_uses_brand_colors(self):
        css = build_homepage_css()
        assert "#59473c" in css  # primary brown
        assert "#1A8A82" in css  # teal
        assert "#B7950B" in css  # gold

    def test_css_sometype_mono(self):
        css = build_homepage_css()
        assert "Sometype Mono" in css

    def test_css_brand_guide_compliance(self):
        """Brand guide: no border-radius, no box-shadow, no gradients, Source Serif 4."""
        css = build_homepage_css()
        assert "box-sizing: border-box" in css
        assert "border-radius" not in css
        assert "box-shadow" not in css
        assert "linear-gradient" not in css
        assert "radial-gradient" not in css
        assert "Source Serif 4" in css
        assert "#ede4d8" in css  # sand background
        assert "#3a2e25" in css  # dark brown borders
        assert "4px double" in css  # double-rule structural borders


# ── JavaScript ───────────────────────────────────────────────


class TestJS:
    def test_js_has_script_tag(self):
        js = build_homepage_js()
        assert js.startswith("<script>")
        assert js.endswith("</script>")

    def test_js_has_ga4_tracking(self):
        js = build_homepage_js()
        assert "data-ga" in js
        assert "gtag" in js
        assert "event_name" in js

    def test_js_no_banned_motion(self):
        """Brand guide bans entrance animations, scroll-triggered animations, and scale transforms."""
        js = build_homepage_js()
        assert "IntersectionObserver" not in js
        assert "translateY" not in js
        assert "scale(" not in js


# ── JSON-LD ──────────────────────────────────────────────────


class TestJSONLD:
    def test_jsonld_has_organization(self, stats):
        jsonld = build_jsonld(stats)
        assert '"Organization"' in jsonld

    def test_jsonld_has_website(self, stats):
        jsonld = build_jsonld(stats)
        assert '"WebSite"' in jsonld

    def test_jsonld_has_search_action(self, stats):
        jsonld = build_jsonld(stats)
        assert '"SearchAction"' in jsonld

    def test_jsonld_valid_json(self, stats):
        jsonld = build_jsonld(stats)
        blocks = re.findall(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
            jsonld, re.DOTALL
        )
        assert len(blocks) == 2  # Organization + WebSite
        for block in blocks:
            parsed = json.loads(block)
            assert "@context" in parsed
            assert "@type" in parsed


# ── Full Page Assembly ───────────────────────────────────────


class TestFullPage:
    def test_valid_html_structure(self, homepage_html):
        assert homepage_html.startswith("<!DOCTYPE html>")
        assert "<html lang=" in homepage_html
        assert "</html>" in homepage_html

    def test_has_title(self, homepage_html):
        assert "<title>" in homepage_html
        assert "Gravel God" in homepage_html

    def test_has_meta_description(self, homepage_html):
        assert 'name="description"' in homepage_html

    def test_has_canonical(self, homepage_html):
        assert 'rel="canonical"' in homepage_html
        assert "/homepage/" in homepage_html

    def test_has_og_tags(self, homepage_html):
        assert 'property="og:title"' in homepage_html
        assert 'property="og:description"' in homepage_html
        assert 'property="og:type"' in homepage_html

    def test_has_google_fonts(self, homepage_html):
        assert "fonts.googleapis.com" in homepage_html
        assert "Sometype+Mono" in homepage_html
        assert "Source+Serif+4" in homepage_html

    def test_has_ga4(self, homepage_html):
        assert GA4_MEASUREMENT_ID in homepage_html
        assert "googletagmanager.com/gtag/js" in homepage_html

    def test_has_all_sections(self, homepage_html):
        assert "gg-hp-header" in homepage_html
        assert "gg-hp-ticker" in homepage_html
        assert "gg-hp-hero" in homepage_html
        assert "gg-hp-stats-bar" in homepage_html
        assert "gg-hp-featured" in homepage_html
        assert "gg-hp-coming-up" in homepage_html
        assert "gg-hp-how-it-works" in homepage_html
        assert "gg-hp-guide" in homepage_html
        assert "gg-hp-featured-in" in homepage_html
        assert "gg-hp-training" in homepage_html
        assert "gg-hp-email" in homepage_html
        assert "gg-hp-footer" in homepage_html

    def test_has_jsonld_blocks(self, homepage_html):
        blocks = re.findall(r'application/ld\+json', homepage_html)
        assert len(blocks) == 2  # Organization + WebSite

    def test_has_h1(self, homepage_html):
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', homepage_html, re.DOTALL)
        assert h1_match is not None
        assert "EVERY GRAVEL RACE" in h1_match.group(1)

    def test_page_size_reasonable(self, homepage_html):
        size_kb = len(homepage_html) / 1024
        assert size_kb < 150, f"Homepage is {size_kb:.1f}KB, expected under 150KB"
        assert size_kb > 20, f"Homepage is {size_kb:.1f}KB, seems too small"

    def test_ctas_have_ga_tracking(self, homepage_html):
        for event in ['hero_cta_click', 'featured_race_click', 'view_all_races',
                       'training_plan_click', 'coaching_click', 'subscribe_click', 'guide_click']:
            assert f'data-ga="{event}"' in homepage_html, f"Missing GA event: {event}"

    def test_no_broken_template_vars(self, homepage_html):
        assert "{race_count}" not in homepage_html
        assert "{search_term_string}" not in homepage_html or "query-input" in homepage_html


# ── Constants ────────────────────────────────────────────────


class TestConstants:
    def test_featured_slugs_count(self):
        assert len(FEATURED_SLUGS) == 6



# ── Regression Tests ────────────────────────────────────────


class TestRegressions:
    """Regression tests for issues found in the critical audit."""

    def test_ticker_classes_match_css(self):
        """Ticker HTML classes must match CSS selectors (was gg-ticker-item, should be gg-hp-ticker-item)."""
        one_liners = [
            {"name": "Test Race", "slug": "test", "score": 90, "tier": 1, "text": "A great race."},
        ]
        ticker = build_ticker(one_liners, [], [])
        assert "gg-hp-ticker-item" in ticker
        assert "gg-hp-ticker-sep" in ticker
        # Must NOT have unprefixed classes
        assert 'class="gg-ticker-item"' not in ticker
        assert 'class="gg-ticker-sep"' not in ticker

    def test_og_image_present(self, homepage_html):
        """Homepage must have og:image meta tag."""
        assert 'property="og:image"' in homepage_html

    def test_twitter_image_present(self, homepage_html):
        """Homepage must have twitter:image meta tag."""
        assert 'name="twitter:image"' in homepage_html

    def test_favicon_present(self, homepage_html):
        """Homepage must have a favicon."""
        assert 'rel="icon"' in homepage_html

    def test_no_inline_style_on_badges(self, homepage_html):
        """Tier badges must use CSS classes, not inline styles."""
        import re
        badge_matches = re.findall(r'class="gg-hp-tier-badge[^"]*"[^>]*>', homepage_html)
        for match in badge_matches:
            assert "style=" not in match, f"Inline style found on badge: {match}"
        cal_badge_matches = re.findall(r'class="gg-hp-cal-badge[^"]*"[^>]*>', homepage_html)
        for match in cal_badge_matches:
            assert "style=" not in match, f"Inline style found on cal badge: {match}"

    def test_badge_classes_exist_in_css(self):
        """CSS must define classes for all 4 tier badge levels."""
        css = build_homepage_css()
        for t in range(1, 5):
            assert f".gg-hp-badge-t{t}" in css

    def test_tier_badge_class_function(self):
        """_tier_badge_class returns correct class for each tier."""
        assert _tier_badge_class(1) == "gg-hp-badge-t1"
        assert _tier_badge_class(2) == "gg-hp-badge-t2"
        assert _tier_badge_class(3) == "gg-hp-badge-t3"
        assert _tier_badge_class(4) == "gg-hp-badge-t4"
        assert _tier_badge_class(99) == "gg-hp-badge-t4"

    def test_skip_link_present(self, homepage_html):
        """Homepage must have a skip-to-content link for accessibility."""
        assert 'class="gg-hp-skip"' in homepage_html
        assert 'href="#main"' in homepage_html

    def test_main_id_exists(self, homepage_html):
        """Hero section must have id="main" for skip link target."""
        assert 'id="main"' in homepage_html

    def test_section_ids_present(self, homepage_html):
        """Key sections must have IDs for anchor navigation."""
        for section_id in ["main", "featured", "training", "newsletter"]:
            assert f'id="{section_id}"' in homepage_html, f"Missing section id: {section_id}"

    def test_tablet_breakpoint(self):
        """CSS must have a tablet breakpoint at 1024px."""
        css = build_homepage_css()
        assert "@media (max-width: 1024px)" in css

    def test_no_grayscale_filter(self):
        """Brand guide prohibits filter/opacity transitions."""
        css = build_homepage_css()
        assert "grayscale" not in css
        assert "filter:" not in css

    def test_no_opacity_transition(self):
        """Hover transitions must be border-color/background-color/color only."""
        css = build_homepage_css()
        assert "transition: opacity" not in css

    def test_substack_included_in_ticker(self, homepage_html):
        """Substack articles should appear in the ticker to surface editorial voice."""
        import re
        ticker_match = re.search(r'class="gg-hp-ticker".*?</div>\s*</div>', homepage_html, re.DOTALL)
        if ticker_match:
            assert "NEWSLETTER" in ticker_match.group(0), "Substack posts should appear in ticker"

    def test_latest_takes_section(self, homepage_html):
        """Latest Takes section should appear with article cards."""
        assert "LATEST TAKES" in homepage_html
        assert "gg-hp-latest-takes" in homepage_html
        assert "gg-hp-take-card" in homepage_html
        assert "ALL ARTICLES" in homepage_html

    def test_latest_takes_before_coming_up(self, homepage_html):
        """Latest Takes should appear before Coming Up in page order."""
        takes_pos = homepage_html.find("gg-hp-latest-takes")
        coming_pos = homepage_html.find("gg-hp-coming-up")
        if takes_pos >= 0 and coming_pos >= 0:
            assert takes_pos < coming_pos, "Latest Takes should appear before Coming Up"

    def test_training_before_guide(self, homepage_html):
        """Training/coaching section should appear before guide preview in body."""
        training_pos = homepage_html.find('id="training"')
        guide_pos = homepage_html.find('id="guide"')
        if training_pos >= 0 and guide_pos >= 0:
            assert training_pos < guide_pos, "Training should appear before Guide"

    def test_featured_in_no_self_deprecation(self):
        """Featured-in copy should not undermine authority."""
        html = build_featured_in()
        assert "probably know better" not in html
        assert "let me talk" not in html

    def test_coming_up_capped(self, upcoming):
        """Coming-up should show max 2 recent + 5 upcoming."""
        html = build_coming_up(upcoming)
        if upcoming:
            past_count = html.count("gg-hp-cal-item--past")
            assert past_count <= 2
            # Count actual calendar links (each has gg-hp-cal-score)
            total = html.count("gg-hp-cal-score")
            assert total <= 7  # 2 recent + 5 upcoming

    def test_how_it_works_accepts_stats(self, stats):
        """build_how_it_works should accept stats and render race count."""
        html = build_how_it_works(stats)
        assert str(stats["race_count"]) in html
        assert "{race_count}" not in html

    def test_ticker_hidden_on_mobile(self):
        """Ticker should be hidden on mobile via CSS."""
        css = build_homepage_css()
        assert ".gg-hp-ticker { display: none; }" in css

    def test_articles_stack_on_mobile(self):
        """Article cards should stack vertically on mobile."""
        css = build_homepage_css()
        assert "flex-direction: column" in css
        assert ".gg-hp-article-card:nth-child(n+4) { display: none; }" in css


def html_escape(text):
    """Helper for test assertions."""
    import html as _html
    return _html.escape(str(text))
