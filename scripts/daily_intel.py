#!/usr/bin/env python3
"""Morning Command — the ecosystem's single daily composer and emailer.

Aggregates commerce, immune findings/repairs, GSC/CWV snapshots, ecosystem CI,
and Endure Labs cron health. It ranks human-needed work, suppresses green/noise,
and is the only daily process allowed to send email.

Every collector is fail-soft: a broken source becomes a BROKEN line in the
report — the email always sends (order-killer lesson: failures loud to the
coach, never silent).

Usage:
    python3 scripts/daily_intel.py                # collect + interpret + send + snapshot
    python3 scripts/daily_intel.py --preview      # offline-safe print; no send/write
    python3 scripts/daily_intel.py --json         # machine report; no send

Env (see .github/workflows/daily-intel.yml):
    GA4_CREDENTIALS, GG_GA4_PROPERTY_ID, RL_GA4_PROPERTY_ID,
    SUPABASE_URL, SUPABASE_SERVICE_KEY, RESEND_API_KEY, ANTHROPIC_API_KEY,
    INTEL_MODEL (default claude-sonnet-5), INTEL_TO, CHECKOUT_WEBHOOK_URL
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "intel-snapshots"
HEALTH_DIR = PROJECT_ROOT / "reports" / "health"
IMMUNE_REPORT = PROJECT_ROOT / "immune" / "report.json"
IMMUNE_LEDGER = PROJECT_ROOT / "immune" / "ledger.jsonl"
ECOSYSTEM_REPORT = HEALTH_DIR / "ci-cron.json"
GSC_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "gsc-snapshots"
CWV_SNAPSHOT_DIR = PROJECT_ROOT / "data" / "cwv-snapshots"

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
    week_ago = (date.today() - timedelta(days=8)).isoformat()

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
        "sessions_7d_avg": round(week_sessions / 8, 1),
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
                     ("wattgod/gravel-race-automation", "regression-tests.yml")]:
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
            compact["orders"] = mc.get("new_orders_24h")
            trend.append(compact)
        except Exception:
            continue
    return trend


# ── Interpretation ──────────────────────────────────────────────────────

INTERPRET_PROMPT = """You are writing the Morning Intel report for Matti, who runs two \
honest-critic cycling race-database businesses (Gravel God Cycling, Roadie Labs) selling \
$15/wk custom training plans (cap $249). Target: one plan sale per day. Baseline when \
this started (Jun 2026): ~35 users/day, ~1 sale/month.

Register: deadpan, terse, zero hype, zero filler. Like a good analyst who respects the \
reader's time. NEVER invent or extrapolate a number not present in the data below. If a \
collector failed, that goes in BROKEN — do not guess what its data would have said.

Write EXACTLY this structure (markdown):
Line 1: `SUBJECT: intel {date}: <hook under 60 chars — the single most important fact>`
Then:
## TOP LINE
- 3 bullets max. What actually happened yesterday. Numbers inline.
## NUMBERS
A compact per-brand markdown table: sessions (vs 7d avg), funnel steps, leads, orders.
## TRAFFIC
For each brand with >5 sessions: top pages (path + views, top 3-5), the channel mix \
(organic/direct/referral with counts), and top landing pages — this is where the reader \
learns WHAT people read and WHERE they came from. One line per item, real paths. If a \
brand is near-zero, one line says so and moves on. Flag anything notable (a page \
suddenly popular, a new referral source).
## COMMERCE (ground truth)
From commerce_ledger (the Railway order ledger — this OVERRIDES any GA4 inference): \
orders in the last 24h with names and fulfillment outcomes, cart-recovery emails sent, \
real questionnaire starts. A FAILED order (success=false) is a paying customer without \
a product — lead the whole report with it if one exists. If the ledger shows nothing, \
one line.
## CONSTRAINT
Use ONLY the precomputed numbers in `constraint` (never compute your own): state the \
binding constraint by name, the 28-day funnel rates, and the sessions/day needed for \
one sale/day at current rates vs actual sessions/day. Two or three sentences, plain.
## HOT LEADS
From mission_control.hot_leads_14d: one line per person — name/email, their race, \
where they are in which sequence, opens/clicks — ending with ONE concrete suggested \
action (e.g. "reply personally about their race — use draft_race_reply"). These are real \
humans Matti may email today; be specific, never invent engagement they don't have. \
If empty: one line.
## SOCIAL
Metrics that matter, in strict order (say WHY when numbers exist): \
(1) social-driven SESSIONS from ga4 channel_mix — the only metric connected to the \
sales constraint; (2) link clicks per post; (3) engagement rate per post as a voice \
signal. Follower counts and likes are explicitly NOT success — never celebrate them. \
Also report what the engine queued (social.posts). While social.accounts_live is \
false: one line — queue status + zero social sessions is expected, no analysis theater.
## BROKEN
Every failed probe/collector/error, severity-ranked. A failed ORDER outranks \
everything else in the report. If nothing: one line saying so.
## DO TODAY
Max 3 action items, each one line: the action, the why, expected impact. If the right \
move is "nothing — let it run", say that.

DATA (today):
{data}

TREND (last {n} days, compact):
{trend}
"""


def interpret(collected: dict, trend: list[dict]) -> tuple[str, str]:
    """Return (subject, markdown_body) from Claude; raises on failure."""
    api_key = os.environ["ANTHROPIC_API_KEY"]
    prompt = INTERPRET_PROMPT.format(
        date=collected["date"], n=len(trend),
        data=json.dumps(collected, indent=1, default=str)[:24000],
        trend=json.dumps(trend, indent=0, default=str)[:6000],
    )
    code, body = _http(
        "https://api.anthropic.com/v1/messages",
        data={"model": INTEL_MODEL, "max_tokens": 1500,
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
    first, _, rest = text.partition("\n")
    subject = first.replace("SUBJECT:", "").strip() if first.startswith("SUBJECT:") \
        else f"intel {collected['date']}"
    return subject, rest.strip()


def plain_digest(collected: dict) -> tuple[str, str]:
    """No-LLM fallback: readable digest of the raw numbers."""
    lines = [f"## RAW DIGEST — {collected['date']} (interpretation unavailable)"]
    for b, meta in BRANDS.items():
        g = collected["ga4"].get(b, {})
        lines.append(f"\n### {meta['label']}")
        if g.get("ok"):
            lines.append(f"- sessions {g['sessions']} (7d avg {g['sessions_7d_avg']}), "
                         f"funnel {g['funnel']}")
        else:
            lines.append(f"- GA4 FAILED: {g.get('error')}")
        c = collected["checkout"].get(b, {})
        lines.append(f"- checkout: {'OK' if c.get('ok') else 'FAIL ' + str(c.get('error'))}")
    mc = collected["mission_control"]
    if mc.get("ok"):
        lines.append(f"\n- leads {mc['new_leads_24h']}, emails {mc['emails_sent_24h']}, "
                     f"errors {len(mc['errors_24h'])} (orders: see GA4 purchase counts)")
    else:
        lines.append(f"\n- Mission Control FAILED: {mc.get('error')}")
    return f"intel {collected['date']}: raw digest", "\n".join(lines)


# ── Morning Command aggregation + deterministic interpretation ──────────

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
LANE_RANK = {"red": 0, "yellow": 1, "green": 2}


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {"ok": False, "error": "unexpected JSON shape"}
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _latest_json(directory: Path) -> tuple[dict, Path | None]:
    files = sorted(directory.glob("*.json")) if directory.exists() else []
    if not files:
        return {"ok": False, "error": "unavailable (no snapshot)"}, None
    return _read_json(files[-1]), files[-1]


def _snapshot_age_hours(path: Path | None) -> float | None:
    if path is None:
        return None
    return round((datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 3600, 1)


def _data_age_hours(snapshot: dict, path: Path | None) -> float | None:
    """Prefer the payload timestamp; checkout/git can make old files look new."""
    raw = snapshot.get("timestamp") or snapshot.get("date")
    if raw:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return round((datetime.now(timezone.utc) - parsed).total_seconds() / 3600, 1)
        except ValueError:
            pass
    return _snapshot_age_hours(path)


def _load_recent_intel(max_hours: int = 30) -> dict | None:
    data, path = _latest_json(SNAPSHOT_DIR)
    age = _snapshot_age_hours(path)
    if path and age is not None and age <= max_hours and data.get("commerce_ledger"):
        return data
    return None


def collect_base_intel(offline: bool = False) -> dict:
    """Reuse a fresh snapshot for preview; otherwise run the existing collectors."""
    if offline:
        cached = _load_recent_intel()
        if cached:
            cached = {**cached, "source": "fresh intel snapshot"}
            cached.pop("report", None)
            return cached
        unavailable = {"ok": False, "error": "unavailable in offline preview"}
        return {
            "date": date.today().isoformat(), "source": "offline",
            "ga4": {b: dict(unavailable) for b in BRANDS},
            "checkout": {b: dict(unavailable) for b in BRANDS},
            "mission_control": dict(unavailable), "commerce_ledger": dict(unavailable),
            "social": dict(unavailable), "constraint": dict(unavailable),
        }
    collected = {
        "date": date.today().isoformat(), "source": "live collectors",
        "ga4": {b: _safe(lambda b=b: collect_ga4(b)) for b in BRANDS},
        "checkout": {b: _safe(lambda b=b: collect_checkout(b)) for b in BRANDS},
        "mission_control": _safe(collect_mission_control),
        "commerce_ledger": _safe(collect_commerce_ledger),
        "social": _safe(collect_social),
    }
    collected["constraint"] = compute_constraint(collected["ga4"].get("gravelgod", {}))
    return collected


def load_site_health() -> dict:
    gsc, gsc_path = _latest_json(GSC_SNAPSHOT_DIR)
    cwv, cwv_path = _latest_json(CWV_SNAPSHOT_DIR)
    gsc_age = _data_age_hours(gsc, gsc_path)
    cwv_age = _data_age_hours(cwv, cwv_path)
    if gsc_age is not None and gsc_age > 48:
        gsc = {**gsc, "ok": False, "error": f"unavailable (snapshot stale: {gsc_age}h)"}
    if cwv_age is not None and cwv_age > 48:
        cwv = {**cwv, "ok": False, "error": f"unavailable (snapshot stale: {cwv_age}h)"}
    return {
        "gsc": {**gsc, "snapshot_age_hours": gsc_age,
                "snapshot_file": str(gsc_path.relative_to(PROJECT_ROOT)) if gsc_path else None},
        "cwv": {**cwv, "snapshot_age_hours": cwv_age,
                "snapshot_file": str(cwv_path.relative_to(PROJECT_ROOT)) if cwv_path else None},
    }


def load_immune() -> dict:
    report = _read_json(IMMUNE_REPORT)
    if not IMMUNE_REPORT.exists():
        report.update({"ok": False, "error": "unavailable (immune report missing)"})
    return report


def load_ecosystem() -> dict:
    report = _read_json(ECOSYSTEM_REPORT)
    if not ECOSYSTEM_REPORT.exists():
        report.update({"ok": False, "error": "unavailable (CI/cron report missing)"})
    return report


def load_recent_heals(hours: int = 36) -> list[dict]:
    if not IMMUNE_LEDGER.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    records = []
    for line in IMMUNE_LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            ts = datetime.fromisoformat(str(record.get("ts", "")).replace("Z", "+00:00"))
        except (json.JSONDecodeError, ValueError):
            continue
        if record.get("type") == "fix" and record.get("lane") == "green" and ts >= cutoff:
            records.append(record)
    return records


def _finding(code: str, lane: str, severity: str, title: str, detail: str,
             remedy: str, source: str) -> dict:
    return {"code": code, "lane": lane, "severity": severity, "title": title,
            "detail": detail, "remedy": remedy, "auto_fix": None,
            "source": source, "new": True}


def commerce_findings(base: dict) -> list[dict]:
    findings = []
    ledger = base.get("commerce_ledger", {})
    for order in ledger.get("failed_orders", []) if ledger.get("ok") else []:
        who = order.get("name") or order.get("email") or "customer"
        findings.append(_finding(
            "failed-order", "red", "critical", f"Failed order · {who}",
            str(order.get("error") or "delivery failed"),
            "Restore this paid customer's delivery and confirm it by hand.", "commerce-ledger"))
    for brand, checkout in base.get("checkout", {}).items():
        if checkout.get("ok") is False and "unavailable" not in str(checkout.get("error", "")):
            findings.append(_finding(
                "money-path", "red", "critical", f"Checkout probe · {brand}",
                str(checkout.get("error") or "checkout unhealthy"),
                "Investigate the checkout manually; money-path code never auto-heals.",
                "checkout-monitor"))
    return findings


def site_findings(site: dict) -> list[dict]:
    findings: list[dict] = []
    gsc = site.get("gsc", {})
    if gsc.get("ok") is not False and gsc.get("overall"):
        current = gsc.get("overall", {})
        files = sorted(GSC_SNAPSHOT_DIR.glob("*.json"))
        if len(files) >= 2:
            previous = _read_json(files[-2]).get("overall", {})
            if previous.get("impressions", 0):
                drop = 100 * (previous["impressions"] - current.get("impressions", 0)) / previous["impressions"]
                if drop > 20:
                    findings.append(_finding(
                        "site-health", "yellow", "high", "GSC impression drop",
                        f"impressions down {drop:.1f}% vs prior snapshot",
                        "Inspect indexing/query losses and propose a reviewed fix.", "gsc-snapshot"))
    cwv = site.get("cwv", {})
    for result in cwv.get("results", []) if cwv.get("ok") is not False else []:
        failed = [key for key, grade in result.get("grades", {}).items() if grade == "FAIL"]
        if failed:
            money = any(term in result.get("url", "") for term in ("/questionnaire/", "/coaching/"))
            findings.append(_finding(
                "money-path" if money else "site-health", "red" if money else "yellow",
                "critical" if money else "high", f"CWV · {result.get('label', 'page')}",
                f"{result.get('strategy', 'unknown')}: {', '.join(failed)} failed",
                ("Inspect manually; this is a money-path page." if money else
                 "Inspect the snapshot and propose a performance fix."), "cwv-snapshot"))
    return findings


def rank_findings(findings: list[dict]) -> list[dict]:
    unique: dict[tuple[str, str, str], dict] = {}
    for finding in findings:
        key = (finding.get("code", ""), finding.get("title", ""), finding.get("source", ""))
        if key in unique and finding.get("detail") not in unique[key].get("detail", ""):
            unique[key]["detail"] += "; " + finding.get("detail", "")
        else:
            unique[key] = dict(finding)
    return sorted(unique.values(), key=lambda f: (
        LANE_RANK.get(f.get("lane"), 9), SEVERITY_RANK.get(f.get("severity"), 9),
        f.get("title", "")))


def aggregate(offline: bool = False) -> dict:
    base = collect_base_intel(offline=offline)
    immune = load_immune()
    ecosystem = load_ecosystem()
    site = load_site_health()
    findings = commerce_findings(base) + site_findings(site)
    findings += [f for f in immune.get("findings", []) if f.get("new", True)]
    findings += ecosystem.get("findings", [])
    ranked = rank_findings(findings)
    unavailable = []
    for label, source in (
        ("commerce", base.get("commerce_ledger", {})), ("immune", immune),
        ("ecosystem CI", ecosystem.get("availability", {}).get("ci", ecosystem)),
        ("cron", ecosystem.get("availability", {}).get("cron", ecosystem)),
        ("GSC", site.get("gsc", {})), ("CWV", site.get("cwv", {})),
    ):
        if source.get("ok") is False or source.get("error"):
            unavailable.append(label)
    suppressed = ecosystem.get("counts", {}).get("suppressed", 0)
    suppressed += sum(1 for f in immune.get("findings", []) if not f.get("new", True))
    suppressed += sum(1 for f in ranked if f.get("lane") == "green")
    return {
        "date": base.get("date", date.today().isoformat()), "base": base,
        "immune": immune, "ecosystem": ecosystem, "site_health": site,
        "findings": ranked, "auto_healed": load_recent_heals(),
        "suppressed": suppressed, "unavailable": sorted(set(unavailable)),
    }


def _sales_amount(ledger: dict) -> str:
    for key in ("sales_total", "sales", "revenue", "revenue_total", "gross_sales"):
        value = ledger.get(key)
        if isinstance(value, (int, float)):
            return f"${value:,.2f}"
    amounts = [o.get("amount") for o in ledger.get("orders", [])]
    if amounts and all(isinstance(value, (int, float)) for value in amounts):
        return f"${sum(amounts):,.2f}"
    return "$ unavailable"


def render_morning_command(command: dict) -> tuple[str, str]:
    date_label = command["date"]
    base = command["base"]
    ledger = base.get("commerce_ledger", {})
    orders = ledger.get("orders", []) if ledger.get("ok") else []
    failed = ledger.get("failed_orders", []) if ledger.get("ok") else []
    human = [f for f in command["findings"] if f.get("lane") in {"red", "yellow"}]
    reds = [f for f in human if f.get("lane") == "red"]
    system_line = "systems up" if not reds and not command["unavailable"] else (
        f"{len(reds)} red" if reds else f"{len(command['unavailable'])} sources unavailable")
    attention = "1 thing needs you" if len(human) == 1 else f"{len(human)} things need you"
    top = (f"{len(orders)} order{'s' if len(orders) != 1 else ''}; {system_line}; "
           f"{attention}.")
    lines = [f"MORNING COMMAND · {date_label}", f"TOP LINE: {top}", "", "💰 MONEY"]
    funnel_bits = []
    for brand, ga4 in base.get("ga4", {}).items():
        if ga4.get("ok"):
            funnel = ga4.get("funnel", {})
            funnel_bits.append(
                f"{brand} CTA {funnel.get('cta_click', 0)} → submit "
                f"{funnel.get('form_submit', 0)} → checkout "
                f"{funnel.get('begin_checkout', 0)} → purchase {funnel.get('purchase', 0)}"
            )
    order_label = f"{len(orders)} order{'s' if len(orders) != 1 else ''}"
    lines.append(
        f"{order_label} · sales {_sales_amount(ledger)} · {len(failed)} failed/lost" +
        (f" · funnel {'; '.join(funnel_bits)}" if funnel_bits else " · funnel unavailable"))

    lines.extend(["", "🔴 ACT TODAY"])
    if human:
        for index, finding in enumerate(human, 1):
            lines.append(f"{index}. {finding.get('title')} · cause: {finding.get('detail')} · action: {finding.get('remedy')}")
    else:
        lines.append("None — let the systems run.")

    lines.extend(["", "🟢 AUTO-HEALED"])
    heals = command.get("auto_healed", [])
    if heals:
        lines.append(f"{len(heals)} fixed overnight:")
        for record in heals:
            lines.append(f"- {record.get('issue_class', 'issue')} · {record.get('fix_applied', 'fixed and verified')}")
    else:
        lines.append("0 fixed overnight.")

    lines.extend(["", "🟡 PROPOSED"])
    proposals = [f for f in human if re.search(r"https://github\.com/[^\s]+/pull/\d+", f.get("detail", ""))]
    if proposals:
        for finding in proposals:
            url = re.search(r"https://github\.com/[^\s]+/pull/\d+", finding["detail"]).group(0)
            lines.append(f"- {finding.get('title')} → {url}")
    else:
        lines.append("No PRs are waiting for approval.")

    lines.extend(["", "📊 PULSE"])
    gsc = command["site_health"].get("gsc", {})
    if gsc.get("ok") is not False and gsc.get("overall"):
        o = gsc["overall"]
        lines.append(f"GSC (7d): {o.get('clicks', 0)} clicks · {o.get('impressions', 0)} impressions · {o.get('ctr', 0)}% CTR · pos {o.get('position', 0)}")
    else:
        lines.append("GSC: unavailable")
    cwv = command["site_health"].get("cwv", {})
    if cwv.get("ok") is not False and cwv.get("summary"):
        s = cwv["summary"]
        lines.append(f"CWV: score {s.get('avg_performance_score', 'unavailable')} · {s.get('fail_count', 0)} fails · {s.get('errors', 0)} errors")
    else:
        lines.append("CWV: unavailable")
    for brand, ga4 in base.get("ga4", {}).items():
        if ga4.get("ok"):
            lines.append(f"{brand}: {ga4.get('sessions', 0)} sessions vs {ga4.get('sessions_7d_avg', 0)} 7d avg")
    if command["unavailable"]:
        lines.append("Unavailable: " + ", ".join(command["unavailable"]))

    lines.extend(["", "🎯 DECIDE"])
    decisions = [f for f in human if f.get("lane") == "yellow"][:3]
    if decisions:
        for finding in decisions:
            lines.append(f"- {finding.get('title')}: approve investigation/fix, or accept as known backlog.")
    else:
        lines.append("No owner-only decision today.")
    lines.extend(["", f"— suppressed: {command['suppressed']} green/known-noise items"])
    subject = f"Morning Command · {date_label} · {len(human)} need you"
    return subject, "\n".join(lines)


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
        'letter-spacing:3px;color:#777777;margin-bottom:4px">MORNING COMMAND</div>'
        f'{body}'
        '<div style="margin-top:28px;padding-top:12px;border-top:1px solid #d0d0c8;'
        'font-family:\'Courier New\',monospace;font-size:11px;color:#999">'
        'gravel-race-automation / daily_intel.py &middot; trend snapshots: '
        'data/intel-snapshots/</div></div></div>'
    )
    code, body_resp = _http("https://api.resend.com/emails", data={
        "from": "Morning Command <matti@gravelgodcycling.com>",
        "to": [INTEL_TO],
        "subject": subject,
        "html": html,
    }, headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"})
    if code != 200:
        raise RuntimeError(f"Resend {code}: {body_resp[:200]}")
    return json.loads(body_resp).get("id", "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Single ranked Morning Command composer")
    ap.add_argument("--preview", action="store_true",
                    help="offline-safe dry run: print only; never send or write snapshots")
    ap.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--json", action="store_true",
                    help="print the aggregate and rendered report as JSON; never send")
    ap.add_argument("--no-llm", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args()

    preview = args.preview or args.dry_run
    command = aggregate(offline=preview or args.json)
    subject, report = render_morning_command(command)
    if args.json:
        print(json.dumps({**command, "subject": subject, "report": report}, indent=2, default=str))
        return 0
    if preview:
        print(f"SUBJECT: {subject}\n\n{report}")
        return 0

    today = command["date"]
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = {**command["base"], "morning_command": {
        "findings": command["findings"], "auto_healed": command["auto_healed"],
        "suppressed": command["suppressed"], "unavailable": command["unavailable"],
    }, "report": report}
    (SNAPSHOT_DIR / f"{today}.json").write_text(
        json.dumps(snapshot, indent=1, default=str) + "\n", encoding="utf-8")
    (SNAPSHOT_DIR / f"{today}.md").write_text(
        f"# {subject}\n\n{report}\n", encoding="utf-8")
    print(f"snapshot: data/intel-snapshots/{today}.json")
    print(f"subject:  {subject}")
    msg_id = send_email(subject, report)
    print(f"sent:     {msg_id} → {INTEL_TO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
