#!/usr/bin/env python3
"""Morning Intel — daily report for both brands.

Collects GA4, checkout health, Mission Control activity + errors, and
workflow statuses; renders the factual core deterministically; asks Claude
only for the subject hook, TOP LINE, and DO TODAY; emails
gravelgodcoaching@gmail.com; snapshots everything to data/intel-snapshots/ so
trends compound. Spec: docs/specs/daily-intel-report.md.

Every collector is fail-soft: a broken source becomes a BROKEN line in the
report — the email always sends (order-killer lesson: failures loud to the
coach, never silent).

Usage:
    python3 scripts/daily_intel.py                # collect + interpret + send + snapshot
    python3 scripts/daily_intel.py --dry-run      # everything except the send
    python3 scripts/daily_intel.py --no-llm       # skip interpretation (plain digest)

Env (see .github/workflows/daily-intel.yml):
    GA4_CREDENTIALS, GG_GA4_PROPERTY_ID, RL_GA4_PROPERTY_ID,
    SUPABASE_URL, SUPABASE_SERVICE_KEY, RESEND_API_KEY, ANTHROPIC_API_KEY,
    INTEL_MODEL (default claude-sonnet-5), INTEL_TO, CHECKOUT_WEBHOOK_URL
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "intel-snapshots"
AEO_DIR = PROJECT_ROOT / "data" / "aeo"

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

WEBHOOK = (os.environ.get("CHECKOUT_WEBHOOK_URL")
           or "https://athlete-custom-training-plan-pipeline-production.up.railway.app").rstrip("/")
INTEL_TO = os.environ.get("INTEL_TO", "gravelgodcoaching@gmail.com")
INTEL_MODEL = os.environ.get("INTEL_MODEL", "claude-sonnet-5")

BRANDS = {
    "gravelgod": {
        "label": "Gravel God",
        "origin": "https://gravelgodcycling.com",
        "property_env": "GG_GA4_PROPERTY_ID",
        "monitor_email": "checkout-monitor@gravelgodcycling.com",
    },
    "roadielabs": {
        "label": "Roadie Labs",
        "origin": "https://roadielabs.com",
        "property_env": "RL_GA4_PROPERTY_ID",
        "monitor_email": "checkout-monitor@roadielabs.com",
    },
}

# The deployed gravel form JS predates the tp_* rename — both generations
# fire in the wild, so each stage counts the union (Jul 2026 investigation:
# June was form_start 33 / form_submit 20 / purchase 2, invisible to tp_*-only queries).
FUNNEL_STAGES = {
    "cta_click": ["cta_click"],
    "form_start": ["form_start", "tp_form_start"],
    "form_submit": ["form_submit", "tp_form_submit"],
    "begin_checkout": ["begin_checkout"],
    "purchase": ["purchase"],
}
FUNNEL_EVENTS = [e for evs in FUNNEL_STAGES.values() for e in evs]


def _http(url: str, data: dict | None = None, headers: dict | None = None,
          timeout: int = 25) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json",
                 "User-Agent": "morning-intel/1.0 (gravel-race-automation)",
                 **(headers or {})},
        method="POST" if data is not None else "GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500]
    except Exception as e:
        return 0, str(e)[:300]


def _safe(fn):
    """Run a collector; on any exception return {'ok': False, 'error': ...}."""
    try:
        out = fn()
        out.setdefault("ok", True)
        return out
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:400]}


# ── Collectors ──────────────────────────────────────────────────────────

def collect_ga4(brand: str) -> dict:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Metric, RunReportRequest,
    )

    creds = os.environ.get("GA4_CREDENTIALS", str(PROJECT_ROOT / "ga4-credentials.json"))
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", creds)
    prop = os.environ.get(BRANDS[brand]["property_env"], "")
    if not prop and brand == "gravelgod":
        prop = os.environ.get("GA4_PROPERTY_ID", "")  # legacy .env name
    prop = prop.strip().removeprefix("properties/")  # .env stores the full resource name
    if not prop:
        return {"ok": False, "error": f"{BRANDS[brand]['property_env']} not set"}
    client = BetaAnalyticsDataClient()
    y = (date.today() - timedelta(days=1)).isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()  # 7 full days ending yesterday

    def run(metrics, dimensions=None, date_from=y, date_to=y, limit=100):
        return client.run_report(RunReportRequest(
            property=f"properties/{prop}",
            date_ranges=[DateRange(start_date=date_from, end_date=date_to)],
            metrics=[Metric(name=m) for m in metrics],
            dimensions=[Dimension(name=d) for d in (dimensions or [])],
            limit=limit,
        ))

    totals = run(["sessions", "totalUsers", "screenPageViews"])
    t = totals.rows[0].metric_values if totals.rows else None
    week = run(["sessions"], date_from=week_ago, date_to=y)
    week_sessions = int(week.rows[0].metric_values[0].value) if week.rows else 0

    events = run(["eventCount"], ["eventName"])
    ev = {r.dimension_values[0].value: int(r.metric_values[0].value)
          for r in events.rows}

    pages = run(["screenPageViews"], ["pagePath"], limit=8)
    top_pages = [{"path": r.dimension_values[0].value,
                  "views": int(r.metric_values[0].value)} for r in pages.rows]

    # 28-day aggregates for the constraint math (precomputed — the
    # interpreter must never do arithmetic itself)
    m_ago = (date.today() - timedelta(days=29)).isoformat()
    agg = run(["sessions"], date_from=m_ago, date_to=y)
    sessions_28d = int(agg.rows[0].metric_values[0].value) if agg.rows else 0
    ev28 = run(["eventCount"], ["eventName"], date_from=m_ago, date_to=y)
    ev28d = {r.dimension_values[0].value: int(r.metric_values[0].value)
             for r in ev28.rows}
    funnel_28d = {stage: sum(ev28d.get(e, 0) for e in evs)
                  for stage, evs in FUNNEL_STAGES.items()}

    channels = run(["sessions"], ["sessionDefaultChannelGroup"], limit=8)
    channel_mix = {r.dimension_values[0].value: int(r.metric_values[0].value)
                   for r in channels.rows}

    landing = run(["sessions"], ["landingPagePlusQueryString"], limit=6)
    top_landing = [{"path": r.dimension_values[0].value.split("?")[0],
                    "sessions": int(r.metric_values[0].value)} for r in landing.rows]

    return {
        "sessions": int(t[0].value) if t else 0,
        "users": int(t[1].value) if t else 0,
        "pageviews": int(t[2].value) if t else 0,
        "sessions_7d_avg": round(week_sessions / 7, 1),
        "funnel": {stage: sum(ev.get(e, 0) for e in evs)
                   for stage, evs in FUNNEL_STAGES.items()},
        "abandoned_submits": max(0, sum(ev.get(e, 0) for e in FUNNEL_STAGES["form_submit"])
                                    - ev.get("purchase", 0)),
        "top_pages": top_pages,
        "channel_mix": channel_mix,
        "top_landing": top_landing,
        "sessions_28d": sessions_28d,
        "funnel_28d": funnel_28d,
    }


def collect_checkout(brand: str) -> dict:
    code, _ = _http(f"{WEBHOOK}/health")
    health_ok = code == 200
    race_date = (date.today() + timedelta(weeks=12)).isoformat()
    ccode, body = _http(f"{WEBHOOK}/api/create-checkout", data={
        "email": BRANDS[brand]["monitor_email"],
        "name": "Morning Intel Probe",
        "races": [{"priority": "A", "name": "Synthetic Monitor Race",
                   "date": race_date}],
    }, headers={"Origin": BRANDS[brand]["origin"]})
    stripe_ok = ccode == 200 and "checkout.stripe.com" in body
    return {"health_ok": health_ok, "stripe_checkout_ok": stripe_ok,
            "ok": health_ok and stripe_ok,
            "error": "" if (health_ok and stripe_ok) else f"health={code} checkout={ccode}"}


def collect_commerce_ledger() -> dict:
    """Ground truth from the webhook's /api/intel-stats (Railway volume logs):
    orders WITH fulfillment outcomes, cart recoveries, questionnaire starts."""
    secret = os.environ.get("CRON_SECRET", "")
    if not secret:
        return {"ok": False, "error": "CRON_SECRET not set"}
    code, body = _http(f"{WEBHOOK}/api/intel-stats",
                       headers={"X-Cron-Secret": secret})
    if code != 200:
        return {"ok": False, "error": f"intel-stats HTTP {code}: {body[:120]}"}
    return json.loads(body)


def compute_constraint(ga4_gravel: dict) -> dict:
    """Name the funnel's binding constraint from 28-day rates. Pure math,
    precomputed here so the interpreter only narrates."""
    if not ga4_gravel.get("ok"):
        return {"ok": False, "error": "no GA4 data"}
    s28 = ga4_gravel.get("sessions_28d") or 0
    f = ga4_gravel.get("funnel_28d") or {}
    cta, sub, pur = f.get("cta_click", 0), f.get("form_submit", 0), f.get("purchase", 0)
    days = 28
    rates = {
        "sessions_per_day": round(s28 / days, 1),
        "cta_rate_pct": round(100 * cta / s28, 2) if s28 else 0,
        "cta_to_submit_pct": round(100 * sub / cta, 1) if cta else 0,
        "submit_to_purchase_pct": round(100 * pur / sub, 1) if sub else 0,
        "purchases_28d": pur, "submits_28d": sub, "ctas_28d": cta,
    }
    # sessions/day needed for 1 purchase/day at current observed rates
    # (fall back through the funnel when a stage has no data yet)
    chain = (cta / s28 if s28 else 0) * (sub / cta if cta else 0) * (pur / sub if sub else 0)
    rates["sessions_per_day_needed_for_1_sale"] = (
        round(1 / chain) if chain > 0 else None)
    # binding constraint heuristic, top-down
    if s28 / days < 100:
        binding = ("traffic — at these volumes no funnel rate is even "
                   "measurable; nothing downstream is worth optimizing yet")
    elif cta == 0:
        binding = "cta_rate — sessions exist but nobody clicks toward a plan"
    elif sub == 0:
        binding = "form completion — clicks exist but nobody finishes intake"
    elif pur == 0:
        binding = "close rate — completed intakes aren't converting to payment"
    else:
        binding = "scaling — every stage has signal; grow the top"
    rates["binding_constraint"] = binding
    return {"ok": True, **rates}


def collect_mission_control() -> dict:
    sys.path.insert(0, str(PROJECT_ROOT))
    from mission_control import supabase_client as db

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    def recent(rows, field="created_at"):
        return [r for r in rows if (r.get(field) or "") >= cutoff]

    enrollments = db.select("gg_sequence_enrollments",
                            columns="sequence_id,source,source_data,enrolled_at,status",
                            order="enrolled_at", limit=1000)
    new_enr = recent(enrollments, field="enrolled_at")
    by_brand = {"gravelgod": 0, "roadielabs": 0}
    countdown = 0
    for e in new_enr:
        sd = e.get("source_data") or {}
        by_brand[sd.get("brand", "gravelgod")] = by_brand.get(sd.get("brand", "gravelgod"), 0) + 1
        if "countdown" in (e.get("sequence_id") or ""):
            countdown += 1

    sends = db.select("gg_sequence_sends",
                      columns="template,status,sent_at,opened_at,clicked_at",
                      order="sent_at", limit=1000)
    new_sends = recent(sends, field="sent_at")
    opened = sum(1 for s in sends if (s.get("opened_at") or "") >= cutoff)
    clicked = sum(1 for s in sends if (s.get("clicked_at") or "") >= cutoff)
    bounced = sum(1 for s in new_sends if s.get("status") == "bounced")

    # NOTE: gg_athletes is NOT written by the purchase path (verified Jul 2026
    # — real June sales never appeared there). Orders truth = GA4 purchase
    # events (see ga4 collector) + the [GG] FAILED emails for fulfillment.
    new_orders = []

    audit = db.get_audit_log(limit=200)
    errors = [
        {"action": a.get("action"), "details": (a.get("details") or "")[:160]}
        for a in recent(audit)
        if "error" in (a.get("action") or "").lower()
           or "fail" in (a.get("action") or "").lower()
    ]

    # Hot leads: recent enrollments with race context + engagement, so the
    # report can NAME people instead of counting them. Cap 8.
    two_weeks = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    recent_enr = [e for e in enrollments if (e.get("enrolled_at") or "") >= two_weeks]
    recent_ids = {e.get("id") for e in db.select(
        "gg_sequence_enrollments", columns="id,contact_email,enrolled_at",
        order="enrolled_at", limit=1000) if (e.get("enrolled_at") or "") >= two_weeks}
    id_sends = [x for x in db.select(
        "gg_sequence_sends", columns="enrollment_id,sent_at,opened_at,clicked_at,template",
        order="sent_at", limit=1000) if x.get("enrollment_id") in recent_ids]
    eng = {}
    for x in id_sends:
        d = eng.setdefault(x["enrollment_id"], {"opens": 0, "clicks": 0, "last_template": None})
        if x.get("opened_at"): d["opens"] += 1
        if x.get("clicked_at"): d["clicks"] += 1
        d["last_template"] = x.get("template")
    full_enr = db.select("gg_sequence_enrollments",
                         columns="id,contact_email,contact_name,sequence_id,current_step,status,enrolled_at,source_data",
                         order="enrolled_at", limit=1000)
    hot_leads = []
    seen_emails = set()
    for e in sorted(full_enr, key=lambda x: x.get("enrolled_at") or "", reverse=True):
        if (e.get("enrolled_at") or "") < two_weeks or e["contact_email"] in seen_emails:
            continue
        seen_emails.add(e["contact_email"])
        sd = e.get("source_data") or {}
        g = eng.get(e.get("id"), {})
        hot_leads.append({
            "email": e["contact_email"], "name": e.get("contact_name") or "",
            "race": sd.get("race_name") or "(no race given)",
            "brand": sd.get("brand", "gravelgod"),
            "sequence": e.get("sequence_id"), "step": e.get("current_step"),
            "status": e.get("status"),
            "opens": g.get("opens", 0), "clicks": g.get("clicks", 0),
        })
        if len(hot_leads) >= 8:
            break

    return {
        "hot_leads_14d": hot_leads,
        "new_leads_24h": len(new_enr),
        "leads_by_brand": by_brand,
        "countdown_enrollments": countdown,
        "emails_sent_24h": len(new_sends),
        "opens_24h": opened, "clicks_24h": clicked, "bounces_24h": bounced,
        "new_orders_24h_UNRELIABLE": "use ga4 purchase counts — gg_athletes is not written by purchases",
        "errors_24h": errors[:10],
    }


def collect_social() -> dict:
    """Social engine status: yesterday's queue + published state. Platform
    metrics (impressions/engagement) join here in Phase 3 when accounts
    exist; social-driven SESSIONS already arrive via ga4.channel_mix."""
    qdir = PROJECT_ROOT / "data" / "social-queue"
    y = (date.today() - timedelta(days=1)).isoformat()
    t = date.today().isoformat()
    out = {"accounts_live": False,  # flip when X/IG/Notes publishing ships
           "queued_today": 0, "queued_yesterday": 0, "posts": []}
    for label, day in (("queued_today", t), ("queued_yesterday", y)):
        f = qdir / f"{day}.json"
        if f.exists():
            q = json.loads(f.read_text())
            out[label] = len(q)
            if label == "queued_today":
                out["posts"] = [{"brand": x["brand"], "race": x["race"],
                                 "kind": x["kind"]} for x in q[:10]]
    return out


def collect_workflows() -> dict:
    """Latest conclusions of the health workflows (needs GITHUB_TOKEN or gh auth)."""
    import subprocess
    out = {}
    for repo, wf in [("wattgod/gravel-race-automation", "link-check.yml"),
                     ("wattgod/road-race-automation", "link-check.yml"),
                     ("wattgod/road-race-automation", "checkout-monitor.yml"),
                     ("wattgod/gravel-race-automation", "regression-tests.yml"),
                     ("wattgod/gravel-race-automation", "aeo-weekly.yml")]:
        try:
            r = subprocess.run(
                ["gh", "run", "list", "--repo", repo, "--workflow", wf,
                 "--limit", "1", "--json", "conclusion,updatedAt"],
                capture_output=True, text=True, timeout=30)
            runs = json.loads(r.stdout or "[]")
            out[f"{repo.split('/')[1]}/{wf}"] = runs[0]["conclusion"] if runs else "never-run"
        except Exception as e:
            out[f"{repo.split('/')[1]}/{wf}"] = f"unknown ({type(e).__name__})"
    return {"latest": out}


AEO_BRANDS = {
    "gravelgod": "Gravel God",
    "roadie": "Roadie Labs",
    "xcski": "XC Ski Labs",
}


def _aeo_total_days(brand: dict, bucket: str) -> int:
    return sum(
        int(day.get(bucket, 0) or 0)
        for day in ((brand.get("logs") or {}).get("days") or {}).values()
        if isinstance(day, dict)
    )


def _aeo_ga4_total(brand: dict) -> int | None:
    ga4 = brand.get("ga4") or {}
    if ga4.get("status") != "ok":
        return None
    return sum(int(value or 0) for value in (ga4.get("current_window") or {}).values())


def _aeo_delta(current: int | None, prior: int | None) -> int | None:
    if current is None or prior is None:
        return None
    return current - prior


def _aeo_delta_text(delta: int | None) -> str:
    if delta is None:
        return "baseline — no prior artifact"
    if delta > 0:
        return f"+{delta} WoW"
    if delta < 0:
        return f"{delta} WoW"
    return "0 WoW"


def _load_aeo_artifact(path: Path) -> dict:
    try:
        artifact = json.loads(path.read_text())
    except Exception as exc:
        raise ValueError(f"{type(exc).__name__}: {exc}") from exc
    try:
        from scripts.aeo_weekly import validate_artifact
    except ImportError:
        from aeo_weekly import validate_artifact
    errors = validate_artifact(artifact, path=path)
    if errors:
        raise ValueError("; ".join(errors))
    return artifact


def _collect_aeo(today: date | None = None) -> dict:
    """Implementation for collect_aeo; the public collector is fully fail-soft."""
    paths = sorted(AEO_DIR.glob("aeo-weekly-*.json"))
    if not paths:
        return {"state": "missing", "ok": True}
    latest_path = paths[-1]
    try:
        latest = _load_aeo_artifact(latest_path)
    except Exception as exc:
        return {
            "state": "invalid",
            "ok": False,
            "error": f"AEO weekly artifact invalid: {str(exc)[:300]}",
        }
    generated_date = datetime.fromisoformat(
        latest["generated_at_utc"].replace("Z", "+00:00")).date()
    utc_today = today or datetime.now(timezone.utc).date()
    age_days = (utc_today - generated_date).days
    if age_days < 0:
        return {
            "state": "invalid",
            "ok": False,
            "error": "AEO weekly artifact invalid: generated date is in the future",
        }
    if age_days > 8:
        return {
            "state": "stale",
            "ok": False,
            "age_days": age_days,
            "error": f"AEO weekly artifact stale ({age_days} days)",
        }

    prior = None
    prior_path = None
    if len(paths) > 1:
        prior_path = paths[-2]
        try:
            prior = _load_aeo_artifact(prior_path)
        except Exception:
            # A healthy current artifact remains useful; an unreadable historical
            # comparison degrades to a baseline instead of hiding the section.
            prior = None

    latest_brands = latest.get("brands") or {}
    prior_brands = (prior or {}).get("brands") or {}
    rendered_brands = {}
    for brand, label in AEO_BRANDS.items():
        current_brand = latest_brands.get(brand) or {}
        prior_brand = prior_brands.get(brand) or {}
        ga4_sessions = _aeo_ga4_total(current_brand)
        prior_ga4_sessions = _aeo_ga4_total(prior_brand) if prior else None
        user_fetch = _aeo_total_days(current_brand, "user_fetch")
        prior_user_fetch = (
            _aeo_total_days(prior_brand, "user_fetch") if prior else None)
        search_index = _aeo_total_days(current_brand, "search_index")
        training_crawl = _aeo_total_days(current_brand, "training_crawl")
        status_buckets = (current_brand.get("logs") or {}).get("status_buckets") or {}
        llms_2xx = int(status_buckets.get("2xx", 0) or 0)
        llms_non_2xx = sum(
            int(status_buckets.get(status, 0) or 0)
            for status in ("3xx", "4xx", "5xx")
        )
        ga4_delta = _aeo_delta(ga4_sessions, prior_ga4_sessions)
        user_fetch_delta = _aeo_delta(user_fetch, prior_user_fetch)
        rendered_brands[brand] = {
            "label": label,
            "ga4_status": (current_brand.get("ga4") or {}).get("status", "error"),
            "logs_status": (current_brand.get("logs") or {}).get("status", "error"),
            "ai_referral_sessions": ga4_sessions,
            "ai_referral_delta": ga4_delta,
            "ai_referral_delta_text": _aeo_delta_text(ga4_delta),
            "user_fetch": user_fetch,
            "user_fetch_delta": user_fetch_delta,
            "user_fetch_delta_text": _aeo_delta_text(user_fetch_delta),
            "search_index": search_index,
            "training_crawl": training_crawl,
            "llms_2xx": llms_2xx,
            "llms_non_2xx": llms_non_2xx,
            "top_user_fetch_paths": [
                {
                    "path": str(item.get("path") or "(not set)"),
                    "hits": int(item.get("hits", 0) or 0),
                }
                for item in (current_brand.get("top_user_fetch_paths") or [])[:3]
                if isinstance(item, dict)
            ],
        }
    return {
        "state": "ok",
        "ok": True,
        "artifact": latest_path.name,
        "prior_artifact": prior_path.name if prior is not None and prior_path else None,
        "generated_at_utc": latest["generated_at_utc"],
        "current_window": latest["current_window"],
        "brands": rendered_brands,
        "unknown_agent_candidates": latest.get("unknown_agent_candidates") or [],
    }


def collect_aeo(today: date | None = None) -> dict:
    """Load weekly AEO facts, returning an error state instead of ever raising."""
    try:
        return _collect_aeo(today=today)
    except Exception as exc:
        return {
            "state": "invalid",
            "ok": False,
            "error": (
                f"AEO weekly artifact invalid: "
                f"{type(exc).__name__}: {str(exc)[:260]}"
            ),
        }


def load_trend(days: int = 7) -> list[dict]:
    """Prior snapshots (compact) for trend context in the interpretation."""
    trend = []
    for f in sorted(SNAPSHOT_DIR.glob("*.json"))[-days:]:
        try:
            snap = json.loads(f.read_text())
            compact = {"date": f.stem}
            for b in BRANDS:
                g = snap.get("ga4", {}).get(b, {})
                compact[b] = {"sessions": g.get("sessions"),
                              "purchases": (g.get("funnel") or {}).get("purchase")}
            mc = snap.get("mission_control", {})
            compact["leads"] = mc.get("new_leads_24h")
            purchases = []
            for b in BRANDS:
                value = (((snap.get("ga4") or {}).get(b) or {}).get("funnel") or {}).get(
                    "purchase", 0)
                try:
                    purchases.append(int(value or 0))
                except (TypeError, ValueError):
                    purchases.append(0)
            compact["orders"] = sum(purchases)
            trend.append(compact)
        except Exception:
            continue
    return trend


# ── Interpretation ──────────────────────────────────────────────────────

def _display(value, default="0") -> str:
    if value is None or value == "":
        return default
    return str(value)


def _path(value) -> str:
    if value is None or value == "":
        return "(not set)"
    return str(value)


def _funnel_line(funnel: dict) -> str:
    return (
        f"cta {_display(funnel.get('cta_click'))} → "
        f"form_start {_display(funnel.get('form_start'))} → "
        f"submit {_display(funnel.get('form_submit'))} → "
        f"checkout {_display(funnel.get('begin_checkout'))} → "
        f"purchase {_display(funnel.get('purchase'))}"
    )


def _person(item: dict) -> str:
    name = (item.get("name") or "").strip()
    email = (item.get("email") or "").strip()
    if name and email:
        return f"{name} <{email}>"
    return name or email or "unknown customer"


def _collector_failures(collected: dict) -> list[str]:
    broken = []
    for group in ("ga4", "checkout"):
        for brand, result in (collected.get(group) or {}).items():
            if not isinstance(result, dict) or result.get("ok") is not False:
                continue
            label = BRANDS.get(brand, {}).get("label", brand)
            error = _display(result.get("error"), "unknown error")
            if group == "checkout":
                broken.append(f"checkout {label} FAIL: {error}")
            else:
                broken.append(f"GA4 {label} collector failed: {error}")
    for key, label in (
        ("mission_control", "Mission Control"),
        ("commerce_ledger", "commerce ledger"),
        ("social", "social"),
        ("workflows", "workflows"),
    ):
        result = collected.get(key) or {}
        if not isinstance(result, dict) or result.get("ok") is not False:
            continue
        error = _display(result.get("error"), "unknown error")
        broken.append(f"{label} collector failed: {error}")
    constraint = collected.get("constraint") or {}
    if isinstance(constraint, dict) and constraint.get("ok") is False:
        error = _display(constraint.get("error"), "unknown error")
        broken.append(f"constraint unavailable: {error}")
    aeo = collected.get("aeo") or {}
    if (
            isinstance(aeo, dict)
            and aeo.get("state") in {"stale", "invalid"}
            and aeo.get("ok") is False):
        broken.append(_display(aeo.get("error"), "AEO weekly artifact unavailable"))
    return broken


def render_report(collected: dict) -> str:
    """Render the factual report sections without network calls or inference."""
    lines = [
        "## NUMBERS",
        "| Brand | Sessions (vs 7d avg) | Funnel | Leads |",
        "|---|---:|---|---:|",
    ]
    ga4 = collected.get("ga4") or {}
    mc = collected.get("mission_control") or {}
    leads_by_brand = mc.get("leads_by_brand") or {}
    for brand, meta in BRANDS.items():
        g = ga4.get(brand) or {}
        if g.get("ok"):
            sessions = _display(g.get("sessions"))
            avg = _display(g.get("sessions_7d_avg"))
            session_cell = f"{sessions} (vs {avg})"
            funnel = _funnel_line(g.get("funnel") or {})
        else:
            session_cell = "unavailable"
            funnel = "unavailable"
        if mc.get("ok"):
            leads = _display(leads_by_brand.get(brand), "unavailable")
        else:
            leads = "unavailable"
        lines.append(f"| {meta['label']} | {session_cell} | {funnel} | {leads} |")

    lines.extend(["", "## TRAFFIC"])
    for brand, meta in BRANDS.items():
        g = ga4.get(brand) or {}
        if not g.get("ok"):
            lines.append(f"- **{meta['label']}:** traffic unavailable.")
            continue
        sessions = g.get("sessions") or 0
        try:
            has_traffic = float(sessions) > 5
        except (TypeError, ValueError):
            has_traffic = False
        if not has_traffic:
            lines.append(f"- **{meta['label']}:** {sessions} sessions; near-zero traffic.")
            continue
        pages = ", ".join(
            f"{_path(p.get('path'))} ({_display(p.get('views'))} views)"
            for p in (g.get("top_pages") or [])[:5]
        ) or "none"
        channels = ", ".join(
            f"{name} {_display(count)}"
            for name, count in (g.get("channel_mix") or {}).items()
        ) or "none"
        landing = ", ".join(
            f"{_path(p.get('path'))} ({_display(p.get('sessions'))} sessions)"
            for p in (g.get("top_landing") or [])[:5]
        ) or "none"
        lines.extend([
            f"- **{meta['label']} top pages:** {pages}.",
            f"- **{meta['label']} channel mix:** {channels}.",
            f"- **{meta['label']} top landing:** {landing}.",
        ])

    lines.extend(["", "## COMMERCE (GROUND TRUTH)"])
    ledger = collected.get("commerce_ledger") or {}
    if not ledger.get("ok"):
        lines.append("- commerce ledger unavailable.")
    else:
        orders = list(ledger.get("orders") or [])
        failed_orders = list(ledger.get("failed_orders") or [])
        failed_orders.extend(o for o in orders if o.get("success") is False)
        successful_orders = [o for o in orders if o.get("success") is not False]
        recoveries = list(ledger.get("recoveries") or [])
        starts = ledger.get("questionnaire_starts") or 0
        if not failed_orders and not successful_orders and not recoveries and not starts:
            lines.append("- no orders, cart recoveries, or questionnaire starts.")
        else:
            seen_failures = set()
            for order in failed_orders:
                identity = (order.get("timestamp"), order.get("email"), order.get("error"))
                if identity in seen_failures:
                    continue
                seen_failures.add(identity)
                product = order.get("product_type") or order.get("product") or "order"
                error = _display(order.get("error"), "unknown fulfillment error")
                lines.append(
                    f"- **FAILED ORDER:** {_person(order)} — {product}; "
                    f"fulfillment FAILED: {error}."
                )
            for order in successful_orders:
                product = order.get("product_type") or order.get("product") or "order"
                outcome = "fulfilled" if order.get("success") is True else "outcome unknown"
                lines.append(f"- order: {_person(order)} — {product}; fulfillment {outcome}.")
            for recovery in recoveries:
                product = recovery.get("product") or recovery.get("product_type") or "order"
                lines.append(f"- cart recovery: {_person(recovery)} — {product}.")
            lines.append(f"- questionnaire starts: {starts}.")

    lines.extend(["", "## CONSTRAINT"])
    constraint = collected.get("constraint") or {}
    if not constraint.get("ok"):
        lines.append("- constraint unavailable.")
    else:
        binding = _display(constraint.get("binding_constraint"), "not available")
        lines.append(f"- binding constraint: {binding}.")
        lines.append(
            "- 28d rates: "
            f"CTA {_display(constraint.get('cta_rate_pct'))}%; "
            f"CTA→submit {_display(constraint.get('cta_to_submit_pct'))}%; "
            f"submit→purchase {_display(constraint.get('submit_to_purchase_pct'))}%."
        )
        needed = constraint.get("sessions_per_day_needed_for_1_sale")
        needed_text = _display(needed, "not measurable")
        actual = _display(constraint.get("sessions_per_day"), "not available")
        lines.append(f"- sessions/day needed for 1 sale/day: {needed_text}; actual: {actual}.")

    lines.extend(["", "## HOT LEADS"])
    hot_leads = (mc.get("hot_leads_14d") or []) if mc.get("ok") else []
    if not hot_leads:
        lines.append("- no hot leads in the last 14 days.")
    else:
        for lead in hot_leads:
            person = _person(lead)
            race = lead.get("race") or "(no race given)"
            sequence = lead.get("sequence") or "unknown sequence"
            step = _display(lead.get("step"), "unknown")
            opens = _display(lead.get("opens"))
            clicks = _display(lead.get("clicks"))
            lines.append(
                f"- {person} — {race}; {sequence} step {step}; "
                f"{opens} opens/{clicks} clicks."
            )

    social = collected.get("social") or {}
    if social.get("accounts_live"):
        lines.extend(["", "## SOCIAL"])
        queued_today = _display(social.get("queued_today"))
        queued_yesterday = _display(social.get("queued_yesterday"))
        lines.append(f"- queued: {queued_today} today; {queued_yesterday} yesterday.")
        for post in social.get("posts") or []:
            brand = post.get("brand") or "unknown brand"
            race = post.get("race") or "unknown race"
            kind = post.get("kind") or "post"
            lines.append(f"- {brand}: {race} — {kind}.")

    aeo = collected.get("aeo") or {}
    if aeo.get("state") == "ok":
        window = aeo.get("current_window") or {}
        lines.extend([
            "",
            "## AEO (WEEKLY)",
            (
                f"- completed window: {_display(window.get('start'), 'unknown')} "
                f"through {_display(window.get('end'), 'unknown')}; AI-referral "
                "sessions are a lower-bound click-through proxy, not proof of citation."
            ),
        ])
        for brand in AEO_BRANDS:
            facts = (aeo.get("brands") or {}).get(brand) or {}
            label = facts.get("label") or AEO_BRANDS[brand]
            if facts.get("ga4_status") == "not_configured":
                referral = "not configured"
            elif facts.get("ga4_status") != "ok":
                referral = "unavailable"
            else:
                referral = (
                    f"{_display(facts.get('ai_referral_sessions'))} "
                    f"({_display(facts.get('ai_referral_delta_text'))})"
                )
            if facts.get("logs_status") != "ok":
                log_facts = "log collector unavailable"
            else:
                log_facts = (
                    f"user_fetch {_display(facts.get('user_fetch'))} "
                    f"({_display(facts.get('user_fetch_delta_text'))}); "
                    f"search_index {_display(facts.get('search_index'))}; "
                    f"training_crawl {_display(facts.get('training_crawl'))}; "
                    f"llms.txt/.md 2xx {_display(facts.get('llms_2xx'))}"
                )
                if facts.get("llms_non_2xx", 0) > 0:
                    log_facts += (
                        f" ({_display(facts.get('llms_non_2xx'))} non-2xx)")
            lines.append(
                f"- **{label}:** AI-referral {referral}; {log_facts}.")
            paths = ", ".join(
                f"{_path(item.get('path'))} ({_display(item.get('hits'))})"
                for item in (facts.get("top_user_fetch_paths") or [])[:3]
            ) or "none"
            lines.append(f"- **{label} top fetched paths:** {paths}.")
        candidates = aeo.get("unknown_agent_candidates") or []
        if candidates:
            rendered_candidates = []
            for item in candidates:
                brands = ", ".join(
                    f"{brand} {_display(count)}"
                    for brand, count in (item.get("brands") or {}).items()
                )
                detail = f"; {brands}" if brands else ""
                rendered_candidates.append(
                    f"{_display(item.get('user_agent'), 'unknown')} "
                    f"({_display(item.get('count'))}{detail})"
                )
            lines.append(
                "- **Unknown agent candidates (spoofable):** "
                + ", ".join(rendered_candidates) + ".")

    lines.extend(["", "## BROKEN"])
    broken = []
    failed_for_broken = list(ledger.get("failed_orders") or [])
    failed_for_broken.extend(
        order for order in (ledger.get("orders") or []) if order.get("success") is False)
    seen_failures = set()
    for order in failed_for_broken:
        identity = (order.get("timestamp"), order.get("email"), order.get("error"))
        if identity in seen_failures:
            continue
        seen_failures.add(identity)
        error = _display(order.get("error"), "unknown fulfillment error")
        broken.append(f"FAILED ORDER: {_person(order)} — {error}")
    broken.extend(_collector_failures(collected))
    if mc.get("ok"):
        for error in mc.get("errors_24h") or []:
            action = error.get("action") or "unknown action"
            details = error.get("details") or "no details"
            broken.append(f"Mission Control {action}: {details}")
    workflows = collected.get("workflows") or {}
    if workflows.get("ok"):
        for name, conclusion in (workflows.get("latest") or {}).items():
            if conclusion != "success":
                broken.append(f"workflow {name}: {conclusion}")
    broken.extend(str(line) for line in (collected.get("report_issues") or []) if line)
    if broken:
        lines.extend(f"- {line}" for line in broken)
    else:
        lines.append("- nothing broken.")
    return "\n".join(lines)


def safe_render(collected: dict) -> str:
    """render_report, but a rendering crash can never cost the email.

    A collector that returns HTTP 200 with a drifted shape passes _safe's
    ok=True and would crash render_report — the one failure mode this script
    must never have (email always sends). Fall back to a minimal report that
    names the error instead.
    """
    try:
        return render_report(collected)
    except Exception as e:
        reason = f"{type(e).__name__}: {e}"[:300]
        lines = [f"## BROKEN", f"- report rendering crashed: {reason}",
                 "- full sections unavailable; raw snapshot has the data"]
        ga4 = collected.get("ga4") if isinstance(collected, dict) else {}
        for brand, meta in BRANDS.items():
            g = (ga4 or {}).get(brand)
            if isinstance(g, dict) and g.get("ok"):
                lines.append(f"- {meta['label']}: sessions {g.get('sessions')}")
        return "\n".join(lines)


def detect_tracking_regression(
        collected: dict, prior_snapshots: list[dict]) -> str | None:
    """Return a warning when healthy traffic has had zero CTA events for 3 days."""
    def is_zero_event_day(snapshot):
        g = ((snapshot.get("ga4") or {}).get("gravelgod") or {})
        funnel = g.get("funnel") or {}
        if g.get("ok") is not True or "cta_click" not in funnel:
            return False
        try:
            enough_sessions = float(g.get("sessions") or 0) >= 15
            zero_ctas = int(funnel["cta_click"]) == 0
        except (TypeError, ValueError):
            return False
        return enough_sessions and zero_ctas

    priors = list(prior_snapshots or [])
    if not is_zero_event_day(collected) or len(priors) < 2:
        return None
    if not all(is_zero_event_day(snapshot) for snapshot in priors[:2]):
        return None
    sessions = ((collected.get("ga4") or {}).get("gravelgod") or {}).get("sessions")
    return (
        f"possible GA4 event-tracking regression: {sessions} sessions but "
        "0 cta_click for 3+ consecutive days"
    )


def load_prior_snapshots(today: str, days: int = 2) -> list[dict]:
    """Load exact preceding calendar days; a missing day breaks consecutiveness."""
    snapshots = []
    current = date.fromisoformat(today)
    for offset in range(1, days + 1):
        path = SNAPSHOT_DIR / f"{current - timedelta(days=offset)}.json"
        if not path.exists():
            break
        try:
            loaded = json.loads(path.read_text())
        except Exception:
            break
        if not isinstance(loaded, dict):
            break
        snapshots.append(loaded)
    return snapshots


def interpretation_failure_streak(today: str) -> int:
    """Count today's failure plus explicit failures on consecutive prior days."""
    streak = 1
    current = date.fromisoformat(today)
    offset = 1
    while True:
        path = SNAPSHOT_DIR / f"{current - timedelta(days=offset)}.json"
        if not path.exists():
            break
        try:
            status = json.loads(path.read_text()).get("interpretation_ok")
        except Exception:
            break
        if status is not False:
            break
        streak += 1
        offset += 1
    return streak


INTERPRET_PROMPT = """You are writing the Morning Intel report for Matti, who runs two \
honest-critic cycling race-database businesses (Gravel God Cycling, Roadie Labs) selling \
$15/wk custom training plans (cap $249). Target: one plan sale per day. Baseline when \
this started (Jun 2026): ~35 users/day, ~1 sale/month.

Register: deadpan, terse, zero hype, zero filler. Like a good analyst who respects the \
reader's time. NEVER invent or extrapolate a number not present in the context below. \
The commerce ledger is ground truth and overrides GA4. The factual report is already \
rendered; do not repeat its sections or add new facts.

Write EXACTLY this structure (markdown):
Line 1: `SUBJECT: intel {date}: <hook under 60 chars — the single most important fact>`
Then:
## TOP LINE
- 3 bullets max. What actually happened yesterday. Numbers inline.
## DO TODAY
Max 3 one-line actions: the action, the why, expected impact. If the right move is \
"nothing — let it run", say that.

DATA (today):
{data}

TREND (last {n} days, compact):
{trend}

DETERMINISTIC FACTUAL REPORT:
{report}
"""


def interpret(collected: dict, trend: list[dict], report: str) -> tuple[str, str]:
    """Return (subject, narration) from Claude; raises on malformed output."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    prompt = INTERPRET_PROMPT.format(
        date=collected["date"], n=len(trend),
        data=json.dumps(collected, indent=1, default=str)[:24000],
        trend=json.dumps(trend, indent=0, default=str)[:6000],
        report=report,
    )
    code, body = _http(
        "https://api.anthropic.com/v1/messages",
        data={"model": INTEL_MODEL, "max_tokens": 4000,
              "thinking": {"type": "disabled"},
              "messages": [{"role": "user", "content": prompt}]},
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        timeout=120,
    )
    if code != 200:
        raise RuntimeError(f"Anthropic API {code}: {body[:200]}")
    # Claude 5 models may emit thinking blocks before text — take text blocks only
    blocks = json.loads(body)["content"]
    text = "\n".join(b.get("text", "") for b in blocks
                     if b.get("type") == "text").strip()
    if not text:
        raise RuntimeError("no text block in model response")
    if text.startswith("```"):  # tolerate a markdown fence around the response
        text = text.strip("`").removeprefix("markdown").strip()
    first, _, rest = text.partition("\n")
    if not first.startswith("SUBJECT:"):
        raise RuntimeError("model response missing SUBJECT line")
    subject = first.replace("SUBJECT:", "", 1).strip() or f"intel {collected['date']}"
    narration = rest.strip()
    top_index = narration.find("## TOP LINE")
    do_index = narration.find("## DO TODAY")
    if top_index != 0 or do_index <= top_index:
        raise RuntimeError("model response missing TOP LINE or DO TODAY")
    headers = [line for line in narration.splitlines() if line.startswith("## ")]
    if headers != ["## TOP LINE", "## DO TODAY"]:
        raise RuntimeError("model response included an unexpected section")
    return subject, narration


def combine_report(narration: str, deterministic_report: str) -> str:
    """Place deterministic facts between the model's two narrative sections."""
    top, marker, actions = narration.partition("## DO TODAY")
    if not marker:
        raise ValueError("narration missing DO TODAY")
    return f"{top.strip()}\n\n{deterministic_report}\n\n## DO TODAY{actions}".strip()


def plain_digest(collected: dict) -> tuple[str, str]:
    """Explicit no-LLM mode: deterministic sections and a raw-digest subject."""
    return f"intel {collected['date']}: raw digest", safe_render(collected)


# ── Delivery + snapshot ─────────────────────────────────────────────────

def _md_to_html(md: str) -> str:
    """Minimal markdown -> styled HTML for the report's known shapes:
    ## headers, - bullets, | tables |, **bold**. Deliberately dependency-free."""
    import html as h
    import re as _re

    def inline(t):
        t = h.escape(t)
        return _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)

    out, i, lines = [], 0, md.splitlines()
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("## "):
            out.append(f'<h2 style="font-family:\'Courier New\',monospace;font-size:13px;'
                       f'letter-spacing:2px;color:#1a1a1a;border-bottom:2px solid #1a1a1a;'
                       f'padding-bottom:6px;margin:28px 0 12px">{inline(line[3:]).upper()}</h2>')
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(set(c) <= set("-: ") for c in cells):  # skip separator row
                    rows.append(cells)
                i += 1
            i -= 1
            table = ['<table style="border-collapse:collapse;width:100%;margin:8px 0 16px;'
                     'font-size:14px">']
            for ri, row in enumerate(rows):
                tag = "th" if ri == 0 else "td"
                style = ("border:1px solid #d0d0c8;padding:7px 10px;text-align:left;" +
                         ("background:#1a1a1a;color:#f5f5f0;font-family:\'Courier New\',"
                          "monospace;font-size:12px" if ri == 0 else "background:#ffffff"))
                table.append("<tr>" + "".join(
                    f'<{tag} style="{style}">{inline(c)}</{tag}>' for c in row) + "</tr>")
            table.append("</table>")
            out.append("".join(table))
        elif line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f'<li style="margin:0 0 8px">{inline(lines[i][2:])}</li>')
                i += 1
            i -= 1
            out.append('<ul style="margin:8px 0 16px;padding-left:22px">' + "".join(items) + "</ul>")
        elif _re.match(r"^\d+\. ", line):
            items = []
            while i < len(lines) and _re.match(r"^\d+\. ", lines[i]):
                item_text = inline(_re.sub(r"^\d+\. ", "", lines[i]))
                items.append(f'<li style="margin:0 0 10px">{item_text}</li>')
                i += 1
            i -= 1
            out.append('<ol style="margin:8px 0 16px;padding-left:22px">' + "".join(items) + "</ol>")
        elif line.strip():
            out.append(f'<p style="margin:0 0 12px">{inline(line)}</p>')
        i += 1
    return "".join(out)


def send_email(subject: str, markdown: str) -> str:
    body = _md_to_html(markdown)
    html = (
        '<div style="background:#f5f5f0;padding:24px 8px">'
        '<div style="max-width:640px;margin:0 auto;background:#ffffff;'
        'border:2px solid #1a1a1a;padding:28px 32px;font-family:Georgia,serif;'
        'color:#1a1a1a;line-height:1.6;font-size:15px">'
        '<div style="font-family:\'Courier New\',monospace;font-size:11px;'
        'letter-spacing:3px;color:#777777;margin-bottom:4px">MORNING INTEL</div>'
        f'{body}'
        '<div style="margin-top:28px;padding-top:12px;border-top:1px solid #d0d0c8;'
        'font-family:\'Courier New\',monospace;font-size:11px;color:#999">'
        'gravel-race-automation / daily_intel.py &middot; trend snapshots: '
        'data/intel-snapshots/</div></div></div>'
    )
    code, body_resp = _http("https://api.resend.com/emails", data={
        "from": "Morning Intel <matti@gravelgodcycling.com>",
        "to": [INTEL_TO],
        "subject": subject,
        "html": html,
    }, headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"})
    if code != 200:
        raise RuntimeError(f"Resend {code}: {body_resp[:200]}")
    return json.loads(body_resp).get("id", "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="skip the email send")
    ap.add_argument("--no-llm", action="store_true", help="skip interpretation")
    args = ap.parse_args()

    today = date.today().isoformat()
    collected = {
        "date": today,
        "ga4": {b: _safe(lambda b=b: collect_ga4(b)) for b in BRANDS},
        "checkout": {b: _safe(lambda b=b: collect_checkout(b)) for b in BRANDS},
        "mission_control": _safe(collect_mission_control),
        "commerce_ledger": _safe(collect_commerce_ledger),
        "social": _safe(collect_social),
        "workflows": _safe(collect_workflows),
        "aeo": _safe(collect_aeo),
    }
    collected["constraint"] = compute_constraint(collected["ga4"].get("gravelgod", {}))
    try:
        tracking_issue = detect_tracking_regression(
            collected, load_prior_snapshots(today))
    except Exception as e:
        tracking_issue = f"tracking-regression check crashed: {type(e).__name__}: {e}"
    collected["report_issues"] = [tracking_issue] if tracking_issue else []
    trend = load_trend()
    deterministic_report = safe_render(collected)

    if args.no_llm:
        # deliberately skipped, not broken — must not extend the failure streak
        collected["interpretation_ok"] = None
        subject, report = plain_digest(collected)
    else:
        try:
            subject, narration = interpret(collected, trend, deterministic_report)
            report = combine_report(narration, deterministic_report)
            collected["interpretation_ok"] = True
        except Exception as e:
            reason = str(e).replace("\n", " ")[:300] or type(e).__name__
            collected["interpretation_ok"] = False
            collected["report_issues"].append(f"interpretation unavailable: {reason}")
            deterministic_report = safe_render(collected)
            try:
                streak = interpretation_failure_streak(today)
            except Exception:
                streak = 1
            subject = f"intel {today}: INTERPRETATION BROKEN — day {streak}"
            report = f"INTERPRETATION UNAVAILABLE: {reason}\n\n{deterministic_report}"

    # persistence must never cost the email — snapshot failures ride in the report
    try:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        (SNAPSHOT_DIR / f"{today}.json").write_text(
            json.dumps({**collected, "report": report}, indent=1, default=str))
        (SNAPSHOT_DIR / f"{today}.md").write_text(f"# {subject}\n\n{report}\n")
        print(f"snapshot: data/intel-snapshots/{today}.json")
    except Exception as e:
        report += f"\n- BROKEN: snapshot write failed: {type(e).__name__}: {e}"
    print(f"subject:  {subject}")

    if args.dry_run:
        print("\n" + report)
        return 0
    msg_id = send_email(subject, report)
    print(f"sent:     {msg_id} → {INTEL_TO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
