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


def test_only_siteground_homes_can_be_unknown(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
    monkeypatch.setattr(uc.urllib.request, "urlopen", fake_urlopen)
    assert uc.probe("https://x/", "GET", 200, None, challengeable=True)[0] == "unknown"
    assert uc.probe("https://x/", "GET", 200, None, challengeable=False)[0] == "down"
    api = [t for t in uc.TARGETS if t[0] == "Checkout API /health"][0]
    assert api[0] not in uc.SITEGROUND_PAGES


def _run_main(monkeypatch, states, open_issues, email_fails=False):
    calls = []
    monkeypatch.setattr(uc, "TARGETS", [(f"T{i}", "u", "GET", 200, None) for i in range(len(states))])
    it = iter(states)
    monkeypatch.setattr(uc, "check", lambda t: (next(it), "d"))

    def fake_gh(method, path, payload=None):
        calls.append(("gh", method, path))
        return open_issues if method == "GET" else {}

    def fake_email(subject, text):
        calls.append(("email", subject))
        if email_fails:
            raise SystemExit("resend down")
    monkeypatch.setattr(uc, "_gh", fake_gh)
    monkeypatch.setattr(uc, "email", fake_email)
    monkeypatch.setattr(sys, "argv", ["uptime_check.py"])
    return calls


def test_failed_alert_email_leaves_no_issue_so_next_run_retries(monkeypatch):
    import pytest
    calls = _run_main(monkeypatch, ["down"], [], email_fails=True)
    with pytest.raises(SystemExit):
        uc.main()
    assert ("gh", "POST", "/issues") not in calls


def test_failed_recovery_email_keeps_issue_open(monkeypatch):
    import pytest
    calls = _run_main(monkeypatch, ["up"], [{"number": 7}], email_fails=True)
    with pytest.raises(SystemExit):
        uc.main()
    assert not any(c[0] == "gh" and c[1] == "PATCH" for c in calls)


def test_alert_emails_then_opens_issue(monkeypatch):
    calls = _run_main(monkeypatch, ["down", "up"], [])
    assert uc.main() == 0
    kinds = [c[0] if c[0] == "email" else c[1] for c in calls if c[1:] != ("GET",) and c[0] != "gh" or c[1] != "GET"]
    assert kinds.index("email") < kinds.index("POST")
