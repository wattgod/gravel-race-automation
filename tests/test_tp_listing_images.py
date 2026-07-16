"""Tests for scripts/generate_tp_listing_images.py.

Covers: golden-ish render of big-sugar, hash stability given identical
inputs, type-floor + contrast assertions firing on deliberate violations,
pending-state rendering (no synthetic zeros), long-name wrap/overflow rules,
the altitude conditional module tile, and the JPEG decode-check.
"""
import copy
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import generate_tp_listing_images as g


REPO_ROOT = Path(__file__).parent.parent
PLANS_DB = REPO_ROOT.parent / "gravel-god-training-plans" / "db" / "plans.json"

requires_plans_db = pytest.mark.skipif(
    not PLANS_DB.exists(), reason="sibling gravel-god-training-plans/db/plans.json not present"
)


def _rated_race(**overrides):
    race = {
        "slug": "test-race",
        "display_name": "Test Race",
        "vitals": {
            "location": "Testville, TX",
            "distance_mi": 100,
            "date_specific": "2027: June 5",
        },
        "gravel_god_rating": {
            "overall_score": 75,
            "tier_label": "TIER 1",
            "logistics": 4, "length": 4, "technicality": 3, "elevation": 3,
            "climate": 2, "altitude": 1, "adventure": 4,
            "prestige": 4, "race_quality": 4, "experience": 4, "community": 3,
            "field_depth": 4, "value": 3, "expenses": 3,
        },
    }
    race.update(overrides)
    return race


class TestBigSugarGolden:
    """Big Sugar is the P0 golden fixture — real race-data, real plans.json."""

    def test_race_data_loads(self):
        race = g.load_race("big-sugar")
        assert race["slug"] == "big-sugar"
        assert g.rating_state(race) == "rated"

    def test_header_renders(self):
        race = g.load_race("big-sugar")
        img, alt = g.build_header_image(race)
        assert img.mode == "RGB"
        assert img.width == g.HEADER_W
        assert "Big Sugar" in alt
        assert "TIER 1" in alt
        assert "86/100" in alt
        # Alt mirrors both subscore radars, not just the overall number.
        assert "Course Profile" in alt
        assert "Editorial" in alt

    def test_includes_renders_for_finisher(self):
        race = g.load_race("big-sugar")
        plan = {"tier": "Finisher", "length_wk": 12}
        img, alt = g.build_includes_image(race, "finisher", plan, altitude_flag=False)
        assert img.mode == "RGB"
        assert img.width == g.INCLUDES_W
        for _, copy_text in g.STANDARD_TILES:
            assert copy_text in alt

    def test_masters_includes_appends_module_tile(self):
        race = g.load_race("big-sugar")
        plan = {"tier": "Masters 50+", "length_wk": 12}
        img, alt = g.build_includes_image(race, "masters", plan, altitude_flag=False)
        assert "Masters 50+" in alt
        assert g.MODULE_TILES["masters"][1] in alt

    @requires_plans_db
    def test_full_pipeline_generates_golden_set(self, tmp_path):
        manifest = g.load_manifest(tmp_path / "manifest.json")
        entry = g.generate_for_race(
            "big-sugar", plan_classes=["finisher", "masters"],
            output_dir=tmp_path, manifest=manifest,
        )
        assert "header" in entry
        assert "finisher" in entry["plans"]
        assert "masters" in entry["plans"]
        for key in ("header",):
            p = tmp_path / entry[key]["file"]
            assert p.exists()
            with Image.open(p) as im:
                im.load()
        for pc, rec in entry["plans"].items():
            p = tmp_path / rec["file"]
            assert p.exists()
            with Image.open(p) as im:
                im.load()


class TestHashStability:
    def test_header_bytes_stable_across_runs(self, tmp_path):
        race = g.load_race("big-sugar")
        img1, _ = g.build_header_image(race)
        img2, _ = g.build_header_image(race)
        p1 = g.save_and_hash(img1, tmp_path, "a")
        p2 = g.save_and_hash(img2, tmp_path, "b")
        assert p1.read_bytes() == p2.read_bytes()

    def test_includes_bytes_stable_across_runs(self, tmp_path):
        race = g.load_race("big-sugar")
        plan = {"tier": "Finisher", "length_wk": 12}
        img1, _ = g.build_includes_image(race, "finisher", plan, False)
        img2, _ = g.build_includes_image(race, "finisher", plan, False)
        p1 = g.save_and_hash(img1, tmp_path, "a")
        p2 = g.save_and_hash(img2, tmp_path, "b")
        assert p1.read_bytes() == p2.read_bytes()

    def test_filename_embeds_hash_of_its_own_bytes(self, tmp_path):
        race = g.load_race("big-sugar")
        img, _ = g.build_header_image(race)
        path = g.save_and_hash(img, tmp_path, "big-sugar-header")
        import hashlib
        expected = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
        assert path.name == f"big-sugar-header-{expected}.jpg"


class TestContrastAndTypeFloor:
    def test_paper_on_gold_fails_aa(self):
        """The prototype's visual paper-on-gold tier chip fails AA; this is
        exactly why the generator must use dark text on gold instead."""
        with pytest.raises(g.ContrastError):
            g.assert_contrast(g.PAPER, g.GOLD, 32, True, "paper on gold")

    def test_dark_on_gold_passes_aa(self):
        ratio = g.assert_contrast(g.DARK_BROWN, g.GOLD, 32, True, "dark on gold")
        assert ratio >= 4.5

    def test_small_normal_text_fails_without_large_text_exemption(self):
        with pytest.raises(g.ContrastError):
            g.assert_contrast(g.GOLD_DEEP, g.PAPER, 14, False, "small normal text")

    def test_same_pair_passes_at_large_bold_size(self):
        # gold-deep on paper is ~3.4:1 — fails 4.5 (normal) but clears 3.0
        # (large: >=19px bold).
        ratio = g.assert_contrast(g.GOLD_DEEP, g.PAPER, 32, True, "large bold text")
        assert ratio >= 3.0

    def test_type_floor_fires_below_32px(self):
        with pytest.raises(g.TypeFloorError):
            g.assert_type_floor(16, "test violation")

    def test_type_floor_passes_at_32px(self):
        g.assert_type_floor(32, "test ok")  # should not raise

    def test_type_floor_skipped_for_non_meaningful_text(self):
        g.assert_type_floor(10, "decorative", meaningful=False)  # should not raise


class TestPendingState:
    def test_rating_state_pending_when_no_rating(self):
        race = {"slug": "unrated-race", "vitals": {}}
        assert g.rating_state(race) == "pending"

    def test_partial_subscores_raise_not_zero_fill(self):
        race = _rated_race()
        del race["gravel_god_rating"]["climate"]
        with pytest.raises(g.DataIntegrityError):
            g.rating_state(race)

    def test_pending_header_has_no_score_or_radar(self):
        race = {
            "slug": "unrated-race",
            "display_name": "Unrated Race",
            "vitals": {"location": "Nowhere, USA", "distance_mi": 50, "date_specific": "2027: June 1"},
        }
        img, alt = g.build_header_image(race)
        assert "not yet rated" in alt.lower()
        assert "/100" not in alt


class TestLongNameWrap:
    def test_unwrappable_name_raises(self):
        race = _rated_race(
            display_name="The Extraordinarily Long Winded Gravel Championship of the Whole Entire Wide World"
        )
        with pytest.raises(g.NameOverflowError):
            g.build_header_image(race)

    def test_two_line_name_wraps_without_error(self):
        race = _rated_race(display_name="Pisgah Monster Cross Gravel Grinder Classic")
        img, alt = g.build_header_image(race)
        assert img.width == g.HEADER_W

    def test_short_name_renders_single_line(self):
        race = _rated_race(display_name="Big Sugar Gravel")
        img, alt = g.build_header_image(race)
        assert "Big Sugar Gravel" in alt


class TestAltitudeModule:
    def test_altitude_flag_true_above_threshold(self):
        race = {"vitals": {"start_elevation_asl_ft": 10200, "avg_elevation_asl_ft": 11000}}
        assert g.check_altitude_flag(race) is True

    def test_altitude_flag_false_below_threshold(self):
        race = {"vitals": {"start_elevation_asl_ft": 1300, "avg_elevation_asl_ft": 1300}}
        assert g.check_altitude_flag(race) is False

    def test_altitude_flag_false_when_absent(self):
        race = {"vitals": {}}
        assert g.check_altitude_flag(race) is False

    def test_altitude_tile_appears_for_high_elevation_fixture(self):
        race = g.load_race("leadville-100")
        assert g.check_altitude_flag(race) is True
        plan = {"tier": "Finisher", "length_wk": 12}
        img, alt = g.build_includes_image(race, "finisher", plan, altitude_flag=True)
        assert g.MODULE_TILES["altitude"][1] in alt

    def test_altitude_tile_absent_for_low_elevation_fixture(self):
        race = g.load_race("big-sugar")
        assert g.check_altitude_flag(race) is False
        plan = {"tier": "Finisher", "length_wk": 12}
        img, alt = g.build_includes_image(race, "finisher", plan, altitude_flag=False)
        assert g.MODULE_TILES["altitude"][1] not in alt


class TestDecodeCheck:
    def test_saved_jpeg_decodes(self, tmp_path):
        race = g.load_race("big-sugar")
        img, _ = g.build_header_image(race)
        path = g.save_and_hash(img, tmp_path, "decode-check")
        with Image.open(path) as im:
            im.load()
            assert im.size == img.size

    def test_decode_check_runs_for_includes_too(self, tmp_path):
        race = g.load_race("big-sugar")
        plan = {"tier": "Finisher", "length_wk": 12}
        img, _ = g.build_includes_image(race, "finisher", plan, False)
        path = g.save_and_hash(img, tmp_path, "decode-check-includes")
        with Image.open(path) as im:
            im.load()


class TestPlansDbHelpers:
    @requires_plans_db
    def test_ladder_excludes_self_from_siblings_and_marks_it(self):
        all_plans = g.load_plans_db(PLANS_DB)
        race_plans = g.plans_for_race(all_plans, "big-sugar")
        self_plan = next(p for p in race_plans if p["tier"] == "Finisher" and p["length_wk"] == 12)
        rows = g.build_ladder(race_plans, self_plan)
        assert rows[0]["is_self"] is True
        assert rows[0]["marketplace_url"] is None
        sibling_titles = [r["title"] for r in rows[1:]]
        assert self_plan["title"] not in sibling_titles

    @requires_plans_db
    def test_plan_class_slugs(self):
        all_plans = g.load_plans_db(PLANS_DB)
        race_plans = g.plans_for_race(all_plans, "big-sugar")
        classes = {g.plan_class_of(p) for p in race_plans}
        assert classes == {"finisher", "masters", "compete", "time-crunched", "save-my-race"}


class TestLogoRasterization:
    def test_logo_rasterizes_to_nonempty_silhouette(self):
        logo = g.rasterize_logo(g.DARK_BROWN, target_h=88)
        assert logo.mode == "RGBA"
        assert logo.height == 88
        alpha = logo.split()[-1]
        # At least some pixels must be opaque (the logo actually drew ink).
        assert alpha.getextrema()[1] > 0

    def test_logo_raster_is_cached(self):
        logo1 = g.rasterize_logo(g.DARK_BROWN, target_h=88)
        logo2 = g.rasterize_logo(g.DARK_BROWN, target_h=88)
        assert logo1 is logo2
