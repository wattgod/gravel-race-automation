from types import SimpleNamespace

from scripts import jev_client, jev_rating_audit


def _profile():
    dimensions = jev_rating_audit.parse_rubric()
    opinions = {
        key: {"score": 4, "explanation": f"{key} has a strong, specific case."}
        for key in dimensions
    }
    return {
        "race": {
            "name": "Synthetic Race",
            "vitals": {"distance_mi": 100, "location": "Fictionland"},
            "gravel_god_rating": {key: 4 for key in dimensions},
            "biased_opinion_ratings": opinions,
        }
    }


def test_rubric_parser_has_fourteen_dimensions_and_five_levels():
    rubric = jev_rating_audit.parse_rubric()
    assert len(rubric) == 14
    assert all(len(levels) == 5 for levels in rubric.values())
    assert "race_quality" in rubric
    assert "field_depth" in rubric


def test_drift_severity_and_explanation_mismatch(monkeypatch):
    profile = _profile()
    dimensions = jev_rating_audit.parse_rubric()
    profile["race"]["gravel_god_rating"]["length"] = 2
    profile["race"]["biased_opinion_ratings"]["length"]["score"] = 3
    answer = SimpleNamespace(score=4, confidence=0.7, probabilities={"4": 0.7})
    monkeypatch.setattr(jev_client, "ask", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(jev_client, "score", lambda *_args: answer)
    rows = jev_rating_audit.audit_profile("synthetic", profile, dimensions)
    length = next(row for row in rows if row["dimension"] == "length")
    assert length["severity"] == "high"
    assert length["explanation_mismatch"] is True


def test_without_client_produces_no_flags(monkeypatch):
    monkeypatch.setattr(jev_client, "get_client", lambda: None)
    report = jev_rating_audit.run(
        SimpleNamespace(slug="synthetic-not-present", tier=None, limit=None, all=False)
    )
    assert report["model"] is None
    assert report["jev_available"] is False
    assert report["summary"]["high"] == 0
