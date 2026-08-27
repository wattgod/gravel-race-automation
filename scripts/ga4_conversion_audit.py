#!/usr/bin/env python3
"""Audit and narrowly correct Gravel God GA4 key-event configuration.

The default mode is read-only.  The only supported mutation removes
``cta_click`` from the property's key-event registry, then reads the registry
again and records before/after state.  Event collection is not changed.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ADMIN_ROOT = "https://analyticsadmin.googleapis.com/v1beta"
DATA_ROOT = "https://analyticsdata.googleapis.com/v1beta"
READ_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
EDIT_SCOPE = "https://www.googleapis.com/auth/analytics.edit"
PROPERTY_RE = re.compile(r"^properties/(\d+)$")
KEY_EVENT_RE = re.compile(r"^properties/(\d+)/keyEvents/([^/]+)$")
MAX_PAGES = 20


class Ga4AuditError(RuntimeError):
    """Safe operator-facing failure."""


def normalize_property(value: str) -> str:
    candidate = str(value or "").strip()
    if candidate.isdigit():
        candidate = f"properties/{candidate}"
    if not PROPERTY_RE.fullmatch(candidate):
        raise Ga4AuditError(
            "property must be a numeric GA4 property ID or properties/ID")
    return candidate


def parse_window(start_date: str, end_date: str) -> tuple[date, date]:
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (TypeError, ValueError) as exc:
        raise Ga4AuditError("dates must use YYYY-MM-DD") from exc
    if end < start:
        raise Ga4AuditError("end date must be on or after start date")
    if (end - start).days > 92:
        raise Ga4AuditError("audit window must be 93 days or fewer")
    return start, end


def authorized_session(credentials_path: Path, edit: bool = False):
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials

    scopes = [READ_SCOPE, EDIT_SCOPE] if edit else [READ_SCOPE]
    credentials = Credentials.from_service_account_file(
        str(credentials_path), scopes=scopes)
    return AuthorizedSession(credentials)


def _json_response(response: Any, operation: str) -> dict:
    status = int(getattr(response, "status_code", 0) or 0)
    if status < 200 or status >= 300:
        error_status = "unknown"
        try:
            body = response.json()
            error_status = str(
                (body.get("error") or {}).get("status") or "unknown")[:80]
        except (TypeError, ValueError, AttributeError):
            pass
        raise Ga4AuditError(
            f"{operation} failed (HTTP {status}, status={error_status})")
    if status == 204 or not getattr(response, "content", b""):
        return {}
    try:
        body = response.json()
    except (TypeError, ValueError, AttributeError) as exc:
        raise Ga4AuditError(f"{operation} returned invalid JSON") from exc
    if not isinstance(body, dict):
        raise Ga4AuditError(f"{operation} returned an invalid response shape")
    return body


def list_key_events(session: Any, property_name: str) -> list[dict]:
    events = []
    page_token = ""
    for _ in range(MAX_PAGES):
        params = {"pageSize": 200}
        if page_token:
            params["pageToken"] = page_token
        response = session.get(
            f"{ADMIN_ROOT}/{property_name}/keyEvents", params=params,
            timeout=30)
        body = _json_response(response, "key-event list")
        for event in body.get("keyEvents") or []:
            if not isinstance(event, dict):
                continue
            name = str(event.get("name") or "")
            event_name = str(event.get("eventName") or "")
            if not KEY_EVENT_RE.fullmatch(name) or not event_name:
                raise Ga4AuditError("key-event list returned an invalid resource")
            events.append({
                "name": name,
                "event_name": event_name,
                "counting_method": str(event.get("countingMethod") or "unspecified"),
                "default_value": event.get("defaultValue"),
                "create_time": str(event.get("createTime") or ""),
            })
        page_token = str(body.get("nextPageToken") or "")
        if not page_token:
            return sorted(events, key=lambda item: item["event_name"])
    raise Ga4AuditError("key-event pagination exceeded the safety limit")


def _run_report(session: Any, property_name: str, body: dict,
                operation: str) -> dict:
    response = session.post(
        f"{DATA_ROOT}/{property_name}:runReport", json=body, timeout=60)
    return _json_response(response, operation)


def _metric_map(report: dict, row: dict) -> dict[str, str]:
    headers = [str(item.get("name") or "")
               for item in report.get("metricHeaders") or []]
    values = [str(item.get("value") or "0")
              for item in row.get("metricValues") or []]
    return dict(zip(headers, values))


def event_report(session: Any, property_name: str,
                 start: date, end: date) -> list[dict]:
    body = {
        "dateRanges": [{"startDate": start.isoformat(),
                        "endDate": end.isoformat()}],
        "dimensions": [{"name": "eventName"}],
        "metrics": [
            {"name": "eventCount"},
            {"name": "totalUsers"},
            {"name": "keyEvents"},
        ],
        "limit": "10000",
    }
    report = _run_report(
        session, property_name, body, "event performance report")
    rows = []
    for row in report.get("rows") or []:
        dimensions = row.get("dimensionValues") or []
        event_name = str((dimensions[0] if dimensions else {}).get("value") or "")
        if not event_name:
            continue
        metrics = _metric_map(report, row)
        rows.append({
            "event_name": event_name,
            "event_count": int(float(metrics.get("eventCount", "0"))),
            "total_users": int(float(metrics.get("totalUsers", "0"))),
            "key_events": float(metrics.get("keyEvents", "0")),
        })
    return sorted(rows, key=lambda item: (-item["key_events"], item["event_name"]))


def purchase_report(session: Any, property_name: str,
                    start: date, end: date) -> list[dict]:
    body = {
        "dateRanges": [{"startDate": start.isoformat(),
                        "endDate": end.isoformat()}],
        "dimensions": [{"name": "transactionId"}],
        "metrics": [
            {"name": "eventCount"},
            {"name": "totalUsers"},
            {"name": "purchaseRevenue"},
        ],
        "dimensionFilter": {
            "filter": {
                "fieldName": "eventName",
                "stringFilter": {
                    "matchType": "EXACT", "value": "purchase",
                    "caseSensitive": True,
                },
            },
        },
        "limit": "10000",
    }
    report = _run_report(
        session, property_name, body, "purchase transaction report")
    rows = []
    for row in report.get("rows") or []:
        dimensions = row.get("dimensionValues") or []
        transaction_id = str(
            (dimensions[0] if dimensions else {}).get("value") or "(not set)")
        metrics = _metric_map(report, row)
        rows.append({
            # Transaction IDs are retained because they are the required
            # reconciliation join and are not customer PII.
            "transaction_id": transaction_id,
            "event_count": int(float(metrics.get("eventCount", "0"))),
            "total_users": int(float(metrics.get("totalUsers", "0"))),
            "purchase_revenue": float(metrics.get("purchaseRevenue", "0")),
        })
    return sorted(rows, key=lambda item: item["transaction_id"])


def _event_controls(events: list[dict], key_events: list[dict]) -> dict:
    keyed_names = {item["event_name"] for item in key_events}
    key_rows = [item for item in events if item["event_name"] in keyed_names]
    total = sum(item["key_events"] for item in key_rows)
    cta = next((item for item in key_rows
                if item["event_name"] == "cta_click"), None)
    return {
        "configured_key_event_count": len(key_events),
        "observed_key_events": total,
        "cta_click_key_events": cta["key_events"] if cta else 0,
        "cta_click_share_of_observed_key_events": (
            round(cta["key_events"] / total, 6) if cta and total else 0),
    }


def _purchase_controls(rows: list[dict]) -> dict:
    missing = {"", "(not set)", "(other)"}
    reported = [item for item in rows if item["transaction_id"] not in missing]
    return {
        "purchase_events": sum(item["event_count"] for item in rows),
        "reported_transaction_ids": len(reported),
        "missing_transaction_id_events": sum(
            item["event_count"] for item in rows
            if item["transaction_id"] in missing),
        "duplicate_transaction_id_rows": sum(
            1 for item in reported if item["event_count"] > 1),
        "purchase_revenue": round(
            sum(item["purchase_revenue"] for item in rows), 2),
    }


def build_audit(session: Any, property_name: str, start: date, end: date,
                mode: str = "audit") -> dict:
    before = list_key_events(session, property_name)
    events = event_report(session, property_name, start, end)
    purchases = purchase_report(session, property_name, start, end)
    action = {
        "requested": mode,
        "status": "read_only",
        "deleted_resource": "",
    }
    after = before
    if mode == "demote_cta_click":
        matches = [item for item in before if item["event_name"] == "cta_click"]
        if len(matches) > 1:
            raise Ga4AuditError("multiple cta_click key-event resources found")
        if matches:
            resource = matches[0]["name"]
            match = KEY_EVENT_RE.fullmatch(resource)
            property_id = PROPERTY_RE.fullmatch(property_name).group(1)
            if not match or match.group(1) != property_id:
                raise Ga4AuditError("cta_click resource does not belong to the property")
            response = session.delete(
                f"{ADMIN_ROOT}/{resource}", timeout=30)
            _json_response(response, "cta_click key-event deletion")
            action = {
                "requested": mode,
                "status": "deleted",
                "deleted_resource": resource,
            }
            after = list_key_events(session, property_name)
            if any(item["event_name"] == "cta_click" for item in after):
                raise Ga4AuditError("cta_click remained a key event after deletion")
        else:
            action = {
                "requested": mode,
                "status": "already_not_a_key_event",
                "deleted_resource": "",
            }

    return {
        "schema": "ga4_conversion_authority_audit/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "property": property_name,
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "timezone": "property_reporting_timezone",
        },
        "key_events_before": before,
        "key_events_after": after,
        "event_performance": events,
        "purchase_transactions": purchases,
        "controls": {
            "before": _event_controls(events, before),
            "after": _event_controls(events, after),
            "purchases": _purchase_controls(purchases),
        },
        "action": action,
        "boundaries": [
            "GA4 is behavioral evidence and does not establish collected cash.",
            "Reports can change during the GA4 attribution and processing window.",
            "Key-event deletion does not stop collection of the underlying event.",
            "Purchase transaction IDs still require a provider-ledger join.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--property", required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--mode", choices=("audit", "demote_cta_click"),
                        default="audit")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    property_name = normalize_property(args.property)
    start, end = parse_window(args.start_date, args.end_date)
    session = authorized_session(
        args.credentials, edit=args.mode == "demote_cta_click")
    receipt = build_audit(session, property_name, start, end, mode=args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "schema": receipt["schema"],
        "property": receipt["property"],
        "period": receipt["period"],
        "controls": receipt["controls"],
        "action": receipt["action"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
