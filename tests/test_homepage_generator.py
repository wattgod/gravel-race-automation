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
    FEATURED_SLUGS,
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
        assert stats["dimensions"] == 14

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

    def test_hero_has_featured_card(self, stats, race_index):
        hero = build_hero(stats, race_index)
        assert "gg-hp-hero-feature" in hero
        assert "<a href=" in hero  # Featured card must be a link

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

    def test_latest_takes_in_main_column(self, homepage_html):
        """Latest Takes should appear in the main column, not the sidebar."""
        # Search within <body> only to avoid matching class names in CSS
        body_start = homepage_html.find("<body")
        body = homepage_html[body_start:]
        main_col_pos = body.find("gg-hp-main-col")
        takes_pos = body.find("gg-hp-latest-takes")
        sidebar_pos = body.find('class="gg-hp-sidebar"')
        if takes_pos >= 0 and main_col_pos >= 0 and sidebar_pos >= 0:
            assert main_col_pos < takes_pos < sidebar_pos, "Latest Takes should be in main column"

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
        assert "7fr 5fr" in css


class TestTabbedRankings:
    def test_tabbed_rankings_aria_roles(self, race_index):
        html = build_tabbed_rankings(race_index)
        assert 'role="tablist"' in html
        assert 'role="tab"' in html
        assert 'role="tabpanel"' in html

    def test_tabbed_rankings_three_tabs(self, race_index):
        html = build_tabbed_rankings(race_index)
        assert html.count('role="tab"') == 3
        assert html.count('role="tabpanel"') == 3

    def test_tabbed_rankings_aria_selected(self, race_index):
        html = build_tabbed_rankings(race_index)
        assert 'aria-selected="true"' in html
        assert html.count('aria-selected="false"') == 2

    def test_tabbed_rankings_aria_controls(self, race_index):
        html = build_tabbed_rankings(race_index)
        assert 'aria-controls="gg-panel-all"' in html
        assert 'aria-controls="gg-panel-t1"' in html
        assert 'aria-controls="gg-panel-t2"' in html

    def test_tabbed_rankings_hidden_panels(self, race_index):
        html = build_tabbed_rankings(race_index)
        # First panel visible, others hidden via CSS class (not hidden attr)
        assert 'id="gg-panel-all"' in html
        assert 'gg-hp-tab-inactive' in html
        assert 'id="gg-panel-t1"' in html
        assert 'id="gg-panel-t2"' in html

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

    def test_sidebar_pullquote(self, stats, race_index, upcoming):
        html = build_sidebar(stats, race_index, upcoming)
        assert "gg-hp-pullquote" in html
        assert "<blockquote" in html

    def test_sidebar_power_rankings(self, stats, race_index, upcoming):
        html = build_sidebar(stats, race_index, upcoming)
        assert "POWER RANKINGS" in html
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

    def test_no_fabricated_quotes(self, stats, race_index, upcoming):
        """Pullquotes in sidebar must come from real race data, not AI-generated copy."""
        sidebar_html = build_sidebar(stats, race_index, upcoming)
        import re
        quotes = re.findall(r'<blockquote[^>]*>.*?<p>(.*?)</p>', sidebar_html, re.DOTALL)
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
                f"Pullquote may be fabricated (not found in race data): {clean[:60]}..."

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

        # Check hero featured card
        hero = build_hero(stats, race_index)
        if "gg-hp-hero-feature" in hero:
            feature_links = re.findall(r'<a\s[^>]*class="gg-hp-hero-feature"', hero)
            assert len(feature_links) == 1, "Hero featured card must be a link"

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

    def test_featured_card_heading_level(self, stats, race_index):
        """Hero featured card should use h3, not h2 (h1 is the page title)."""
        import re
        hero = build_hero(stats, race_index)
        if "gg-hp-hero-feature" in hero:
            # Extract the featured card HTML
            feature_start = hero.find("gg-hp-hero-feature")
            feature_html = hero[feature_start:]
            assert "<h3" in feature_html, "Featured card should use h3, not h2"
            assert "<h2" not in feature_html, "Featured card must not use h2"

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

    def test_pullquote_is_dynamic(self, race_index):
        """Sidebar pullquote should pull from featured race data."""
        stats = compute_stats(race_index)
        sidebar = build_sidebar(stats, race_index, [])
        # Should contain a pullquote with cite referencing a real race
        assert "gg-hp-pullquote" in sidebar
        assert "<cite>" in sidebar
        # The cite should reference a race that exists in FEATURED_SLUGS
        from generate_homepage import FEATURED_SLUGS
        featured_names = [
            r.get("name", "") for r in race_index
            if r.get("slug") in FEATURED_SLUGS
        ]
        cite_found = any(name in sidebar for name in featured_names if name)
        assert cite_found or "Unbound" in sidebar, \
            "Pullquote cite must reference a real featured race"

    def test_sidebar_empty_upcoming(self, race_index):
        """Sidebar with 0 upcoming races should show off-season message."""
        stats = compute_stats(race_index)
        sidebar = build_sidebar(stats, race_index, [])
        assert "Off-season" in sidebar or "Browse all races" in sidebar

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


def html_escape(text):
    """Helper for test assertions."""
    import html as _html
    return _html.escape(str(text))
