from types import SimpleNamespace

from scripts import jev_client, jev_duplicate_check


def test_duplicate_verdict_bands(monkeypatch):
    values = iter((0.9, 0.1, 0.5))
    monkeypatch.setattr(jev_duplicate_check, "_profile", lambda slug: {"slug": slug})
    monkeypatch.setattr(jev_client, "ask", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        jev_client,
        "noul",
        lambda *_args: SimpleNamespace(noul=next(values)),
    )
    assert jev_duplicate_check._row("a", "b")["verdict"] == "likely_same"
    assert jev_duplicate_check._row("a", "b")["verdict"] == "likely_distinct"
    assert jev_duplicate_check._row("a", "b")["verdict"] == "unclear"


def test_unavailable_duplicate_is_unclear(monkeypatch):
    monkeypatch.setattr(jev_client, "get_client", lambda: None)
    monkeypatch.setattr(jev_duplicate_check, "_profile", lambda slug: {"slug": slug})
    row = jev_duplicate_check._row("a", "b")
    assert row["same_event_probability"] is None
    assert row["verdict"] == "unclear"
