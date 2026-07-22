"""Regression tests for the SiteGround WAF-challenge handling in the immune
link checker (Roadie Labs 2026-07-22 incident: 18 false dead/money-path
findings that were all HTTP 202 bot-challenge responses).

Covers: challenge classification, retry budget, checker exit semantics, and
immune_check's parsing of the checker's output (including crash handling).
"""

from __future__ import annotations

import io
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_links
import immune_check


class FakeResponse:
    def __init__(self, status: int, headers: dict[str, str] | None = None,
                 body: bytes = b"", content_type: str = "text/html"):
        self.status = status
        hdrs = {"Content-Type": content_type}
        hdrs.update(headers or {})
        self.headers = hdrs
        self._body = body

    def read(self, n: int = -1) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# ── Challenge classification ─────────────────────────────────────────────────
def test_202_is_challenged_not_dead(monkeypatch):
    monkeypatch.setattr(check_links.urllib.request, "urlopen",
                        lambda req, timeout=15: FakeResponse(202, {"sg-captcha": "challenge"}))
    status, _, challenged = check_links._fetch_once("https://gravelgodcycling.com/x/", 15, False)
    assert status == 202 and challenged


def test_404_with_sg_captcha_header_is_dead_not_challenged(monkeypatch):
    err = urllib.error.HTTPError(
        "https://gravelgodcycling.com/x/", 404, "Not Found",
        {"sg-captcha": "challenge"}, io.BytesIO(b""))
    def raise_it(req, timeout=15):
        raise err
    monkeypatch.setattr(check_links.urllib.request, "urlopen", raise_it)
    status, _, challenged = check_links._fetch_once("https://gravelgodcycling.com/x/", 15, False)
    assert status == 404 and not challenged


def test_200_is_clean(monkeypatch):
    monkeypatch.setattr(check_links.urllib.request, "urlopen",
                        lambda req, timeout=15: FakeResponse(200, body=b"<html></html>"))
    status, _, challenged = check_links._fetch_once("https://gravelgodcycling.com/", 15, False)
    assert status == 200 and not challenged


# ── Retry budget ─────────────────────────────────────────────────────────────
def test_retry_backoff_consumes_budget(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(check_links.time, "sleep", sleeps.append)
    monkeypatch.setattr(check_links, "_fetch_once",
                        lambda url, timeout, text_mode: (202, "", True))
    monkeypatch.setattr(check_links, "_challenge_budget",
                        check_links.CHALLENGE_RETRY_BUDGET)
    status, _, challenged = check_links.fetch("https://gravelgodcycling.com/x/")
    assert challenged
    assert sleeps == list(check_links.CHALLENGE_BACKOFF)
    assert check_links._challenge_budget == \
        check_links.CHALLENGE_RETRY_BUDGET - sum(check_links.CHALLENGE_BACKOFF)


def test_exhausted_budget_skips_sleeping(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(check_links.time, "sleep", sleeps.append)
    monkeypatch.setattr(check_links, "_fetch_once",
                        lambda url, timeout, text_mode: (202, "", True))
    monkeypatch.setattr(check_links, "_challenge_budget", 5)
    status, _, challenged = check_links.fetch("https://gravelgodcycling.com/x/")
    assert challenged and sleeps == []


def test_incident_pattern_fits_subprocess_timeout():
    """18 persistently challenged URLs (the Jul 22 pattern) must not be able
    to sleep past immune_check's 900s subprocess timeout."""
    assert check_links.CHALLENGE_RETRY_BUDGET + 300 < 900


# ── immune_check parsing of checker output ───────────────────────────────────
def parse(monkeypatch, stdout, returncode, stderr=""):
    fake = SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)
    monkeypatch.setattr(immune_check.subprocess, "run", lambda *a, **k: fake)
    return immune_check.run_live_link_check()


def test_mixed_waf_and_dead(monkeypatch):
    stdout = (
        "  WAF challenge on https://gravelgodcycling.com/a/ — retrying in 20s\n"
        "Loaded 1538 URLs from live sitemap(s)\n"
        "Checked 200 sitemap seed pages + 300 discovered/required URLs\n"
        "\nWAF-CHALLENGED (2): still behind SiteGround's bot challenge after retries\n"
        "   202  https://gravelgodcycling.com/a/\n"
        "   202  https://gravelgodcycling.com/a/\n"
        "\nDEAD LINKS (2):\n"
        "   404  https://gravelgodcycling.com/questionnaire/\n"
        "   500  https://gravelgodcycling.com/some-page/\n")
    findings = parse(monkeypatch, stdout, 1)
    codes = [f.code for f in findings]
    assert codes.count("live-check-challenged") == 1
    assert "money-path-404" in codes and "dead-link" in codes
    assert "live-check-failed" not in codes
    challenged = next(f for f in findings if f.code == "live-check-challenged")
    assert "https://gravelgodcycling.com/a/" in challenged.detail
    assert challenged.lane == immune_check.YELLOW
    money = next(f for f in findings if f.code == "money-path-404")
    assert money.lane == immune_check.RED


def test_challenged_only_rc2(monkeypatch):
    stdout = (
        "\nWAF-CHALLENGED (1): still behind SiteGround's bot challenge after retries\n"
        "   202  https://gravelgodcycling.com/questionnaire/\n"
        "No dead links found, but the scan is INCONCLUSIVE (WAF challenges).\n")
    findings = parse(monkeypatch, stdout, 2)
    assert [f.code for f in findings] == ["live-check-challenged"]
    assert "questionnaire" in findings[0].detail


def test_crash_is_a_finding_not_silence(monkeypatch):
    findings = parse(monkeypatch, "", 3, stderr="Traceback (most recent call last): ...")
    assert [f.code for f in findings] == ["live-check-failed"]
    assert "Traceback" in findings[0].detail


def test_rc1_without_parsable_dead_lines_flags_drift(monkeypatch):
    findings = parse(monkeypatch, "SOMETHING UNEXPECTED\n", 1)
    assert [f.code for f in findings] == ["live-check-failed"]


def test_clean_run_yields_nothing(monkeypatch):
    findings = parse(monkeypatch, "All links alive.\n", 0)
    assert findings == []
