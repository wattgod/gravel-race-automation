#!/usr/bin/env python3
"""
Daily Marketing Report — Gravel God

Generates a daily markdown report with key metrics, trends, content gaps,
and actionable recommendations. Designed to be run daily (manually or via cron).

Data sources:
  - Local: race-index.json, blog-index.json, sitemap.xml, wordpress/output/
  - Remote (when configured): GA4 Data API, Google Search Console API
  - RSS: Substack newsletter feed

Usage:
    python scripts/daily-marketing-report.py
    python scripts/daily-marketing-report.py --output reports/2026-02-14.md
    python scripts/daily-marketing-report.py --json  # Machine-readable output

Setup for GA4/GSC (optional but recommended):
    1. Create a Google Cloud project at console.cloud.google.com
    2. Enable "Google Analytics Data API" and "Search Console API"
    3. Create a service account, download JSON key
    4. Grant service account "Viewer" role on your GA4 property
    5. Add the service account email to Search Console as a user
    6. Set env vars:
       GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
       GA4_PROPERTY_ID=properties/XXXXXXXXX
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CURRENT_DATE = date.today()
SITE_BASE_URL = "https://gravelgodcycling.com"

# ── Report sections ──────────────────────────────────────────────


def load_race_index():
    path = PROJECT_ROOT / "web" / "race-index.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def load_blog_index():
    path = PROJECT_ROOT / "web" / "blog-index.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def load_sitemap():
    path = PROJECT_ROOT / "web" / "sitemap.xml"
    if not path.exists():
        return []
    tree = ElementTree.parse(path)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []
    for url_el in tree.findall(".//sm:url", ns):
        loc = url_el.find("sm:loc", ns)
        if loc is not None:
            urls.append(loc.text)
    return urls


def count_output_pages():
    """Count generated page types in wordpress/output/."""
    output_dir = PROJECT_ROOT / "wordpress" / "output"
    if not output_dir.exists():
        return {}

    counts = {"vs_pages": 0, "state_hubs": 0, "series_hubs": 0, "other": 0}
    series_dir = output_dir / "race" / "series"
    if series_dir.exists():
        counts["series_hubs"] = sum(1 for d in series_dir.iterdir()
                                    if d.is_dir() and (d / "index.html").exists())

    for d in output_dir.iterdir():
        if not d.is_dir():
            continue
        name = d.name
        if "-vs-" in name:
            counts["vs_pages"] += 1
        elif name.startswith("best-gravel-races-"):
            counts["state_hubs"] += 1
        elif name.startswith("power-rankings-"):
            counts["power_rankings"] = 1
        elif name == "calendar":
            counts["calendar"] = 1
        elif name.startswith("tier-"):
            counts["tier_hubs"] = counts.get("tier_hubs", 0) + 1

    return counts


# ── Content gap analysis ─────────────────────────────────────────


def analyze_content_gaps(races, blogs):
    """Find races missing blog posts, prep kits, and other content."""
    blog_slugs = {b["slug"] for b in blogs}
    race_slugs = {r["slug"] for r in races}

    # Races without blog previews
    races_without_blog = []
    for r in races:
        if r["slug"] not in blog_slugs:
            races_without_blog.append(r)

    # Prep kit coverage
    pk_dir = PROJECT_ROOT / "wordpress" / "output" / "prep-kit"
    pk_slugs = set()
    if pk_dir.exists():
        pk_slugs = {f.stem for f in pk_dir.glob("*.html")}

    races_without_pk = [r for r in races if r["slug"] not in pk_slugs]

    # T1/T2 without blog (highest priority)
    t1t2_without_blog = [r for r in races_without_blog if r.get("tier") in (1, 2)]

    # Upcoming races (next 3 months) without blog
    upcoming_months = set()
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    current_month_idx = CURRENT_DATE.month - 1
    for i in range(3):
        idx = (current_month_idx + i) % 12
        upcoming_months.add(month_names[idx])
    upcoming_without_blog = [
        r for r in races_without_blog
        if r.get("month") in upcoming_months
    ]

    return {
        "races_without_blog": races_without_blog,
        "races_without_pk": races_without_pk,
        "t1t2_without_blog": t1t2_without_blog,
        "upcoming_without_blog": upcoming_without_blog,
        "total_blog_coverage": len(blog_slugs & race_slugs),
        "total_pk_coverage": len(pk_slugs & race_slugs),
    }


# ── SEO health check ────────────────────────────────────────────


def check_seo_health(sitemap_urls, races, output_pages):
    """Quick SEO health metrics."""
    issues = []

    # Sitemap vs actual pages
    total_expected = (
        len(races) +  # race profiles
        output_pages.get("vs_pages", 0) +
        output_pages.get("state_hubs", 0) +
        output_pages.get("series_hubs", 0) +
        output_pages.get("tier_hubs", 0) +
        output_pages.get("power_rankings", 0) +
        output_pages.get("calendar", 0) +
        7  # homepage, gravel-races, methodology, etc.
    )

    sitemap_count = len(sitemap_urls)
    if sitemap_count < total_expected * 0.9:
        issues.append(f"Sitemap has {sitemap_count} URLs but expected ~{total_expected}. "
                      f"May be missing new page types.")

    # Check for races not in sitemap
    sitemap_set = set(sitemap_urls)
    races_missing_from_sitemap = [
        r for r in races
        if f"{SITE_BASE_URL}/race/{r['slug']}/" not in sitemap_set
    ]
    if races_missing_from_sitemap:
        issues.append(f"{len(races_missing_from_sitemap)} races missing from sitemap")

    return {
        "sitemap_urls": sitemap_count,
        "expected_urls": total_expected,
        "issues": issues,
    }


# ── Substack RSS ─────────────────────────────────────────────────


def fetch_substack_rss():
    """Fetch latest posts from Substack RSS feed."""
    url = "https://gravelgodcycling.substack.com/feed"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GravelGod-Report/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
        root = ElementTree.fromstring(data)
        items = []
        for item in root.findall(".//item")[:10]:
            title = item.find("title")
            pub_date = item.find("pubDate")
            link = item.find("link")
            items.append({
                "title": title.text if title is not None else "",
                "date": pub_date.text if pub_date is not None else "",
                "link": link.text if link is not None else "",
            })
        return items
    except (urllib.error.URLError, ElementTree.ParseError, Exception) as e:
        return [{"error": str(e)}]


# ── GA4 Data API ─────────────────────────────────────────────────


def fetch_ga4_data():
    """Fetch GA4 metrics if credentials are configured.

    Requires:
      - GOOGLE_APPLICATION_CREDENTIALS env var pointing to service account JSON
      - GA4_PROPERTY_ID env var (e.g., "properties/123456789")
      - google-analytics-data pip package installed
    """
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    property_id = os.environ.get("GA4_PROPERTY_ID")

    if not creds_path or not property_id:
        return None  # Not configured

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest,
        )
    except ImportError:
        return {"error": "pip install google-analytics-data"}

    client = BetaAnalyticsDataClient()

    # Last 7 days vs previous 7 days
    today = CURRENT_DATE
    seven_ago = today - timedelta(days=7)
    fourteen_ago = today - timedelta(days=14)

    def run_report(start, end, dims, mets):
        request = RunReportRequest(
            property=property_id,
            date_ranges=[DateRange(start_date=start.isoformat(), end_date=end.isoformat())],
            dimensions=[Dimension(name=d) for d in dims],
            metrics=[Metric(name=m) for m in mets],
        )
        return client.run_report(request)

    results = {}

    # Overall traffic
    try:
        current = run_report(seven_ago, today, [], ["sessions", "totalUsers", "screenPageViews"])
        previous = run_report(fourteen_ago, seven_ago, [], ["sessions", "totalUsers", "screenPageViews"])

        if current.rows and previous.rows:
            c = current.rows[0]
            p = previous.rows[0]
            results["traffic"] = {
                "sessions_7d": int(c.metric_values[0].value),
                "sessions_prev_7d": int(p.metric_values[0].value),
                "users_7d": int(c.metric_values[1].value),
                "users_prev_7d": int(p.metric_values[1].value),
                "pageviews_7d": int(c.metric_values[2].value),
                "pageviews_prev_7d": int(p.metric_values[2].value),
            }
    except Exception as e:
        results["traffic_error"] = str(e)

    # Top pages
    try:
        top = run_report(seven_ago, today, ["pagePath"], ["screenPageViews"])
        top_pages = []
        for row in top.rows[:20]:
            top_pages.append({
                "path": row.dimension_values[0].value,
                "views": int(row.metric_values[0].value),
            })
        results["top_pages"] = top_pages
    except Exception as e:
        results["top_pages_error"] = str(e)

    # Traffic sources
    try:
        sources = run_report(seven_ago, today, ["sessionSource"], ["sessions"])
        source_list = []
        for row in sources.rows[:10]:
            source_list.append({
                "source": row.dimension_values[0].value,
                "sessions": int(row.metric_values[0].value),
            })
        results["sources"] = source_list
    except Exception as e:
        results["sources_error"] = str(e)

    # Events (lead captures)
    try:
        events = run_report(seven_ago, today, ["eventName"], ["eventCount"])
        event_list = []
        target_events = {"guide_unlock", "tp_form_submit", "pk_fueling_submit",
                         "tp_form_start", "tp_form_abandon"}
        for row in events.rows:
            name = row.dimension_values[0].value
            if name in target_events:
                event_list.append({
                    "event": name,
                    "count": int(row.metric_values[0].value),
                })
        results["conversion_events"] = event_list
    except Exception as e:
        results["events_error"] = str(e)

    return results


# ── Google Search Console ────────────────────────────────────────


def fetch_gsc_data():
    """Fetch Search Console metrics if credentials are configured.

    Requires:
      - GOOGLE_APPLICATION_CREDENTIALS env var
      - google-api-python-client pip package
    """
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        return {"error": "pip install google-api-python-client google-auth"}

    try:
        creds = service_account.Credentials.from_service_account_file(
            creds_path, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
        )
        service = build("searchconsole", "v1", credentials=creds)

        today = CURRENT_DATE
        seven_ago = today - timedelta(days=7)
        fourteen_ago = today - timedelta(days=14)

        results = {}

        # Overall search performance
        for label, start, end in [("current_7d", seven_ago, today),
                                   ("previous_7d", fourteen_ago, seven_ago)]:
            resp = service.searchanalytics().query(
                siteUrl=SITE_BASE_URL,
                body={
                    "startDate": start.isoformat(),
                    "endDate": end.isoformat(),
                    "dimensions": [],
                }
            ).execute()
            if resp.get("rows"):
                r = resp["rows"][0]
                results[label] = {
                    "clicks": r.get("clicks", 0),
                    "impressions": r.get("impressions", 0),
                    "ctr": r.get("ctr", 0),
                    "position": r.get("position", 0),
                }

        # Top queries
        resp = service.searchanalytics().query(
            siteUrl=SITE_BASE_URL,
            body={
                "startDate": seven_ago.isoformat(),
                "endDate": today.isoformat(),
                "dimensions": ["query"],
                "rowLimit": 20,
            }
        ).execute()
        results["top_queries"] = [
            {
                "query": r["keys"][0],
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr": round(r.get("ctr", 0) * 100, 1),
                "position": round(r.get("position", 0), 1),
            }
            for r in resp.get("rows", [])
        ]

        # Top pages by clicks
        resp = service.searchanalytics().query(
            siteUrl=SITE_BASE_URL,
            body={
                "startDate": seven_ago.isoformat(),
                "endDate": today.isoformat(),
                "dimensions": ["page"],
                "rowLimit": 20,
            }
        ).execute()
        results["top_pages"] = [
            {
                "page": r["keys"][0].replace(SITE_BASE_URL, ""),
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr": round(r.get("ctr", 0) * 100, 1),
                "position": round(r.get("position", 0), 1),
            }
            for r in resp.get("rows", [])
        ]

        return results
    except Exception as e:
        return {"error": str(e)}


# ── Upcoming race analysis ───────────────────────────────────────


def analyze_upcoming_races(races):
    """Find races in the next 3 months — content opportunities."""
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    current_idx = CURRENT_DATE.month - 1
    upcoming = {}
    for offset in range(3):
        month = month_names[(current_idx + offset) % 12]
        month_races = sorted(
            [r for r in races if r.get("month") == month],
            key=lambda x: -x.get("overall_score", 0),
        )
        upcoming[month] = month_races
    return upcoming


# ── Report builder ───────────────────────────────────────────────


def build_report(args) -> str:
    """Build the full markdown report."""
    lines = []
    lines.append(f"# Gravel God — Daily Marketing Report")
    lines.append(f"**Date:** {CURRENT_DATE.isoformat()}")
    lines.append("")

    # ── 1. Content inventory
    races = load_race_index()
    blogs = load_blog_index()
    sitemap_urls = load_sitemap()
    output_pages = count_output_pages()

    tier_counts = Counter(r.get("tier") for r in races)
    disc_counts = Counter(r.get("discipline", "gravel") for r in races)

    lines.append("## 1. Content Inventory")
    lines.append("")
    lines.append("| Page Type | Count |")
    lines.append("|-----------|-------|")
    lines.append(f"| Race profiles | {len(races)} |")
    lines.append(f"| Blog posts | {len(blogs)} |")
    lines.append(f"| VS comparison pages | {output_pages.get('vs_pages', 0)} |")
    lines.append(f"| State/region hubs | {output_pages.get('state_hubs', 0)} |")
    lines.append(f"| Series hubs | {output_pages.get('series_hubs', 0)} |")
    lines.append(f"| Tier hubs | {output_pages.get('tier_hubs', 0)} |")
    lines.append(f"| Calendar | {output_pages.get('calendar', 0)} |")
    lines.append(f"| Power rankings | {output_pages.get('power_rankings', 0)} |")
    lines.append(f"| **Sitemap URLs** | **{len(sitemap_urls)}** |")
    lines.append("")

    lines.append(f"**Tier breakdown:** T1={tier_counts.get(1,0)}, T2={tier_counts.get(2,0)}, "
                 f"T3={tier_counts.get(3,0)}, T4={tier_counts.get(4,0)}")
    lines.append(f"**Disciplines:** {', '.join(f'{d}={c}' for d, c in disc_counts.most_common())}")
    lines.append("")

    # ── 2. GA4 traffic (if configured)
    lines.append("## 2. Traffic & Analytics")
    lines.append("")
    ga4 = fetch_ga4_data()
    if ga4 is None:
        lines.append("**GA4 not configured.** Set `GOOGLE_APPLICATION_CREDENTIALS` and "
                      "`GA4_PROPERTY_ID` env vars to enable traffic reporting.")
        lines.append("")
        lines.append("Setup steps:")
        lines.append("1. Go to console.cloud.google.com")
        lines.append("2. Enable 'Google Analytics Data API'")
        lines.append("3. Create service account → download JSON key")
        lines.append("4. Grant Viewer role on GA4 property")
        lines.append("5. `export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`")
        lines.append("6. `export GA4_PROPERTY_ID=properties/YOUR_ID`")
        lines.append("7. `pip install google-analytics-data`")
    elif "error" in ga4:
        lines.append(f"**GA4 error:** {ga4['error']}")
    else:
        t = ga4.get("traffic", {})
        if t:
            s_cur = t.get("sessions_7d", 0)
            s_prev = t.get("sessions_prev_7d", 0)
            s_change = ((s_cur - s_prev) / max(s_prev, 1)) * 100

            u_cur = t.get("users_7d", 0)
            u_prev = t.get("users_prev_7d", 0)
            u_change = ((u_cur - u_prev) / max(u_prev, 1)) * 100

            pv_cur = t.get("pageviews_7d", 0)
            pv_prev = t.get("pageviews_prev_7d", 0)
            pv_change = ((pv_cur - pv_prev) / max(pv_prev, 1)) * 100

            arrow = lambda x: "+" if x >= 0 else ""

            lines.append("| Metric | Last 7 days | Previous 7 days | Change |")
            lines.append("|--------|-------------|-----------------|--------|")
            lines.append(f"| Sessions | {s_cur:,} | {s_prev:,} | {arrow(s_change)}{s_change:.1f}% |")
            lines.append(f"| Users | {u_cur:,} | {u_prev:,} | {arrow(u_change)}{u_change:.1f}% |")
            lines.append(f"| Pageviews | {pv_cur:,} | {pv_prev:,} | {arrow(pv_change)}{pv_change:.1f}% |")
            lines.append("")

            # Why this matters
            if s_change < -10:
                lines.append(f"**Action needed:** Sessions dropped {s_change:.0f}% week-over-week. "
                             f"Check if recent deploys broke any pages. Verify sitemap.xml "
                             f"is accessible and all 526 URLs resolve.")
            elif s_change > 20:
                lines.append(f"**Good news:** Sessions up {s_change:.0f}% week-over-week. "
                             f"Check top pages to see what's driving growth and double down.")

        # Top pages
        top_pages = ga4.get("top_pages", [])
        if top_pages:
            lines.append("")
            lines.append("### Top 10 Pages (Last 7 Days)")
            lines.append("| Page | Views |")
            lines.append("|------|-------|")
            for p in top_pages[:10]:
                lines.append(f"| {p['path']} | {p['views']:,} |")

        # Conversion events
        events = ga4.get("conversion_events", [])
        if events:
            lines.append("")
            lines.append("### Conversion Events (Last 7 Days)")
            lines.append("| Event | Count | Why It Matters |")
            lines.append("|-------|-------|----------------|")
            event_explanations = {
                "guide_unlock": "Newsletter subscribers via guide gate",
                "tp_form_submit": "Training plan requests ($$$)",
                "pk_fueling_submit": "Fueling calculator leads",
                "tp_form_start": "Started training plan form (top of funnel)",
                "tp_form_abandon": "Abandoned form (lost conversions)",
            }
            for e in events:
                why = event_explanations.get(e["event"], "")
                lines.append(f"| {e['event']} | {e['count']} | {why} |")

        # Traffic sources
        sources = ga4.get("sources", [])
        if sources:
            lines.append("")
            lines.append("### Traffic Sources")
            lines.append("| Source | Sessions |")
            lines.append("|--------|----------|")
            for s in sources[:10]:
                lines.append(f"| {s['source']} | {s['sessions']:,} |")
    lines.append("")

    # ── 3. Google Search Console
    lines.append("## 3. Search Performance")
    lines.append("")
    gsc = fetch_gsc_data()
    if gsc is None:
        lines.append("**Google Search Console not configured.** Set `GOOGLE_APPLICATION_CREDENTIALS` "
                      "env var and add service account email to GSC as a user.")
    elif "error" in gsc:
        lines.append(f"**GSC error:** {gsc['error']}")
    else:
        cur = gsc.get("current_7d", {})
        prev = gsc.get("previous_7d", {})
        if cur and prev:
            c_clicks = cur.get("clicks", 0)
            p_clicks = prev.get("clicks", 0)
            click_change = ((c_clicks - p_clicks) / max(p_clicks, 1)) * 100

            c_impr = cur.get("impressions", 0)
            p_impr = prev.get("impressions", 0)
            impr_change = ((c_impr - p_impr) / max(p_impr, 1)) * 100

            lines.append("| Metric | Last 7 days | Previous 7 days | Change |")
            lines.append("|--------|-------------|-----------------|--------|")
            lines.append(f"| Clicks | {c_clicks:,} | {p_clicks:,} | {click_change:+.1f}% |")
            lines.append(f"| Impressions | {c_impr:,} | {p_impr:,} | {impr_change:+.1f}% |")
            lines.append(f"| CTR | {cur.get('ctr',0)*100:.1f}% | {prev.get('ctr',0)*100:.1f}% | |")
            lines.append(f"| Avg Position | {cur.get('position',0):.1f} | {prev.get('position',0):.1f} | |")
            lines.append("")

            if impr_change > 20 and click_change < 5:
                lines.append("**Action:** Impressions growing but clicks flat — "
                             "titles/meta descriptions may need optimization for higher CTR.")

        queries = gsc.get("top_queries", [])
        if queries:
            lines.append("### Top Search Queries")
            lines.append("| Query | Clicks | Impressions | CTR | Position |")
            lines.append("|-------|--------|-------------|-----|----------|")
            for q in queries[:15]:
                lines.append(f"| {q['query']} | {q['clicks']} | {q['impressions']:,} "
                             f"| {q['ctr']}% | {q['position']} |")
            lines.append("")
            lines.append("**Why this matters:** These are the queries Google shows your site for. "
                         "Low-CTR high-impression queries = title tag optimization opportunities. "
                         "Queries with position 8-20 = pages close to page 1 that need a content boost.")

        pages = gsc.get("top_pages", [])
        if pages:
            lines.append("")
            lines.append("### Top Pages in Search")
            lines.append("| Page | Clicks | Impressions | CTR | Position |")
            lines.append("|------|--------|-------------|-----|----------|")
            for p in pages[:15]:
                lines.append(f"| {p['page']} | {p['clicks']} | {p['impressions']:,} "
                             f"| {p['ctr']}% | {p['position']} |")
    lines.append("")

    # ── 4. Content gaps
    lines.append("## 4. Content Gaps & Opportunities")
    lines.append("")
    gaps = analyze_content_gaps(races, blogs)

    lines.append(f"**Blog coverage:** {gaps['total_blog_coverage']}/{len(races)} races have blog posts "
                 f"({gaps['total_blog_coverage']/max(len(races),1)*100:.0f}%)")
    lines.append(f"**Prep kit coverage:** {gaps['total_pk_coverage']}/{len(races)} races have prep kits "
                 f"({gaps['total_pk_coverage']/max(len(races),1)*100:.0f}%)")
    lines.append("")

    if gaps["t1t2_without_blog"]:
        lines.append(f"### High-Priority: {len(gaps['t1t2_without_blog'])} T1/T2 Races Without Blog Posts")
        lines.append("These are your highest-value races with no blog content — easy SEO wins.")
        lines.append("")
        for r in sorted(gaps["t1t2_without_blog"], key=lambda x: -x.get("overall_score", 0))[:10]:
            lines.append(f"- **{r['name']}** (T{r['tier']}, score {r['overall_score']}) — "
                         f"{r.get('location','')} / {r.get('month','')}")
        lines.append("")

    if gaps["upcoming_without_blog"]:
        lines.append(f"### Timely: {len(gaps['upcoming_without_blog'])} Upcoming Races Without Blog Posts")
        lines.append("These races are in the next 3 months — blog posts NOW will capture "
                     "search traffic from riders researching them.")
        lines.append("")
        for r in sorted(gaps["upcoming_without_blog"], key=lambda x: -x.get("overall_score", 0))[:10]:
            lines.append(f"- **{r['name']}** ({r.get('month','')}, T{r['tier']}, "
                         f"score {r['overall_score']})")
        lines.append("")

    # ── 5. Upcoming race calendar
    lines.append("## 5. Upcoming Race Calendar")
    lines.append("")
    upcoming = analyze_upcoming_races(races)
    for month, month_races in upcoming.items():
        if month_races:
            t1_count = sum(1 for r in month_races if r["tier"] == 1)
            lines.append(f"### {month} ({len(month_races)} races, {t1_count} T1)")
            for r in month_races[:8]:
                lines.append(f"- {r['name']} — T{r['tier']} ({r['overall_score']}) "
                             f"— {r.get('location','')}")
            if len(month_races) > 8:
                lines.append(f"- ... and {len(month_races) - 8} more")
            lines.append("")

    # ── 6. Newsletter / Substack
    lines.append("## 6. Newsletter (Substack)")
    lines.append("")
    posts = fetch_substack_rss()
    if posts and "error" not in posts[0]:
        lines.append(f"Latest {min(len(posts), 5)} posts:")
        for p in posts[:5]:
            lines.append(f"- **{p['title']}** — {p['date'][:16]}")
        lines.append("")

        # Publishing cadence
        if len(posts) >= 2:
            try:
                dates = []
                for p in posts:
                    d = p.get("date", "")
                    if d:
                        # Parse RSS date format
                        for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"]:
                            try:
                                dates.append(datetime.strptime(d, fmt).date())
                                break
                            except ValueError:
                                continue
                if len(dates) >= 2:
                    gaps_days = [(dates[i] - dates[i+1]).days for i in range(len(dates)-1)]
                    avg_gap = sum(gaps_days) / len(gaps_days)
                    days_since_last = (CURRENT_DATE - dates[0]).days
                    lines.append(f"**Publishing cadence:** avg {avg_gap:.0f} days between posts")
                    lines.append(f"**Days since last post:** {days_since_last}")
                    if days_since_last > avg_gap * 1.5:
                        lines.append(f"**Action:** You're overdue for a newsletter post "
                                     f"(last one was {days_since_last} days ago, "
                                     f"your average is every {avg_gap:.0f} days).")
            except Exception:
                pass
    elif posts and "error" in posts[0]:
        lines.append(f"Could not fetch Substack RSS: {posts[0]['error']}")
    lines.append("")

    # ── 7. SEO health
    lines.append("## 7. SEO Health Check")
    lines.append("")
    seo = check_seo_health(sitemap_urls, races, output_pages)
    lines.append(f"**Sitemap:** {seo['sitemap_urls']} URLs (expected ~{seo['expected_urls']})")
    if seo["issues"]:
        for issue in seo["issues"]:
            lines.append(f"- {issue}")
    else:
        lines.append("- No issues found")
    lines.append("")

    # ── 8. Recommendations
    lines.append("## 8. Today's Recommendations")
    lines.append("")
    recs = []

    # Content recommendations
    if gaps["t1t2_without_blog"]:
        top = gaps["t1t2_without_blog"][0]
        recs.append(f"**Write a blog post for {top['name']}** (T{top['tier']}, score {top['overall_score']}). "
                     f"This is your highest-rated race without a blog post — easy SEO capture.")

    if gaps["upcoming_without_blog"]:
        top = gaps["upcoming_without_blog"][0]
        recs.append(f"**Publish a race preview for {top['name']}** (racing in {top.get('month','')}). "
                     f"Riders are searching for this NOW.")

    # Newsletter
    try:
        posts = fetch_substack_rss()
        if posts and "error" not in posts[0]:
            for fmt in ["%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"]:
                try:
                    last_date = datetime.strptime(posts[0]["date"], fmt).date()
                    if (CURRENT_DATE - last_date).days > 7:
                        recs.append(f"**Send a newsletter** — it's been "
                                    f"{(CURRENT_DATE - last_date).days} days since the last post.")
                    break
                except ValueError:
                    continue
    except Exception:
        pass

    if not recs:
        recs.append("No urgent action items today. Keep shipping.")

    for i, rec in enumerate(recs, 1):
        lines.append(f"{i}. {rec}")
    lines.append("")

    lines.append("---")
    lines.append(f"*Generated by `scripts/daily-marketing-report.py` on {CURRENT_DATE}*")
    lines.append(f"*Run daily: `python3 scripts/daily-marketing-report.py`*")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Daily marketing report for Gravel God")
    parser.add_argument("--output", "-o", help="Output path (default: stdout)")
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of markdown")
    args = parser.parse_args()

    report = build_report(args)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"Report written to {out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
