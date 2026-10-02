"""Topo OG share cards (scripts/og_topo.py and its four generators).

Guards the Feb-2026 failure — cards drawn once with hardcoded numbers and
never regenerated, so shared links showed the old logo/palette, "328 races /
14 dimensions", and race scores that no longer matched their pages (Unbound
200: card 80, page 96) — plus the Oct-2026 Topo rules: every card's numbers
come from the page's own source, the race card stays in the critic's
register, and a page never ships ahead of its card.
"""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "wordpress"))

import og_topo  # noqa: E402
import generate_og_images as race_og  # noqa: E402
import generate_page_og as page_og  # noqa: E402
import generate_homepage_og as home_og  # noqa: E402
import generate_course_og as course_og  # noqa: E402
from generate_neo_brutalist import build_hero, load_race_data  # noqa: E402
from generate_season_review import (  # noqa: E402
    VARIANTS, generate_season_review_page, og_image_name,
)

UNBOUND = ROOT / "race-data" / "unbound-200.json"


def _text(card_html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", card_html))


def _lit(card_html: str):
    """Label of the strip pillar rendered as a solid chip, if any."""
    m = re.search(r'<span style="background:[^"]+">([A-Z ]+)</span>', card_html)
    return m.group(1) if m else None


# ── Race cards: same values as the page hero ────────────────────

def test_race_card_matches_page_hero():
    rd = load_race_data(UNBOUND)
    rd.setdefault("slug", "unbound-200")
    card = race_og.race_card_html(rd)
    hero = build_hero(rd)
    assert f'data-target="{rd["overall_score"]}"' in hero
    text = _text(card)
    assert f"LAB SCORE {rd['overall_score']}" in text
    assert rd["name"] in text and rd["tier_label"] in text
    verdict = race_og.verdict_of(rd)
    assert verdict and verdict in hero and og_topo.e(verdict) in card


def test_race_card_lights_ratings_and_never_pitches():
    rd = load_race_data(UNBOUND)
    rd.setdefault("slug", "unbound-200")
    card = race_og.race_card_html(rd)
    assert _lit(card) == "RACE RATINGS"
    assert "AVAILABLE" not in card.upper()


def test_topo_contours_are_deterministic_per_key():
    assert og_topo.topo_svg("unbound-200", "#fff", .1) == og_topo.topo_svg("unbound-200", "#fff", .1)
    assert og_topo.topo_svg("unbound-200", "#fff", .1) != og_topo.topo_svg("mid-south", "#fff", .1)


# ── Homepage / fallback ladder ──────────────────────────────────

def test_homepage_ladder_reads_live_sources():
    from generate_homepage import compute_stats, load_race_index
    from pricing import PRICE_PER_WEEK
    rows = home_og.ladder_rows(compute_stats(load_race_index()))
    assert [r[1] for r in rows] == ["Pick a race.", "Get a plan.", "Get coached."]
    assert rows[0][2] == f"{compute_stats(load_race_index())['race_count']} RATED"
    assert rows[1][2] == f"{PRICE_PER_WEEK} A WEEK"
    card = og_topo.ladder_card(key="homepage", rows=rows)
    assert _lit(card) is None  # all three pillars equal on the fallback card


def test_no_hardcoded_counts_or_prices_in_generators():
    for name in ("generate_homepage_og.py", "generate_page_og.py"):
        src = (ROOT / "scripts" / name).read_text()
        code = src.split('"""', 2)[2]  # everything after the module docstring
        assert not re.search(r'"\$\d|\b384\b|\b328\b', code), name


# ── Plans / coaching / season review page cards ────────────────

def test_plans_card_prices_from_pricing():
    from pricing import PRICE_CAP, PRICE_PER_WEEK
    card = page_og.training_plans_card_html()
    text = _text(card)
    assert f"PER WEEK {PRICE_PER_WEEK}" in text and f"CAPPED AT {PRICE_CAP}" in text
    assert _lit(card) == "TRAINING PLANS"


def test_coaching_card_price_from_tiers():
    from generate_coaching import TIERS
    card = page_og.coaching_card_html()
    assert f"{TIERS[0][2]}" in _text(card) and "PER 4 WEEKS" in card
    assert _lit(card) == "COACHING"


@pytest.mark.parametrize("intro,expected", [
    ("About twenty-five minutes. Same deal as always", 25),
    ("About 15 minutes, with optional sections", 15),
    ("Fifteen minutes. Don&#39;t write what you&#39;d post.", 15),
    ("Five minutes, less if you&#39;re quick.", 5),
    ("No time given here.", None),
])
def test_minutes_from_intro(intro, expected):
    assert page_og.minutes_from_intro(intro) == expected


@pytest.mark.parametrize("slug", sorted(VARIANTS))
def test_season_review_card_and_page(slug):
    card = page_og.season_review_card_html(slug)
    assert _lit(card) == "COACHING"
    mins = page_og.minutes_from_intro(VARIANTS[slug].get("intro", ""))
    if mins:
        assert f"MINUTES {mins}" in _text(card)
    html = generate_season_review_page(slug)
    assert f'og:image" content="https://gravelgodcycling.com/og/{og_image_name(slug)}"' in html
    assert "og/homepage.jpg" not in html


@pytest.mark.parametrize("generator,card", [
    ("generate_coaching.py", "page-coaching.jpg"),
    ("generate_coaching_apply.py", "page-coaching.jpg"),
    ("generate_training_plans.py", "page-training-plans.jpg"),
])
def test_pillar_pages_point_at_their_card(generator, card):
    src = (ROOT / "wordpress" / generator).read_text()
    assert f"/og/{card}" in src and "/og/homepage.jpg" not in src


def test_course_bundle_card_makes_no_savings_claim():
    src = (ROOT / "scripts" / "generate_course_og.py").read_text()
    assert not re.search(r'kicker="[^"]*SAVE', src, re.I)
    assert _lit(course_og.course_card_html("Dirt Craft", 21, 49)) is None


# ── Deploy: a Season Review page never ships ahead of its card ──

def _sync_env(monkeypatch, tmp_path, *, card=True, fail_card=False):
    import subprocess
    import push_wordpress as pw
    out = tmp_path / "wordpress" / "output"
    (out / "og").mkdir(parents=True)
    (out / "season-review-athlete.html").write_text("<html></html>")
    if card:
        (out / "og" / og_image_name("athlete")).write_bytes(b"jpg")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pw, "get_ssh_credentials", lambda: ("host", "user", "1"))
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if fail_card and cmd[0] == "scp" and "/og/" in cmd[-1]:
            raise subprocess.CalledProcessError(1, cmd, stderr="denied")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(pw.subprocess, "run", fake_run)
    return pw, calls


def _page_uploaded(calls):
    return any(c[0] == "scp" and c[-1].endswith("index.html") for c in calls)


def test_season_review_sync_uploads_card_before_page(monkeypatch, tmp_path):
    pw, calls = _sync_env(monkeypatch, tmp_path)
    assert pw.sync_season_review("athlete")
    scps = [c[-1] for c in calls if c[0] == "scp"]
    assert scps[0].endswith(f"/og/{og_image_name('athlete')}")
    assert scps[1].endswith("/coaching/season-review/athlete/index.html")


def test_season_review_sync_skips_page_without_card(monkeypatch, tmp_path):
    pw, calls = _sync_env(monkeypatch, tmp_path, card=False)
    assert pw.sync_season_review("athlete") is None
    assert not _page_uploaded(calls)


def test_season_review_sync_skips_page_when_card_upload_fails(monkeypatch, tmp_path):
    pw, calls = _sync_env(monkeypatch, tmp_path, fail_card=True)
    assert pw.sync_season_review("athlete") is None
    assert not _page_uploaded(calls)


# ── Rendering (needs Playwright + Chromium; CI installs both) ───

@pytest.fixture(scope="module")
def renderer():
    pytest.importorskip("playwright")
    try:
        with og_topo.Renderer() as r:
            yield r
    except Exception as exc:  # browser not installed locally
        pytest.skip(f"Chromium unavailable: {exc}")


def _field_at(path, xy=(6, 300)):
    from PIL import Image
    return Image.open(path).convert("RGB").getpixel(xy)


def _hex(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


@pytest.mark.parametrize("kind", ["race", "home", "plans", "coaching", "season"])
def test_cards_render_on_their_pillar_field(kind, renderer, tmp_path):
    rd = load_race_data(UNBOUND)
    rd.setdefault("slug", "unbound-200")
    cards = {
        "race": (race_og.race_card_html(rd), "races"),
        "home": (og_topo.ladder_card(key="homepage", rows=home_og.ladder_rows(
            {"race_count": 384})), "races"),
        "plans": (page_og.training_plans_card_html(), "plans"),
        "coaching": (page_og.coaching_card_html(), "coaching"),
        "season": (page_og.season_review_card_html("athlete"), "coaching"),
    }
    card_html, pillar = cards[kind]
    path = renderer.render(card_html, tmp_path / f"{kind}.jpg")
    from PIL import Image
    assert Image.open(path).size == (1200, 630)
    got, want = _field_at(path), _hex(og_topo.FIELDS[pillar][0])
    assert all(abs(a - b) <= 10 for a, b in zip(got, want)), (got, want)


def test_overflowing_text_raises_instead_of_shipping(renderer, tmp_path):
    card = og_topo.pillar_card(pillar="races", key="x", kicker="K",
                               title_html="word " * 80, size=84)
    with pytest.raises(og_topo.OGCardError):
        renderer.render(card, tmp_path / "x.jpg")
