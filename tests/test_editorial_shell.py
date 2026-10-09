"""Editorial shell (wordpress/editorial_shell.py) and the Sweet Spot article built on it."""
from __future__ import annotations

import json
import re
import sys
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
        assert {"custom_plan", "coaching"} <= caught


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


# ── The Sweet Spot article ────────────────────────────────────


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

    def test_ladder_no_in_short(self, html):
        main = _main(html)
        assert "slot-summary" not in main
        assert main.count('class="slot slot-ladder"') == 1
        assert main.index("slot-ladder") < main.index("gg-references")

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
        assert rail.count("<li>") == 9
