"""Imported WordPress posts, batch W1-3 (the 8 posts that showed "[POST_CONTENT]" live).

Same checks as tests/test_wp_post_import.py runs on the pilots, for this batch's
modules in wordpress/post_sources/, plus the batch rules: "In short" is plain and
third person, the read-only comment archive matches the inventory, and every
number in an added infographic is stated in the post.

Fixtures in tests/fixtures/wp_posts/<id>.* (from the 2026-10-09 WP audit).
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
for _p in ("scripts", "wordpress", "wordpress/post_sources"):
    if str(PROJECT_ROOT / _p) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT / _p))

import editorial_shell as es  # noqa: E402
import wp_post  # noqa: E402
import wp_post_import as imp  # noqa: E402

POSTS = {
    2014: "how_to_hydrate_so_you_dont_die_in_your_gravel_race",
    2394: "no_one_cares_if_youre_bored",
    2414: "to_make_it_count_flip_the_switch",
    2445: "your_frame_is_all_there_is",
    1879: "the_jester_precedes_the_king",
    1269: "does_beer_make_you_slow",
    2345: "gratitude_and_toilet_bowls",
    1431: "you_dont_need_to_bike_to_bike_fast",
}
TWEET_LABEL = 'elementor-blockquote__tweet-label">Tweet</span>'


def _module(pid):
    return importlib.import_module(POSTS[pid])


def _page(pid) -> str:
    return _module(pid).OUTPUT_PATH.read_text(encoding="utf-8")


def _baseline(pid) -> str:
    """The snapshot text, minus the Click-to-Tweet button labels ("Tweet"): share-button
    chrome, not article text; the converter turns the quote into a pull quote without it."""
    txt = (FIXTURES / f"{pid}.txt").read_text(encoding="utf-8")
    n = (FIXTURES / f"{pid}.html").read_text(encoding="utf-8").count(TWEET_LABEL)
    words = imp.words(txt)
    for _ in range(n):
        words.remove("Tweet")
    return " ".join(words)


@pytest.mark.parametrize("pid", POSTS)
def test_body_text_is_word_for_word(pid):
    diff = imp.text_diff(_baseline(pid), _page(pid), getattr(_module(pid), "ADDED_IDS", set()))
    assert diff == [], "\n".join(diff[:80])


def test_only_tweet_button_labels_are_dropped():
    raw = (FIXTURES / "1431.txt").read_text(encoding="utf-8")
    assert imp.words(raw).count("Tweet") == 2 and imp.words(_baseline(1431)).count("Tweet") == 0
    assert len(imp.words(raw)) - len(imp.words(_baseline(1431))) == 2


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
def test_page_lives_at_its_original_url_with_live_metadata(pid):
    m = _module(pid)
    live = m.SOURCE.data["live"]
    html = _page(pid)
    url = f"https://gravelgodcycling.com/{m.SLUG}/"
    assert live["canonical"] == url and f'<link rel="canonical" href="{url}">' in html
    assert f"<title>{es.esc(getattr(m, 'TITLE', None) or live['title'])}</title>" in html
    desc = getattr(m, "DESCRIPTION", None) or live["description"]
    assert f'<meta name="description" content="{es.esc(desc)}">' in html
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert [b["@type"] for b in ld] == ["BlogPosting"] and ld[0]["description"] == desc
    assert "[POST_CONTENT]" not in html
    assert m.OUTPUT_PATH == PROJECT_ROOT / "wordpress" / "posts" / m.SLUG / "index.html"


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
    assert shipped <= {".webp", ".mp4", ".webm"}, "WebP + video only (+ the og:image JPEG)"
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


FIRST_PERSON = re.compile(r"\b(I|I'm|I’m|me|my|mine|we|our|us)\b")


@pytest.mark.parametrize("pid", POSTS)
def test_in_short_is_plain_short_and_linked(pid):
    """2-4 claims (at most 2 under 800 words), each <= 25 words, linking to an anchor
    on the page; matter of fact: no first person, no exclamation marks."""
    m = _module(pid)
    html = _page(pid)
    cap = 2 if es.word_count(m.SOURCE.body) < wp_post.SHORT_POST_WORDS else 4
    assert 2 <= len(m.IN_SHORT) <= cap
    for c in m.IN_SHORT:
        plain = re.sub(r"<[^>]+>", "", c.text_html).replace("&rsquo;", "’")
        assert len(plain.split()) <= 25, plain
        assert "!" not in plain and not FIRST_PERSON.search(plain), plain
        assert c.href.startswith("#") and f'id="{c.href[1:]}"' in html, c.href


@pytest.mark.parametrize("pid", POSTS)
def test_comments_render_as_the_read_only_archive(pid):
    record = json.loads((FIXTURES / f"{pid}.record.json").read_text(encoding="utf-8"))
    html = _page(pid)
    n = record["comment_count"]
    assert html.count('class="gg-comment"') == n == len(_module(pid).SOURCE.data["comments"])
    if n:
        assert "data-gg-archive" in html and "Comments are closed." in html
    assert "<textarea" not in html and 'name="comment"' not in html


def _post_text(pid) -> str:
    return (FIXTURES / f"{pid}.txt").read_text(encoding="utf-8")


def test_switch_hours_numbers_are_the_posts():
    import to_make_it_count_flip_the_switch as m
    text = _post_text(2414)
    for phrase in ("roughly 80 days, or 11 weeks", "down to 58 days", "that leaves 50 days",
                   "75 hours of training stress", "more like 60 hours", "about 80% quality"):
        assert phrase in text, phrase
    assert [n for _, _, n in m.DAYS] == [80, 58, 50] and [n for _, _, n in m.HOURS] == [75, 60]


def test_sodium_bars_are_the_posts_rule():
    import how_to_hydrate_so_you_dont_die_in_your_gravel_race as m
    text = _post_text(2014)
    for label, value, _, _ in m.SODIUM:
        assert f"{label}? Put a {value} sodium tablet in your water bottle." in text
    assert "Drink a bottle like that every hour you’re riding in hot conditions." in text


def test_beer_steps_redraw_keeps_the_original_one_click_away():
    import does_beer_make_you_slow as m
    html = _page(1269)
    assert len(m.SOBER) == 8 and len(m.DRINKING) == 7
    fig = html.split('id="fig-beer-steps"', 1)[1].split("</figure>", 1)[0]
    assert "data-draw-in" in html.split('id="fig-beer-steps"', 1)[0][-300:] + fig[:200]
    assert '<details class="gg-original"' in fig and "fitness-progression-sober-1" in fig
    assert 'id="fig-fitness-progression-sober"' in html  # the sober-only chart stays as published


# post id -> (a phrase in the wrong live description, a phrase in the correction)
CORRECTED = {
    2414: ("racing is war", "offseason"),
    1269: ("The evidence", "metaphors rather than studies"),
}


@pytest.mark.parametrize("pid", POSTS)
def test_corrected_descriptions_replace_meta_og_and_json_ld(pid):
    """2414 is about switching from the offseason to discipline, not race-day
    intensity; 1269 argues by metaphor and cites no studies. Only those two
    override the live text."""
    m = _module(pid)
    if pid not in CORRECTED:
        assert not hasattr(m, "DESCRIPTION")
        return
    wrong, right = CORRECTED[pid]
    html = _page(pid)
    assert wrong in m.SOURCE.data["live"]["description"] and wrong not in html
    assert right in m.DESCRIPTION
    assert len(m.DESCRIPTION) <= 160 and "!" not in m.DESCRIPTION
    assert not re.search(r"\b(I|me|my|we|our|you|your)\b", m.DESCRIPTION)
    for tag in ('name="description"', 'property="og:description"'):
        assert f'<meta {tag} content="{es.esc(m.DESCRIPTION)}">' in html
