"""Imported WordPress posts, batch W2-4. The same per-post checks as
tests/test_wp_post_import.py runs on the pilots, for this batch's posts, plus
the batch's infographics and corrected descriptions. Fixtures in
tests/fixtures/wp_posts/<id>.*.
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
    2956: ("how_to_beat_people_20_years_younger_than_you", {"fig-hours", "fig-adaptations"}),
    1964: ("i_screwed_up_unbound_gravel_200_so_you_dont_have_to", {"fig-if"}),
    1923: ("i_screwed_up_belgian_waffle_ride_so_you_dont_have_to", set()),
    2065: ("i_screwed_up_gunni_grinder_so_you_dont_have_to", set()),
    3617: ("i_got_into_yoga_so_you_dont_have_to", set()),
    2927: ("maybe_stop_sandbagging_your_goals", {"fig-steps"}),
    3653: ("tour_of_the_gila_stage_1_full_tilt_like_a_peter_built", set()),
    2684: ("the_double_day_11_how_do_you_get_excited_for_crits", set()),
    3281: ("tour_of_the_gila_inner_loop_road_race", set()),
    3673: ("tour_of_the_gila_stage_5_the_big_sad", set()),
}
# Live descriptions that misstate the post, replaced (meta, og, JSON-LD) by DESCRIPTION.
REWRITTEN = {2065, 3617, 3653, 2684, 3281, 3673}


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
    assert live["canonical"] == url
    assert f'<link rel="canonical" href="{url}">' in html
    assert f"<title>{es.esc(getattr(m, 'TITLE', None) or live['title'])}</title>" in html
    desc = getattr(m, "DESCRIPTION", None) or live["description"]
    assert f'<meta name="description" content="{es.esc(desc)}">' in html
    assert f'<meta property="og:title" content="{es.esc(getattr(m, "TITLE", None) or live["og_title"])}">' in html
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert [b["@type"] for b in ld] == ["BlogPosting"]
    assert ld[0]["headline"] == (m.TITLE.removesuffix(" | Gravel God") if hasattr(m, "TITLE") else live["headline"]) and ld[0]["datePublished"] == live["published"]
    assert ld[0]["mainEntityOfPage"] == url and ld[0]["description"] == desc
    head = html.split("</head>", 1)[0]
    assert f'<meta property="article:published_time" content="{live["published"]}">' in head
    assert m.OUTPUT_PATH == PROJECT_ROOT / "wordpress" / "posts" / m.SLUG / "index.html"


@pytest.mark.parametrize("pid", POSTS)
def test_rewritten_descriptions_are_plain_and_consistent(pid):
    m = _module(pid)
    html = _page(pid)
    if pid not in REWRITTEN:
        assert not hasattr(m, "DESCRIPTION")
        return
    d = m.DESCRIPTION
    assert d != m.SOURCE.data["live"]["description"]
    assert len(d) <= 160 and "!" not in d and not re.search(r"\b(I|me|my|we|our)\b", d), d
    assert f'<meta property="og:description" content="{es.esc(d)}">' in html
    assert es.esc(m.SOURCE.data["live"]["description"]) not in html


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
    feat = m.SOURCE.data["featured"]
    og = m.SOURCE.data["renditions"][feat["name"]]["og"]
    assert f'<meta property="og:image" content="https://gravelgodcycling.com/{m.SLUG}/img/{og["file"]}">' in _page(pid)
    assert (m.OUTPUT_PATH.parent / "img" / og["file"]).stat().st_size <= imp.OG_MAX_BYTES


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
def test_in_short_claims(pid):
    """2-4 claims (at most 2 under 800 words), each at most 25 words, plain
    (no first person, no "!"), each linking to an anchor on the page."""
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


def test_comments_only_where_the_post_had_them():
    for pid in POSTS:
        n = len(_module(pid).SOURCE.data["comments"])
        assert ('id="comments"' in _page(pid)) == bool(n), pid
    assert "1 comment from the original post" in _page(1964)


def test_gila_gallery_has_one_figure_per_photo():
    html = _page(3281)
    grid = html.split('<figure class="gg-gallery"', 1)[1].split("</figure>", 1)[0]
    assert grid.count('class="gg-gallery-item"') == 5


def test_hours_bars_use_the_posts_numbers():
    m = _module(2956)
    body = m.SOURCE.body
    assert "200 hours? 300? 500?" in body and "750 hours." in body and "850-1000 hours a year" in body
    assert [(lo, hi) for _, lo, hi, _ in m.HOURS] == [(200, 200), (300, 300), (500, 500), (750, 750), (850, 1000)]


def test_adaptation_tiers_are_the_screenshots_words_with_the_original_kept():
    m = _module(2956)
    alt = m.ALT["screen-shot-2023-01-19-at-12-18-30-pm"]
    assert [w for w, _ in m.TIERS] == ["Weeks", "Months", "Years", "Decades"] and all(w in alt for w, _ in m.TIERS)
    fig = _page(2956).split('id="fig-adaptations"', 1)[1].split("</figure>", 1)[0]
    assert '<details class="gg-original" data-gg-added>' in fig and "screen-shot-2023-01-19-at-12-18-30-pm" in fig


def test_if_scale_values_come_from_the_text_and_the_file():
    m = _module(1964)
    body = m.SOURCE.body
    assert ".55 is recovery pace" in body and "should not exceed .69" in body and "1.0 is an all out effort" in body
    alt = m.ALT["dk-card"]
    for v, _, source, _ in m.MARKS:
        if source == "file":
            assert f"{v:.2f}" in alt


def test_steps_chart_matches_the_original_and_keeps_it():
    m = _module(2927)
    assert [lv for _, lv, _ in m.PATHS] == [(1, 2, 1, 2), (1, 2, 3, 4)]
    fig = _page(2927).split('id="fig-steps"', 1)[1].split("</figure>", 1)[0]
    assert fig.count("<svg") == 2 and fig.count('data-draw="grow"') == 8
    assert '<details class="gg-original" data-gg-added>' in fig


def test_paragraph_anchors_leave_the_text_unchanged():
    for pid in (3617, 2065):
        m = _module(pid)
        for start, aid in m.ANCHORS.items():
            assert f'<p id="{aid}">{start}' in _page(pid)
