"""Uptime monitor decisions (sweep ALL-06)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import uptime_check as uc  # noqa: E402

T = ("X", "https://x.example/", "GET", 200, "X")


def seq(*states):
    it = iter(states)
    return lambda *a: next(it)


def test_one_good_try_is_up():
    assert uc.check(T, sleep=lambda s: None, probe_fn=seq(("down", "e"), ("up", "ok")))[0] == "up"


def test_three_bad_tries_is_down():
    calls = []
    st, _ = uc.check(T, sleep=calls.append, probe_fn=seq(*[("down", "e")] * 3))
    assert st == "down" and calls == [30.0, 30.0]


def test_bot_challenge_is_unknown_not_down():
    assert uc.check(T, sleep=lambda s: None, probe_fn=seq(*[("unknown", "403")] * 3))[0] == "unknown"


def test_decide():
    assert uc.decide(["up", "down"], issue_open=False) == "alert"
    assert uc.decide(["up", "down"], issue_open=True) == "update"
    assert uc.decide(["up", "up"], issue_open=True) == "recover"
    assert uc.decide(["up", "unknown"], issue_open=True) == "none"
    assert uc.decide(["unknown"], issue_open=False) == "none"
    assert uc.decide(["up"], issue_open=False) == "none"


def test_targets_cover_sites_checkout_and_workers():
    names = " ".join(t[0] for t in uc.TARGETS)
    for needed in ("Gravel God home", "Roadie Labs home", "XC Ski Labs home",
                   "Checkout API", "coaching-intake"):
        assert needed in names
    assert uc.ALERT_TO == "gravelgodcoaching@gmail.com"
    assert "Mozilla" not in uc.UA  # SiteGround resets spoofed browser UAs


def test_missing_resend_key_fails_loudly(monkeypatch):
    import pytest
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        uc.email("s", "b")
