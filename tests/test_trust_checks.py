"""Trust checks: the kinds of wrong data that make a visitor stop believing us.

Each class below is a problem that shipped (found Nov 1, 2026) and was
fixed; the test keeps it from coming back.

1. Discipline     — road / MTB / bikepacking races labelled "gravel".
2. Not running    — cancelled races ranked as top races.
3. Printed scores — prose saying "80 / 100" or "keeps it in Tier 4" when the
                    computed score / tier says otherwise.
4. Tiers          — tier labels that do not match the score thresholds.
5. Criteria copy  — "15 criteria" (it is 14 plus a cultural-impact bonus).
6. Race counts    — hard-coded "328 races" / "757 races" / "700+ races".
7. Countries      — homepage "regions" counted raw location text.
8. Links          — "Check X website" placeholders rendered as links.
9. Examples       — methodology examples whose tier is not what they show.
10. Stale dates   — new races dated more than a year in the past.
11. Email claims  — "lowest score in the database" no longer true.
12. Duplicates    — one real event published as two or three race pages.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RACE_DATA = ROOT / "race-data"
INDEX_PATH = ROOT / "web" / "race-index.json"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "wordpress"))

from race_facts import (  # noqa: E402
    BASE_CRITERIA_COUNT, date_says_inactive, is_ranked, location_countries,
    race_discipline, race_status,
)

T1, T2, T3 = 80, 60, 45


def _profiles():
    out = {}
    for f in sorted(RACE_DATA.glob("*.json")):
        out[f.stem] = json.loads(f.read_text(encoding="utf-8"))["race"]
    return out


PROFILES = _profiles()


def _index():
    if not INDEX_PATH.exists():
        pytest.skip("web/race-index.json not generated")
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def _strings(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _strings(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        yield path, obj


# Fields that quote outside sources or record history, not our verdicts.
_NOT_OUR_PROSE = (".youtube_data", ".citations", ".research_metadata",
                  ".source_review", ".results")


def _our_prose(race):
    for path, text in _strings(race):
        if path.startswith(_NOT_OUR_PROSE) or "score_note" in path:
            continue
        yield path, text


# ── 1. Discipline ─────────────────────────────────────────────────────────

class TestDiscipline:
    def test_rating_and_vitals_discipline_agree(self):
        bad = []
        for slug, r in PROFILES.items():
            g = (r.get("gravel_god_rating") or {}).get("discipline")
            v = (r.get("vitals") or {}).get("discipline")
            if v and not g:
                bad.append(f"{slug}: vitals says {v}, rating has none")
            elif v and g and race_discipline({"gravel_god_rating": {"discipline": v}}) != race_discipline(r):
                bad.append(f"{slug}: rating {g} vs vitals {v}")
        assert not bad, "\n".join(bad)

    def test_index_discipline_matches_profile(self):
        bad = [f"{e['slug']}: index {e.get('discipline')} vs profile {race_discipline(PROFILES[e['slug']])}"
               for e in _index() if e["slug"] in PROFILES
               and e.get("discipline") != race_discipline(PROFILES[e["slug"]])]
        assert not bad, "\n".join(bad)

    def test_recalculate_tiers_keeps_discipline(self):
        import copy
        import recalculate_tiers
        for slug in ("granfondo-nove-colli", "tour-divide"):
            if slug not in PROFILES:
                continue
            data = {"race": copy.deepcopy(PROFILES[slug])}
            before = race_discipline(data["race"])
            recalculate_tiers.recalculate_race(data, slug)
            assert data["race"]["gravel_god_rating"]["discipline"] == before


# ── 2. Not running ────────────────────────────────────────────────────────

class TestNotRunning:
    def test_cancelled_wording_has_the_status_switch(self):
        """date_specific saying cancelled/hiatus/dropped must set taking_a_break,
        the one switch every page and ranking reads."""
        bad = [slug for slug, r in PROFILES.items()
               if date_says_inactive(r) and not r.get("taking_a_break")]
        assert not bad, f"say not-running in date_specific but have no taking_a_break: {bad}"

    def test_index_carries_status(self):
        for e in _index():
            r = PROFILES.get(e["slug"])
            if r is None:
                continue
            assert e.get("status") == race_status(r)["status"], e["slug"]

    def test_power_rankings_skip_not_running(self):
        from generate_power_rankings import build_power_rankings_page
        idx = _index()
        inactive = [e for e in idx if not is_ranked(e)]
        assert inactive, "expected at least one not-running race in the catalog"
        page = build_power_rankings_page(idx)
        for e in inactive:
            assert f'/race/{e["slug"]}/"' not in page, e["slug"]

    def test_homepage_top_lists_skip_not_running(self):
        from generate_homepage import (build_sidebar, build_tabbed_rankings,
                                       compute_stats, get_featured_races)
        idx = _index()
        inactive = {e["slug"] for e in idx if not is_ranked(e)}
        assert not inactive & {r["slug"] for r in get_featured_races(idx)}
        stats = compute_stats(idx)
        sidebar = build_sidebar(stats, idx, [])
        rankings = build_tabbed_rankings(idx)
        for e in idx:
            if e["slug"] in inactive:
                assert e["name"] not in sidebar.split("TOP 5")[1].split("</ol>")[0], e["slug"]
                assert f'/race/{e["slug"]}/"' not in rankings, e["slug"]

    def test_calendar_skips_not_running(self):
        from generate_calendar import build_calendar_page
        idx = _index()
        page = build_calendar_page(idx)
        for e in idx:
            if not is_ranked(e):
                assert f'/race/{e["slug"]}/"' not in page, e["slug"]

    def test_tier_hubs_mark_not_running(self):
        from generate_tier_hubs import build_hub_page
        idx = _index()
        for tier in (1, 2, 3, 4):
            races = [e for e in idx if e.get("tier") == tier]
            off = [e for e in races if not is_ranked(e)]
            if not off:
                continue
            page = build_hub_page(tier, races, idx)
            assert page.count('class="gg-status-badge"') == len(off)


# ── 3. Printed scores ─────────────────────────────────────────────────────

# Not "25/50/100-mile" options or "$250/200/150/100" purse splits.
_SCORE_RE = re.compile(r"(?<![\d.$/])(\d{2,3})\s*/\s*100\b(?!\s*(?:/|-?mi|km))")
_KEEP_TIER_RE = re.compile(r"\b(?:keeps?|keeping|places?|holds?) it (?:firmly )?in Tier ([1-4])\b")
_RATIONALE_RE = re.compile(r"\bscore (\d{2,3})\b", re.IGNORECASE)


class TestPrintedScores:
    def test_final_verdict_score_matches_overall(self):
        bad = []
        for slug, r in PROFILES.items():
            fv = (r.get("final_verdict") or {}).get("score")
            if fv is None:
                continue
            want = f"{r['gravel_god_rating']['overall_score']} / 100"
            if fv != want:
                bad.append(f"{slug}: final_verdict.score {fv!r}, computed {want!r}")
        assert not bad, "\n".join(bad)

    def test_prose_scores_match_overall(self):
        bad = []
        for slug, r in PROFILES.items():
            overall = r["gravel_god_rating"]["overall_score"]
            for path, text in _our_prose(r):
                if path == ".final_verdict.score":
                    continue
                for m in _SCORE_RE.finditer(text):
                    if int(m.group(1)) != overall:
                        bad.append(f"{slug} {path}: says {m.group(0)}, computed {overall}")
            rationale = r["gravel_god_rating"].get("tier_rationale") or ""
            for m in _RATIONALE_RE.finditer(rationale):
                if int(m.group(1)) != overall:
                    bad.append(f"{slug} tier_rationale: says score {m.group(1)}, computed {overall}")
        assert not bad, "\n".join(bad)

    def test_prose_tier_matches_tier(self):
        bad = []
        for slug, r in PROFILES.items():
            g = r["gravel_god_rating"]
            tier = g.get("display_tier", g.get("tier"))
            for path, text in _our_prose(r):
                for m in _KEEP_TIER_RE.finditer(text):
                    if int(m.group(1)) != tier:
                        bad.append(f"{slug} {path}: '{m.group(0)}' but tier is {tier}")
        assert not bad, "\n".join(bad)


# ── 4. Tiers ──────────────────────────────────────────────────────────────

def _expected_tier(score, prestige):
    base = 1 if score >= T1 else 2 if score >= T2 else 3 if score >= T3 else 4
    if prestige == 5:
        if score >= 75:
            return 1
        return min(base, 2)
    if prestige == 4 and base > 2:
        return base - 1
    return base


class TestTiers:
    def test_tier_follows_published_thresholds(self):
        """Score thresholds plus the published prestige override, no
        undocumented demotions or promotions in either direction."""
        bad = []
        for slug, r in PROFILES.items():
            g = r["gravel_god_rating"]
            want = _expected_tier(g["overall_score"], g.get("prestige", 0))
            for key in ("tier", "display_tier"):
                if key in g and g[key] != want:
                    bad.append(f"{slug}: {key}={g[key]}, score {g['overall_score']} "
                               f"prestige {g.get('prestige')} -> Tier {want}")
        assert not bad, "\n".join(bad)


# ── 5 + 6. Public copy: criteria count and race counts ────────────────────

PUBLIC_SOURCES = (
    sorted((ROOT / "wordpress").glob("*.py"))
    + [ROOT / "scripts" / n for n in (
        "generate_meta_descriptions.py", "generate_video_scripts.py",
        "generate_video_briefs.py", "social_engine.py", "assemble_video.py",
        "experiment_templates.py", "generate_llms_txt.py")]
    + [p for p in sorted((ROOT / "mission_control" / "templates" / "emails").rglob("*.html"))
       if not p.name.startswith("road_")]   # Roadie Labs copy: its own rubric
    + [ROOT / "seo" / "meta-descriptions.json", ROOT / "website-data" / "README.md"]
)

_FIFTEEN_RE = re.compile(
    r"\b(?:15|fifteen)[\s-]+(?:scoring[\s-]+)?(?:criteria|dimensions?|things)\b", re.IGNORECASE)
_STALE_COUNT_RE = re.compile(
    r"\b(?:328|757|700\+?|700-plus)\s+(?:gravel\s+)?(?:races?|race profiles|course profiles|analyzed courses|Race Prep Kits)\b",
    re.IGNORECASE)
# Coaching copy describes the coach's whole body of work across brands.
_COUNT_EXEMPT = {"generate_coaching.py"}


class TestPublicCopy:
    def test_no_fifteen_criteria(self):
        bad = []
        for p in PUBLIC_SOURCES:
            if not p.exists():
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if _FIFTEEN_RE.search(line) and "Roadie Labs rubric" not in line:
                    bad.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:120]}")
        assert not bad, ("The rating is 14 criteria plus a cultural-impact bonus:\n"
                         + "\n".join(bad))

    def test_no_hardcoded_race_counts(self):
        bad = []
        for p in PUBLIC_SOURCES:
            if not p.exists() or p.name in _COUNT_EXEMPT:
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if _STALE_COUNT_RE.search(line) and not line.lstrip().startswith("#"):
                    bad.append(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:120]}")
        assert not bad, "Read the count from race-data, never a literal:\n" + "\n".join(bad)

    def test_criteria_constant(self):
        from generate_neo_brutalist import ALL_DIMS
        assert BASE_CRITERIA_COUNT == len(ALL_DIMS) == 14


# ── 7. Countries ──────────────────────────────────────────────────────────

class TestCountries:
    def test_every_location_resolves_to_a_country(self):
        allowed_unknown = {"grinduro"}  # a multi-continent series, no single place
        bad = [f"{slug}: {r['vitals'].get('location')!r}"
               for slug, r in PROFILES.items()
               if slug not in allowed_unknown and r["vitals"].get("location")
               and not location_countries(r["vitals"]["location"])
               and "europe" not in r["vitals"]["location"].lower()]
        assert not bad, "\n".join(bad)

    @pytest.mark.parametrize("loc,want", [
        ("Elbert, CO", ["USA"]),
        ("Lincoln, Nebraska (Sandhills Global Event Center)", ["USA"]),
        ("Cedar Hill, New Mexico", ["USA"]),
        ("Turkey, Texas", ["USA"]),
        ("Patagonia, Arizona", ["USA"]),
        ("Mississippi Station, Ontario", ["Canada"]),
        ("Banff, Alberta to Antelope Wells, New Mexico", ["Canada", "USA"]),
        ("Mudgee, New South Wales, Australia", ["Australia"]),
        ("Hong Kong, China", ["China"]),
    ])
    def test_location_countries(self, loc, want):
        assert location_countries(loc) == want

    def test_balanced_brackets_in_locations(self):
        bad = [f"{slug}: {r['vitals']['location']!r}" for slug, r in PROFILES.items()
               if r["vitals"].get("location", "").count("(") != r["vitals"].get("location", "").count(")")]
        assert not bad, "\n".join(bad)


# ── 8. Links ──────────────────────────────────────────────────────────────

class TestLinks:
    def test_official_links_are_urls_or_empty(self):
        bad = []
        for slug, r in PROFILES.items():
            lg = r.get("logistics") or {}
            for k in ("official_site", "registration_url"):
                v = lg.get(k)
                if v and not re.match(r"https?://", str(v)):
                    bad.append(f"{slug}: logistics.{k} = {v!r}")
        assert not bad, "\n".join(bad)


# ── 9. Methodology examples ───────────────────────────────────────────────

class TestExamples:
    def test_methodology_tier_examples(self):
        src = (ROOT / "wordpress" / "generate_methodology.py").read_text(encoding="utf-8")
        table = src[src.index("def build_tier_system"):src.index("def build_dimensions")]
        rows = re.findall(r">TIER (\d)</span>.*?/race/([a-z0-9-]+)/", table, re.S)
        assert len(rows) == 4
        for tier, slug in rows:
            assert slug in PROFILES, f"example {slug} has no profile"
            assert PROFILES[slug]["gravel_god_rating"]["tier"] == int(tier), (
                f"methodology shows {slug} as Tier {tier}")

    def test_scoring_doc_example_tables_match_data(self):
        doc = (ROOT / "docs" / "GRAVEL_GOD_SCORING_SYSTEM.md").read_text(encoding="utf-8")
        blocks = re.findall(r"<!-- example-scores: ([a-z0-9-]+) .*?-->(.*?)(?=\n###|\n---)", doc, re.S)
        assert len(blocks) >= 2
        labels = {"Length": "length", "Technicality": "technicality", "Elevation": "elevation",
                  "Climate": "climate", "Altitude": "altitude", "Logistics": "logistics",
                  "Adventure": "adventure", "Prestige": "prestige", "Race Quality": "race_quality",
                  "Experience": "experience", "Community": "community", "Field Depth": "field_depth",
                  "Value": "value", "Expenses": "expenses", "Cultural Impact": "cultural_impact"}
        for slug, body in blocks:
            g = PROFILES[slug]["gravel_god_rating"]
            for label, val in re.findall(r"\| (?:Course|Editorial|Bonus) \| ([A-Za-z ]+) \| (\d) \|", body):
                assert int(val) == (g.get(labels[label]) or 0), f"{slug} {label}"
            assert f"**{g['overall_score']}/100**" in body, slug

    def test_scoring_doc_tier_examples(self):
        doc = (ROOT / "docs" / "GRAVEL_GOD_SCORING_SYSTEM.md").read_text(encoding="utf-8")
        assert "Barry-Roubaix" not in doc.split("## Course Profile")[0]
        assert "SBT GRVL" not in doc.split("## Course Profile")[0]


# ── 10. Stale dates (ratchet) ─────────────────────────────────────────────

# Running races whose newest listed date is in an earlier calendar year.
# Each needs a fresh date or a taking_a_break note; shrink this list, never
# grow it.
STALE_DATE_BASELINE = {
    "berryman-epic", "bohemian-border-bash", "burgr-95",
    "dusty-gravel-lacs-de-leau-dheure", "etape-du-dales", "galactic-grinder",
    "gran-fondo-argentina", "gran-fondo-hainan", "hardwood-hustle",
    "iron-cross", "la-vaujany", "nicolet-hot-days",
    "pickerel-buck40", "rose-city-rampage", "rust-buster-gravel-fondo",
    "serenissima-gravel", "switchgrass", "trans-iowa", "velothon-berlin",
    "veneto-gravel", "wollombi-gravel-fest",
}


class TestStaleDates:
    def test_no_new_stale_dates(self):
        this_year = date.today().year
        stale = set()
        for slug, r in PROFILES.items():
            if r.get("taking_a_break"):
                continue
            ds = str(r["vitals"].get("date_specific") or "")
            years = [int(y) for y in re.findall(r"\b(20\d\d)\b", ds)]
            if years and max(years) < this_year:
                stale.add(slug)
        new = stale - STALE_DATE_BASELINE
        assert not new, f"races newly showing a past-year date: {sorted(new)}"


# ── 11. Email claims ──────────────────────────────────────────────────────

class TestEmailClaims:
    def test_lowest_score_claim(self):
        """honest_ratings.html names the lowest-scoring race still running."""
        running = {s: r for s, r in PROFILES.items() if not r.get("taking_a_break")}
        low = min(running, key=lambda s: running[s]["gravel_god_rating"]["overall_score"])
        email = (ROOT / "mission_control/templates/emails/sequences/honest_ratings.html").read_text()
        score = running[low]["gravel_god_rating"]["overall_score"]
        name = running[low].get("display_name") or running[low]["name"]
        assert f"{score} out of 100" in email and name.split()[0] in email, (
            f"lowest running race is now {low} ({score})")


# ── 12. Duplicates ──────────────────────────────────────────────────────────

MERGES = json.loads((ROOT / "data" / "duplicate-merges.json").read_text())["merges"]

# Same first-location word + same month, but checked and NOT the same event.
NOT_DUPLICATES = {
    frozenset({"unbound-200", "unbound-xl"}): "two distances, separately rated",
    frozenset({"sea-otter-gravel", "fuego-mtb"}): "gravel race vs MTB race at one festival",
    frozenset({"big-sugar", "little-sugar-mtb"}): "gravel race vs MTB race, same weekend",
    frozenset({"crystal-bear", "bear-100"}): "separate Laona events (flagged for review)",
    frozenset({"opelika-okey-dokey", "standard-deluxe-dirt-road-century"}): "different dates (flagged for review)",
    frozenset({"nordic-chase-berlin-copenhagen-gravel", "velothon-berlin"}): "bikepacking route vs road sportive",
    frozenset({"forbidden-gravel", "unravel-gravel-va"}): "Cumberland, BC vs Cumberland, VA",
}

_MONTH_RE = re.compile(r"(January|February|March|April|May|June|July|August|"
                       r"September|October|November|December)")


class TestDuplicates:
    def test_merged_duplicates_are_retired_and_redirected(self):
        tombstones = {t["slug"]: t for t in json.loads(
            (ROOT / "config" / "tombstones.json").read_text())["tombstones"]}
        deployer = (ROOT / "scripts" / "push_wordpress.py").read_text()
        for m in MERGES:
            dup, canon = m["duplicate"], m["canonical"]
            assert not (RACE_DATA / f"{dup}.json").exists(), dup
            assert (ROOT / "race-data-archived" / "duplicates" / f"{dup}.json").exists(), dup
            assert (RACE_DATA / f"{canon}.json").exists(), canon
            assert tombstones.get(dup, {}).get("redirect") == f"/race/{canon}/", dup
            for rule in (
                f"RewriteRule ^race/{dup}/?$ /race/{canon}/ [R=301,L]",
                f"RewriteRule ^race/{dup}\\\\.md$ /race/{canon}.md [R=301,L]",
                f"RewriteRule ^race/{dup}/(.*)$ /race/{canon}/$1 [R=301,L]",
            ):
                assert rule in deployer, rule

    def test_alternative_slugs_point_at_live_races(self):
        bad = []
        for slug, race in PROFILES.items():
            for alt in (race.get("final_verdict") or {}).get("alternative_slugs") or []:
                if alt == slug or alt not in PROFILES:
                    bad.append(f"{slug} -> {alt}")
        assert not bad, bad

    def test_no_new_same_city_same_month_pairs(self):
        groups = {}
        for slug, race in PROFILES.items():
            vitals = race.get("vitals") or {}
            city = (vitals.get("location") or "").split(",")[0].strip().lower()
            month = _MONTH_RE.search(vitals.get("date_specific") or "")
            if city and month:
                groups.setdefault((city, month.group(1)), []).append(slug)
        suspects = []
        for slugs in groups.values():
            for i, a in enumerate(slugs):
                for b in slugs[i + 1:]:
                    if frozenset({a, b}) not in NOT_DUPLICATES:
                        suspects.append((a, b))
        assert not suspects, (
            f"Possible duplicate race pages (check, then merge or add to "
            f"NOT_DUPLICATES with the reason): {sorted(suspects)}")
