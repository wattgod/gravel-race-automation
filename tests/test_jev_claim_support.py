from pathlib import Path
from types import SimpleNamespace

from scripts import jev_claim_support, jev_client


def test_sentence_filter_respects_decimal_and_claim_signals():
    sentences = jev_claim_support.split_sentences("A 6.5-mile climb. Most riders finish first. A calm day.")
    assert sentences == ["A 6.5-mile climb", "Most riders finish first", "A calm day"]
    assert jev_claim_support.should_check(sentences[0])
    assert jev_claim_support.should_check(sentences[1])
    assert not jev_claim_support.should_check(sentences[2])


def test_claims_batch_in_tens(monkeypatch):
    data = {
        "race": {
            "biased_opinion_ratings": {
                "length": {"explanation": " ".join(f"Race fact {index}." for index in range(21))}
            }
        }
    }
    calls = []

    class Answer:
        def __init__(self):
            self.noul = 0.8

    def ask(state, questions):
        calls.append((state, questions))
        return object()

    monkeypatch.setattr(jev_client, "ask", ask)
    monkeypatch.setattr(jev_client, "noul", lambda *_args: Answer())
    rows = jev_claim_support.audit_profile("synthetic", data, "Race fact research.")
    assert len(calls) == 2
    assert [len(call[1]) for call in calls] == [10, 10]
    assert len(rows) == 20


def test_no_dump_is_counted_and_unavailable_has_no_flags(monkeypatch, tmp_path):
    monkeypatch.setattr(jev_claim_support, "RACE_DATA", tmp_path / "race-data")
    monkeypatch.setattr(jev_claim_support, "RESEARCH", tmp_path / "research")
    jev_claim_support.RACE_DATA.mkdir()
    jev_claim_support.RESEARCH.mkdir()
    (jev_claim_support.RACE_DATA / "synthetic.json").write_text('{"race": {}}')
    monkeypatch.setattr(jev_client, "get_client", lambda: None)
    report = jev_claim_support.run(SimpleNamespace(slug=None, limit=None))
    assert report["model"] is None
    assert report["jev_available"] is False
    assert report["summary"]["no_dump"] == 1
    assert report["summary"]["unsupported"] == 0
