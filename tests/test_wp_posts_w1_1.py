"""Imported WordPress posts, batch W1-1 (the eight posts that were broken live,
showing [POST_CONTENT]). Fixtures in tests/fixtures/wp_posts/<id>.*.

tests/test_wp_post_import.py::test_every_post_module_is_complete_and_fresh already
runs on every post module (converter reproduces body + metadata, "In short" lint,
alt coverage, fresh page). This file adds the word-for-word diff and the per-page
checks the pilots get, plus this batch's own figures and corrected descriptions.
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
    2469: ("how_to_do_workouts_the_right_way", {"fig-zones"}),
    1533: ("if_youre_not_talented_you_should_probably_quit", {"fig-great-dane"}),
    1230: ("since_no_one_asked_why_did_dumoulin_retire_he_just_wants_to_eat_some_cheese_2", {"fig-phenotypes"}),
    1078: ("controversial_opinion_you_dont_need_a_power_meter_to_be_fast", {"fig-fortunato-year"}),
    901: ("since_no_one_asked_my_take_on_whoop", set()),
    915: ("so_why_do_you_skip_weight_training", set()),
    922: ("the_tao_of_tom", set()),
    1186: ("since_no_one_asked_why_did_dumoulin_retire_he_just_wants_to_eat_some_cheese", set()),
}
# Posts whose live meta description misstated the post (Matt, 2026-10-09).
CORRECTED_DESCRIPTION = {922, 1078, 1533}


def _module(pid):
    return importlib.import_module(POSTS[pid][0])


def _page(pid) -> str:
    return _module(pid).OUTPUT_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize("pid", POSTS)
def test_body_text_is_word_for_word(pid):
    diff = imp.text_diff(wp_post.corrected_baseline((FIXTURES / f"{pid}.txt").read_text(encoding="utf-8"), getattr(_module(pid), "CORRECTIONS", ())), _page(pid), POSTS[pid][1])
    assert diff == [], "\n".join(diff[:80])


@pytest.mark.parametrize("pid", POSTS)
def test_metadata_comes_from_the_live_page(pid):
    m = _module(pid)
    live = m.SOURCE.data["live"]
    html = _page(pid)
    url = f"https://gravelgodcycling.com/{m.SLUG}/"
    assert live["canonical"] == url
    assert f'<link rel="canonical" href="{url}">' in html
    assert f"<title>{es.esc(getattr(m, 'TITLE', None) or live['title'])}</title>" in html
    desc = getattr(m, "DESCRIPTION", None) or live["description"]
    assert (pid in CORRECTED_DESCRIPTION) == hasattr(m, "DESCRIPTION")
    assert f'<meta name="description" content="{es.esc(desc)}">' in html
    assert f'<meta property="og:description" content="{es.esc(desc)}">' in html
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert [b["@type"] for b in ld] == ["BlogPosting"]
    assert ld[0]["headline"] == (m.TITLE.removesuffix(" | Gravel God") if hasattr(m, "TITLE") else live["headline"]) and ld[0]["mainEntityOfPage"] == url
    assert ld[0]["description"] == desc and ld[0]["datePublished"] == live["published"]
    head = html.split("</head>", 1)[0]
    assert f'<meta property="article:published_time" content="{live["published"]}">' in head
    modified = wp_post.CORRECTED_MODIFIED if getattr(m, "CORRECTIONS", ()) else live["modified"]
    assert f'<meta property="article:modified_time" content="{modified}">' in head
    assert m.OUTPUT_PATH == PROJECT_ROOT / "wordpress" / "posts" / m.SLUG / "index.html"


@pytest.mark.parametrize("pid", POSTS)
def test_analytics_and_consent(pid):
    html = _page(pid)
    assert get_ga4_head_snippet().strip() in html
    assert "article_scroll_depth" in html
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
    referenced = set(re.findall(r'(?:src|srcset|data-poster)="(img/[^" ]+)', html))
    referenced |= set(re.findall(r", (img/[^ ]+) 2x", html))
    for path in referenced:
        assert (m.OUTPUT_PATH.parent / path).is_file(), path
    img_dir = m.OUTPUT_PATH.parent / "img"
    shipped = {p.suffix for p in img_dir.iterdir() if not p.name.endswith("-og.jpg")}
    assert shipped <= {".webp", ".mp4", ".webm"}
    assert [p.name for p in img_dir.glob("*.jpg")] == ([f"{feat['name']}-og.jpg"] if feat else [])


@pytest.mark.parametrize("pid", POSTS)
def test_og_image_is_the_featured_image_crop(pid):
    m = _module(pid)
    html = _page(pid)
    og = m.SOURCE.data["renditions"][m.SOURCE.data["featured"]["name"]]["og"]
    assert f'<meta property="og:image" content="https://gravelgodcycling.com/{m.SLUG}/img/{og["file"]}">' in html
    assert "cropped-Gravel-God-logo" not in html
    local = m.OUTPUT_PATH.parent / "img" / og["file"]
    assert local.stat().st_size <= imp.OG_MAX_BYTES and local.stat().st_size == og["bytes"]


@pytest.mark.parametrize("pid", POSTS)
def test_gifs_are_muted_videos(pid):
    m = _module(pid)
    html = _page(pid)
    for f in m.SOURCE.data["figures"]:
        if f["kind"] == "gif":
            n = f["name"]
            # smallest file first (browsers play the first source); the MP4 always ships
            srcs = "".join(f'<source src="{s}" type="{t}">'
                           for s, t in m.wp_post.video_sources(m.SOURCE.data["renditions"][n]))
            assert srcs in html and f'img/{n}.mp4' in srcs
    assert ".gif" not in re.sub(r"https://gravelgodcycling\.com/wp-content/[^\"' ]+", "", html)


@pytest.mark.parametrize("pid", POSTS)
def test_in_short_links_land_on_the_page(pid):
    """The rule itself is linted for every post in test_wp_post_import; here each
    claim's link must hit an id that exists on the rendered page."""
    html = _page(pid)
    for c in _module(pid).IN_SHORT:
        assert f'id="{c.href[1:]}"' in html, c.href


@pytest.mark.parametrize("pid", POSTS)
def test_no_comments_on_this_batch(pid):
    """None of these posts has approved comments, so no archive renders."""
    assert _module(pid).SOURCE.data["comments"] == []
    assert 'id="comments"' not in _page(pid)


def test_zone_table_is_the_posts_text():
    m = _module(2469)
    body = m.SOURCE.body
    for _, ftp, _, hr, dose in m.ZONES:
        for v in (ftp, hr, dose):
            assert v in body, v
    for note in m.HR_NOTES.values():
        assert note in body, note


def test_great_dane_numbers_are_in_the_gif_alts():
    m = _module(1533)
    alts = m.ALT["the-great-dane-2018-3"] + m.ALT["the-great-dane-2018-5"]
    for d, a, b, ch in m.DANE:
        assert f"{d} {a} w" in alts and f"{d} {b} w" in alts, d
        if ch:
            assert ch in alts
    assert "56 more watts over 2 hours" in m.SOURCE.body


def test_phenotypes_redrawn_with_the_original_kept():
    html = _page(1230)
    fig = html.split('id="fig-phenotypes"', 1)[1].split("</figure>", 1)[0]
    assert fig.count("<svg") == 4 and fig.count('data-draw="wipe"') == 4
    assert '<details class="gg-original" data-gg-added>' in fig and "img/phenotypes.webp" in fig


def test_fortunato_table_uses_the_posts_words():
    m = _module(1078)
    body = m.SOURCE.body
    for row in m.YEAR:
        for v in row[1:]:
            if v:
                assert v in body, v
    assert '<p id="p-kom">' in _page(1078)


def test_1186_slides_are_eight_step_figures_in_order():
    """The slides widget (the Grand Tour recipe) renders one text figure per slide,
    Step 1..8 in order, the slide text word for word (test_body_text_is_word_for_word)."""
    html = _page(1186)
    assert re.findall(r'<figure class="gg-slide">.*?<figcaption>(Step \d)</figcaption>', html, re.S) == [
        f"Step {n}" for n in range(1, 9)]


def test_1186_and_1230_are_different_posts():
    a, b = _module(1186).SOURCE.data, _module(1230).SOURCE.data
    assert a["id"] != b["id"] and a["live"]["headline"] != b["live"]["headline"]
    assert _module(1230).SLUG == _module(1186).SLUG + "-2"


def test_corrected_descriptions():
    assert "younger teammate" in _module(922).DESCRIPTION and "trusted the plan" in _module(922).DESCRIPTION
    assert "talent is real" in _module(1533).DESCRIPTION
    assert "when data helps" not in _module(1078).DESCRIPTION and "power meter" in _module(1078).DESCRIPTION
