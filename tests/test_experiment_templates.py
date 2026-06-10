#!/usr/bin/env python3
"""Tests for experiment_templates.py — validates template structure and selectors."""

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from experiment_templates import (
    TEMPLATES,
    VALID_SELECTORS,
    count_templates,
    get_next_template,
    list_categories,
    validate_selectors,
)

# ── Required fields ──────────────────────────────────────────

REQUIRED_TEMPLATE_FIELDS = {"id", "description", "selector", "pages", "conversion_selector", "variants"}
REQUIRED_VARIANT_FIELDS = {"id", "name", "content"}


class TestTemplateStructure:
    """Every template must have required fields."""

    def _all_templates(self):
        """Yield (category, template) for every template."""
        for category, templates in TEMPLATES.items():
            for template in templates:
                yield category, template

    def test_every_template_has_required_fields(self):
        for category, template in self._all_templates():
            tid = template.get("id", "<missing>")
            missing = REQUIRED_TEMPLATE_FIELDS - set(template.keys())
            assert not missing, (
                f"{category}/{tid} missing fields: {missing}"
            )

    def test_every_variant_has_required_fields(self):
        for category, template in self._all_templates():
            tid = template.get("id", "<missing>")
            for variant in template.get("variants", []):
                vid = variant.get("id", "<missing>")
                missing = REQUIRED_VARIANT_FIELDS - set(variant.keys())
                assert not missing, (
                    f"{category}/{tid}/{vid} missing fields: {missing}"
                )

    def test_every_template_has_at_least_two_variants(self):
        for category, template in self._all_templates():
            tid = template.get("id", "<missing>")
            assert len(template["variants"]) >= 2, (
                f"{category}/{tid} has fewer than 2 variants"
            )

    def test_pages_is_nonempty_list(self):
        for category, template in self._all_templates():
            tid = template.get("id", "<missing>")
            pages = template.get("pages", [])
            assert isinstance(pages, list) and len(pages) > 0, (
                f"{category}/{tid} 'pages' must be a non-empty list"
            )


class TestControlVariant:
    """Every template must have exactly one control variant."""

    def test_exactly_one_control_per_template(self):
        for category, templates in TEMPLATES.items():
            for template in templates:
                tid = template["id"]
                controls = [v for v in template["variants"] if v["id"] == "control"]
                assert len(controls) == 1, (
                    f"{category}/{tid} has {len(controls)} control variant(s), expected 1"
                )


class TestSelectorValidity:
    """All selectors must reference known data-ab attributes."""

    def test_validate_selectors_returns_no_errors(self):
        errors = validate_selectors()
        assert errors == [], (
            f"Selector validation errors:\n" +
            "\n".join(f"  - {e}" for e in errors)
        )

    def test_every_selector_uses_data_ab_format(self):
        for category, templates in TEMPLATES.items():
            for template in templates:
                tid = template["id"]
                sel = template["selector"]
                assert "data-ab='" in sel, (
                    f"{category}/{tid}: selector '{sel}' does not use data-ab format"
                )

    def test_all_valid_selectors_have_pages(self):
        """VALID_SELECTORS registry has page lists for every attribute."""
        for attr, pages in VALID_SELECTORS.items():
            assert isinstance(pages, list) and len(pages) > 0, (
                f"VALID_SELECTORS['{attr}'] must be a non-empty page list"
            )


class TestNoDuplicateIds:
    """No two templates should share the same ID."""

    def test_no_duplicate_template_ids(self):
        all_ids = []
        for category, templates in TEMPLATES.items():
            for template in templates:
                all_ids.append(template["id"])
        duplicates = [tid for tid in all_ids if all_ids.count(tid) > 1]
        assert not duplicates, (
            f"Duplicate template IDs: {set(duplicates)}"
        )

    def test_no_duplicate_variant_ids_within_template(self):
        for category, templates in TEMPLATES.items():
            for template in templates:
                tid = template["id"]
                variant_ids = [v["id"] for v in template["variants"]]
                duplicates = [vid for vid in variant_ids if variant_ids.count(vid) > 1]
                assert not duplicates, (
                    f"{category}/{tid} has duplicate variant IDs: {set(duplicates)}"
                )


class TestGetNextTemplate:
    """get_next_template returns correct template or None."""

    def test_returns_first_when_none_used(self):
        for category in TEMPLATES:
            result = get_next_template(category)
            assert result is not None
            assert result["id"] == TEMPLATES[category][0]["id"]

    def test_skips_used_ids(self):
        for category in TEMPLATES:
            first_id = TEMPLATES[category][0]["id"]
            result = get_next_template(category, used_ids=[first_id])
            if len(TEMPLATES[category]) > 1:
                assert result is not None
                assert result["id"] == TEMPLATES[category][1]["id"]

    def test_returns_none_when_all_used(self):
        for category in TEMPLATES:
            all_ids = [t["id"] for t in TEMPLATES[category]]
            result = get_next_template(category, used_ids=all_ids)
            assert result is None, (
                f"Expected None for {category} when all IDs used, got {result}"
            )

    def test_raises_on_unknown_category(self):
        with pytest.raises(ValueError, match="Unknown category"):
            get_next_template("nonexistent_category")

    def test_empty_used_ids_same_as_none(self):
        for category in TEMPLATES:
            result_none = get_next_template(category, used_ids=None)
            result_empty = get_next_template(category, used_ids=[])
            assert result_none["id"] == result_empty["id"]


class TestHelperFunctions:
    """list_categories and count_templates work correctly."""

    def test_list_categories_returns_sorted(self):
        cats = list_categories()
        assert cats == sorted(cats)
        assert len(cats) == len(TEMPLATES)

    def test_count_templates_matches_actual(self):
        counts = count_templates()
        for cat, count in counts.items():
            assert count == len(TEMPLATES[cat])

    def test_total_template_count(self):
        counts = count_templates()
        total = sum(counts.values())
        actual = sum(len(t) for t in TEMPLATES.values())
        assert total == actual
