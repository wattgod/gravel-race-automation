import importlib.util
from datetime import date
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parent.parent / "scripts" / "ga4_conversion_audit.py"
SPEC = importlib.util.spec_from_file_location("ga4_conversion_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class Response:
    def __init__(self, body=None, status=200):
        self._body = {} if body is None else body
        self.status_code = status
        self.content = b"" if status == 204 else b"{}"

    def json(self):
        return self._body


class Session:
    def __init__(self):
        self.deleted = []
        self.after_delete = False
        self.posts = 0

    @staticmethod
    def _key_events(include_cta=True):
        rows = [{
            "name": "properties/123/keyEvents/purchase-key",
            "eventName": "purchase", "countingMethod": "ONCE_PER_EVENT",
        }, {
            "name": "properties/123/keyEvents/email-key",
            "eventName": "email_capture", "countingMethod": "ONCE_PER_EVENT",
        }]
        if include_cta:
            rows.append({
                "name": "properties/123/keyEvents/cta-key",
                "eventName": "cta_click", "countingMethod": "ONCE_PER_EVENT",
            })
        return rows

    def get(self, url, **kwargs):
        assert url.endswith("/properties/123/keyEvents")
        return Response({"keyEvents": self._key_events(not self.after_delete)})

    def post(self, url, json=None, **kwargs):
        assert url.endswith("/properties/123:runReport")
        self.posts += 1
        if self.posts == 1:
            return Response({
                "metricHeaders": [
                    {"name": "eventCount"}, {"name": "totalUsers"},
                    {"name": "keyEvents"},
                ],
                "rows": [
                    {"dimensionValues": [{"value": "cta_click"}],
                     "metricValues": [
                         {"value": "178"}, {"value": "132"}, {"value": "178"}]},
                    {"dimensionValues": [{"value": "purchase"}],
                     "metricValues": [
                         {"value": "7"}, {"value": "7"}, {"value": "7"}]},
                    {"dimensionValues": [{"value": "email_capture"}],
                     "metricValues": [
                         {"value": "9"}, {"value": "9"}, {"value": "9"}]},
                ],
            })
        return Response({
            "metricHeaders": [
                {"name": "eventCount"}, {"name": "totalUsers"},
                {"name": "purchaseRevenue"},
            ],
            "rows": [
                {"dimensionValues": [{"value": "order-1"}],
                 "metricValues": [
                     {"value": "2"}, {"value": "1"}, {"value": "200"}]},
                {"dimensionValues": [{"value": "(not set)"}],
                 "metricValues": [
                     {"value": "1"}, {"value": "1"}, {"value": "145"}]},
            ],
        })

    def delete(self, url, **kwargs):
        self.deleted.append(url)
        self.after_delete = True
        return Response({}, status=200)


def test_normalization_and_window_validation():
    assert audit.normalize_property("123") == "properties/123"
    assert audit.normalize_property("properties/123") == "properties/123"
    with pytest.raises(audit.Ga4AuditError):
        audit.normalize_property("accounts/123")
    assert audit.parse_window("2026-07-30", "2026-08-26") == (
        date(2026, 7, 30), date(2026, 8, 26))
    with pytest.raises(audit.Ga4AuditError):
        audit.parse_window("2026-08-27", "2026-08-26")


def test_read_only_audit_preserves_key_events_and_surfaces_authority_gaps():
    session = Session()
    receipt = audit.build_audit(
        session, "properties/123", date(2026, 7, 30), date(2026, 8, 26))

    assert session.deleted == []
    assert receipt["action"]["status"] == "read_only"
    assert receipt["controls"]["before"] == {
        "configured_key_event_count": 3,
        "observed_key_events": 194.0,
        "cta_click_key_events": 178.0,
        "cta_click_share_of_observed_key_events": 0.917526,
    }
    assert receipt["controls"]["purchases"] == {
        "purchase_events": 3,
        "reported_transaction_ids": 1,
        "missing_transaction_id_events": 1,
        "duplicate_transaction_id_rows": 1,
        "purchase_revenue": 345.0,
    }


def test_demote_cta_click_deletes_only_the_exact_key_event_and_reads_back():
    session = Session()
    receipt = audit.build_audit(
        session, "properties/123", date(2026, 7, 30), date(2026, 8, 26),
        mode="demote_cta_click")

    assert session.deleted == [
        f"{audit.ADMIN_ROOT}/properties/123/keyEvents/cta-key"]
    assert receipt["action"]["status"] == "deleted"
    assert {item["event_name"] for item in receipt["key_events_after"]} == {
        "purchase", "email_capture"}
    assert receipt["controls"]["after"]["cta_click_key_events"] == 0


def test_demote_is_idempotent_when_cta_click_is_already_not_keyed():
    session = Session()
    session.after_delete = True
    receipt = audit.build_audit(
        session, "properties/123", date(2026, 7, 30), date(2026, 8, 26),
        mode="demote_cta_click")
    assert session.deleted == []
    assert receipt["action"]["status"] == "already_not_a_key_event"


def test_provider_errors_are_sanitized():
    response = Response({
        "error": {"status": "PERMISSION_DENIED", "message": "secret detail"}},
        status=403)
    with pytest.raises(audit.Ga4AuditError) as error:
        audit._json_response(response, "key-event list")
    assert "PERMISSION_DENIED" in str(error.value)
    assert "secret detail" not in str(error.value)
