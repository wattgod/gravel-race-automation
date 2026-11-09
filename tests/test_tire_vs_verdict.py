"""Tire VS pages: both tires' BRR lab tests head to head, ranked the way the
tire pages rank them. No made-up score (durability, versatility, composite)
and no hand-written claim (tagline, strengths, weaknesses) reaches the page;
our calls are labelled "(our call)"."""

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

import generate_tire_pages as gtp  # noqa: E402
import generate_tire_vs_pages as gvs  # noqa: E402


def _test(width, rr, punct, wet, weight, knobs=(1.0, 2.0)):
    return {"width_mm": width, "measured_width_mm": width - 1, "year": 2024,
            "rr_watts": rr, "puncture_tread": punct, "wet_grip": wet, "weight_g": weight,
            "knob_center_mm": knobs[0], "knob_edge_mm": knobs[1],
            "url": f"https://brr.example/{width}"}


def _tire(tid, *tests, **extra):
    return {"id": tid, "name": tid.upper(), "brand": "Brand", "widths_mm": [40, 50],
            "tread_type": "file", "mud_clearance": "low", "msrp_usd": 70.0,
            "tubeless_ready": True, "lab_tested": True, "brr_tests": list(tests), **extra}


@pytest.fixture
def pool(monkeypatch):
    # Four tires at 40mm, three at 50mm (a, b, e), one at 45mm (f).
    tires = [
        _tire("a", _test(40, 15.0, 50, 60, 400), _test(50, 14.0, 52, 61, 500)),
        _tire("b", _test(40, 16.0, 55, 75, 380), _test(50, 15.0, 56, 76, 480),
              mud_clearance="moderate", tread_type="knobby", msrp_usd=80.0),
        _tire("c", _test(40, 17.0, 40, 70, 440)),
        _tire("d", _test(40, 18.0, 35, 65, 460)),
        _tire("e", _test(50, 19.0, 30, 60, 470)),
        _tire("f", _test(45, 20.0, 25, 55, 500)),
    ]
    monkeypatch.setattr(gtp, "_lab_pool", {t["id"]: gtp.tests_by_class(t) for t in tires})
    return {t["id"]: t for t in tires}


# ── Head to head ──────────────────────────────────────────────


def test_pair_is_ranked_in_the_biggest_class_both_were_tested_in(pool):
    h2h = gvs.head_to_head(pool["a"], pool["b"])
    assert h2h["width"] == 40  # four tires at 40mm beat three at 50mm
    assert h2h["pool"] == 4
    assert [t["url"] for t in h2h["tests"]] == ["https://brr.example/40"] * 2

    h2h = gvs.head_to_head(pool["a"], pool["e"])
    assert h2h["width"] == 50  # the only class they share
    assert h2h["pool"] == 3


def test_tire_ranks_takes_the_shared_class(pool):
    assert gtp.tire_ranks(pool["a"])["width_class"] == 40
    ranks = gtp.tire_ranks(pool["a"], 50)
    assert ranks["width_class"] == 50
    assert [(r["label"], r["rank"], r["of"]) for r in ranks["rows"]] == [
        ("Rolling resistance", 1, 3), ("Puncture (tread)", 2, 3),
        ("Wet grip", 2, 3), ("Weight", 3, 3)]
    assert gtp.tire_ranks(pool["c"], 50) is None


def test_no_shared_width_no_head_to_head(pool):
    assert gvs.head_to_head(pool["c"], pool["f"]) is None
    untested = {**pool["c"], "id": "u", "lab_tested": False}
    assert gvs.head_to_head(pool["a"], untested) is None


def test_each_measure_has_a_leader_or_a_tie(pool):
    h2h = gvs.head_to_head(pool["a"], pool["b"])
    assert {r["key"]: r["leader"] for r in h2h["rows"]} == {
        "rr_watts": 0, "puncture_tread": 1, "wet_grip": 1, "weight_g": 1}
    ranks = {r["key"]: [c["rank"] for c in r["cells"]] for r in h2h["rows"]}
    assert ranks["rr_watts"] == [1, 2]
    assert ranks["weight_g"] == [2, 1]  # lighter ranks higher


def test_verdict_names_who_leads_on_what(pool):
    h2h = gvs.head_to_head(pool["a"], pool["b"])
    assert gvs.verdict_sentence(pool["a"], pool["b"], h2h) == (
        "In BRR's 40mm tests, A rolls faster; B resists punctures better, "
        "grips better in the wet and weighs less.")


def test_equal_numbers_are_nobodys_lead(pool, monkeypatch):
    twin = _tire("twin", _test(40, 15.0, 50, 60, 400))
    monkeypatch.setitem(gtp._lab_pool, "twin", gtp.tests_by_class(twin))
    h2h = gvs.head_to_head(pool["a"], twin)
    assert all(r["leader"] is None for r in h2h["rows"])
    assert gvs.verdict_sentence(pool["a"], twin, h2h) == (
        "In BRR's 40mm tests, the two measure the same on every lab measure.")
    assert "Neither: both measured 15 W in BRR's 40mm rolling resistance test." in [
        a for _, a in gvs.faq_pairs(pool["a"], twin, h2h)]


def test_faq_answers_read_off_the_numbers(pool):
    h2h = gvs.head_to_head(pool["a"], pool["b"])
    answers = dict(gvs.faq_pairs(pool["a"], pool["b"], h2h))
    assert answers["Is A or B faster?"] == (
        "A rolls faster: 15 W against 16 W for B in BRR's 40mm rolling resistance test.")
    assert answers["Which is lighter, A or B?"] == (
        "B weighs less: 380 g against 400 g for A as weighed by BRR at 40mm.")
    assert answers["Which costs less, A or B?"] == (
        "A costs less: $70.00 MSRP against $80.00 for B.")
    assert answers["Which is better in mud, A or B?"].startswith(
        "Mud clearance is our call; BRR doesn't test it. We rate it Low for A and Moderate for B.")


def test_our_calls_are_labelled(pool):
    html = gvs.build_specs_comparison(pool["a"], pool["b"])
    assert "<td>Mud clearance (our call)</td><td>Low</td><td>Moderate</td>" in html
    assert "<td>Tread type (our call)</td><td>File</td><td>Knobby</td>" in html
    # Puncture and wet are measured, so they live in the rank table, not here.
    assert "Puncture" not in html and "Wet" not in html


def test_ranks_section_cites_both_tests(pool):
    h2h = gvs.head_to_head(pool["a"], pool["b"])
    html = gvs.build_ranks_section(pool["a"], pool["b"], h2h, "verdict")
    assert html.count('href="https://brr.example/40"') == 2
    assert "Ranked among the 4 tires in our database BRR tested at 35–42mm." in html
    assert ('<td class="tvs-winner-cell">15 W<span class="tvs-rank">1st of 4</span></td>'
            '<td>16 W<span class="tvs-rank">2nd of 4</span></td>') in html


HAND_WRITTEN = {
    "tagline": "The fastest tire ever made.",
    "strengths": ["Unbeatable grip"],
    "weaknesses": ["Wears out in a week"],
    "recommended_use": ["racing", "training", "touring", "commuting", "bikepacking", "cx"],
    "avoid_use": ["mud"],
    "best_conditions": ["dry"],
    "worst_conditions": ["wet"],
    "tread_description": "Made-up tread copy",
}


def test_hand_written_fields_do_not_change_the_page(pool):
    plain = gvs.generate_vs_page(pool["a"], pool["b"], {})
    a, b = copy.deepcopy(pool["a"]), copy.deepcopy(pool["b"])
    a.update(HAND_WRITTEN)
    b.update({**HAND_WRITTEN, "tread_type": b["tread_type"]})
    assert gvs.generate_vs_page(a, b, {}) == plain


# ── The real pages ────────────────────────────────────────────


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("tire-vs")
    argv = sys.argv
    sys.argv = ["generate_tire_vs_pages.py", "--output-dir", str(out)]
    try:
        gvs.main()
    finally:
        sys.argv = argv
    tires = gvs.load_tire_database()
    db = {t["id"]: t for t in tires}
    pairs = gvs.select_tire_pairs(tires)
    return out, db, pairs


def _page(out, a, b):
    return (out / f"{a}-vs-{b}" / "index.html").read_text()


def test_every_published_pair_compares_one_tested_width(built):
    out, db, pairs = built
    assert pairs
    for a, b in pairs:
        h2h = gvs.head_to_head(db[a], db[b])
        assert h2h, (a, b)
        assert h2h["tests"][0]["width_mm"] == h2h["tests"][1]["width_mm"] == h2h["width"]
    assert sorted(p.name for p in out.iterdir()) == sorted(f"{a}-vs-{b}" for a, b in pairs)


def test_no_hand_written_claims_reach_the_page(built):
    out, db, pairs = built
    for a, b in pairs:
        html = _page(out, a, b)
        for tire in (db[a], db[b]):
            claims = [tire.get("tagline")] + tire.get("strengths", []) + tire.get("weaknesses", [])
            for claim in filter(None, claims):
                assert gvs.esc(claim) not in html, (a, b, claim)


def test_made_up_scores_are_gone(built):
    out, db, pairs = built
    for a, b in pairs:
        html = _page(out, a, b)
        for gone in ("composite rating", "tvs-radar", ">DUR<", ">VERS<", "Choose ",
                     "Durability", "Versatility", "Which gravel tire is right for your next race?"):
            assert gone not in html, (a, b, gone)


def test_meta_description_is_the_verdict(built):
    out, db, pairs = built
    for a, b in pairs:
        html = _page(out, a, b)
        meta = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
        h2h = gvs.head_to_head(db[a], db[b])
        verdict = gvs.verdict_sentence(db[a], db[b], h2h)
        assert meta == gvs.esc(verdict), (a, b)
        assert f'<p class="tvs-verdict">{gvs.esc(verdict)}</p>' in html


def test_lab_numbers_and_links_come_from_the_brr_tests(built):
    out, db, pairs = built
    for a, b in pairs:
        html = _page(out, a, b)
        h2h = gvs.head_to_head(db[a], db[b])
        for test in h2h["tests"]:
            assert f'href="{gvs.esc(test["url"])}"' in html, (a, b)
            for key, _, _, unit, _ in gtp.RANK_MEASURES:
                if test.get(key) is not None:
                    assert f">{gtp._num(test[key], unit)}<span" in html, (a, b, key)


def test_our_calls_are_labelled_on_every_page(built):
    out, db, pairs = built
    for a, b in pairs:
        html = _page(out, a, b)
        assert "<td>Mud clearance (our call)</td>" in html, (a, b)
        assert "<td>Tread type (our call)</td>" in html, (a, b)


def test_sections_are_numbered_in_order(built):
    out, db, pairs = built
    for a, b in pairs:
        nums = re.findall(r'class="tvs-section-num">(\d{2}) /', _page(out, a, b))
        assert nums == [f"{i:02d}" for i in range(1, len(nums) + 1)], (a, b)


def test_faq_json_ld_matches_the_faq(built):
    out, db, pairs = built
    a, b = pairs[0]
    html = _page(out, a, b)
    ld = [json.loads(m) for m in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]
    faq = next(x for x in ld if x["@type"] == "FAQPage")
    h2h = gvs.head_to_head(db[a], db[b])
    assert [(q["name"], q["acceptedAnswer"]["text"]) for q in faq["mainEntity"]] == (
        gvs.faq_pairs(db[a], db[b], h2h))
