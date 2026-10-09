"""Imported WordPress posts, batch W2-1. The same per-post checks as
tests/test_wp_post_import.py runs on the pilots, for this batch's posts.
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
    2844: ("i_didnt_screw_up_red_granite_grinder_again_and_neither_do_you", {"fig-night-before"}),
    2324: ("i_screwed_up_sbt_grvl_so_you_dont_have_to", {"fig-sodium"}),
    3353: ("i_screwed_up_co2ut_so_you_dont_have_to", set()),
    2830: ("the_tyranny_of_irony_in_cycling", set()),
    4060: ("i_opened_a_fascat_ai_coaching_email_so_you_dont_have_to", set()),
    3825: ("right_now_i_cant", set()),
    3306: ("tour_of_the_gila_the_gila_monster", set()),
    2696: ("the_double_day_12_i_like_the_way_you_die_boy", set()),
    2608: ("the_double_day_4_sheeesh", set()),
    2623: ("the_double_day_5_rolly_gang_rolly_gang_rolly_gang", set()),
}
# Approved comments per post (read-only archive); every other post has none.
COMMENTS = {2844: 6, 4060: 1}
# Posts whose live meta description misstates the post (module DESCRIPTION).
REWRITTEN = {2844, 2324, 3353, 3825, 2696, 2608, 2623}


def _module(pid):
    return importlib.import_module(POSTS[pid][0])


def _page(pid) -> str:
    return _module(pid).OUTPUT_PATH.read_text(encoding="utf-8")


# Share-button chrome captured in a snapshot's visible text, not post text: the
# Click-to-Tweet widget's "Tweet" button label (the converter keeps the quote as a
# pull quote and drops the share button). Removed from the baseline, one line each.
SHARE_LABELS = {2623: ("Tweet",)}


def _baseline(pid) -> str:
    lines = (FIXTURES / f"{pid}.txt").read_text(encoding="utf-8").split("\n")
    snapshot = (FIXTURES / f"{pid}.html").read_text(encoding="utf-8")
    for label in SHARE_LABELS.get(pid, ()):
        assert f'<span class="elementor-blockquote__tweet-label">{label}</span>' in snapshot
        assert [ln.strip() for ln in lines].count(label) == 1, label
        lines.pop([ln.strip() for ln in lines].index(label))
    return "\n".join(lines)


@pytest.mark.parametrize("pid", POSTS)
def test_body_text_is_word_for_word(pid):
    diff = imp.text_diff(_baseline(pid), _page(pid), POSTS[pid][1])
    assert diff == [], "\n".join(diff[:80])


def test_only_the_share_label_is_dropped_from_the_baseline():
    """Without the share-label exception, the only difference is that one word."""
    diff = imp.text_diff((FIXTURES / "2623.txt").read_text(encoding="utf-8"), _page(2623), POSTS[2623][1])
    assert [d for d in diff if d[:1] in "+-" and not d.startswith(("---", "+++"))] == ["-Tweet"]


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
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert [b["@type"] for b in ld] == ["BlogPosting"]
    assert ld[0]["headline"] == live["headline"] and ld[0]["mainEntityOfPage"] == url
    assert ld[0]["datePublished"] == live["published"]
    assert m.OUTPUT_PATH == PROJECT_ROOT / "wordpress" / "posts" / m.SLUG / "index.html"


@pytest.mark.parametrize("pid", POSTS)
def test_description_is_consistent_and_rewritten_only_where_wrong(pid):
    """A rewritten description (module DESCRIPTION) replaces the live one in meta,
    OG and JSON-LD alike; the live one appears nowhere. Other posts keep the live one."""
    m = _module(pid)
    html = _page(pid)
    live = m.SOURCE.data["live"]["description"]
    desc = getattr(m, "DESCRIPTION", None)
    assert (desc is not None) == (pid in REWRITTEN)
    want = desc or live
    assert f'<meta name="description" content="{es.esc(want)}">' in html
    assert f'<meta property="og:description" content="{es.esc(want)}">' in html
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
    assert ld["description"] == want
    if desc:
        assert es.esc(live) not in html
        assert len(desc.split()) <= 35 and "!" not in desc
        assert not re.search(r"\b(I|me|my|we|our)\b(?!-)", desc), desc


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
def test_gifs_are_muted_videos(pid):
    m = _module(pid)
    html = _page(pid)
    for f in m.SOURCE.data["figures"]:
        if f["kind"] == "gif":
            n = f["name"]
            assert f'<source src="img/{n}.webm" type="video/webm"><source src="img/{n}.mp4" type="video/mp4">' in html
            tag = html.split(f'<source src="img/{n}.webm"', 1)[0].rsplit("<video", 1)[1]
            assert "muted playsinline" in tag and "autoplay" not in tag
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


@pytest.mark.parametrize("pid", POSTS)
def test_comments_archive_only_where_approved(pid):
    m = _module(pid)
    html = _page(pid)
    n = COMMENTS.get(pid, 0)
    assert len(m.SOURCE.data["comments"]) == n
    if n:
        assert 'id="comments"' in html and "<form" not in html.split('id="comments"', 1)[1]
        for c in m.SOURCE.data["comments"]:
            assert es.esc(c["author"]) in html
    else:
        assert 'id="comments"' not in html


def test_sbt_call_to_action_is_kept_verbatim():
    html = _page(2324)
    assert 'class="gg-case-study gg-cta"' in html
    assert "SBT GRVL Training Plan" in html and "Gimme' the plan" in html
    assert "trainingpeaks.com/training-plans/cycling/gran-fondo-century/tp-287683" in html


def test_sodium_table_quotes_the_post():
    m = _module(2324)
    body = m.SOURCE.body
    for _, what in m.SODIUM:
        assert what.strip("“”") in body, what
    assert 'id="fig-sodium"' in _page(2324)


def test_night_before_times_are_the_posts():
    m = _module(2844)
    body = m.SOURCE.body
    for when, _ in m.NIGHT:
        assert when in body or when.capitalize() in body, when
    html = _page(2844)
    assert html.index('id="p-derailleur"') < html.index('id="fig-night-before"') < html.index('id="p-brakes"')


@pytest.mark.parametrize("pid", (2844, 2324, 3353, 3825))
def test_paragraph_anchors_change_no_text(pid):
    m = _module(pid)
    for start, aid in m.ANCHORS.items():
        assert f'<p id="{aid}">{start}' in _page(pid)
