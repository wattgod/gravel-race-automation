#!/usr/bin/env python3
"""Morning Intel — daily interpreted report for both brands.

Collects GA4, checkout health, Mission Control activity + errors, and
workflow statuses; interprets via Claude with 7-day trend context; emails
gravelgodcoaching@gmail.com; snapshots everything to data/intel-snapshots/
so trends compound. Spec: docs/specs/daily-intel-report.md.

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

    return {
        "new_leads_24h": len(new_enr),
        "leads_by_brand": by_brand,
        "countdown_enrollments": countdown,
        "emails_sent_24h": len(new_sends),
        "opens_24h": opened, "clicks_24h": clicked, "bounces_24h": bounced,
        "new_orders_24h_UNRELIABLE": "use ga4 purchase counts — gg_athletes is not written by purchases",
        "errors_24h": errors[:10],
    }


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
## BROKEN
Every failed probe/collector/error, severity-ranked. If nothing: one line saying so.
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
                items.append(f'<li style="margin:0 0 10px">{inline(_re.sub(r"^\d+\. ", "", lines[i]))}</li>')
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
        "workflows": _safe(collect_workflows),
    }
    trend = load_trend()

    if args.no_llm or not os.environ.get("ANTHROPIC_API_KEY"):
        subject, report = plain_digest(collected)
    else:
        try:
            subject, report = interpret(collected, trend)
        except Exception as e:
            subject, report = plain_digest(collected)
            report = f"**INTERPRETATION FAILED: {e}**\n\n{report}"

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    (SNAPSHOT_DIR / f"{today}.json").write_text(
        json.dumps({**collected, "report": report}, indent=1, default=str))
    (SNAPSHOT_DIR / f"{today}.md").write_text(f"# {subject}\n\n{report}\n")
    print(f"snapshot: data/intel-snapshots/{today}.json")
    print(f"subject:  {subject}")

    if args.dry_run:
        print("\n" + report)
        return 0
    msg_id = send_email(subject, report)
    print(f"sent:     {msg_id} → {INTEL_TO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
