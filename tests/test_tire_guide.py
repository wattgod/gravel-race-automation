#!/usr/bin/env python3
"""
Comprehensive tests for the Tire Guide V2 system.

Tests: database validation, matching algorithm, edge cases, negation handling,
width recommendations, front/rear split, enrichment round-trip, HTML generation.

Usage:
    python -m pytest tests/test_tire_guide.py -v
    python tests/test_tire_guide.py
"""

import json
import sys
import unittest
from pathlib import Path

# Setup imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from generate_tire_guide import (
    load_tire_database,
    load_weather_data,
    build_race_profile,
    get_top_tires,
    get_front_rear_split,
    get_condition_alternatives,
    recommend_width,
    filter_tires,
    score_tire,
    generate_why_text,
    compute_pressure_table,
    parse_terrain_text,
    extract_negated_keywords,
    keyword_present,
    generate_tire_guide_page,
    SURFACE_FAST,
    SURFACE_MIXED,
    SURFACE_TECHNICAL,
    SURFACE_MUDDY,
    SURFACE_WET,
)
from generate_neo_brutalist import normalize_race_data

RACE_DATA_DIR = PROJECT_ROOT / "race-data"


class TestDatabaseValidation(unittest.TestCase):
    """Test that all tires in the database have valid, complete data."""

    def setUp(self):
        self.tires = load_tire_database()

    def test_database_not_empty(self):
        self.assertGreater(len(self.tires), 20, "Should have at least 20 tires")

    def test_required_fields_present(self):
        required = ["id", "name", "brand", "widths_mm", "tread_type",
                     "best_conditions", "worst_conditions", "tubeless_ready",
                     "brr_urls_by_width", "tagline", "strengths", "weaknesses",
                     "msrp_usd", "weight_grams", "puncture_resistance",
                     "wet_traction", "mud_clearance", "recommended_use", "avoid_use"]
        for tire in self.tires:
            for field in required:
                self.assertIn(field, tire,
                              f"Tire '{tire.get('id', '?')}' missing field '{field}'")

    def test_no_removed_fields(self):
        """Verify old subjective fields are gone."""
        removed = ["rolling_resistance", "puncture_protection", "price_range",
                    "scoring_profile"]
        for tire in self.tires:
            for field in removed:
                self.assertNotIn(field, tire,
                                 f"Tire '{tire['id']}' still has removed field '{field}'")

    def test_msrp_positive(self):
        for tire in self.tires:
            self.assertIsInstance(tire["msrp_usd"], (int, float),
                                 f"Tire '{tire['id']}': msrp_usd must be numeric")
            self.assertGreater(tire["msrp_usd"], 0,
                               f"Tire '{tire['id']}': msrp_usd must be > 0")

    def test_weight_grams_valid(self):
        for tire in self.tires:
            wg = tire["weight_grams"]
            self.assertIsInstance(wg, dict,
                                 f"Tire '{tire['id']}': weight_grams must be dict")
            self.assertGreater(len(wg), 0,
                               f"Tire '{tire['id']}': weight_grams must not be empty")
            for width_str, grams in wg.items():
                self.assertIsInstance(grams, (int, float),
                                     f"Tire '{tire['id']}': weight for {width_str}mm must be numeric")
                self.assertGreater(grams, 100,
                                   f"Tire '{tire['id']}': weight {grams}g seems too low")
                self.assertLess(grams, 1000,
                                f"Tire '{tire['id']}': weight {grams}g seems too high")

    def test_crr_watts_valid(self):
        for tire in self.tires:
            crr = tire.get("crr_watts_at_29kmh")
            if crr is None:
                continue  # null is valid (not tested by BRR)
            if isinstance(crr, dict):
                for width_str, watts in crr.items():
                    self.assertIsInstance(watts, (int, float),
                                         f"Tire '{tire['id']}': Crr for {width_str}mm must be numeric")
                    self.assertGreater(watts, 20,
                                       f"Tire '{tire['id']}': Crr {watts}W seems too low")
                    self.assertLess(watts, 60,
                                    f"Tire '{tire['id']}': Crr {watts}W seems too high")

    def test_puncture_resistance_valid(self):
        valid = {"low", "moderate", "high"}
        for tire in self.tires:
            self.assertIn(tire["puncture_resistance"], valid,
                          f"Tire '{tire['id']}': invalid puncture_resistance")

    def test_wet_traction_valid(self):
        valid = {"poor", "fair", "good"}
        for tire in self.tires:
            self.assertIn(tire["wet_traction"], valid,
                          f"Tire '{tire['id']}': invalid wet_traction")

    def test_mud_clearance_valid(self):
        valid = {"none", "low", "moderate", "high"}
        for tire in self.tires:
            self.assertIn(tire["mud_clearance"], valid,
                          f"Tire '{tire['id']}': invalid mud_clearance")

    def test_tread_type_valid(self):
        valid = {"file", "knobby", "aggressive", "mud"}
        for tire in self.tires:
            self.assertIn(tire["tread_type"], valid,
                          f"Tire '{tire['id']}': invalid tread_type '{tire['tread_type']}'")

    def test_unique_ids(self):
        ids = [t["id"] for t in self.tires]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate tire IDs found")

    def test_widths_mm_not_empty(self):
        for tire in self.tires:
            self.assertGreater(len(tire["widths_mm"]), 0,
                               f"Tire '{tire['id']}': widths_mm must not be empty")

    def test_recommended_use_not_empty(self):
        for tire in self.tires:
            self.assertGreater(len(tire["recommended_use"]), 0,
                               f"Tire '{tire['id']}': recommended_use must not be empty")


class TestMatchingAlgorithm(unittest.TestCase):
    """Test that known races get appropriate tire categories."""

    def setUp(self):
        self.tires = load_tire_database()
        self.tire_index = {t["id"]: t for t in self.tires}

    def _load_race(self, slug):
        filepath = RACE_DATA_DIR / f"{slug}.json"
        if not filepath.exists():
            self.skipTest(f"Race data not found: {slug}")
        data = json.loads(filepath.read_text())
        raw = data.get("race", data)
        rd = normalize_race_data(data)
        rd["slug"] = rd.get("slug") or slug
        weather = load_weather_data(slug)
        return rd, raw, weather

    def _get_top_tire(self, slug):
        rd, raw, weather = self._load_race(slug)
        profile = build_race_profile(rd, raw, weather)
        top = get_top_tires(self.tires, profile)
        return top[0]["tire"] if top else None, profile

    def test_muddy_race_gets_mud_tire(self):
        """Rasputitsa (mud race) should get a mud/aggressive tire."""
        tire, profile = self._get_top_tire("rasputitsa")
        self.assertIsNotNone(tire)
        self.assertEqual(profile["surface_category"], SURFACE_MUDDY)
        self.assertIn(tire["tread_type"], ("mud", "aggressive"),
                      f"Muddy race got {tire['tread_type']} tire: {tire['name']}")

    def test_smooth_race_gets_fast_tire(self):
        """Steamboat Gravel (smooth) should get an all-rounder or fast tire."""
        tire, profile = self._get_top_tire("steamboat-gravel")
        self.assertIsNotNone(tire)
        # Steamboat is mixed, not pure fast — knobby or file are both acceptable
        self.assertIn(tire["tread_type"], ("file", "knobby"),
                      f"Smooth race got {tire['tread_type']} tire: {tire['name']}")

    def test_chunky_race_gets_puncture_protection(self):
        """Unbound 200 (sharp limestone) should get high puncture resistance."""
        tire, profile = self._get_top_tire("unbound-200")
        self.assertIsNotNone(tire)
        self.assertTrue(profile["needs_puncture"],
                        "Unbound should need puncture protection")
        self.assertEqual(tire["puncture_resistance"], "high",
                         f"Chunky race got {tire['puncture_resistance']} protection: {tire['name']}")

    def test_technical_race_gets_grip(self):
        """Big Sugar (technical) should get aggressive/knobby tire."""
        tire, profile = self._get_top_tire("big-sugar")
        self.assertIsNotNone(tire)
        self.assertIn(tire["tread_type"], ("aggressive", "knobby"),
                      f"Technical race got {tire['tread_type']} tire: {tire['name']}")

    def test_ultra_distance_prioritizes_durability(self):
        """Unbound 200 (200mi) should have needs_comfort=True."""
        _, profile = self._get_top_tire("unbound-200")
        self.assertTrue(profile["needs_comfort"],
                        "200mi race should need comfort/durability")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases in terrain parsing and scoring."""

    def setUp(self):
        self.tires = load_tire_database()

    def test_string_terrain(self):
        """Races with terrain as plain string should not crash."""
        raw = {"terrain": "Rolling gravel roads with sharp limestone",
               "vitals": {"distance_mi": 100, "elevation_ft": 5000}}
        rd = {"slug": "test", "name": "Test Race", "vitals": {"distance_mi": 100}}
        profile = build_race_profile(rd, raw, {})
        top = get_top_tires(self.tires, profile)
        self.assertEqual(len(top), 3)

    def test_dict_surface(self):
        """Races with terrain.surface as dict should not crash."""
        raw = {"terrain": {"surface": {"gravel": 60, "dirt": 40},
                           "technical_rating": 2},
               "vitals": {"distance_mi": 50}}
        rd = {"slug": "test", "name": "Test Race", "vitals": {"distance_mi": 50}}
        profile = build_race_profile(rd, raw, {})
        top = get_top_tires(self.tires, profile)
        self.assertEqual(len(top), 3)

    def test_missing_terrain(self):
        """Races with no terrain data should default to mixed profile."""
        raw = {"vitals": {"distance_mi": 50}}
        rd = {"slug": "test", "name": "Test Race", "vitals": {"distance_mi": 50}}
        profile = build_race_profile(rd, raw, {})
        self.assertEqual(profile["surface_category"], SURFACE_MIXED)
        top = get_top_tires(self.tires, profile)
        self.assertEqual(len(top), 3)

    def test_missing_weather(self):
        """Races with no weather data should not crash."""
        raw = {"terrain": {"technical_rating": 2, "surface": "gravel"},
               "vitals": {"distance_mi": 50}}
        rd = {"slug": "test", "name": "Test Race", "vitals": {"distance_mi": 50}}
        profile = build_race_profile(rd, raw, {})
        self.assertFalse(profile["needs_wet"])  # default precip is low
        top = get_top_tires(self.tires, profile)
        self.assertEqual(len(top), 3)

    def test_no_features(self):
        """Races with no features array should not crash."""
        raw = {"terrain": {"technical_rating": 3, "surface": "Mixed gravel"},
               "vitals": {"distance_mi": 80}}
        rd = {"slug": "test", "name": "Test Race", "vitals": {"distance_mi": 80}}
        profile = build_race_profile(rd, raw, {})
        top = get_top_tires(self.tires, profile)
        self.assertEqual(len(top), 3)

    def test_string_elevation(self):
        """Elevation as string like '4,500-9,116' should not crash."""
        raw = {"terrain": {"technical_rating": 3, "surface": "Mixed"},
               "vitals": {"distance_mi": 70, "elevation_ft": "4,500-9,116"}}
        rd = {"slug": "test", "name": "Test Race", "vitals": {"distance_mi": 70}}
        profile = build_race_profile(rd, raw, {})
        self.assertIsInstance(profile["elevation_ft"], (int, float))

    def test_mtb_crossover_filters_file_tread(self):
        """Tech rating >= 5 should filter out file tread tires."""
        profile = {
            "surface_category": SURFACE_TECHNICAL,
            "tech_rating": 5,
            "distance_mi": 50,
            "elevation_ft": 5000,
            "climbing_ratio": 100,
            "precip_pct": 20,
            "needs_puncture": True,
            "needs_wet": False,
            "needs_mud": False,
            "needs_speed": False,
            "needs_comfort": False,
            "combined_text": "extreme singletrack technical descent",
            "features_list": [],
        }
        filtered = filter_tires(self.tires, profile)
        for tire in filtered:
            self.assertNotEqual(tire["tread_type"], "file",
                                f"File tread tire '{tire['name']}' should be filtered for tech_rating 5")


class TestNegationHandling(unittest.TestCase):
    """Test that negation-aware matching works correctly."""

    def test_no_mud_does_not_boost_mud(self):
        """'no mud sections' should NOT trigger mud demand."""
        negated = extract_negated_keywords("no mud sections on this course")
        self.assertIn("mud", negated)
        self.assertFalse(keyword_present("no mud sections", "mud", negated))

    def test_positive_mud_does_trigger(self):
        """'heavy mud sections' SHOULD trigger mud demand."""
        negated = extract_negated_keywords("heavy mud sections on this course")
        self.assertNotIn("mud", negated)
        self.assertTrue(keyword_present("heavy mud sections", "mud", negated))

    def test_negated_keyword_in_race_profile(self):
        """Race with 'no mud' in terrain should NOT classify as muddy."""
        raw = {"terrain": {"surface": "Dry gravel, no mud sections",
                           "technical_rating": 2},
               "vitals": {"distance_mi": 50}}
        rd = {"slug": "test", "name": "Test Race", "vitals": {"distance_mi": 50}}
        profile = build_race_profile(rd, raw, {})
        self.assertFalse(profile["needs_mud"],
                         "'no mud' terrain should not trigger needs_mud")
        self.assertNotEqual(profile["surface_category"], SURFACE_MUDDY)


class TestWidthRecommendations(unittest.TestCase):
    """Test width recommendation logic."""

    def setUp(self):
        self.tires = load_tire_database()

    def test_tech_rating_1_targets_38mm(self):
        tire = {"widths_mm": [35, 38, 40, 45]}
        self.assertEqual(recommend_width(1, tire), 38)

    def test_tech_rating_2_targets_40mm(self):
        tire = {"widths_mm": [35, 40, 45]}
        self.assertEqual(recommend_width(2, tire), 40)

    def test_tech_rating_3_targets_42mm(self):
        tire = {"widths_mm": [38, 42, 47]}
        self.assertEqual(recommend_width(3, tire), 42)

    def test_tech_rating_4_targets_45mm(self):
        tire = {"widths_mm": [40, 45, 50]}
        self.assertEqual(recommend_width(4, tire), 45)

    def test_closest_available_when_target_missing(self):
        """If target width not available, pick closest."""
        tire = {"widths_mm": [38, 47]}
        # tech_rating 3 targets 42, closest available is 38 or 47
        result = recommend_width(3, tire)
        self.assertIn(result, [38, 47])

    def test_single_width_tire(self):
        """Tire with only one width should return that width."""
        tire = {"widths_mm": [44]}
        self.assertEqual(recommend_width(1, tire), 44)
        self.assertEqual(recommend_width(5, tire), 44)


class TestFrontRearSplit(unittest.TestCase):
    """Test front/rear split logic."""

    def setUp(self):
        self.tires = load_tire_database()

    def _make_profile(self, tech_rating):
        return {
            "surface_category": SURFACE_MIXED,
            "tech_rating": tech_rating,
            "distance_mi": 100,
            "elevation_ft": 5000,
            "climbing_ratio": 50,
            "precip_pct": 20,
            "needs_puncture": False,
            "needs_wet": False,
            "needs_mud": False,
            "needs_speed": True,
            "needs_comfort": True,
            "combined_text": "mixed gravel with rolling hills",
            "features_list": [],
        }

    def test_split_applicable_for_tech_2_3(self):
        """Tech rating 2-3 should get front/rear split."""
        for tr in (2, 3):
            profile = self._make_profile(tr)
            top = get_top_tires(self.tires, profile)
            split = get_front_rear_split(self.tires, profile, top)
            self.assertTrue(split["applicable"],
                            f"Split should be applicable for tech_rating {tr}")

    def test_no_split_for_tech_1(self):
        """Tech rating 1 (smooth) should NOT get split."""
        profile = self._make_profile(1)
        top = get_top_tires(self.tires, profile)
        split = get_front_rear_split(self.tires, profile, top)
        self.assertFalse(split["applicable"])

    def test_no_split_for_tech_4_plus(self):
        """Tech rating 4+ (very technical) should NOT get split."""
        profile = self._make_profile(4)
        top = get_top_tires(self.tires, profile)
        split = get_front_rear_split(self.tires, profile, top)
        self.assertFalse(split["applicable"])

    def test_split_has_different_tires(self):
        """Front and rear tires should be different."""
        profile = self._make_profile(2)
        top = get_top_tires(self.tires, profile)
        split = get_front_rear_split(self.tires, profile, top)
        if split["applicable"]:
            self.assertNotEqual(split["front"]["tire_id"],
                                split["rear"]["tire_id"])


class TestEnrichmentRoundTrip(unittest.TestCase):
    """Test that enrichment data can be written and read back correctly."""

    def test_enrichment_round_trip(self):
        """Write tire_recommendations to JSON, read back, verify data intact."""
        # Import enrichment function
        from enrich_tire_recommendations import build_enrichment, load_race_file

        tire_db = load_tire_database()
        filepath = RACE_DATA_DIR / "unbound-200.json"
        if not filepath.exists():
            self.skipTest("unbound-200.json not found")

        data, raw_race, is_nested = load_race_file(filepath)
        rd = normalize_race_data(data)
        rd["slug"] = "unbound-200"

        enrichment = build_enrichment(rd, raw_race, tire_db, "unbound-200")

        # Verify structure
        self.assertIn("generated_at", enrichment)
        self.assertIn("primary", enrichment)
        self.assertIn("front_rear_split", enrichment)
        self.assertIn("race_surface_profile", enrichment)
        self.assertIn("recommended_width_mm", enrichment)
        self.assertIn("pressure_psi", enrichment)

        # Verify primary has 3 picks
        self.assertEqual(len(enrichment["primary"]), 3)
        for rec in enrichment["primary"]:
            self.assertIn("rank", rec)
            self.assertIn("tire_id", rec)
            self.assertIn("name", rec)
            self.assertIn("brand", rec)
            self.assertIn("recommended_width_mm", rec)
            self.assertIn("msrp_usd", rec)
            self.assertIn("why", rec)
            self.assertIsNotNone(rec["msrp_usd"])
            self.assertGreater(rec["msrp_usd"], 0)

        # Verify JSON round-trip
        json_str = json.dumps(enrichment)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["primary"][0]["tire_id"],
                         enrichment["primary"][0]["tire_id"])


class TestHTMLGeneration(unittest.TestCase):
    """Test that generated HTML contains expected elements."""

    def setUp(self):
        self.tires = load_tire_database()

    def test_standalone_html_contains_tire_names(self):
        """Generated tire guide page should contain tire names and prices."""
        filepath = RACE_DATA_DIR / "unbound-200.json"
        if not filepath.exists():
            self.skipTest("unbound-200.json not found")

        data = json.loads(filepath.read_text())
        raw = data.get("race", data)
        rd = normalize_race_data(data)
        rd["slug"] = "unbound-200"
        weather = load_weather_data("unbound-200")

        html = generate_tire_guide_page(rd, raw, weather, self.tires)

        # Should contain at least one tire name
        self.assertIn("tg-tire-name", html)
        # Should contain real prices
        self.assertIn("$", html)
        # Should contain Crr watts
        self.assertIn("@ 29km/h", html)
        # Should contain weight in grams
        self.assertRegex(html, r'\d+g')
        # Should contain pressure table
        self.assertIn("tg-pressure-table", html)
        # Should contain BRR link
        self.assertIn("bicyclerollingresistance.com", html)
        # Should contain front/rear split section
        self.assertIn("FRONT / REAR SPLIT", html)
        # Should contain rim width caveat
        self.assertIn("21-25mm internal width rims", html)

    def test_standalone_html_has_valid_structure(self):
        """Generated page should be valid HTML structure."""
        filepath = RACE_DATA_DIR / "steamboat-gravel.json"
        if not filepath.exists():
            self.skipTest("steamboat-gravel.json not found")

        data = json.loads(filepath.read_text())
        raw = data.get("race", data)
        rd = normalize_race_data(data)
        rd["slug"] = "steamboat-gravel"
        weather = load_weather_data("steamboat-gravel")

        html = generate_tire_guide_page(rd, raw, weather, self.tires)

        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("</html>", html)
        self.assertIn("<title>", html)
        self.assertIn("Tire Guide", html)

    def test_all_races_generate_without_error(self):
        """All race JSONs should generate tire guides without error."""
        files = sorted(RACE_DATA_DIR.glob("*.json"))
        self.assertGreater(len(files), 300, "Should have 300+ race files")

        errors = []
        for filepath in files:
            try:
                data = json.loads(filepath.read_text())
                raw = data.get("race", data)
                rd = normalize_race_data(data)
                rd["slug"] = rd.get("slug") or filepath.stem
                weather = load_weather_data(filepath.stem)
                html = generate_tire_guide_page(rd, raw, weather, self.tires)
                self.assertIn("tg-tire-name", html)
            except Exception as e:
                errors.append(f"{filepath.stem}: {e}")

        self.assertEqual(len(errors), 0,
                         f"{len(errors)} races failed:\n" + "\n".join(errors[:5]))


class TestWhyText(unittest.TestCase):
    """Test that 'Why This Tire' text references real data."""

    def setUp(self):
        self.tires = load_tire_database()
        self.tire_index = {t["id"]: t for t in self.tires}

    def test_why_text_includes_crr(self):
        """Tires with Crr data should mention it in why text."""
        tire = self.tire_index["continental-terra-speed-40"]
        profile = {
            "surface_category": SURFACE_FAST,
            "needs_puncture": False,
            "needs_wet": False,
            "needs_mud": False,
            "needs_speed": True,
            "needs_comfort": False,
            "combined_text": "smooth gravel roads",
        }
        text = generate_why_text(tire, profile, "Test Race")
        self.assertIn("28.5W", text, "Should reference actual Crr watts")

    def test_why_text_includes_price(self):
        """Why text should mention real MSRP."""
        tire = self.tire_index["specialized-pathfinder-pro"]
        profile = {
            "surface_category": SURFACE_MIXED,
            "needs_puncture": False,
            "needs_wet": False,
            "needs_mud": False,
            "needs_speed": False,
            "needs_comfort": False,
            "combined_text": "mixed gravel",
        }
        text = generate_why_text(tire, profile, "Test Race")
        self.assertIn("$54.99", text, "Should reference actual MSRP")

    def test_why_text_includes_weight(self):
        """Why text should mention weight in grams."""
        tire = self.tire_index["continental-terra-speed-40"]
        profile = {
            "surface_category": SURFACE_FAST,
            "needs_puncture": False,
            "needs_wet": False,
            "needs_mud": False,
            "needs_speed": True,
            "needs_comfort": False,
            "combined_text": "smooth gravel",
        }
        text = generate_why_text(tire, profile, "Test Race")
        self.assertRegex(text, r'\d+g per tire', "Should reference weight in grams")


class TestConditionAlternatives(unittest.TestCase):
    """Test Plan B tire recommendations."""

    def setUp(self):
        self.tires = load_tire_database()

    def test_wet_alt_only_when_primary_weak(self):
        """Wet alternative should only appear if primary has poor/fair wet traction."""
        profile = {
            "surface_category": SURFACE_FAST,
            "tech_rating": 1,
            "distance_mi": 50,
            "elevation_ft": 1000,
            "climbing_ratio": 20,
            "precip_pct": 20,
            "needs_puncture": False,
            "needs_wet": False,
            "needs_mud": False,
            "needs_speed": True,
            "needs_comfort": False,
            "combined_text": "smooth fast gravel",
            "features_list": [],
        }
        top = get_top_tires(self.tires, profile)
        alts = get_condition_alternatives(self.tires, profile, top)

        # Primary is likely a file tread with poor wet traction
        primary_wet = top[0]["tire"].get("wet_traction", "fair")
        if primary_wet in ("poor", "fair"):
            self.assertIsNotNone(alts["wet"],
                                 "Should have wet alternative when primary has poor/fair wet grip")
            self.assertEqual(alts["wet"]["tire"]["wet_traction"], "good",
                             "Wet alternative should have good wet traction")

    def test_dry_alt_only_when_primary_conservative(self):
        """Dry alternative should only appear if primary is aggressive/mud."""
        profile = {
            "surface_category": SURFACE_MUDDY,
            "tech_rating": 3,
            "distance_mi": 50,
            "elevation_ft": 2000,
            "climbing_ratio": 40,
            "precip_pct": 60,
            "needs_puncture": False,
            "needs_wet": True,
            "needs_mud": True,
            "needs_speed": False,
            "needs_comfort": False,
            "combined_text": "mud clay wet",
            "features_list": [],
        }
        top = get_top_tires(self.tires, profile)
        alts = get_condition_alternatives(self.tires, profile, top)

        primary_tread = top[0]["tire"].get("tread_type", "knobby")
        if primary_tread in ("mud", "aggressive"):
            self.assertIsNotNone(alts["dry"],
                                 "Should have dry alternative when primary is mud/aggressive")
            self.assertEqual(alts["dry"]["tire"]["tread_type"], "file",
                             "Dry alternative should be file tread")


class TestPressureTable(unittest.TestCase):
    """Test pressure table generation."""

    def test_pressure_values_reasonable(self):
        """Pressure values should be in reasonable range (18-50 psi)."""
        rows = compute_pressure_table(tech_rating=2, rec_width=40)
        self.assertEqual(len(rows), 4, "Should have 4 weight ranges")
        for row in rows:
            for cond in ("dry", "mixed", "wet"):
                val_str = row[cond]
                # Parse range like "35-39"
                parts = val_str.split("-")
                low = int(parts[0])
                high = int(parts[1])
                self.assertGreaterEqual(low, 18, f"Pressure too low: {val_str}")
                self.assertLessEqual(high, 50, f"Pressure too high: {val_str}")
                self.assertLess(low, high, f"Low should be less than high: {val_str}")


class TestScoreTireDirect(unittest.TestCase):
    """Direct tests on score_tire() to verify scoring logic produces correct rankings."""

    def setUp(self):
        self.tires = load_tire_database()
        self.tire_index = {t["id"]: t for t in self.tires}

    def _make_profile(self, surface_category, **overrides):
        profile = {
            "surface_category": surface_category,
            "tech_rating": 2,
            "distance_mi": 60,
            "elevation_ft": 3000,
            "climbing_ratio": 50,
            "precip_pct": 20,
            "needs_puncture": False,
            "needs_wet": False,
            "needs_mud": False,
            "needs_speed": True,
            "needs_comfort": False,
            "combined_text": "mixed gravel roads",
            "features_list": [],
        }
        profile.update(overrides)
        return profile

    def test_mud_tire_scores_highest_for_mud_profile(self):
        """A mud-specific tire should outscore a fast tire on a mud profile."""
        profile = self._make_profile(
            SURFACE_MUDDY,
            needs_mud=True, needs_speed=False, needs_wet=True,
            combined_text="heavy mud clay saturated courses",
        )
        # Vittoria Terreno Wet (mud) vs Continental Terra Speed (fast)
        mud_tire = self.tire_index["vittoria-terreno-wet"]
        fast_tire = self.tire_index["continental-terra-speed-40"]
        mud_score = score_tire(mud_tire, profile)
        fast_score = score_tire(fast_tire, profile)
        self.assertGreater(mud_score, fast_score,
                           f"Mud tire ({mud_score}) should outscore fast tire ({fast_score}) on mud profile")

    def test_fast_tire_scores_highest_for_fast_profile(self):
        """A fast tire should outscore a mud tire on a fast/smooth profile."""
        profile = self._make_profile(
            SURFACE_FAST,
            needs_speed=True, needs_mud=False,
            combined_text="smooth fast gravel dry racing",
        )
        fast_tire = self.tire_index["continental-terra-speed-40"]
        mud_tire = self.tire_index["vittoria-terreno-wet"]
        fast_score = score_tire(fast_tire, profile)
        mud_score = score_tire(mud_tire, profile)
        self.assertGreater(fast_score, mud_score,
                           f"Fast tire ({fast_score}) should outscore mud tire ({mud_score}) on fast profile")

    def test_avoid_use_penalty_reduces_score(self):
        """A tire with matching avoid_use should score lower than one without."""
        profile = self._make_profile(
            SURFACE_MUDDY,
            needs_mud=True, needs_speed=False,
            combined_text="mud clay bog",
        )
        # Find a tire that avoids mud conditions
        for tire in self.tires:
            if any("mud" in a.lower() or "wet" in a.lower() for a in tire.get("avoid_use", [])):
                avoid_score = score_tire(tire, profile)
                # It should have a negative contribution from avoid_use
                # Test that score is lower than a mud-friendly tire
                mud_tire = self.tire_index["vittoria-terreno-wet"]
                mud_score = score_tire(mud_tire, profile)
                self.assertGreater(mud_score, avoid_score,
                                   f"Tire avoiding mud ({tire['id']}: {avoid_score}) "
                                   f"should score lower than mud tire ({mud_score})")
                break

    def test_crr_bonus_applied_when_speed_needed(self):
        """Tires with low CRR should get bonus when needs_speed=True."""
        profile = self._make_profile(
            SURFACE_FAST,
            needs_speed=True,
            combined_text="smooth fast gravel",
        )
        # Continental Terra Speed has CRR 28.5W (low = good)
        fast_tire = self.tire_index["continental-terra-speed-40"]
        score_with_speed = score_tire(fast_tire, profile)

        profile_no_speed = self._make_profile(
            SURFACE_FAST,
            needs_speed=False,
            combined_text="smooth fast gravel",
        )
        score_without_speed = score_tire(fast_tire, profile_no_speed)
        self.assertGreater(score_with_speed, score_without_speed,
                           "CRR bonus should increase score when needs_speed=True")


class TestRankingOrder(unittest.TestCase):
    """Verify that get_top_tires returns tires in descending score order."""

    def setUp(self):
        self.tires = load_tire_database()

    def test_top_tires_descending_score(self):
        """Top picks must be ordered by decreasing score."""
        profiles = [
            {"surface_category": SURFACE_FAST, "tech_rating": 1, "distance_mi": 50,
             "elevation_ft": 1000, "climbing_ratio": 20, "precip_pct": 10,
             "needs_puncture": False, "needs_wet": False, "needs_mud": False,
             "needs_speed": True, "needs_comfort": False,
             "combined_text": "smooth fast gravel", "features_list": []},
            {"surface_category": SURFACE_MUDDY, "tech_rating": 3, "distance_mi": 80,
             "elevation_ft": 4000, "climbing_ratio": 50, "precip_pct": 65,
             "needs_puncture": True, "needs_wet": True, "needs_mud": True,
             "needs_speed": False, "needs_comfort": False,
             "combined_text": "heavy mud clay limestone", "features_list": []},
            {"surface_category": SURFACE_TECHNICAL, "tech_rating": 4, "distance_mi": 120,
             "elevation_ft": 8000, "climbing_ratio": 67, "precip_pct": 30,
             "needs_puncture": True, "needs_wet": False, "needs_mud": False,
             "needs_speed": False, "needs_comfort": True,
             "combined_text": "rocky technical singletrack sharp", "features_list": []},
        ]
        for profile in profiles:
            top = get_top_tires(self.tires, profile)
            self.assertEqual(len(top), 3, f"Should return 3 tires for {profile['surface_category']}")
            self.assertGreaterEqual(top[0]["score"], top[1]["score"],
                                    f"#1 score ({top[0]['score']}) < #2 score ({top[1]['score']}) "
                                    f"for {profile['surface_category']}")
            self.assertGreaterEqual(top[1]["score"], top[2]["score"],
                                    f"#2 score ({top[1]['score']}) < #3 score ({top[2]['score']}) "
                                    f"for {profile['surface_category']}")


class TestEnrichmentHardened(unittest.TestCase):
    """Tightened enrichment tests that verify content, not just existence."""

    def setUp(self):
        self.tires = load_tire_database()
        self.tire_ids = {t["id"] for t in self.tires}
        self.tire_widths = {t["id"]: t["widths_mm"] for t in self.tires}

    def test_enrichment_ranks_are_sequential(self):
        """Primary picks must have rank 1, 2, 3 in order."""
        from enrich_tire_recommendations import build_enrichment, load_race_file

        filepath = RACE_DATA_DIR / "unbound-200.json"
        if not filepath.exists():
            self.skipTest("unbound-200.json not found")

        data, raw_race, is_nested = load_race_file(filepath)
        rd = normalize_race_data(data)
        rd["slug"] = "unbound-200"
        enrichment = build_enrichment(rd, raw_race, self.tires, "unbound-200")

        ranks = [rec["rank"] for rec in enrichment["primary"]]
        self.assertEqual(ranks, [1, 2, 3], f"Ranks should be [1,2,3], got {ranks}")

    def test_enrichment_tire_ids_exist_in_database(self):
        """Every enriched tire_id must exist in the tire database."""
        from enrich_tire_recommendations import build_enrichment, load_race_file

        filepath = RACE_DATA_DIR / "unbound-200.json"
        if not filepath.exists():
            self.skipTest("unbound-200.json not found")

        data, raw_race, is_nested = load_race_file(filepath)
        rd = normalize_race_data(data)
        rd["slug"] = "unbound-200"
        enrichment = build_enrichment(rd, raw_race, self.tires, "unbound-200")

        for rec in enrichment["primary"]:
            self.assertIn(rec["tire_id"], self.tire_ids,
                          f"tire_id '{rec['tire_id']}' not found in tire database")

    def test_enrichment_width_valid_for_tire(self):
        """Recommended width must be one of the tire's available widths."""
        from enrich_tire_recommendations import build_enrichment, load_race_file

        filepath = RACE_DATA_DIR / "unbound-200.json"
        if not filepath.exists():
            self.skipTest("unbound-200.json not found")

        data, raw_race, is_nested = load_race_file(filepath)
        rd = normalize_race_data(data)
        rd["slug"] = "unbound-200"
        enrichment = build_enrichment(rd, raw_race, self.tires, "unbound-200")

        for rec in enrichment["primary"]:
            tid = rec["tire_id"]
            width = rec["recommended_width_mm"]
            self.assertIn(width, self.tire_widths[tid],
                          f"Width {width}mm not in {tid}'s widths {self.tire_widths[tid]}")

    def test_enrichment_why_not_empty(self):
        """Why text must be non-empty for every pick."""
        from enrich_tire_recommendations import build_enrichment, load_race_file

        filepath = RACE_DATA_DIR / "unbound-200.json"
        if not filepath.exists():
            self.skipTest("unbound-200.json not found")

        data, raw_race, is_nested = load_race_file(filepath)
        rd = normalize_race_data(data)
        rd["slug"] = "unbound-200"
        enrichment = build_enrichment(rd, raw_race, self.tires, "unbound-200")

        for rec in enrichment["primary"]:
            self.assertTrue(len(rec["why"]) > 0,
                            f"Why text empty for tire {rec['tire_id']}")


class TestElevationParsing(unittest.TestCase):
    """Verify elevation parsing produces correct numeric values."""

    def test_range_elevation_uses_first_value(self):
        """'4,500-9,116' should parse to 4500 (first value in range)."""
        raw = {"terrain": {"technical_rating": 3, "surface": "Mixed"},
               "vitals": {"distance_mi": 70, "elevation_ft": "4,500-9,116"}}
        rd = {"slug": "test", "name": "Test Race", "vitals": {"distance_mi": 70}}
        profile = build_race_profile(rd, raw, {})
        self.assertEqual(profile["elevation_ft"], 4500,
                         "Should parse first value from range string")

    def test_comma_formatted_elevation(self):
        """'12,000' should parse to 12000."""
        raw = {"terrain": {"technical_rating": 2, "surface": "Gravel"},
               "vitals": {"distance_mi": 100, "elevation_ft": "12,000"}}
        rd = {"slug": "test", "name": "Test Race", "vitals": {"distance_mi": 100}}
        profile = build_race_profile(rd, raw, {})
        self.assertEqual(profile["elevation_ft"], 12000)


class TestFilterFallback(unittest.TestCase):
    """Test behavior when all tires are filtered out."""

    def setUp(self):
        self.tires = load_tire_database()

    def test_extreme_profile_still_returns_3_tires(self):
        """Even with extreme profile that filters most tires, should return 3."""
        profile = {
            "surface_category": SURFACE_MUDDY,
            "tech_rating": 5,
            "distance_mi": 50,
            "elevation_ft": 5000,
            "climbing_ratio": 100,
            "precip_pct": 90,
            "needs_puncture": True,
            "needs_wet": True,
            "needs_mud": True,
            "needs_speed": False,
            "needs_comfort": False,
            "combined_text": "extreme mud bog swamp clay",
            "features_list": [],
        }
        top = get_top_tires(self.tires, profile)
        self.assertEqual(len(top), 3,
                         "Should return 3 tires even with extreme filtering")


class TestWhyTextNullCrr(unittest.TestCase):
    """Test generate_why_text when tire has null CRR data."""

    def setUp(self):
        self.tires = load_tire_database()
        self.tire_index = {t["id"]: t for t in self.tires}

    def test_null_crr_tire_still_generates_why(self):
        """Tire with crr_watts_at_29kmh: null should still produce why text."""
        # Find a tire with null CRR
        null_crr_tire = None
        for t in self.tires:
            if t.get("crr_watts_at_29kmh") is None:
                null_crr_tire = t
                break
        if null_crr_tire is None:
            self.skipTest("No tire with null CRR found")

        profile = {
            "surface_category": SURFACE_MIXED,
            "tech_rating": 2,
            "needs_puncture": False,
            "needs_wet": False,
            "needs_mud": False,
            "needs_speed": False,
            "needs_comfort": False,
            "combined_text": "mixed gravel",
        }
        text = generate_why_text(null_crr_tire, profile, "Test Race")
        self.assertTrue(len(text) > 0, "Should produce non-empty why text even with null CRR")
        self.assertNotIn("None", text, "Should not contain 'None' string in why text")


class TestNegationExpanded(unittest.TestCase):
    """Test expanded negation patterns beyond 'no {word}'."""

    def test_without_mud(self):
        negated = extract_negated_keywords("without mud on this course")
        self.assertIn("mud", negated)

    def test_minimal_mud(self):
        negated = extract_negated_keywords("minimal mud expected this year")
        self.assertIn("mud", negated)

    def test_little_to_no_mud(self):
        negated = extract_negated_keywords("little to no mud on the course")
        self.assertIn("mud", negated)

    def test_no_significant_mud(self):
        negated = extract_negated_keywords("no significant mud sections")
        self.assertIn("mud", negated)


class TestWidthRecommendationsHardened(unittest.TestCase):
    """Tightened width tests with exact expected values."""

    def test_closest_available_picks_nearest(self):
        """When target is 42mm and options are [38, 47], should pick 38 (closer by 1mm)."""
        tire = {"widths_mm": [38, 47]}
        # tech_rating 3 targets 42: |42-38|=4, |42-47|=5 → 38 is closer
        result = recommend_width(3, tire)
        self.assertEqual(result, 38, "38mm is 4mm from target 42, 47mm is 5mm away")

    def test_tech_rating_5_uses_45mm_target(self):
        """Tech ratings above 4 should still target 45mm (clamped)."""
        tire = {"widths_mm": [40, 45, 50]}
        result = recommend_width(5, tire)
        self.assertEqual(result, 45, "Tech rating 5+ should target 45mm")


if __name__ == "__main__":
    unittest.main(verbosity=2)
