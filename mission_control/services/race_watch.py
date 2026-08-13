"""Daily notifications for Gravel God race-entry watchers."""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from mission_control import supabase_client as db
from mission_control.services.sequence_engine import _inject_unsubscribe, _send_email_sync

logger = logging.getLogger(__name__)

INTEL_URL = "https://gravelgodcycling.com/race-intel.json"
_USER_AGENT = "GG-MissionControl/1.0"
_SETTING_KEY = "race_watch_intel"
_MAX_SENDS = 50
_intel_cache: dict[str, list[dict]] = {}
_last_error = ""


def _valid_intel(value) -> bool:
    return isinstance(value, dict) and all(isinstance(events, list) for events in value.values())


def _fetch_intel_sync() -> dict[str, list[dict]]:
    """Fetch race intel with the identifying UA and persistent last-good fallback."""
    global _intel_cache, _last_error
    try:
        req = urllib.request.Request(INTEL_URL, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as response:
            value = json.load(response)
        if not _valid_intel(value):
            raise ValueError("race intel response was not an event dictionary")
        _intel_cache = value
        _last_error = ""
        try:
            db.set_setting(_SETTING_KEY, json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "intel": value}))
        except Exception as exc:
            logger.warning("race-watch DB cache write failed: %s", exc)
        return _intel_cache
    except Exception as exc:
        _last_error = repr(exc)
        if not _intel_cache:
            try:
                stored = json.loads(db.get_setting(_SETTING_KEY) or "{}")
                value = stored.get("intel") or {}
                if _valid_intel(value):
                    _intel_cache = value
            except Exception as fallback_exc:
                logger.warning("race-watch DB fallback failed: %s", fallback_exc)
        logger.warning("race-watch fetch failed (%s): %s — using cache (%d races)", INTEL_URL, exc, len(_intel_cache))
        return _intel_cache


def _event_date(event: dict) -> date | None:
    try:
        return date.fromisoformat(str(event.get("date", "")))
    except (TypeError, ValueError):
        return None


def pending_events(enrollment: dict, events: list[dict]) -> list[dict]:
    """Events newer than last notification, or newer than signup on first run."""
    source_data = enrollment.get("source_data") or {}
    baseline = source_data.get("last_notified_event_date") or str(enrollment.get("enrolled_at", ""))[:10]
    try:
        baseline_date = date.fromisoformat(baseline)
    except ValueError:
        return []
    return sorted(
        [event for event in events if _event_date(event) and _event_date(event) > baseline_date and isinstance(event.get("text"), str)],
        key=lambda event: (_event_date(event), event.get("text", "")),
    )


def _render_update(enrollment: dict, events: list[dict]) -> str:
    template = (Path(__file__).resolve().parent.parent / "templates" / "emails" / "sequences" / "race_watch_update.html").read_text()
    lines = "\n".join(f'{event["date"]} · {event["text"]}' for event in events)
    return template.replace("{ledger_lines}", escape(lines))


async def run_race_watch(now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    summary = {"watchers": 0, "notified": 0, "skipped_baseline": 0, "skipped_rate_cap": 0, "skipped_unsubscribed": 0, "capped": False}
    intel = await asyncio.to_thread(_fetch_intel_sync)
    if not intel:
        db.log_action("race_watch_aborted", "sequence", "race_watch_v1", f"no race intel available — {_last_error or 'unknown'}"[:500])
        return summary

    rows = db.select("gg_sequence_enrollments", columns="id,sequence_id,contact_email,contact_name,source_data,status,enrolled_at")
    unsubscribed = {row.get("contact_email") for row in rows if row.get("status") == "unsubscribed"}
    watchers = [row for row in rows if row.get("sequence_id") == "race_watch_v1" and row.get("status") in ("active", "completed")]
    summary["watchers"] = len(watchers)
    for enrollment in watchers:
        if summary["notified"] >= _MAX_SENDS:
            summary["capped"] = True
            break
        email = enrollment.get("contact_email")
        if email in unsubscribed:
            summary["skipped_unsubscribed"] += 1
            continue
        source_data = enrollment.get("source_data") or {}
        events = pending_events(enrollment, intel.get(source_data.get("race_slug"), []))
        if not events:
            summary["skipped_baseline"] += 1
            continue
        last_notified = source_data.get("last_notified_at")
        if last_notified:
            try:
                if now - datetime.fromisoformat(last_notified) < timedelta(days=7):
                    summary["skipped_rate_cap"] += 1
                    continue
            except ValueError:
                pass
        subject = f'{source_data.get("race_name") or source_data.get("race_slug")}: update'
        html = _inject_unsubscribe(_render_update(enrollment, events), email)
        resend_id = await asyncio.to_thread(_send_email_sync, email, subject, html, "gravelgod")
        newest = max(_event_date(event) for event in events)
        updated = dict(source_data)
        updated.update({"last_notified_event_date": newest.isoformat(), "last_notified_at": now.isoformat()})
        db.update("gg_sequence_enrollments", {"source_data": updated}, {"id": enrollment["id"]})
        db.insert("gg_sequence_sends", {"enrollment_id": enrollment["id"], "step_index": -1, "template": "race_watch_update", "subject": subject, "resend_id": resend_id, "status": "sent"})
        db.log_action("race_watch_notified", "enrollment", str(enrollment["id"]), f'{email} — {source_data.get("race_slug")} — {len(events)} event(s)')
        summary["notified"] += 1
    logger.info("race-watch run: %s", summary)
    return summary
