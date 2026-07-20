"""Unit tests for the pure Morning Intel report functions."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.daily_intel import combine_report, detect_tracking_regression, render_report


def _ga4(sessions=20, cta=2):
    return {
        "ok": True,
        "sessions": sessions,
        "sessions_7d_avg": 18.5,
        "funnel": {
            "cta_click": cta,
            "form_start": 2,
            "form_submit": 1,
            "begin_checkout": 0,
            "purchase": 0,
        },
        "top_pages": [{"path": "/race/test/", "views": 7}],
        "channel_mix": {"Organic Search": 12, "Direct": 8},
        "top_landing": [{"path": "/race/test/", "sessions": 5}],
    }


@pytest.fixture
def collected():
    return {
        "date": "2026-07-20",
        "ga4": {
            "gravelgod": _ga4(),
            "roadielabs": _ga4(sessions=3, cta=0),
        },
        "checkout": {
            "gravelgod": {"ok": True},
            "roadielabs": {"ok": True},
        },
        "mission_control": {
            "ok": True,
            "leads_by_brand": {"gravelgod": 2, "roadielabs": 1},
            "hot_leads_14d": [{
                "name": "Ada Rider",
                "email": "ada@example.com",
                "race": "Test Gravel",
                "sequence": "welcome_v1",
                "step": 2,
                "opens": 3,
                "clicks": 1,
            }],
            "errors_24h": [],
        },
        "commerce_ledger": {
            "ok": True,
            "failed_orders": [],
            "orders": [],
            "recoveries": [],
            "questionnaire_starts": 0,
        },
        "constraint": {
            "ok": True,
            "binding_constraint": "traffic",
            "cta_rate_pct": 4.05,
            "cta_to_submit_pct": 60.5,
            "submit_to_purchase_pct": 11.5,
            "sessions_per_day_needed_for_1_sale": 354,
            "sessions_per_day": 37.9,
        },
        "social": {"ok": True, "accounts_live": False},
        "workflows": {"ok": True, "latest": {"regression-tests.yml": "success"}},
        "report_issues": [],
    }


def test_render_report_has_deterministic_sections_and_readable_funnel(collected):
    report = render_report(collected)

    assert report.startswith("## NUMBERS")
    assert "cta 2 → form_start 2 → submit 1 → checkout 0 → purchase 0" in report
    assert "{'cta_click'" not in report
    assert "## TRAFFIC" in report
    assert "Gravel God top pages" in report
    assert "Roadie Labs:** 3 sessions; near-zero traffic" in report
    assert "## COMMERCE (GROUND TRUTH)" in report
    assert "no orders, cart recoveries, or questionnaire starts" in report
    assert "binding constraint: traffic" in report
    assert "354; actual: 37.9" in report
    assert "Ada Rider <ada@example.com> — Test Gravel; welcome_v1 step 2" in report
    assert "## SOCIAL" not in report
    assert "###" not in report
    assert report.endswith("- nothing broken.")


def test_render_report_failed_orders_are_first_and_broken_is_complete(collected):
    collected["commerce_ledger"].update({
        "failed_orders": [{
            "name": "Failed Rider",
            "email": "failed@example.com",
            "product_type": "training_plan",
            "success": False,
            "error": "delivery timeout",
        }],
        "orders": [{
            "name": "Paid Rider",
            "email": "paid@example.com",
            "product_type": "training_plan",
            "success": True,
        }],
        "recoveries": [{"email": "cart@example.com", "product": "training_plan"}],
        "questionnaire_starts": 2,
    })
    collected["checkout"]["roadielabs"] = {"ok": False, "error": "checkout=500"}
    collected["mission_control"]["errors_24h"] = [
        {"action": "sequence_send_error", "details": "Resend 500"},
    ]
    collected["workflows"]["latest"]["link-check.yml"] = "failure"
    collected["report_issues"] = ["possible tracking regression"]

    report = render_report(collected)
    commerce = report.split("## COMMERCE (GROUND TRUTH)\n", 1)[1].split("\n\n## CONSTRAINT", 1)[0]

    assert commerce.index("**FAILED ORDER:**") < commerce.index("- order: Paid Rider")
    assert "fulfillment FAILED: delivery timeout" in commerce
    assert "fulfillment fulfilled" in commerce
    assert "cart recovery: cart@example.com" in commerce
    assert "questionnaire starts: 2" in commerce
    assert "checkout Roadie Labs FAIL: checkout=500" in report
    assert "Mission Control sequence_send_error: Resend 500" in report
    assert "workflow link-check.yml: failure" in report
    assert "possible tracking regression" in report


def test_render_report_includes_social_only_when_accounts_are_live(collected):
    collected["social"] = {
        "ok": True,
        "accounts_live": True,
        "queued_today": 1,
        "queued_yesterday": 2,
        "posts": [{"brand": "gravelgod", "race": "Test Gravel", "kind": "preview"}],
    }

    report = render_report(collected)

    assert "## SOCIAL" in report
    assert "queued: 1 today; 2 yesterday" in report
    assert "gravelgod: Test Gravel — preview" in report


def test_detect_tracking_regression_after_three_qualifying_days():
    today = {"ga4": {"gravelgod": _ga4(sessions=27, cta=0)}}
    priors = [
        {"ga4": {"gravelgod": _ga4(sessions=24, cta=0)}},
        {"ga4": {"gravelgod": _ga4(sessions=31, cta=0)}},
    ]

    warning = detect_tracking_regression(today, priors)

    assert warning == (
        "possible GA4 event-tracking regression: 27 sessions but "
        "0 cta_click for 3+ consecutive days"
    )


def test_detect_tracking_regression_requires_explicit_cta_counts():
    today = {"ga4": {"gravelgod": _ga4(sessions=20, cta=0)}}
    priors = [
        {"ga4": {"gravelgod": _ga4(sessions=20, cta=0)}},
        {"ga4": {"gravelgod": _ga4(sessions=20, cta=0)}},
    ]
    del priors[1]["ga4"]["gravelgod"]["funnel"]["cta_click"]

    assert detect_tracking_regression(today, priors) is None


@pytest.mark.parametrize(
    ("today_sessions", "today_cta", "prior_index", "prior_change"),
    [
        (14, 0, None, None),
        (20, 1, None, None),
        (20, 0, 0, {"sessions": 14}),
        (20, 0, 1, {"cta_click": 1}),
        (20, 0, 0, {"ok": False}),
    ],
)
def test_detect_tracking_regression_guard_conditions(
        today_sessions, today_cta, prior_index, prior_change):
    today = {"ga4": {"gravelgod": _ga4(sessions=today_sessions, cta=today_cta)}}
    priors = [
        {"ga4": {"gravelgod": _ga4(sessions=20, cta=0)}},
        {"ga4": {"gravelgod": _ga4(sessions=20, cta=0)}},
    ]
    if prior_index is not None:
        g = priors[prior_index]["ga4"]["gravelgod"]
        for key, value in prior_change.items():
            if key == "cta_click":
                g["funnel"][key] = value
            else:
                g[key] = value

    assert detect_tracking_regression(today, priors) is None


def test_combine_report_keeps_deterministic_core_between_narration(collected):
    core = render_report(deepcopy(collected))
    narration = "## TOP LINE\n- 20 sessions.\n\n## DO TODAY\n- nothing — let it run"

    report = combine_report(narration, core)

    assert report.index("## TOP LINE") < report.index("## NUMBERS")
    assert report.index("## BROKEN") < report.index("## DO TODAY")


# ── Delivery-guard tests (email must always send) ───────────────────────

def test_safe_render_survives_shape_drift(collected):
    from scripts import daily_intel
    bad = deepcopy(collected)
    bad["commerce_ledger"] = {"ok": True, "orders": ["not-a-dict"]}
    out = daily_intel.safe_render(bad)
    assert "## BROKEN" in out
    assert "report rendering crashed" in out


def test_load_prior_snapshots_skips_non_dict(tmp_path, monkeypatch):
    from scripts import daily_intel
    monkeypatch.setattr(daily_intel, "SNAPSHOT_DIR", tmp_path)
    (tmp_path / "2026-07-19.json").write_text("[]")
    assert daily_intel.load_prior_snapshots("2026-07-20") == []


def test_no_llm_does_not_extend_failure_streak(tmp_path, monkeypatch):
    from scripts import daily_intel
    monkeypatch.setattr(daily_intel, "SNAPSHOT_DIR", tmp_path)
    (tmp_path / "2026-07-19.json").write_text('{"interpretation_ok": null}')
    (tmp_path / "2026-07-18.json").write_text('{"interpretation_ok": false}')
    assert daily_intel.interpretation_failure_streak("2026-07-20") == 1


def test_main_sends_email_even_when_everything_downstream_breaks(
        tmp_path, monkeypatch, capsys):
    """Collectors return drifted shapes, interpretation raises, snapshots are
    unwritable — send_email must still be called."""
    from scripts import daily_intel

    def boom(*a, **k):
        raise RuntimeError("boom")

    for name in ("collect_ga4", "collect_checkout", "collect_mission_control",
                 "collect_commerce_ledger", "collect_social", "collect_workflows"):
        monkeypatch.setattr(daily_intel, name, boom)
    monkeypatch.setattr(daily_intel, "render_report", boom)
    monkeypatch.setattr(daily_intel, "interpret", boom)
    monkeypatch.setattr(daily_intel, "load_trend", lambda: [])
    # unwritable snapshot dir: a path whose parent is a file
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    monkeypatch.setattr(daily_intel, "SNAPSHOT_DIR", blocker / "nope")

    sent = {}
    monkeypatch.setattr(daily_intel, "send_email",
                        lambda subject, report: sent.update(
                            subject=subject, report=report) or "msg_test")
    monkeypatch.setattr("sys.argv", ["daily_intel.py"])

    assert daily_intel.main() == 0
    assert "INTERPRETATION BROKEN" in sent["subject"]
    assert "snapshot write failed" in sent["report"]
