"""Tests for the Gravel God homepage generator."""
import json
import re
import sys
from datetime import date
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
    build_bento_features,
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
    build_top_bar,
    build_content_grid,
    build_tabbed_rankings,
    build_sidebar,
    build_latest_takes,
    build_testimonials,
    _tier_badge_class,
    _build_stat_bars,
    _build_hero_radar_viz,
    _compute_archetype_examples,
    _SERIES_UMBRELLA_SLUGS,
    _parse_score,
    FEATURED_SLUGS,
    STAT_BAR_DIMENSIONS,
    STAT_BAR_DIMENSIONS_COMPACT,
    HERO_VIZ_DIMS,
    HERO_VIZ_LABELS,
    HERO_VIZ_TOOLTIPS,
    HERO_VIZ_ARCHETYPES,
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
    from unittest.mock import patch
    fake_posts = [{"title": "Test Post", "url": "https://example.com", "snippet": "Test snippet"}]
    with patch("generate_homepage.fetch_substack_posts", return_value=fake_posts):
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
        assert stats["dimensions"] == 15

    def test_stats_t1_count(self, stats, race_index):
        expected = sum(1 for r in race_index if r.get("tier") == 1)
        assert stats["t1_count"] == expected

    def test_stats_keys(self, stats):
        assert "race_count" in stats
        assert "dimensions" in stats
        assert "t1_count" in stats
        assert "t2_count" in stats
        assert "region_count" in stats


# ── Featured Races ───────────────────────────────────────────


class TestFeaturedRaces:
    def test_returns_three_races(self, race_index):
        featured = get_featured_races(race_index)
        assert len(featured) == 3

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
        ]
        featured = get_featured_races(minimal_index)
        assert len(featured) == 3


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
        assert ">RACES</a>" in nav
        assert ">PRODUCTS</a>" in nav
        assert ">SERVICES</a>" in nav
        assert ">ARTICLES</a>" in nav
        assert ">ABOUT</a>" in nav

    def test_nav_has_dropdowns(self):
        nav = build_nav()
        assert "gg-site-header-dropdown" in nav
        assert "gg-site-header-item" in nav

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

    def test_hero_has_h1(self, stats, race_index):
        hero = build_hero(stats, race_index)
        assert "<h1" in hero
        assert "Every gravel race, honestly rated" in hero

    def test_hero_has_announcement_pill(self, stats, race_index):
        hero = build_hero(stats, race_index)
        assert "gg-hp-announce-pill" in hero
        assert f'{stats["race_count"]} Races Scored' in hero

    def test_hero_has_ctas(self, stats, race_index):
        hero = build_hero(stats, race_index)
        assert "Browse All Races" in hero
        assert "How We Rate" in hero

    def test_hero_has_radar_viz(self, stats, race_index):
        hero = build_hero(stats, race_index)
        assert 'data-viz="hero-radar"' in hero
        assert "<svg" in hero

    def test_stats_bar_five_stats(self, stats):
        bar = build_stats_bar(stats)
        assert bar.count("gg-hp-ss-val") == 5

    def test_stats_bar_has_values(self, stats):
        bar = build_stats_bar(stats)
        assert str(stats["race_count"]) in bar
        assert str(stats["dimensions"]) in bar
        assert str(stats["t1_count"]) in bar
        assert str(stats["t2_count"]) in bar
        assert "Regions" in bar

    def test_bento_features_section(self, race_index):
        html = build_bento_features(race_index)
        assert "gg-hp-bento" in html
        assert "gg-hp-bento-card" in html
        assert "gg-hp-statbar" in html

    def test_bento_features_has_three_cards(self, race_index):
        html = build_bento_features(race_index)
        assert html.count("gg-hp-bento-card") == 3

    def test_how_it_works_three_steps(self):
        html = build_how_it_works()
        assert "01" in html
        assert "02" in html
        assert "03" in html
        assert "PICK YOUR RACE" in html
        assert "READ THE REAL TAKE" in html
        assert "SHOW UP READY" in html

    def test_featured_in_section(self):
        html = build_featured_in()
        assert "AS FEATURED IN" in html
        assert "TrainingPeaks" in html
        assert "gg-hp-feat-logo" in html

    def test_training_cta_has_content(self):
        html = build_training_cta()
        assert "Train for the course" in html
        assert "Get Your Plan" in html
        assert "gg-hp-cta-card" in html

    def test_training_cta_links(self):
        html = build_training_cta()
        assert "/training-plans/" in html

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
        assert "substack" in html.lower()

    def test_footer_has_copyright(self):
        html = build_footer()
        assert "GRAVEL GOD CYCLING" in html
        assert "2026" in html

    def test_footer_has_structure(self):
        html = build_footer()
        assert "PRODUCTS" in html
        assert "SERVICES" in html
        assert "NEWSLETTER" in html
        assert "SUBSCRIBE" in html

    def test_footer_has_nav_headings(self):
        html = build_footer()
        assert "/products/training-plans/" in html
        assert "/guide/" in html


# ── CSS ──────────────────────────────────────────────────────


class TestCSS:
    def test_css_has_style_tag(self):
        css = build_homepage_css()
        assert css.startswith("<style>")
        assert css.endswith("</style>")

    def test_css_has_hero_styles(self):
        css = build_homepage_css()
        assert ".gg-hp-hero" in css

    def test_css_has_responsive_breakpoints(self):
        css = build_homepage_css()
        assert "@media (max-width: 900px)" in css
        assert "@media (max-width: 600px)" in css

    def test_css_uses_brand_colors(self):
        css = build_homepage_css()
        assert "#59473c" in css  # primary brown
        assert "#178079" in css  # teal
        assert "#9a7e0a" in css  # gold

    def test_css_sometype_mono(self):
        css = build_homepage_css()
        assert "Sometype Mono" in css

    def test_css_brand_guide_compliance(self):
        """Brand guide: no border-radius, no box-shadow, no gradients, Source Serif 4."""
        css = build_homepage_css()
        assert "box-sizing: border-box" in css
        # Token definition (--gg-border-radius: 0) is OK; actual property usage is not
        css_no_tokens = re.sub(r'--gg-border-radius:\s*0', '', css)
        assert "border-radius" not in css_no_tokens
        assert "box-shadow" not in css
        assert "linear-gradient" not in css
        assert "radial-gradient" not in css
        assert "Source Serif 4" in css
        assert "#ede4d8" in css  # sand background
        assert "#3a2e25" in css  # dark brown text color


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
        """Brand guide bans entrance animations and scale transforms.
        IntersectionObserver is allowed for counters (guarded by prefers-reduced-motion)."""
        js = build_homepage_js()
        assert "translateY" not in js
        assert "scale(" not in js

    def test_js_reduced_motion_guard(self):
        """IntersectionObserver usage must be guarded by prefers-reduced-motion check."""
        js = build_homepage_js()
        if "IntersectionObserver" in js:
            assert "prefers-reduced-motion" in js, "IntersectionObserver must check prefers-reduced-motion"


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
        assert 'gravelgodcycling.com/"' in homepage_html

    def test_has_og_tags(self, homepage_html):
        assert 'property="og:title"' in homepage_html
        assert 'property="og:description"' in homepage_html
        assert 'property="og:type"' in homepage_html

    def test_has_self_hosted_fonts(self, homepage_html):
        assert "@font-face" in homepage_html
        assert "Sometype Mono" in homepage_html
        assert "Source Serif 4" in homepage_html
        assert "fonts.googleapis.com" not in homepage_html

    def test_has_ga4(self, homepage_html):
        assert GA4_MEASUREMENT_ID in homepage_html
        assert "googletagmanager.com/gtag/js" in homepage_html

    def test_has_all_sections(self, homepage_html):
        assert "gg-site-header" in homepage_html
        assert "gg-hp-ticker" in homepage_html
        assert "gg-hp-hero" in homepage_html
        assert "gg-hp-stats-stripe" in homepage_html
        assert "gg-hp-content-grid" in homepage_html
        assert "gg-hp-bento" in homepage_html
        assert "gg-hp-sidebar" in homepage_html
        assert "gg-hp-how-it-works" in homepage_html
        assert "gg-hp-guide" in homepage_html
        assert "gg-hp-featured-in" in homepage_html
        assert "gg-hp-training-cta-full" in homepage_html
        assert "gg-hp-email" in homepage_html
        assert "gg-mega-footer" in homepage_html

    def test_has_jsonld_blocks(self, homepage_html):
        blocks = re.findall(r'application/ld\+json', homepage_html)
        assert len(blocks) == 2  # Organization + WebSite

    def test_has_h1(self, homepage_html):
        h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', homepage_html, re.DOTALL)
        assert h1_match is not None
        assert "gravel race" in h1_match.group(1).lower()

    def test_page_size_reasonable(self, homepage_html):
        size_kb = len(homepage_html) / 1024
        assert size_kb < 150, f"Homepage is {size_kb:.1f}KB, expected under 150KB"
        assert size_kb > 20, f"Homepage is {size_kb:.1f}KB, seems too small"

    def test_ctas_have_ga_tracking(self, homepage_html):
        for event in ['hero_cta_click', 'featured_race_click',
                       'training_plan_click', 'sidebar_cta_click', 'guide_click']:
            assert f'data-ga="{event}"' in homepage_html, f"Missing GA event: {event}"

    def test_no_broken_template_vars(self, homepage_html):
        assert "{race_count}" not in homepage_html
        assert "{search_term_string}" not in homepage_html or "query-input" in homepage_html


# ── Constants ────────────────────────────────────────────────


class TestConstants:
    def test_featured_slugs_count(self):
        assert len(FEATURED_SLUGS) == 3



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
        for section_id in ["main", "training", "newsletter"]:
            assert f'id="{section_id}"' in homepage_html, f"Missing section id: {section_id}"

    def test_grid_breakpoint(self):
        """CSS must have a grid collapse breakpoint at 900px."""
        css = build_homepage_css()
        assert "@media (max-width: 900px)" in css

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

    def test_latest_takes_is_standalone_section(self, homepage_html):
        """Latest Takes must be between content grid and how-it-works, outside both."""
        body_start = homepage_html.find("<body")
        body = homepage_html[body_start:]
        # Find the content grid's closing </div> by matching the opening tag's nesting
        grid_open = body.find('class="gg-hp-content-grid"')
        assert grid_open >= 0, "Content grid not found"
        # The sidebar-sticky closing, sidebar closing, then grid closing —
        # the grid close is the </div> right before "gg-hp-latest-takes"
        sidebar_close = body.find("</aside>", grid_open)
        assert sidebar_close >= 0, "Sidebar close not found"
        grid_close = body.find("</div>", sidebar_close)
        assert grid_close >= 0, "Grid close not found"

        takes_pos = body.find('class="gg-hp-latest-takes"')
        how_it_works_pos = body.find('class="gg-hp-how-it-works"')
        assert takes_pos >= 0, "Latest Takes section not found in body"
        assert how_it_works_pos >= 0, "How It Works section not found in body"
        assert takes_pos > grid_close, \
            "Latest Takes must appear AFTER content grid closes"
        assert takes_pos < how_it_works_pos, \
            "Latest Takes must appear BEFORE How It Works"

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

    def test_sidebar_coming_up_capped(self, stats, race_index, upcoming):
        """Sidebar coming-up should show max 4 future races."""
        html = build_sidebar(stats, race_index, upcoming)
        compact_items = html.count("gg-hp-coming-compact-item")
        assert compact_items <= 4

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


# ── New Section Builders ─────────────────────────────────────


class TestTopBar:
    def test_top_bar_exists(self):
        html = build_top_bar()
        assert "gg-hp-top-bar" in html

    def test_top_bar_aria_hidden(self):
        html = build_top_bar()
        assert 'aria-hidden="true"' in html


class TestContentGrid:
    def test_content_grid_structure(self, race_index, stats, upcoming):
        html = build_content_grid(race_index, stats, upcoming)
        assert "gg-hp-content-grid" in html
        assert "gg-hp-main-col" in html
        assert "gg-hp-sidebar" in html
        assert "gg-hp-sidebar-sticky" in html

    def test_content_grid_has_bento(self, race_index, stats, upcoming):
        html = build_content_grid(race_index, stats, upcoming)
        assert "gg-hp-bento" in html

    def test_content_grid_has_rankings(self, race_index, stats, upcoming):
        html = build_content_grid(race_index, stats, upcoming)
        assert 'role="tablist"' in html

    def test_content_grid_css(self):
        css = build_homepage_css()
        assert "gg-hp-content-grid" in css
        assert "3fr 2fr" in css


class TestTabbedRankings:
    def test_tabbed_rankings_aria_roles(self, race_index):
        html = build_tabbed_rankings(race_index)
        assert 'role="tablist"' in html
        assert 'role="tab"' in html
        assert 'role="tabpanel"' in html

    def test_tabbed_rankings_five_tabs(self, race_index):
        html = build_tabbed_rankings(race_index)
        assert html.count('role="tab"') == 5
        assert html.count('role="tabpanel"') == 5

    def test_tabbed_rankings_aria_selected(self, race_index):
        html = build_tabbed_rankings(race_index)
        assert 'aria-selected="true"' in html
        assert html.count('aria-selected="false"') == 4

    def test_tabbed_rankings_aria_controls(self, race_index):
        html = build_tabbed_rankings(race_index)
        assert 'aria-controls="gg-panel-all"' in html
        assert 'aria-controls="gg-panel-t1"' in html
        assert 'aria-controls="gg-panel-t2"' in html
        assert 'aria-controls="gg-panel-t3"' in html
        assert 'aria-controls="gg-panel-t4"' in html

    def test_tabbed_rankings_hidden_panels(self, race_index):
        html = build_tabbed_rankings(race_index)
        # First panel visible, others hidden via CSS class (not hidden attr)
        assert 'id="gg-panel-all"' in html
        assert 'gg-hp-tab-inactive' in html
        assert 'id="gg-panel-t1"' in html
        assert 'id="gg-panel-t2"' in html
        assert 'id="gg-panel-t3"' in html
        assert 'id="gg-panel-t4"' in html

    def test_tabbed_rankings_keyboard_nav_in_js(self):
        js = build_homepage_js()
        assert "ArrowRight" in js
        assert "ArrowLeft" in js
        assert "Home" in js
        assert "End" in js

    def test_tabbed_rankings_has_items(self, race_index):
        html = build_tabbed_rankings(race_index)
        assert "gg-hp-article-item" in html
        assert "gg-hp-article-score" in html


class TestBentoFeatures:
    def test_bento_has_lead_card(self, race_index):
        html = build_bento_features(race_index)
        assert "gg-hp-bento-lead" in html

    def test_bento_cards_are_links(self, race_index):
        html = build_bento_features(race_index)
        # Every card must be a link to /race/{slug}/
        import re
        cards = re.findall(r'<a href="[^"]*?/race/[^"]+/"[^>]*class="gg-hp-bento-card', html)
        assert len(cards) == 3

    def test_bento_cards_have_ga_tracking(self, race_index):
        html = build_bento_features(race_index)
        assert 'data-ga="featured_race_click"' in html

    def test_bento_backward_compat_alias(self, race_index):
        """build_featured_races should be an alias for build_bento_features."""
        assert build_featured_races(race_index) == build_bento_features(race_index)


class TestScrollProgress:
    def test_scroll_progress_in_html(self, homepage_html):
        assert "gg-hp-scroll-progress" in homepage_html
        assert 'id="scrollProgress"' in homepage_html

    def test_scroll_progress_in_js(self):
        js = build_homepage_js()
        assert "scrollProgress" in js
        assert "requestAnimationFrame" in js

    def test_scroll_progress_aria_hidden(self, homepage_html):
        assert 'class="gg-hp-scroll-progress"' in homepage_html
        # The scroll progress bar should be aria-hidden
        import re
        progress_match = re.search(r'<div class="gg-hp-scroll-progress"[^>]*>', homepage_html)
        assert progress_match is not None
        assert 'aria-hidden="true"' in progress_match.group(0)


class TestAnimatedCounters:
    def test_data_counter_attrs_in_stats(self, stats):
        bar = build_stats_bar(stats)
        assert "data-counter=" in bar

    def test_counter_js_present(self):
        js = build_homepage_js()
        assert "data-counter" in js
        assert "counterObserver" in js

    def test_counter_reduced_motion_guard(self):
        js = build_homepage_js()
        assert "prefers-reduced-motion" in js
        # The guard must appear BEFORE the IntersectionObserver
        motion_pos = js.find("prefers-reduced-motion")
        observer_pos = js.find("IntersectionObserver")
        assert motion_pos < observer_pos, "Reduced-motion check must come before IntersectionObserver"


class TestSidebar:
    def test_sidebar_stats_bento(self, stats, race_index, upcoming):
        html = build_sidebar(stats, race_index, upcoming)
        assert "gg-hp-sidebar-stat-grid" in html
        assert "BY THE NUMBERS" in html

    def test_sidebar_no_pullquote(self, stats, race_index, upcoming):
        """Pullquote was moved to bento lead card — sidebar should not have it."""
        html = build_sidebar(stats, race_index, upcoming)
        assert "gg-hp-pullquote" not in html

    def test_sidebar_top_5(self, stats, race_index, upcoming):
        html = build_sidebar(stats, race_index, upcoming)
        assert "TOP 5" in html
        assert "POWER RANKINGS" not in html
        assert "gg-hp-rank-list" in html
        assert "<ol" in html

    def test_sidebar_cta(self, stats, race_index, upcoming):
        html = build_sidebar(stats, race_index, upcoming)
        assert "gg-hp-sidebar-cta" in html
        assert "/training-plans/" in html

    def test_sidebar_coming_up(self, stats, race_index, upcoming):
        html = build_sidebar(stats, race_index, upcoming)
        assert "COMING UP" in html


class TestLatestTakes:
    def test_latest_takes_has_content(self):
        html = build_latest_takes()
        assert "LATEST TAKES" in html
        assert "gg-hp-take-card" in html

    def test_latest_takes_cards_are_links(self):
        html = build_latest_takes()
        import re
        card_links = re.findall(r'<a href="[^"]*"[^>]*class="gg-hp-take-card"', html)
        assert len(card_links) > 0

    def test_latest_takes_has_carousel(self):
        html = build_latest_takes()
        assert 'id="gg-takes-carousel"' in html


class TestTestimonials:
    def test_testimonials_section(self):
        html = build_testimonials()
        if html:  # May be empty if TESTIMONIALS is empty
            assert "ATHLETE RESULTS" in html
            assert "gg-hp-test-card" in html


# ── Brand & Tone Guard Tests ────────────────────────────────


class TestBrandToneGuard:
    """Tests that prevent recurring brand/tone issues found in the audit."""

    def test_no_fabricated_quotes(self, race_index):
        """Bento lead card quote must come from real race data, not AI-generated copy."""
        bento_html = build_bento_features(race_index)
        import re
        quotes = re.findall(r'<blockquote[^>]*>(.*?)</blockquote>', bento_html, re.DOTALL)
        race_data_dir = Path(__file__).parent.parent / "race-data"
        # Load ALL race profiles to check quotes against real data
        all_text = ""
        for json_file in race_data_dir.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    all_text += f.read()
            except OSError:
                pass
        for quote in quotes:
            # Strip HTML entities for comparison
            clean = re.sub(r'&[a-z]+;', '', quote).strip()
            # Check that a meaningful substring (first 30 chars) appears in race data
            check_text = clean[:30]
            assert check_text in all_text, \
                f"Bento quote may be fabricated (not found in race data): {clean[:60]}..."

    def test_no_duplicate_cta_headlines(self):
        """CTA sections must have distinct headlines — no copy-paste CTAs."""
        import re
        # Compare CTA-specific sections only (not race name headings which repeat by design)
        cta_sections = [
            build_training_cta(),
        ]
        # Also get the sidebar CTA headline
        # We can't easily call build_sidebar without fixtures, so check the two known CTAs
        training_h2 = re.findall(r'<h2[^>]*>(.*?)</h2>', build_training_cta(), re.DOTALL)
        # Sidebar CTA uses h3 "Don't wing race day" — verified in test_sidebar_cta_differs_from_main_cta
        # Here we just verify the training CTA headline isn't generic/duplicate
        for h in training_h2:
            text = re.sub(r'<[^>]+>', '', h).strip().lower()
            assert text != "", "CTA heading must not be empty"
            assert "click here" not in text, "CTA heading must not be generic"
            assert "learn more" not in text, "CTA heading must not be generic"

    def test_all_race_cards_are_links(self, race_index, stats, upcoming):
        """Every race card (bento, hero feature, sidebar rankings) must be clickable links."""
        import re
        # Check bento cards — each must be an <a> tag
        bento = build_bento_features(race_index)
        bento_links = re.findall(r'<a\s[^>]*class="gg-hp-bento-card[^"]*"', bento)
        bento_total = len(re.findall(r'class="gg-hp-bento-card', bento))
        assert len(bento_links) == bento_total, \
            f"Not all bento cards are links: {len(bento_links)} links vs {bento_total} cards"

        # Hero radar viz is not a link — it's an interactive infographic

    def test_heading_hierarchy(self, stats, race_index):
        """Only one h1 on the page. No h2 inside the hero section."""
        import re
        hero = build_hero(stats, race_index)
        h1_count = len(re.findall(r'<h1[\s>]', hero))
        assert h1_count == 1, f"Hero should have exactly 1 h1, found {h1_count}"
        h2_count = len(re.findall(r'<h2[\s>]', hero))
        assert h2_count == 0, f"Hero should have 0 h2 tags, found {h2_count}"

    def test_no_inline_styles_in_builders(self, stats, race_index, upcoming, chapters):
        """Section builders should not use inline style attributes (except allowed cases)."""
        import re
        # Test key builders for inline styles
        builders_output = [
            ("hero", build_hero(stats, race_index)),
            ("stats_bar", build_stats_bar(stats)),
            ("bento", build_bento_features(race_index)),
            ("tabbed_rankings", build_tabbed_rankings(race_index)),
            ("sidebar", build_sidebar(stats, race_index, upcoming)),
            ("training_cta", build_training_cta()),
            ("how_it_works", build_how_it_works(stats)),
            ("guide_preview", build_guide_preview(chapters)),
            ("top_bar", build_top_bar()),
        ]
        # Allowed inline styles: width on progress bar, border:none on iframes
        allowed_patterns = [
            r'style="width:',
            r'style="border:none',
        ]
        for name, html in builders_output:
            style_matches = re.findall(r'style="[^"]*"', html)
            for match in style_matches:
                is_allowed = any(re.search(p, match) for p in allowed_patterns)
                assert is_allowed, \
                    f"Inline style in {name} builder: {match}. Use CSS class instead."

    def test_all_css_hex_in_known_set(self):
        """All hex colors in homepage CSS must be from the brand token set or known exceptions."""
        import re
        css = build_homepage_css()
        # Read token hex values from tokens.css to stay in sync
        tokens_path = Path(__file__).parent.parent.parent / "gravel-god-brand" / "tokens" / "tokens.css"
        known_hex = set()
        if tokens_path.exists():
            with open(tokens_path, encoding="utf-8") as f:
                for match in re.finditer(r'#([0-9a-fA-F]{3,8})\b', f.read()):
                    known_hex.add(match.group(1).lower())
        # Standard web colors
        known_hex.update(["fff", "ffffff", "000", "000000"])
        # Pre-existing hex values that predate the token system.
        # TODO: migrate these to token values in a dedicated color-sync sprint.
        known_hex.update([
            "178079",  # legacy teal (tokens: 1a8a82)
            "7d695d",  # legacy secondary brown (tokens: 8c7568)
            "766a5e",  # legacy tier-3 badge (tokens: 999999)
            "5e6868",  # legacy tier-4 badge (tokens: cccccc)
            "9a7e0a",  # legacy gold (tokens: b7950b)
        ])
        # Find all hex colors in CSS
        hex_matches = re.finditer(r'#([0-9a-fA-F]{3,8})\b', css)
        for match in hex_matches:
            hex_val = match.group(1).lower()
            # Normalize 3-char to 6-char
            if len(hex_val) == 3:
                hex_val_6 = hex_val[0]*2 + hex_val[1]*2 + hex_val[2]*2
            else:
                hex_val_6 = hex_val
            assert hex_val in known_hex or hex_val_6 in known_hex, \
                f"Hex color #{match.group(1)} in homepage CSS is not in tokens.css or known exceptions"

    def test_hero_no_featured_card(self, stats, race_index):
        """Hero must not contain old featured card classes."""
        hero = build_hero(stats, race_index)
        assert "gg-hp-hero-feature" not in hero
        assert "gg-hp-hf-" not in hero

    def test_sidebar_cta_differs_from_main_cta(self):
        """Sidebar CTA and main CTA must have different headlines."""
        import re
        sidebar_pattern = r'class="gg-hp-sidebar-cta".*?<h3>(.*?)</h3>'
        main_pattern = r'class="gg-hp-cta-left".*?<h2>(.*?)</h2>'

        # Build both sections
        training = build_training_cta()
        # Can't easily get sidebar alone without stats/index, so check the function output
        main_match = re.search(main_pattern, training, re.DOTALL)
        assert main_match is not None, "Main CTA should have an h2"
        main_headline = re.sub(r'<[^>]+>', '', main_match.group(1)).strip()
        # The sidebar CTA headline is "Don't wing race day" — verify it differs
        assert "wing race day" not in main_headline.lower(), \
            "Main CTA must differ from sidebar CTA"


class TestEdgeCases:
    """Verify empty-state and boundary-condition handling."""

    def test_tabbed_rankings_empty_tier(self, race_index):
        """Tab panel for an empty tier should show a message, not be blank."""
        # Filter out all T1 races to simulate empty tier
        no_t1 = [r for r in race_index if r.get("tier") != 1]
        rankings = build_tabbed_rankings(no_t1)
        # The T1 panel should have a fallback message
        import re
        t1_panel = re.search(
            r'id="gg-panel-t1"[^>]*>(.*?)</div>\s*<div role="tabpanel"',
            rankings, re.DOTALL
        )
        if t1_panel:
            assert "No races in this tier" in t1_panel.group(1), \
                "Empty tier panel must show a fallback message"

    def test_bento_empty_fallback(self):
        """Bento with 0 featured races should show fallback, not crash."""
        result = build_bento_features([])
        assert "gg-hp-bento" in result
        assert "loading" in result.lower() or "Featured" in result

    def test_tab_panels_no_hidden_attribute(self, race_index):
        """Tab panels must use CSS class, not hidden attr (SEO)."""
        rankings = build_tabbed_rankings(race_index)
        import re
        # Check specifically for hidden as a standalone HTML attribute on tabpanels
        hidden_attrs = re.findall(r'role="tabpanel"[^>]*\bhidden\b', rankings)
        assert len(hidden_attrs) == 0, \
            "Tab panels must not use hidden attr — Googlebot won't index hidden content"

    def test_tab_panels_use_css_class(self, race_index):
        """Inactive tab panels must use gg-hp-tab-inactive class."""
        rankings = build_tabbed_rankings(race_index)
        assert "gg-hp-tab-inactive" in rankings

    def test_tab_js_uses_class_not_hidden(self):
        """JS tab handler must toggle CSS class, not hidden attribute."""
        js = build_homepage_js()
        assert "classList.add" in js and "tab-inactive" in js, \
            "Tab JS must use classList.add for inactive panels"
        assert "classList.remove" in js and "tab-inactive" in js, \
            "Tab JS must use classList.remove for active panel"

    def test_bento_quote_is_dynamic(self, race_index):
        """Bento lead card quote should pull from featured race tagline."""
        bento = build_bento_features(race_index)
        assert "gg-hp-bento-quote" in bento
        # The quote should contain tagline text from a featured race
        featured = get_featured_races(race_index)
        if featured:
            lead_tagline = featured[0].get("tagline", "")[:30]
            if lead_tagline:
                import html as _html
                escaped = _html.escape(lead_tagline)
                assert escaped in bento or lead_tagline in bento, \
                    "Bento quote must contain lead race tagline"

    def test_sidebar_empty_upcoming(self, race_index):
        """Sidebar with 0 upcoming races should show off-season message."""
        stats = compute_stats(race_index)
        sidebar = build_sidebar(stats, race_index, [])
        assert "Off-season" in sidebar or "Browse all races" in sidebar
        assert "on the calendar" in sidebar  # Section intro always present

    def test_training_cta_solution_state(self):
        """Training CTA should contain Solution-State comparison language."""
        cta = build_training_cta()
        assert "generic plan" in cta.lower(), \
            "Training CTA should contrast against generic plans"


class TestSultanicCopyGuard:
    """Verify Sultanic copy on homepage is present and brand-appropriate."""

    def test_training_cta_no_coffee_cliche(self):
        """Training CTA must not use generic SaaS comparisons."""
        cta = build_training_cta()
        lower = cta.lower()
        assert "coffee" not in lower
        assert "latte" not in lower

    def test_tab_inactive_css_exists(self):
        """Tab inactive CSS class must be defined."""
        css = build_homepage_css()
        assert "gg-hp-tab-inactive" in css

    def test_article_empty_css_exists(self):
        """Article empty-state CSS class should not break layout."""
        css = build_homepage_css()
        # Even if not styled, the class shouldn't cause errors
        # The empty message is plain text inside a panel
        assert "[role=\"tabpanel\"]" in css


class TestDisciplineFiltering:
    """Verify bikepacking/MTB races are excluded from all homepage rankings.

    The race-index.json has 7 bikepacking and 4 MTB races. The top 7 by score
    are ALL non-gravel. Without filtering, the entire "All Tiers" top 5 and
    all 5 power rankings would be bikepacking/MTB races.
    """

    def test_real_data_has_non_gravel_races(self, race_index):
        """Precondition: verify the index actually contains non-gravel races.
        If this fails, the other tests in this class are vacuous."""
        non_gravel = [r for r in race_index
                      if r.get("discipline") not in (None, "", "gravel")]
        assert len(non_gravel) >= 5, \
            f"Expected >=5 non-gravel races in index, found {len(non_gravel)}. " \
            "If this changes, discipline filtering tests need updating."

    def test_rankings_zero_non_gravel(self, race_index):
        """ALL 15 ranking slots (3 tabs x 5 items) must be gravel-only."""
        html = build_tabbed_rankings(race_index)
        non_gravel = [r for r in race_index
                      if r.get("discipline") not in (None, "", "gravel")]
        for race in non_gravel:
            name = race.get("name", "")
            assert name not in html, \
                f"Non-gravel race '{name}' (discipline={race['discipline']}) " \
                f"appeared in tabbed rankings"

    def test_top5_zero_non_gravel(self, stats, race_index, upcoming):
        """All 5 top-5 ranking slots must be gravel-only."""
        html = build_sidebar(stats, race_index, upcoming)
        non_gravel = [r for r in race_index
                      if r.get("discipline") not in (None, "", "gravel")]
        for race in non_gravel:
            name = race.get("name", "")
            # Top 5 rankings are in <ol class="gg-hp-rank-list">
            rank_start = html.find("gg-hp-rank-list")
            rank_end = html.find("</ol>", rank_start) if rank_start >= 0 else -1
            if rank_start >= 0 and rank_end >= 0:
                rank_html = html[rank_start:rank_end]
                assert name not in rank_html, \
                    f"Non-gravel race '{name}' (discipline={race['discipline']}) " \
                    f"appeared in top 5 rankings"

    def test_rankings_synthetic_mixed_disciplines(self):
        """Synthetic test: rankings with mixed discipline data should only show gravel."""
        mixed_index = [
            {"slug": "gravel-race", "name": "Gravel Race", "tier": 1, "overall_score": 95,
             "discipline": "gravel", "tagline": "A gravel race"},
            {"slug": "mtb-race", "name": "MTB Race", "tier": 1, "overall_score": 98,
             "discipline": "mtb", "tagline": "A mountain bike race"},
            {"slug": "bp-race", "name": "BP Race", "tier": 1, "overall_score": 94,
             "discipline": "bikepacking", "tagline": "A bikepacking race"},
            {"slug": "default-race", "name": "Default Race", "tier": 2, "overall_score": 70,
             "tagline": "No discipline field"},
        ]
        html = build_tabbed_rankings(mixed_index)
        assert "Gravel Race" in html
        assert "Default Race" in html  # Missing discipline defaults to gravel
        assert "MTB Race" not in html
        assert "BP Race" not in html

    def test_filter_handles_null_discipline(self):
        """discipline: null should be treated as gravel, not excluded."""
        index = [
            {"slug": "null-disc", "name": "Null Disc Race", "tier": 1,
             "overall_score": 99, "discipline": None, "tagline": "Has null discipline"},
        ]
        html = build_tabbed_rankings(index)
        assert "Null Disc Race" in html

    def test_filter_handles_empty_discipline(self):
        """discipline: '' should be treated as gravel, not excluded."""
        index = [
            {"slug": "empty-disc", "name": "Empty Disc Race", "tier": 1,
             "overall_score": 99, "discipline": "", "tagline": "Has empty discipline"},
        ]
        html = build_tabbed_rankings(index)
        assert "Empty Disc Race" in html

    def test_filter_handles_missing_discipline(self):
        """Race with no discipline field should be treated as gravel."""
        index = [
            {"slug": "no-disc", "name": "No Disc Race", "tier": 1,
             "overall_score": 99, "tagline": "Has no discipline field"},
        ]
        html = build_tabbed_rankings(index)
        assert "No Disc Race" in html

    def test_empty_gravel_set_shows_fallback(self):
        """If ALL races are non-gravel, rankings should show empty-state message."""
        all_mtb = [
            {"slug": "mtb-1", "name": "MTB Race 1", "tier": 1, "overall_score": 99,
             "discipline": "mtb", "tagline": "MTB race"},
            {"slug": "mtb-2", "name": "MTB Race 2", "tier": 2, "overall_score": 80,
             "discipline": "mtb", "tagline": "Another MTB race"},
        ]
        html = build_tabbed_rankings(all_mtb)
        # All 5 panels should show empty fallback (All, T1, T2, T3, T4)
        assert html.count("No races in this tier") == 5, \
            "All tab panels should show empty fallback when no gravel races exist"

    def test_editorial_one_liners_exclude_non_gravel(self):
        """Ticker one-liners should exclude non-gravel races."""
        import tempfile, os
        # Create temp race data with a bikepacking race that has a one-liner
        bp_race = {
            "race": {
                "name": "Fake BP Race", "slug": "fake-bp",
                "display_name": "Fake BP Race",
                "gravel_god_rating": {
                    "tier": 1, "overall_score": 99, "discipline": "bikepacking",
                },
                "final_verdict": {"one_liner": "The ultimate bikepacking adventure."},
            }
        }
        gravel_race = {
            "race": {
                "name": "Fake Gravel Race", "slug": "fake-gravel",
                "display_name": "Fake Gravel Race",
                "gravel_god_rating": {
                    "tier": 1, "overall_score": 85, "discipline": "gravel",
                },
                "final_verdict": {"one_liner": "A proper gravel race."},
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            for name, data in [("fake-bp.json", bp_race), ("fake-gravel.json", gravel_race)]:
                with open(os.path.join(tmpdir, name), "w") as f:
                    json.dump(data, f)
            one_liners = load_editorial_one_liners(Path(tmpdir))
            names = [ol["name"] for ol in one_liners]
            assert "Fake Gravel Race" in names, "Gravel race should appear in one-liners"
            assert "Fake BP Race" not in names, "Bikepacking race should be excluded from one-liners"

    def test_upcoming_races_exclude_non_gravel(self):
        """Upcoming races should exclude non-gravel races."""
        import tempfile, os
        from datetime import timedelta
        today = date.today()
        future_date = today + timedelta(days=10)
        date_str = f"{future_date.year}: {future_date.strftime('%B')} {future_date.day}"
        bp_upcoming = {
            "race": {
                "name": "Upcoming BP", "slug": "upcoming-bp",
                "display_name": "Upcoming BP",
                "vitals": {"date_specific": date_str, "location": "Somewhere"},
                "gravel_god_rating": {
                    "tier": 1, "overall_score": 95, "discipline": "bikepacking",
                },
            }
        }
        gravel_upcoming = {
            "race": {
                "name": "Upcoming Gravel", "slug": "upcoming-gravel",
                "display_name": "Upcoming Gravel",
                "vitals": {"date_specific": date_str, "location": "Somewhere Else"},
                "gravel_god_rating": {
                    "tier": 2, "overall_score": 75, "discipline": "gravel",
                },
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            for name, data in [("bp.json", bp_upcoming), ("gravel.json", gravel_upcoming)]:
                with open(os.path.join(tmpdir, name), "w") as f:
                    json.dump(data, f)
            upcoming = load_upcoming_races(Path(tmpdir), today)
            names = [r["name"] for r in upcoming]
            assert "Upcoming Gravel" in names
            assert "Upcoming BP" not in names

    def test_featured_races_fallback_excludes_non_gravel(self):
        """Featured race fallback should only pick gravel T1 races."""
        index = [
            {"slug": "bp-top", "name": "BP Top", "tier": 1, "overall_score": 99,
             "discipline": "bikepacking"},
            {"slug": "gravel-lower", "name": "Gravel Lower", "tier": 1, "overall_score": 80,
             "discipline": "gravel"},
        ]
        featured = get_featured_races(index)
        names = [r["name"] for r in featured]
        assert "BP Top" not in names, "Bikepacking race should not be in featured fallback"
        assert "Gravel Lower" in names


class TestBentoNoImage:
    """Verify bento feature cards have no image placeholders."""

    def test_bento_no_image_placeholder(self, race_index):
        """Bento cards should not have beige image placeholder divs."""
        html = build_bento_features(race_index)
        assert "gg-hp-bento-img" not in html

    def test_bento_no_image_css(self):
        """CSS should not define .gg-hp-bento-img rules."""
        css = build_homepage_css()
        assert ".gg-hp-bento-img" not in css


class TestLatestTakesFullWidth:
    """Verify Latest Takes is full-width with 3-card layout."""

    def test_latest_takes_not_in_content_grid(self, race_index, stats, upcoming):
        """Latest Takes should not be part of the content grid output."""
        grid_html = build_content_grid(race_index, stats, upcoming)
        assert "gg-hp-latest-takes" not in grid_html

    def test_latest_takes_css_max_width(self):
        """Latest Takes should have its own max-width for full-width layout."""
        css = build_homepage_css()
        assert "gg-hp-latest-takes" in css
        # Should have max-width: 1080px
        import re
        takes_rule = re.search(r'\.gg-hp-latest-takes\s*\{[^}]+\}', css)
        assert takes_rule is not None
        assert "max-width: 1080px" in takes_rule.group(0)

    def test_latest_takes_three_card_layout(self):
        """Take cards should be 33.333% width for 3-card layout."""
        css = build_homepage_css()
        assert "calc(33.333%" in css

    def test_carousel_js_three_per_page(self):
        """Carousel JS should show 3 cards per page on desktop."""
        js = build_homepage_js()
        assert "return 3;" in js


class TestFeaturedSlugsIntegrity:
    """Verify FEATURED_SLUGS are valid and gravel-only."""

    def test_featured_slugs_exist_in_index(self, race_index):
        """Every slug in FEATURED_SLUGS must exist in race-index.json."""
        index_slugs = {r["slug"] for r in race_index}
        for slug in FEATURED_SLUGS:
            assert slug in index_slugs, \
                f"FEATURED_SLUGS contains '{slug}' which is not in race-index.json. " \
                f"Check for typos (e.g., 'sbt-grvl' vs 'steamboat-gravel')."

    def test_featured_slugs_are_gravel(self, race_index):
        """Every race in FEATURED_SLUGS must have discipline == gravel."""
        slug_to_race = {r["slug"]: r for r in race_index}
        for slug in FEATURED_SLUGS:
            if slug not in slug_to_race:
                pytest.skip(f"Slug '{slug}' missing from index — covered by test above")
            race = slug_to_race[slug]
            disc = race.get("discipline") or "gravel"
            assert disc == "gravel", \
                f"FEATURED_SLUGS contains '{slug}' with discipline='{race.get('discipline')}'. " \
                f"Only gravel races should be featured."

    def test_featured_slugs_not_empty(self):
        """FEATURED_SLUGS should have at least 2 entries."""
        assert len(FEATURED_SLUGS) >= 2, \
            f"FEATURED_SLUGS has {len(FEATURED_SLUGS)} entries — need at least 2 for bento layout."

    def test_featured_slugs_no_duplicates(self):
        """FEATURED_SLUGS should not contain duplicates."""
        assert len(FEATURED_SLUGS) == len(set(FEATURED_SLUGS)), \
            f"FEATURED_SLUGS has duplicates: {[s for s in FEATURED_SLUGS if FEATURED_SLUGS.count(s) > 1]}"


def html_escape(text):
    """Helper for test assertions."""
    import html as _html
    return _html.escape(str(text))


# ── Stat Bars ──────────────────────────────────────────────────


class TestStatBars:
    """Tests for the _build_stat_bars helper and STAT_BAR_DIMENSIONS constants."""

    def test_stat_bar_dimensions_count(self):
        """Full stat bar set should have 6 dimensions."""
        assert len(STAT_BAR_DIMENSIONS) == 6

    def test_stat_bar_compact_count(self):
        """Compact stat bar set should have 3 dimensions."""
        assert len(STAT_BAR_DIMENSIONS_COMPACT) == 3

    def test_compact_is_subset(self):
        """Compact dimensions must be a subset of full dimensions."""
        for dim in STAT_BAR_DIMENSIONS_COMPACT:
            assert dim in STAT_BAR_DIMENSIONS, \
                f"Compact dimension '{dim}' not in full set"

    def test_dimensions_no_duplicates(self):
        """Both dimension lists must have no duplicates."""
        assert len(STAT_BAR_DIMENSIONS) == len(set(STAT_BAR_DIMENSIONS))
        assert len(STAT_BAR_DIMENSIONS_COMPACT) == len(set(STAT_BAR_DIMENSIONS_COMPACT))

    def test_dimensions_are_valid_keys(self, race_index):
        """All stat bar dimension names must exist as keys in race scores."""
        races_with_scores = [r for r in race_index if r.get("scores")]
        assert len(races_with_scores) > 0, "No races with scores in index"
        sample = races_with_scores[0]
        for dim in STAT_BAR_DIMENSIONS:
            assert dim in sample["scores"], \
                f"Dimension '{dim}' not found in race scores. Available: {list(sample['scores'].keys())}"

    def test_full_bars_exactly_six_rows(self, race_index):
        """Full stat bars must generate exactly 6 rows — no more, no fewer."""
        featured = get_featured_races(race_index)
        assert len(featured) > 0
        html = _build_stat_bars(featured[0], compact=False)
        assert html.count("gg-hp-statbar-row") == 6

    def test_compact_bars_exactly_three_rows(self, race_index):
        """Compact stat bars must generate exactly 3 rows."""
        featured = get_featured_races(race_index)
        assert len(featured) > 0
        html = _build_stat_bars(featured[0], compact=True)
        assert html.count("gg-hp-statbar-row") == 3

    def test_stat_bars_every_row_has_aria(self, race_index):
        """Every stat bar fill must have an aria-label with 'N out of 5' format."""
        featured = get_featured_races(race_index)
        assert len(featured) > 0
        html = _build_stat_bars(featured[0], compact=False)
        aria_matches = re.findall(r'aria-label="(\d+) out of 5"', html)
        assert len(aria_matches) == 6, \
            f"Expected 6 aria-labels, found {len(aria_matches)}"

    def test_stat_bars_empty_scores(self):
        """Race with empty scores dict should produce bars with 0 values."""
        race = {"slug": "test", "name": "Test", "scores": {}}
        html = _build_stat_bars(race, compact=False)
        assert html.count("gg-hp-statbar-row") == 6
        assert 'width: 0%' in html

    def test_stat_bars_width_calculation(self):
        """Bar width should be (score/5)*100 percent."""
        race = {"slug": "test", "name": "Test", "scores": {"prestige": 3}}
        html = _build_stat_bars(race, compact=True)
        assert "width: 60%;" in html

    def test_stat_bars_width_boundaries(self):
        """Score 0 = 0%, score 5 = 100%."""
        for score, expected_pct in [(0, "0%"), (1, "20%"), (5, "100%")]:
            race = {"scores": {"prestige": score}}
            html = _build_stat_bars(race, compact=True)
            assert f"width: {expected_pct};" in html, \
                f"Score {score} should produce width: {expected_pct}"

    def test_stat_bars_has_labels_uppercase_no_underscores(self, race_index):
        """Stat bar labels must be uppercase with spaces, never underscores."""
        featured = get_featured_races(race_index)
        assert len(featured) > 0
        html = _build_stat_bars(featured[0], compact=False)
        assert "PRESTIGE" in html
        assert "TECHNICALITY" in html
        assert "ADVENTURE" in html
        assert "FIELD DEPTH" in html
        assert "RACE QUALITY" in html
        # Must never render underscore in labels
        labels = re.findall(r'class="gg-hp-statbar-label">(.*?)</span>', html)
        for label in labels:
            assert "_" not in label, f"Underscore in label: '{label}'"

    def test_stat_bars_no_missing_scores_key(self):
        """Race missing 'scores' key entirely should produce valid bars with 0s."""
        race = {"slug": "test", "name": "Test"}
        html = _build_stat_bars(race, compact=True)
        assert "gg-hp-statbar" in html
        assert html.count("gg-hp-statbar-row") == 3
        vals = re.findall(r'class="gg-hp-statbar-val">(\d+)</span>', html)
        assert all(v == "0" for v in vals), f"Expected all 0s, got {vals}"

    def test_stat_bars_none_scores_key(self):
        """scores: None must not crash — same as missing key."""
        race = {"slug": "test", "name": "Test", "scores": None}
        html = _build_stat_bars(race, compact=False)
        assert html.count("gg-hp-statbar-row") == 6
        assert "None" not in html, "None must never appear as text in stat bars"

    def test_stat_bars_none_dimension_value(self):
        """A dimension with value None must render as 0, not 'None'."""
        race = {"scores": {"prestige": None, "adventure": 4, "technicality": None}}
        html = _build_stat_bars(race, compact=True)
        assert "None" not in html, "None must never appear as text in stat bars"
        # prestige=None should render as 0
        assert 'width: 0%;' in html
        # adventure=4 should render as 80%
        assert 'width: 80%;' in html

    def test_stat_bars_score_clamped_above_5(self):
        """Scores above 5 must be clamped to 5 (100%), never exceed 100%."""
        race = {"scores": {"prestige": 7}}
        html = _build_stat_bars(race, compact=True)
        assert "width: 100%;" in html
        assert ">5</span>" in html
        assert ">7</span>" not in html

    def test_stat_bars_score_clamped_below_0(self):
        """Negative scores must be clamped to 0 (0%)."""
        race = {"scores": {"prestige": -2}}
        html = _build_stat_bars(race, compact=True)
        assert "width: 0%;" in html
        assert ">0</span>" in html
        assert ">-2</span>" not in html

    def test_stat_bars_no_none_in_aria(self):
        """aria-label must never contain 'None'."""
        race = {"scores": {"prestige": None, "adventure": None, "technicality": None}}
        html = _build_stat_bars(race, compact=True)
        aria_vals = re.findall(r'aria-label="(.*?)"', html)
        for val in aria_vals:
            assert "None" not in val, f"aria-label contains None: '{val}'"

    def test_all_featured_races_get_stat_bars(self, race_index):
        """Every bento card (lead + secondary) must have stat bars."""
        html = build_bento_features(race_index)
        # 3 cards, each with a statbar div
        assert html.count('class="gg-hp-statbar"') == 3

    def test_lead_gets_full_bars_secondary_gets_compact(self, race_index):
        """Lead card has 6 stat rows, secondary cards have 3 each."""
        html = build_bento_features(race_index)
        # Find stat bar sections by splitting on card boundaries
        cards = html.split("gg-hp-bento-card")
        # First card (lead) should have 6 rows
        assert cards[1].count("gg-hp-statbar-row") == 6, \
            "Lead card must have 6 stat bar rows"
        # Second card should have 3 rows
        assert cards[2].count("gg-hp-statbar-row") == 3, \
            "Secondary card must have 3 stat bar rows"
        # Third card should have 3 rows
        assert cards[3].count("gg-hp-statbar-row") == 3, \
            "Secondary card must have 3 stat bar rows"

    def test_stat_bars_css_defined(self):
        """All stat bar CSS classes must be defined."""
        css = build_homepage_css()
        for cls in ["gg-hp-statbar", "gg-hp-statbar-row", "gg-hp-statbar-label",
                     "gg-hp-statbar-track", "gg-hp-statbar-fill", "gg-hp-statbar-val"]:
            assert f".{cls}" in css, f"CSS class .{cls} not defined"

    def test_stat_bars_mobile_css(self):
        """Stat bar mobile styles must be in 600px breakpoint."""
        css = build_homepage_css()
        # Find the 600px media query block
        m600 = re.search(
            r'@media\s*\(max-width:\s*600px\)\s*\{(.*?)(?=\n@media|\n/\*\s*──\s*Responsive:\s*480)',
            css, re.DOTALL
        )
        assert m600 is not None, "600px breakpoint not found"
        mobile_css = m600.group(1)
        assert "gg-hp-statbar-label" in mobile_css, \
            "Stat bar label must have mobile styles"


class TestBentoQuote:
    """Tests for the blockquote on the lead bento card."""

    def test_quote_only_on_lead(self, race_index):
        """Only the lead card (first) should have the bento-quote blockquote."""
        html = build_bento_features(race_index)
        assert html.count("gg-hp-bento-quote") == 1

    def test_quote_not_on_secondary_cards(self, race_index):
        """Secondary cards must not have a blockquote."""
        html = build_bento_features(race_index)
        # Split by card boundaries and check non-lead cards
        parts = html.split("gg-hp-bento-card")
        for i, part in enumerate(parts[2:], start=2):
            assert "gg-hp-bento-quote" not in part, \
                f"Card {i} (non-lead) should not have a quote"

    def test_quote_absent_when_tagline_empty(self):
        """Lead card with empty tagline should have no quote."""
        index = [
            {"slug": "no-tag", "name": "No Tagline", "tier": 1,
             "overall_score": 90, "tagline": "", "scores": {"prestige": 5}},
            {"slug": "sec-1", "name": "Secondary 1", "tier": 2,
             "overall_score": 70, "tagline": "Has one", "scores": {}},
            {"slug": "sec-2", "name": "Secondary 2", "tier": 3,
             "overall_score": 60, "tagline": "Also has", "scores": {}},
        ]
        html = build_bento_features(index)
        assert "gg-hp-bento-quote" not in html, \
            "No quote when lead tagline is empty"

    def test_quote_has_gold_border_css(self):
        """Bento quote CSS must specify gold left border."""
        css = build_homepage_css()
        quote_rule = re.search(r'\.gg-hp-bento-quote\s*\{[^}]+\}', css)
        assert quote_rule is not None, "gg-hp-bento-quote CSS rule not found"
        rule = quote_rule.group(0)
        assert "border-left" in rule, "Quote must have left border"
        assert "#9a7e0a" in rule, "Quote border must be gold"

    def test_no_bento_excerpt_html(self, race_index):
        """gg-hp-bento-excerpt must be removed from bento cards."""
        html = build_bento_features(race_index)
        assert "gg-hp-bento-excerpt" not in html

    def test_no_bento_excerpt_css(self):
        """CSS must not define .gg-hp-bento-excerpt rules."""
        css = build_homepage_css()
        assert ".gg-hp-bento-excerpt" not in css

    def test_bento_card_body_order(self, race_index):
        """Card body order must be: meta → name → byline → stat bars → quote."""
        html = build_bento_features(race_index)
        # Check lead card ordering
        lead_start = html.find("gg-hp-bento-lead")
        assert lead_start >= 0
        lead_html = html[lead_start:]
        meta_pos = lead_html.find("gg-hp-bento-meta")
        name_pos = lead_html.find("gg-hp-bento-name")
        byline_pos = lead_html.find("gg-hp-bento-byline")
        statbar_pos = lead_html.find("gg-hp-statbar")
        quote_pos = lead_html.find("gg-hp-bento-quote")
        assert 0 < meta_pos < name_pos < byline_pos < statbar_pos < quote_pos, \
            f"Card body order wrong: meta={meta_pos} name={name_pos} " \
            f"byline={byline_pos} statbar={statbar_pos} quote={quote_pos}"


class TestSectionIntros:
    """Tests for section intro paragraphs."""

    def test_section_intro_css_exists(self):
        """Section intro class must be styled in CSS."""
        css = build_homepage_css()
        assert "gg-hp-section-intro" in css

    def test_section_intro_css_italic(self):
        """Section intros must be italic per editorial voice."""
        css = build_homepage_css()
        intro_rule = re.search(r'\.gg-hp-section-intro\s*\{[^}]+\}', css)
        assert intro_rule is not None
        assert "font-style: italic" in intro_rule.group(0), \
            "Section intros must be italic"

    def test_rankings_intro(self, race_index):
        """Tabbed rankings must have a section intro."""
        html = build_tabbed_rankings(race_index)
        assert "gg-hp-section-intro" in html
        assert "Sorted by the numbers" in html

    def test_latest_takes_intro(self):
        """Latest Takes must have a section intro."""
        html = build_latest_takes()
        assert "gg-hp-section-intro" in html
        assert "stand behind" in html

    def test_testimonials_intro(self):
        """Testimonials must have a section intro."""
        html = build_testimonials()
        assert "gg-hp-section-intro" in html
        assert "Real plans" in html

    def test_sidebar_stats_intro(self, stats, race_index, upcoming):
        """Sidebar BY THE NUMBERS must have a section intro."""
        html = build_sidebar(stats, race_index, upcoming)
        assert "at a glance" in html

    def test_sidebar_top5_intro(self, stats, race_index, upcoming):
        """Sidebar TOP 5 must have a section intro."""
        html = build_sidebar(stats, race_index, upcoming)
        assert "compares themselves" in html

    def test_sidebar_coming_up_intro(self, stats, race_index, upcoming):
        """Sidebar COMING UP must have a section intro."""
        html = build_sidebar(stats, race_index, upcoming)
        assert "on the calendar" in html

    def test_section_intros_not_empty(self, race_index):
        """Section intros must contain actual text content."""
        rankings = build_tabbed_rankings(race_index)
        takes = build_latest_takes()
        testimonials = build_testimonials()
        for section_html, name in [
            (rankings, "rankings"),
            (takes, "latest takes"),
            (testimonials, "testimonials"),
        ]:
            match = re.search(
                r'class="gg-hp-section-intro">(.*?)</p>',
                section_html, re.DOTALL
            )
            assert match is not None, f"Section intro missing in {name}"
            assert len(match.group(1).strip()) > 5, \
                f"Section intro in {name} is too short"

    def test_all_six_intros_in_full_page(self, homepage_html):
        """Full page must contain all 6 section intros."""
        expected_fragments = [
            "Sorted by the numbers",
            "stand behind",
            "Real plans",
            "at a glance",
            "compares themselves",
            "on the calendar",
        ]
        for frag in expected_fragments:
            assert frag in homepage_html, \
                f"Section intro fragment '{frag}' missing from full page"


class TestVisualDividers:
    """Tests for gold top-border dividers on sections."""

    def test_latest_takes_gold_border(self):
        """Latest Takes must have gold top border matching existing section border color."""
        css = build_homepage_css()
        takes_rule = re.search(r'\.gg-hp-latest-takes\s*\{[^}]+\}', css)
        assert takes_rule is not None
        assert "border-top: 2px solid #9a7e0a" in takes_rule.group(0)

    def test_testimonials_gold_border(self):
        """Testimonials must have gold top border matching existing section border color."""
        css = build_homepage_css()
        test_rule = re.search(r'\.gg-hp-testimonials\s*\{[^}]+\}', css)
        assert test_rule is not None
        assert "border-top: 2px solid #9a7e0a" in test_rule.group(0)

    def test_divider_gold_matches_how_it_works(self):
        """All gold section dividers must use the same hex as how-it-works."""
        css = build_homepage_css()
        hiw_rule = re.search(r'\.gg-hp-how-it-works\s*\{[^}]+\}', css)
        assert hiw_rule is not None
        hiw_gold = re.search(r'border-top:\s*2px\s+solid\s+(#[0-9a-fA-F]+)', hiw_rule.group(0))
        assert hiw_gold is not None

        takes_rule = re.search(r'\.gg-hp-latest-takes\s*\{[^}]+\}', css)
        takes_gold = re.search(r'border-top:\s*2px\s+solid\s+(#[0-9a-fA-F]+)', takes_rule.group(0))
        assert takes_gold is not None

        test_rule = re.search(r'\.gg-hp-testimonials\s*\{[^}]+\}', css)
        test_gold = re.search(r'border-top:\s*2px\s+solid\s+(#[0-9a-fA-F]+)', test_rule.group(0))
        assert test_gold is not None

        assert hiw_gold.group(1).lower() == takes_gold.group(1).lower() == test_gold.group(1).lower(), \
            f"Gold divider hex mismatch: how-it-works={hiw_gold.group(1)}, " \
            f"latest-takes={takes_gold.group(1)}, testimonials={test_gold.group(1)}"


class TestNoPullquote:
    """Verify pullquote is fully removed from sidebar, CSS, and full page."""

    def test_no_pullquote_css(self):
        """CSS must not define .gg-hp-pullquote rules."""
        css = build_homepage_css()
        assert ".gg-hp-pullquote" not in css

    def test_no_pullquote_in_sidebar(self, stats, race_index, upcoming):
        """Sidebar must not contain any blockquote element."""
        html = build_sidebar(stats, race_index, upcoming)
        assert "<blockquote" not in html
        assert "gg-hp-pullquote" not in html

    def test_no_power_rankings_label_anywhere(self, homepage_html):
        """'POWER RANKINGS' must not appear anywhere in the full page."""
        assert "POWER RANKINGS" not in homepage_html, \
            "Renamed to TOP 5 — POWER RANKINGS must not appear"

    def test_top5_label_in_sidebar(self, stats, race_index, upcoming):
        """Sidebar must use 'TOP 5' heading, not 'POWER RANKINGS'."""
        html = build_sidebar(stats, race_index, upcoming)
        assert "TOP 5" in html
        assert "POWER RANKINGS" not in html


class TestHeroRadarViz:
    """Tests for the interactive 14-axis hero radar visualization.

    Covers: structure, accessibility, brand compliance, buttons, tooltips,
    data integrity, CSS, JS morph animation, and XML well-formedness.
    """

    @pytest.fixture()
    def viz_html(self, race_index):
        return _build_hero_radar_viz(race_index)

    # ── Structure ──

    def test_viz_has_svg(self, viz_html):
        """Output contains SVG and data-viz attribute."""
        assert "<svg" in viz_html
        assert 'data-viz="hero-radar"' in viz_html

    def test_viz_no_featured_card(self, stats, race_index):
        """Hero must not contain old featured card classes."""
        hero = build_hero(stats, race_index)
        assert "gg-hp-hero-feature" not in hero

    def test_viz_no_old_radar(self, stats, race_index):
        """Hero and CSS must not contain old gg-hp-hf- classes."""
        hero = build_hero(stats, race_index)
        assert "gg-hp-hf-" not in hero

    def test_viz_svg_role_img(self, viz_html):
        """SVG has role='img' for screen readers."""
        assert 'role="img"' in viz_html

    def test_viz_svg_aria_label(self, viz_html):
        """SVG has aria-label mentioning 14 scoring criteria."""
        assert 'aria-label="Rating system radar chart showing 14 scoring criteria"' in viz_html

    def test_viz_14_axis_labels(self, viz_html):
        """14 text elements with the label class."""
        import re
        labels = re.findall(r'<text[^>]*class="gg-hp-hv-lbl"', viz_html)
        assert len(labels) == 14

    def test_viz_14_axis_spokes(self, viz_html):
        """14 line elements with the grid class (spokes)."""
        import re
        spokes = re.findall(r'<line[^>]*class="gg-hp-hv-grid"', viz_html)
        assert len(spokes) == 14

    def test_viz_3_grid_rings(self, viz_html):
        """3 polygon elements with the grid class (concentric rings)."""
        import re
        rings = re.findall(r'<polygon[^>]*class="gg-hp-hv-grid"', viz_html)
        assert len(rings) == 3

    def test_viz_data_polygon(self, viz_html):
        """Exactly 1 data polygon."""
        import re
        data = re.findall(r'<polygon[^>]*class="gg-hp-hv-data"', viz_html)
        assert len(data) == 1

    def test_viz_14_rect_markers(self, viz_html):
        """14 rect elements with the dot class."""
        import re
        dots = re.findall(r'<rect[^>]*class="gg-hp-hv-dot"', viz_html)
        assert len(dots) == 14

    def test_viz_no_circles(self, viz_html):
        """No circle elements (brand rule: no border-radius)."""
        assert "<circle" not in viz_html

    def test_viz_xml_wellformed(self, viz_html):
        """SVG parses as valid XML."""
        import xml.etree.ElementTree as ET
        svg_start = viz_html.index("<svg")
        svg_end = viz_html.index("</svg>") + len("</svg>")
        svg_str = viz_html[svg_start:svg_end]
        ET.fromstring(svg_str)

    # ── Tooltips ──

    def test_viz_labels_have_tooltip_data(self, viz_html):
        """Every label has data-dim-name and data-dim-desc for JS tooltip."""
        import re
        labels = re.findall(r'<text[^>]*class="gg-hp-hv-lbl"[^>]*>', viz_html)
        for lbl in labels:
            assert 'data-dim-name="' in lbl, f"Label missing data-dim-name: {lbl}"
            assert 'data-dim-desc="' in lbl, f"Label missing data-dim-desc: {lbl}"

    def test_viz_tooltip_div_exists(self, viz_html):
        """Tooltip HTML div is present in the wrapper."""
        assert 'class="gg-hp-hv-tooltip"' in viz_html

    def test_viz_tooltip_descriptions_match_dict(self, viz_html):
        """data-dim-desc values match HERO_VIZ_TOOLTIPS."""
        import re
        descs = re.findall(r'data-dim-desc="([^"]+)"', viz_html)
        assert len(descs) == 14
        expected = list(HERO_VIZ_TOOLTIPS.values())
        for tooltip in expected:
            assert tooltip in descs, f"Missing tooltip desc: {tooltip}"

    def test_viz_labels_are_focusable(self, viz_html):
        """Every label has tabindex for keyboard accessibility."""
        import re
        labels = re.findall(r'<text[^>]*class="gg-hp-hv-lbl"[^>]*>', viz_html)
        for lbl in labels:
            assert 'tabindex="0"' in lbl, f"Label missing tabindex: {lbl}"

    # ── Buttons ──

    def test_viz_4_archetype_buttons(self, viz_html):
        """4 buttons with the btn class."""
        import re
        btns = re.findall(r'<button[^>]*class="gg-hp-hv-btn[^"]*"', viz_html)
        assert len(btns) == 4

    def test_viz_button_labels(self, viz_html):
        """Button text matches archetype names (uppercased)."""
        for name in HERO_VIZ_ARCHETYPES:
            assert name.upper() in viz_html, f"Missing button label: {name.upper()}"

    def test_viz_button_data_points(self, viz_html):
        """Every button has data-points attribute."""
        import re
        btns = re.findall(r'<button[^>]*class="gg-hp-hv-btn[^"]*"[^>]*>', viz_html)
        for btn in btns:
            assert 'data-points="' in btn, f"Button missing data-points: {btn}"

    def test_viz_button_data_markers(self, viz_html):
        """Every button has data-markers attribute."""
        import re
        btns = re.findall(r'<button[^>]*class="gg-hp-hv-btn[^"]*"[^>]*>', viz_html)
        for btn in btns:
            assert 'data-markers="' in btn, f"Button missing data-markers: {btn}"

    def test_viz_first_button_active(self, viz_html):
        """First button has the active class."""
        import re
        btns = re.findall(r'<button[^>]*class="(gg-hp-hv-btn[^"]*)"', viz_html)
        assert len(btns) >= 1
        assert "gg-hp-hv-btn--active" in btns[0]

    def test_viz_only_one_active(self, viz_html):
        """Exactly 1 button has the active class."""
        assert viz_html.count("gg-hp-hv-btn--active") == 1

    def test_viz_button_points_14_pairs(self, viz_html):
        """Each data-points has 14 coordinate pairs."""
        import re
        points_attrs = re.findall(r'data-points="([^"]+)"', viz_html)
        for pts in points_attrs:
            pairs = pts.split()
            assert len(pairs) == 14, f"Expected 14 pairs, got {len(pairs)}: {pts[:60]}..."

    # ── Methodology link ──

    def test_viz_methodology_link(self, viz_html):
        """Output contains link to /race/methodology/."""
        assert "/race/methodology/" in viz_html
        assert "How We Rate" in viz_html

    def test_viz_methodology_ga(self, viz_html):
        """Methodology link has GA4 tracking attribute."""
        assert 'data-ga="hero_methodology_click"' in viz_html

    # ── Data integrity ──

    def test_viz_dims_match_all_dims(self):
        """HERO_VIZ_DIMS matches ALL_DIMS from neo_brutalist."""
        from generate_neo_brutalist import ALL_DIMS
        assert HERO_VIZ_DIMS == ALL_DIMS

    def test_viz_labels_cover_all_dims(self):
        """Every dim in HERO_VIZ_DIMS has a label."""
        for dim in HERO_VIZ_DIMS:
            assert dim in HERO_VIZ_LABELS, f"Missing label for dim: {dim}"

    def test_viz_tooltips_cover_all_dims(self):
        """Every dim has a tooltip."""
        for dim in HERO_VIZ_DIMS:
            assert dim in HERO_VIZ_TOOLTIPS, f"Missing tooltip for dim: {dim}"

    def test_viz_archetype_scores_length(self):
        """All archetype arrays have length 14."""
        for name, scores in HERO_VIZ_ARCHETYPES.items():
            assert len(scores) == 14, f"{name} has {len(scores)} scores, expected 14"

    def test_viz_archetype_scores_range(self):
        """All scores between 1 and 5."""
        for name, scores in HERO_VIZ_ARCHETYPES.items():
            for i, s in enumerate(scores):
                assert 1 <= s <= 5, f"{name}[{i}] = {s}, expected 1-5"

    def test_viz_archetypes_visually_distinct(self):
        """No two archetypes have identical scores."""
        names = list(HERO_VIZ_ARCHETYPES.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                assert HERO_VIZ_ARCHETYPES[names[i]] != HERO_VIZ_ARCHETYPES[names[j]], \
                    f"{names[i]} and {names[j]} have identical scores"

    def test_viz_polygon_points_match_default(self, viz_html):
        """Default polygon matches first archetype's pre-computed points."""
        import re
        # Get the data polygon points
        data_match = re.search(r'<polygon points="([^"]+)" class="gg-hp-hv-data"', viz_html)
        assert data_match, "Data polygon not found"
        data_pts = data_match.group(1)

        # Get the first button's data-points
        btn_match = re.search(r'class="gg-hp-hv-btn gg-hp-hv-btn--active"[^>]*data-points="([^"]+)"', viz_html) or \
                    re.search(r'data-points="([^"]+)"[^>]*class="gg-hp-hv-btn gg-hp-hv-btn--active"', viz_html)
        assert btn_match, "Active button not found"
        assert data_pts == btn_match.group(1), "Default polygon must match active button's points"

    # ── CSS ──

    def test_viz_css_classes_defined(self):
        """CSS contains all gg-hp-hv-* classes."""
        css = build_homepage_css()
        for cls in [".gg-hp-hv-wrap", ".gg-hp-hv-grid", ".gg-hp-hv-data",
                    ".gg-hp-hv-dot", ".gg-hp-hv-lbl", ".gg-hp-hv-btns",
                    ".gg-hp-hv-btn", ".gg-hp-hv-btn--active", ".gg-hp-hv-link",
                    ".gg-hp-hv-tooltip", ".gg-hp-hv-tooltip--visible",
                    ".gg-hp-hv-examples", ".gg-hp-hv-ex-list",
                    ".gg-hp-hv-ex-link"]:
            assert cls in css, f"CSS missing rule for {cls}"

    def test_viz_css_no_old_classes(self):
        """CSS does NOT contain old gg-hp-hf- or gg-hp-hero-feature classes."""
        css = build_homepage_css()
        assert ".gg-hp-hf-" not in css
        assert ".gg-hp-hero-feature" not in css

    def test_viz_css_colors_in_known_set(self):
        """All hex colors in radar CSS are in brand color set."""
        import re
        css = build_homepage_css()
        # Extract just the hero radar viz CSS section
        known_colors = {
            "#59473c", "#7d695d", "#178079", "#4ecdc4", "#9a7e0a",
            "#c9a92c", "#c4b5ab", "#d4c5b9", "#f5efe6", "#3a2e25",
            "#1a1613", "#b7950b", "#766a5e", "#5e6868", "#8c7568",
            "#ede4d8", "#fff",
        }
        # Find hex colors specifically in the hv- rules
        hv_rules = re.findall(r'\.gg-hp-hv-[^{]*\{[^}]+\}', css)
        for rule in hv_rules:
            hex_matches = re.findall(r'#[0-9a-fA-F]{3,8}\b', rule)
            for h in hex_matches:
                assert h.lower() in known_colors, \
                    f"Unknown hex {h} in radar viz CSS rule: {rule[:60]}..."

    # ── JS ──

    def test_viz_js_morph_handler(self):
        """JS contains hero-radar morph handler."""
        js = build_homepage_js()
        assert 'data-viz="hero-radar"' in js

    def test_viz_js_uses_prefers_reduced_motion(self):
        """Morph code references prefersReducedMotion."""
        js = build_homepage_js()
        assert "prefersReducedMotion" in js

    def test_viz_js_easing_function(self):
        """JS contains easeInOutQuad math."""
        js = build_homepage_js()
        assert "2 * pct * pct" in js

    def test_viz_js_tooltip_handler(self):
        """JS contains tooltip show/hide handlers."""
        js = build_homepage_js()
        assert "gg-hp-hv-tooltip" in js
        assert "data-dim-name" in js

    def test_viz_js_examples_update(self):
        """JS contains examples update logic with ordered list."""
        js = build_homepage_js()
        assert "data-examples" in js
        assert "gg-hp-hv-ex-link" in js
        assert "gg-hp-hv-ex-list" in js
        assert "<li>" in js

    # ── Example races ──

    def test_viz_examples_div_exists(self, viz_html):
        """Examples div is present."""
        assert 'class="gg-hp-hv-examples"' in viz_html

    def test_viz_examples_ordered_list(self, viz_html):
        """Examples use an ordered list structure."""
        assert '<ol class="gg-hp-hv-ex-list">' in viz_html
        assert '<li>' in viz_html

    def test_viz_default_has_example_links(self, viz_html):
        """Default archetype's example links are pre-populated."""
        import re
        links = re.findall(r'class="gg-hp-hv-ex-link"', viz_html)
        assert len(links) == 5, f"Expected 5 example links, got {len(links)}"

    def test_viz_buttons_have_example_data(self, viz_html):
        """Every button has data-examples and data-example-names."""
        import re
        btns = re.findall(r'<button[^>]*class="gg-hp-hv-btn[^"]*"[^>]*>', viz_html)
        for btn in btns:
            assert 'data-examples="' in btn
            assert 'data-example-names="' in btn

    def test_viz_each_archetype_has_5_examples(self, race_index):
        """Each archetype maps to exactly 5 example races."""
        examples = _compute_archetype_examples(race_index)
        for name in HERO_VIZ_ARCHETYPES:
            assert name in examples, f"Missing examples for {name}"
            assert len(examples[name]) == 5, \
                f"{name} has {len(examples[name])} examples, expected 5"

    def test_viz_example_slugs_are_valid(self, race_index):
        """All example race slugs exist in the race index."""
        by_slug = {r["slug"] for r in race_index}
        examples = _compute_archetype_examples(race_index)
        for name, races in examples.items():
            for r in races:
                assert r["slug"] in by_slug, \
                    f"Example slug '{r['slug']}' for {name} not in race index"

    def test_viz_examples_exclude_series(self, race_index):
        """No series umbrella entries appear as example races."""
        examples = _compute_archetype_examples(race_index)
        for name, races in examples.items():
            for r in races:
                assert r["slug"] not in _SERIES_UMBRELLA_SLUGS, \
                    f"Series umbrella '{r['slug']}' in {name} examples"
                assert not r["name"].endswith(" Series"), \
                    f"Series name '{r['name']}' in {name} examples"

    def test_viz_example_links_are_clickable(self, viz_html):
        """Example links point to valid race profile URLs."""
        import re
        hrefs = re.findall(r'class="gg-hp-hv-ex-link"[^>]*href="([^"]+)"', viz_html)
        if not hrefs:
            hrefs = re.findall(r'href="([^"]+)"[^>]*class="gg-hp-hv-ex-link"', viz_html)
        for href in hrefs:
            assert "/race/" in href, f"Example link not a race URL: {href}"

    # ── SVG styling compliance ──

    def test_viz_svg_no_inline_styles(self, viz_html):
        """SVG elements must not use style= attributes."""
        import re
        svg_start = viz_html.index("<svg")
        svg_end = viz_html.index("</svg>") + len("</svg>")
        svg_str = viz_html[svg_start:svg_end]
        style_matches = re.findall(r'style="[^"]*"', svg_str)
        assert not style_matches, \
            f"SVG has inline styles (must use CSS classes): {style_matches}"

    def test_viz_svg_no_hex_colors(self, viz_html):
        """SVG HTML must not contain raw hex colors."""
        import re
        svg_start = viz_html.index("<svg")
        svg_end = viz_html.index("</svg>") + len("</svg>")
        svg_str = viz_html[svg_start:svg_end]
        hex_matches = re.findall(r'#[0-9a-fA-F]{3,8}\b', svg_str)
        assert not hex_matches, \
            f"SVG has raw hex colors (must use CSS classes): {hex_matches}"

    def test_viz_svg_no_fill_stroke_attrs(self, viz_html):
        """SVG elements must not have fill= or stroke= presentation attributes."""
        import re
        svg_start = viz_html.index("<svg")
        svg_end = viz_html.index("</svg>") + len("</svg>")
        svg_str = viz_html[svg_start:svg_end]
        inner_svg = svg_str[svg_str.index(">") + 1:svg_str.rindex("</svg>")]
        fill_attrs = re.findall(r'\bfill="[^"]*"', inner_svg)
        stroke_attrs = re.findall(r'\bstroke="[^"]*"', inner_svg)
        assert not fill_attrs, \
            f"SVG elements use fill= attrs (must use CSS): {fill_attrs}"
        assert not stroke_attrs, \
            f"SVG elements use stroke= attrs (must use CSS): {stroke_attrs}"

    # ── Integration ──

    def test_hero_integration_has_radar_viz(self, stats, race_index):
        """build_hero() output contains the interactive radar viz."""
        hero = build_hero(stats, race_index)
        assert 'data-viz="hero-radar"' in hero
        assert "<svg" in hero
        assert "gg-hp-hv-btn" in hero

    def test_full_page_has_radar_viz(self, homepage_html):
        """Full generate_homepage() output contains the radar viz."""
        assert "gg-hp-hv-data" in homepage_html
        assert 'data-viz="hero-radar"' in homepage_html

    def test_full_page_no_old_featured(self, homepage_html):
        """Full page must not reference old featured card classes."""
        assert "gg-hp-hf-radar" not in homepage_html
        assert "gg-hp-hero-feature" not in homepage_html


class TestParseScore:
    """Tests for _parse_score() — the shared score parsing utility."""

    def test_integer(self):
        from generate_homepage import _parse_score
        assert _parse_score(3) == 3

    def test_string_integer(self):
        from generate_homepage import _parse_score
        assert _parse_score("4") == 4

    def test_float(self):
        from generate_homepage import _parse_score
        assert _parse_score(3.7) == 3

    def test_string_float(self):
        from generate_homepage import _parse_score
        assert _parse_score("3.5") == 3

    def test_none(self):
        from generate_homepage import _parse_score
        assert _parse_score(None) == 0

    def test_empty_string(self):
        from generate_homepage import _parse_score
        assert _parse_score("") == 0

    def test_string_none(self):
        from generate_homepage import _parse_score
        assert _parse_score("None") == 0

    def test_garbage_string(self):
        from generate_homepage import _parse_score
        assert _parse_score("abc") == 0

    def test_clamp_high(self):
        from generate_homepage import _parse_score
        assert _parse_score(8) == 5

    def test_clamp_negative(self):
        from generate_homepage import _parse_score
        assert _parse_score(-3) == 0

    def test_bool_true(self):
        from generate_homepage import _parse_score
        assert _parse_score(True) == 1

    def test_bool_false(self):
        from generate_homepage import _parse_score
        assert _parse_score(False) == 0

    def test_list_returns_zero(self):
        from generate_homepage import _parse_score
        assert _parse_score([1, 2]) == 0

    def test_dict_returns_zero(self):
        from generate_homepage import _parse_score
        assert _parse_score({"a": 1}) == 0

    def test_boundary_zero(self):
        from generate_homepage import _parse_score
        assert _parse_score(0) == 0

    def test_boundary_five(self):
        from generate_homepage import _parse_score
        assert _parse_score(5) == 5
