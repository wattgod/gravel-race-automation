"""Offline rendered-fact release gate tests."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import prep_kit_fact_gate as gate  # noqa: E402
import push_wordpress as pw  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _page(*, distance="70 mi", elevation="7,800 ft", conditions="Dry and warm",
          course="Long exposed climb", historical=False, css="") -> str:
    label = "<p>Historical course information.</p>" if historical else ""
    return f"""<html><style>{css}</style><div class=\"gg-pk-context-box\">
<p><strong>Distance:</strong> {distance}</p>
<p><strong>Elevation:</strong> {elevation}</p>
<p><strong>Conditions:</strong> {conditions}</p>
<p><strong>Signature Challenge:</strong> {course}</p>{label}</div></html>"""


def _source(root: Path, text="Official Fuego XL is 66 mi with 7,800 ft."):
    capture = root / "captures" / "official.txt"
    capture.parent.mkdir(parents=True, exist_ok=True)
    capture.write_text(text)
    return capture


def _review(field, proposed, capture, *, author="author-a", reviewer="reviewer-b",
            outcome="accepted", status="current", variant=None, pair=None, historical_label=None):
    entry = {
        "field": field,
        "proposed_value": proposed,
        "source": {
            "url": "https://organizer.example/fuego",
            "capture": str(capture.relative_to(capture.parents[1])),
            "sha256": _sha(capture),
            "excerpt": "Official course announcement for the selected edition.",
        },
        "edition_or_status": status,
        "author": author,
        "independent_review": {
            "outcome": outcome,
            "reviewer": reviewer,
            "reviewed_at": "2026-09-09T12:00:00Z",
        },
    }
    if variant:
        entry["course_variant"] = variant
    if pair is not None:
        entry["course_pair"] = pair
    if historical_label is not None:
        entry["historical_label"] = historical_label
    return entry


def _manifest(tmp_path: Path, baseline: Path, proposed: Path, facts, *, kind="captured_live",
              manifest_proposed_sha=None, historical=False):
    capture = _source(tmp_path)
    page = {
        "slug": "fuego-mtb",
        "baseline": {"kind": kind},
        "proposed_sha256": manifest_proposed_sha or _sha(proposed / "fuego-mtb.html"),
        "facts": facts(capture) if callable(facts) else facts,
    }
    if kind == "captured_live":
        page["baseline"]["sha256"] = _sha(baseline / "fuego-mtb.html")
    packet = {
        "schemaVersion": gate.SCHEMA_VERSION,
        "baseline_metadata": {
            "captured_at": "2026-09-09T12:00:00Z",
            "canonical_live_base_url": "https://gravelgodcycling.com/race/",
        },
        "pages": [page],
    }
    path = tmp_path / "review.json"
    path.write_text(json.dumps(packet))
    return path


@pytest.fixture
def tree(tmp_path):
    baseline = tmp_path / "live"
    proposed = tmp_path / "proposed"
    baseline.mkdir()
    proposed.mkdir()
    (baseline / "fuego-mtb.html").write_text(_page())
    (proposed / "fuego-mtb.html").write_text(_page())
    return baseline, proposed


class TestExtraction:
    def test_extracts_only_rendered_context_facts_and_fueling_distance(self):
        facts = gate.extract_rendered_facts(
            _page(distance="66 mi", conditions="Windy", course="Ridge").replace(
                '<p><strong>Elevation:</strong> 7,800 ft</p>', '') +
            '<p><strong>Your Fueling Math (66 miles):</strong> text</p>')
        assert facts == {"distance": "66 mi", "conditions": "Windy", "course": "Ridge"}

    def test_rejects_conflicting_rendered_distance_values(self):
        with pytest.raises(gate.GateError, match="conflicting rendered distance"):
            gate.extract_rendered_facts(
                _page(distance="66 mi") + '<p><strong>Your Fueling Math (70 miles):</strong> text</p>')


class TestRenderedFactGate:
    def test_unchanged_facts_pass_with_css_change_and_no_reviews(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(css="body { color: red; }"))
        manifest = _manifest(tree[0].parent, baseline, proposed, [])
        report = gate.validate_release(proposed, baseline, manifest)
        assert report.changed_facts == []

    def test_generator_only_live_drift_fuego_fails_without_review(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="66 mi"))
        manifest = _manifest(tree[0].parent, baseline, proposed, [])
        with pytest.raises(gate.GateError, match="fuego-mtb.distance"):
            gate.validate_release(proposed, baseline, manifest)

    def test_accepted_current_distance_and_elevation_pair_passes(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="66 mi", elevation="7,900 ft"))
        def facts(capture):
            pair = {"distance": "66 mi", "elevation": "7,900 ft"}
            return [
                _review("distance", "66 mi", capture, variant="Fuego XL", pair=pair),
                _review("elevation", "7,900 ft", capture, variant="Fuego XL", pair=pair),
            ]
        manifest = _manifest(tree[0].parent, baseline, proposed, facts)
        assert gate.validate_release(proposed, baseline, manifest).changed_facts == [
            ("fuego-mtb", "distance"), ("fuego-mtb", "elevation")]

    def test_why_not_chee_mismatched_course_variants_fail(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="46 mi", elevation="2,000 ft"))
        def facts(capture):
            return [
                _review("distance", "46 mi", capture, variant="two loops",
                        pair={"distance": "46 mi", "elevation": "4,000 ft"}),
                _review("elevation", "2,000 ft", capture, variant="one loop",
                        pair={"distance": "23 mi", "elevation": "2,000 ft"}),
            ]
        manifest = _manifest(tree[0].parent, baseline, proposed, facts)
        with pytest.raises(gate.GateError, match="course_variant"):
            gate.validate_release(proposed, baseline, manifest)

    @pytest.mark.parametrize("outcome", ["contradicted", "unverified", "unavailable"])
    def test_unreceipted_or_negative_review_outcomes_fail(self, tree, outcome):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="66 mi"))
        manifest = _manifest(
            tree[0].parent, baseline, proposed,
            lambda capture: [_review("distance", "66 mi", capture, outcome=outcome,
                                     variant="Fuego XL",
                                     pair={"distance": "66 mi", "elevation": "7,800 ft"})])
        with pytest.raises(gate.GateError, match=outcome):
            gate.validate_release(proposed, baseline, manifest)

    def test_future_date_without_accepted_receipt_fails(self, tree):
        baseline, proposed = tree
        (baseline / "fuego-mtb.html").write_text(_page() + "<p><strong>Race Date:</strong> 2026-07-26</p>")
        (proposed / "fuego-mtb.html").write_text(_page() + "<p><strong>Race Date:</strong> 2027-07-25</p>")
        manifest = _manifest(tree[0].parent, baseline, proposed, [])
        with pytest.raises(gate.GateError, match="race_date"):
            gate.validate_release(proposed, baseline, manifest)

    def test_historical_fact_requires_historical_render_label(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="82 mi", historical=False))
        manifest = _manifest(
            tree[0].parent, baseline, proposed,
            lambda capture: [_review("distance", "82 mi", capture, outcome="historical",
                                     status="historical", variant="2025 long course",
                                     pair={"distance": "82 mi", "elevation": "7,800 ft"},
                                     historical_label="Historical course information")])
        with pytest.raises(gate.GateError, match="historical"):
            gate.validate_release(proposed, baseline, manifest)

    def test_historical_fact_with_historical_render_label_passes(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="82 mi", historical=True))
        manifest = _manifest(
            tree[0].parent, baseline, proposed,
            lambda capture: [_review("distance", "82 mi", capture, outcome="historical",
                                     status="historical", variant="2025 long course",
                                     pair={"distance": "82 mi", "elevation": "7,800 ft"},
                                     historical_label="Historical course information")])
        assert gate.validate_release(proposed, baseline, manifest).changed_facts == [("fuego-mtb", "distance")]

    def test_missing_baseline_is_not_treated_as_404_approval(self, tree):
        baseline, proposed = tree
        manifest = _manifest(tree[0].parent, baseline, proposed, [], kind="captured_live")
        (baseline / "fuego-mtb.html").unlink()
        with pytest.raises(gate.GateError, match="baseline"):
            gate.validate_release(proposed, baseline, manifest)

    def test_new_page_requires_explicit_designation_and_all_reviews(self, tree):
        baseline, proposed = tree
        (baseline / "fuego-mtb.html").unlink()
        def facts(capture):
            pair = {"distance": "70 mi", "elevation": "7,800 ft"}
            return [
                _review("distance", "70 mi", capture, variant="Fuego XL", pair=pair),
                _review("elevation", "7,800 ft", capture, variant="Fuego XL", pair=pair),
                _review("conditions", "Dry and warm", capture),
                _review("course", "Long exposed climb", capture, variant="Fuego XL"),
            ]
        manifest = _manifest(tree[0].parent, baseline, proposed, facts, kind="new_page")
        assert gate.validate_release(proposed, baseline, manifest).new_pages == ["fuego-mtb"]

    def test_proposed_or_capture_tampering_fails(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="66 mi"))
        manifest = _manifest(
            tree[0].parent, baseline, proposed,
            lambda capture: [_review("distance", "66 mi", capture, variant="Fuego XL",
                                     pair={"distance": "66 mi", "elevation": "7,800 ft"})])
        (proposed / "fuego-mtb.html").write_text(_page(distance="67 mi"))
        with pytest.raises(gate.GateError, match="proposed_sha256"):
            gate.validate_release(proposed, baseline, manifest)

    def test_capture_tampering_fails(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="66 mi"))
        manifest = _manifest(
            tree[0].parent, baseline, proposed,
            lambda capture: [_review("distance", "66 mi", capture, variant="Fuego XL",
                                     pair={"distance": "66 mi", "elevation": "7,800 ft"})])
        (tree[0].parent / "captures" / "official.txt").write_text("tampered")
        with pytest.raises(gate.GateError, match="source capture sha256"):
            gate.validate_release(proposed, baseline, manifest)

    def test_manifest_inventory_must_exactly_match_proposed_files(self, tree):
        baseline, proposed = tree
        (proposed / "extra.html").write_text(_page())
        manifest = _manifest(tree[0].parent, baseline, proposed, [])
        with pytest.raises(gate.GateError, match="inventory"):
            gate.validate_release(proposed, baseline, manifest)

    def test_author_cannot_independently_review_own_claim(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="66 mi"))
        manifest = _manifest(
            tree[0].parent, baseline, proposed,
            lambda capture: [_review("distance", "66 mi", capture, author="same", reviewer="same",
                                     variant="Fuego XL",
                                     pair={"distance": "66 mi", "elevation": "7,800 ft"})])
        with pytest.raises(gate.GateError, match="differ"):
            gate.validate_release(proposed, baseline, manifest)


class TestPushWordpressIntegration:
    def test_direct_sync_cannot_reach_credentials_without_fact_packet(self, tree, monkeypatch, capsys):
        proposed = tree[1]
        monkeypatch.setattr(pw, "get_ssh_credentials", lambda: pytest.fail("credentials were touched"))
        assert pw.sync_prep_kits(str(proposed)) is None
        assert "direct sync_prep_kits requires" in capsys.readouterr().out

    def test_cli_fact_gate_runs_before_any_dispatch(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        main_block = source[source.index('if __name__ == "__main__":'):]
        assert main_block.index("apply_prep_kit_fact_gate(args)") < main_block.index("_run(")
        assert "args.prep_kit_live_baseline_dir, args.prep_kit_fact_manifest" in main_block
