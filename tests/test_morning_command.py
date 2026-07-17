"""Offline contract tests for Morning Command detection, lanes, and rendering."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts import daily_intel
from scripts.daily_intel import rank_findings, render_morning_command
from scripts.immune_check import GREEN, RED, YELLOW, classify
from scripts.immune_ci import classify_ci_runs, classify_cron_runs

FIXTURES = Path(__file__).parent / "fixtures"


def test_new_lane_policy_rows():
    cases = {
        "invalid workflow YAML: step-level strategy": ("ci-workflow-syntax", GREEN),
        "Node-version drift: Node 20 without native WebSocket": ("ci-node-drift", GREEN),
        "Scheduled workflow failed 3 consecutive runs due to a missing script": (
            "ci-disable-broken-schedule", GREEN),
        "pytest: 3 tests failed": ("ci-test-failure", YELLOW),
        "monitor flagging a real site issue": ("site-health", YELLOW),
        "cron doing 0 work: david-resolve-predictions": ("cron-unhealthy", YELLOW),
        "checkout production outage": ("money-path", RED),
        "credential leak security incident": ("security", RED),
    }
    for message, expected in cases.items():
        finding = classify(message, source="test")
        assert (finding.code, finding.lane) == expected
    assert classify("checkout production outage").auto_fix is None


def test_ci_detector_surfaces_new_and_chronic_only_and_demotes_sibling_green():
    payload = json.loads((FIXTURES / "morning_command_ci.json").read_text())
    logs = {
        101: "The workflow is not valid: strategy is not allowed here on this step",
        201: "pytest: 2 tests failed with AssertionError",
        401: "Node 20 without native WebSocket while syncing Supabase",
    }
    findings, suppressed = classify_ci_runs(payload, lambda _repo, run_id: logs.get(run_id, ""))
    by_title = {finding.title: finding for finding in findings}

    assert by_title["Broken YAML · gravel-race-automation"].lane == GREEN
    assert by_title["Tests · gravel-race-automation"].lane == YELLOW
    sibling = by_title["Node Sync · road-race-automation"]
    assert sibling.lane == YELLOW
    assert sibling.auto_fix is None
    assert suppressed == 1


def test_cron_detector_classifies_repeated_failure_and_zero_work():
    payload = json.loads((FIXTURES / "morning_command_cron.json").read_text())
    findings, suppressed = classify_cron_runs(payload)
    assert {finding.title for finding in findings} == {
        "david-resolve-predictions", "calendar-refresh",
    }
    assert all(finding.code == "cron-unhealthy" for finding in findings)
    assert all(finding.lane == YELLOW for finding in findings)
    assert suppressed == 1


def _command_fixture() -> dict:
    findings = [
        {"code": "ci-test-failure", "lane": "yellow", "severity": "high",
         "title": "Tests · endurelabs", "detail": "pytest: 2 tests failed",
         "remedy": "Open a reviewed PR.", "auto_fix": None,
         "source": "github-actions", "new": True},
        {"code": "money-path", "lane": "red", "severity": "critical",
         "title": "Checkout probe", "detail": "checkout HTTP 500",
         "remedy": "Investigate manually.", "auto_fix": None,
         "source": "checkout-monitor", "new": True},
    ]
    return {
        "date": "2026-07-13",
        "base": {
            "commerce_ledger": {"ok": True, "orders": [{"amount": 249}], "failed_orders": []},
            "ga4": {"gravelgod": {"ok": True, "sessions": 44, "sessions_7d_avg": 36,
                                     "funnel": {"purchase": 1}}},
        },
        "site_health": {
            "gsc": {"ok": True, "overall": {"clicks": 10, "impressions": 500,
                                                "ctr": 2.0, "position": 8.1}},
            "cwv": {"ok": True, "summary": {"avg_performance_score": 91,
                                                "fail_count": 0, "errors": 0}},
        },
        "findings": rank_findings(findings),
        "auto_healed": [{"issue_class": "ci-workflow-syntax",
                          "fix_applied": "moved strategy to job level"}],
        "suppressed": 7,
        "unavailable": [],
    }


def test_report_rendering_has_ranked_spec_sections_and_money_first():
    subject, report = render_morning_command(_command_fixture())
    assert subject == "Morning Command · 2026-07-13 · 2 need you"
    expected = [
        "MORNING COMMAND · 2026-07-13", "TOP LINE:", "💰 MONEY",
        "🔴 ACT TODAY", "🟢 AUTO-HEALED", "🟡 PROPOSED", "📊 PULSE",
        "🎯 DECIDE", "— suppressed: 7 green/known-noise items",
    ]
    positions = [report.index(section) for section in expected]
    assert positions == sorted(positions)
    assert report.index("Checkout probe") < report.index("Tests · endurelabs")
    assert "sales $249.00" in report
    assert "cause:" in report and "action:" in report


def test_preview_prints_without_sending_or_writing(monkeypatch, capsys):
    monkeypatch.setattr(daily_intel, "aggregate", lambda offline=False: _command_fixture())
    monkeypatch.setattr(
        daily_intel, "send_email",
        lambda *_args: (_ for _ in ()).throw(AssertionError("preview must not send")),
    )
    monkeypatch.setattr(sys, "argv", ["daily_intel.py", "--preview"])
    assert daily_intel.main() == 0
    output = capsys.readouterr().out
    assert "SUBJECT: Morning Command" in output
    assert "MORNING COMMAND · 2026-07-13" in output
