"""Unit tests for the pure Morning Intel report functions."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.daily_intel import (
    INTERPRET_PROMPT,
    combine_report,
    detect_tracking_regression,
    measurement_epochs_for_report,
    measurement_epochs_in_window,
    render_report,
)


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


def test_measurement_window_fully_after_epoch_has_no_annotation(collected):
    collected["date"] = "2026-09-25"
    collected["measurement_epochs"] = measurement_epochs_for_report(collected["date"])

    report = render_report(collected)

    assert collected["measurement_epochs"] == []
    assert "measurement regime change" not in report


def test_measurement_window_straddle_is_annotated_and_serializable(collected):
    import json

    collected["date"] = "2026-07-29"
    collected["measurement_epochs"] = measurement_epochs_for_report(collected["date"])

    report = render_report(collected)
    snapshot = json.loads(json.dumps({**collected, "report": report}))

    warning = (
        "⚠ measurement regime change 2026-07-26 — comparison not like-for-like"
    )
    assert report.count(warning) == 2
    assert "(28d sessions, funnel, and constraint rates)." in report
    assert snapshot["measurement_epochs"] == [{
        "date": "2026-07-26",
        "scope": "sessions",
        "label": (
            "consent geo-gate deployed (f52d2722): non-EEA analytics default granted; "
            "sessions before this date captured only opted-in visitors and are not comparable"
        ),
    }]
    assert warning in snapshot["report"]
    assert "analytics collection changes, not demand changes" in INTERPRET_PROMPT


def test_empty_epoch_list_preserves_report_behavior(collected):
    baseline = render_report(deepcopy(collected))
    collected["measurement_epochs"] = []

    assert render_report(collected) == baseline
    assert measurement_epochs_in_window(
        "2026-07-01", "2026-07-31", epochs=[]) == []


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


def test_collect_checkout_gated_brand_is_not_broken(monkeypatch):
    from scripts import daily_intel

    def fake_http(url, data=None, headers=None, timeout=25):
        if url.endswith("/health"):
            return 200, "ok"
        return 400, '{"error": "XC Ski Labs does not support training-plan generation yet"}'

    monkeypatch.setattr(daily_intel, "_http", fake_http)
    out = daily_intel.collect_checkout("xcski")
    assert out["plans_gated"] is True
    assert out["error"] == ""


def test_collect_checkout_real_400_still_fails(monkeypatch):
    from scripts import daily_intel

    def fake_http(url, data=None, headers=None, timeout=25):
        if url.endswith("/health"):
            return 200, "ok"
        return 400, '{"error": "Valid email is required"}'

    monkeypatch.setattr(daily_intel, "_http", fake_http)
    out = daily_intel.collect_checkout("gravelgod")
    assert out["ok"] is False
    assert "checkout=400" in out["error"]


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


def test_collect_mission_control_reads_newest_rows_past_the_1000_row_cap(monkeypatch):
    """Regression: gg_sequence_sends crossed 1000 rows on 2026-08-26 and the
    collector — which sorted ascending and capped at 1000 — stopped seeing
    any send in the 24h window, reporting "0 emails sent" for eight days
    while the scheduler was sending daily. Every capped select must page
    newest-first so the recent windows are always inside the page."""
    import sys
    import types
    from datetime import datetime, timedelta, timezone

    from scripts import daily_intel

    now = datetime.now(timezone.utc)
    iso = lambda dt: dt.isoformat()  # noqa: E731 — PostgREST returns ISO 8601 strings

    old_sends = [
        {"id": f"s-old-{i}", "enrollment_id": "e-old", "template": "old",
         "status": "sent", "sent_at": iso(now - timedelta(days=200, minutes=-i)),
         "opened_at": None, "clicked_at": None}
        for i in range(1100)
    ]
    new_sends = [
        {"id": "s-new-1", "enrollment_id": "e-new", "template": "prep_kit_delivery",
         "status": "clicked", "sent_at": iso(now - timedelta(hours=3)),
         "opened_at": iso(now - timedelta(hours=2)),
         "clicked_at": iso(now - timedelta(hours=1))},
        {"id": "s-new-2", "enrollment_id": "e-new", "template": "welcome_value",
         "status": "sent", "sent_at": iso(now - timedelta(hours=2)),
         "opened_at": None, "clicked_at": None},
        {"id": "s-new-3", "enrollment_id": "e-old", "template": "sober_repitch",
         "status": "sent", "sent_at": iso(now - timedelta(minutes=30)),
         "opened_at": None, "clicked_at": None},
    ]
    enrollments = [
        {"id": "e-old", "contact_email": "old@example.com", "contact_name": "Old",
         "sequence_id": "nurture_v1", "current_step": 3, "status": "completed",
         "enrolled_at": iso(now - timedelta(days=100)), "source": "kit",
         "source_data": {"brand": "gravelgod", "race_name": "Unbound"}},
        {"id": "e-new", "contact_email": "new@example.com", "contact_name": "New",
         "sequence_id": "kit_delivery_v1", "current_step": 1, "status": "completed",
         "enrolled_at": iso(now - timedelta(hours=4)), "source": "kit",
         "source_data": {"brand": "gravelgod", "race_name": "The Rift"}},
        {"id": "e-new-2", "contact_email": "new2@example.com", "contact_name": "",
         "sequence_id": "road_kit_delivery_v1", "current_step": 0, "status": "active",
         "enrolled_at": iso(now - timedelta(hours=1)), "source": "kit",
         "source_data": {"brand": "roadielabs", "race_name": "Haute Route"}},
    ]
    tables = {"gg_sequence_sends": old_sends + new_sends,
              "gg_sequence_enrollments": enrollments}

    fake = types.ModuleType("mission_control.supabase_client")

    def select(table, columns="*", match=None, order=None, order_desc=False,
               limit=None, offset=None):
        # Mirrors PostgREST: sort by `order` (ascending unless order_desc),
        # then cap at `limit`. Ascending + limit=1000 returns the OLDEST page.
        rows = list(tables[table])
        for k, v in (match or {}).items():
            rows = [r for r in rows if r.get(k) == v]
        if order:
            rows.sort(key=lambda r: r.get(order) or "", reverse=order_desc)
        if limit:
            rows = rows[:limit]
        return [dict(r) for r in rows]

    fake.select = select
    fake.get_audit_log = lambda limit=50: []
    monkeypatch.setitem(sys.modules, "mission_control.supabase_client", fake)
    import mission_control
    monkeypatch.setattr(mission_control, "supabase_client", fake, raising=False)

    out = daily_intel.collect_mission_control()

    assert out["emails_sent_24h"] == 3
    assert out["opens_24h"] == 1
    assert out["clicks_24h"] == 1
    assert out["new_leads_24h"] == 2
    assert out["leads_by_brand"] == {"gravelgod": 1, "roadielabs": 1}
    hot = {lead["email"]: lead for lead in out["hot_leads_14d"]}
    assert set(hot) == {"new@example.com", "new2@example.com"}
    assert hot["new@example.com"]["opens"] == 1
    assert hot["new@example.com"]["clicks"] == 1
    assert hot["new@example.com"]["race"] == "The Rift"
