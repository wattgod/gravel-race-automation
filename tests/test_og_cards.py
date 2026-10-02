"""OG share cards (scripts/og_brand.py and its three generators).

Guards the Feb-2026 failure: cards drawn once on the pre-rebrand dark theme
with hardcoded numbers, then never regenerated — so every shared link showed
the old logo/palette, "328 races / 14 dimensions", and race scores that no
longer matched their pages (Unbound 200: card 80, page 96).
"""

import re
import sys
from pathlib import Path

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "wordpress"))

import og_brand as og  # noqa: E402
import generate_og_images as race_og  # noqa: E402
import generate_page_og as page_og  # noqa: E402
import generate_homepage_og as home_og  # noqa: E402
import generate_course_og as course_og  # noqa: E402
from generate_neo_brutalist import build_hero, load_race_data  # noqa: E402
from generate_season_review import (  # noqa: E402
    VARIANTS, generate_season_review_page, og_image_name,
)

EDGE_SLUGS = [
    "unbound-200",                        # series + verdict
    "race-across-germany",                # long name, long location, long verdict
    "uec-gravel-european-championships",  # longest name
    "leadville-100",                      # non-gravel discipline + series
    "belgian-waffle-ride-kansas",         # taking_a_break
    "gran-fondo-argentina",               # no verdict
]


def _is_paper(img: Image.Image, xy) -> bool:
    px = img.convert("RGB").getpixel(xy)
    return all(abs(a - b) <= 6 for a, b in zip(px, og.WARM_PAPER))


def _assert_brand_frame(path: Path):
    img = Image.open(path)
    assert img.size == (1200, 630)
    # Paper ground (not the old near-black), gold top line + header rule.
    assert _is_paper(img, (600, 600)) and _is_paper(img, (10, 300))
    gold = og.GOLD
    for xy in ((600, 2), (600, og.HEADER_RULE_Y + 1)):
        px = img.convert("RGB").getpixel(xy)
        assert all(abs(a - b) <= 24 for a, b in zip(px, gold)), (xy, px)  # JPEG
    # The 2026 mark sits top-left: dark ink inside the logo box.
    crop = img.convert("L").crop((og.MARGIN, 20, og.MARGIN + 60, 120))
    assert min(crop.getdata()) < 80


# ── Brand ───────────────────────────────────────────────────────

def test_brand_tokens_match_site_tokens():
    from brand_tokens import get_tokens_css
    css = get_tokens_css()
    for name, rgb in (("warm-paper", og.WARM_PAPER), ("dark-brown", og.DARK_BROWN),
                      ("gold", og.GOLD), ("teal", og.TEAL),
                      ("secondary-brown", og.SEC_BROWN)):
        m = re.search(rf"--gg-color-{name}:\s*#([0-9a-fA-F]{{6}})", css)
        assert m, name
        assert tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4)) == rgb, name


def test_logo_is_2026_mark_asset():
    assert og.LOGO_PNG.exists()
    assert og.logo(68).height == 68


# ── Race cards ──────────────────────────────────────────────────

@pytest.mark.parametrize("slug", EDGE_SLUGS)
def test_race_card_renders_on_brand(slug, tmp_path):
    rd = load_race_data(ROOT / "race-data" / f"{slug}.json")
    rd.setdefault("slug", slug)
    _assert_brand_frame(race_og.generate_og_image(rd, tmp_path / f"{slug}.jpg"))


def test_race_card_score_and_verdict_come_from_page_normalizer():
    rd = load_race_data(ROOT / "race-data" / "unbound-200.json")
    hero = build_hero(rd)
    # The card reads rd["overall_score"] and verdict_of(rd); both must be
    # exactly what the page hero prints.
    assert f'data-target="{rd["overall_score"]}"' in hero
    verdict = race_og.verdict_of(rd)
    assert verdict and verdict in hero


@pytest.mark.parametrize("raw,expected", [
    ("2027: June 5; final 2027 route and elevation are pending", "June 5, 2027"),
    ("2026: Sept. 12", "Sept. 12, 2026"),
    ("May 1, 2026", "May 1, 2026"),
    ("2027: Friday, June 4; final 2027 route and elevation are pending", "June 4, 2027"),
    ("2027: Friday, June 11 at 8:00 AM Mountain Time", "June 11, 2027"),
    ("2026: Sunday, June 7th", "June 7, 2026"),
    ("2027: March 13-20", "March 13-20, 2027"),
    ("2026: June 19-20 (Friday check-in/expo, Saturday race day)", "June 19-20, 2026"),
    ("2026: Aug 19-23 (festival week)", "Aug 19-23, 2026"),
    ("2027: TBD", ""),
    ("2026: May 2026", ""),
    ("2026: Early September (weather dependent)", ""),
    ("2026: Spring/Fall TBD", ""),
    ("Status: DROPPED — no 2026 or 2027 edition; last held October 11, 2025", ""),
    ("", ""),
])
def test_short_date(raw, expected):
    assert race_og.short_date(raw) == expected


# ── Homepage / fallback card ────────────────────────────────────

def test_homepage_card_renders_on_brand(tmp_path):
    _assert_brand_frame(home_og.generate(tmp_path))


def test_homepage_og_has_no_hardcoded_counts():
    src = (ROOT / "scripts" / "generate_homepage_og.py").read_text()
    assert not re.search(r'"\d{3}"', src), "race counts must come from compute_stats()"
    assert "compute_stats" in src


# ── Page cards (Season Review) ──────────────────────────────────

def test_every_season_review_variant_has_its_own_card(tmp_path):
    paths = page_og.season_review_cards(tmp_path)
    assert sorted(p.name for p in paths) == sorted(og_image_name(s) for s in VARIANTS)
    for p in paths:
        _assert_brand_frame(p)


@pytest.mark.parametrize("slug", sorted(VARIANTS))
def test_season_review_page_points_at_its_card(slug):
    html = generate_season_review_page(slug)
    assert f'og:image" content="https://gravelgodcycling.com/og/{og_image_name(slug)}"' in html
    assert "og/homepage.jpg" not in html


# ── Course cards ────────────────────────────────────────────────

def test_course_card_renders_on_brand(tmp_path):
    path = course_og.generate_course_og("Dirt Craft: Technical Gravel Mastery",
                                        "Stop fighting the bike. Start riding it.",
                                        21, 49, tmp_path / "c.png")
    _assert_brand_frame(path)


def test_course_bundle_card_makes_no_hardcoded_savings_claim():
    src = (ROOT / "scripts" / "generate_course_og.py").read_text()
    assert not re.search(r'kicker="[^"]*SAVE', src, re.I)


# ── Overflow is loud, not silent ────────────────────────────────

def test_headline_that_cannot_fit_raises(tmp_path):
    with pytest.raises(og.OGCardError):
        page_og.render_page_card("KICKER", "word " * 60, tmp_path / "x.jpg")


# ── Deploy: a Season Review page never ships ahead of its card ──

def _fake_sync_env(monkeypatch, tmp_path, fail_card=False):
    import subprocess
    import push_wordpress as pw
    out = tmp_path / "wordpress" / "output"
    out.mkdir(parents=True)
    (out / "season-review-athlete.html").write_text("<html></html>")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pw, "get_ssh_credentials", lambda: ("host", "user", "1"))
    real_card = page_og.season_review_card
    monkeypatch.setattr(page_og, "season_review_card", lambda slug: real_card(slug, tmp_path))
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if fail_card and cmd[0] == "scp" and "/og/" in cmd[-1]:
            raise subprocess.CalledProcessError(1, cmd, stderr="denied")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(pw.subprocess, "run", fake_run)
    return pw, calls


def test_season_review_sync_uploads_card_before_page(monkeypatch, tmp_path):
    pw, calls = _fake_sync_env(monkeypatch, tmp_path)
    assert pw.sync_season_review("athlete")
    scps = [c[-1] for c in calls if c[0] == "scp"]
    assert scps[0].endswith(f"/og/{og_image_name('athlete')}")
    assert scps[1].endswith("/coaching/season-review/athlete/index.html")


def test_season_review_sync_skips_page_when_card_upload_fails(monkeypatch, tmp_path):
    pw, calls = _fake_sync_env(monkeypatch, tmp_path, fail_card=True)
    assert pw.sync_season_review("athlete") is None
    assert not any(c[0] == "scp" and c[-1].endswith("index.html") for c in calls)
