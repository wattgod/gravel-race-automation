"""On-site reviews/testimonials section — training-plan page generator.

Guards: (a) empty testimonials.json renders nothing, (b) verified+consent+
display entries render with every data-derived value esc()'d (XSS), (c)
unverified / no-consent / display:false entries never render. Trust-bearing
per scoring-and-veracity: real testimonials only, honest empty state
otherwise. Fixture entries are used for the populated cases — the real
data/testimonials.json stays empty.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

import generate_training_plan_pages as gtpp
from generate_training_plan_pages import build_reviews, generate_page, load_pack

RACE_DATA = Path(__file__).resolve().parent.parent / "race-data"


@pytest.fixture(scope="module")
def rd():
    d = json.loads((RACE_DATA / "unbound-200.json").read_text())
    race = d.get("race", d)
    race.setdefault("slug", "unbound-200")
    return race


@pytest.fixture(scope="module")
def pack():
    return load_pack("unbound-200")


def _write_testimonials(tmp_path, entries):
    p = tmp_path / "testimonials.json"
    p.write_text(json.dumps({
        "_schema": "gg-testimonials-v1",
        "generated": None,
        "testimonials": entries,
    }), encoding="utf-8")
    return p


def _base_entry(**overrides):
    entry = {
        "id": "unbound-2026-jordans",
        "race_slug": "unbound-200",
        "plan_ref": "Unbound 200 · Finisher · 12wk",
        "tier": "Finisher",
        "athlete_name": "Jordan S.",
        "date": "2026-06",
        "headline": "Still making good decisions at mile 180",
        "body": "The testing week set my zones honestly.",
        "outcome": "First 200-mile finish",
        "source": "tp_review",
        "source_ref": "https://www.trainingpeaks.com/example-review",
        "consent": True,
        "verified_by": "matti",
        "verified_at": "2026-07-13",
        "display": True,
    }
    entry.update(overrides)
    return entry


class TestEmptyState:
    """No testimonials.json content -> no reviews section, anywhere."""

    def test_empty_testimonials_file_renders_nothing(self, rd, tmp_path, monkeypatch):
        path = _write_testimonials(tmp_path, [])
        monkeypatch.setattr(gtpp, "TESTIMONIALS_PATH", path)
        assert build_reviews(rd, "unbound-200") == ""

    def test_missing_testimonials_file_renders_nothing(self, rd, tmp_path, monkeypatch):
        monkeypatch.setattr(gtpp, "TESTIMONIALS_PATH", tmp_path / "does-not-exist.json")
        assert build_reviews(rd, "unbound-200") == ""

    def test_real_data_file_currently_renders_nothing(self, rd):
        """The live data/testimonials.json ships empty — guards against
        accidental fabricated entries slipping into the repo."""
        assert build_reviews(rd, "unbound-200") == ""

    def test_generated_page_has_no_reviews_section_today(self, rd, pack):
        html = generate_page(rd, pack)
        assert 'id="reviews"' not in html


class TestVerifiedEntryRenders:
    def test_matching_verified_entry_renders(self, rd, tmp_path, monkeypatch):
        path = _write_testimonials(tmp_path, [_base_entry()])
        monkeypatch.setattr(gtpp, "TESTIMONIALS_PATH", path)
        html = build_reviews(rd, "unbound-200")
        assert 'id="reviews"' in html
        assert "Jordan S." in html
        assert "Still making good decisions at mile 180" in html
        assert "First 200-mile finish" in html

    def test_values_are_html_escaped(self, rd, tmp_path, monkeypatch):
        entry = _base_entry(
            athlete_name='Jordan <script>alert(1)</script>',
            headline='Tom & Jerry\'s "best" plan',
            body='<img src=x onerror=alert(1)>quote body',
            outcome='PB & first finish <b>ever</b>',
        )
        path = _write_testimonials(tmp_path, [entry])
        monkeypatch.setattr(gtpp, "TESTIMONIALS_PATH", path)
        html = build_reviews(rd, "unbound-200")

        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "<img src=x" not in html
        assert "&lt;img" in html
        assert "Tom &amp; Jerry" in html
        assert "PB &amp; first finish &lt;b&gt;ever&lt;/b&gt;" in html

    def test_wired_into_full_page(self, rd, pack, tmp_path, monkeypatch):
        path = _write_testimonials(tmp_path, [_base_entry()])
        monkeypatch.setattr(gtpp, "TESTIMONIALS_PATH", path)
        html = generate_page(rd, pack)
        assert 'id="reviews"' in html
        assert "Jordan S." in html


class TestGateEnforcement:
    """verified_by AND consent AND display must all be truthy/True."""

    def test_unverified_entry_does_not_render(self, rd, tmp_path, monkeypatch):
        entry = _base_entry(verified_by=None)
        path = _write_testimonials(tmp_path, [entry])
        monkeypatch.setattr(gtpp, "TESTIMONIALS_PATH", path)
        assert build_reviews(rd, "unbound-200") == ""

    def test_verified_by_empty_string_does_not_render(self, rd, tmp_path, monkeypatch):
        entry = _base_entry(verified_by="")
        path = _write_testimonials(tmp_path, [entry])
        monkeypatch.setattr(gtpp, "TESTIMONIALS_PATH", path)
        assert build_reviews(rd, "unbound-200") == ""

    def test_no_consent_does_not_render(self, rd, tmp_path, monkeypatch):
        entry = _base_entry(consent=False)
        path = _write_testimonials(tmp_path, [entry])
        monkeypatch.setattr(gtpp, "TESTIMONIALS_PATH", path)
        assert build_reviews(rd, "unbound-200") == ""

    def test_display_false_does_not_render(self, rd, tmp_path, monkeypatch):
        entry = _base_entry(display=False)
        path = _write_testimonials(tmp_path, [entry])
        monkeypatch.setattr(gtpp, "TESTIMONIALS_PATH", path)
        assert build_reviews(rd, "unbound-200") == ""

    def test_different_race_slug_does_not_render(self, rd, tmp_path, monkeypatch):
        entry = _base_entry(race_slug="some-other-race")
        path = _write_testimonials(tmp_path, [entry])
        monkeypatch.setattr(gtpp, "TESTIMONIALS_PATH", path)
        assert build_reviews(rd, "unbound-200") == ""


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
