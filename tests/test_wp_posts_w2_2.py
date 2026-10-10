"""Imported WordPress posts, batch W2-2. The same per-post checks as
tests/test_wp_post_import.py runs on the pilots, for this batch's posts, plus
this batch's infographics, paragraph anchors and corrected descriptions.
Fixtures in tests/fixtures/wp_posts/<id>.*.
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
    2209: ("i_didnt_screw_up_red_granite_grinder_and_neither_do_you", {"fig-rgg-race"}),
    3520: ("i_didnt_screw_up_sbt_grvl_and_neither_do_you", set()),
    3694: ("listening_to_robert_in_silver_city", set()),
    2942: ("how_to_not_fk_up_your_holiday_training", set()),
    3811: ("but_are_you_eating_almonds_out_of_your_purse", {"fig-killer-math"}),
    3945: ("maybe_a_hate_poster_is_what_youve_been_missing", set()),
    3796: ("i_messed_up_big_horn_gravel_so_you_dont_have_to", set()),
    2916: ("and_just_like_that_its_over", set()),
    3278: ("tour_of_the_gila_tyrone_time_trial", set()),
    3335: ("tour_of_the_gila_the_mogollon", set()),
    2563: ("the_double_day_2_thiccc_is_kwik", set()),
}
# Posts whose live meta description misstated the post (module DESCRIPTION).
CORRECTED = {2209, 3520, 3796, 2916, 3278, 3335, 2563}


def _module(pid):
    return importlib.import_module(POSTS[pid][0])


def _page(pid) -> str:
    return _module(pid).OUTPUT_PATH.read_text(encoding="utf-8")


# Snapshot artifacts: the snapshot .txt is the post's textContent, which glues the
# text before a nested list to the list's first word ("people will:</span><ol><li>
# <span>Compliment" -> "will:Compliment"). The page renders the same words in the
# same blocks; only that block boundary is restored here, nothing else is relaxed.
SNAPSHOT_GLUE = {3520: ("will:Compliment", "will: Compliment")}
# Elementor template filler the converter drops (wp_post_import.ELEMENTOR_PLACEHOLDER_HEADING):
# an unedited heading widget, not the author's words. Only that string may be absent.
SNAPSHOT_FILLER = {2942: imp.ELEMENTOR_PLACEHOLDER_HEADING}


def _baseline(pid) -> str:
    text = (FIXTURES / f"{pid}.txt").read_text(encoding="utf-8")
    if pid in SNAPSHOT_GLUE:
        glued, split = SNAPSHOT_GLUE[pid]
        assert text.count(glued) == 1, glued
        text = text.replace(glued, split)
    if pid in SNAPSHOT_FILLER:
        filler = SNAPSHOT_FILLER[pid]
        assert text.count(filler) == 1, filler
        text = text.replace(filler, "")
    return text


@pytest.mark.parametrize("pid", POSTS)
def test_body_text_is_word_for_word(pid):
    diff = imp.text_diff(_baseline(pid), _page(pid), POSTS[pid][1])
    assert diff == [], "\n".join(diff[:80])


def test_3520_glue_is_only_a_block_boundary():
    """Unpatched, the one difference is the glued token, split at the nested list."""
    diff = imp.text_diff((FIXTURES / "3520.txt").read_text(encoding="utf-8"), _page(3520))
    assert [d for d in diff if d[:1] in "+-" and d[:3] not in ("---", "+++")] == [
        "-will:Compliment", "+will:", "+Compliment"]
    assert "people will:<ol>" in _module(3520).SOURCE.body


def test_2942_placeholder_heading_is_the_only_text_dropped():
    """Unpatched, the one difference is Elementor's placeholder heading, missing from the page."""
    diff = imp.text_diff((FIXTURES / "2942.txt").read_text(encoding="utf-8"), _page(2942))
    assert [d for d in diff if d[:1] in "+-" and d[:3] not in ("---", "+++")] == [
        "-Add", "-Your", "-Heading", "-Text", "-Here"]
    assert imp.ELEMENTOR_PLACEHOLDER_HEADING not in _page(2942)
    assert imp.ELEMENTOR_PLACEHOLDER_HEADING not in _module(2942).SOURCE.body


@pytest.mark.parametrize("pid", POSTS)
def test_converter_reproduces_committed_body_and_metadata(pid):
    record = json.loads((FIXTURES / f"{pid}.record.json").read_text(encoding="utf-8"))
    conv, data = imp.import_post(record, (FIXTURES / f"{pid}.html").read_text(encoding="utf-8"),
                                 (FIXTURES / f"{pid}.live-head.html").read_text(encoding="utf-8"))
    src = _module(pid).SOURCE
    assert conv.body_html == src.body
    assert data["live"] == src.data["live"]
    assert [f["name"] for f in data["figures"]] == [f["name"] for f in src.data["figures"]]
    assert data["featured"] == src.data["featured"]


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
    assert m.SLUG == m.SOURCE.data["slug"] and live["canonical"] == url
    assert f'<link rel="canonical" href="{url}">' in html
    assert f"<title>{es.esc(getattr(m, 'TITLE', None) or live['title'])}</title>" in html
    desc = getattr(m, "DESCRIPTION", None) or live["description"]
    assert (pid in CORRECTED) == hasattr(m, "DESCRIPTION")
    assert f'<meta name="description" content="{es.esc(desc)}">' in html
    assert f'<meta property="og:description" content="{es.esc(desc)}">' in html
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert [b["@type"] for b in ld] == ["BlogPosting"]
    assert ld[0]["headline"] == (m.TITLE.removesuffix(" | Gravel God") if hasattr(m, "TITLE") else live["headline"]) and ld[0]["datePublished"] == live["published"]
    assert ld[0]["mainEntityOfPage"] == url and ld[0]["description"] == desc
    assert m.OUTPUT_PATH == PROJECT_ROOT / "wordpress" / "posts" / m.SLUG / "index.html"
    if pid in CORRECTED:
        assert es.esc(live["description"]) not in html


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
        assert es.esc(alt) in html, name
    img_dir = m.OUTPUT_PATH.parent / "img"
    referenced = set(re.findall(r'(?:src|srcset|data-poster)="(img/[^" ]+)', html))
    referenced |= set(re.findall(r", (img/[^ ]+) 2x", html))
    for path in referenced:
        assert (m.OUTPUT_PATH.parent / path).is_file(), path
    shipped = {p.suffix for p in img_dir.iterdir() if not p.name.endswith("-og.jpg")}
    assert shipped <= {".webp", ".mp4", ".webm"}
    assert [p.name for p in img_dir.glob("*.jpg")] == ([f"{feat['name']}-og.jpg"] if feat else [])


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
        assert c.href.startswith("#") and html.count(f'id="{c.href[1:]}"') == 1, c.href


@pytest.mark.parametrize("pid", POSTS)
def test_no_comments_on_this_batch(pid):
    assert _module(pid).SOURCE.data["comments"] == []
    assert 'id="comments"' not in _page(pid)


@pytest.mark.parametrize("pid", [p for p in POSTS if hasattr(importlib.import_module(POSTS[p][0]), "ANCHORS")])
def test_paragraph_anchors_only_add_ids(pid):
    m = _module(pid)
    html = _page(pid)
    for start, aid in m.ANCHORS.items():
        assert f'<p id="{aid}">{start}' in html
        assert m.SOURCE.body.count(f"<p>{start}") == 1


def test_gila_galleries_have_every_photo():
    for pid, n in ((3278, 4), (3335, 10)):
        m = _module(pid)
        (names,) = m.SOURCE.data["galleries"].values()
        assert len(names) == len(set(names)) == n
        html = _page(pid)
        for name in names:
            assert html.count(f'src="img/{name}.webp"') == 1, name


def test_rgg_race_figure_uses_the_posts_miles():
    m = _module(2209)
    body = m.SOURCE.body
    for phrase in ("We’d ridden 8 miles", "7 of them did 35 miles in", "Highway 29 at mile 50",
                   "100 miles down, 44 to go", "14 miles from the finish", "less than 10 miles out",
                   "8 hours and 20 minutes", "144 miles in total"):
        assert phrase in body, phrase
    assert [r[0] for r in m.RACE] == ["Mile 8", "Mile 35", "Mile 50", "Mile 100", "14 to go",
                                      "Under 10 to go", "Mile 144"]
    assert m.TOTAL == 144
    fig = _page(2209).split('id="fig-rgg-race"', 1)[1].split("</figure>", 1)[0]
    assert fig.count('data-draw="grow-x"') == len(m.RACE) and "is-span" in fig


def test_killer_math_table_is_the_posts_numbers():
    m = _module(3811)
    body = m.SOURCE.body
    for row in m.KILLER_MATH.rows:
        for cell in row.cells[1:]:
            v = cell.html.replace("&minus;", "-")
            assert v.lstrip("+-") in body, v
    for v in ("+2.10", "+3.31", "+500", "+179", "Starting total: -1", "New total: 0", "New total: +1"):
        assert v in body, v


def test_2209_is_its_own_slug_not_3537():
    m = _module(2209)
    assert m.SOURCE.data["id"] == 2209
    assert m.SLUG == "i-didnt-screw-up-red-granite-grinder-and-neither-do-you"
