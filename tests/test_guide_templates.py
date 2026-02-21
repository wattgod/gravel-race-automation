"""Tests for guide media infographic templates.

Verifies every registered template:
- Imports and has a render() callable
- Returns a PIL Image of the correct dimensions
- Doesn't call apply_brand_border (pipeline adds it)
"""
import importlib
import sys
from pathlib import Path

import pytest
from PIL import Image

# Ensure scripts/ is on the path so media_templates is importable
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from media_templates.base import apply_brand_border  # noqa: E402

# All registered templates and their expected dimensions from the manifest
TEMPLATES = {
    "zone_spectrum": (1200, 600),
    "training_phases": (1600, 500),
    "supercompensation": (1200, 600),
    "pmc_chart": (1600, 600),
    "psych_phases": (1200, 600),
    "bonk_math": (1200, 600),
    "execution_gap": (1200, 600),
    "traffic_light": (1200, 800),
    "tier_distribution": (1200, 400),
    "rider_categories": (1200, 600),
    "gear_grid": (1200, 800),
    "hierarchy_pyramid": (1200, 800),
    "scoring_dimensions": (1200, 800),
    "fueling_timeline": (1200, 500),
    "three_acts": (1200, 600),
    "race_week_countdown": (1600, 600),
}


@pytest.fixture(params=TEMPLATES.keys())
def template_info(request):
    """Yield (module, expected_width, expected_height) for each template."""
    name = request.param
    w, h = TEMPLATES[name]
    mod = importlib.import_module(f"media_templates.{name}")
    return name, mod, w, h


class TestTemplateRender:
    """Verify each template renders to the correct size and type."""

    def test_has_render_function(self, template_info):
        name, mod, _, _ = template_info
        assert hasattr(mod, "render"), f"{name} missing render()"
        assert callable(mod.render), f"{name}.render is not callable"

    def test_returns_pil_image(self, template_info):
        name, mod, w, h = template_info
        img = mod.render(width=w, height=h)
        assert isinstance(img, Image.Image), f"{name}.render() returned {type(img)}, expected Image"

    def test_correct_dimensions(self, template_info):
        name, mod, w, h = template_info
        img = mod.render(width=w, height=h)
        assert img.size == (w, h), f"{name} rendered {img.size}, expected ({w}, {h})"

    def test_rgb_mode(self, template_info):
        name, mod, w, h = template_info
        img = mod.render(width=w, height=h)
        assert img.mode == "RGB", f"{name} mode is {img.mode}, expected RGB"


class TestNoBorderInTemplate:
    """Templates must NOT apply borders — the pipeline adds them."""

    def test_no_double_border(self, template_info):
        """Render at exact size and verify no border was added (image size unchanged)."""
        name, mod, w, h = template_info
        img = mod.render(width=w, height=h)
        # If a template calls apply_brand_border internally, the returned image
        # will be larger than requested (border adds 6px to each dimension)
        assert img.width == w, f"{name} added border: width {img.width} != {w}"
        assert img.height == h, f"{name} added border: height {img.height} != {h}"


class TestScoringDimensionsData:
    """Scoring dimensions should load from race-data/, not hardcode."""

    def test_loads_from_database(self):
        """Verify scoring_dimensions reads from unbound-200.json."""
        mod = importlib.import_module("media_templates.scoring_dimensions")
        course, editorial, overall, tier = mod._load_unbound_scores()
        # Unbound 200 is Tier 1
        assert tier == 1, f"Expected tier 1, got {tier}"
        assert overall == 93, f"Expected overall 93, got {overall}"
        assert len(course) == 7, f"Expected 7 course dims, got {len(course)}"
        assert len(editorial) == 7, f"Expected 7 editorial dims, got {len(editorial)}"
        # All scores should be 1-5
        for name, score in course + editorial:
            assert 1 <= score <= 5, f"{name} score {score} out of range"
