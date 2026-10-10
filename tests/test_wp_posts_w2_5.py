"""Imported WordPress posts, batch W2-5. The same per-post checks as
tests/test_wp_post_import.py runs on the pilots, for this batch's posts, plus
this batch's corrected meta descriptions, infographics and comment archive.
Fixtures in tests/fixtures/wp_posts/<id>.*.
"""
from __future__ import annotations

import html as htmllib
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
    2521: ("what_is_hrv_and_why_should_i_care", {"fig-load-patterns"}),
    3594: ("eight_years_of_nate_wilson", {"fig-road-to-cat-1"}),
    3483: ("i_didnt_screw_up_ned_gravel_and_neither_do_you", set()),
    2790: ("i_screwed_up_the_ironhorse_classic_so_you_dont_have_to", set()),
    2904: ("how_to_develop_your_athletic_sht_detector", {"fig-compass"}),
    1496: ("how_do_i_know_if_im_getting_fitter", set()),
    3662: ("tour_of_the_gila_stage_4_its_not_the_rider_its_the_bike", set()),
    3791: ("random_midweek_thought_stay_present", set()),
    2649: ("the_double_day_8_check_yourself_before_you_wreck_yourself", set()),
    2552: ("the_double_day_1", set()),
}
# Posts whose live meta description misstated the post (module DESCRIPTION).
CORRECTED = (2552, 2649, 3791, 3662, 2904, 1496)


def _module(pid):
    return importlib.import_module(POSTS[pid][0])


def _page(pid) -> str:
    return _module(pid).OUTPUT_PATH.read_text(encoding="utf-8")


def _plain(fragment: str) -> str:
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


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
    page = _page(pid)
    url = f"https://gravelgodcycling.com/{m.SLUG}/"
    assert m.SLUG == json.loads((FIXTURES / f"{pid}.record.json").read_text(encoding="utf-8"))["slug"]
    assert live["canonical"] == url
    assert f'<link rel="canonical" href="{url}">' in page
    assert f"<title>{es.esc(getattr(m, 'TITLE', None) or live['title'])}</title>" in page
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)]
    assert [b["@type"] for b in ld] == ["BlogPosting"]
    assert ld[0]["headline"] == (m.TITLE.removesuffix(" | Gravel God") if hasattr(m, "TITLE") else live["headline"]) and ld[0]["mainEntityOfPage"] == url
    assert m.OUTPUT_PATH == PROJECT_ROOT / "wordpress" / "posts" / m.SLUG / "index.html"


@pytest.mark.parametrize("pid", POSTS)
def test_description_is_live_unless_corrected_and_consistent(pid):
    """meta, og and JSON-LD carry the same description: the live one, or the
    module's DESCRIPTION for the posts whose live one misstated the post."""
    m = _module(pid)
    page = _page(pid)
    want = getattr(m, "DESCRIPTION", None)
    assert (want is not None) == (pid in CORRECTED)
    want = want or m.SOURCE.data["live"]["description"]
    assert f'<meta name="description" content="{es.esc(want)}">' in page
    assert f'<meta property="og:description" content="{es.esc(want)}">' in page
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S).group(1))
    assert ld["description"] == want
    if pid in CORRECTED:
        assert m.SOURCE.data["live"]["description"] not in page
        assert "!" not in want and not re.search(r"\b(I|me|my|we|our)\b", want)


@pytest.mark.parametrize("pid", POSTS)
def test_analytics_and_consent(pid):
    page = _page(pid)
    assert get_ga4_head_snippet().strip() in page
    assert "article_scroll_depth" in page
    assert "onclick=" not in page


@pytest.mark.parametrize("pid", POSTS)
def test_every_image_has_alt_text_and_committed_files(pid):
    m = _module(pid)
    page = _page(pid)
    names = [f["name"] for f in m.SOURCE.data["figures"]]
    feat = m.SOURCE.data["featured"]
    if feat and not feat["also_inline"]:
        names.append(feat["name"])
    assert sorted(m.ALT) == sorted(names)
    for name, alt in m.ALT.items():
        assert len(alt) >= 40, name
        assert f'alt="{es.esc(alt)}"' in page or f'alt="{alt}"' in page, name
    referenced = set(re.findall(r'(?:src|srcset|poster)="(img/[^" ]+)', page))
    referenced |= set(re.findall(r", (img/[^ ]+) 2x", page))
    assert referenced
    for path in referenced:
        assert (m.OUTPUT_PATH.parent / path).is_file(), path
    shipped = {p.suffix for p in (m.OUTPUT_PATH.parent / "img").iterdir()}
    assert shipped <= {".webp", ".mp4", ".webm", ".jpg"}


@pytest.mark.parametrize("pid", POSTS)
def test_gifs_are_muted_videos(pid):
    m = _module(pid)
    page = _page(pid)
    for f in m.SOURCE.data["figures"]:
        if f["kind"] == "gif":
            n = f["name"]
            # smallest file first (browsers play the first source); the MP4 always ships
            srcs = "".join(f'<source src="{s}" type="{t}">'
                           for s, t in m.wp_post.video_sources(m.SOURCE.data["renditions"][n]))
            assert srcs in page and f'img/{n}.mp4' in srcs
    assert ".gif" not in re.sub(r"https://gravelgodcycling\.com/wp-content/[^\"' ]+", "", page)


@pytest.mark.parametrize("pid", POSTS)
def test_og_image_is_the_featured_image_crop(pid):
    m = _module(pid)
    page = _page(pid)
    feat = m.SOURCE.data["featured"]
    og = m.SOURCE.data["renditions"][feat["name"]]["og"]
    assert f'<meta property="og:image" content="https://gravelgodcycling.com/{m.SLUG}/img/{og["file"]}">' in page
    local = m.OUTPUT_PATH.parent / "img" / og["file"]
    assert local.stat().st_size <= imp.OG_MAX_BYTES


@pytest.mark.parametrize("pid", POSTS)
def test_in_short_claims(pid):
    """2-4 claims (at most 2 under 800 words), each at most 25 words, plain
    (no first person, no "!"), each linking to an anchor on the page."""
    m = _module(pid)
    page = _page(pid)
    assert wp_post.in_short_problems(m.IN_SHORT, es.word_count(m.SOURCE.body)) == []
    cap = wp_post.SHORT_POST_MAX_CLAIMS if es.word_count(m.SOURCE.body) < wp_post.SHORT_POST_WORDS else 4
    assert 2 <= len(m.IN_SHORT) <= cap
    for c in m.IN_SHORT:
        text = re.sub(r"<[^>]+>", "", c.text_html)
        assert len(text.split()) <= 25, text
        assert "!" not in text and not re.search(r"\b(I|me|my|we|our)\b", text), text
        assert c.href.startswith("#") and f'id="{c.href[1:]}"' in page, c.href


@pytest.mark.parametrize("pid", POSTS)
def test_comments_archive(pid):
    """Only 3594 has an approved comment; it renders read-only, no form."""
    page = _page(pid)
    comments = _module(pid).SOURCE.data["comments"]
    if pid == 3594:
        assert len(comments) == 1
        assert 'id="comments"' in page and "Comments are closed." in page
        assert "<strong>Jim Wilson</strong>" in page and "<form" not in page
    else:
        assert comments == [] and 'id="comments"' not in page


# ── Infographics: every quoted cell is the post's own text ──


def _figure(pid: int, fid: str) -> str:
    page = _page(pid)
    return page.split(f'id="{fid}"', 1)[1].split("</figure>", 1)[0]


@pytest.mark.parametrize("pid,attr,fid", [
    (2521, "PATTERNS", "fig-load-patterns"),
    (2904, "COMPASS", "fig-compass"),
    (3594, "YEARS", "fig-road-to-cat-1"),
])
def test_infographic_quotes_are_verbatim(pid, attr, fid):
    m = _module(pid)
    body = _plain(m.SOURCE.body)
    fig = _plain(_figure(pid, fid))
    for row in getattr(m, attr):
        for quote in row[1:]:
            if quote:
                assert " ".join(quote.split()) in body, quote
                assert " ".join(quote.split()) in fig, quote


def test_paragraph_anchors_keep_the_text():
    """Anchored posts only gain an id on <p>; the words are the converter's."""
    for pid in (3483, 3791, 3594):
        m = _module(pid)
        page = _page(pid)
        for start, pid_ in m.ANCHORS.items():
            assert f'<p id="{pid_}">{start}' in page
