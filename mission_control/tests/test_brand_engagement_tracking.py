"""Blind-tracking detector: a brand with sends but zero opens/clicks."""

from datetime import datetime, timedelta, timezone


def _now(days_ago=1):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _seed(fake_db, sequence_id, n, opens=0, clicks=0, days_ago=1, prefix=None):
    prefix = prefix or sequence_id
    for i in range(n):
        eid = f"{prefix}-e{i}"
        fake_db.store["gg_sequence_enrollments"].append(
            {"id": eid, "sequence_id": sequence_id})
        fake_db.store["gg_sequence_sends"].append({
            "id": f"{prefix}-s{i}",
            "enrollment_id": eid,
            "resend_id": f"{prefix}-r{i}",
            "sent_at": _now(days_ago),
            "opened_at": _now(days_ago) if i < opens else None,
            "clicked_at": _now(days_ago) if i < clicks else None,
        })


def _by_domain(checks):
    return {c["name"].split(": ", 1)[1]: c for c in checks}


class TestBrandTrackingChecks:
    def test_blind_brand_warns_with_resend_fix(self):
        from mission_control.services.triage import brand_tracking_checks
        checks = _by_domain(brand_tracking_checks({
            "gravelgod": {"sends": 100, "opens": 45, "clicks": 6},
            "roadielabs": {"sends": 30, "opens": 0, "clicks": 0},
        }))
        assert checks["gravelgodcycling.com"]["status"] == "ok"
        road = checks["roadielabs.com"]
        assert road["status"] == "warning"
        assert "Enable tracking metrics" in road["detail"]
        assert "roadielabs.com" in road["detail"]

    def test_too_few_sends_is_not_flagged(self):
        from mission_control.services.triage import brand_tracking_checks
        checks = _by_domain(brand_tracking_checks(
            {"xcskilabs": {"sends": 5, "opens": 0, "clicks": 0}}))
        assert checks["xcskilabs.com"]["status"] == "ok"
        assert "too few" in checks["xcskilabs.com"]["detail"]

    def test_any_click_counts_as_tracked(self):
        from mission_control.services.triage import brand_tracking_checks
        checks = brand_tracking_checks(
            {"roadielabs": {"sends": 40, "opens": 0, "clicks": 1}})
        assert checks[0]["status"] == "ok"

    def test_brand_without_sends_is_omitted(self):
        from mission_control.services.triage import brand_tracking_checks
        assert brand_tracking_checks({}) == []


class TestEngagementFromDb:
    def test_groups_by_sequence_brand(self, fake_db):
        from mission_control.services.triage import _check_brand_engagement_tracking
        _seed(fake_db, "welcome_v1", 25, opens=10, clicks=2)
        _seed(fake_db, "road_welcome_v1", 25)
        _seed(fake_db, "xc_welcome_v1", 3)
        checks = _by_domain(_check_brand_engagement_tracking())
        assert checks["gravelgodcycling.com"]["status"] == "ok"
        assert checks["roadielabs.com"]["status"] == "warning"
        assert checks["xcskilabs.com"]["status"] == "ok"

    def test_old_sends_outside_window_ignored(self, fake_db):
        from mission_control.services.triage import _check_brand_engagement_tracking
        _seed(fake_db, "road_welcome_v1", 25, days_ago=120)
        assert _check_brand_engagement_tracking() == []

    def test_expanded_health_includes_tracking(self, fake_db, monkeypatch):
        from mission_control.services import triage
        monkeypatch.setattr(triage, "_check_self_health",
                            lambda: {"name": "Self-ping", "status": "ok", "detail": ""})
        monkeypatch.setattr(triage, "_check_resend_connectivity",
                            lambda: {"name": "Resend API", "status": "ok", "detail": ""})
        _seed(fake_db, "road_welcome_v1", 25)
        names = [c["name"] for c in triage.get_expanded_health()["checks"]]
        assert "Email tracking: roadielabs.com" in names


class TestWebhookMatchesEveryBrand:
    """record_event matches on resend_id alone, so road/xc events land too."""

    def test_road_and_xc_open_click_recorded(self, fake_db):
        from mission_control.services.sequence_engine import record_event
        _seed(fake_db, "road_welcome_v1", 1)
        _seed(fake_db, "xc_welcome_v1", 1)
        assert record_event("road_welcome_v1-r0", "email.opened")
        assert record_event("xc_welcome_v1-r0", "email.clicked")
        sends = {s["resend_id"]: s for s in fake_db.store["gg_sequence_sends"]}
        assert sends["road_welcome_v1-r0"]["opened_at"]
        assert sends["xc_welcome_v1-r0"]["clicked_at"]
