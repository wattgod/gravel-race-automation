"""Tests for the deploy-parity detector (WS3, 2026-07-22): expected-manifest
rules, SSH inventory parsing, and orphan/undeployed comparison."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import deploy_parity as dp


ROOT = "/home/u/www/gravelgodcycling.com/public_html"


class TestParseInventory:
    def test_normalizes_paths(self):
        out = f"{ROOT}/race/unbound-200/index.html\n{ROOT}/blog/roundup-may-2026/index.html\n"
        assert dp.parse_inventory(out) == {"/race/unbound-200/", "/blog/roundup-may-2026/"}

    def test_nested_subpages(self):
        out = f"{ROOT}/race/unbound-200/tires/index.html\n"
        assert dp.parse_inventory(out) == {"/race/unbound-200/tires/"}

    def test_excludes_assets_and_wp(self):
        out = (f"{ROOT}/wp-content/x/index.html\n"
               f"{ROOT}/assets/fonts/index.html\n"
               f"{ROOT}/ab/index.html\n"
               f"{ROOT}/race/x/index.html\n")
        assert dp.parse_inventory(out) == {"/race/x/"}

    def test_malformed_lines_ignored(self):
        out = "garbage\n\nnot-a-path index.html\n/etc/passwd\n"
        assert dp.parse_inventory(out) == set()


class TestCompare:
    EXPECTED = {
        "race": {"/race/a/", "/race/b/"},
        "race-tires": {"/race/a/tires/"},
        "blog": {"/blog/roundup-may-2026/"},
    }

    def test_clean_parity(self):
        live = {"/race/a/", "/race/b/", "/race/a/tires/", "/blog/roundup-may-2026/"}
        r = dp.compare(self.EXPECTED, live)
        assert r["orphans"] == [] and r["undeployed"] == []

    def test_orphan_detected_with_section(self):
        live = {"/race/a/", "/race/b/", "/race/a/tires/", "/blog/roundup-may-2026/",
                "/race/stale-race/", "/race/b/tires/", "/blog/old-preview/"}
        r = dp.compare(self.EXPECTED, live)
        got = {(o["section"], o["path"]) for o in r["orphans"]}
        assert ("race", "/race/stale-race/") in got
        assert ("race-tires", "/race/b/tires/") in got
        assert ("blog", "/blog/old-preview/") in got

    def test_undeployed_detected(self):
        live = {"/race/a/", "/race/a/tires/", "/blog/roundup-may-2026/"}
        r = dp.compare(self.EXPECTED, live)
        assert r["undeployed"] == [{"section": "race", "path": "/race/b/"}]

    def test_static_registry_never_orphan(self):
        live = {"/race/a/", "/race/b/", "/race/a/tires/", "/blog/roundup-may-2026/",
                "/gravel-races/", "/race/methodology/"}
        r = dp.compare(self.EXPECTED, live)
        assert r["orphans"] == []

    def test_uncovered_sections_never_orphan(self):
        live = {"/race/a/", "/race/b/", "/race/a/tires/", "/blog/roundup-may-2026/",
                "/race/calendar/2026/", "/race/tier-1/"}
        r = dp.compare(self.EXPECTED, live)
        assert r["orphans"] == []


class TestExpectedRules:
    """The manifest must agree with data and generated output at HEAD."""

    @pytest.fixture(scope="class")
    def expected(self):
        return dp.expected_pages()

    def test_race_count_matches_data(self, expected):
        n = len([p for p in (PROJECT_ROOT / "race-data").glob("*.json")
                 if p.stem != "_schema"])
        assert len(expected["race"]) == n

    def test_no_tombstoned_slugs_anywhere(self, expected):
        for section, paths in expected.items():
            for t in dp.TOMBSTONES:
                assert not any(f"/{t}/" in p for p in paths), (section, t)

    def test_tires_matches_generated_output(self, expected):
        gen = {p.stem for p in (PROJECT_ROOT / "wordpress" / "output" / "tires").glob("*.html")}
        if not gen:
            pytest.skip("no local tire output")
        assert {p.split("/")[2] for p in expected["race-tires"]} == gen

    def test_blog_rule_matches_generator_output(self, expected):
        gen = {f"/blog/{p.stem}/" for p in
               (PROJECT_ROOT / "wordpress" / "output" / "blog").glob("roundup-*.html")}
        if not gen:
            pytest.skip("no local roundup output")
        assert expected["blog"] == gen

    def test_race_vs_deterministic_across_calls(self, expected):
        assert expected["race-vs"] == dp.expected_pages()["race-vs"]
