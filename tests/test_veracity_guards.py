"""Guards for the rankings veracity bot, one class per guard.

Fixtures are modeled on the real bad edits the bot committed to main:
  - 564145d5 (2026-10-01): Leadville elevation 11,900 -> 9,916 ft, the
    one-off 2026 Willow Fire reroute, sourced from cyclingnews.com;
    Majka Gran Fondo 73 -> 45.5 mi (the MedioFondo option).
  - 217d624f (2026-10-08): Nordic Chase elevation 23,622 -> 18,575 ft from
    Dotwatcher, contradicting the profile's own elevation_m 7200;
    Nordsjorittet 96 -> 56 mi from a blog.
  - Both runs: race-data edited, web/race-index.json never regenerated.
No API calls: verify_race is replaced with the agent's recorded verdicts.
"""

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import veracity_guards as vg  # noqa: E402
import verify_race_rankings as vrr  # noqa: E402
from recalculate_tiers import recalculate_score  # noqa: E402


def _rating(**overrides):
    r = {"logistics": 3, "length": 5, "technicality": 4, "elevation": 5,
         "climate": 4, "altitude": 5, "adventure": 5, "prestige": 5,
         "race_quality": 5, "experience": 5, "community": 5,
         "field_depth": 5, "value": 3, "expenses": 3, "cultural_impact": 0}
    r.update(overrides)
    r["overall_score"] = recalculate_score(r)
    for k in ("tier", "editorial_tier", "display_tier"):
        r[k] = 1 if r["overall_score"] >= 80 else 2
        r[f"{k}_label"] = f"TIER {r[k]}"
    return r


LEADVILLE = {
    "name": "Leadville Trail 100 MTB",
    "vitals": {"distance_mi": 100, "elevation_ft": 11900,
               "prize_purse": "$25,000+"},
    "logistics": {"official_site": "https://www.leadvilleraceseries.com/mtb"},
    "gravel_god_rating": _rating(),
}
NORDIC_CHASE = {
    "name": "Nordic Chase Copenhagen to Oslo Gravel",
    "vitals": {"distance_km": 800, "distance_mi": 497,
               "elevation_m": 7200, "elevation_ft": 23622},
    "logistics": {"official_site": "https://nordicchase.com/cph-osl-gravel"},
    "citations": [{"url": "https://nordicchase.com/cph-osl-gravel",
                   "category": "official", "label": "official route"}],
    "gravel_god_rating": _rating(),
}
MAJKA = {
    "name": "Majka Gran Fondo",
    "vitals": {"distance_mi": 73, "elevation_ft": 5200,
               "website": "https://www.majkagranfondo.com"},
    "gravel_god_rating": _rating(length=3, elevation=4, altitude=2, prestige=3),
}
NORDSJORITTET = {
    "name": "Nordsjorittet",
    "vitals": {"distance_mi": 96, "elevation_ft": 4900},
    "logistics": {"official_site": "https://nordsjorittet.no"},
    "gravel_god_rating": _rating(length=3, elevation=3, altitude=1),
}


@pytest.fixture
def races(tmp_path, monkeypatch):
    """A temp race-data dir; returns a writer(slug, race) -> path."""
    race_dir = tmp_path / "race-data"
    race_dir.mkdir()
    monkeypatch.setattr(vrr, "RACE_DATA", race_dir)

    def write(slug, race):
        path = race_dir / f"{slug}.json"
        path.write_text(json.dumps({"race": json.loads(json.dumps(race))}))
        return path
    return write


# base sum 54 -> 77; one length point less -> 53 -> 76 (a 1-point move)
SMALL_RATING = _rating(length=4, elevation=4, altitude=3, prestige=4,
                       field_depth=4, community=4, value=2)


def _v(field, web_value, url, note=None, scope="standard_course",
       source_type="official_site"):
    return {"field": field, "verdict": "mismatch", "web_value": web_value,
            "confidence": "high", "source_url": url, "source_type": source_type,
            "course_scope": scope, "note": note}


def _vitals(path):
    return json.loads(path.read_text())["race"]["vitals"]


def _one(changes, field):
    return next(c for c in changes if c["field"] == field)


# ---------------------------------------------------------------------------
# 2. Source priority
# ---------------------------------------------------------------------------

class TestSourcePriority:
    @pytest.mark.parametrize("url,tier", [
        ("https://nordicchase.com/cph-osl-gravel-2026", vg.TIER_OFFICIAL),
        ("https://www.athlinks.com/event/123/results", vg.TIER_RESULTS),
        ("https://www.cyclingnews.com/races/leadville-trail-100-mtb-2026/", vg.TIER_OUTLET),
        ("https://battistrada.com/en/cycling-calendar/edition/x/1/", vg.TIER_OTHER),
        ("https://dotwatcher.cc/race/nordic-chase-2026-cph-osl-gravel-edition", vg.TIER_TRACKER),
        (None, vg.TIER_TRACKER),
    ])
    def test_tiers(self, url, tier):
        assert vg.source_tier(url, NORDIC_CHASE) == tier

    def test_dotwatcher_never_overwrites_organizer_elevation(self, races):
        """217d624f: Dotwatcher's 5,660 m replaced the organizer's 7,200 m."""
        path = races("nordic-chase-gravel", NORDIC_CHASE)
        changes = vrr.apply_fixes("nordic-chase-gravel", [_v(
            "elevation_ft", "18575",
            "https://dotwatcher.cc/race/nordic-chase-2026-cph-osl-gravel-edition",
            note="Official 2026 race data from Dotwatcher shows 5,660 m elevation")],
            dry_run=False)
        c = _one(changes, "vitals.elevation_ft")
        assert c["flag_only"] and "tracker" in c["reason"]
        assert _vitals(path)["elevation_ft"] == 23622

    def test_outlet_cannot_overwrite_official_backed_value(self, races):
        path = races("nordic-chase-gravel", NORDIC_CHASE)
        changes = vrr.apply_fixes("nordic-chase-gravel", [_v(
            "distance_mi", "430", "https://www.bikepacking.com/news/nordic-chase/")],
            dry_run=False)
        c = _one(changes, "vitals.distance_mi")
        assert c["flag_only"] and "cannot overwrite" in c["reason"]
        assert _vitals(path)["distance_mi"] == 497

    def test_recorded_provenance_blocks_weaker_source(self, races):
        """No official citation, but the bot recorded an official source for
        the current value on an earlier run."""
        path = races("leadville-100", {**LEADVILLE, "logistics": {}})
        prov = {"prize_purse": {"value": "$25,000+", "tier": vg.TIER_OFFICIAL,
                                "url": "https://www.leadvilleraceseries.com/mtb"}}
        changes = vrr.apply_fixes("leadville-100", [_v(
            "prize_purse", "$15,000", "https://www.cyclingnews.com/x/")],
            dry_run=False, provenance=prov)
        assert _one(changes, "vitals.prize_purse")["flag_only"]
        assert _vitals(path)["prize_purse"] == "$25,000+"

    def test_outlet_change_goes_to_review_not_main(self, races):
        path = races("leadville-100", {**LEADVILLE, "logistics": {}})
        changes = vrr.apply_fixes("leadville-100", [_v(
            "prize_purse", "$60,000", "https://www.cyclingnews.com/x/")],
            dry_run=False)
        assert _one(changes, "vitals.prize_purse")["needs_review"]
        assert _vitals(path)["prize_purse"] == "$25,000+"

    def test_official_site_small_fix_still_auto_applies(self, races):
        path = races("leadville-100", LEADVILLE)
        changes = vrr.apply_fixes("leadville-100", [_v(
            "prize_purse", "$60,000",
            "https://www.leadvilleraceseries.com/mtb/leadvilletrail100mtb/")],
            dry_run=False)
        assert not _one(changes, "vitals.prize_purse").get("needs_review")
        assert _vitals(path)["prize_purse"] == "$60,000"

    def test_prompt_states_source_priority(self):
        prompt = vrr.build_prompt(NORDIC_CHASE)
        assert "official race website" in prompt and "trackers" in prompt
        assert "Dotwatcher" in prompt


# ---------------------------------------------------------------------------
# 3. Course scope
# ---------------------------------------------------------------------------

REROUTE_NOTE = ("2026 elevation gain is 9,916 feet, not 11,900 feet. Modified "
                "route excludes Powerline, Sugarloaf, and Hagerman Pass.")


class TestCourseScope:
    def test_leadville_fire_reroute_is_a_note_not_the_value(self, races):
        """564145d5, the exact verdict the bot acted on (cyclingnews)."""
        path = races("leadville-100", LEADVILLE)
        changes = vrr.apply_fixes("leadville-100", [_v(
            "elevation_ft", "9916",
            "https://www.cyclingnews.com/races/leadville-trail-100-mtb-2026/",
            note=REROUTE_NOTE, scope="one_off_edition", source_type="media_outlet")],
            dry_run=False)
        c = _one(changes, "vitals.elevation_ft")
        assert c["flag_only"] and c.get("one_off")
        data = json.loads(path.read_text())["race"]
        assert data["vitals"]["elevation_ft"] == 11900
        assert data["gravel_god_rating"]["elevation"] == 5
        assert data["gravel_god_rating"]["overall_score"] == LEADVILLE["gravel_god_rating"]["overall_score"]

    def test_reroute_blocked_even_from_official_site(self, races):
        path = races("leadville-100", LEADVILLE)
        vrr.apply_fixes("leadville-100", [_v(
            "elevation_ft", "9916", "https://www.leadvilleraceseries.com/mtb/",
            note="2026 course modified due to the Willow Fire",
            scope="one_off_edition")], dry_run=False)
        assert _vitals(path)["elevation_ft"] == 11900

    def test_note_keywords_backstop_a_mislabelled_scope(self, races):
        """The agent says standard_course, but its own note says reroute."""
        path = races("leadville-100", LEADVILLE)
        changes = vrr.apply_fixes("leadville-100", [_v(
            "elevation_ft", "9916", "https://www.leadvilleraceseries.com/mtb/",
            note=REROUTE_NOTE, scope="standard_course")], dry_run=False)
        assert _one(changes, "vitals.elevation_ft").get("one_off")
        assert _vitals(path)["elevation_ft"] == 11900

    def test_majka_medio_fondo_never_replaces_flagship(self, races):
        """564145d5: official site lists 100/73/46 km; the bot took 73 km."""
        path = races("majka-gran-fondo", MAJKA)
        note = ("Official website states three distances: 100 km (62.1 mi), "
                "73 km (45.4 mi), and 46 km (28.6 mi).")
        changes = vrr.apply_fixes("majka-gran-fondo", [
            _v("distance_mi", "45.5", "https://www.majkagranfondo.com/", note=note),
            _v("elevation_ft", "3937", "https://www.majkagranfondo.com/",
               note="MedioFondo (73 km distance) has 1200m", scope="shorter_option"),
        ], dry_run=False)
        assert all(c["flag_only"] for c in changes)
        assert _vitals(path)["distance_mi"] == 73
        assert _vitals(path)["elevation_ft"] == 5200

    def test_agent_shorter_option_label_blocks(self, races):
        path = races("nordsjorittet", NORDSJORITTET)
        vrr.apply_fixes("nordsjorittet", [_v(
            "distance_mi", "84", "https://nordsjorittet.no/",
            scope="shorter_option")], dry_run=False)
        assert _vitals(path)["distance_mi"] == 96

    def test_prompt_states_flagship_scope(self):
        prompt = vrr.build_prompt(LEADVILLE)
        assert "STANDARD FLAGSHIP course" in prompt
        assert "one_off_edition" in prompt and "shorter_option" in prompt

    def test_schema_requires_scope_and_source_type(self):
        item = vrr.VERIFY_SCHEMA["properties"]["fields"]["items"]
        assert {"course_scope", "source_type"} <= set(item["required"])


# ---------------------------------------------------------------------------
# 4. Change limits
# ---------------------------------------------------------------------------

class TestChangeLimits:
    def test_nordsjorittet_blog_source_is_never_written(self, races):
        """217d624f: 96 -> 56 mi from nordictrailblazer.cc (a blog)."""
        path = races("nordsjorittet", NORDSJORITTET)
        changes = vrr.apply_fixes("nordsjorittet", [_v(
            "distance_mi", "56",
            "https://nordictrailblazer.cc/blog/follow-nordsjorittet-gravel-race/",
            note="Multiple sources confirm the race is 91 km (56 mi)",
            source_type="other")], dry_run=False)
        assert _one(changes, "vitals.distance_mi")["flag_only"]
        assert _vitals(path)["distance_mi"] == 96

    def test_over_15_percent_official_goes_to_review(self, races):
        path = races("nordsjorittet", NORDSJORITTET)
        changes = vrr.apply_fixes("nordsjorittet", [_v(
            "distance_mi", "70", "https://nordsjorittet.no/")], dry_run=False)
        c = _one(changes, "vitals.distance_mi")
        assert c["needs_review"] and "limit 15%" in c["reason"]
        assert _vitals(path)["distance_mi"] == 96  # not on main
        # the review pass applies it, for the PR
        vrr.apply_fixes("nordsjorittet", [_v(
            "distance_mi", "70", "https://nordsjorittet.no/")],
            dry_run=False, allow_review=True)
        assert _vitals(path)["distance_mi"] == 70

    def test_king_of_the_lake_huge_swing_is_flag_only(self, races):
        path = races("king-of-the-lake",
                     {**NORDSJORITTET, "vitals": {"distance_mi": 65, "elevation_ft": 3500}})
        changes = vrr.apply_fixes("king-of-the-lake", [_v(
            "distance_mi", "29", "https://nordsjorittet.no/")],
            dry_run=False, allow_review=True)
        assert _one(changes, "vitals.distance_mi")["flag_only"]
        assert _vitals(path)["distance_mi"] == 65

    def test_overall_score_move_of_two_goes_to_review(self, races):
        # base sum + ci = 55 -> 79; one length point less -> 54 -> 77
        rating = _rating(length=4, elevation=4, altitude=3, prestige=4,
                         field_depth=4, community=4)
        assert rating["overall_score"] == 79
        path = races("score-race", {"name": "Score Race",
                                    "vitals": {"distance_mi": 105, "elevation_ft": 7000},
                                    "logistics": {"official_site": "https://score.example"},
                                    "gravel_god_rating": rating})
        changes = vrr.apply_fixes("score-race", [_v(
            "distance_mi", "98", "https://score.example/course")], dry_run=False)
        overall = _one(changes, "rating.overall_score")
        assert (overall["old"], overall["new"]) == (79, 77)
        assert overall["needs_review"] and "2+" in overall["reason"]
        # race is all-or-nothing: the small distance fix waits for review too
        assert _one(changes, "vitals.distance_mi")["needs_review"]
        assert _vitals(path)["distance_mi"] == 105

    def test_one_point_move_auto_applies(self, races):
        rating = SMALL_RATING
        path = races("small-race", {"name": "Small Race",
                                    "vitals": {"distance_mi": 105, "elevation_ft": 7000},
                                    "logistics": {"official_site": "https://small.example"},
                                    "gravel_god_rating": rating})
        changes = vrr.apply_fixes("small-race", [_v(
            "distance_mi", "98", "https://small.example/")], dry_run=False)
        overall = _one(changes, "rating.overall_score")
        assert abs(overall["new"] - overall["old"]) == 1
        assert not any(c.get("needs_review") for c in changes)
        assert _vitals(path)["distance_mi"] == 98

    @pytest.mark.parametrize("old,new,review", [(5, 4, False), (5, 3, True),
                                                (89, 87, True), (70, 71, False)])
    def test_score_delta_rule(self, old, new, review):
        assert vg.score_delta_needs_review(old, new) is review


# ---------------------------------------------------------------------------
# 5. Unit sanity
# ---------------------------------------------------------------------------

class TestUnitSanity:
    def test_official_value_contradicting_own_elevation_m_is_refused(self, races):
        """Even from the organizer's domain, 18,575 ft != the profile's 7,200 m."""
        path = races("nordic-chase-gravel", NORDIC_CHASE)
        changes = vrr.apply_fixes("nordic-chase-gravel", [_v(
            "elevation_ft", "18575", "https://nordicchase.com/cph-osl-gravel-2026")],
            dry_run=False, allow_review=True)
        c = _one(changes, "vitals.elevation_ft")
        assert c["flag_only"] and "elevation_m" in c["reason"]
        assert _vitals(path)["elevation_ft"] == 23622

    def test_value_matching_own_metric_twin_is_allowed(self, races):
        """elevation_ft was the bad conversion; the twin (1000 m) backs 3,281 ft."""
        race = {**NORDIC_CHASE, "vitals": {"elevation_m": 1000, "elevation_ft": 2600}}
        path = races("twin-race", race)
        changes = vrr.apply_fixes("twin-race", [_v(
            "elevation_ft", "3281", "https://nordicchase.com/x")],
            dry_run=False, allow_review=True)
        assert not _one(changes, "vitals.elevation_ft").get("flag_only")
        assert _vitals(path)["elevation_ft"] == 3281

    def test_km_as_miles_mixup_goes_to_review(self, races):
        """Majka's 73 'mi' was 73 km: 45.4 is a conversion, not a correction."""
        race = {**MAJKA, "vitals": {"distance_mi": 73, "elevation_ft": 5200,
                                    "website": "https://www.majkagranfondo.com"}}
        path = races("majka-gran-fondo", race)
        changes = vrr.apply_fixes("majka-gran-fondo", [_v(
            "distance_mi", "45.4", "https://www.majkagranfondo.com/")], dry_run=False)
        c = _one(changes, "vitals.distance_mi")
        assert c["needs_review"] and "unit conversion" in c["reason"]
        assert _vitals(path)["distance_mi"] == 73

    @pytest.mark.parametrize("field,old,new,mixup", [
        ("distance_mi", 73, 45.4, True), ("distance_mi", 56, 90, True),
        ("elevation_ft", 2000, 6562, True), ("distance_mi", 100, 90, False),
    ])
    def test_mixup_detector(self, field, old, new, mixup):
        assert vg.looks_like_unit_mixup(field, old, new) is mixup


# ---------------------------------------------------------------------------
# 1. Derived data: index regeneration + drift check
# ---------------------------------------------------------------------------

def _write_index(tmp_path, monkeypatch, entries):
    idx = tmp_path / "race-index.json"
    idx.write_text(json.dumps(entries))
    monkeypatch.setattr(vrr, "INDEX_FILE", idx)
    return idx


def _index_entry(slug, race):
    r, v = race["gravel_god_rating"], race["vitals"]
    return {"slug": slug, "overall_score": r["overall_score"], "tier": r["display_tier"],
            "distance_mi": v.get("distance_mi"), "elevation_ft": v.get("elevation_ft")}


class TestIndexRegeneration:
    def test_missing_regen_is_detected(self, races, tmp_path, monkeypatch):
        """The 9-day red main: profile edited, index still holds old values."""
        races("leadville-100", LEADVILLE)
        stale = dict(_index_entry("leadville-100", LEADVILLE), overall_score=87,
                     elevation_ft=9916)
        _write_index(tmp_path, monkeypatch, [stale])
        drift = vrr.publish_derived(["leadville-100"], regenerate=lambda: None)
        assert any("overall_score" in d for d in drift)
        assert any("elevation_ft" in d for d in drift)

    def test_regenerated_index_passes(self, races, tmp_path, monkeypatch):
        races("leadville-100", LEADVILLE)
        idx = _write_index(tmp_path, monkeypatch, [])
        regen = lambda: idx.write_text(json.dumps([_index_entry("leadville-100", LEADVILLE)]))  # noqa: E731
        assert vrr.publish_derived(["leadville-100"], regenerate=regen) == []

    def test_no_writes_no_regen(self):
        called = []
        assert vrr.publish_derived([], regenerate=lambda: called.append(1)) == []
        assert called == []

    def _run_main(self, races, tmp_path, monkeypatch, slug, race, verdicts, regen):
        races(slug, race)
        vdir = tmp_path / "verification"
        monkeypatch.setattr(vrr, "VERIFY_DIR", vdir)
        monkeypatch.setattr(vrr, "STATE_FILE", vdir / "verify_state.json")
        monkeypatch.setattr(vrr, "REPORT_FILE", vdir / "last_run_report.json")
        monkeypatch.setattr(vrr.anthropic, "Anthropic", lambda: None)
        monkeypatch.setattr(vrr, "verify_race",
                            lambda client, s: {"slug": s, "fields": verdicts})
        monkeypatch.setattr(vrr, "regenerate_derived", regen)
        queue = tmp_path / "queue.json"
        monkeypatch.setattr(sys, "argv", ["verify", "--slug", slug,
                                          "--review-queue", str(queue)])
        return vrr.main(), queue, vdir

    def test_main_regenerates_after_auto_fix(self, races, tmp_path, monkeypatch):
        idx = _write_index(tmp_path, monkeypatch, [_index_entry("leadville-100", LEADVILLE)])
        calls = []

        def regen():
            calls.append(1)
            race = json.loads((vrr.RACE_DATA / "leadville-100.json").read_text())["race"]
            idx.write_text(json.dumps([_index_entry("leadville-100", race)]))

        code, _, _ = self._run_main(races, tmp_path, monkeypatch, "leadville-100", LEADVILLE,
                                    [_v("prize_purse", "$60,000",
                                        "https://www.leadvilleraceseries.com/mtb/")], regen)
        assert calls == [1] and code == 0

    def test_main_fails_when_index_not_regenerated(self, races, tmp_path, monkeypatch):
        rating = SMALL_RATING
        race = {"name": "Small Race", "vitals": {"distance_mi": 105, "elevation_ft": 7000},
                "logistics": {"official_site": "https://small.example"},
                "gravel_god_rating": rating}
        _write_index(tmp_path, monkeypatch, [_index_entry("small-race", race)])
        code, _, _ = self._run_main(races, tmp_path, monkeypatch, "small-race", race,
                                    [_v("distance_mi", "98", "https://small.example/")],
                                    regen=lambda: None)
        assert code == 2

    def test_main_queues_review_and_records_one_off(self, races, tmp_path, monkeypatch):
        _write_index(tmp_path, monkeypatch, [_index_entry("leadville-100", LEADVILLE)])
        verdicts = [
            _v("elevation_ft", "9916", "https://www.leadvilleraceseries.com/mtb/",
               note=REROUTE_NOTE, scope="one_off_edition"),
            _v("prize_purse", "$60,000", "https://www.cyclingnews.com/x/"),
        ]
        race = {**LEADVILLE, "logistics": {"official_site": "https://www.leadvilleraceseries.com/mtb"}}
        code, queue, vdir = self._run_main(races, tmp_path, monkeypatch, "leadville-100",
                                           race, verdicts, regen=lambda: None)
        assert code == 0
        state = json.loads((vdir / "verify_state.json").read_text())
        assert state["leadville-100"]["one_off_notes"][0]["value"] == 9916
        # no official citation backs the purse, so the outlet's value is
        # queued for the human-review PR instead of landing on main
        assert json.loads(queue.read_text())[0]["slug"] == "leadville-100"
        assert _vitals(vrr.RACE_DATA / "leadville-100.json")["prize_purse"] == "$25,000+"

    def test_review_queue_pass_writes_pr_body(self, races, tmp_path, monkeypatch):
        path = races("nordsjorittet", NORDSJORITTET)
        idx = _write_index(tmp_path, monkeypatch, [])
        monkeypatch.setattr(vrr, "STATE_FILE", tmp_path / "state.json")

        def regen():
            race = json.loads(path.read_text())["race"]
            idx.write_text(json.dumps([_index_entry("nordsjorittet", race)]))
        monkeypatch.setattr(vrr, "regenerate_derived", regen)
        queue = tmp_path / "queue.json"
        queue.write_text(json.dumps([{"slug": "nordsjorittet", "verdicts": [
            _v("distance_mi", "70", "https://nordsjorittet.no/")]}]))
        body = tmp_path / "body.md"
        assert vrr.apply_review_queue(queue, body) == 0
        assert _vitals(path)["distance_mi"] == 70
        text = body.read_text()
        assert "| `nordsjorittet` | vitals.distance_mi | 96.0 | 70.0 | https://nordsjorittet.no/" in text


# ---------------------------------------------------------------------------
# Workflow wiring: gates before push, PR fallback, labelled review PR
# ---------------------------------------------------------------------------

class TestWorkflowWiring:
    @pytest.fixture(scope="class")
    def steps(self):
        wf = yaml.safe_load((ROOT / ".github/workflows/rankings-veracity.yml").read_text())
        return {s.get("name", ""): s for s in wf["jobs"]["verify"]["steps"]}

    def _step(self, steps, prefix):
        return next(s for n, s in steps.items() if n.startswith(prefix))

    def test_index_integrity_gates_the_commit(self, steps):
        gate = self._step(steps, "Verification gates")
        assert "tests/test_index_integrity.py" in gate["run"]
        commit = self._step(steps, "Commit fixes to main")
        assert "steps.gates.outcome == 'success'" in commit["if"]
        assert "web/race-index.json" in commit["run"]
        assert "generate_index.py --with-jsonld" in commit["run"]

    def test_gate_failure_opens_pr_not_push_to_main(self, steps):
        fail = self._step(steps, "Gates failed")
        assert "steps.gates.outcome == 'failure'" in fail["if"]
        assert "gh pr create" in fail["run"] and "--label" in fail["run"]
        assert "git push origin \"$BRANCH\"" in fail["run"]

    def test_over_limit_changes_open_labelled_review_pr(self, steps):
        review = self._step(steps, "Over-limit changes")
        assert "--apply-review-queue" in review["run"]
        assert "gh pr create" in review["run"] and "$REVIEW_LABEL" in review["run"]
        assert "--body-file" in review["run"]
