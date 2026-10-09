"""Imported WordPress posts, batch W2-3 (12 posts: race reports, The Double, Tour of
the Gila, Best Bike Split, Beckham). The same per-post checks as
tests/test_wp_post_import.py runs on the pilots, for this batch's posts, plus the
batch's own decisions (rewritten meta descriptions, the Best Bike Split table,
the price-table "Apply Now" kept as text). Fixtures in tests/fixtures/wp_posts/<id>.*.
"""
from __future__ import annotations

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
POSTS = {
    3433: ("i_didnt_screw_up_unbound_200_and_you_dont_have_to_either", set()),
    3203: ("hacking_unbound_200_with_best_bike_split", {"fig-bbs-savings"}),
    3537: ("i_didnt_screw_up_red_granite_grinder_and_neither_do_you_2", set()),
    3581: ("david_beckham_has_something_to_say_to_cyclists", set()),
    3749: ("i_screwed_up_unbound_2024_so_you_dont_have_to", set()),
    2673: ("the_double_day_10_im_not_sure_what_an_18_hrv_means", set()),
    2635: ("the_double_day_6_do_you_know_what_rolly_gang_means", set()),
    2663: ("the_double_day_9_gruppetto_gods", set()),
    2716: ("the_double_day_13_the_hangover", set()),
    3641: ("tour_of_the_gila_stage_what_is_cole_doing", set()),
    3297: ("tour_of_the_gila_silver_city_criterium", set()),
    3631: ("tour_of_the_gila_stage_3_my_life_is_a_mistake", set()),
}
# Posts whose live meta description misstated the post: the module's DESCRIPTION
# replaces it (meta, og:description and JSON-LD), with a phrase the live one had.
REWRITTEN = {
    3203: "pacing strategy",
    3537: "Some races just fit your strengths",
    3749: "heat and hubris",
    2673: "the body sends signals",
    2635: "existential clarity",
    2663: "embracing the gruppetto",
    3297: "stage racers try to sprint",
    3631: "Gila Monster stage",
}
WITH_COMMENTS = {3433: 1, 3537: 1}


def _module(pid):
    return importlib.import_module(POSTS[pid][0])


def _page(pid) -> str:
    return _module(pid).OUTPUT_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize("pid", POSTS)
def test_body_text_is_word_for_word(pid):
    diff = imp.text_diff((FIXTURES / f"{pid}.txt").read_text(encoding="utf-8"), _page(pid), POSTS[pid][1])
    assert diff == [], "\n".join(diff[:80])


@pytest.mark.parametrize("pid", POSTS)
def test_converter_reproduces_committed_body_and_metadata(pid):
    record = json.loads((FIXTURES / f"{pid}.record.json").read_text(encoding="utf-8"))
    conv, data = imp.import_post(record, (FIXTURES / f"{pid}.html").read_text(encoding="utf-8"),
                                 (FIXTURES / f"{pid}.live-head.html").read_text(encoding="utf-8"))
    src = _module(pid).SOURCE
    assert conv.body_html == src.body
    assert data["live"] == src.data["live"]
    assert [f["name"] for f in data["figures"]] == [f["name"] for f in src.data["figures"]]


@pytest.mark.parametrize("pid", POSTS)
def test_committed_page_is_fresh(pid):
    m = _module(pid)
    assert m.OUTPUT_PATH.read_text(encoding="utf-8") == m.render(), (
        f"stale: run python3 wordpress/post_sources/{m.__name__}.py")


@pytest.mark.parametrize("pid", POSTS)
def test_metadata_comes_from_the_live_page(pid):
    m = _module(pid)
    live = m.SOURCE.data["live"]
    html = _page(pid)
    url = f"https://gravelgodcycling.com/{m.SLUG}/"
    assert m.SLUG == json.loads((FIXTURES / f"{pid}.record.json").read_text(encoding="utf-8"))["slug"]
    assert live["canonical"] == url
    assert f'<link rel="canonical" href="{url}">' in html
    assert f"<title>{es.esc(live['title'])}</title>" in html
    desc = getattr(m, "DESCRIPTION", None) or live["description"]
    assert f'<meta name="description" content="{es.esc(desc)}">' in html
    assert f'<meta property="og:description" content="{es.esc(desc)}">' in html
    assert f'<meta property="og:title" content="{es.esc(live["og_title"])}">' in html
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert [b["@type"] for b in ld] == ["BlogPosting"]
    assert ld[0]["headline"] == live["headline"] and ld[0]["datePublished"] == live["published"]
    assert ld[0]["mainEntityOfPage"] == url and ld[0]["description"] == desc
    assert m.OUTPUT_PATH == PROJECT_ROOT / "wordpress" / "posts" / m.SLUG / "index.html"


@pytest.mark.parametrize("pid", POSTS)
def test_rewritten_descriptions_replace_the_live_one_everywhere(pid):
    m = _module(pid)
    html = _page(pid)
    if pid not in REWRITTEN:
        assert not hasattr(m, "DESCRIPTION")
        return
    assert REWRITTEN[pid] in m.SOURCE.data["live"]["description"]
    assert REWRITTEN[pid] not in html
    assert len(m.DESCRIPTION) <= 160 and "!" not in m.DESCRIPTION
    assert not re.search(r"\b(I|me|my|we|our)\b", m.DESCRIPTION)


@pytest.mark.parametrize("pid", POSTS)
def test_analytics_and_consent(pid):
    html = _page(pid)
    assert get_ga4_head_snippet().strip() in html
    assert "article_scroll_depth" in html and "article_deep_read" in html
    assert 'id="gg-consent-banner"' in html or "gg-consent" in html
    assert "onclick=" not in html


@pytest.mark.parametrize("pid", POSTS)
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


@pytest.mark.parametrize("pid", POSTS)
def test_og_image_is_the_featured_image_crop(pid):
    m = _module(pid)
    html = _page(pid)
    feat = m.SOURCE.data["featured"]
    og = m.SOURCE.data["renditions"][feat["name"]]["og"]
    assert og["file"] == f"{feat['name']}-og.jpg"
    assert f'<meta property="og:image" content="https://gravelgodcycling.com/{m.SLUG}/img/{og["file"]}">' in html
    local = m.OUTPUT_PATH.parent / "img" / og["file"]
    assert local.stat().st_size <= imp.OG_MAX_BYTES and local.stat().st_size == og["bytes"]


@pytest.mark.parametrize("pid", POSTS)
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


@pytest.mark.parametrize("pid", POSTS)
def test_in_short_follows_the_rule(pid):
    """2-4 neutral third-person claims (at most 2 under 800 words), each at most
    25 words, no "!", each linking to an anchor on the page."""
    m = _module(pid)
    html = _page(pid)
    assert wp_post.in_short_problems(m.IN_SHORT, es.word_count(m.SOURCE.body)) == []
    cap = wp_post.SHORT_POST_MAX_CLAIMS if es.word_count(m.SOURCE.body) < wp_post.SHORT_POST_WORDS else 4
    assert 2 <= len(m.IN_SHORT) <= cap
    for c in m.IN_SHORT:
        text = re.sub(r"<[^>]+>", "", c.text_html)
        assert len(text.split()) <= 25, text
        assert "!" not in text and not re.search(r"\b(I|me|my|we|our)\b", text), text
        assert c.href.startswith("#") and f'id="{c.href[1:]}"' in html, c.href


@pytest.mark.parametrize("pid", POSTS)
def test_comments_archive_only_where_the_post_had_comments(pid):
    n = WITH_COMMENTS.get(pid, 0)
    assert len(_module(pid).SOURCE.data["comments"]) == n
    html = _page(pid)
    if n:
        assert 'id="comments" data-gg-archive' in html and f"{n} comment from the original post" in html
        assert "<form" not in html.split('id="comments"', 1)[1]
    else:
        assert 'id="comments"' not in html


def test_best_bike_split_table_is_the_posts_numbers():
    m = _module(3203)
    body = m.SOURCE.body
    for phrase in ("as much as 7 watts", "15:29", "increasing your power by 5% saves you 17:33",
                   "decreasing your weight by 5% saves you 8:18", "FTP of 370", "weighing 166 lbs"):
        assert phrase in body, phrase
    fig = _page(3203).split('id="fig-bbs-savings"', 1)[1].split("</figure>", 1)[0]
    for v in ("15:29", "17:33", "8:18"):
        assert v in fig, v


def test_price_table_apply_now_stays_plain_text():
    """The live coaching table's "Apply Now" button has an empty link: kept as text."""
    html = _page(3203)
    assert '<dd class="gg-price-action">Apply Now</dd>' in html
    assert 'href=""' not in html
    assert html.count('class="gg-price-table"') == 2


def test_red_granite_2023_keeps_its_own_slug():
    """3537 shares its title with 2209; it lives at its own (-2) slug."""
    m = _module(3537)
    assert m.SLUG.endswith("-2")
    assert f'<link rel="canonical" href="https://gravelgodcycling.com/{m.SLUG}/">' in _page(3537)


@pytest.mark.parametrize("pid", (2663, 2673, 2716))
def test_h6_only_double_day_posts_get_h2_sections(pid):
    m = _module(pid)
    assert m.SOURCE.data["heading_map"] == {"h6": "h2"}
    assert re.search(r'<h2 id="[a-z0-9-]+" data-toc>', _page(pid))


def test_gila_crit_gallery_renders_as_a_grid():
    html = _page(3297)
    assert 'class="gg-gallery"' in html and html.count('class="gg-gallery-item"') == 2
