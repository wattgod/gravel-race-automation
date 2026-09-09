"""Offline rendered-fact release gate tests."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "prep_kit_fact_gate"
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import prep_kit_fact_gate as gate  # noqa: E402
import push_wordpress as pw  # noqa: E402


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _page(*, name="Fuego MTB", distance="70 mi", elevation="7,800 ft",
          race_date="July 26, 2026", location="Monterey, California",
          conditions="Dry and warm", course="Long exposed climb", entry_fee=None,
          trip_cost=None, nearest_airport=None, start_time=None, aid_stations=None,
          historical=False, css="") -> str:
    label = "<p>Historical course information.</p>" if historical else ""
    vitals = []
    if distance is not None:
        vitals.append(f'<span class="gg-pk-stat"><strong>{distance}</strong></span>')
    if elevation is not None:
        vitals.append(f'<span class="gg-pk-stat"><strong>{elevation}</strong></span>')
    vitals.extend((f'<span class="gg-pk-stat">{race_date}</span>',
                   f'<span class="gg-pk-stat">{location}</span>'))
    budget = "".join(
        f"<p><strong>{label}:</strong> {value}</p>"
        for label, value in (("Entry Fee", entry_fee), ("Cost of Trip", trip_cost),
                             ("Nearest Airport", nearest_airport),
                             ("Aid Stations", aid_stations))
        if value is not None)
    start = (f"<p><strong>{name} Start Time:</strong> {start_time}</p>"
             if start_time is not None else "")
    return f"""<html><style>{css}</style><header class="gg-pk-header">
<h1 class="gg-pk-header-title">{name}</h1>
<div class="gg-pk-vitals-ribbon">{' '.join(vitals)}</div></header>
<div class=\"gg-pk-context-box\">
<p><strong>Distance:</strong> {distance}</p>
{'' if elevation is None else f'<p><strong>Elevation:</strong> {elevation}</p>'}
<p><strong>Conditions:</strong> {conditions}</p>
<p><strong>Signature Challenge:</strong> {course}</p>{budget}</div>{start}{label}</html>"""


def _source(root: Path, text="Official course announcement. Fuego XL is 66 mi with 7,800 ft."):
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
            "excerpt": "Official course announcement.",
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
            _page(distance="66 mi", elevation=None, conditions="Windy", course="Ridge") +
            '<p><strong>Your Fueling Math (66 miles):</strong> text</p>')
        assert facts == {
            "name": "Fuego MTB", "distance": "66 mi", "race_date": "July 26, 2026",
            "location": "Monterey, California", "conditions": "Windy", "course": "Ridge",
        }

    def test_rejects_conflicting_rendered_distance_values(self):
        with pytest.raises(gate.GateError, match="conflicting rendered distance"):
            gate.extract_rendered_facts(
                _page(distance="66 mi") + '<p><strong>Your Fueling Math (70 miles):</strong> text</p>')

    def test_real_the_divide_headers_include_date_and_all_hero_vitals(self):
        provenance = json.loads((FIXTURE_DIR / "provenance.json").read_text())
        assert provenance["the-divide-live-header.html"]["source_sha256"] == (
            "304ff713c979929cf76455629987cf8d6dbbb96f96b74525db6a774dde635f5c")
        live = gate.extract_rendered_facts((FIXTURE_DIR / "the-divide-live-header.html").read_text())
        proposed = gate.extract_rendered_facts((FIXTURE_DIR / "the-divide-proposed-header.html").read_text())
        assert live == {
            "name": "The Divide", "distance": "50 mi", "elevation": "2,500 ft",
            "race_date": "July 26, 2026", "location": "Manton, Michigan",
        }
        assert proposed == {
            "name": "The Divide", "distance": "52 mi", "elevation": "4,500 ft",
            "race_date": "July 25, 2027", "location": "Manton, Michigan, United States",
        }

    def test_real_trans_sylvania_headers_include_name_and_date_change(self):
        provenance = json.loads((FIXTURE_DIR / "provenance.json").read_text())
        assert provenance["trans-sylvania-proposed-header.html"]["source_sha256"] == (
            "51a2a89a675a77082ec8893953225979625c2066f550f8662ef732bba98ac1ea")
        live = gate.extract_rendered_facts((FIXTURE_DIR / "trans-sylvania-live-header.html").read_text())
        proposed = gate.extract_rendered_facts((FIXTURE_DIR / "trans-sylvania-proposed-header.html").read_text())
        assert live["name"] == "Trans-Sylvania Epic"
        assert proposed["name"] == "Trans-Sylvania Gravel Epic"
        assert live["race_date"] == "May 19-23, 2026"
        assert proposed["race_date"] == "May 21-23; 2027 not announced, 2026"

    def test_unknown_or_unmanaged_header_markup_refuses(self):
        with pytest.raises(gate.GateError, match="unrecognized prep-kit header"):
            gate.extract_rendered_facts("<h1>New Race</h1><p>Race date: July 25, 2027</p>")

    def test_rejects_empty_hero_date_or_location(self):
        for kwargs in ({"race_date": ""}, {"location": ""}):
            with pytest.raises(gate.GateError, match="vitals-ribbon values"):
                gate.extract_rendered_facts(_page(**kwargs))

    def test_extracts_actual_generated_budget_morning_and_aid_regions(self):
        facts = gate.extract_rendered_facts(
            (FIXTURE_DIR / "lone-wolf-factual-regions.html").read_text())
        assert facts == {
            "name": "Lone Wolf Gravel", "distance": "62 mi", "elevation": "4,000 ft",
            "race_date": "September 27, 2026", "location": "Iron Mountain, Michigan",
            "entry_fee": "~$60", "trip_cost": "Above average (4/5)",
            "nearest_airport": "Green Bay (GRB) 2 hours, or Detroit (DTW) 5 hours",
            "start_time": "9:15 AM CDT. Set your alarm for 6:15 AM.",
            "aid_stations": "Minimal aid stations",
        }


class TestRenderedFactGate:
    def test_unchanged_facts_pass_with_css_change_and_no_reviews(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(css="body { color: red; }"))
        manifest = _manifest(tree[0].parent, baseline, proposed, [])
        report = gate.validate_release(proposed, baseline, manifest)
        assert report.changed_facts == []

    def test_unchanged_suppressed_elevation_passes(self, tree):
        baseline, proposed = tree
        (baseline / "fuego-mtb.html").write_text(_page(elevation=None))
        (proposed / "fuego-mtb.html").write_text(_page(elevation=None, css="body { color: red; }"))
        manifest = _manifest(tree[0].parent, baseline, proposed, [])
        assert gate.validate_release(proposed, baseline, manifest).changed_facts == []

    def test_generator_only_live_drift_fuego_fails_without_review(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="66 mi"))
        manifest = _manifest(tree[0].parent, baseline, proposed, [])
        with pytest.raises(gate.GateError, match="fuego-mtb.distance"):
            gate.validate_release(proposed, baseline, manifest)

    @pytest.mark.parametrize("field,baseline_value,proposed_value", [
        ("entry_fee", "~$75", "~$109"),
        ("trip_cost", "Moderate (3/5)", "Premium destination (5/5)"),
        ("nearest_airport", "Airport A", "Airport B"),
        ("start_time", "8:00 AM mass start.", "8:15 AM wave start."),
        ("aid_stations", "Multiple on course", "Two stocked stops"),
    ])
    def test_generated_factual_region_change_requires_review(
            self, tree, field, baseline_value, proposed_value):
        baseline, proposed = tree
        (baseline / "fuego-mtb.html").write_text(_page(**{field: baseline_value}))
        (proposed / "fuego-mtb.html").write_text(_page(**{field: proposed_value}))
        manifest = _manifest(tree[0].parent, baseline, proposed, [])
        with pytest.raises(gate.GateError, match=f"fuego-mtb.{field}"):
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
                        pair={"distance": "46 mi", "elevation": "2,000 ft"}),
                _review("elevation", "2,000 ft", capture, variant="one loop",
                        pair={"distance": "46 mi", "elevation": "2,000 ft"}),
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
                _review("name", "Fuego MTB", capture),
                _review("distance", "70 mi", capture, variant="Fuego XL", pair=pair),
                _review("elevation", "7,800 ft", capture, variant="Fuego XL", pair=pair),
                _review("race_date", "July 26, 2026", capture),
                _review("location", "Monterey, California", capture),
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

    def test_excerpt_must_appear_in_the_hashed_capture(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="66 mi"))
        manifest = _manifest(
            tree[0].parent, baseline, proposed,
            lambda capture: [_review("distance", "66 mi", capture, variant="Fuego XL",
                                     pair={"distance": "66 mi", "elevation": "7,800 ft"})])
        payload = json.loads(manifest.read_text())
        payload["pages"][0]["facts"][0]["source"]["excerpt"] = "not in capture"
        manifest.write_text(json.dumps(payload))
        with pytest.raises(gate.GateError, match="excerpt"):
            gate.validate_release(proposed, baseline, manifest)

    def test_review_date_must_be_timezone_aware_iso_timestamp(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="66 mi"))
        manifest = _manifest(
            tree[0].parent, baseline, proposed,
            lambda capture: [_review("distance", "66 mi", capture, variant="Fuego XL",
                                     pair={"distance": "66 mi", "elevation": "7,800 ft"})])
        payload = json.loads(manifest.read_text())
        payload["pages"][0]["facts"][0]["independent_review"]["reviewed_at"] = "2026-09-09T12:00:00"
        manifest.write_text(json.dumps(payload))
        with pytest.raises(gate.GateError, match="timezone"):
            gate.validate_release(proposed, baseline, manifest)

    def test_distance_only_change_must_bind_unmodified_rendered_elevation(self, tree):
        baseline, proposed = tree
        (proposed / "fuego-mtb.html").write_text(_page(distance="66 mi", elevation="7,800 ft"))
        manifest = _manifest(
            tree[0].parent, baseline, proposed,
            lambda capture: [_review("distance", "66 mi", capture, variant="Fuego XL",
                                     pair={"distance": "66 mi", "elevation": "2,000 ft"})])
        with pytest.raises(gate.GateError, match="rendered elevation"):
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
