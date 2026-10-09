"""Imported WordPress posts, batch W1-1 (the posts that were broken live, showing
[POST_CONTENT]). The same per-post checks as tests/test_wp_post_import.py runs on
the pilots, for this batch's posts. Fixtures in tests/fixtures/wp_posts/<id>.*.

Post 1186 (since-no-one-asked-why-did-dumoulin-retire-he-just-wants-to-eat-some-cheese)
is not converted: its snapshot has an Elementor slides widget the converter does
not map (test_1186_still_fails_loudly).
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
}


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
    assert f"<title>{es.esc(live['title'])}</title>" in html
    assert f'<meta name="description" content="{es.esc(live["description"])}">' in html
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert [b["@type"] for b in ld] == ["BlogPosting"]
    assert ld[0]["headline"] == live["headline"] and ld[0]["mainEntityOfPage"] == url
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
    shipped = {p.suffix for p in (m.OUTPUT_PATH.parent / "img").iterdir()}
    assert shipped <= {".webp", ".mp4", ".webm"}


@pytest.mark.parametrize("pid", POSTS)
def test_gifs_are_muted_videos(pid):
    m = _module(pid)
    html = _page(pid)
    for f in m.SOURCE.data["figures"]:
        if f["kind"] == "gif":
            n = f["name"]
            assert f'<source src="img/{n}.webm" type="video/webm"><source src="img/{n}.mp4" type="video/mp4">' in html
    assert ".gif" not in re.sub(r"https://gravelgodcycling\.com/wp-content/[^\"' ]+", "", html)


@pytest.mark.parametrize("pid", POSTS)
def test_in_short_claims(pid):
    """2-4 claims (at most 2 under 800 words), each at most 25 words, plain
    (no first person, no "!"), each linking to an anchor on the page."""
    m = _module(pid)
    html = _page(pid)
    cap = wp_post.SHORT_POST_MAX_CLAIMS if es.word_count(m.SOURCE.body) < wp_post.SHORT_POST_WORDS else 4
    assert 2 <= len(m.IN_SHORT) <= cap
    for c in m.IN_SHORT:
        text = re.sub(r"<[^>]+>", "", c.text_html)
        assert len(text.split()) <= 25, text
        assert "!" not in text and not re.search(r"\b(I|me|my|we|our)\b", text), text
        assert c.href.startswith("#") and f'id="{c.href[1:]}"' in html, c.href


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


def test_1186_still_fails_loudly():
    """1186's slides widget has no mapping: the converter raises instead of dropping it."""
    snap = Path.home() / "specs" / "gg-wp-posts-2026-10-09" / "snapshots" / "1186.html"
    if not snap.exists():
        pytest.skip("audit snapshots not on this machine")
    with pytest.raises(NotImplementedError, match="slides"):
        imp.ElementorConverter({}).convert(snap.read_text(encoding="utf-8"))
