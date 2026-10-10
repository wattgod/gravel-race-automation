"""Editorial shell (wordpress/editorial_shell.py) and the Sweet Spot article built on it."""
from __future__ import annotations

import json
import re
import sys
import warnings
from datetime import date
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
sys.path.insert(0, str(PROJECT_ROOT / "wordpress" / "article_sources"))

import editorial_shell as es  # noqa: E402
import pricing  # noqa: E402
import sweet_spot_training_cycling as sweet_spot  # noqa: E402
import your_training_app_doesnt_know_your_race_exists as training_app  # noqa: E402
from brand_tokens import (  # noqa: E402
    get_favicon_head_snippet,
    get_font_face_css,
    get_ga4_head_snippet,
    get_preload_hints,
)
from blog_tracking import get_plan_intent_tracking_script  # noqa: E402
from cookie_consent import get_consent_banner_html  # noqa: E402
from shared_header import get_site_header_html, get_site_header_js  # noqa: E402

SWEET_SPOT_INDEX = PROJECT_ROOT / "wordpress" / "articles" / "sweet-spot-training-cycling" / "index.html"
TRAINING_APP_INDEX = training_app.OUTPUT_PATH

# Every article built from wordpress/article_sources/. A new source module goes here.
ARTICLE_SOURCES = (sweet_spot, training_app)

BODY = """<section class="gg-blog-section">
  <p>Intro paragraph.</p>
</section>
<section class="gg-blog-section">
  <h2>First Thing</h2>
  <p>One.</p>
  <h3>A detail</h3>
</section>
<section class="gg-blog-section">
  <h2 id="kept">Second &amp; Last</h2>
  <p>Two.</p>
</section>
<section class="gg-blog-section">
  <h2>First Thing</h2>
  <p>Dup heading.</p>
</section>
<section class="gg-blog-section gg-references">
  <h2>References</h2>
  <p id="ref-1"><sup>1</sup> Someone (2020).</p>
</section>
"""


def _meta(**kw) -> es.ArticleMeta:
    base = dict(
        slug="test-article",
        canonical_url="https://gravelgodcycling.com/articles/test-article/",
        title="Test Article | Gravel God",
        description="A test article.",
        headline="Test Article",
        date_published=date(2026, 3, 26),
        kicker="Training",
        dek="A dek.",
    )
    base.update(kw)
    return es.ArticleMeta(**base)


@pytest.fixture
def page() -> str:
    return es.render_editorial_page(_meta(), BODY)


def _head(html: str) -> str:
    return html.split("<head>", 1)[1].split("</head>", 1)[0]


def _main(html: str) -> str:
    """The page body between <main> and </main> (no CSS, no scripts)."""
    return html.split("<main>", 1)[1].split("</main>", 1)[0]


# ── Head ──────────────────────────────────────────────────────


class TestHead:
    def test_required_tags(self, page):
        head = _head(page)
        assert '<meta charset="UTF-8">' in head
        assert '<meta name="viewport" content="width=device-width, initial-scale=1.0">' in head
        assert '<meta name="robots" content="index, follow">' in head
        assert "<title>Test Article | Gravel God</title>" in head
        assert '<meta name="description" content="A test article.">' in head
        assert '<link rel="canonical" href="https://gravelgodcycling.com/articles/test-article/">' in head
        for prop in ("og:title", "og:description", "og:url", "og:type", "og:site_name"):
            assert f'property="{prop}"' in head

    def test_brand_snippets_verbatim(self, page):
        head = _head(page)
        assert get_ga4_head_snippet().strip() in head
        assert get_font_face_css() in head
        assert get_preload_hints().strip() in head
        assert get_favicon_head_snippet().strip() in head

    def test_consent_defaults_load_before_gtag(self, page):
        head = _head(page)
        assert head.index("gtag('consent','default'") < head.index("googletagmanager.com/gtag/js")

    def test_og_image_optional(self, page):
        assert "og:image" not in _head(page)
        with_img = es.render_editorial_page(_meta(og_image=es.OgImage("https://x/y.png", 10, 20)), BODY)
        assert '<meta property="og:image" content="https://x/y.png">' in with_img
        assert '<meta property="og:image:width" content="10">' in with_img

    def test_robots_override_for_previews(self):
        html = es.render_editorial_page(_meta(robots="noindex, follow"), BODY)
        assert '<meta name="robots" content="noindex, follow">' in html

    def test_json_ld_round_trips_and_cannot_close_script(self):
        ld = {"@type": "Article", "headline": "Bad </script><b>x"}
        html = es.render_editorial_page(_meta(json_ld=(ld,)), BODY)
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        assert len(blocks) == 1
        assert json.loads(blocks[0]) == ld

    def test_meta_text_is_escaped(self):
        html = es.render_editorial_page(
            _meta(title='A "quoted" <b> & co', headline="<script>x</script>", description='d"x'),
            BODY,
        )
        assert "<title>A &quot;quoted&quot; &lt;b&gt; &amp; co</title>" in html
        assert "<h1>&lt;script&gt;x&lt;/script&gt;</h1>" in html
        assert 'content="d&quot;x"' in html


# ── Body: contents, markers, blocks ───────────────────────────


class TestContents:
    def test_h2_ids_and_contents_order(self):
        body, toc = es.add_heading_ids(BODY)
        assert [sid for sid, _ in toc] == ["first-thing", "kept", "first-thing-2"]
        assert '<h3 id="a-detail">A detail</h3>' in body
        assert '<h2 id="kept" data-toc>' in body  # existing id preserved
        assert '<h2 id="references">References</h2>' in body  # no data-toc

    def test_references_left_out(self):
        _, toc = es.add_heading_ids(BODY)
        assert "References" not in [label for _, label in toc]

    def test_contents_rendered_twice_rail_and_bar(self, page):
        assert page.count('<ol class="toc">') == 2
        assert 'href="#first-thing-2"' in page

    def test_contents_can_be_hidden(self):
        html = es.render_editorial_page(_meta(), BODY, contents=False)
        assert 'class="toc"' not in html and 'class="rail"' not in html

    def test_one_rail_at_a_time_on_wide_screens(self, page):
        """The contents rail waits (.rail.wait) while "In short" is beside the
        text; no-JS readers still get both (the rail is visible by default)."""
        assert '<nav class="rail" aria-label="Contents">' in page  # no .wait in the markup
        assert ".rail.wait .stick{opacity:0;visibility:hidden}" in page
        assert "rail.classList.toggle('wait',sum.getBoundingClientRect().bottom>28)" in page


# 20 sections, like WP post 1626 ("5 ways ... power meter clown"): one dot per
# section overflowed the phone Contents bar (416px wide at 390).
TWENTY_SECTIONS = "\n".join(
    f'<section class="gg-blog-section">\n  <h2>Section number {i}</h2>\n  <p>Text {i}.</p>\n</section>'
    for i in range(1, 21))


class TestPhoneContentsBarManySections:
    def test_many_sections_collapse_the_dots_into_one_bar(self):
        html = es.render_editorial_page(_meta(), TWENTY_SECTIONS)
        assert '<span class="mini many" id="mini" aria-hidden="true"></span>' in html
        assert html.count('<ol class="toc">') == 2  # the full list is still there, twice
        assert "mini.classList.contains('many')" in html  # JS draws a progress bar, not 20 dots
        assert "fill.style.width=((cur+1)/heads.length*100)+'%'" in html

    def test_up_to_the_cap_keeps_one_dot_per_section(self):
        n = es.MINI_DOTS_MAX
        body = "\n".join(f'<section class="gg-blog-section">\n  <h2>S{i}</h2>\n  <p>T.</p>\n</section>'
                         for i in range(1, n + 1))
        html = es.render_editorial_page(_meta(), body)
        assert '<span class="mini" id="mini" aria-hidden="true"></span>' in html
        assert es.MINI_DOTS_MAX == 10

    def test_the_dots_can_never_widen_the_bar(self):
        """The dot strip shrinks and clips inside the summary instead of pushing
        it past the viewport; the collapsed bar is at most 96px."""
        css = es.SHELL_CSS
        assert ".toc-m .mini{display:flex;gap:6px;flex:0 1 auto;min-width:0;overflow:hidden}" in css
        assert ".toc-m .mini.many{flex:0 1 96px}" in css
        assert "min-width:0;flex:1}" in css.split(".toc-m .now{", 1)[1].split("\n", 1)[0]


DIV_BODY = """<div class="gg-blog-section">
  <p>Roundup intro.</p>
</div>
<div class="gg-blog-section gg-roundup">
  <h2>Tier 1</h2>
  <div class="gg-roundup-grid"><div class="card"><h3>Race A</h3></div></div>
  <h2>Tier 2</h2>
</div>
<div class="gg-roundup-grid"><h2>Outside any section</h2></div>
<div class="gg-blog-section gg-references">
  <h2>Sources</h2>
  <div><h2>Nested in references</h2></div>
</div>
"""


class TestHeadingRobustness:
    def test_gt_inside_h2_attribute(self):
        body = '<section class="gg-blog-section"><h2 title="a > b" class="x">Gear &gt; Fitness</h2><p>x</p></section>'
        out, toc = es.add_heading_ids(body)
        assert toc == [("gear-fitness", "Gear &gt; Fitness")]
        assert '<h2 title="a > b" class="x" id="gear-fitness" data-toc>Gear &gt; Fitness</h2>' in out

    def test_gt_inside_h3_attribute_keeps_text(self):
        body = '<section class="gg-blog-section"><h2>A</h2><h3 data-x=\'1>0\'>Detail</h3></section>'
        out, _ = es.add_heading_ids(body)
        assert '<h3 data-x=\'1>0\' id="detail">Detail</h3>' in out

    def test_warns_when_h2s_but_no_contents(self):
        body = "<div><h2>Loose heading</h2><p>Not in a gg-blog-section.</p></div>"
        with pytest.warns(UserWarning, match="none is a contents heading"):
            _, toc = es.add_heading_ids(body)
        assert toc == []

    def test_no_warning_for_valid_or_heading_free_bodies(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            es.add_heading_ids(BODY)
            es.add_heading_ids(DIV_BODY)
            es.add_heading_ids('<section class="gg-blog-section"><p>No headings.</p></section>')


class TestSectionRule:
    """One rule for Contents, numbering, scrollspy and references, <section> or <div>."""

    def _toc_attr_ids(self, html: str) -> list[str]:
        return re.findall(r'<h2[^>]*\bid="([^"]+)"[^>]*\bdata-toc\b', html)

    @pytest.mark.parametrize("body,expected", [
        (BODY, ["first-thing", "kept", "first-thing-2"]),
        (DIV_BODY, ["tier-1", "tier-2"]),
    ], ids=["section", "div"])
    def test_contents_equals_data_toc_headings(self, body, expected):
        out, toc = es.add_heading_ids(body)
        assert [sid for sid, _ in toc] == expected
        assert self._toc_attr_ids(out) == expected

    def test_div_body_page(self):
        html = es.render_editorial_page(_meta(), DIV_BODY)
        rail = html.split('<nav class="rail"', 1)[1].split("</nav>", 1)[0]
        assert re.findall(r'href="#([^"]+)"', rail) == ["tier-1", "tier-2"]
        main = _main(html)
        # The ladder goes right before the <div> references block.
        assert main.index("Outside any section") < main.index("slot-ladder") < main.index("gg-references")
        assert main.count("data-toc") == 2

    def test_mixed_section_and_div(self):
        body = BODY.replace('<section class="gg-blog-section gg-references">', DIV_BODY + '<section class="gg-blog-section gg-references">')
        _, toc = es.add_heading_ids(body)
        assert [sid for sid, _ in toc] == ["first-thing", "kept", "first-thing-2", "tier-1", "tier-2"]

    def test_references_start_is_outermost(self):
        start = es.outline(DIV_BODY).references_start
        assert DIV_BODY[start:].startswith('<div class="gg-blog-section gg-references">')
        assert es.outline("<section class=\"gg-blog-section\"><h2>x</h2></section>").references_start is None

    def test_css_and_js_follow_data_toc(self):
        assert ".article h2[data-toc]{counter-increment:blk}" in es.SHELL_CSS
        assert "content:counter(blk,decimal-leading-zero)" in es.SHELL_CSS
        assert "querySelectorAll('#article h2[data-toc]')" in es.SHELL_JS
        assert "gg-blog-section:not(.gg-references) h2" not in es.SHELL_CSS + es.SHELL_JS


class TestInShortAndLadder:
    CLAIMS = (es.Claim("Claim <em>one</em>.", "#first-thing", "See it · §01", 0),)

    def test_in_short_defaults_to_start(self):
        html = es.render_editorial_page(_meta(), BODY, in_short=self.CLAIMS)
        art = html.split('id="article">', 1)[1]
        assert art.lstrip().startswith('<div class="slot slot-summary"')
        assert '<li data-sec="0"><p>Claim <em>one</em>.</p>' in html

    def test_in_short_marker(self):
        body = BODY.replace("<p>One.</p>", "<p>One.</p>" + es.IN_SHORT_MARKER)
        html = _main(es.render_editorial_page(_meta(), body, in_short=self.CLAIMS))
        assert html.index("<p>One.</p>") < html.index("slot-summary") < html.index("A detail")
        assert es.IN_SHORT_MARKER not in html

    def test_no_in_short_by_default(self, page):
        assert "slot-summary" not in _main(page)

    def test_ladder_defaults_before_references(self, page):
        main = _main(page)
        assert main.index('class="slot slot-ladder"') < main.index("gg-references")
        assert main.index("Dup heading.") < main.index('class="slot slot-ladder"')

    def test_ladder_marker_and_custom_lead(self):
        body = es.LADDER_MARKER + BODY
        html = es.render_editorial_page(_meta(), body, ladder="Custom lead.")
        art = html.split('id="article">', 1)[1]
        assert art.lstrip().startswith('<div class="slot slot-ladder"')
        assert '<p class="lead">Custom lead.</p>' in html

    def test_ladder_off(self):
        html = es.render_editorial_page(_meta(), es.LADDER_MARKER + BODY, ladder=False)
        assert "slot-ladder" not in _main(html) and es.LADDER_MARKER not in html

    def test_ladder_links(self, page):
        ladder = page.split('class="slot slot-ladder"', 1)[1].split("</aside>", 1)[0]
        links = re.findall(
            r'<a class="btn" href="([^"]+)" data-event="article_cta_click" data-label="([^"]+)" data-cta="([^"]+)">',
            ladder,
        )
        assert links == [
            ("/products/training-plans/", "custom_plan", "custom_plan"),
            ("/season-plan/", "season_plan", "season_plan"),
            ("/coaching/", "coaching", "coaching"),
        ]

    def test_plan_intent_script_catches_ladder_buttons(self, page):
        """blog_tracking selects a[data-cta][href*=X]; the plan + coaching rungs must match."""
        script = get_plan_intent_tracking_script()
        needles = re.findall(r"a\[data-cta\]\[href\*=\"([^\"]+)\"\]", script)
        assert needles, "blog_tracking selector format changed"
        ladder = page.split('class="slot slot-ladder"', 1)[1].split("</aside>", 1)[0]
        caught = {
            cta
            for href, cta in re.findall(r'<a class="btn" href="([^"]+)"[^>]* data-cta="([^"]+)"', ladder)
            if any(n in href for n in needles)
        }
        assert caught == {"custom_plan", "season_plan", "coaching"}

    def test_plan_intent_selector_covers_season_plan(self):
        assert 'a[data-cta][href*="/season-plan"]' in get_plan_intent_tracking_script()


class TestLadderPricing:
    def test_prices_come_from_pricing_json(self, page):
        race, season = pricing.RACE_PLAN, pricing.SEASON_PLAN
        coaching = pricing.PRICING["products"]["coaching"]
        assert f'{race["weekly_rate_display"]}/week \u00b7 capped at {race["cap_display"]}' in page
        assert f'<span class="price">{season["price_display"]}</span>' in page
        assert f'From {coaching["from_display"]} every {coaching["interval_weeks"]} weeks' in page
        assert f'within {race["delivery_hours"]} hours. {race["refund_window_days"]}-day refund.' in page
        assert f'up to {season["max_weeks"]} weeks' in page

    def test_ladder_follows_a_price_change(self, monkeypatch):
        monkeypatch.setitem(pricing.RACE_PLAN, "cap_display", "$999")
        monkeypatch.setitem(pricing.SEASON_PLAN, "scheduled_rebuilds", 3)
        html = es.render_ladder()
        assert "capped at $999" in html
        assert "three scheduled rebuilds" in html

    def test_no_money_literals_in_shell_source(self):
        src = (PROJECT_ROOT / "wordpress" / "editorial_shell.py").read_text()
        assert not re.search(r"\$\d", src), "type prices into data/pricing.json, not the shell"

    def test_coaching_entry_price_matches_coaching_page_tiers(self):
        """pricing.json's coaching 'from' price must equal the Min tier on /coaching/."""
        src = (PROJECT_ROOT / "wordpress" / "generate_coaching.py").read_text()
        m = re.search(r'\("min",\s*"Min",\s*"([^"]+)"\)', src)
        assert m, "generate_coaching.TIERS Min row not found"
        coaching = pricing.PRICING["products"]["coaching"]
        assert coaching["from_display"] == m.group(1)
        assert coaching["from_cents"] == int(m.group(1).lstrip("$").replace(",", "")) * 100


# ── Analytics, consent, chrome ────────────────────────────────


class TestAnalyticsAndChrome:
    def test_article_events(self, page):
        assert "'article_scroll_depth'" in page
        assert "'article_cta_click'" in page
        assert "'article_slug': \"test-article\"" in page
        # Deep read fires only at 75%+ (the funnel metric).
        deep = page.split("'article_deep_read'", 1)[0]
        assert "if (depths[i] >= 75)" in deep[-400:]

    def test_events_can_be_off(self):
        html = es.render_editorial_page(_meta(track_article_events=False), BODY)
        assert "article_scroll_depth" not in html

    def test_events_off_by_default_on_noindex_pages(self):
        """Blog previews/recaps are "noindex, follow": no article_* events there."""
        html = es.render_editorial_page(_meta(robots="noindex, follow"), BODY)
        for event in ("article_scroll_depth", "article_deep_read", "article_cta_click"):
            assert f"'{event}'" not in html  # no gtag('event', '<name>', ...) call
        assert "Article-specific GA4 events" not in html
        # The ladder still renders and still carries data-cta for blog_tracking.
        assert 'data-cta="custom_plan"' in html

    def test_events_on_by_default_on_indexable_pages(self):
        assert es.render_editorial_page(_meta(robots="index, follow"), BODY).count("'article_deep_read'") == 1

    def test_events_can_be_forced_on_noindex(self):
        html = es.render_editorial_page(_meta(robots="noindex, follow", track_article_events=True), BODY)
        assert "'article_scroll_depth'" in html

    def test_consent_banner_and_legal_links(self, page):
        assert get_consent_banner_html() in page
        assert 'href="/privacy/"' in page and 'href="/terms/"' in page

    def test_header_is_the_shared_site_header(self, page):
        header = page.split('<header class="gg-site-header"', 1)[1].split("</header>", 1)[0]
        shared = get_site_header_html("articles")
        # Every nav link (desktop dropdowns + mobile drawer) comes from shared_header.
        for href in set(re.findall(r'href="([^"]+)"', shared)):
            assert f'href="{href}"' in header, href
        assert header.count('class="gg-site-header-dropdown"') == shared.count('class="gg-site-header-dropdown"')
        assert '<a href="https://gravelgodcycling.com/articles/" aria-current="page">ARTICLES</a>' in header
        assert 'class="btn gg-hdr-sub"' in header and 'data-label="substack_header"' in header
        assert '<nav class="nav"' not in page and 'class="menu"' not in page

    def test_header_raises_if_subscribe_anchor_is_gone(self, monkeypatch):
        monkeypatch.setattr(es, "get_site_header_html", lambda active=None: "<header>no hamburger</header>")
        with pytest.raises(RuntimeError, match="gg-hamburger"):
            es.render_header()

    def test_every_restyled_header_class_exists_in_shared_header(self):
        """SHELL_CSS restyles shared_header's markup; a renamed class would silently unstyle it."""
        restyled = set(re.findall(r"\.((?:gg-site-header|gg-hamburger|gg-mobile-nav)[\w-]*|is-open)\b", es.SHELL_CSS))
        assert {"gg-site-header-nav", "gg-hamburger-bar", "gg-mobile-nav-sub", "is-open"} <= restyled
        html_classes = {
            c for attr in re.findall(r'class="([^"]*)"', get_site_header_html("articles")) for c in attr.split()
        }
        js_classes = set(re.findall(r"classList\.\w+\('([\w-]+)'", get_site_header_js()))
        missing = restyled - html_classes - js_classes
        assert not missing, f"shell CSS restyles classes shared_header no longer emits: {sorted(missing)}"

    def test_footer_nav_is_the_header_nav(self, page):
        links = es.header_nav_links()
        assert [label for _, label in links] == ["RACES", "PRODUCTS", "SERVICES", "ARTICLES", "ABOUT"]
        shared = get_site_header_html(None)
        for href, label in links:
            assert f'<a href="{href}">{label}</a>' in shared
        foot = page.split('<nav aria-label="Footer">', 1)[1].split("</nav>", 1)[0]
        assert re.findall(r'<a href="([^"]+)">', foot) == [h for h, _ in links] + [es.SUBSTACK_URL]
        assert not hasattr(es, "NAV_LINKS")

    def test_header_js_drives_hamburger_and_dropdowns(self, page):
        assert get_site_header_js().strip() in page
        assert 'id="gg-hamburger"' in page and 'id="gg-mobile-nav"' in page

    def test_nav_active_is_configurable(self):
        html = es.render_editorial_page(_meta(nav_active=None), BODY)
        header = html.split('<header class="gg-site-header"', 1)[1].split("</header>", 1)[0]
        assert "aria-current" not in header

    def test_no_inline_handlers(self, page):
        assert not re.search(r"\son[a-z]+=", page)

    def test_hero_byline_and_reading_time(self, page):
        assert "Gravel God &middot; March 26, 2026 &middot; 1 min read" in page

    def test_reading_time_can_be_off(self):
        html = es.render_editorial_page(_meta(show_read_time=False), BODY)
        assert '<p class="by">Gravel God &middot; March 26, 2026</p>' in html
        assert "min read" not in html

    def test_no_hero_image(self, page):
        assert 'class="frame hero no-img"' in page
        assert "hero-img" not in page.split("<main>", 1)[1].split("</main>", 1)[0]

    def test_hero_portrait_is_default(self):
        html = es.render_editorial_page(_meta(hero=es.HeroImage("a.png", "Alt", 734, 894)), BODY)
        assert 'class="frame hero"' in html
        assert '<img src="a.png" alt="Alt" width="734" height="894" loading="eager">' in html

    def test_hero_wide_for_og_cards(self):
        hero = es.HeroImage("og.jpg", "Card", 1200, 630, layout="wide")
        html = es.render_editorial_page(_meta(hero=hero), BODY)
        assert 'class="frame hero wide"' in html
        assert 'width="1200" height="630"' in html

    def test_hero_layout_is_validated(self):
        with pytest.raises(ValueError):
            es.HeroImage("x.jpg", "x", 1, 1, layout="banner")

    def test_hero_class_hooks(self):
        hero = es.HeroImage("og.jpg", "Card", 1200, 630, layout="wide", figure_class="gg-blog-hero-img")
        html = es.render_editorial_page(_meta(hero=hero, hero_class="gg-blog-hero"), BODY)
        assert '<div class="frame hero wide gg-blog-hero">' in html
        assert '<figure class="hero-img gg-blog-hero-img"><img src="og.jpg"' in html

    def test_hero_class_without_image(self):
        html = es.render_editorial_page(_meta(hero_class="  a  b "), BODY)
        assert '<div class="frame hero no-img a b">' in html

    def test_hero_class_hooks_default_to_unchanged_markup(self):
        """Generators that string-replace the hero markup keep working."""
        hero = es.HeroImage("og.jpg", "Card", 1200, 630, layout="wide")
        html = es.render_editorial_page(_meta(hero=hero), BODY)
        assert html.count('<div class="frame hero wide">') == 1
        assert html.count('<figure class="hero-img">') == 1

    @pytest.mark.parametrize("bad", ['x" onclick="y', "a<b", "a>b"])
    def test_hero_classes_are_validated(self, bad):
        with pytest.raises(ValueError):
            es.HeroImage("x.jpg", "x", 1, 1, figure_class=bad)
        with pytest.raises(ValueError):
            _meta(hero_class=bad)

    def test_hero_frame_class_starts_every_hero(self):
        for kw in ({}, {"hero": es.HeroImage("a.png", "A", 1, 1)},
                   {"hero": es.HeroImage("a.png", "A", 1, 1, layout="wide"), "hero_class": "x"}):
            html = es.render_editorial_page(_meta(**kw), BODY)
            assert re.search(r'<div class="' + re.escape(es.HERO_FRAME_CLASS) + r'[ "]', _main(html))

    def test_byline_date_default_hidden_and_custom(self):
        assert '<p class="by">Gravel God &middot; March 26, 2026 &middot;' in es.render_editorial_page(_meta(), BODY)
        hidden = es.render_editorial_page(_meta(byline_date="", show_read_time=False), BODY)
        assert '<p class="by">Gravel God</p>' in hidden
        custom = es.render_editorial_page(_meta(byline_date="Updated May 2026 & on", show_read_time=False), BODY)
        assert '<p class="by">Gravel God &middot; Updated May 2026 &amp; on</p>' in custom

    def test_h1_wraps_long_words(self):
        rule = re.search(r"\nh1\{[^}]*\}", es.SHELL_CSS).group(0)
        assert "overflow-wrap:break-word" in rule

    @pytest.mark.parametrize("headline", [
        "Test Article",
        "Sweet Spot Isn’t That Sweet",
        "Your Training App Doesn’t Know Your Race Exists",
        "Alentejo Gravel Race Preview",
        "Unbound 200 Race Preview",
        "Championship",  # 12.2 units
        "championships",  # 13 units: the widest word that stays untiered
        "UNBOUND XL",
    ])
    def test_h1_normal_titles_unchanged(self, headline):
        assert es.h1_long_word_class(headline) == ""
        html = es.render_editorial_page(_meta(headline=headline), BODY)
        assert f"      <h1>{es.esc(headline)}</h1>" in html

    @pytest.mark.parametrize("headline,cls", [
        ("Periodization Explained", "h1-long-1"),     # 13.2 units (capital P)
        ("Ultradistance", "h1-long-1"),               # 13.2
        ("Ultradistances", "h1-long-1"),              # 14.2
        ("Gravelbikepacking", "h1-long-3"),            # 17.2
        ("Transcontinental Race Preview", "h1-long-2"),  # 16.2
        ("TRANSCONTINENTAL RACE Race Preview", "h1-long-3"),  # 19.2
        ("TRANSCONTINENTALS", "h1-long-4"),           # 20.4
    ])
    def test_h1_long_word_tiers(self, headline, cls):
        assert es.h1_long_word_class(headline) == cls
        html = es.render_editorial_page(_meta(headline=headline), BODY)
        assert f'<h1 class="{cls}">{es.esc(headline)}</h1>' in html

    def test_h1_tier_boundaries(self):
        assert es.h1_long_word_class("a" * 13) == ""
        assert es.h1_long_word_class("a" * 14) == "h1-long-1"
        assert es.h1_long_word_class("a" * 15) == "h1-long-1"
        assert es.h1_long_word_class("a" * 16) == "h1-long-2"
        assert es.h1_long_word_class("a" * 17) == "h1-long-2"
        assert es.h1_long_word_class("a" * 18) == "h1-long-3"
        assert es.h1_long_word_class("a" * 19) == "h1-long-3"
        assert es.h1_long_word_class("a" * 20) == "h1-long-4"

    def test_h1_words_split_on_hyphens_and_dashes(self):
        assert es.h1_long_word_class("Race-Day Fueling — Bikepacking/Gravel") == ""
        assert es.h1_long_word_class("") == ""

    def test_h1_long_tiers_have_css_and_fit_the_phone_column(self):
        css = es.SHELL_CSS
        for limit, cls in es.H1_LONG_TIERS:
            w = float(re.search(r"h1\." + cls + r"\{--h1-w:([\d.]+)\}", css).group(1))
            if limit != float("inf"):
                assert w >= limit * 0.55 - 1e-9  # the tier's widest word fits its width
        assert 13 * 0.55 * 42 <= 360 - 32  # untiered words fit the 42px phone h1
        phone = css.split("@media (max-width:640px)", 1)[1]
        assert 'h1[class*="h1-long-"]{font-size:min(42px,calc((100vw - 32px) / var(--h1-w)))}' in phone


ONE_H2 = '<section class="gg-blog-section"><h2>Only</h2><p>x</p></section>'
TWO_H2 = ONE_H2 + '<section class="gg-blog-section"><h2>Second</h2><p>y</p></section>'


class TestContentsThreshold:
    def test_one_heading_hides_contents(self):
        html = es.render_editorial_page(_meta(), ONE_H2)
        assert 'class="toc"' not in html and 'class="rail"' not in html and 'id="tocm"' not in html
        assert '<h2 id="only" data-toc>' in html  # still numbered

    def test_two_headings_show_contents(self):
        html = es.render_editorial_page(_meta(), TWO_H2)
        assert html.count('<ol class="toc">') == 2 and 'id="tocm"' in html

    def test_explicit_false_still_wins(self):
        html = es.render_editorial_page(_meta(), TWO_H2, contents=False)
        assert 'class="toc"' not in html

    def test_threshold_is_two(self):
        assert es.MIN_CONTENTS_HEADINGS == 2


def _body_scripts(html: str) -> list[str]:
    body = html.split("</head>", 1)[1]
    return re.findall(r"<script[^>]*>(.*?)</script>", body, flags=re.S)


class TestValidatorHooks:
    def test_each_shell_script_marker_is_in_exactly_one_body_script(self, page):
        scripts = _body_scripts(page)
        for marker in es.SHELL_BODY_SCRIPT_MARKERS:
            assert sum(marker in s for s in scripts) == 1, marker

    def test_markers_come_from_their_sources(self):
        assert es.HEADER_JS_MARKER in get_site_header_js()
        assert es.SCROLLSPY_JS_MARKER in es.SHELL_JS
        assert es.HEADER_JS_MARKER not in es.SHELL_JS
        assert es.SCROLLSPY_JS_MARKER not in get_site_header_js()


# ── Essay components (opt-in) ─────────────────────────────────

FIG_BODY = """<section class="gg-blog-section">
  <p>Intro paragraph.</p>
</section>
<section class="gg-blog-section">
  <h2>First Thing</h2>
  <p>One &mdash; anchor here.</p>
  <ul><li>List anchor</li></ul>
  <!--GG:FIGURE one-->
</section>
<section class="gg-blog-section">
  <h2>Second</h2>
  <p>Two.</p>
</section>
"""


def _pic(**kw) -> es.Picture:
    return es.Picture.from_stem("img/scene", "A scene", 1600, 1000, **kw)


def _table(**kw) -> es.DataTable:
    base = dict(
        id="fig-t",
        title="Studies",
        columns=(
            es.TableColumn("Study", card="title"),
            es.TableColumn("Year", kind="num", card="aside"),
            es.TableColumn("n", kind="num", card="fact"),
            es.TableColumn("Result"),
        ),
        rows=(
            es.TableRow((es.TableCell("B <sup><a href=\"#ref-2\">2</a></sup>"), es.TableCell("2019", sort=2019),
                         es.TableCell("", sort=""), es.TableCell("b result")),
                        links=(es.TableLink("https://x.test/2/", "abstract", "Abstract (ref 2)"),)),
            es.TableRow((es.TableCell("A"), es.TableCell("2007", sort=2007), es.TableCell("12", sort=12, note_html="cyclists"),
                         es.TableCell("a result")),
                        links=(es.TableLink("https://x.test/1/", "abstract", "Abstract (ref 1)"),)),
        ),
        sort_by=1,
        marker="one",
    )
    base.update(kw)
    return es.DataTable(**base)


class TestEssayComponentsOptIn:
    def test_plain_pages_get_no_essay_css_or_js(self, page):
        assert es.ESSAY_JS_MARKER not in page
        assert "gg-draw-grow" not in page and "gg-essay-fig" not in page

    def test_figure_page_gets_css_and_one_essay_script(self):
        html = es.render_editorial_page(_meta(), FIG_BODY, figures=[_table()])
        assert "gg-draw-grow" in _head(html)
        assert sum(es.ESSAY_JS_MARKER in s for s in _body_scripts(html)) == 1
        assert es.ESSAY_JS_MARKER not in es.SHELL_BODY_SCRIPT_MARKERS  # blog validator untouched

    def test_still_figure_needs_css_but_no_js(self):
        html = es.render_editorial_page(_meta(), FIG_BODY, figures=[es.EssayFigure(_pic(), marker="one")])
        assert "gg-essay-fig" in _head(html)
        assert es.ESSAY_JS_MARKER not in html

    def test_draw_in_inside_a_placed_figure_opts_in(self):
        svg = es.SvgFigure(id="fig-t", svg='<svg viewBox="0 0 1 1"><g data-draw-in><rect data-draw="grow"/></g></svg>',
                           title="T", marker="one")
        html = es.render_editorial_page(_meta(), FIG_BODY, figures=[svg])
        assert es.ESSAY_JS_MARKER in html

    def test_draw_in_alone_opts_in(self):
        body = FIG_BODY.replace("<!--GG:FIGURE one-->", '<figure data-draw-in><i data-draw="grow"></i></figure>')
        html = es.render_editorial_page(_meta(), body)
        assert es.ESSAY_JS_MARKER in html and "@keyframes gg-draw-grow" in html


class TestPicture:
    def test_from_stem_paths(self):
        p = _pic(phone=(900, 760))
        assert p.files() == ("img/scene.png", "img/scene@2x.png", "img/scene.webp", "img/scene@2x.webp",
                             "img/scene-m.webp", "img/scene-m@2x.webp")

    def test_render_order_and_attrs(self):
        out = es.render_picture(_pic(phone=(900, 760)))
        phone = out.index('media="(max-width: 640px)"')
        webp = out.index('<source type="image/webp" srcset="img/scene.webp 1x, img/scene@2x.webp 2x">')
        img = out.index("<img ")
        assert phone < webp < img
        assert 'srcset="img/scene-m.webp 1x, img/scene-m@2x.webp 2x" width="900" height="760"' in out
        assert 'srcset="img/scene.png 1x, img/scene@2x.png 2x"' in out
        assert 'width="1600" height="1000" loading="lazy" decoding="async"' in out
        assert 'class="gg-pic gg-pic-art"' in out

    def test_plain_picture(self):
        out = es.render_picture(es.Picture("img/a.jpg", "A", 10, 20))
        assert "<source" not in out and "srcset" not in out and 'class="gg-pic"' in out

    def test_eager(self):
        assert 'loading="eager" fetchpriority="high"' in es.render_picture(_pic(), eager=True)

    def test_hero_from_picture(self):
        html = es.render_editorial_page(_meta(hero=es.HeroImage.from_picture(_pic(phone=(1130, 635)))), BODY)
        hero = _main(html).split('<figure class="hero-img">', 1)[1].split("</figure>", 1)[0]
        assert hero.startswith('<picture class="gg-pic gg-pic-art">') and 'fetchpriority="high"' in hero
        assert ".hero:not(.wide) .hero-img .gg-pic-art img{aspect-ratio:auto" in html

    def test_plain_hero_unchanged(self):
        html = es.render_editorial_page(_meta(hero=es.HeroImage("img/a.png", "A", 10, 20)), BODY)
        assert '<figure class="hero-img"><img src="img/a.png" alt="A" width="10" height="20" loading="eager"></figure>' in html
        assert "gg-essay-fig" not in html


class TestEssayFigure:
    def _video(self, **kw):
        base = dict(sources=(("img/v.webm", "video/webm"), ("img/v.mp4", "video/mp4")), poster="img/v.png",
                    width=1280, height=800, phone_aspect="900/760", phone_position="100% 0")
        base.update(kw)
        return es.PlayOnceVideo(**base)

    def test_still_with_caption(self):
        out = es.render_essay_figure(es.EssayFigure(_pic(), caption_html="A <em>cap</em>", id="fig-x"))
        assert out.startswith('<figure class="gg-essay-fig" id="fig-x">')
        assert "<figcaption>A <em>cap</em></figcaption>" in out and "<video" not in out

    def test_column_width(self):
        assert 'class="gg-essay-fig is-column"' in es.render_essay_figure(es.EssayFigure(_pic(), width="column"))
        with pytest.raises(ValueError):
            es.EssayFigure(_pic(), width="huge")

    def test_play_once_video(self):
        out = es.render_essay_figure(es.EssayFigure(_pic(), video=self._video()))
        v = re.search(r"<video[^>]*>", out).group(0)
        for attr in ("muted", "playsinline", 'preload="none"', 'data-poster="img/v.png"', 'aria-label="A scene"'):
            assert attr in v, attr
        assert " poster=" not in v  # attached by JS only when the clip will show
        assert "autoplay" not in v and "loop" not in v and "controls" not in v
        assert 'style="--ph-ar:900/760;--ph-pos:100% 0"' in v
        assert out.index('src="img/v.webm"') < out.index('src="img/v.mp4"')
        assert re.search(r'<button class="gg-replay" type="button" aria-label="Replay animation" hidden>', out)
        assert "data-play-once" in out and '<picture class="gg-pic">' in out  # the still

    def test_still_until_live_and_under_reduced_motion(self):
        css = es.ESSAY_CSS
        # Without JS the still shows and the video (and its poster) never load.
        assert ".gg-media.has-video video{display:none}" in css
        assert ".gg-media.has-video .gg-pic{display:block}" in css
        assert ".gg-media.has-video.is-live video{display:block}" in css
        rm = css.split("@media (prefers-reduced-motion:reduce){", 1)[1].split("\n}", 1)[0]
        assert ".gg-media.has-video.is-live video,.gg-replay{display:none}" in rm
        assert ".gg-media.has-video.is-live .gg-pic{display:block}" in rm

    def test_js_attaches_poster_only_when_the_clip_shows(self):
        js = es.ESSAY_JS
        assert "v.poster=poster; box.classList.add('is-live')" in js
        # sync() returns under reduced motion before live(), so no poster is set.
        assert "function sync(){ if(RM.matches){ v.pause(); return; } live();" in js

    def test_js_plays_once_at_half_visible_and_holds(self):
        js = es.ESSAY_JS
        assert "v.loop=false" in js and "intersectionRatio>=0.5" in js and "b.hidden=false" in js

    @pytest.mark.parametrize("bad", [dict(sources=()), dict(phone_aspect="tall"), dict(phone_position="0;x:y")])
    def test_video_validation(self, bad):
        with pytest.raises(ValueError):
            self._video(**bad)


class TestFigurePlacement:
    def test_marker(self):
        html = es.render_editorial_page(_meta(), FIG_BODY, figures=[es.EssayFigure(_pic(), marker="one")])
        main = _main(html)
        assert "GG:FIGURE" not in main
        assert main.index("List anchor") < main.index("gg-essay-fig") < main.index('<h2 id="second"')

    def test_after_paragraph_and_list(self):
        body = FIG_BODY.replace("<!--GG:FIGURE one-->", "")
        out = es.place_figures(body, [es.EssayFigure(_pic(), id="f1", after="anchor here."),
                                      es.EssayFigure(_pic(), id="f2", after="List anchor")])
        assert out.index("anchor here.</p>") < out.index('id="f1"') < out.index("<ul>")
        assert out.index("</ul>") < out.index('id="f2"')

    @pytest.mark.parametrize("body,after", [
        ("<ul><li><p>Item anchor.</p></li><li>Next</li></ul>\n<p>After.</p>", "Item anchor."),
        ("<blockquote><p>Quote anchor.</p><p>More.</p></blockquote>\n<p>After.</p>", "Quote anchor."),
        ("<h2>Heading anchor</h2>\n<p>After.</p>", "Heading anchor"),
        ("<ol><li>One <em>emph anchor</em></li></ol>\n<p>After.</p>", "emph anchor"),
    ])
    def test_after_lands_after_the_enclosing_block(self, body, after):
        out = es.place_figures(body, [es.EssayFigure(_pic(), id="f", after=after)])
        before, rest = out.split('<figure class="gg-essay-fig" id="f">', 1)
        assert before.rstrip().endswith(("</ul>", "</blockquote>", "</h2>", "</ol>")), before
        assert rest.split("</figure>", 1)[1].lstrip().startswith("<p>After.</p>")

    def test_after_outside_any_block_raises(self):
        with pytest.raises(ValueError, match="not inside"):
            es.place_figures("<div>bare anchor</div>", [es.EssayFigure(_pic(), after="bare anchor")])

    @pytest.mark.parametrize("fig", [
        es.EssayFigure(_pic(), marker="nope"),
        es.EssayFigure(_pic(), after="not in the body"),
        es.EssayFigure(_pic(), after="<p>"),  # more than once
        es.EssayFigure(_pic()),  # no anchor
        es.EssayFigure(_pic(), marker="one", after="Two."),  # both
    ])
    def test_bad_anchors_raise(self, fig):
        with pytest.raises(ValueError):
            es.place_figures(FIG_BODY, [fig, es.EssayFigure(_pic(), marker="one")] if fig.marker != "one" else [fig])

    def test_unclaimed_marker_raises(self):
        with pytest.raises(ValueError, match="without a figure"):
            es.render_editorial_page(_meta(), FIG_BODY, figures=[es.EssayFigure(_pic(), after="Two.")])

    def test_reading_time_ignores_figures(self):
        plain = es.render_editorial_page(_meta(), FIG_BODY.replace("<!--GG:FIGURE one-->", ""))
        with_fig = es.render_editorial_page(_meta(), FIG_BODY, figures=[_table()])
        by = lambda h: re.search(r'<p class="by">(.*?)</p>', h).group(1)  # noqa: E731
        assert by(plain) == by(with_fig)


class TestDataTable:
    def test_default_sort_and_aria(self):
        out = es.render_data_table(_table())
        assert '<th scope="col" data-type="num" aria-sort="ascending"><button type="button">Year' in out
        assert out.count("aria-sort") == 1
        tbody = out.split("<tbody>", 1)[1]
        assert tbody.index("a result") < tbody.index("b result")  # 2007 before 2019

    def test_blank_cells_are_dashes_and_sort_last(self):
        out = es.render_data_table(_table())
        assert '<td class="num" data-v=""><span class="na">&mdash;</span></td>' in out
        assert "if(!x||!y) return" in es.ESSAY_JS

    def test_sort_values_strip_citations_and_entities(self):
        col = es.TableColumn("Study")
        assert es._sort_value(col, es.TableCell('St&ouml;ggl &amp; S. <sup><a href="#r">10</a></sup>')) == "Stöggl & S."

    def test_cards_and_per_row_links(self):
        out = es.render_data_table(_table())
        cards = out.split('<ol class="gg-cards"', 1)[1]
        assert cards.count('<li class="gg-card">') == 2
        assert '<span class="gg-card-aside">2007</span>' in cards
        assert "<dt>n</dt><dd>12<span class=\"who\">cyclists</span></dd>" in cards
        for part in (out.split("<tbody>", 1)[1].split("</tbody>", 1)[0], cards):
            assert part.count('class="gg-cite"') == 2
            assert 'href="https://x.test/1/" target="_blank" rel="noopener" aria-label="Abstract (ref 1)">abstract</a>' in part

    def test_sort_hint_only_when_a_column_sorts(self):
        assert 'class="gg-sort-hint">Click a column to sort.' in es.render_data_table(_table())
        cols = tuple(es.TableColumn(c.label, kind=c.kind, card=c.card, sortable=False) for c in _table().columns)
        out = es.render_data_table(_table(columns=cols, sort_by=None))
        assert "gg-sort-hint" not in out and "<button" not in out

    def test_live_region_and_phone_css(self):
        out = es.render_data_table(_table())
        assert 'aria-live="polite" data-sort-status' in out
        phone = es.ESSAY_CSS.split("/* sortable table", 1)[1].split("/* chart draw-in", 1)[0]
        assert ".gg-table-wrap,.gg-sort-hint{display:none}" in phone and ".gg-table .gg-cards{display:block" in phone

    @pytest.mark.parametrize("bad", [
        dict(rows=(es.TableRow((es.TableCell("x"),)),)),
        dict(sort_by=9),
        dict(columns=(es.TableColumn("a"), es.TableColumn("b"), es.TableColumn("c"), es.TableColumn("d"))),
        dict(id=""),
    ])
    def test_validation(self, bad):
        with pytest.raises(ValueError):
            _table(**bad)


class TestSvgFigure:
    SVG = '<svg viewBox="0 0 10 10"><title>T</title></svg>'

    def test_with_phone_overview(self):
        out = es.render_svg_figure(es.SvgFigure(id="fig-g", svg=self.SVG, phone_svg=self.SVG, title="Graph",
                                                kicker="Evidence", caption_html="Cap", detail_min_width=700))
        assert out.startswith('<figure class="gg-svgfig gg-fig has-mini" id="fig-g" aria-labelledby="fig-g-h">')
        assert 'aria-expanded="false" aria-controls="fig-g-detail"' in out
        assert '<div class="gg-svg-detail" id="fig-g-detail" tabindex="0" role="region"' in out
        assert "--svg-min:700px" in out and "<figcaption>Cap</figcaption>" in out

    def test_without_overview_no_toggle_no_js(self):
        fig = es.SvgFigure(id="fig-g", svg=self.SVG, marker="one")
        assert "gg-svg-zoom" not in es.render_svg_figure(fig)
        assert es.ESSAY_JS_MARKER not in es.render_editorial_page(_meta(), FIG_BODY, figures=[fig])

    def test_validation(self):
        with pytest.raises(ValueError):
            es.SvgFigure(id="", svg=self.SVG)
        with pytest.raises(ValueError):
            es.SvgFigure(id="x", svg="<div></div>")


class TestDrawIn:
    def test_complete_at_rest(self):
        # Only .is-armed (added by JS while off-screen) hides anything.
        hiding = re.findall(r"([^{}]*)\{(?:transform:scale[XY]\(0\)|opacity:0|clip-path:inset\(0 100% 0 0\))\}", es.ESSAY_CSS)
        hiding = [sel for sel in hiding if sel.strip() not in ("from", "to")]  # keyframes
        assert hiding and all(".is-armed" in sel for sel in hiding)

    def test_plays_once_and_respects_reduced_motion(self):
        js = es.ESSAY_JS
        assert "intersectionRatio>=0.15" in js and "threshold:[0,0.15]" in js
        assert "io.disconnect()" in js and "RM.matches" in js
        assert "[data-draw-in] [data-draw]{animation:none!important" in es.ESSAY_CSS

    def test_prints_the_finished_chart(self):
        # An armed (off-screen) chart must not print blank.
        css = es.ESSAY_CSS.split("@media print{", 1)[1].split("\n}", 1)[0]
        assert ("[data-draw-in] [data-draw]{animation:none!important;transform:none!important;"
                "opacity:1!important;clip-path:none!important}") in css


class TestInShortOnPhone:
    CLAIMS = (es.Claim("A claim.", "#first-thing", "See it", 0),)

    def test_after_intro(self):
        html = es.render_editorial_page(_meta(), BODY, in_short=self.CLAIMS, in_short_on_phone="after_intro")
        main = _main(html)
        assert main.count('class="inshort"') == 2
        assert main.index('class="slot slot-summary has-phone-copy"') < main.index("Intro paragraph")
        assert main.index("Intro paragraph") < main.index('class="slot slot-summary-m"') < main.index("<h2")
        assert ".slot-summary.has-phone-copy{display:none}" in html

    def test_default_is_unchanged(self):
        html = es.render_editorial_page(_meta(), BODY, in_short=self.CLAIMS)
        assert "slot-summary-m" not in _main(html) and "has-phone-copy" not in html

    def test_validated(self):
        with pytest.raises(ValueError):
            es.render_editorial_page(_meta(), BODY, in_short=self.CLAIMS, in_short_on_phone="bottom")


# ── The Sweet Spot article ────────────────────────────────────


MEMES = {
    sweet_spot: ("scooby-unmask", "clown-ftp", "spiderman-threshold", "midwit-sweet-spot", "same-picture",
                 "so-over-so-back", "virgin-sweetspot-chad-polarized", "gru-noob-gains", "panik-kalm-panik",
                 "four-horsemen", "drake-polarized", "gigachad-yes"),
    training_app: ("pov-mile-82", "look-inside", "drake-fit", "starter-pack-fueling", "uno-draw-25",
                   "pigeon-compliance"),
}


@pytest.mark.parametrize("source", ARTICLE_SOURCES, ids=lambda m: m.SLUG)
def test_memes_are_placed_after_their_paragraphs_with_their_files(source):
    """Each meme renders once, WebP only (no PNG shipped), with its phone crop,
    a real alt, lazy loading, and every file it references committed."""
    html = _main(source.OUTPUT_PATH.read_text(encoding="utf-8"))
    figs = [f for f in source.FIGURES if isinstance(f, es.EssayFigure) and "/memes/" in f.picture.src]
    names = [f.picture.src.split("/")[-1].removesuffix(".webp") for f in figs]
    assert sorted(names) == sorted(MEMES[source])
    for fig, name in zip(figs, names):
        tag = f'<img src="img/memes/{name}.webp" srcset="img/memes/{name}.webp 1x, img/memes/{name}@2x.webp 2x"'
        assert html.count(tag) == 1, name
        assert f'srcset="img/memes/{name}-m.webp 1x, img/memes/{name}-m@2x.webp 2x"' in html, name
        assert len(fig.picture.alt) > 60 and 'loading="lazy"' in html.split(tag, 1)[1].split(">", 1)[0]
        assert html.index(fig.after) < html.index(tag), name
        for p in fig.picture.files():
            assert p.endswith(".webp") and (source.OUTPUT_PATH.parent / p).is_file(), p
    memes_dir = source.OUTPUT_PATH.parent / "img" / "memes"
    assert sorted(f.name for f in memes_dir.iterdir()) == sorted(
        f"{n}{v}.webp" for n in names for v in ("", "@2x", "-m", "-m@2x"))


@pytest.mark.parametrize("source", ARTICLE_SOURCES, ids=lambda m: m.SLUG)
def test_committed_article_html_is_fresh(source):
    """Fails after a change to the shell, data/pricing.json, brand_tokens
    snippets, the consent banner or the logo: regenerate and commit."""
    assert source.OUTPUT_PATH.read_text(encoding="utf-8") == source.render(), (
        f"stale: run python3 wordpress/article_sources/{Path(source.__file__).name}"
    )


def test_every_article_source_is_covered():
    modules = {p.stem for p in (PROJECT_ROOT / "wordpress" / "article_sources").glob("*.py")}
    assert modules == {Path(m.__file__).stem for m in ARTICLE_SOURCES}


class TestSweetSpotArticle:

    def test_is_an_indexed_article(self):
        html = SWEET_SPOT_INDEX.read_text(encoding="utf-8")
        assert '<meta name="robots" content="index, follow">' in html
        assert '<link rel="canonical" href="https://gravelgodcycling.com/articles/sweet-spot-training-cycling/">' in html
        types = [json.loads(b)["@type"] for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        assert types == ["Article", "FAQPage"]

    def test_slots_and_figures(self):
        html = SWEET_SPOT_INDEX.read_text(encoding="utf-8")
        slots = re.findall(r'data-slot="([a-z]+)"', html)
        assert slots == ["summary", "drift", "recovery", "polarized", "ladder"]
        # Every "In short" link resolves to an anchor on the page.
        for href in re.findall(r'<a class="ev" href="#([^"]+)"', html):
            assert f'id="{href}"' in html, href
        # Ladder sits right before the G-Spot section.
        main = _main(html).split('id="article">', 1)[1]
        assert main.index("slot-ladder") < main.index("That Said, G-Spot") < main.index("gg-references")

    def test_all_images_exist(self):
        html = SWEET_SPOT_INDEX.read_text(encoding="utf-8")
        for src in set(re.findall(r'<img src="(img/[^"]+)"', html)):
            assert (SWEET_SPOT_INDEX.parent / src).exists(), src

    def test_contents_has_eight_sections(self):
        html = SWEET_SPOT_INDEX.read_text(encoding="utf-8")
        rail = html.split('<nav class="rail"', 1)[1].split("</nav>", 1)[0]
        assert rail.count("<li>") == 8

    def test_every_figure_asset_exists(self):
        paths = list(sweet_spot.SCENE_TOMBSTONE.files())
        for fig in sweet_spot.FIGURES:
            if isinstance(fig, sweet_spot.EssayFigure):
                paths += fig.picture.files()
                if fig.video:
                    paths += [s for s, _ in fig.video.sources] + [fig.video.poster]
        assert len(paths) == 21 + 12 * 4  # scenes + twelve memes (1x, 2x, phone 1x/2x WebP)
        for p in paths:
            assert (sweet_spot.IMG_DIR.parent / p).is_file(), p

    def test_scenes_replace_the_old_illustrations(self):
        main = _main(SWEET_SPOT_INDEX.read_text(encoding="utf-8"))
        for old in ("black-hole.jpg", "g-spot-tablet.jpg", "sweet-spot-rip.png", 'src="img/unitless-graph.png"'):
            assert old not in main, old
        assert main.count("<picture") == 3 + 12 and main.count("<video") == 1  # 3 scenes + 12 memes
        assert '<figure class="gg-svgfig gg-fig has-mini" id="fig-graph"' in main
        assert "data-draw-in" in main.split('id="fig-drift"', 1)[1].split(">", 1)[0]

    def test_og_image_is_the_tombstone_crop(self):
        html = SWEET_SPOT_INDEX.read_text(encoding="utf-8")
        assert f'<meta property="og:image" content="{sweet_spot.URL}img/og-tombstone.jpg">' in html
        assert '<meta property="og:image:width" content="1200">' in html
        assert '<meta property="og:image:height" content="630">' in html
        og = SWEET_SPOT_INDEX.parent / "img/og-tombstone.jpg"
        assert og.is_file() and og.stat().st_size <= 200_000
        assert og.read_bytes()[:3] == b"\xff\xd8\xff"  # JPEG

    def test_studies_table(self):
        main = _main(SWEET_SPOT_INDEX.read_text(encoding="utf-8"))
        table = main.split('id="fig-studies"', 1)[1].split("</figure>", 1)[0]
        tbody = table.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        years = re.findall(r'<td class="num" data-v="(\d{4})">', tbody)
        assert years == ["2007", "2013", "2014", "2019", "2025"]
        assert tbody.count("pubmed.ncbi.nlm.nih.gov") == 5 and table.count('<li class="gg-card">') == 5
        for ref in range(9, 14):
            assert f'href="#ref-{ref}"' in tbody
        # The studies sit in "Polarized Training is Just Better", before the polarized figure.
        assert main.index("Polarized Training is Just Better") < main.index('id="fig-studies"') < main.index('id="fig-polarized"')

    def test_body_copy_is_the_source_file(self):
        html = SWEET_SPOT_INDEX.read_text(encoding="utf-8")
        body = sweet_spot.BODY_PATH.read_text(encoding="utf-8")
        for para in re.findall(r"<(p|li|h2|h3)>(.*?)</\1>", body, re.S):
            assert para[1] in html

    def test_in_short_after_intro_on_phones(self):
        main = _main(SWEET_SPOT_INDEX.read_text(encoding="utf-8"))
        assert main.index("time machine") < main.index("slot-summary-m") < main.index('<h2 id="what-is-the-sweet-spot')


# ── Your Training App Doesn't Know Your Race Exists ───────────


class TestTrainingAppArticle:
    @pytest.fixture(scope="class")
    def html(self) -> str:
        return TRAINING_APP_INDEX.read_text(encoding="utf-8")

    def test_is_an_indexed_article_with_events(self, html):
        assert '<meta name="robots" content="index, follow">' in html
        assert f'<link rel="canonical" href="{training_app.URL}">' in html
        assert "'article_slug': \"your-training-app-doesnt-know-your-race-exists\"" in html
        assert "July 2, 2026" in html

    def test_in_short_and_ladder(self, html):
        main = _main(html)
        # In short opens the essay; every claim links to an h2 on the page.
        assert main.count('class="slot slot-summary"') == 1
        assert main.index("slot-summary") < main.index("<h2 id=\"first-the-part")
        hrefs = re.findall(r'<a class="ev" href="#([^"]+)"', main)
        assert len(hrefs) == len(training_app.IN_SHORT) == 4
        for href in hrefs:
            assert f'<h2 id="{href}"' in main, href
        assert main.count('class="slot slot-ladder"') == 1
        # No references: the ladder closes the essay, after the mid subscribe callout.
        assert main.index("Compliance Score") < main.index("gg-subscribe-callout") < main.index("slot-ladder")
        assert "gg-references" not in main

    def test_sweet_spot_leftovers_are_gone(self, html):
        main = _main(html)
        for gone in ("It Makes You Slow", "Noob Gains", "Polarized Training is Just Better",
                     "G-Spot is Better", ">References<", "Seiler"):
            assert gone not in main, gone
        last_h2 = re.findall(r"<h2[^>]*>(.*?)</h2>", main)[-1]
        assert last_h2 == "The Start Line Doesn&rsquo;t Care About Your Compliance Score"

    def test_og_image_is_the_look_inside_crop(self, html):
        assert f'<meta property="og:image" content="{training_app.URL}img/og-look-inside.jpg">' in html
        assert '<meta property="og:image:width" content="1200">' in html
        assert '<meta property="og:image:height" content="630">' in html
        og = TRAINING_APP_INDEX.parent / "img/og-look-inside.jpg"
        assert og.is_file() and og.stat().st_size <= 200_000
        assert og.read_bytes()[:3] == b"\xff\xd8\xff"  # JPEG
        from PIL import Image
        with Image.open(og) as im:
            assert im.size == (1200, 630)

    def test_json_ld_is_this_article(self, html):
        blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
        assert [b["@type"] for b in blocks] == ["Article"]
        ld = blocks[0]
        assert ld["headline"] == "Your Training App Doesn't Know Your Race Exists"
        assert ld["description"] == training_app.META.og_description
        assert f'<meta property="og:description" content="{ld["description"]}">' in html
        assert (ld["datePublished"], ld["dateModified"]) == ("2026-07-02", "2026-10-08")
        assert ld["mainEntityOfPage"] == training_app.URL
        assert "keywords" not in ld and "citation" not in ld

    def test_body_is_the_source_file(self, html):
        body = training_app.BODY_PATH.read_text(encoding="utf-8")
        # Every paragraph of the source survives into the page unchanged.
        for para in re.findall(r"<p>(.*?)</p>", body, re.S):
            assert para in html

    def test_old_chrome_is_gone(self, html):
        for old in ("gg-blog-container", "gg-blog-cta", "gg-blog-footer", "gg-blog-hero"):
            assert old not in html

    def test_contents(self, html):
        rail = html.split('<nav class="rail"', 1)[1].split("</nav>", 1)[0]
        assert rail.count("<li>") == 5


# ── Shell nits: opted-out h2s, dash-rule paragraphs ───────────


class TestNoTocAndDashRules:
    def test_data_no_toc_h2_is_not_a_contents_heading_and_does_not_warn(self):
        import warnings as _w
        body = ('<section class="gg-blog-section"><h2>One</h2><p>x</p></section>\n'
                '<section class="gg-comments"><h2 id="comments-h" data-no-toc>Comments</h2></section>')
        out, toc = es.add_heading_ids(body)
        assert [label for _, label in toc] == ["One"]
        assert '<h2 id="comments-h" data-no-toc>Comments</h2>' in out
        with _w.catch_warnings():
            _w.simplefilter("error")
            es.add_heading_ids('<p>short post</p><section class="gg-comments"><h2 data-no-toc>Comments</h2></section>')
        with pytest.warns(UserWarning):
            es.add_heading_ids('<p>short post</p><section class="gg-comments"><h2>Comments</h2></section>')
        inside = '<section class="gg-blog-section"><h2>One</h2><h2 data-no-toc>Aside</h2></section>'
        assert [label for _, label in es.add_heading_ids(inside)[1]] == ["One"]

    def test_dash_only_paragraphs_get_the_wrap_class_text_unchanged(self):
        run = "\u2014" * 26
        body = f'<p>{run}</p><p class="x">{run}-</p><p>A sentence \u2014 with a dash.</p><p>\u2014\u2014</p>'
        out = es.mark_dash_rules(body)
        assert f'<p class="gg-dashrule">{run}</p>' in out
        assert f'<p class="x gg-dashrule">{run}-</p>' in out
        assert "<p>A sentence \u2014 with a dash.</p>" in out and "<p>\u2014\u2014</p>" in out
        assert re.sub(r"<[^>]+>", "", out) == re.sub(r"<[^>]+>", "", body)
        assert ".article p.gg-dashrule{overflow-wrap:anywhere}" in es.SHELL_CSS
