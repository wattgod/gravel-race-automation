"""Tire pages: the verdict is computed from BRR lab tests and our race picks.
No hand-written claim (tagline, strengths, weaknesses) reaches the page."""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

import generate_tire_pages as gtp  # noqa: E402


def _test(width, rr, punct, wet, weight):
    return {"width_mm": width, "rr_watts": rr, "puncture_tread": punct,
            "wet_grip": wet, "weight_g": weight, "url": f"https://brr.example/{width}"}


def _tire(tid, *tests, name=None):
    return {"id": tid, "name": name or tid, "lab_tested": True, "brr_tests": list(tests)}


@pytest.fixture
def pool(monkeypatch):
    # Six tires at 40mm; three of them also at 50mm.
    tires = [
        _tire("a", _test(40, 15.0, 50, 80, 400), _test(50, 14.0, 52, 81, 500)),
        _tire("b", _test(40, 16.0, 45, 75, 420), _test(50, 15.0, 46, 76, 520)),
        _tire("c", _test(40, 17.0, 40, 70, 440), _test(50, 16.0, 41, 71, 540)),
        _tire("d", _test(40, 18.0, 35, 65, 460)),
        _tire("e", _test(40, 19.0, 30, 60, 480)),
        _tire("f", _test(40, 20.0, 25, 55, 500)),
    ]
    monkeypatch.setattr(gtp, "_lab_pool", {t["id"]: gtp.tests_by_class(t) for t in tires})
    return {t["id"]: t for t in tires}


def test_ranks_use_the_biggest_width_class(pool):
    ranks = gtp.tire_ranks(pool["a"])
    assert ranks["width_class"] == 40  # six tires at 40mm beat three at 50mm
    assert [(r["label"], r["rank"], r["of"]) for r in ranks["rows"]] == [
        ("Rolling resistance", 1, 6), ("Puncture (tread)", 1, 6),
        ("Wet grip", 1, 6), ("Weight", 1, 6)]


def test_lower_watts_and_grams_rank_higher(pool):
    ranks = gtp.tire_ranks(pool["f"])
    assert {r["label"]: r["rank"] for r in ranks["rows"]} == {
        "Rolling resistance": 6, "Puncture (tread)": 6, "Wet grip": 6, "Weight": 6}


def test_sentence_follows_the_thirds(pool):
    assert gtp.rank_sentence(gtp.tire_ranks(pool["a"])) == (
        "top third for rolling resistance, puncture resistance, wet grip and weight")
    assert gtp.rank_sentence(gtp.tire_ranks(pool["c"])) == "middle third on every lab measure"
    assert gtp.rank_sentence(gtp.tire_ranks(pool["f"])).startswith("bottom third for")


def test_untested_tire_has_no_ranks():
    assert gtp.tire_ranks({"id": "x", "name": "X", "lab_tested": False}) is None
    assert "No lab test yet." in gtp.build_ranks_section(None)


def test_ranks_section_cites_the_test(pool):
    html = gtp.build_ranks_section(gtp.tire_ranks(pool["b"]))
    assert 'href="https://brr.example/40"' in html
    assert "ranked among the 6 tires in our database BRR tested at 35–42mm" in html
    assert "2nd of 6" in html


# ── The real pages ────────────────────────────────────────────


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("tires")
    argv = sys.argv
    sys.argv = ["generate_tire_pages.py", "--output-dir", str(out)]
    try:
        gtp.main()
    finally:
        sys.argv = argv
    tires = [json.loads(f.read_text()) for f in (ROOT / "data" / "tires").glob("*.json")]
    return out, {gtp.tire_slug(t): t for t in tires}


def _page(built, slug):
    return (built[0] / slug / "index.html").read_text()


def test_no_hand_written_claims_reach_the_page(built):
    out, db = built
    for slug, tire in db.items():
        html = _page(built, slug)
        claims = [tire.get("tagline")] + tire.get("strengths", []) + tire.get("weaknesses", [])
        for claim in filter(None, claims):
            assert gtp.esc(claim) not in html, (slug, claim)
        assert "When to Use This Tire" not in html


def test_meta_description_is_the_verdict(built):
    out, db = built
    for slug, tire in db.items():
        html = _page(built, slug)
        meta = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
        ranks = gtp.tire_ranks(tire)
        if ranks:
            assert gtp.esc(gtp.rank_sentence(ranks)) in meta, slug
        else:
            assert "No lab test yet." in meta, slug


def test_sections_are_numbered_in_order(built):
    out, db = built
    for slug in db:
        nums = re.findall(r'class="tp-section-num">(\d{2}) /', _page(built, slug))
        assert nums == [f"{i:02d}" for i in range(1, len(nums) + 1)], slug


def test_who_raced_it_lists_sourced_podium_rows():
    from generate_tire_guide import load_podiums
    podiums = load_podiums()
    pathfinder = {"id": "specialized-pathfinder", "name": "Specialized Pathfinder"}
    html = gtp.build_who_raced_section(pathfinder)
    entries = [(slug, e) for slug, p in podiums.items() for e in p["entries"]
               if e["tire"] == pathfinder["name"]]
    assert entries
    assert html.count("<tr><td>") == len(entries)
    for slug, e in entries:
        assert f'href="{gtp.esc(e["source_url"])}"' in html
        assert f'href="/race/{slug}/tires/"' in html
    assert gtp.build_who_raced_section({"id": "x", "name": "Specialized Pathfinder Pro"}) == ""


def test_brand_sources_are_labelled():
    html = gtp.build_who_raced_section({"id": "schwalbe-g-one-rx-pro", "name": "Schwalbe G-One RX Pro"})
    assert "(brand)" in html


def _rec(slug, rank, position="primary"):
    return {"slug": slug, "name": slug.title(), "rank": rank, "width": 45,
            "why": "", "position": position}


def test_where_we_pick_counts_the_picks(monkeypatch):
    monkeypatch.setattr(gtp, "_race_meta", {
        "a": {"name": "A", "tier": 1, "profile": "mixed"},
        "b": {"name": "B", "tier": 2, "profile": "technical"},
        "c": {"name": "C", "tier": 3, "profile": "mixed"}})
    html = gtp.build_where_we_pick_section([_rec("a", 1), _rec("b", 2), _rec("c", 1, "rear")])
    assert "#1 pick at 1 of 3 races; top 3 at 2. Front/rear split at 1." in html
    assert "<td>Mixed surface</td><td>1 of 2</td>" in html
    assert "<td>Technical</td><td>1 of 1</td>" in html
    assert "tp-race-more" not in html  # short lists stay open


def test_long_race_lists_collapse_to_tier_1(monkeypatch):
    meta = {f"r{i}": {"name": f"R{i}", "tier": 1 if i < 2 else 3, "profile": "mixed"}
            for i in range(20)}
    monkeypatch.setattr(gtp, "_race_meta", meta)
    html = gtp.build_where_we_pick_section([_rec(slug, 2) for slug in meta])
    assert "Top 3 at 20 of 20 races, never #1." in html
    open_list = html.split("Tier 1 races")[1].split("tp-race-more")[0]
    assert open_list.count("tp-race-item") == 2
    assert "<summary>All 20 races</summary>" in html
