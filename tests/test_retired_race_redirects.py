"""A race that leaves race-data/ must leave no live page behind.

The deploy only adds files, so every URL a retired race ever had (page, .md
mirror, prep kit, training plan, tires, head-to-head pages) keeps serving its
old content until an .htaccess rule catches it. On 2026-11-06 eight races
deleted in August (#63) still answered 200 on every one of those URLs, 14
retired races still served their .md mirror, and ~350 road races that moved to
Roadie Labs still served their prep kit and training plan.

These tests read the evaluated REDIRECT_BLOCK the way Apache does (first
matching unconditional rule wins). The server-side twin is
`push_wordpress.py --check-retired-races`, run by Publish Site.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "wordpress"))

import retired_races as rr  # noqa: E402
from push_wordpress import (  # noqa: E402
    REDIRECT_BLOCK,
    RETIRED_RACE_REDIRECT_SECTION,
)

RULES = rr.unconditional_rules(REDIRECT_BLOCK)
GENERATED_RULES = rr.unconditional_rules(RETIRED_RACE_REDIRECT_SECTION)
TOMBSTONES = rr.load_tombstones()
LIVE = rr.live_race_slugs()
RETIRED = rr.retired_slugs(REDIRECT_BLOCK, TOMBSTONES, LIVE)
INDEX = json.loads((ROOT / "web" / "race-index.json").read_text())

# Served 200 on 2026-11-06 although their race had left race-data/.
LIVE_ON_2026_11_06 = [
    *(f"race/{s}{p}" for s in (
        "3-state-3-mountain-challenge", "6-hours-of-syllamo",
        "gravel-fondo-louisiana", "gun-flint-44", "lake-country-gravel",
        "paris-mountain-gravel-grinder", "ride-the-gravel-trails", "spring-thaw")
      for p in ("/", ".md", "/prep-kit/", "/training-plan/")),
    *(f"race/{s}.md" for s in (
        "3rides-aachen", "66-south-pyrenees", "almanzo-100", "big-horn-gravel",
        "chiang-mai-gran-fondo", "gfny-bali", "gran-fondo-greece-loutraki",
        "gravel-des-flandres", "gravel-fondo-switzerland", "polish-gravel",
        "pony-xpress-gravel-160", "rad-dirt-fest", "rasputitsa-spring-classic",
        "sagan-fondo")),
    "race/la-marmotte/prep-kit/", "race/la-marmotte/training-plan/",
    "race/gfny-new-york/prep-kit/", "race/letape-du-tour/training-plan/",
]


def _hubs() -> set[str]:
    from generate_state_hubs import MIN_RACES, _slugify, group_races_by_state
    return {f"/race/best-gravel-races-{_slugify(state)}/"
            for state, races in group_races_by_state(INDEX).items()
            if len(races) >= MIN_RACES}


def _target_exists(target: str, hubs: set[str]) -> bool:
    if target.startswith("https://roadielabs.com/"):
        return True
    if target in {"/race/calendar/", "/gravel-races/"} or target in hubs:
        return True
    parts = target.strip("/").split("/")
    if len(parts) == 3 and parts[:2] == ["race", "series"]:
        return (ROOT / "series-data" / f"{parts[2]}.json").exists()
    return len(parts) == 2 and parts[0] == "race" and parts[1] in LIVE


def _live_paths() -> list[str]:
    from generate_vs_pages import select_pairs
    from season import season_year
    paths = [p for s in LIVE for p in (
        f"race/{s}/", f"race/{s}.md", f"race/{s}/prep-kit/",
        f"race/{s}/training-plan/", f"race/{s}/tires/")]
    paths += [f"race/{a}-vs-{b}/" for a, b in select_pairs(INDEX)]
    paths += [h.lstrip("/") for h in _hubs()]
    paths += [f"race/{a}/prep-kit/" for a in rr.published_slugs() - LIVE]
    paths += [f"race/calendar/{season_year()}/",
              f"race/power-rankings-{season_year()}/", "race/methodology/",
              "race/series/", "race/quiz/", "race/tier-1/"]
    return paths


class TestTombstones:
    def test_no_tombstone_is_a_live_race(self):
        assert not set(TOMBSTONES) & LIVE

    @pytest.mark.parametrize("slug", sorted(TOMBSTONES))
    def test_page_goes_where_the_tombstone_says(self, slug):
        rule = rr.first_match(RULES, f"race/{slug}/")
        assert rule is not None, f"/race/{slug}/ has no redirect"
        assert rule.permanent and rule.target == TOMBSTONES[slug], (
            f"/race/{slug}/ goes to {rule.target}, tombstone says {TOMBSTONES[slug]}")

    def test_every_tombstone_target_exists(self):
        hubs = _hubs()
        dead = {s: t for s, t in TOMBSTONES.items() if not _target_exists(t, hubs)}
        assert not dead, f"tombstones redirect to pages that don't exist: {dead}"


class TestRetiredUrls:
    def test_every_url_of_a_retired_race_redirects(self):
        missing = []
        for slug in RETIRED:
            for path in rr.retired_paths(slug):
                rule = rr.first_match(RULES, path)
                if rule is None or not rule.permanent:
                    missing.append("/" + path)
        assert not missing, f"{len(missing)} retired URLs still serve: {missing[:20]}"

    @pytest.mark.parametrize("path", LIVE_ON_2026_11_06)
    def test_urls_found_live_on_2026_11_06_now_redirect(self, path):
        rule = rr.first_match(RULES, path)
        assert rule is not None and rule.permanent, f"/{path} still serves"

    def test_no_live_page_is_caught(self):
        caught = [p for p in _live_paths() if rr.first_match(GENERATED_RULES, p)]
        assert not caught, f"generated retired-race rules catch live pages: {caught[:20]}"

    def test_generated_section_comes_before_the_fallbacks(self):
        assert (REDIRECT_BLOCK.index(rr.SECTION_END)
                < REDIRECT_BLOCK.index("# Dead-reference self-healing"))

    def test_lines_stay_under_the_apache_limit(self):
        assert max(map(len, RETIRED_RACE_REDIRECT_SECTION.splitlines())) < 8000


class TestGenerator:
    def test_a_tombstone_alone_retires_every_url(self):
        section = rr.generate_section("", {"made-up-race": "/race/calendar/"}, set())
        rules = rr.unconditional_rules(section)
        assert rr.first_match(rules, "race/made-up-race/").target == "/race/calendar/"
        for path in rr.retired_paths("made-up-race")[1:]:
            assert rr.first_match(rules, path).target == "/race/$1/", path

    def test_a_hand_written_page_rule_is_not_repeated(self):
        block = "RewriteRule ^race/made-up-race/?$ /race/calendar/ [R=301,L]\n"
        section = rr.generate_section(block, {"made-up-race": "/race/calendar/"}, set())
        assert "^race/made-up-race/?$" not in section
        assert "made-up-race" in section

    def test_a_live_race_is_never_retired(self):
        block = "RewriteRule ^race/real-race/?$ /race/calendar/ [R=301,L]\n"
        section = rr.generate_section(block, {"real-race": "/race/calendar/"}, {"real-race"})
        assert "real-race" not in section


class TestServerCheck:
    def test_flags_only_unredirected_files_of_races_not_in_race_data(self):
        live = sorted(LIVE)[0]
        listing = "\n".join([
            f"{live}.md", f"{live}/prep-kit",          # live race
            "gun-flint-44.md", "gun-flint-44/prep-kit",  # tombstoned
            "la-marmotte/training-plan",                 # moved to Roadie Labs
            "made-up-race.md", "made-up-race/training-plan",  # deleted, no tombstone
            "assets", "index.html",                      # not race files
        ])
        assert rr.server_orphans(listing, LIVE, RULES) == [
            "/race/made-up-race.md", "/race/made-up-race/training-plan/"]

    def test_retired_legacy_prep_kit_redirects(self):
        # Leads were emailed /race/the-mid-south/prep-kit/. It was kept as a
        # prep-kit alias until 2026-11-09, when the-mid-south was tombstoned
        # (#554): the link now redirects and nothing builds it.
        assert "the-mid-south" not in rr.published_slugs()
        rule = rr.first_match(RULES, "race/the-mid-south/prep-kit/")
        assert rule is not None and rule.permanent
        # One hop to the kit itself, not the race page via /race/the-mid-south/.
        assert rule.target.replace("$1", "prep-kit/") == "/race/mid-south/prep-kit/"
        assert rr.server_orphans(
            "the-mid-south/prep-kit", rr.published_slugs(), RULES) == []
