"""Course Dossier race page (mock 6, issue #675): plan-week math, the race
date the plan counts to, and the new first screen and section cards."""

import copy
import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

import course_dossier as cd  # noqa: E402
import generate_neo_brutalist as gnb  # noqa: E402

ON = date(2026, 11, 17)


# ── Plan-week math ─────────────────────────────────────────────

@pytest.mark.parametrize("n, base, build, spec, taper", [
    (0, 0, 0, 0, 0),
    (1, 0, 0, 0, 1),
    (2, 0, 0, 0, 2),
    (3, 0, 0, 1, 2),
    (10, 0, 0, 8, 2),
    (12, 0, 2, 8, 2),
    (18, 0, 8, 8, 2),
    (29, 11, 8, 8, 2),
])
def test_plan_phases(n, base, build, spec, taper):
    assert cd.plan_phases(n) == {"base": base, "build": build, "specific": spec, "taper": taper}


@pytest.mark.parametrize("n", range(1, 61))
def test_plan_phases_cover_every_week(n):
    ph = cd.plan_phases(n)
    assert sum(ph.values()) == n
    assert ph["taper"] == min(2, n)
    assert ph["specific"] == min(8, n - ph["taper"])
    assert ph["build"] == min(8, n - ph["taper"] - ph["specific"])


def test_weeks_to_counts_whole_weeks():
    # Unbound 200, Sat Jun 5, 2027: 200 days from Nov 17, 2026 -> 29 weeks.
    assert cd.weeks_to(date(2027, 6, 5), ON) == 29
    assert cd.weeks_to(date(2026, 11, 24), ON) == 1
    assert cd.weeks_to(date(2026, 11, 25), ON) == 2
    assert cd.weeks_to(ON, ON) == 0
    assert cd.weeks_to(date(2026, 1, 1), ON) == 0


@pytest.mark.parametrize("n", [1, 4, 5, 9, 29, 33])
def test_plan_weeks_blocks_and_dress_rehearsal(n):
    blocks = cd.plan_weeks(n)
    assert [w["week"] for b in blocks for w in b] == list(range(1, n + 1))
    assert all(len(b) == 4 for b in blocks[:-1])
    assert len(blocks[-1]) == (n % 4 or 4)
    dress = [w["week"] for b in blocks for w in b if w["dress"]]
    assert dress == ([n - 3] if n > 4 else [])
    phases = [w["phase"] for b in blocks for w in b]
    assert phases[-min(2, n):] == ["taper"] * min(2, n)
    # Phases run in order: base, build, race-specific, taper.
    order = {"base": 0, "build": 1, "specific": 2, "taper": 3}
    assert [order[p] for p in phases] == sorted(order[p] for p in phases)


def test_page_script_uses_the_same_math():
    js = cd.get_js()
    for formula in ("Math.min(2, n)", "Math.min(8, n - taper)", "Math.min(8, n - taper - spec)",
                    "n > 4 ? n - 3 : 0", "(w - 1) % 4 === 0", "Math.ceil(Math.round((race - today) / 864e5) / 7)"):
        assert formula in js
    assert "innerHTML" not in js


# ── The date the plan counts to ────────────────────────────────

def _rd(date_specific, editions=(), **extra):
    rd = {"vitals": {"date_specific": date_specific, "course_status": ""},
          "editions": list(editions)}
    rd.update(extra)
    return rd


def test_plan_target_confirmed_date():
    t = cd.plan_target(_rd("2027: June 5 (Saturday, CONFIRMED)"), ON)
    assert t == {"date": date(2027, 6, 5), "kind": "confirmed"}
    assert cd.plan_note(t) == "Counted from today to Sat, Jun 5, 2027."


def test_plan_target_unannounced_uses_last_years_slot_and_says_so():
    t = cd.plan_target(_rd("2026: March 28"), ON)
    assert t["kind"] == "last_year"
    assert t["last"] == date(2026, 3, 28)
    assert t["date"] == date(2027, 3, 27)  # 4th Saturday of March, again
    note = cd.plan_note(t)
    assert "isn't announced" in note and "last year's slot" in note and "Mar 28, 2026" in note


def test_plan_target_estimated_date_is_not_treated_as_confirmed():
    rd = _rd("2027: May 29 (estimated)", editions=[{"year": 2026, "date": "2026-05-30"}])
    t = cd.plan_target(rd, ON)
    assert t["kind"] == "last_year" and t["last"] == date(2026, 5, 30)


def test_plan_target_none_without_any_date_or_when_not_running():
    assert cd.plan_target(_rd(""), ON) is None
    assert cd.plan_target(_rd("2026: March 28", taking_a_break={"label": "Taking a break"}), ON) is None


def test_plan_strip_without_a_runway_is_empty():
    assert cd.build_plan_strip({"date": ON, "kind": "confirmed"}, ON) == ""


# ── Stored course data is used only for the listed route ───────

def _unbound():
    path = ROOT / "race-data" / "unbound-200.json"
    return gnb.normalize_race_data(json.loads(path.read_text()))


def test_elevation_and_map_only_for_the_route_the_race_lists():
    rd = _unbound()
    assert cd.load_elevation(rd) and cd.load_geometry(rd)
    other = copy.deepcopy(rd)
    other["course"]["ridewithgps_id"] = "1"
    assert cd.load_elevation(other) is None and cd.load_geometry(other) is None
    none = copy.deepcopy(rd)
    none["course"]["ridewithgps_id"] = None
    assert cd.load_elevation(none) is None and cd.load_geometry(none) is None


def test_elevation_cache_is_real_route_data():
    for path in sorted((ROOT / "data" / "route-elevation").glob("*.json")):
        rec = json.loads(path.read_text())
        assert rec["source_url"].startswith("https://ridewithgps.com/routes/"), path.name
        assert len(rec["distance_km"]) == len(rec["elevation_m"]) >= 2, path.name
        assert rec["distance_km"] == sorted(rec["distance_km"]), path.name
        assert rec["low_m"] <= min(rec["elevation_m"]) and max(rec["elevation_m"]) <= rec["high_m"], path.name


# ── The page ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def race_index():
    return json.loads((ROOT / "web" / "race-index.json").read_text())


def _body(html):
    """The page markup, without the inlined stylesheet and scripts."""
    body = html[html.index("<body>"):html.index('id="gg-back-to-top"')]
    return body


@pytest.fixture(scope="module")
def unbound_html(race_index):
    return _body(gnb.generate_page(_unbound(), race_index))


def test_first_screen_order(unbound_html):
    html = unbound_html
    order = ['class="gg-cd-hero', 'class="gg-cd-fold', 'gg-cd-why', 'gg-cd-coursecard',
             'gg-cd-yours', 'class="gg-cd-route"', 'id="deep-dive"']
    positions = [html.index(m) for m in order]
    assert positions == sorted(positions)
    assert html.count('data-page-format="course-dossier"') == 1


def test_hero_has_elevation_profile_and_score(unbound_html):
    hero = unbound_html[unbound_html.index('class="gg-cd-hero'):unbound_html.index('class="gg-cd-fold')]
    assert 'gg-cd-prof--hero' in hero and "ridewithgps.com/routes/46551378" in hero
    assert ">96</b>" in hero and "RATED BY MATTI ROWE" in hero
    m = re.search(r"#(\d+) OF (\d+)", hero)
    assert m and int(m.group(1)) >= 1 and int(m.group(2)) > 100


def test_route_bar_links_only_sections_on_the_page(unbound_html):
    bar = unbound_html[unbound_html.index('class="gg-cd-route"'):unbound_html.index('id="deep-dive"')]
    stops = re.findall(r'data-cd-stop="([^"]+)"', bar)
    assert stops[:2] == ["ratings", "course"]
    for anchor in stops:
        assert f'id="{anchor}"' in unbound_html
    assert 'href="#plan"' in bar and 'id="plan"' in unbound_html


def test_section_cards_present(unbound_html):
    for anchor in ("ratings", "course", "race-day", "should", "logistics", "history",
                   "from-the-field", "finish-time", "citations"):
        assert f'id="{anchor}"' in unbound_html, anchor


def test_rating_citations_resolve(unbound_html):
    ratings = unbound_html[unbound_html.index('id="ratings"'):unbound_html.index('id="course"')]
    refs = set(re.findall(r'href="#gg-citation-(\d+)"', ratings))
    assert refs
    for n in refs:
        assert f'id="gg-citation-{n}"' in unbound_html


def test_plan_offer_shows_only_the_rate(unbound_html):
    assert cd.PRICE_RATE == "$49.99 / four weeks"
    yours = unbound_html[unbound_html.index('gg-cd-yours'):unbound_html.index('class="gg-cd-route"')]
    assert "$49.99 / four weeks" in yours
    assert "Start my plan" in yours and 'data-cta="approved_custom_plan"' in yours
    assert "data-cd-weeks" in yours and "data-cd-estimator" in yours
    lowered = unbound_html.lower()
    for banned in ("every 4 weeks", "payments", " in all", "total of"):
        assert banned not in yours.lower(), banned
    assert "every 4 weeks" not in lowered


def test_page_keeps_schema_and_unique_ids(race_index):
    full = gnb.generate_page(_unbound(), race_index)
    assert full.count('<script type="application/ld+json">') >= 2
    assert '<link rel="canonical" href="https://gravelgodcycling.com/race/unbound-200/">' in full
    ids = re.findall(r'\bid="([^"]+)"', full)
    assert len(ids) == len(set(ids)), sorted({i for i in ids if ids.count(i) > 1})


def test_race_without_route_data_hides_the_drawings(race_index):
    rd = _unbound()
    rd["course"]["ridewithgps_id"] = None
    html = _body(gnb.generate_page(rd, race_index))
    assert "gg-cd-prof" not in html and '<svg class="gg-cd-map' not in html
    assert "gg-cd-hero--flat" in html


def test_suppressed_marketing_drops_every_plan_ask(race_index):
    rd = _unbound()
    rd["taking_a_break"] = {"label": "Taking a break", "line": "No 2027 edition."}
    html = _body(gnb.generate_page(rd, race_index))
    assert "Start my plan" not in html and "route_bar_plan" not in html
    assert 'data-measure-section="custom-plan"' not in html
    assert "four weeks" not in html


def test_no_innerhtml_in_module():
    src = (ROOT / "wordpress" / "course_dossier.py").read_text()
    assert "innerHTML" not in src


def test_race_day_temperatures_cite_the_weather_archive(unbound_html):
    day = unbound_html[unbound_html.index('id="race-day"'):unbound_html.index('id="should"')]
    n = re.search(r'href="#gg-citation-(\d+)"', day).group(1)
    assert f'id="gg-citation-{n}"' in unbound_html
    item = unbound_html[unbound_html.index(f'id="gg-citation-{n}"'):]
    assert "open-meteo.com" in item[:400]
    assert "Open-Meteo" not in day
