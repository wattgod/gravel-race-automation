"""WordPress post importer (scripts/wp_post_import.py) and imported posts (wordpress/wp_post.py).

Fixtures in tests/fixtures/wp_posts/ (from the 2026-10-09 WP audit):
  <id>.html            the post's rendered Elementor content (the converter input)
  <id>.txt             its visible text: the word-for-word baseline
  <id>.record.json     the inventory record (slug, images, featured image)
  <id>.live-head.html  the live page's <head> tags the converter reads
"""
from __future__ import annotations

import dataclasses
import importlib
import json
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "wp_posts"
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
sys.path.insert(0, str(PROJECT_ROOT / "wordpress" / "post_sources"))

import editorial_shell as es  # noqa: E402
import wp_post  # noqa: E402
import wp_post_import as imp  # noqa: E402
from brand_tokens import get_ga4_head_snippet  # noqa: E402

# post id -> (module, ids of figures the module ADDS: excluded from the text diff)
PILOTS = {
    3504: ("i_screwed_up_foco_fondo_so_you_dont_have_to", set()),
    2592: ("the_double_day_3_yield_to_tonnage", {"fig-rte66-stats"}),
    2161: ("how_to_manage_dopamine_to_be_a_better_cyclist", set()),
}
IMPORT_ARGS = {3504: {"asides": ("Sidebar",)}}


def _module(pid):
    return importlib.import_module(PILOTS[pid][0])


def _page(pid) -> str:
    return _module(pid).OUTPUT_PATH.read_text(encoding="utf-8")


# ── The three pilots ─────────────────────────────────────────


@pytest.mark.parametrize("pid", PILOTS)
def test_body_text_is_word_for_word(pid):
    """The committed page's article text equals the WordPress snapshot, word for word
    (shell additions, infographics and comments excluded)."""
    diff = imp.text_diff((FIXTURES / f"{pid}.txt").read_text(encoding="utf-8"), _page(pid), PILOTS[pid][1])
    assert diff == [], "\n".join(diff[:80])


def test_text_diff_catches_a_changed_word():
    page = _page(2592).replace("Toasters make life better.", "Toasters make life worse.", 1)
    diff = imp.text_diff((FIXTURES / "2592.txt").read_text(encoding="utf-8"), page, PILOTS[2592][1])
    assert "-better." in diff and "+worse." in diff


@pytest.mark.parametrize("pid", PILOTS)
def test_converter_reproduces_committed_body_and_metadata(pid):
    record = json.loads((FIXTURES / f"{pid}.record.json").read_text(encoding="utf-8"))
    conv, data = imp.import_post(record, (FIXTURES / f"{pid}.html").read_text(encoding="utf-8"),
                                 (FIXTURES / f"{pid}.live-head.html").read_text(encoding="utf-8"),
                                 **IMPORT_ARGS.get(pid, {}))
    src = _module(pid).SOURCE
    assert conv.body_html == src.body
    assert data["live"] == src.data["live"]
    assert [f["name"] for f in data["figures"]] == [f["name"] for f in src.data["figures"]]


@pytest.mark.parametrize("pid", PILOTS)
def test_committed_page_is_fresh(pid):
    m = _module(pid)
    assert m.OUTPUT_PATH.read_text(encoding="utf-8") == m.render(), (
        f"stale: run python3 wordpress/post_sources/{m.__name__}.py")


def test_every_post_source_is_covered():
    modules = {p.stem for p in (PROJECT_ROOT / "wordpress" / "post_sources").glob("*.py")}
    assert modules == {m for m, _ in PILOTS.values()}


@pytest.mark.parametrize("pid", PILOTS)
def test_metadata_comes_from_the_live_page(pid):
    """Title, description, OG, canonical and date are the live page's (not REST/aioseo);
    the page lives at its original root URL."""
    m = _module(pid)
    live = m.SOURCE.data["live"]
    html = _page(pid)
    url = f"https://gravelgodcycling.com/{m.SLUG}/"
    assert live["canonical"] == url
    assert f'<link rel="canonical" href="{url}">' in html
    assert f"<title>{es.esc(live['title'])}</title>" in html
    assert f'<meta name="description" content="{es.esc(live["description"])}">' in html
    assert f'<meta property="og:title" content="{es.esc(live["og_title"])}">' in html
    assert f'<meta property="og:image" content="{es.esc(live["og_image"]["url"])}">' in html
    assert '<meta name="robots" content="index, follow, max-image-preview:large">' in html
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert [b["@type"] for b in ld] == ["BlogPosting"]
    assert ld[0]["headline"] == live["headline"] and ld[0]["datePublished"] == live["published"]
    assert ld[0]["mainEntityOfPage"] == url
    assert m.OUTPUT_PATH == PROJECT_ROOT / "wordpress" / "posts" / m.SLUG / "index.html"


def test_no_hero_when_the_featured_image_is_also_inline():
    """Double Day 3's featured image is a byte-identical copy of its first image."""
    html = _page(2592)
    assert 'class="frame hero no-img"' in html and html.count('src="img/ut-pa-baeretur-1.webp"') == 1
    assert 'class="frame hero wide"' in _page(3504)


def test_byline_date_is_the_sites_local_date():
    """2022-04-23T01:08Z was the evening of April 22 in Colorado."""
    assert "April 22, 2022" in _page(2592)


@pytest.mark.parametrize("pid", PILOTS)
def test_analytics_and_consent_as_on_the_essays(pid):
    html = _page(pid)
    assert get_ga4_head_snippet().strip() in html
    assert "article_scroll_depth" in html and "article_deep_read" in html
    assert 'id="gg-consent-banner"' in html or "gg-consent" in html
    assert "onclick=" not in html


@pytest.mark.parametrize("pid", PILOTS)
def test_every_image_has_alt_text_and_committed_files(pid):
    m = _module(pid)
    html = _page(pid)
    names = [f["name"] for f in m.SOURCE.data["figures"]]
    feat = m.SOURCE.data["featured"]
    if feat and not feat["also_inline"]:
        names.append(feat["name"])
    assert sorted(m.ALT) == sorted(names)
    for name, alt in m.ALT.items():
        assert len(alt) >= 40, name
    img_dir = m.OUTPUT_PATH.parent / "img"
    referenced = set(re.findall(r'(?:src|srcset|data-poster)="(img/[^" ]+)', html))
    referenced |= set(re.findall(r", (img/[^ ]+) 2x", html))
    for path in referenced:
        assert (m.OUTPUT_PATH.parent / path).is_file(), path
    shipped = {p.suffix for p in img_dir.iterdir()}
    assert shipped <= {".webp", ".mp4", ".webm"}, "no PNG/JPEG/GIF ships; WebP + video only"


@pytest.mark.parametrize("pid", PILOTS)
def test_gifs_are_muted_play_once_videos(pid):
    m = _module(pid)
    html = _page(pid)
    for f in m.SOURCE.data["figures"]:
        if f["kind"] != "gif":
            continue
        n = f["name"]
        assert f'<source src="img/{n}.webm" type="video/webm"><source src="img/{n}.mp4" type="video/mp4">' in html
        tag = html.split(f'<source src="img/{n}.webm"', 1)[0].rsplit("<video", 1)[1]
        assert "muted playsinline" in tag and 'preload="none"' in tag and "autoplay" not in tag
    assert ".gif" not in re.sub(r"https://gravelgodcycling\.com/wp-content/[^\"' ]+", "", html)


@pytest.mark.parametrize("pid", PILOTS)
def test_in_short_drafts(pid):
    """2-4 claims, each at most 25 words, each linking to an anchor on the page."""
    m = _module(pid)
    html = _page(pid)
    assert 2 <= len(m.IN_SHORT) <= 4
    for c in m.IN_SHORT:
        words = re.sub(r"<[^>]+>", "", c.text_html).split()
        assert len(words) <= 25, c.text_html
        assert c.href.startswith("#") and f'id="{c.href[1:]}"' in html, c.href


def test_h6_only_post_gets_a_contents():
    html = _page(2592)
    assert '<nav class="rail" aria-label="Contents">' in html
    assert re.search(r'<h2 id="mediocre-power-reveal-inner-race-commentary" data-toc>', html)
    assert re.search(r'<h2 id="what-i-loved-about-today" data-toc>', html)


def test_foco_sidebar_is_an_aside_and_the_tweet_a_pull_quote():
    html = _page(3504)
    assert '<aside class="gg-case-study gg-sidebar" id="aside-sidebar">' in html
    assert '<figure class="gg-pullquote" id="pull-quote-1">' in html
    assert "Ben Delaney, lying through his teeth." in html


def test_phasic_chart_is_redrawn_with_the_original_kept():
    html = _page(2161)
    fig = html.split('id="fig-phasic"', 1)[1].split("</figure>", 1)[0]
    assert fig.count("<svg") == 2 and "data-draw=\"wipe\"" in fig
    assert '<details class="gg-original" data-gg-added>' in fig and "img/phasic.webp" in fig
    assert fig.count("<polyline") == 2


def test_dopamine_bars_use_the_posts_values_verbatim():
    m = _module(2161)
    body = m.SOURCE.body
    for label, text, _, _ in m.MULTIPLES:
        assert f"<li>{label} – {text}</li>" in body, label


def test_rte66_table_numbers_are_in_the_alt_of_the_gif():
    """Every number in the table is one the GIF shows (its alt text transcribes them)."""
    m = _module(2592)
    alt = m.ALT["bufz-doge-fuchs"]
    for row in m.RTE66_STATS.rows:
        for cell in (row.cells[1], row.cells[2], row.cells[3], row.cells[4]):
            assert cell.html.split()[0] in alt, cell.html


# ── Widget mapping (synthetic Elementor) ─────────────────────


def _w(wtype: str, inner: str, settings: str = "") -> str:
    s = f" data-settings='{settings}'" if settings else ""
    return (f'<div class="elementor-element elementor-widget" data-widget_type="{wtype}"{s}>'
            f'<div class="elementor-widget-container">{inner}</div></div>')


def _convert(*widgets: str, **kw) -> imp.Converted:
    return imp.ElementorConverter(**kw).convert("<section>" + "".join(widgets) + "</section>")


def test_heading_levels_map_to_h2_then_h3_text_unchanged():
    c = _convert(_w("heading.default", "<h5>Big <b>one</b></h5>"),
                 _w("text-editor.default", "<p>a</p><h6>small</h6><p>b</p>"),
                 _w("heading.default", "<h5>Next</h5>"))
    assert c.heading_map == {"h5": "h2", "h6": "h3"}
    assert "<h2>Big one</h2>" in c.body_html and "<h3>small</h3>" in c.body_html
    assert c.body_html.count('<section class="gg-blog-section">') == 2


def test_text_editor_keeps_lists_quotes_links_and_inline_marks():
    c = _convert(_w("text-editor.default",
                    '<p>Go <a href="https://x.test/" target="_blank">here</a>, <i>now</i>&nbsp;<span style="x">ok</span></p>'
                    "<ol><li>one</li><li>two <b>bold</b></li></ol><blockquote><p>quoted</p></blockquote>"))
    b = c.body_html
    assert '<a href="https://x.test/" target="_blank" rel="noopener">here</a>' in b
    assert "<em>now</em>" in b and "style=" not in b and "<span" not in b
    assert "<ol>\n<li>one</li>\n<li>two <strong>bold</strong></li>\n</ol>" in b
    assert "<blockquote>\n<p>quoted</p>\n</blockquote>" in b


def test_click_to_tweet_becomes_a_pull_quote():
    c = _convert(_w("blockquote.default",
                    '<blockquote class="elementor-blockquote"><p class="elementor-blockquote__content">Ride easy.</p>'
                    '<div class="e-q-footer"><cite class="elementor-blockquote__author">Matti</cite>'
                    '<a class="elementor-blockquote__tweet-button" href="https://twitter.com/intent/tweet">Tweet</a>'
                    "</div></blockquote>"))
    assert ('<figure class="gg-pullquote" id="pull-quote-1">\n  <blockquote><p>Ride easy.</p></blockquote>\n'
            "  <figcaption>Matti</figcaption>\n</figure>") in c.body_html
    assert "twitter.com" not in c.body_html


def test_galleries_become_a_figure_grid():
    g = ('<div class="gallery"><figure><a href="https://gravelgodcycling.com/wp-content/uploads/2023/04/a.png">'
         '<img data-src="https://gravelgodcycling.com/wp-content/uploads/2023/04/a-300x225.png"></a></figure>'
         '<figure><img src="https://gravelgodcycling.com/wp-content/uploads/2023/04/b-300x225.jpg"></figure></div>')
    pro = '<a class="e-gallery-item"><div class="e-gallery-image" data-thumbnail="https://gravelgodcycling.com/wp-content/uploads/2022/05/c-225x300.png"></div></a>'
    c = _convert(_w("image-gallery.default", g), _w("gallery.default", pro))
    assert c.galleries == {"gallery-a": ["a", "b"], "gallery-c": ["c"]}
    assert "<!--GG:GALLERY gallery-a-->" in c.body_html and "<!--GG:GALLERY gallery-c-->" in c.body_html
    assert [f.url.rsplit("/", 1)[1] for f in c.figures] == ["a.png", "b.jpg", "c.png"]


def test_youtube_is_click_to_load():
    c = _convert(_w("video.default", "", '{"youtube_url":"https:\\/\\/youtu.be\\/laCYM4ZpcBQ","video_type":"youtube"}'),
                 _w("text-editor.default", '<p><iframe src="https://www.youtube.com/embed/QmOF0crdyRU?start=90"></iframe></p>'))
    b = c.body_html
    assert "<iframe" not in b and "<script" not in b
    assert 'data-yt="laCYM4ZpcBQ" data-start="0"' in b and 'data-yt="QmOF0crdyRU" data-start="90"' in b
    assert 'href="https://www.youtube.com/watch?v=QmOF0crdyRU&amp;t=90s"' in b


def test_youtube_ids_and_start_times():
    assert imp.youtube_id("https://www.youtube.com/watch?v=QmOF0crdyRU&t=2406s") == ("QmOF0crdyRU", 2406)
    assert imp.youtube_id("https://youtu.be/laCYM4ZpcBQ?t=1m5s") == ("laCYM4ZpcBQ", 65)
    assert imp.youtube_id("https://example.com/watch?v=x") is None


def test_other_widgets_and_drops():
    c = _convert(_w("divider.default", "<span></span>"), _w("spacer.default", "<div></div>"),
                 _w("share-buttons.default", "<span>Share</span>"),
                 _w("icon-list.default", '<ul><li><span class="elementor-icon-list-text">Eat.</span></li></ul>'))
    assert c.body_html == '<section class="gg-blog-section">\n<hr>\n<ul>\n<li>Eat.</li>\n</ul>\n</section>\n'


def test_unknown_widgets_fail_loudly():
    with pytest.raises(NotImplementedError, match="price-table"):
        _convert(_w("price-table.default", "<p>$99</p>"))


def test_image_inside_a_paragraph_goes_after_it():
    c = _convert(_w("text-editor.default",
                    '<p>Look: <img data-src="https://gravelgodcycling.com/wp-content/uploads/2021/09/x-1024x576.png"> wow</p>'))
    assert c.body_html.index("<p>Look:  wow</p>") < c.body_html.index("<!--GG:FIGURE x-->")


def test_bold_only_paragraphs_get_ids():
    c = _convert(_w("text-editor.default", "<p><strong>Quote of the day</strong></p><p><strong>a</strong> b</p>"))
    assert '<p id="quote-of-the-day"><strong>Quote of the day</strong></p>' in c.body_html
    assert "<p><strong>a</strong> b</p>" in c.body_html


def test_aside_option_wraps_heading_and_next_text():
    c = _convert(_w("heading.default", "<h3>Sidebar</h3>"), _w("text-editor.default", "<p>Side.</p>"),
                 _w("text-editor.default", "<p>Main.</p>"), asides=("Sidebar",))
    assert '<aside class="gg-case-study gg-sidebar" id="aside-sidebar">\n<h3>Sidebar</h3>\n<p>Side.</p>\n</aside>' in c.body_html
    assert c.heading_map == {}


def test_live_meta_extraction():
    meta = imp.extract_live_meta((FIXTURES / "3504.live-head.html").read_text(encoding="utf-8"))
    assert meta["title"] == "FoCo Fondo Race Report | Gravel God"
    assert meta["canonical"] == "https://gravelgodcycling.com/i-screwed-up-foco-fondo-so-you-dont-have-to/"
    assert meta["headline"] == "I Screwed Up Foco Fondo So You Don’t Have To"
    assert meta["published"] == "2023-08-31T18:59:25+00:00" and meta["author"] == "Matti Rowe"
    assert imp.local_date(meta["published"]) == "2023-08-31"


# ── Comments (read-only archive) ─────────────────────────────

COMMENTS = [
    {"id": 11, "parent": 0, "author": "Jack", "date": "2025-02-20T08:09:25",
     "content_html": "<p>Great read &amp; thanks!</p>\n<p>Second <a href=\"https://spam.test\">para</a><br>line</p>"},
    {"id": 12, "parent": 11, "author": "Matti Rowe", "date": "2025-02-21T10:00:00", "content_html": "<p>Cheers, Jack.</p>"},
    {"id": 13, "parent": 0, "author": "<script>alert(1)</script>", "date": "2025-03-01T09:00:00",
     "content_html": "<p>&lt;img src=x onerror=alert(1)&gt; nice</p>"},
]


def test_comments_render_escaped_threaded_and_read_only():
    out = wp_post.render_comments(COMMENTS)
    assert out.startswith('<section class="gg-comments" id="comments" data-gg-archive')
    assert "<h2 id=\"comments-h\">Comments</h2>" in out and "3 comments from the original post" in out
    assert '<strong>Jack</strong> &middot; <time datetime="2025-02-20">February 20, 2025</time>' in out
    assert "<p>Great read &amp; thanks!</p><p>Second para<br>line</p>" in out
    assert "spam.test" not in out and "<script>" not in out and "<img" not in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out and "&lt;img src=x onerror=alert(1)&gt; nice" in out
    reply = out.split('id="comment-11"', 1)[1].split('id="comment-13"', 1)[0]
    assert '<ol class="gg-comment-list"><li class="gg-comment" id="comment-12">' in reply
    for banned in ("<form", "<input", "<textarea", "<button"):
        assert banned not in out


def test_no_comments_renders_nothing():
    assert wp_post.render_comments([]) == ""


def test_comments_on_a_page_are_excluded_from_the_text_diff():
    src = _module(2592).SOURCE
    data = dict(src.data, comments=COMMENTS)
    page = wp_post.render_post(dataclasses.replace(src, data=data), alt=_module(2592).ALT)
    assert 'id="comments"' in page and page.index('id="comments"') < page.index('data-slot="ladder"')
    assert imp.text_diff((FIXTURES / "2592.txt").read_text(encoding="utf-8"), page) == []
    assert "Comments are closed." in page and "<form" not in page.split('id="comments"', 1)[1].split("</section>", 1)[0]


# ── Renderer guards ──────────────────────────────────────────


def test_missing_alt_text_raises():
    m = _module(3504)
    alt = dict(m.ALT, **{"focofondo-2": ""})
    with pytest.raises(ValueError, match="missing"):
        wp_post.render_post(m.SOURCE, alt=alt)


def test_gallery_and_youtube_render_with_their_css_and_js_only_when_used():
    src = _module(2592).SOURCE
    r = src.data["renditions"]["nap-god"]
    data = dict(src.data, figures=[dict(f, kind="still") for f in src.data["figures"]],
                galleries={"gallery-x": ["nap-god", "screen-shot-2022-04-22-at-5-17-43-pm"]},
                renditions=dict(src.data["renditions"], **{"nap-god": r}))
    body = src.body.replace("<!--GG:FIGURE nap-god-->", "<!--GG:GALLERY gallery-x-->").replace(
        "<!--GG:FIGURE screen-shot-2022-04-22-at-5-17-43-pm-->", imp.render_youtube("QmOF0crdyRU", 30))
    page = wp_post.render_post(dataclasses.replace(src, data=data, body=body), alt=_module(2592).ALT)
    assert '<figure class="gg-gallery" style="--cols:2">' in page and page.count('class="gg-gallery-item"') == 2
    assert "gg-yt-link" in page and "youtube-nocookie.com/embed/" in page and "<iframe" not in page
    plain = _page(2592)
    assert ".gg-gallery{" not in plain and "youtube-nocookie" not in plain
