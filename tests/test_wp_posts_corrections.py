"""Figure corrections and dead YouTube embeds on imported WordPress posts
(Matt, 2026-10-09: "Yeah go ahead and fix").

A post module's CORRECTIONS (wp_post.Correction: old, new, why) are the only
text the page may change. The batch tests compare each page with its snapshot
after applying the same corrections; this file checks the other direction:
against the raw snapshot, every difference is one of the corrections. It also
checks the correction note, the bumped modified date, and that each
DEAD_YOUTUBE embed is gone from the page but still recorded in the body.
"""
from __future__ import annotations

import difflib
import importlib
import json
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "wp_posts"
SOURCES = PROJECT_ROOT / "wordpress" / "post_sources"
for _p in ("scripts", "wordpress", "wordpress/post_sources", "tests"):
    if str(PROJECT_ROOT / _p) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT / _p))

import wp_post  # noqa: E402
import wp_post_import as imp  # noqa: E402

BATCHES = ("test_wp_post_import",) + tuple(
    f"test_wp_posts_{w}" for w in ("w1_1", "w1_2", "w1_3", "w2_1", "w2_2", "w2_3", "w2_4", "w2_5"))


def _batches() -> dict[int, object]:
    """post id -> the batch test module that owns it (its POSTS / PILOTS map)."""
    out = {}
    for name in BATCHES:
        t = importlib.import_module(name)
        for pid in getattr(t, "POSTS", None) or getattr(t, "PILOTS"):
            out[pid] = t
    return out


BATCH = _batches()


def _entry(t, pid):
    v = (getattr(t, "POSTS", None) or getattr(t, "PILOTS"))[pid]
    return (v, set()) if isinstance(v, str) else (v[0], set(v[1]) if len(v) > 1 else set())


MODULES = {pid: _entry(t, pid)[0] for pid, t in BATCH.items()}
CORRECTED = sorted(pid for pid, m in MODULES.items() if getattr(importlib.import_module(m), "CORRECTIONS", ()))
DEAD = sorted(pid for pid, m in MODULES.items() if getattr(importlib.import_module(m), "DEAD_YOUTUBE", None))
LIVE_VIDEO = "4WWNUjAwNKw"  # Red Granite Grinder again: still on YouTube, stays


def _module(pid):
    return importlib.import_module(MODULES[pid])


def _page(pid) -> str:
    return _module(pid).OUTPUT_PATH.read_text(encoding="utf-8")


def _baseline_and_skip(pid) -> tuple[str, set[str]]:
    t = BATCH[pid]
    text = t._baseline(pid) if hasattr(t, "_baseline") else (FIXTURES / f"{pid}.txt").read_text(encoding="utf-8")
    skip = _entry(t, pid)[1]
    if t.__name__.endswith("w1_3"):
        skip = getattr(_module(pid), "ADDED_IDS", set())
    return text, skip


def test_every_post_is_covered_and_the_lists_are_the_approved_ones():
    assert len(MODULES) == 77
    assert len(CORRECTED) == 12
    assert DEAD == sorted([2844, 3537, 2065, 2324, 1964, 3662, 3673])


@pytest.mark.parametrize("pid", CORRECTED)
def test_corrections_are_the_only_differences_from_the_snapshot(pid):
    """Raw snapshot vs page: every changed run of words sits inside one
    correction (old words -> new words), and every correction shows up."""
    m = _module(pid)
    base, skip = _baseline_and_skip(pid)
    a = imp.words(" ".join(base.split()))
    b = imp.words(imp.visible_text(imp.article_of(_page(pid)), skip))
    def spans(tokens, texts):
        """Token index range [s, e) covering each text's one occurrence."""
        joined = " ".join(tokens)
        out = []
        for t in texts:
            t = " ".join(t.split())
            assert joined.count(t) == 1, t
            pos = joined.index(t)
            out.append((joined[:pos].count(" "), joined[:pos + len(t)].count(" ") + 1))
        return out

    old = spans(a, [c.old for c in m.CORRECTIONS])
    new = spans(b, [c.new for c in m.CORRECTIONS])
    used = set()
    hunks = [op for op in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes() if op[0] != "equal"]
    assert hunks, "no corrections reached the page"
    for _, i1, i2, j1, j2 in hunks:
        hits = [k for k in range(len(old))
                if old[k][0] <= i1 and i2 <= old[k][1] and new[k][0] <= j1 and j2 <= new[k][1]]
        assert hits, f"unexplained change: {a[i1:i2]} -> {b[j1:j2]}"
        used.update(hits)
    assert used == set(range(len(old))), "a correction left no trace on the page"


@pytest.mark.parametrize("pid", CORRECTED)
def test_correction_entries_are_exact_and_carry_their_evidence(pid):
    m = _module(pid)
    for c in m.CORRECTIONS:
        assert isinstance(c, wp_post.Correction)
        assert c.old != c.new and len(c.why.split()) >= 4
        assert m.SOURCE.body.count(c.old) == 1
        assert c.old not in _page(pid) or c.old in c.new


@pytest.mark.parametrize("pid", CORRECTED)
def test_corrected_post_says_so_and_bumps_its_modified_date(pid):
    html = _page(pid)
    note = wp_post.CORRECTION_NOTE
    assert html.count(note) == 1
    assert f'<p class="gg-corrected" data-gg-added>{note}</p>' in imp.article_of(html)
    head = html.split("</head>", 1)[0]
    assert f'<meta property="article:modified_time" content="{wp_post.CORRECTED_MODIFIED}">' in head
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
    assert ld["dateModified"] == wp_post.CORRECTED_MODIFIED
    assert ld["datePublished"] == _module(pid).SOURCE.data["live"]["published"]


RESTORED = sorted(pid for pid, m in MODULES.items() if getattr(importlib.import_module(m), "RESTORED", ()))


@pytest.mark.parametrize("pid", sorted(set(MODULES) - set(CORRECTED) - set(RESTORED)))
def test_uncorrected_posts_keep_the_live_modified_date_and_no_note(pid):
    html = _page(pid)
    assert wp_post.CORRECTION_NOTE not in html
    live = _module(pid).SOURCE.data["live"]
    if live.get("modified"):
        assert f'<meta property="article:modified_time" content="{live["modified"]}">' in html


@pytest.mark.parametrize("pid", DEAD)
def test_dead_youtube_embeds_are_left_out_but_recorded(pid):
    m = _module(pid)
    html = _page(pid)
    for vid, where in m.DEAD_YOUTUBE.items():
        assert where.strip()
        assert f'data-yt="{vid}"' in m.SOURCE.body  # still in the converter body: restorable
        assert vid not in html
    assert not re.search(r'<figure class="gg-yt">\s*</figure>', html)
    assert html.count('class="gg-yt"') == m.SOURCE.body.count('class="gg-yt"') - len(m.DEAD_YOUTUBE)


def test_the_live_video_stays_and_no_dead_one_renders_anywhere():
    dead = {v for pid in DEAD for v in _module(pid).DEAD_YOUTUBE}
    assert len(dead) == 8 and LIVE_VIDEO not in dead
    pages = {pid: _page(pid) for pid in MODULES}
    assert sum(LIVE_VIDEO in p for p in pages.values()) == 1
    for pid, p in pages.items():
        assert not any(v in p for v in dead), pid
        if 'class="gg-yt"' not in p:
            assert "youtube-nocookie" not in p  # no orphaned click-to-load JS


def test_apply_corrections_rejects_missing_duplicate_and_unexplained():
    body = "<p>20 laps of a 5-mile circuit. 5 laps.</p>"
    fix = wp_post.Correction("5-mile", "3-mile", "the screenshot shows 60 mi over 20 laps")
    assert wp_post.apply_corrections(body, [fix]) == "<p>20 laps of a 3-mile circuit. 5 laps.</p>"
    with pytest.raises(ValueError, match="found 0 times"):
        wp_post.apply_corrections(body, [wp_post.Correction("7-mile", "3-mile", "x y z w")])
    with pytest.raises(ValueError, match="found 2 times"):
        wp_post.apply_corrections(body, [wp_post.Correction("5", "6", "x y z w")])
    with pytest.raises(ValueError, match="reason"):
        wp_post.apply_corrections(body, [wp_post.Correction("5-mile", "3-mile", " ")])
    with pytest.raises(ValueError, match="snapshot"):
        wp_post.corrected_baseline("20 laps of a\n5-mile circuit", [wp_post.Correction("6-mile", "3-mile", "x")])
    assert wp_post.corrected_baseline("20 laps of a\n5-mile circuit", [fix]) == "20 laps of a 3-mile circuit"


def test_drop_youtube_needs_exactly_one_embed():
    one = imp.render_youtube("abcdefghijk", 0)
    assert wp_post.drop_youtube(f"<p>a</p>\n{one}\n<p>b</p>", {"abcdefghijk": "between a and b"}) == "<p>a</p>\n<p>b</p>"
    with pytest.raises(ValueError, match="found 0 times"):
        wp_post.drop_youtube("<p>a</p>", {"abcdefghijk": "nowhere"})
