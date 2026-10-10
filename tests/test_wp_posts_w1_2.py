"""Imported WordPress posts, batch W1-2 (the five posts that showed a [POST_CONTENT]
placeholder live): 2298, 1626, 2191, 1499, 1673.

The same checks tests/test_wp_post_import.py runs on the pilots, for this batch's
modules. Fixtures in tests/fixtures/wp_posts/ (from the 2026-10-09 WP audit):
  <id>.html            the post's rendered Elementor content (the converter input)
  <id>.txt             its visible text: the word-for-word baseline
  <id>.record.json     the inventory record (slug, images, featured image)
  <id>.live-head.html  the live page's <head> tags the converter reads

Click-to-Tweet: 1499's snapshot text carries the label of each Click-to-Tweet
button ("Tweet"), which the converter drops with the button. The baseline loses
exactly one standalone "Tweet" line per tweet button in the snapshot HTML, and
nothing else.
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
    2298: ("how_to_achieve_your_goals_and_stop_ruining_your_dreams", set()),  # HtmlFigure: data-gg-added
    1626: ("post_5_ways_to_become_a_power_meter_clown", {"fig-power-meters"}),
    2191: ("if_you_really_want_to_race_bikes_fast_train_your_heart", set()),
    1499: ("your_eating_habits_are_killing_your_performance", {"fig-waffles-tests"}),
    1673: ("you_know_people_remember_how_you_race_right", set()),
}
INFOGRAPHICS = {2298: "fig-weight-chart", 1626: "fig-power-meters", 1499: "fig-waffles-tests"}
COMMENTS = {2298: 1}


def _module(pid):
    return importlib.import_module(POSTS[pid][0])


def _page(pid) -> str:
    return _module(pid).OUTPUT_PATH.read_text(encoding="utf-8")


def _baseline(pid) -> str:
    """The snapshot text minus Click-to-Tweet button labels (one per button)."""
    lines = (FIXTURES / f"{pid}.txt").read_text(encoding="utf-8").splitlines()
    kept = [ln for ln in lines if ln.strip() != "Tweet"]
    buttons = (FIXTURES / f"{pid}.html").read_text(encoding="utf-8").count('tweet-label">Tweet<')
    assert len(lines) - len(kept) == buttons
    return "\n".join(kept)


@pytest.mark.parametrize("pid", POSTS)
def test_body_text_is_word_for_word(pid):
    diff = imp.text_diff(wp_post.corrected_baseline(_baseline(pid), getattr(_module(pid), "CORRECTIONS", ())), _page(pid), POSTS[pid][1])
    assert diff == [], "\n".join(diff[:80])


def test_only_1499_has_tweet_labels():
    assert {pid for pid in POSTS if (FIXTURES / f"{pid}.html").read_text().count('tweet-label">Tweet<')} == {1499}


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
    ld = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    assert [b["@type"] for b in ld] == ["BlogPosting"]
    assert ld[0]["headline"] == (m.TITLE.removesuffix(" | Gravel God") if hasattr(m, "TITLE") else live["headline"]) and ld[0]["mainEntityOfPage"] == url
    assert ld[0]["description"] == desc
    assert m.OUTPUT_PATH == PROJECT_ROOT / "wordpress" / "posts" / m.SLUG / "index.html"


@pytest.mark.parametrize("pid", POSTS)
def test_analytics_and_consent(pid):
    html = _page(pid)
    assert get_ga4_head_snippet().strip() in html
    assert "article_scroll_depth" in html and "onclick=" not in html


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
        if f["kind"] != "gif":
            continue
        n = f["name"]
        # smallest file first (browsers play the first source); the MP4 always ships
        srcs = "".join(f'<source src="{s}" type="{t}">'
                       for s, t in m.wp_post.video_sources(m.SOURCE.data["renditions"][n]))
        assert srcs in html and f'img/{n}.mp4' in srcs
    assert ".gif" not in re.sub(r"https://gravelgodcycling\.com/wp-content/[^\"' ]+", "", html)


@pytest.mark.parametrize("pid", POSTS)
def test_in_short_is_plain_and_linked(pid):
    """2-4 claims, each at most 25 words, linking to an anchor on the page;
    matter-of-fact: no first person, no exclamation marks."""
    m = _module(pid)
    html = _page(pid)
    assert 2 <= len(m.IN_SHORT) <= 4
    for c in m.IN_SHORT:
        text = re.sub(r"<[^>]+>", "", c.text_html)
        assert len(text.split()) <= 25, c.text_html
        assert "!" not in text and not re.search(r"\b(I|me|my|we|our|you|your)\b", text), text
        assert c.href.startswith("#") and f'id="{c.href[1:]}"' in html, c.href


@pytest.mark.parametrize("pid", POSTS)
def test_infographics_and_comments(pid):
    html = _page(pid)
    fid = INFOGRAPHICS.get(pid)
    assert len(re.findall(r'<figure class="gg-fig gg-htmlfig"|class="gg-table', html)) >= (1 if fid else 0)
    if fid:
        assert f'id="{fid}"' in html
    n = COMMENTS.get(pid, 0)
    if n:
        archive = html.split('id="comments"', 1)[1].split("</section>", 1)[0]
        assert archive.count('class="gg-comment"') == n and "<form" not in archive
    else:
        assert 'id="comments"' not in html


def test_weight_chart_ends_on_the_charts_own_labels():
    m = _module(2298)
    pts = m.WEIGHINS.split()
    assert pts[0] == "2.2:186.5" and pts[-1] == "121.4:169.1"
    html = _page(2298)
    assert "186.5 lb · Nov 27" in html and "169.1 lb · Mar 26" in html


def test_tables_use_the_posts_numbers():
    pm = _page(1626).split('id="fig-power-meters"', 1)[1].split("</figure>", 1)[0]
    for w in ("280 W", "310 W", "270 W", "500 W", "460 W", "480 W"):
        assert w in pm
    wt = _page(1499).split('id="fig-waffles-tests"', 1)[1].split("</figure>", 1)[0]
    for v in ("369 W", "291 W", "149 lb", "376 W", "296 W", "148 lb", "397 W", "321 W", "155 lb"):
        assert v in wt


# post id -> (a phrase in the wrong live description, a phrase in the correction)
CORRECTED = {
    2191: ("cardiac output", "young children"),
    1626: ("chasing FTP", "racing by power"),
}


@pytest.mark.parametrize("pid", POSTS)
def test_corrected_descriptions_replace_meta_og_and_json_ld(pid):
    """2191 is about motivation and family, not cardiac output; 1626's five
    mistakes don't include chasing FTP. Only those two override the live text."""
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


def test_power_meter_clown_has_no_page_css():
    """The shell's phone Contents bar handles 20 sections; no page-only patch."""
    assert not hasattr(_module(1626), "CSS")
    assert ".toc-m .mini i{width:7px" not in _page(1626)
