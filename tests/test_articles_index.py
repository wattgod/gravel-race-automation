"""The essay listing, gravelgodcycling.com/articles/ (wordpress/generate_articles_index.py)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))

import generate_articles_index as gai  # noqa: E402
from brand_tokens import get_ga4_head_snippet  # noqa: E402
from cookie_consent import get_consent_banner_html  # noqa: E402
from editorial_shell import render_footer, render_header  # noqa: E402

SITE = "https://gravelgodcycling.com"


@pytest.fixture(scope="module")
def page() -> str:
    return gai.render()


def _cards(html: str) -> list[str]:
    return re.findall(r'<a class="gg-ai-card[^"]*" href="[^"]*">.*?</a>', html, re.S)


def _page(headline: str, dek: str, og: str, minutes: int) -> str:
    """A minimal committed essay page in editorial-shell markup."""
    return (
        f'<meta property="og:image" content="{og}">\n'
        '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
        f'<h1>{headline}</h1>\n<p class="dek">{dek}</p>\n'
        f'<p class="by">Gravel God &middot; May 1, 2027 &middot; {minutes} min read</p>'
    )


def _write(tmp_path: Path, entries: list[dict], pages: dict[str, str] | None = None) -> tuple[Path, Path]:
    index = tmp_path / "blog-index.json"
    index.write_text(json.dumps(entries), encoding="utf-8")
    articles = tmp_path / "articles"
    for slug, html in (pages or {}).items():
        (articles / slug).mkdir(parents=True)
        (articles / slug / "index.html").write_text(html, encoding="utf-8")
    articles.mkdir(exist_ok=True)
    return index, articles


def _entry(slug: str, day: str, **kw) -> dict:
    return {"slug": slug, "category": "article", "date": day, "url": f"/articles/{slug}/",
            "title": f"{slug} | Gravel God", "excerpt": f"{slug} excerpt", "og_image": "", **kw}


# ── The committed page ────────────────────────────────────────


def test_committed_listing_is_fresh(page):
    """Fails after a change to blog-index.json, a committed essay page, the
    shell, brand_tokens, the consent banner or the header: regenerate with
    python3 wordpress/generate_articles_index.py and commit."""
    assert gai.OUTPUT_PATH.read_text(encoding="utf-8") == page


def test_every_article_in_blog_index_has_a_card(page):
    urls = [e["url"] for e in json.loads(gai.INDEX_JSON.read_text()) if e.get("category") == "article"]
    hrefs = [re.search(r'href="([^"]*)"', c).group(1) for c in _cards(page)]
    assert sorted(hrefs) == sorted(urls)
    assert 'href=""' not in page


def test_sweet_spot_card_uses_its_current_og_image(page):
    card = next(c for c in _cards(page) if "/articles/sweet-spot-training-cycling/" in c)
    assert f'src="{SITE}/articles/sweet-spot-training-cycling/img/og-tombstone.jpg"' in card
    assert "sweet-spot-rip.png" not in page


def test_training_app_card_uses_look_inside(page):
    card = next(c for c in _cards(page) if "/articles/your-training-app-doesnt-know-your-race-exists/" in c)
    assert f'src="{SITE}/articles/your-training-app-doesnt-know-your-race-exists/img/og-look-inside.jpg"' in card


def test_card_matches_its_essay_page(page):
    """Headline, dek, image and reading time come from the committed essay."""
    for essay in gai.load_essays():
        src = (gai.ARTICLES_DIR / essay.slug / "index.html").read_text(encoding="utf-8")
        assert re.search(rf'<meta property="og:image" content="{re.escape(essay.og_image)}">', src)
        assert f"{essay.minutes} min read" in src
        card = next(c for c in _cards(page) if f'href="{essay.url}"' in c)
        assert f">{gai.esc(essay.headline)}</h2>" in card
        assert gai.esc(essay.dek) in card
        assert 'width="1200" height="630"' in card
        assert "| Gravel God" not in card


def test_newest_essay_leads(page):
    essays = gai.load_essays()
    assert [e.published for e in essays] == sorted((e.published for e in essays), reverse=True)
    lead = _cards(page)[0]
    assert 'class="gg-ai-card gg-ai-lead"' in lead and f'href="{essays[0].url}"' in lead
    assert sum('gg-ai-lead' in c for c in _cards(page)) == 1


def test_head_metadata_carried_over(page):
    for tag in (
        '<meta name="robots" content="index, follow">',
        "<title>Articles — Gravel God Cycling</title>",
        '<meta name="description" content="In-depth articles on gravel cycling training, nutrition, and race strategy from Gravel God.">',
        '<meta property="og:title" content="Articles — Gravel God Cycling">',
        '<meta property="og:description" content="In-depth articles on gravel cycling training, nutrition, and race strategy.">',
        f'<meta property="og:url" content="{SITE}/articles/">',
        '<meta property="og:type" content="website">',
        f'<link rel="canonical" href="{SITE}/articles/">',
    ):
        assert tag in page, tag
    assert page.count('rel="canonical"') == 1
    assert page.count('name="robots"') == 1


def test_analytics_and_consent_as_the_essays(page):
    assert get_ga4_head_snippet().strip() in page
    assert page.index("gtag('consent','default'") < page.index("googletagmanager.com/gtag/js")
    assert page.rstrip().endswith(get_consent_banner_html().strip() + "\n</body>\n</html>")
    assert 'id="gg-privacy-choices"' in page


def test_listing_does_not_fire_article_events(page):
    assert "article_scroll_depth" not in page
    assert "article_deep_read" not in page


def test_shell_header_and_footer(page):
    assert render_header("articles") in page
    assert render_footer() in page
    assert 'aria-current="page"' in page  # Articles is the current nav item
    assert "getElementById('gg-hamburger')" in page


# Every link on the pre-shell live page (fetched 2026-10-10), minus its
# href="" bug. None may go missing; same-site links compare by path (the old
# mega footer wrote /cookies/ etc. absolute, the shell's legal footer relative).
PRE_SHELL_LINKS = (
    "/articles/sweet-spot-training-cycling/",
    "/articles/your-training-app-doesnt-know-your-race-exists/",
    "/cookies/", "/privacy/", "/terms/",
    f"{SITE}/", f"{SITE}/about/", f"{SITE}/articles/", f"{SITE}/coaching/", f"{SITE}/consulting/",
    f"{SITE}/cookies/", f"{SITE}/course/", f"{SITE}/fueling-methodology/", f"{SITE}/gravel-races/",
    f"{SITE}/guide/", f"{SITE}/insights/", f"{SITE}/privacy/", f"{SITE}/products/training-plans/",
    f"{SITE}/race/methodology/", f"{SITE}/terms/", "https://gravelgodcycling.substack.com",
)


@pytest.mark.parametrize("href", PRE_SHELL_LINKS)
def test_no_link_lost(page, href):
    def norm(h: str) -> str:
        return h[len(SITE):] if h.startswith(SITE + "/") else h
    assert norm(href) in {norm(h) for h in re.findall(r'href="([^"]*)"', page)}


def test_no_hardcoded_essays_in_generator():
    src = Path(gai.__file__).read_text(encoding="utf-8")
    for e in json.loads(gai.INDEX_JSON.read_text()):
        if e.get("category") == "article":
            assert e["slug"] not in src


def test_listing_frame_is_1200(page):
    assert re.search(r"\.gg-ai-page\{max-width:1200px", page)


# ── Data rules (future essays need no code change) ────────────


def test_new_essay_appears_first_with_no_code_change(tmp_path):
    index, articles = _write(
        tmp_path,
        [_entry("older", "2026-03-26"), _entry("brand-new", "2027-05-01")],
        {"brand-new": _page("Brand &amp; New", "A dek.", f"{SITE}/articles/brand-new/img/og.jpg", 7)},
    )
    with pytest.warns(UserWarning, match="older"):
        essays = gai.load_essays(index, articles)
    assert [e.slug for e in essays] == ["brand-new", "older"]
    new = essays[0]
    assert (new.headline, new.dek, new.minutes, new.og_width) == ("Brand & New", "A dek.", 7, 1200)
    html = gai.render_articles_index(essays)
    lead = _cards(html)[0]
    assert 'href="/articles/brand-new/"' in lead and "Brand &amp; New</h2>" in lead
    assert '<time datetime="2027-05-01">May 1, 2027</time> &middot; 7 min read' in lead


def test_fallback_without_committed_page(tmp_path):
    index, articles = _write(tmp_path, [_entry("legacy", "2026-01-02", og_image=f"{SITE}/x.jpg")])
    with pytest.warns(UserWarning):
        (e,) = gai.load_essays(index, articles)
    assert (e.headline, e.dek, e.og_image, e.minutes) == ("legacy", "legacy excerpt", f"{SITE}/x.jpg", None)
    card = gai.render_card(e)
    assert "min read" not in card and 'src="https://gravelgodcycling.com/x.jpg"' in card
    assert "width=" not in card  # no size known: don't invent one


def test_card_without_image(tmp_path):
    index, articles = _write(tmp_path, [_entry("noimg", "2026-01-02")])
    with pytest.warns(UserWarning):
        (e,) = gai.load_essays(index, articles)
    assert "<img" not in gai.render_card(e)


def test_non_articles_are_ignored(tmp_path):
    index, articles = _write(tmp_path, [{"slug": "p", "category": "preview", "url": "/blog/p/", "date": "x"}])
    assert gai.load_essays(index, articles) == []
    assert '<p class="gg-ai-empty">More articles coming soon.</p>' in gai.render_articles_index([])


@pytest.mark.parametrize("bad", [{"url": ""}, {"url": "/articles/"}, {"url": "/blog/x/"}, {"date": ""}, {"date": "July 2"}])
def test_broken_entry_stops_the_build(tmp_path, bad):
    index, articles = _write(tmp_path, [{**_entry("x", "2026-01-02"), **bad}])
    with pytest.raises(ValueError):
        gai.load_essays(index, articles)


def test_invalid_json_is_not_swallowed(tmp_path):
    index = tmp_path / "blog-index.json"
    index.write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        gai.load_essays(index, tmp_path)


def test_text_is_escaped(tmp_path):
    index, articles = _write(tmp_path, [_entry("x", "2026-01-02", title='<b>"x"</b> | Gravel God',
                                               excerpt="a < b & c")])
    with pytest.warns(UserWarning):
        (e,) = gai.load_essays(index, articles)
    card = gai.render_card(e)
    assert "&lt;b&gt;&quot;x&quot;&lt;/b&gt;" in card and "a &lt; b &amp; c" in card
