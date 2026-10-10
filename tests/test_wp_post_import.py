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
    diff = imp.text_diff(wp_post.corrected_baseline((FIXTURES / f"{pid}.txt").read_text(encoding="utf-8"), getattr(_module(pid), "CORRECTIONS", ())), _page(pid), PILOTS[pid][1])
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


# ── Every post module (auto-discovered: pilots and batch PRs alike) ──

POST_SOURCES = PROJECT_ROOT / "wordpress" / "post_sources"
POST_MODULES = sorted(p.stem for p in POST_SOURCES.glob("*.py"))
FIXTURE_KINDS = ("html", "txt", "record.json", "live-head.html")


def _post_test_files() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in (PROJECT_ROOT / "tests").glob("test_wp_post*.py")}


def _uncovered(modules, test_texts) -> list[str]:
    return [m for m in modules if not any(f'"{m}"' in text for text in test_texts)]


def test_every_post_source_is_covered():
    """Every wordpress/post_sources/<module>.py is named in a test_wp_post*.py
    post table (PILOTS here, a batch's POSTS in its own file), so its
    word-for-word diff and its other per-post checks run."""
    assert POST_MODULES, "no post modules found"
    uncovered = _uncovered(POST_MODULES, _post_test_files().values())
    assert uncovered == [], f"post modules no test_wp_post*.py names: {uncovered}"


@pytest.mark.parametrize("module", POST_MODULES)
def test_every_post_module_is_complete_and_fresh(module):
    """Invariants for every discovered post: the module's interface, its
    converter output and fixtures, the converter reproducing its body and live
    metadata, the "In short" rule, alt text, and a fresh committed page."""
    m = importlib.import_module(module)
    for name in ("SLUG", "SOURCE", "OUTPUT_PATH", "ALT", "IN_SHORT", "render"):
        assert hasattr(m, name), f"{module}: no {name}"
    assert m.__name__ == imp.module_name(m.SLUG)
    assert (POST_SOURCES / f"{m.SLUG}.body.html").is_file() and (POST_SOURCES / f"{m.SLUG}.json").is_file()
    pid = m.SOURCE.data["id"]
    for kind in FIXTURE_KINDS:
        assert (FIXTURES / f"{pid}.{kind}").is_file(), f"{module}: missing fixture {pid}.{kind}"
    record = json.loads((FIXTURES / f"{pid}.record.json").read_text(encoding="utf-8"))
    asides = tuple((m.SOURCE.data.get("import") or {}).get("asides", ()))
    conv, data = imp.import_post(record, (FIXTURES / f"{pid}.html").read_text(encoding="utf-8"),
                                 (FIXTURES / f"{pid}.live-head.html").read_text(encoding="utf-8"), asides=asides)
    assert conv.body_html == m.SOURCE.body, f"{module}: body differs from the converter's output"
    assert data["live"] == m.SOURCE.data["live"]
    assert [f["name"] for f in data["figures"]] == [f["name"] for f in m.SOURCE.data["figures"]]
    assert m.SOURCE.data["live"]["canonical"] == f"https://gravelgodcycling.com/{m.SLUG}/"
    assert wp_post.in_short_problems(m.IN_SHORT, es.word_count(m.SOURCE.body)) == []
    names = [f["name"] for f in m.SOURCE.data["figures"]]
    feat = m.SOURCE.data.get("featured")
    if feat and not feat["also_inline"]:
        names.append(feat["name"])
    assert sorted(m.ALT) == sorted(names) and all(a.strip() for a in m.ALT.values())
    assert m.OUTPUT_PATH.read_text(encoding="utf-8") == m.render(), (
        f"stale: run python3 wordpress/post_sources/{module}.py")


def test_coverage_check_sees_a_new_module():
    """Discovery is by file, not by a list: a module no test table names fails."""
    tables = ['POSTS = {1: ("covered_post", set())}']
    assert _uncovered(["covered_post", "brand_new_post"], tables) == ["brand_new_post"]


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
    assert f"<title>{es.esc(getattr(m, 'TITLE', None) or live['title'])}</title>" in html
    desc = getattr(m, "DESCRIPTION", None) or live["description"]
    assert f'<meta name="description" content="{es.esc(desc)}">' in html
    assert f'<meta property="og:title" content="{es.esc(getattr(m, "TITLE", None) or live["og_title"])}">' in html
    assert '<meta name="robots" content="index, follow, max-image-preview:large">' in html
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert [b["@type"] for b in ld] == ["BlogPosting"]
    assert ld[0]["headline"] == (m.TITLE.removesuffix(" | Gravel God") if hasattr(m, "TITLE") else live["headline"]) and ld[0]["datePublished"] == live["published"]
    assert ld[0]["mainEntityOfPage"] == url and ld[0]["description"] == desc
    head = html.split("</head>", 1)[0]
    assert f'<meta property="article:published_time" content="{live["published"]}">' in head
    modified = wp_post.CORRECTED_MODIFIED if getattr(m, "CORRECTIONS", ()) else live["modified"]
    assert f'<meta property="article:modified_time" content="{modified}">' in head
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
    shipped = {p.suffix for p in img_dir.iterdir() if not p.name.endswith("-og.jpg")}
    assert shipped <= {".webp", ".mp4", ".webm"}, "no PNG/JPEG/GIF ships; WebP + video only (+ the og:image JPEG)"
    assert [p.name for p in img_dir.glob("*.jpg")] == ([f"{feat['name']}-og.jpg"] if feat else [])


@pytest.mark.parametrize("pid", PILOTS)
def test_gifs_are_muted_play_once_videos(pid):
    m = _module(pid)
    html = _page(pid)
    for f in m.SOURCE.data["figures"]:
        if f["kind"] != "gif":
            continue
        n = f["name"]
        # smallest file first (browsers play the first source); the MP4 always ships
        srcs = "".join(f'<source src="{s}" type="{t}">'
                       for s, t in m.wp_post.video_sources(m.SOURCE.data["renditions"][n]))
        assert srcs in html and f'img/{n}.mp4' in srcs
        tag = html.split(srcs, 1)[0].rsplit("<video", 1)[1]
        assert "muted playsinline" in tag and 'preload="none"' in tag and "autoplay" not in tag
    assert ".gif" not in re.sub(r"https://gravelgodcycling\.com/wp-content/[^\"' ]+", "", html)


@pytest.mark.parametrize("pid", PILOTS)
def test_in_short_follows_the_rule(pid):
    """The "In short" rule (wp_post docstring): 2-4 neutral third-person claims
    (no I/me/my/we, no "!"), each at most 25 words, at most 2 under 800 words,
    each linking to an anchor on the page."""
    m = _module(pid)
    html = _page(pid)
    assert wp_post.in_short_problems(m.IN_SHORT, es.word_count(m.SOURCE.body)) == []
    assert 2 <= len(m.IN_SHORT) <= 4
    for c in m.IN_SHORT:
        text = re.sub(r"<[^>]+>", "", c.text_html)
        assert len(text.split()) <= 25, text
        assert "!" not in text and not re.search(r"\b(I|me|my|we)\b", text, re.I), text
        assert c.href.startswith("#") and f'id="{c.href[1:]}"' in html, c.href


def test_in_short_lint_catches_voice_breaks():
    ok = es.Claim("The post argues that a dopamine spike above baseline is followed by an equal dip below it.",
                  "#a", "See §01", 0)
    assert wp_post.in_short_problems((ok, ok), 1000) == []
    bad = {
        "first person": es.Claim("I mashed the button and we paid for it.", "#a", "x", 0),
        "no '!'": es.Claim("The toaster costs $20!", "#a", "x", 0),
        "words (max 25)": es.Claim(" ".join(["word"] * 26), "#a", "x", 0),
        "must link": es.Claim("The post says so.", "https://example.com/", "x", 0),
    }
    for want, claim in bad.items():
        assert any(want in p for p in wp_post.in_short_problems((ok, claim), 1000)), want
    assert any("at most 2 claims" in p for p in wp_post.in_short_problems((ok, ok, ok), 799))
    assert wp_post.in_short_problems((ok, ok, ok), 800) == []
    assert any("write 2-4" in p for p in wp_post.in_short_problems((ok,), 1000))
    m = _module(2592)
    with pytest.raises(ValueError, match="first person"):
        wp_post.render_post(m.SOURCE, alt=m.ALT, in_short=(ok, bad["first person"]))


@pytest.mark.parametrize("pid", PILOTS)
def test_og_image_is_the_featured_image_crop(pid):
    """og:image = the post's featured image as a 1200x630 JPEG (<=200 KB) in its own img/."""
    from PIL import Image
    m = _module(pid)
    html = _page(pid)
    feat = m.SOURCE.data["featured"]
    og = m.SOURCE.data["renditions"][feat["name"]]["og"]
    url = f"https://gravelgodcycling.com/{m.SLUG}/img/{og['file']}"
    assert og["file"] == f"{feat['name']}-og.jpg"
    assert f'<meta property="og:image" content="{url}">' in html
    assert '<meta property="og:image:width" content="1200">' in html
    assert '<meta property="og:image:height" content="630">' in html
    assert "cropped-Gravel-God-logo" not in html
    local = m.OUTPUT_PATH.parent / "img" / og["file"]  # what the URL serves once deployed
    assert local.stat().st_size <= imp.OG_MAX_BYTES and local.stat().st_size == og["bytes"]
    with Image.open(local) as im:
        assert im.format == "JPEG" and im.size == (1200, 630)


def test_og_image_falls_back_to_the_live_one_without_a_featured_image():
    src = _module(2161).SOURCE
    bare = dataclasses.replace(src, data={**src.data, "featured": None})
    live = src.data["live"]["og_image"]
    assert wp_post.og_image(bare) == es.OgImage(live["url"], live["width"], live["height"])
    no_crop = dataclasses.replace(src, data={**src.data, "renditions": {}})
    assert wp_post.og_image(no_crop).url == live["url"]


def test_og_rendition_crops_flattens_and_fits_the_budget(tmp_path):
    """A noisy transparent portrait still comes out 1200x630, opaque, <=200 KB;
    ensure_og falls back to the committed 1x WebP when the original isn't cached."""
    import random
    from PIL import Image
    rnd = random.Random(7)
    im = Image.new("RGBA", (1000, 1500), (0, 0, 0, 0))  # grain over a gradient, a transparent band every 3rd row
    im.putdata([(min(255, x // 4 + rnd.randrange(64)), min(255, y // 6 + rnd.randrange(64)), rnd.randrange(64, 192),
                 255 if y % 3 else 0) for y in range(1500) for x in range(1000)])
    src = tmp_path / "noise.png"
    im.save(src)
    out = imp.og_rendition(src, tmp_path / "img", "noise")
    assert out["width"] == 1200 and out["height"] == 630 and out["bytes"] <= imp.OG_MAX_BYTES
    with Image.open(tmp_path / "img" / "noise-og.jpg") as og:
        assert og.mode == "RGB" and og.size == (1200, 630)

    Image.new("RGB", (1600, 900), (40, 90, 140)).save(tmp_path / "img" / "hero.webp")
    data = {"featured": {"name": "hero", "url": "https://x/wp-content/uploads/hero.png", "kind": "still"},
            "renditions": {"hero": {"1x": {"file": "hero.webp", "width": 1600, "height": 900}}}}
    imp.ensure_og(data, tmp_path / "img", tmp_path / "no-cache")
    assert data["renditions"]["hero"]["og"]["file"] == "hero-og.jpg"
    imp.ensure_og({"featured": None, "renditions": {}}, tmp_path / "img", tmp_path)  # no featured: no-op


def test_double_day_3_description_is_corrected_and_only_there():
    """The live description misread "Yield to tonnage" (it's backing up a trailer)."""
    html = _page(2592)
    m = _module(2592)
    assert "bigger riders" in m.SOURCE.data["live"]["description"]
    assert "bigger riders" not in html and "trailer backed through a tight gap" in m.DESCRIPTION
    assert f'<meta property="og:description" content="{es.esc(m.DESCRIPTION)}">' in html
    assert len(m.DESCRIPTION) <= 160 and "!" not in m.DESCRIPTION
    for pid in (3504, 2161):
        assert not hasattr(_module(pid), "DESCRIPTION")


def test_h6_only_post_gets_sections_but_no_contents_under_three():
    """Its two H6 headings become numbered sections, but two sections are
    fewer than wp_post.MIN_CONTENTS_SECTIONS, so no Contents rail or bar."""
    html = _page(2592)
    assert re.search(r'<h2 id="mediocre-power-reveal-inner-race-commentary" data-toc>', html)
    assert re.search(r'<h2 id="what-i-loved-about-today" data-toc>', html)
    assert '<nav class="rail"' not in html and 'class="toc-m"' not in html


def test_three_or_more_sections_get_contents():
    assert '<nav class="rail" aria-label="Contents">' in _page(2161)  # four sections


def test_double_day_3_claims_state_no_watt_gap():
    """The text says "100 more watts"; the stats it links to show 328 W vs 415 W.
    The claim states only what both agree on: the teammate out-powered the author."""
    claims = [re.sub(r"<[^>]+>", "", c.text_html) for c in _module(2592).IN_SHORT]
    assert not any(re.search(r"\b\d+\s*(?:more\s+)?watts?\b|\b\d+\s*W\b", c) for c in claims), claims
    assert any("out-powered the author in the Route 66 time trial" in c for c in claims)


def test_short_post_in_short_is_capped():
    m = _module(2592)
    assert len(m.IN_SHORT) <= wp_post.SHORT_POST_MAX_CLAIMS
    extra = m.IN_SHORT + (es.Claim("x", "#x", "x", 0),)
    with pytest.raises(ValueError, match="at most 2 claims"):
        wp_post.render_post(m.SOURCE, alt=m.ALT, in_short=extra)


def test_pull_quote_has_a_safe_gutter():
    html = _page(3504)
    assert ".article .gg-pullquote{margin:44px 0 40px;padding:0 20px}" in html
    assert ".article .gg-pullquote{padding:0 18px}" in html
    assert "hanging-punctuation:none" in html


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


def test_dopamine_caffeine_reads_no_increase_with_the_note():
    html = _page(2161)
    assert '<span class="dm-val">No increase</span>' in html
    assert "**" not in html.split('id="fig-dopamine-multiples"')[1].split("</figure>")[0]
    assert "no increase above baseline, but it does increase the number of receptors that accept dopamine" in html


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


def test_elementor_placeholder_heading_is_dropped_real_headings_kept():
    c = _convert(_w("heading.default", "<h2>  add your HEADING\n text here </h2>"),
                 _w("heading.default", "<h3>Real one</h3>"),
                 _w("text-editor.default", "<p>Add Your Heading Text Here</p>"),
                 _w("heading.default", "<h3>Add Your Heading Text Here, please</h3>"))
    assert "<h2>Real one</h2>" in c.body_html  # placeholder's h2 level never enters the heading map
    assert c.heading_map == {"h3": "h2"}
    assert c.headings == [("h2", "Real one"), ("h2", "Add Your Heading Text Here, please")]
    assert "<p>Add Your Heading Text Here</p>" in c.body_html  # only heading widgets are filtered


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
    with pytest.raises(NotImplementedError, match="flip-box"):
        _convert(_w("flip-box.default", "<p>$99</p>"))


def _fixture_convert(name: str) -> imp.Converted:
    return imp.ElementorConverter().convert((FIXTURES / name).read_text(encoding="utf-8"))


def _same_words(fixture: str, conv: imp.Converted) -> None:
    """The converted widget's visible words equal the widget's own, in order."""
    want = imp.words(imp.visible_text((FIXTURES / fixture).read_text(encoding="utf-8")))
    got = imp.words(imp.visible_text(conv.body_html))
    assert got == want, "\n".join(__import__("difflib").unified_diff(want, got, lineterm="", n=2))


def test_gallery_skips_noscript_fallbacks_one_figure_per_photo():
    """Post 3335 (Tour of the Gila): 10 gallery photos, each lazy-loaded with a
    <noscript> copy; that was 20 figures."""
    c = _fixture_convert("3335-gallery.html")
    assert len(c.galleries) == 1
    names = next(iter(c.galleries.values()))
    assert len(names) == 10 == len(c.figures) == len({f.url for f in c.figures})
    assert names[:2] == ["do-you-even-lift-bro", "abq-burritoes"]
    assert not any(re.search(r"-\d$", n) for n in names), names  # no "-2" duplicates


def test_gallery_dedupes_the_same_upload_at_two_sizes():
    g = ('<div class="gallery"><img data-src="https://gravelgodcycling.com/wp-content/uploads/2023/05/a-768x1024.png">'
         '<img src="https://gravelgodcycling.com/wp-content/uploads/2023/05/a-225x300.png">'
         '<img src="https://gravelgodcycling.com/wp-content/uploads/2023/05/b-scaled.jpeg">'
         '<img src="https://gravelgodcycling.com/wp-content/uploads/2023/05/b-300x200.jpeg"></div>')
    c = _convert(_w("image-gallery.default", g))
    assert c.galleries == {"gallery-a": ["a", "b-scaled"]}  # one figure per upload, named from the first size seen


def test_image_in_a_paragraph_ignores_its_noscript_copy():
    c = _convert(_w("text-editor.default",
                    '<p>Look <img class="lazyload" data-src="https://gravelgodcycling.com/wp-content/uploads/2021/09/x-1024x576.png">'
                    '<noscript><img src="https://gravelgodcycling.com/wp-content/uploads/2021/09/x-1024x576.png"></noscript></p>'))
    assert [f.name for f in c.figures] == ["x"]


def test_slides_become_one_figure_per_slide_text_verbatim():
    """Post 1186 (Dumoulin): an 8-slide carousel, text only, button labels "Step N" (no links)."""
    c = _fixture_convert("1186-slides.html")
    b = c.body_html
    assert b.count('<figure class="gg-slide">') == 8 and c.figures == [] and c.heading_map == {}
    assert ("<p>Pick the right parents, especially your mom (she's the one that passes on her mitochondrion, "
            "which creates all the ATP required for aerobic respiration).</p>\n<figcaption>Step 1</figcaption>") in b
    assert [int(n) for n in re.findall(r"<figcaption>Step (\d)</figcaption>", b)] == list(range(1, 9))
    assert "swiper" not in b and "<a " not in b
    _same_words("1186-slides.html", c)


def test_slide_background_image_and_link():
    s = ('<div class="swiper-slide"><div class="swiper-slide-bg" style="background-image: url(https://gravelgodcycling.com/wp-content/uploads/2021/01/bg-1024x576.jpg)"></div>'
         '<a class="swiper-slide-inner" href="https://x.test/"><div class="elementor-slide-heading">Head</div>'
         '<div class="elementor-slide-description">Desc</div><div class="elementor-slide-button">Go</div></a></div>')
    c = _convert(_w("slides.default", s))
    assert c.body_html.index("<!--GG:FIGURE bg-->") < c.body_html.index('<figure class="gg-slide">')
    assert ('<p class="gg-slide-heading"><strong>Head</strong></p>\n<p>Desc</p>\n'
            '<figcaption><a href="https://x.test/">Go</a></figcaption>') in c.body_html


def test_price_tables_become_definition_lists_every_price_and_feature_kept():
    """Post 3203 (Hacking Unbound 200): two price tables side by side."""
    c = _fixture_convert("3203-price-tables.html")
    b = c.body_html
    assert b.count('<dl class="gg-price-table">') == 2 and c.heading_map == {}  # their h3s are not post headings
    assert "<dt>Unbound 200 Training Plan</dt>" in b and "<dt>Coaching</dt>" in b
    assert "<dd class=\"gg-price-sub\">For the 2/3 of speed you can't buy.</dd>" in b
    assert '<dd class="gg-price">$\u202f100</dd>' in b
    assert '<dd class="gg-price">$\u202f175 <span class="gg-price-period">Monthly</span></dd>' in b
    for feat in ("Science-based", "Workouts exportable to device", "Race Tactics", "Heat Training",
                 "Mobility Workouts", "Tactics", "Accountability", "Support", "Custom-tailored",
                 "Guaranteed Results", "Analysis"):
        assert f"<li>{feat}</li>" in b
    assert ('<dd class="gg-price-action"><a href="https://www.trainingpeaks.com/training-plans/cycling/'
            'gran-fondo-century/tp-196715/gravel-god-unbound-200" target="_blank" rel="noopener">Buy Now</a></dd>') in b
    assert '<dd class="gg-price-action">Apply Now</dd>' in b  # live button has href="": text kept, no dead link
    assert '<dd class="gg-price-ribbon">Popular</dd>' in b
    assert "elementor" not in b and "fa-check" not in b
    _same_words("3203-price-tables.html", c)


def test_call_to_action_becomes_a_callout_text_and_link_verbatim():
    """Post 2324 (SBT GRVL): a CTA box with a background image (left out: decoration)."""
    c = _fixture_convert("2324-cta.html")
    assert c.body_html == (
        '<section class="gg-blog-section">\n<aside class="gg-case-study gg-cta">\n'
        '<p class="gg-cta-title"><strong>SBT GRVL Training Plan</strong></p>\n'
        "<p>Can't be bothered to figture out how to train for SBT GRVL yourself? I get it. "
        "Grab yourself a training plan and save the headache.</p>\n"
        '<p class="gg-cta-action"><a href="https://www.trainingpeaks.com/training-plans/cycling/gran-fondo-century/'
        "tp-287683/gravel-god-sbt-grvl-base-to-race\">Gimme' the plan</a></p>\n</aside>\n</section>\n")
    assert c.figures == [] and c.heading_map == {}
    _same_words("2324-cta.html", c)


def test_boxed_widgets_render_with_their_css_only_when_used():
    src = _module(2592).SOURCE
    extra = "\n".join(_fixture_convert(f).body_html for f in ("1186-slides.html", "3203-price-tables.html", "2324-cta.html"))
    page = wp_post.render_post(dataclasses.replace(src, body=src.body + extra), alt=_module(2592).ALT)
    assert ".gg-slide{" in page and ".gg-price-table{" in page and ".gg-cta .gg-cta-title{" in page
    plain = _page(2592)
    assert ".gg-slide{" not in plain and ".gg-price-table{" not in plain and ".gg-cta " not in plain


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
    assert "<h2 id=\"comments-h\" data-no-toc>Comments</h2>" in out and "3 comments from the original post" in out
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


# ── Post polish (2026-10-09): video weight, titles, descriptions ─────────

ALL_POST_JSON = sorted((PROJECT_ROOT / "wordpress" / "post_sources").glob("*.json"))
# ~4 MB for a ~15 s clip: the served (first) source of every GIF video stays under this.
MAX_SERVED_VIDEO_BYTES = 4_000_000


def test_video_sources_list_the_smaller_file_first():
    both = {"mp4": {"file": "a.mp4", "bytes": 300}, "webm": {"file": "a.webm", "bytes": 200}}
    assert wp_post.video_sources(both) == (("img/a.webm", "video/webm"), ("img/a.mp4", "video/mp4"))
    heavier_webm = {"mp4": {"file": "a.mp4", "bytes": 300}, "webm": {"file": "a.webm", "bytes": 400}}
    assert wp_post.video_sources(heavier_webm)[0] == ("img/a.mp4", "video/mp4")
    assert wp_post.video_sources({"mp4": {"file": "a.mp4", "bytes": 3}}) == (("img/a.mp4", "video/mp4"),)


def test_gif_filters_cap_side_fps_and_denoise():
    vf = imp._gif_filters({"width": 1080, "height": 1920, "avg_frame_rate": "100/3"})
    assert vf == f"fps={imp.GIF_MAX_FPS},scale=720:1280:flags=lanczos,{imp.GIF_DENOISE}"
    vf = imp._gif_filters({"width": 480, "height": 394, "avg_frame_rate": "5/1"})
    assert vf == f"scale=480:394:flags=lanczos,{imp.GIF_DENOISE}"


@pytest.mark.parametrize("path", ALL_POST_JSON, ids=lambda p: p.stem)
def test_gif_videos_are_light_and_smallest_first(path):
    """Every GIF ships as an MP4, plus a WebM only when it is smaller; the
    recorded bytes match the files, the page lists the smaller one first, and
    the served one is at most MAX_SERVED_VIDEO_BYTES."""
    data = json.loads(path.read_text(encoding="utf-8"))
    img = PROJECT_ROOT / "wordpress" / "posts" / data["slug"] / "img"
    page = (img.parent / "index.html").read_text(encoding="utf-8")
    for name, r in data.get("renditions", {}).items():
        if "mp4" not in r:
            continue
        for k in ("mp4", "webm"):
            if k in r:
                assert (img / r[k]["file"]).stat().st_size == r[k]["bytes"], (name, k)
        assert not (img / f"{name}.webm").exists() or "webm" in r, f"{name}.webm ships but is not listed"
        if "webm" in r:
            assert r["webm"]["bytes"] < r["mp4"]["bytes"], name
        srcs = wp_post.video_sources(r)
        assert min(r[k]["bytes"] for k in ("mp4", "webm") if k in r) == r[srcs[0][0].rsplit(".", 1)[1]]["bytes"]
        assert r[srcs[0][0].rsplit(".", 1)[1]]["bytes"] <= MAX_SERVED_VIDEO_BYTES, name
        if f"img/{name}.mp4" in page:
            assert "".join(f'<source src="{s}" type="{t}">' for s, t in srcs) in page, name


CORRECTED_TITLES = {
    "the-tao-of-tom": "The Tao of Tom — Trusting the Plan | Gravel God",
    "how-do-i-know-if-im-getting-fitter": "Training Is a Privilege, Not a Right | Gravel God",
    "eight-years-of-nate-wilson": "Eight Years of Nate Wilson, My Cycling Coach | Gravel God",
}


@pytest.mark.parametrize("slug", CORRECTED_TITLES)
def test_corrected_titles_are_consistent(slug):
    title = CORRECTED_TITLES[slug]
    page = (PROJECT_ROOT / "wordpress" / "posts" / slug / "index.html").read_text(encoding="utf-8")
    live = json.loads((PROJECT_ROOT / "wordpress" / "post_sources" / f"{slug}.json").read_text(encoding="utf-8"))["live"]
    assert live["title"] != title
    assert f"<title>{es.esc(title)}</title>" in page
    assert f'<meta property="og:title" content="{es.esc(title)}">' in page
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)]
    assert ld[0]["headline"] == title.removesuffix(" | Gravel God")
    assert es.esc(live["headline"]) in page.split("</h1>", 1)[0].rsplit("<h1", 1)[1]  # the h1 is unchanged
    assert f'<link rel="canonical" href="https://gravelgodcycling.com/{slug}/">' in page


def test_title_override_must_keep_the_site_pattern():
    src = _module(2592).SOURCE
    with pytest.raises(ValueError, match="Gravel God"):
        wp_post.build_meta(src, hero=None, title="No suffix")
    with pytest.raises(ValueError):
        wp_post.build_meta(src, hero=None, title=" | Gravel God")
    meta = wp_post.build_meta(src, hero=None, title="A Better Title | Gravel God")
    assert (meta.title, meta.og_title, meta.json_ld[0]["headline"]) == (
        "A Better Title | Gravel God", "A Better Title | Gravel God", "A Better Title")
    assert meta.headline == src.data["live"]["headline"]  # the h1 never changes


@pytest.mark.parametrize("path", ALL_POST_JSON, ids=lambda p: p.stem)
def test_meta_descriptions_fit_160_chars(path):
    import html as _html
    slug = json.loads(path.read_text(encoding="utf-8"))["slug"]
    page = (PROJECT_ROOT / "wordpress" / "posts" / slug / "index.html").read_text(encoding="utf-8")
    desc = _html.unescape(re.search(r'<meta name="description" content="([^"]*)"', page).group(1))
    assert len(desc) <= 160, (len(desc), desc)
