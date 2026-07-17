#!/usr/bin/env python3
"""
Daily Report Email — Gravel God

Generates a branded HTML report email with site health, business metrics,
and rule-based trend commentary. Sends via Resend, archives to reports/daily/.

Data sources:
  - Always available: race-index.json, blog-index.json, race-data/*.json,
    ab_experiments.py, sitemap.xml, wordpress/output/
  - Requires credentials: GA4 Data API, Supabase (revenue, athletes)

Usage:
    python scripts/daily_report.py                        # Send email
    python scripts/daily_report.py --dry-run              # Generate + archive, no send
    python scripts/daily_report.py --stdout               # Print HTML to stdout
    python scripts/daily_report.py --to matt@example.com  # Override recipient
    python scripts/daily_report.py --no-archive           # Skip saving to reports/daily/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from html import escape as html_escape
from pathlib import Path
from xml.etree import ElementTree

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(PROJECT_ROOT / ".env")

CURRENT_DATE = date.today()
DEFAULT_RECIPIENT = "gravelgodcoaching@gmail.com"
REPORTS_DIR = PROJECT_ROOT / "reports" / "daily"


# ── Data Collectors ────────────────────────────────────────────────


def collect_race_stats() -> dict:
    """Race database stats from race-index.json."""
    try:
        path = PROJECT_ROOT / "web" / "race-index.json"
        if not path.exists():
            return {"error": "race-index.json not found"}
        with open(path) as f:
            races = json.load(f)

        tier_counts = Counter(r.get("tier") for r in races)
        months = Counter(r.get("month") for r in races)

        # Upcoming races (next 3 months)
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        upcoming_months = set()
        for i in range(3):
            idx = (CURRENT_DATE.month - 1 + i) % 12
            upcoming_months.add(month_names[idx])
        upcoming = [r for r in races if r.get("month") in upcoming_months]

        return {
            "total": len(races),
            "tier_counts": {f"T{k}": v for k, v in sorted(tier_counts.items()) if k},
            "upcoming_count": len(upcoming),
            "upcoming_races": sorted(
                upcoming, key=lambda r: r.get("overall_score", 0), reverse=True
            )[:5],
        }
    except Exception as e:
        return {"error": str(e)}


def collect_blog_stats() -> dict:
    """Blog content stats from blog-index.json."""
    try:
        path = PROJECT_ROOT / "web" / "blog-index.json"
        if not path.exists():
            return {"total": 0, "categories": {}}
        with open(path) as f:
            blogs = json.load(f)

        categories = Counter(b.get("category", "uncategorized") for b in blogs)
        recent = [
            b for b in blogs
            if b.get("date") and b["date"] >= (CURRENT_DATE - timedelta(days=7)).isoformat()
        ]

        return {
            "total": len(blogs),
            "categories": dict(categories.most_common()),
            "recent_count": len(recent),
            "recent": recent[:5],
        }
    except Exception as e:
        return {"error": str(e)}


def collect_data_quality() -> dict:
    """Data quality scan of race-data/*.json."""
    try:
        race_dir = PROJECT_ROOT / "race-data"
        if not race_dir.exists():
            return {"error": "race-data/ not found"}

        total = 0
        stale_dates = 0
        missing_dates = 0
        stubs = 0
        missing_coords = 0

        for f in sorted(race_dir.glob("*.json")):
            try:
                with open(f) as fp:
                    data = json.load(fp)
            except (json.JSONDecodeError, OSError):
                continue

            total += 1
            race = data.get("race", {})
            gg = race.get("gravel_god_rating", {})

            # Check date
            race_date = race.get("date")
            if not race_date or race_date == "TBD":
                missing_dates += 1
            elif "2025" in str(race_date) or "2024" in str(race_date):
                stale_dates += 1

            # Check for stubs (no final_verdict)
            fv = gg.get("final_verdict", {})
            if not fv.get("course_description"):
                stubs += 1

            # Check coordinates
            loc = race.get("location", {})
            if not loc.get("lat") or not loc.get("lng"):
                missing_coords += 1

        quality_score = round(
            ((total - stale_dates - stubs) / total * 100) if total else 0
        )

        return {
            "total_profiles": total,
            "stale_dates": stale_dates,
            "missing_dates": missing_dates,
            "stubs": stubs,
            "missing_coords": missing_coords,
            "quality_score": quality_score,
        }
    except Exception as e:
        return {"error": str(e)}


def collect_ab_status() -> dict:
    """Active A/B experiment status."""
    try:
        from wordpress.ab_experiments import EXPERIMENTS

        today = CURRENT_DATE.isoformat()
        active = []
        for exp in EXPERIMENTS:
            start = exp.get("start", "")
            end = exp.get("end")
            if start <= today and (end is None or end >= today):
                days_running = (CURRENT_DATE - date.fromisoformat(start)).days
                active.append({
                    "id": exp["id"],
                    "description": exp.get("description", ""),
                    "variants": len(exp.get("variants", [])),
                    "days_running": days_running,
                    "traffic": exp.get("traffic", 0),
                })

        return {"active_count": len(active), "experiments": active}
    except Exception as e:
        return {"error": str(e)}


def collect_seo_health() -> dict:
    """SEO health from sitemap and output dirs."""
    try:
        sitemap_path = PROJECT_ROOT / "web" / "sitemap.xml"
        sitemap_count = 0
        if sitemap_path.exists():
            tree = ElementTree.parse(sitemap_path)
            ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            # Check if index or urlset
            root = tree.getroot()
            if "sitemapindex" in root.tag:
                sitemap_count = len(root.findall(".//sm:sitemap", ns))
            else:
                sitemap_count = len(root.findall(".//sm:url", ns))

        # Count output pages
        output_dir = PROJECT_ROOT / "wordpress" / "output"
        prep_kit_count = 0
        race_page_count = 0
        if output_dir.exists():
            pk_dir = output_dir / "prep-kit"
            if pk_dir.exists():
                prep_kit_count = sum(1 for _ in pk_dir.glob("*.html"))
            race_pages = [
                d for d in output_dir.iterdir()
                if d.is_dir() and (d / "index.html").exists()
                and d.name not in ("prep-kit", "assets", "race")
            ]
            race_page_count = len(race_pages)

        return {
            "sitemap_entries": sitemap_count,
            "prep_kits": prep_kit_count,
            "race_pages": race_page_count,
        }
    except Exception as e:
        return {"error": str(e)}


def collect_ga4_metrics() -> dict:
    """GA4 analytics — requires credentials."""
    try:
        from mission_control.services.ga4 import (
            get_conversion_events,
            get_daily_sessions,
            get_top_pages,
            get_traffic_sources,
        )

        daily = get_daily_sessions(days=14)
        if not daily:
            return {"configured": False}

        # Last 7 days vs previous 7 days
        if len(daily) >= 14:
            recent_7 = sum(d["sessions"] for d in daily[-7:])
            prev_7 = sum(d["sessions"] for d in daily[-14:-7])
        elif len(daily) >= 7:
            recent_7 = sum(d["sessions"] for d in daily[-7:])
            prev_7 = None
        else:
            recent_7 = sum(d["sessions"] for d in daily)
            prev_7 = None

        top_pages = get_top_pages(days=7, limit=5)
        sources = get_traffic_sources(days=7)
        conversions = get_conversion_events(days=7)

        pct_change = None
        if prev_7 and prev_7 > 0:
            pct_change = round((recent_7 - prev_7) / prev_7 * 100, 1)

        return {
            "configured": True,
            "sessions_7d": recent_7,
            "sessions_prev_7d": prev_7,
            "sessions_pct_change": pct_change,
            "top_pages": top_pages[:5],
            "sources": sources[:5],
            "conversions": conversions[:5],
        }
    except Exception:
        return {"configured": False}


def collect_revenue() -> dict:
    """Revenue metrics — requires Supabase."""
    try:
        from mission_control.services.revenue import (
            monthly_revenue,
            plans_sold_this_month,
            revenue_vs_target,
            total_open_pipeline_value,
        )

        rvt = revenue_vs_target()
        plans = plans_sold_this_month()
        pipeline = total_open_pipeline_value()

        return {
            "configured": True,
            "mtd_revenue": rvt["actual"],
            "target": rvt["target"],
            "pct_of_target": rvt["pct"],
            "remaining": rvt["remaining"],
            "plans_sold": plans,
            "pipeline_value": pipeline,
            "month": rvt["month"],
        }
    except Exception:
        return {"configured": False}


def collect_athletes() -> dict:
    """Athlete stats — requires Supabase."""
    try:
        from mission_control.services.stats import dashboard_stats

        stats = dashboard_stats()
        return {
            "configured": True,
            "total": stats.get("total_athletes", 0),
            "active_plans": stats.get("active_plans", 0),
            "delivered": stats.get("delivered", 0),
            "due_touchpoints": stats.get("due_touchpoints", 0),
            "nps_score": stats.get("nps_score"),
            "nps_count": stats.get("nps_count", 0),
        }
    except Exception:
        return {"configured": False}


def collect_enrollments() -> dict:
    """New sequence enrollments (last 24h) with reply context — the
    friend-register KPI surface. Requires Supabase."""
    try:
        import urllib.request
        from datetime import timezone as _tz

        # REST, not the supabase SDK — local cron python lacks the package
        # (same pattern as scripts/sequence_report.py).
        base = os.environ["SUPABASE_URL"]
        key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
               or os.environ.get("SUPABASE_SERVICE_KEY", ""))
        url = (f"{base}/rest/v1/gg_sequence_enrollments"
               "?select=contact_email,contact_name,sequence_id,source,source_data,enrolled_at"
               "&order=enrolled_at.desc&limit=500")
        req = urllib.request.Request(
            url, headers={"apikey": key, "Authorization": f"Bearer {key}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode())

        cutoff = (datetime.now(_tz.utc) - timedelta(hours=24)).isoformat()
        new = [r for r in rows if (r.get("enrolled_at") or "") >= cutoff]
        people = []
        for r in new:
            sd = r.get("source_data") or {}
            if isinstance(sd, str):
                try:
                    sd = json.loads(sd)
                except (ValueError, TypeError):
                    sd = {}
            context = (
                (sd.get("wb_guide") and "guide: " + str(sd["wb_guide"]))
                or (sd.get("wb_trail") and "viewed: " + str(sd["wb_trail"]))
                or (sd.get("race_name") and "race: " + str(sd["race_name"]))
                or "\u2014"
            )
            people.append({
                "email": r.get("contact_email", ""),
                "name": r.get("contact_name", ""),
                "sequence": r.get("sequence_id", ""),
                "source": r.get("source", ""),
                "brand": sd.get("brand", "gravelgod"),
                "context": context,
                "at": (r.get("enrolled_at") or "")[:16].replace("T", " "),
            })
        return {"configured": True, "count": len(people), "people": people}
    except Exception:
        return {"configured": False}


def collect_pipeline_e2e() -> dict:
    """Latest custom-training-plan-pipeline daily E2E result (see ~/gg-e2e/).

    Wrapped in a broad guard: this is a best-effort read of an external file and
    must NEVER break the brief. Any failure degrades to ``configured: False``.
    """
    import re

    try:
        reports = Path.home() / "gg-e2e" / "reports"
        files = sorted(reports.glob("e2e-20*.md"))
        if not files:
            return {"configured": False}
        latest = files[-1]
        text = latest.read_text(errors="replace")

        m = re.match(r"e2e-(\d{4}-\d{2}-\d{2})\.md", latest.name)
        report_date = m.group(1) if m else "?"
        stale = report_date != CURRENT_DATE.isoformat()

        if "deterministic gates PASS" in text:
            det_gate = "PASS"
        elif "❌ FAIL" in text or "gates FAIL" in text or "deterministic gates" not in text:
            det_gate = "FAIL"
        else:
            det_gate = "?"
        vm = re.search(r"VERDICT:\s*(GO|NO-GO)", text)
        verdict = vm.group(1) if vm else "?"
        pm = re.search(r"^- pytest:\s*\*\*(.+?)\*\*", text, re.M)
        pytest_summary = pm.group(1) if pm else "?"
        rm = re.search(r"^- Ref:\s*`(.+?)`\s*@\s*`(.+?)`", text, re.M)
        ref, commit = (rm.group(1), rm.group(2)) if rm else ("?", "?")
        racem = re.search(r"^- Fixture race:\s*\*\*(.+?)\*\*", text, re.M)
        race = racem.group(1) if racem else "?"

        # Capture blockers listed under the BLOCKERS: heading. Stop at WATCH: or
        # the closing code-fence. Headings may carry markdown hashes (## WATCH:).
        blockers = []
        in_block = False
        for line in text.splitlines():
            if re.match(r"\s*#*\s*BLOCKERS:", line):
                in_block = True
                continue
            if in_block:
                if re.match(r"\s*#*\s*WATCH:", line) or line.strip() == "```":
                    break
                if line.strip() == "":
                    continue
                bm = re.match(r"\s*(\d+)\.\s+(.*)", line)
                if bm:
                    blockers.append(bm.group(2).strip())
                elif blockers and line.strip():
                    blockers[-1] += " " + line.strip()
        # "none" is a sentinel only when it is the SOLE, standalone entry.
        if len(blockers) == 1 and blockers[0].strip().lower().rstrip(".") == "none":
            blockers = []
        blocker_count = len(blockers)

        return {
            "configured": True,
            "report_date": report_date,
            "stale": stale,
            "det_gate": det_gate,
            "verdict": verdict,
            "pytest": pytest_summary,
            "ref": ref,
            "commit": commit,
            "race": race,
            "blocker_count": blocker_count,
            "blockers": blockers[:4],
        }
    except Exception:
        return {"configured": False}


# ── Commentary Engine ──────────────────────────────────────────────


def _load_yesterday_data() -> dict | None:
    """Load yesterday's JSON sidecar for trend comparison."""
    yesterday = CURRENT_DATE - timedelta(days=1)
    path = REPORTS_DIR / f"{yesterday.isoformat()}.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def generate_commentary(data: dict) -> list[str]:
    """Rule-based interpretive commentary. Returns list of bullet strings."""
    bullets = []

    # Session trends
    ga4 = data.get("ga4", {})
    if ga4.get("configured") and ga4.get("sessions_pct_change") is not None:
        pct = ga4["sessions_pct_change"]
        if pct > 15:
            bullets.append(
                f"Sessions up {pct}% week-over-week. Check top pages for what's driving traffic."
            )
        elif pct < -15:
            bullets.append(
                f"Sessions down {abs(pct)}% week-over-week. Review traffic sources for drops."
            )

    # Revenue pacing
    rev = data.get("revenue", {})
    if rev.get("configured") and rev.get("target"):
        day_of_month = CURRENT_DATE.day
        # Expected pace: proportional to day of month (assume 30-day month)
        expected_pct = round(day_of_month / 30 * 100, 1)
        actual_pct = rev.get("pct_of_target", 0)
        if actual_pct > expected_pct + 10:
            bullets.append(
                f"Revenue ahead of pace: {actual_pct}% of target vs {expected_pct}% expected by day {day_of_month}."
            )
        elif actual_pct < expected_pct - 10:
            bullets.append(
                f"Revenue behind pace: {actual_pct}% of target vs {expected_pct}% expected by day {day_of_month}."
            )

    # Data quality trend (compare vs yesterday)
    yesterday = _load_yesterday_data()
    quality = data.get("data_quality", {})
    if yesterday and not quality.get("error"):
        prev_quality = yesterday.get("data_quality", {})
        prev_stale = prev_quality.get("stale_dates", 0)
        curr_stale = quality.get("stale_dates", 0)
        if curr_stale < prev_stale:
            bullets.append(
                f"Data quality improving: stale dates reduced from {prev_stale} to {curr_stale}."
            )
        elif curr_stale > prev_stale:
            bullets.append(
                f"Data quality degrading: stale dates increased from {prev_stale} to {curr_stale}."
            )

    # A/B experiment maturity
    ab = data.get("ab_status", {})
    for exp in ab.get("experiments", []):
        days = exp.get("days_running", 0)
        if days >= 14:
            bullets.append(
                f"A/B test '{exp['id']}' running {days} days. Consider evaluating results."
            )
        elif days >= 7:
            bullets.append(
                f"A/B test '{exp['id']}' running {days} days. Nearing evaluation window."
            )

    # Athlete touchpoints due
    athletes = data.get("athletes", {})
    if athletes.get("configured"):
        due = athletes.get("due_touchpoints", 0)
        if due > 0:
            bullets.append(f"{due} athlete touchpoint(s) due today.")

    # Fallback
    if not bullets:
        bullets.append("No notable trends today. Steady state.")

    return bullets


# ── HTML Renderer ──────────────────────────────────────────────────


def _trend_arrow(current, previous) -> str:
    """Return HTML trend arrow span."""
    if current is None or previous is None:
        return ""
    if current > previous:
        return ' <span style="color:#178079;">&#8593;</span>'
    elif current < previous:
        return ' <span style="color:#c0392b;">&#8595;</span>'
    return ' <span style="color:#7d695d;">&#8212;</span>'


def _pct_change_str(current, previous) -> str:
    """Return formatted percentage change string."""
    if current is None or previous is None or previous == 0:
        return ""
    pct = round((current - previous) / previous * 100, 1)
    sign = "+" if pct > 0 else ""
    return f" ({sign}{pct}%)"


def _not_configured_section(title: str) -> str:
    """Render a 'Not Configured' placeholder section."""
    return f"""
    <tr><td style="padding:20px 32px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-family:'Courier New',monospace;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;padding-bottom:8px;">{title}</td></tr>
        <tr><td style="font-family:Georgia,serif;font-size:14px;color:#7d695d;padding:12px;border:1px dashed #d4c5b9;">
          Not configured. See <code>scripts/daily_report.py</code> for setup instructions.
        </td></tr>
      </table>
    </td></tr>"""


def _metric_cell(label: str, value: str, width: str = "25%") -> str:
    """Render a single metric in the key metrics bar."""
    return f"""<td width="{width}" style="text-align:center;padding:12px 8px;">
          <div style="font-family:'Courier New',monospace;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;">{label}</div>
          <div style="font-family:Georgia,serif;font-size:22px;color:#3a2e25;padding-top:4px;">{value}</div>
        </td>"""


def render_html(data: dict) -> str:
    """Render the full HTML email from collected data."""
    report_date = CURRENT_DATE.strftime("%B %d, %Y")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    race = data.get("race_stats", {})
    blog = data.get("blog_stats", {})
    quality = data.get("data_quality", {})
    ab = data.get("ab_status", {})
    seo = data.get("seo_health", {})
    ga4 = data.get("ga4", {})
    rev = data.get("revenue", {})
    ath = data.get("athletes", {})
    e2e = data.get("pipeline_e2e", {})
    commentary = data.get("commentary", [])

    # Key metrics bar values
    sessions_str = str(ga4.get("sessions_7d", "--")) if ga4.get("configured") else "--"
    revenue_str = f"${rev.get('mtd_revenue', 0):,.0f}" if rev.get("configured") else "--"
    athletes_str = str(ath.get("total", "--")) if ath.get("configured") else "--"
    quality_str = f"{quality.get('quality_score', '--')}%" if not quality.get("error") else "--"

    # ── Build sections ──
    sections = []

    # 1. Header
    sections.append(f"""
    <tr><td style="background:#3a2e25;padding:24px 32px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="font-family:'Courier New',monospace;font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#9a7e0a;">GRAVEL GOD</td>
          <td style="text-align:right;font-family:'Courier New',monospace;font-size:11px;color:#7d695d;">{report_date}</td>
        </tr>
        <tr><td colspan="2" style="font-family:Georgia,serif;font-size:20px;color:#ffffff;padding-top:8px;">Daily Report</td></tr>
      </table>
    </td></tr>""")

    # 2. Key Metrics Bar
    sections.append(f"""
    <tr><td style="padding:0;border-bottom:2px solid #d4c5b9;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          {_metric_cell("Sessions (7d)", sessions_str)}
          {_metric_cell("Revenue MTD", revenue_str)}
          {_metric_cell("Athletes", athletes_str)}
          {_metric_cell("Quality", quality_str)}
        </tr>
      </table>
    </td></tr>""")

    # 3. Commentary
    if commentary:
        commentary_html = ""
        for bullet in commentary:
            commentary_html += f'<tr><td style="font-family:Georgia,serif;font-size:14px;color:#3a2e25;padding:4px 0 4px 16px;line-height:1.6;">&#8226; {bullet}</td></tr>\n'
        sections.append(f"""
    <tr><td style="padding:20px 32px 12px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-family:'Courier New',monospace;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;padding-bottom:8px;">Commentary</td></tr>
        {commentary_html}
      </table>
    </td></tr>""")

    # 3b. Pipeline E2E (custom training plan pipeline daily test + codex-sol)
    if e2e.get("configured"):
        gate = e2e.get("det_gate", "?")
        verdict = e2e.get("verdict", "?")
        gate_color = "#178079" if gate == "PASS" else "#c0392b"
        verdict_color = "#178079" if verdict == "GO" else ("#c0392b" if verdict == "NO-GO" else "#7d695d")

        def _pill(label: str, color: str) -> str:
            return (f'<span style="display:inline-block;font-family:\'Courier New\',monospace;'
                    f'font-size:11px;font-weight:bold;color:#fff;background:{color};'
                    f'padding:3px 10px;border-radius:3px;letter-spacing:0.5px;">{label}</span>')

        # Report content is external text — escape before it enters the markup.
        e_pytest = html_escape(str(e2e.get("pytest", "?")))
        e_ref = html_escape(str(e2e.get("ref", "?")))
        e_commit = html_escape(str(e2e.get("commit", "?")))
        e_race = html_escape(str(e2e.get("race", "?")))
        e_date = html_escape(str(e2e.get("report_date", "?")))

        stale_html = ""
        if e2e.get("stale"):
            stale_html = (f'<tr><td style="font-family:Georgia,serif;font-size:13px;color:#b8860b;'
                          f'padding:6px 0 0;">&#9888; E2E did not run today &mdash; showing last result from '
                          f'{e_date}.</td></tr>')

        blockers_html = ""
        if e2e.get("blocker_count", 0) > 0:
            items = ""
            for b in e2e.get("blockers", []):
                snippet = html_escape(b[:180]) + ("&hellip;" if len(b) > 180 else "")
                items += (f'<tr><td style="font-family:Georgia,serif;font-size:12px;color:#3a2e25;'
                          f'padding:2px 0 2px 16px;line-height:1.5;">&#8226; {snippet}</td></tr>\n')
            more = e2e.get("blocker_count", 0) - len(e2e.get("blockers", []))
            more_html = (f'<tr><td style="font-family:Georgia,serif;font-size:12px;color:#7d695d;'
                         f'padding:2px 0 2px 16px;">&#8226; &hellip;and {more} more (see '
                         f'~/gg-e2e/reports/e2e-{e_date}.md)</td></tr>') if more > 0 else ""
            blockers_html = (f'<tr><td style="font-family:Georgia,serif;font-size:12px;color:#7d695d;'
                             f'padding:8px 0 2px;">codex-sol blockers ({e2e.get("blocker_count")}):</td></tr>'
                             f'{items}{more_html}')

        sections.append(f"""
    <tr><td style="padding:20px 32px 12px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-family:'Courier New',monospace;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;padding-bottom:8px;">Pipeline E2E &mdash; Custom Training Plan</td></tr>
        <tr><td style="padding:2px 0 6px;">
          {_pill("GATES " + gate, gate_color)} &nbsp; {_pill("codex-sol " + verdict, verdict_color)}
        </td></tr>
        <tr><td style="font-family:Georgia,serif;font-size:13px;color:#3a2e25;line-height:1.7;">
          pytest: {e_pytest}<br>
          ref: <span style="font-family:'Courier New',monospace;font-size:12px;">{e_ref}@{e_commit}</span> &middot; fixture race: {e_race}
        </td></tr>
        {stale_html}
        {blockers_html}
      </table>
    </td></tr>""")

    # 4. Race Database
    if not race.get("error"):
        tier_rows = ""
        for tier_key in ["T1", "T2", "T3", "T4"]:
            count = race.get("tier_counts", {}).get(tier_key, 0)
            tier_rows += f'<tr><td style="font-family:\'Courier New\',monospace;font-size:13px;color:#3a2e25;padding:3px 12px;border-bottom:1px solid #f0ebe3;">{tier_key}</td><td style="font-family:Georgia,serif;font-size:14px;color:#3a2e25;padding:3px 12px;border-bottom:1px solid #f0ebe3;text-align:right;">{count}</td></tr>\n'

        upcoming_html = ""
        for r in race.get("upcoming_races", []):
            upcoming_html += f'<tr><td style="font-family:Georgia,serif;font-size:13px;color:#3a2e25;padding:2px 0;">{r.get("name", r.get("slug", ""))}</td><td style="font-family:\'Courier New\',monospace;font-size:12px;color:#7d695d;text-align:right;padding:2px 0;">T{r.get("tier", "?")}</td></tr>\n'

        sections.append(f"""
    <tr><td style="padding:20px 32px 12px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-family:'Courier New',monospace;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;padding-bottom:8px;">Race Database — {race.get("total", 0)} Races</td></tr>
        <tr><td>
          <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #d4c5b9;">
            <tr><td style="font-family:'Courier New',monospace;font-size:11px;text-transform:uppercase;color:#7d695d;padding:6px 12px;border-bottom:2px solid #d4c5b9;">Tier</td><td style="font-family:'Courier New',monospace;font-size:11px;text-transform:uppercase;color:#7d695d;padding:6px 12px;border-bottom:2px solid #d4c5b9;text-align:right;">Count</td></tr>
            {tier_rows}
          </table>
        </td></tr>
        {"<tr><td style='padding-top:12px;font-family:Georgia,serif;font-size:13px;color:#7d695d;'>Upcoming (next 3 months): " + str(race.get('upcoming_count', 0)) + " races</td></tr>" if race.get("upcoming_count") else ""}
        {("<tr><td style='padding-top:8px;'><table width='100%' cellpadding='0' cellspacing='0'>" + upcoming_html + "</table></td></tr>") if upcoming_html else ""}
      </table>
    </td></tr>""")

    # 5. Blog Content
    if not blog.get("error"):
        cat_rows = ""
        for cat, count in blog.get("categories", {}).items():
            cat_rows += f'<tr><td style="font-family:Georgia,serif;font-size:13px;color:#3a2e25;padding:2px 0;">{cat}</td><td style="font-family:\'Courier New\',monospace;font-size:13px;color:#3a2e25;text-align:right;padding:2px 0;">{count}</td></tr>\n'

        sections.append(f"""
    <tr><td style="padding:20px 32px 12px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-family:'Courier New',monospace;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;padding-bottom:8px;">Blog Content — {blog.get("total", 0)} Articles</td></tr>
        <tr><td>
          <table width="100%" cellpadding="0" cellspacing="0">
            {cat_rows}
          </table>
        </td></tr>
        <tr><td style="font-family:Georgia,serif;font-size:13px;color:#7d695d;padding-top:8px;">Added this week: {blog.get("recent_count", 0)}</td></tr>
      </table>
    </td></tr>""")

    # 6. GA4 Analytics
    if ga4.get("configured"):
        sessions_arrow = _trend_arrow(ga4.get("sessions_7d"), ga4.get("sessions_prev_7d"))
        pct_str = _pct_change_str(ga4.get("sessions_7d"), ga4.get("sessions_prev_7d"))

        top_pages_html = ""
        for p in ga4.get("top_pages", []):
            top_pages_html += f'<tr><td style="font-family:Georgia,serif;font-size:13px;color:#3a2e25;padding:2px 0;max-width:300px;overflow:hidden;text-overflow:ellipsis;">{p["path"]}</td><td style="font-family:\'Courier New\',monospace;font-size:12px;color:#7d695d;text-align:right;padding:2px 0;">{p["pageviews"]:,}</td></tr>\n'

        sources_html = ""
        for s in ga4.get("sources", []):
            sources_html += f'<tr><td style="font-family:Georgia,serif;font-size:13px;color:#3a2e25;padding:2px 0;">{s["channel"]}</td><td style="font-family:\'Courier New\',monospace;font-size:12px;color:#7d695d;text-align:right;padding:2px 0;">{s["sessions"]:,}</td></tr>\n'

        sections.append(f"""
    <tr><td style="padding:20px 32px 12px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-family:'Courier New',monospace;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;padding-bottom:8px;">GA4 Analytics</td></tr>
        <tr><td style="font-family:Georgia,serif;font-size:14px;color:#3a2e25;padding-bottom:12px;">Sessions (7d): <strong>{ga4.get("sessions_7d", 0):,}</strong>{sessions_arrow}{pct_str}</td></tr>
        {("<tr><td style='font-family:Georgia,serif;font-size:13px;color:#7d695d;padding-bottom:4px;'>Top Pages:</td></tr><tr><td><table width='100%' cellpadding='0' cellspacing='0'>" + top_pages_html + "</table></td></tr>") if top_pages_html else ""}
        {("<tr><td style='font-family:Georgia,serif;font-size:13px;color:#7d695d;padding:8px 0 4px;'>Traffic Sources:</td></tr><tr><td><table width='100%' cellpadding='0' cellspacing='0'>" + sources_html + "</table></td></tr>") if sources_html else ""}
      </table>
    </td></tr>""")
    else:
        sections.append(_not_configured_section("GA4 Analytics"))

    # 7. Revenue & Pipeline
    if rev.get("configured"):
        pct = rev.get("pct_of_target", 0)
        bar_width = min(100, max(0, pct))
        sections.append(f"""
    <tr><td style="padding:20px 32px 12px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-family:'Courier New',monospace;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;padding-bottom:8px;">Revenue — {rev.get("month", "")}</td></tr>
        <tr><td style="font-family:Georgia,serif;font-size:14px;color:#3a2e25;">MTD: <strong>${rev.get("mtd_revenue", 0):,.0f}</strong> / ${rev.get("target", 0):,.0f} ({pct}%)</td></tr>
        <tr><td style="padding:8px 0;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td style="background:#f0ebe3;height:8px;"><div style="background:#178079;height:8px;width:{bar_width}%;"></div></td>
          </tr></table>
        </td></tr>
        <tr><td style="font-family:Georgia,serif;font-size:13px;color:#3a2e25;">Plans sold this month: {rev.get("plans_sold", 0)} &middot; Pipeline: ${rev.get("pipeline_value", 0):,.0f}</td></tr>
      </table>
    </td></tr>""")
    else:
        sections.append(_not_configured_section("Revenue &amp; Pipeline"))

    # 8. Athletes
    if ath.get("configured"):
        nps_str = f"{ath['nps_score']}" if ath.get("nps_score") is not None else "N/A"
        sections.append(f"""
    <tr><td style="padding:20px 32px 12px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-family:'Courier New',monospace;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;padding-bottom:8px;">Athletes</td></tr>
        <tr><td style="font-family:Georgia,serif;font-size:14px;color:#3a2e25;">
          Total: <strong>{ath.get("total", 0)}</strong> &middot;
          Active: {ath.get("active_plans", 0)} &middot;
          Delivered: {ath.get("delivered", 0)}
        </td></tr>
        <tr><td style="font-family:Georgia,serif;font-size:13px;color:#3a2e25;padding-top:4px;">
          NPS: {nps_str} (n={ath.get("nps_count", 0)}) &middot;
          Touchpoints due: {ath.get("due_touchpoints", 0)}
        </td></tr>
      </table>
    </td></tr>""")
    else:
        sections.append(_not_configured_section("Athletes"))


    # 8b. New enrollments (24h) — friend-register reply surface
    enr = data.get("enrollments", {})
    if enr.get("configured"):
        _rows = "".join(
            "<tr>"
            + f"<td style='padding:4px 8px;font-size:12px'>{html_escape(p['at'])}</td>"
            + f"<td style='padding:4px 8px'><b>{html_escape(p['name'] or p['email'])}</b>"
            + f"<br><span style='color:#7d695d;font-size:11px'>{html_escape(p['email'])}</span></td>"
            + f"<td style='padding:4px 8px;font-size:12px'>{html_escape(p['brand'])}</td>"
            + f"<td style='padding:4px 8px;font-size:12px'>{html_escape(p['source'])}</td>"
            + f"<td style='padding:4px 8px;font-size:12px'>{html_escape(p['context'])}</td>"
            + f"<td style='padding:4px 8px;font-size:12px'>{html_escape(p['sequence'])}</td>"
            + "</tr>"
            for p in enr.get("people", [])
        ) or "<tr><td colspan='6' style='padding:8px;color:#7d695d'>none in the last 24h</td></tr>"
        sections.append(f"""
        <tr><td style="font-family:'Courier New',monospace;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;padding-bottom:8px;">New Enrollments (24h) \u2014 {enr.get('count', 0)}</td></tr>
        <tr><td>
        <p style="color:#7d695d;font-size:12px;margin:0 0 6px">Each one is a conversation \u2014 reply fast. Race known? <code>python3 scripts/draft_race_reply.py "&lt;race&gt;"</code></p>
        <table style="width:100%;border-collapse:collapse">
        <tr style="text-align:left"><th style="padding:4px 8px;font-size:11px">when (utc)</th><th style="padding:4px 8px;font-size:11px">who</th><th style="padding:4px 8px;font-size:11px">brand</th><th style="padding:4px 8px;font-size:11px">source</th><th style="padding:4px 8px;font-size:11px">context</th><th style="padding:4px 8px;font-size:11px">sequence</th></tr>
        {_rows}
        </table>
        </td></tr>
""")

    # 9. A/B Experiments
    if not ab.get("error"):
        exp_rows = ""
        for exp in ab.get("experiments", []):
            days = exp.get("days_running", 0)
            days_color = "#c0392b" if days >= 14 else "#178079" if days >= 7 else "#3a2e25"
            exp_rows += f'<tr><td style="font-family:Georgia,serif;font-size:13px;color:#3a2e25;padding:3px 0;">{exp["id"]}</td><td style="font-family:\'Courier New\',monospace;font-size:12px;color:{days_color};text-align:right;padding:3px 0;">{days}d</td></tr>\n'

        sections.append(f"""
    <tr><td style="padding:20px 32px 12px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-family:'Courier New',monospace;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;padding-bottom:8px;">A/B Experiments — {ab.get("active_count", 0)} Active</td></tr>
        <tr><td>
          <table width="100%" cellpadding="0" cellspacing="0">
            {exp_rows if exp_rows else '<tr><td style="font-family:Georgia,serif;font-size:13px;color:#7d695d;">No active experiments.</td></tr>'}
          </table>
        </td></tr>
      </table>
    </td></tr>""")

    # 10. Data Quality
    if not quality.get("error"):
        sections.append(f"""
    <tr><td style="padding:20px 32px 12px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-family:'Courier New',monospace;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;padding-bottom:8px;">Data Quality — {quality.get("quality_score", 0)}%</td></tr>
        <tr><td style="font-family:Georgia,serif;font-size:14px;color:#3a2e25;line-height:1.8;">
          Profiles: {quality.get("total_profiles", 0)}<br>
          Stale dates: {quality.get("stale_dates", 0)}<br>
          Missing dates: {quality.get("missing_dates", 0)}<br>
          Stubs: {quality.get("stubs", 0)}<br>
          Missing coordinates: {quality.get("missing_coords", 0)}
        </td></tr>
      </table>
    </td></tr>""")

    # 11. Quick Links
    sections.append("""
    <tr><td style="padding:20px 32px 12px;border-top:2px solid #d4c5b9;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr><td style="font-family:'Courier New',monospace;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:#7d695d;padding-bottom:8px;">Quick Links</td></tr>
        <tr><td style="font-family:Georgia,serif;font-size:13px;color:#3a2e25;line-height:2;">
          <a href="https://analytics.google.com" style="color:#178079;">GA4 Dashboard</a> &middot;
          <a href="https://gravelgodcycling.com/wp-admin/" style="color:#178079;">WP Admin</a> &middot;
          <a href="https://gravelgodcycling.com/gravel-races/" style="color:#178079;">Race Search</a> &middot;
          <a href="https://dashboard.resend.com" style="color:#178079;">Resend</a>
        </td></tr>
      </table>
    </td></tr>""")

    # 12. Footer
    sections.append(f"""
    <tr><td style="padding:16px 32px;border-top:2px solid #d4c5b9;font-family:'Courier New',monospace;font-size:11px;color:#7d695d;">
      Generated by scripts/daily_report.py &middot; {generated_at}
    </td></tr>""")

    # Assemble
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gravel God Daily Report — {report_date}</title>
</head>
<body style="font-family:Georgia,serif;background:#f8f3ec;margin:0;padding:20px;">
  <table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
  <table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;background:#ffffff;border:2px solid #d4c5b9;">
    {"".join(sections)}
  </table>
  </td></tr></table>
</body>
</html>"""

    return html


# ── Email Sender ───────────────────────────────────────────────────


def send_email(html: str, recipient: str) -> dict:
    """Send the report email via Resend."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        try:
            from mission_control.config import RESEND_API_KEY
            api_key = RESEND_API_KEY
        except Exception:
            pass

    if not api_key:
        return {"success": False, "message": "RESEND_API_KEY not set"}

    try:
        import resend
        resend.api_key = api_key

        from_email = os.environ.get(
            "REPORT_FROM", "Gravel God <matt@gravelgodcycling.com>"
        )

        subject = f"Daily Report — {CURRENT_DATE.strftime('%b %d, %Y')}"
        result = resend.Emails.send({
            "from": from_email,
            "to": [recipient],
            "subject": subject,
            "html": html,
        })

        resend_id = result.get("id", "") if isinstance(result, dict) else ""
        return {"success": True, "resend_id": resend_id, "message": f"Sent to {recipient}"}

    except Exception as e:
        return {"success": False, "message": f"Send failed: {e}"}


# ── Archive ────────────────────────────────────────────────────────


def archive_report(data: dict, html: str) -> Path:
    """Save JSON data + HTML to reports/daily/."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = CURRENT_DATE.isoformat()

    json_path = REPORTS_DIR / f"{date_str}.json"
    html_path = REPORTS_DIR / f"{date_str}.html"

    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

    with open(html_path, "w") as f:
        f.write(html)

    return html_path


# ── Main ───────────────────────────────────────────────────────────


def collect_all() -> dict:
    """Run all data collectors and commentary engine."""
    data = {
        "date": CURRENT_DATE.isoformat(),
        "race_stats": collect_race_stats(),
        "blog_stats": collect_blog_stats(),
        "data_quality": collect_data_quality(),
        "ab_status": collect_ab_status(),
        "seo_health": collect_seo_health(),
        "ga4": collect_ga4_metrics(),
        "revenue": collect_revenue(),
        "athletes": collect_athletes(),
        "enrollments": collect_enrollments(),
        "pipeline_e2e": collect_pipeline_e2e(),
    }
    data["commentary"] = generate_commentary(data)
    return data


def main():
    parser = argparse.ArgumentParser(description="Gravel God Daily Report Email")
    parser.add_argument("--dry-run", action="store_true", help="Generate + archive, no send")
    parser.add_argument("--stdout", action="store_true", help="Print HTML to stdout")
    parser.add_argument("--to", default=os.environ.get("REPORT_TO", DEFAULT_RECIPIENT),
                        help="Override recipient email")
    parser.add_argument("--no-archive", action="store_true", help="Skip saving to reports/daily/")
    args = parser.parse_args()

    # Collect data
    print("Collecting data...", file=sys.stderr)
    data = collect_all()

    # Render HTML
    print("Rendering HTML...", file=sys.stderr)
    html = render_html(data)

    # Archive
    if not args.no_archive:
        path = archive_report(data, html)
        print(f"Archived to {path.parent}/", file=sys.stderr)

    # Output
    if args.stdout:
        print(html)
        return

    if args.dry_run:
        print("Dry run complete. Skipping email send.", file=sys.stderr)
        return

    # Send
    print(f"Sending to {args.to}...", file=sys.stderr)
    result = send_email(html, args.to)
    if result["success"]:
        print(f"Sent. {result.get('message', '')}", file=sys.stderr)
    else:
        print(f"FAILED: {result['message']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
