"""WS-G contract tests for the bikepacking guide and Ultra shelf."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORDPRESS_DIR = PROJECT_ROOT / "wordpress"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(WORDPRESS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

import generate_guide_cluster as guide_cluster
from generate_guide_cluster import build_cluster_js
from guide_configs import (
    BIKEPACKING_CHAPTER_META,
    BIKEPACKING_GUIDE,
    GRAVEL_GUIDE,
)
from generate_homepage import build_hero
from generate_power_rankings import build_power_rankings_page
from generate_sitemap import generate_sitemap
from slop_rules import check_text
from validate_bikepacking_guide import _customer_copy, validate_content


GRAVEL_BASELINE_SHA256 = {
    "index.html": "d4d2d55463ca25eea6bf2df9eafdb82b89334f59135e1598b7ecd2d582c859ca",
    "what-is-gravel-racing/index.html": "8bc6d10a0a787b11af6381f7f4bd9732cf1d94a30ccce7280f57064f0f10082c",
    "race-selection/index.html": "6451e5e55b4d660b8ae6e18adb65e17623834856877a8add4d168c4c04be8066",
    "training-fundamentals/index.html": "8d184894f3ce4583ecf63aa9d6dd42e450d79886ef0a204350b8c0ae73958cb5",
    "workout-execution/index.html": "255f1ec92ed0f31234e7a799f0822cf224218bb908b939bd73228cfda2aae072",
    "nutrition-fueling/index.html": "002412c98b29495137b5a5e992719f006e679f3c00fc59b15c47f1eee2c01036",
    "mental-training-race-tactics/index.html": "69fa1b6e0b1a6eea50efd6100190db6d080158a3c60f89fe43979238f247fcab",
    "race-week/index.html": "37ae1f9589454ab0ca98a5efb2a43ce6ed8347f6e6e4c45fdae39a17b6f35858",
    "post-race/index.html": "b7c61020740d2fdb6d3c3978fa318e341628903d8120db344bf986effb892726",
    "race-prep-configurator/index.html": "748386d03768b491f98158582c6a58695bcc08851050c15ce4ac691d4cec6ff2",
}


@pytest.fixture(scope="module")
def bikepacking_content():
    return json.loads(BIKEPACKING_GUIDE.content_path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bikepacking_output(tmp_path_factory):
    output = tmp_path_factory.mktemp("bikepacking-guide")
    assert guide_cluster.generate_cluster(output_dir=output, config=BIKEPACKING_GUIDE)
    return output


@pytest.fixture(scope="module")
def bikepacking_pages(bikepacking_output):
    return {
        str(path.relative_to(bikepacking_output)): path.read_text(encoding="utf-8")
        for path in sorted(bikepacking_output.rglob("index.html"))
    }


def _sentences(text: str):
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
        if sentence.strip()
    ]


def _word_count(sentence: str) -> int:
    return len(re.findall(r"\b[\w’'-]+\b", sentence))


def _procedural_copy(content: dict):
    for chapter in content["chapters"]:
        for section in chapter["sections"]:
            for block in section["blocks"]:
                block_type = block["type"]
                if block_type == "accordion":
                    yield from (item["content"] for item in block["items"])
                elif block_type == "process_list":
                    yield from (item["detail"] for item in block["items"])
                elif block_type == "data_table":
                    yield from (cell for row in block["rows"] for cell in row)
                elif block_type == "timeline":
                    yield from (step["content"] for step in block["steps"])
                elif block_type == "knowledge_check":
                    yield block["explanation"]
                    yield from (option["text"] for option in block["options"])


class TestGravelGuideByteParity:
    def test_config_one_matches_origin_main_baseline_byte_for_byte(self, tmp_path):
        """The make-or-break refactor gate: all ten gravel pages stay exact."""
        output = tmp_path / "guide"
        assert guide_cluster.generate_cluster(output_dir=output, config=GRAVEL_GUIDE)

        actual_files = {
            str(path.relative_to(output)) for path in output.rglob("index.html")
        }
        assert actual_files == set(GRAVEL_BASELINE_SHA256)
        for relative_path, expected_hash in GRAVEL_BASELINE_SHA256.items():
            actual_hash = hashlib.sha256(
                (output / relative_path).read_bytes()
            ).hexdigest()
            assert actual_hash == expected_hash, relative_path


class TestBikepackingContentContract:
    def test_schema_and_r1_r2_r4_guards(self):
        assert validate_content() == []

    def test_all_chapter_copy_passes_slop_rules(self, bikepacking_content):
        chapter_copy = "\n".join(
            _customer_copy({"chapters": bikepacking_content["chapters"]})
        )
        assert check_text(chapter_copy) == []

    def test_editorial_sentence_cap(self, bikepacking_content):
        failures = []
        for text in _customer_copy(bikepacking_content):
            for sentence in _sentences(text):
                if _word_count(sentence) > 25:
                    failures.append(sentence)
        assert failures == []

    def test_procedural_ste_length_and_contractions(self, bikepacking_content):
        failures = []
        contractions = re.compile(
            r"\b(can't|don't|doesn't|isn't|won't|you're|it's|shouldn't)\b",
            re.IGNORECASE,
        )
        for text in _procedural_copy(bikepacking_content):
            for sentence in _sentences(text):
                if _word_count(sentence) > 20 or contractions.search(sentence):
                    failures.append(sentence)
        assert failures == []

    def test_chapter_three_opens_with_approved_frame(self, bikepacking_content):
        chapter = bikepacking_content["chapters"][2]
        opening = chapter["sections"][0]["blocks"][0]["content"]
        assert opening.startswith(
            "No one trains for a 90-hour week — not even the winners."
        )

    def test_chapter_three_centers_working_athlete_architecture(
        self, bikepacking_content
    ):
        chapter_text = json.dumps(bikepacking_content["chapters"][2])
        for required in (
            "Commute conversion",
            "Micro-doubles",
            "Dark-hours riding",
            "Indoor density",
            "Utility miles",
            "PTO-designed SIM",
            "VO2",
            "ceiling maintenance",
        ):
            assert required in chapter_text

    def test_race_shelf_scores_match_race_data(self, bikepacking_content):
        rows = bikepacking_content["chapters"][1]["sections"][1]["blocks"][0]["rows"]
        expected = {
            "Tour Divide": "tour-divide",
            "Colorado Trail Race": "colorado-trail-race",
            "Transcontinental Race": "transcontinental-race",
            "Badlands": "badlands",
            "Atlas Mountain Race": "atlas-mountain-race",
        }
        for row in rows:
            slug = expected[row[0]]
            rating = json.loads(
                (PROJECT_ROOT / "race-data" / f"{slug}.json").read_text()
            )["race"]["gravel_god_rating"]
            assert row[2] == f"Tier {rating['tier']} · {rating['overall_score']}"


class TestBikepackingGuideOutput:
    def test_generates_pillar_and_eight_chapters(self, bikepacking_pages):
        assert len(bikepacking_pages) == 9
        assert "index.html" in bikepacking_pages

    def test_gated_chapters_use_worker_first_form_and_honeypot(
        self, bikepacking_content, bikepacking_pages
    ):
        for chapter in bikepacking_content["chapters"]:
            page = bikepacking_pages[f"{chapter['id']}/index.html"]
            if chapter["number"] <= 3:
                assert 'id="gg-cluster-gate-form"' not in page
            else:
                assert 'id="gg-cluster-gate-form"' in page
                assert 'name="website"' in page
                assert 'name="source" value="bikepacking_guide"' in page

    def test_quiet_capture_waits_for_successful_worker_response(self):
        js = build_cluster_js(BIKEPACKING_GUIDE)
        assert 'if(!r.ok)throw new Error("bad status")' in js
        assert ".then(function(){" in js
        assert 'success.style.display="block"' in js
        assert 'errEl.textContent="Something went wrong — please try again."' in js

    def test_ga4_storage_and_fonts_are_isolated(self, bikepacking_pages):
        for page in bikepacking_pages.values():
            assert "gg_bikepacking_guide_unlocked" in page
            assert "bikepacking_guide" in page
            assert "gtag('config'" in page
            assert "@font-face" in page
            assert "Sometype Mono" in page
            assert "Source Serif 4" in page

    def test_only_ultra_shelf_and_coaching_ctas_render(self, bikepacking_pages):
        all_html = "\n".join(bikepacking_pages.values())
        assert "/gravel-races/?discipline=ultra" in all_html
        assert "APPLY FOR COACHING" in all_html
        assert "TRAINING PLANS" not in all_html
        assert "personalized training plan" not in all_html.lower()

    def test_all_chapter_metadata_is_specific(self, bikepacking_content):
        assert set(BIKEPACKING_CHAPTER_META) == {
            chapter["id"] for chapter in bikepacking_content["chapters"]
        }
        assert len({
            meta["description"] for meta in BIKEPACKING_CHAPTER_META.values()
        }) == 8


class TestUltraShelfSurfaces:
    def test_homepage_has_one_combined_shelf_filter(self):
        html = build_hero(
            {"race_count": 370, "region_count": 10, "dimensions": 15},
            [],
        )
        assert html.count("Ultra &amp; Bikepacking") == 1
        assert "discipline=ultra" in html
        assert ">Bikepacking</a>" not in html
        assert ">MTB</a>" not in html

    def test_rankings_filter_combines_bikepacking_and_mtb(self):
        races = [
            {"slug": "g", "name": "Gravel", "discipline": "gravel", "tier": 1, "overall_score": 90},
            {"slug": "b", "name": "Bikepacking", "discipline": "bikepacking", "tier": 1, "overall_score": 89},
            {"slug": "m", "name": "MTB", "discipline": "mtb", "tier": 2, "overall_score": 70},
        ]
        html = build_power_rankings_page(races)
        assert 'data-disc="ultra">Ultra &amp; Bikepacking (2)' in html
        assert "activeDisc === 'ultra'" in html
        assert 'data-disc="bikepacking"' not in html
        assert 'data-disc="mtb"' not in html

    def test_search_uses_combined_shelf_filter(self):
        widget = (PROJECT_ROOT / "web" / "gravel-race-search.html").read_text()
        script = (PROJECT_ROOT / "web" / "gravel-race-search.js").read_text()
        assert '<option value="ultra">Ultra &amp; Bikepacking</option>' in widget
        assert "discipline === 'bikepacking' || discipline === 'mtb'" in script
        assert "['ultra', 'Ultra & Bikepacking']" in script


class TestDeployAndDiscoveryCoverage:
    def test_sitemap_contains_all_nine_bikepacking_guide_pages(self, tmp_path):
        output = tmp_path / "web" / "sitemap.xml"
        generate_sitemap([], output)
        root = ET.parse(output).getroot()
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locations = {node.text for node in root.findall("s:url/s:loc", ns)}
        expected = {"https://gravelgodcycling.com/bikepacking-guide/"}
        expected.update(
            f"https://gravelgodcycling.com/bikepacking-guide/{slug}/"
            for slug in BIKEPACKING_CHAPTER_META
        )
        assert expected <= locations

    def test_sync_and_live_validation_surfaces_are_declared(self):
        push_source = (SCRIPTS_DIR / "push_wordpress.py").read_text()
        validation_source = (SCRIPTS_DIR / "validate_deploy.py").read_text()
        assert "--sync-bikepacking-guide" in push_source
        assert '"bikepacking-guide"' in push_source
        for slug in BIKEPACKING_CHAPTER_META:
            assert f"/bikepacking-guide/{slug}/" in validation_source

    def test_robots_and_llms_generators_mention_guide(self):
        robots = (PROJECT_ROOT / "web" / "robots.txt").read_text()
        llms_source = (SCRIPTS_DIR / "generate_llms_txt.py").read_text()
        assert "Allow: /bikepacking-guide/" in robots
        assert "[Complete Bikepacking Race Training Guide]" in llms_source
