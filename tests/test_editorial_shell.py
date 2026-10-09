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
from brand_tokens import (  # noqa: E402
    get_favicon_head_snippet,
    get_font_face_css,
    get_ga4_head_snippet,
    get_preload_hints,
)
from cookie_consent import get_consent_banner_html  # noqa: E402

SWEET_SPOT_INDEX = PROJECT_ROOT / "wordpress" / "articles" / "sweet-spot-training-cycling" / "index.html"

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
        assert '<h2 id="kept">' in body  # existing id preserved

    def test_references_left_out(self):
        _, toc = es.add_heading_ids(BODY)
        assert "References" not in [label for _, label in toc]

    def test_contents_rendered_twice_rail_and_bar(self, page):
        assert page.count('<ol class="toc">') == 2
        assert 'href="#first-thing-2"' in page

    def test_contents_can_be_hidden(self):
        html = es.render_editorial_page(_meta(), BODY, contents=False)
        assert 'class="toc"' not in html and 'class="rail"' not in html


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
        links = re.findall(r'<a class="btn" href="([^"]+)" data-event="article_cta_click" data-label="([^"]+)">', ladder)
        assert links == [
            ("/products/training-plans/", "custom_plan"),
            ("/season-plan/", "season_plan"),
            ("/coaching/", "coaching"),
        ]


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

    def test_consent_banner_and_legal_links(self, page):
        assert get_consent_banner_html() in page
        assert 'href="/privacy/"' in page and 'href="/terms/"' in page

    def test_header_nav_and_subscribe(self, page):
        header = page.split('<header class="site">', 1)[1].split("</header>", 1)[0]
        for href in ("/gravel-races/", "/products/training-plans/", "/coaching/", "/articles/", "/about/"):
            assert f'href="{href}"' in header
        assert "gravelgodcycling.substack.com" in header

    def test_no_inline_handlers(self, page):
        assert not re.search(r"\son[a-z]+=", page)

    def test_hero_byline_and_reading_time(self, page):
        assert "Gravel God &middot; March 26, 2026 &middot; 1 min read" in page

    def test_no_hero_image(self, page):
        assert 'class="frame hero no-img"' in page
        assert "hero-img" not in page.split("<main>", 1)[1].split("</main>", 1)[0]


# ── The Sweet Spot article ────────────────────────────────────


class TestSweetSpotArticle:
    def test_committed_html_is_fresh(self):
        assert SWEET_SPOT_INDEX.read_text(encoding="utf-8") == sweet_spot.render(), (
            "stale: run python3 wordpress/article_sources/sweet_spot_training_cycling.py"
        )

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
