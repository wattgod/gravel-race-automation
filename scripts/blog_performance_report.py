#!/usr/bin/env python3
"""Per-post GA4 performance for Gravel God essays and blog posts.

Compares the 30 days before the 2026-10-09 editorial redesign with
2026-10-09 → yesterday. Every count is normalised per day because the
after-window is short; ratios (engagement rate, average engagement time,
deep-read rate) are reported as-is.

Content covered:
  essays   /articles/<slug>/      (wordpress/articles/)
  posts    /<slug>/               (wordpress/post_sources/*.json)
  blog     /blog/<slug>/          (previews, recaps, roundups — every
                                   /blog/* path GA4 returns, plus the
                                   slugs in web/blog-index.json)

Read-only: uses the analytics.readonly scope and the same service-account
auth as scripts/ga4_conversion_audit.py. Runs in GitHub Actions
(.github/workflows/blog-performance-report.yml); credentials never live in
the repo.

Usage:
    python scripts/blog_performance_report.py --mock --output-dir /tmp/bp
    python scripts/blog_performance_report.py --property 123 \
        --credentials ga4.json --output-dir data/blog-performance
"""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POST_SOURCES = PROJECT_ROOT / "wordpress" / "post_sources"
ARTICLES_DIR = PROJECT_ROOT / "wordpress" / "articles"
BLOG_INDEX = PROJECT_ROOT / "web" / "blog-index.json"

REDESIGN_DATE = date(2026, 10, 9)
BEFORE_DAYS = 30

ARTICLE_EVENTS = ("article_scroll_depth", "article_deep_read",
                  "article_cta_click", "cta_click")
# cta_click on content pages is the canonical plan-intent click
# (wordpress/blog_tracking.py: cta_name = data-cta or "plan_intent").
PLAN_CTA_NAMES = frozenset({
    "custom_plan", "season_plan", "plan_intent", "approved_custom_plan",
    "tpp_hero_build", "tpp_preview_build", "tpp_footer_build", "hero_build",
    "pricing_build", "sticky_mobile", "build_plan", "personalized_plan"})
COACHING_CTA_NAMES = frozenset({"coaching"})

PAGE_METRICS = ("screenPageViews", "activeUsers",
                "userEngagementDuration", "engagementRate")
TITLE_SUFFIX_RE = re.compile(r"\s*[|—–-]\s*Gravel God\s*$")


def _load_audit_module():
    """Reuse auth + runReport plumbing from ga4_conversion_audit.py."""
    path = Path(__file__).resolve().parent / "ga4_conversion_audit.py"
    spec = importlib.util.spec_from_file_location("ga4_conversion_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_audit = _load_audit_module()
Ga4Error = _audit.Ga4AuditError
normalize_property = _audit.normalize_property


# ── Content inventory ─────────────────────────────────────────────────────

def _clean_title(value: str) -> str:
    return TITLE_SUFFIX_RE.sub("", html.unescape(str(value or "")).strip())


def _slug_title(slug: str) -> str:
    return slug.replace("-", " ").strip().capitalize()


def classify_blog_slug(slug: str) -> str:
    """Same slug rules as scripts/generate_blog_index.py (no HTML here)."""
    if slug.startswith("roundup-"):
        return "roundup"
    if slug.endswith("-recap"):
        return "recap"
    return "preview"


def load_inventory(post_sources: Path = POST_SOURCES,
                   articles_dir: Path = ARTICLES_DIR,
                   blog_index: Path = BLOG_INDEX) -> dict[str, dict]:
    """Known content URLs → {title, type}. Essays and posts always appear in
    the report (zero rows included); blog pages appear if known or if GA4
    returns them."""
    pages: dict[str, dict] = {}
    if articles_dir.exists():
        for index in sorted(articles_dir.glob("*/index.html")):
            slug = index.parent.name
            match = re.search(r"<title>(.*?)</title>",
                              index.read_text(errors="replace"), re.DOTALL)
            pages[f"/articles/{slug}/"] = {
                "title": _clean_title(match.group(1)) if match else _slug_title(slug),
                "type": "essay"}
    if post_sources.exists():
        for source in sorted(post_sources.glob("*.json")):
            try:
                data = json.loads(source.read_text())
            except ValueError:
                continue
            slug = str(data.get("slug") or source.stem)
            live = data.get("live") or {}
            title = live.get("headline") or live.get("title") or _slug_title(slug)
            pages[f"/{slug}/"] = {"title": _clean_title(title), "type": "post"}
    if blog_index.exists():
        try:
            entries = json.loads(blog_index.read_text())
        except ValueError:
            entries = []
        for entry in entries if isinstance(entries, list) else []:
            url = str(entry.get("url") or "")
            if not url.startswith("/blog/"):
                continue  # /articles/ entries come from the HTML titles above
            slug = url.strip("/").split("/")[-1]
            pages[url] = {"title": _clean_title(entry.get("title") or slug),
                          "type": classify_blog_slug(slug)}
    return pages


def normalize_path(path: str) -> str:
    path = str(path or "").split("?")[0].split("#")[0].strip() or "/"
    if not path.startswith("/"):
        path = "/" + path
    if not path.endswith("/"):
        path += "/"
    return re.sub(r"/{2,}", "/", path)


def is_blog_content(path: str) -> bool:
    """A /blog/<slug>/ page (not the /blog/ index itself)."""
    return bool(re.fullmatch(r"/blog/[^/]+/", path))


# ── Windows ───────────────────────────────────────────────────────────────

def build_windows(end: date) -> dict[str, dict]:
    if end < REDESIGN_DATE:
        raise Ga4Error(
            f"after-window is empty: end date {end} is before {REDESIGN_DATE}")
    before_start = REDESIGN_DATE - timedelta(days=BEFORE_DAYS)
    before_end = REDESIGN_DATE - timedelta(days=1)
    return {
        "before": {"start": before_start.isoformat(), "end": before_end.isoformat(),
                   "days": BEFORE_DAYS},
        "after": {"start": REDESIGN_DATE.isoformat(), "end": end.isoformat(),
                  "days": (end - REDESIGN_DATE).days + 1},
    }


# ── GA4 queries (REST runReport) ─────────────────────────────────────────

def _page_filter(post_paths: list[str]) -> dict:
    exprs = [
        {"filter": {"fieldName": "pagePath", "stringFilter": {
            "matchType": "BEGINS_WITH", "value": prefix}}}
        for prefix in ("/blog/", "/articles/")
    ]
    # pagePath may arrive with or without the trailing slash.
    variants = sorted({v for p in post_paths for v in (p, p.rstrip("/"))})
    if variants:
        exprs.append({"filter": {"fieldName": "pagePath",
                                 "inListFilter": {"values": variants}}})
    return {"orGroup": {"expressions": exprs}}


def _and(*exprs: dict) -> dict:
    return {"andGroup": {"expressions": list(exprs)}}


def report_requests(window: dict, post_paths: list[str]) -> dict[str, dict]:
    date_ranges = [{"startDate": window["start"], "endDate": window["end"]}]
    pages = _page_filter(post_paths)
    return {
        "pages": {
            "dateRanges": date_ranges,
            "dimensions": [{"name": "pagePath"}],
            "metrics": [{"name": m} for m in PAGE_METRICS],
            "dimensionFilter": pages,
            "limit": "10000",
        },
        "events": {
            "dateRanges": date_ranges,
            "dimensions": [{"name": "pagePath"}, {"name": "eventName"}],
            "metrics": [{"name": "eventCount"}],
            "dimensionFilter": _and(pages, {"filter": {
                "fieldName": "eventName",
                "inListFilter": {"values": list(ARTICLE_EVENTS)}}}),
            "limit": "10000",
        },
        "cta": {
            "dateRanges": date_ranges,
            "dimensions": [{"name": "pagePath"},
                           {"name": "customEvent:cta_name"}],
            "metrics": [{"name": "eventCount"}],
            "dimensionFilter": _and(pages, {"filter": {
                "fieldName": "eventName",
                "stringFilter": {"matchType": "EXACT", "value": "cta_click"}}}),
            "limit": "10000",
        },
    }


def _rows(report: dict) -> list[tuple[list[str], dict[str, float]]]:
    metric_names = [m.get("name", "") for m in report.get("metricHeaders") or []]
    out = []
    for row in report.get("rows") or []:
        dims = [str(d.get("value") or "") for d in row.get("dimensionValues") or []]
        values = {}
        for name, mv in zip(metric_names, row.get("metricValues") or []):
            try:
                values[name] = float(mv.get("value") or 0)
            except (TypeError, ValueError):
                values[name] = 0.0
        out.append((dims, values))
    return out


def _empty_raw() -> dict:
    return {"views": 0.0, "active_users": 0.0, "engagement_seconds": 0.0,
            "engaged_weight": 0.0, "events": {e: 0.0 for e in ARTICLE_EVENTS},
            "plan_clicks": 0.0, "coaching_clicks": 0.0}


def parse_window_reports(reports: dict[str, dict | None]) -> dict[str, dict]:
    """Raw GA4 report bodies → path → summed raw counts.

    Rows whose paths differ only by a trailing slash are merged.
    engagementRate is per-session, so it is recombined weighted by views."""
    raw: dict[str, dict] = {}
    for dims, vals in _rows(reports.get("pages") or {}):
        r = raw.setdefault(normalize_path(dims[0]), _empty_raw())
        views = vals.get("screenPageViews", 0.0)
        r["views"] += views
        r["active_users"] += vals.get("activeUsers", 0.0)
        r["engagement_seconds"] += vals.get("userEngagementDuration", 0.0)
        r["engaged_weight"] += vals.get("engagementRate", 0.0) * views
    for dims, vals in _rows(reports.get("events") or {}):
        if len(dims) < 2 or dims[1] not in ARTICLE_EVENTS:
            continue
        r = raw.setdefault(normalize_path(dims[0]), _empty_raw())
        r["events"][dims[1]] += vals.get("eventCount", 0.0)
    cta = reports.get("cta")
    for dims, vals in _rows(cta or {}):
        if len(dims) < 2:
            continue
        name = dims[1].strip().lower()
        r = raw.setdefault(normalize_path(dims[0]), _empty_raw())
        if name in PLAN_CTA_NAMES:
            r["plan_clicks"] += vals.get("eventCount", 0.0)
        elif name in COACHING_CTA_NAMES:
            r["coaching_clicks"] += vals.get("eventCount", 0.0)
    if cta is None:
        for r in raw.values():
            r["plan_clicks"] = r["coaching_clicks"] = None
    return raw


def fetch_window(session: Any, property_name: str, window: dict,
                 post_paths: list[str]) -> tuple[dict, list[str]]:
    """Run the three reports for one window. The cta_name breakdown is
    optional: if the custom dimension is unavailable the report still ships
    with plan/coaching clicks marked unavailable."""
    warnings: list[str] = []
    reports: dict[str, dict | None] = {}
    for name, body in report_requests(window, post_paths).items():
        try:
            reports[name] = _audit._run_report(
                session, property_name, body, f"{name} report")
        except Ga4Error as exc:
            if name != "cta":
                raise
            reports[name] = None
            warnings.append(f"plan/coaching click breakdown unavailable: {exc}")
    return reports, warnings


# ── Mock data ─────────────────────────────────────────────────────────────

def _mock_report(dim_names: list[str], metric_names: list[str],
                 rows: list[tuple[list[str], list[float]]]) -> dict:
    return {
        "dimensionHeaders": [{"name": d} for d in dim_names],
        "metricHeaders": [{"name": m} for m in metric_names],
        "rows": [{"dimensionValues": [{"value": d} for d in dims],
                  "metricValues": [{"value": str(v)} for v in vals]}
                 for dims, vals in rows],
    }


def mock_reports(window_name: str, paths: list[str]) -> dict[str, dict]:
    """Deterministic GA4-shaped responses for --mock and tests."""
    after = window_name == "after"
    page_rows, event_rows, cta_rows = [], [], []
    for i, path in enumerate(sorted(paths)):
        seed = (sum(map(ord, path)) % 97) + 3
        days = 2 if after else BEFORE_DAYS
        lift = 1.0 + ((seed % 7) - 3) / 10 if after else 1.0
        views = round(seed * days / 10 * lift)
        if views == 0:
            continue
        # Exercise trailing-slash merging on one row.
        out_path = path.rstrip("/") if i == 0 else path
        page_rows.append(([out_path], [views, max(1, views * 0.7),
                                       views * (40 + seed % 60),
                                       0.4 + (seed % 5) / 10]))
        event_rows.append(([path, "article_scroll_depth"], [views * 2]))
        event_rows.append(([path, "article_deep_read"],
                           [round(views * (0.1 + (seed % 4) / 20) * lift)]))
        event_rows.append(([path, "article_cta_click"], [seed % 5]))
        event_rows.append(([path, "cta_click"], [seed % 4]))
        cta_rows.append(([path, "custom_plan"], [seed % 3]))
        cta_rows.append(([path, "coaching"], [seed % 2]))
    return {
        "pages": _mock_report(["pagePath"], list(PAGE_METRICS), page_rows),
        "events": _mock_report(["pagePath", "eventName"], ["eventCount"], event_rows),
        "cta": _mock_report(["pagePath", "customEvent:cta_name"], ["eventCount"],
                            cta_rows),
    }


# ── Assembly ──────────────────────────────────────────────────────────────

def _r(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def window_metrics(raw: dict | None, days: int) -> dict:
    raw = raw or _empty_raw()
    views = raw["views"]
    users = raw["active_users"]
    events = raw["events"]
    deep = events["article_deep_read"]
    per_day = lambda v: None if v is None else _r(v / days, 2)  # noqa: E731
    return {
        "views": int(views),
        "views_per_day": per_day(views),
        "active_users": int(users),
        "active_users_per_day": per_day(users),
        "avg_engagement_seconds": _r(raw["engagement_seconds"] / users, 1) if users else None,
        "engagement_rate": _r(raw["engaged_weight"] / views) if views else None,
        "events": {name: int(count) for name, count in events.items()},
        "events_per_day": {name: per_day(count) for name, count in events.items()},
        "deep_read_rate": _r(deep / views) if views else None,
        "plan_clicks": None if raw["plan_clicks"] is None else int(raw["plan_clicks"]),
        "coaching_clicks": (None if raw["coaching_clicks"] is None
                            else int(raw["coaching_clicks"])),
    }


def _delta(after: float | None, before: float | None, digits: int = 3):
    if after is None or before is None:
        return None
    return round(after - before, digits)


def _pct(after: float | None, before: float | None):
    if after is None or not before:
        return None
    return round((after - before) / before * 100, 1)


def deltas(before: dict, after: dict) -> dict:
    return {
        "views_per_day": _delta(after["views_per_day"], before["views_per_day"], 2),
        "views_per_day_pct": _pct(after["views_per_day"], before["views_per_day"]),
        "active_users_per_day": _delta(after["active_users_per_day"],
                                       before["active_users_per_day"], 2),
        "avg_engagement_seconds": _delta(after["avg_engagement_seconds"],
                                         before["avg_engagement_seconds"], 1),
        "engagement_rate_pts": _delta(after["engagement_rate"], before["engagement_rate"]),
        "deep_read_rate_pts": _delta(after["deep_read_rate"], before["deep_read_rate"]),
        "events_per_day": {
            name: _delta(after["events_per_day"][name],
                         before["events_per_day"][name], 2)
            for name in ARTICLE_EVENTS},
    }


def build_rows(inventory: dict[str, dict], raw_before: dict, raw_after: dict,
               windows: dict) -> list[dict]:
    paths = set(inventory)
    paths |= {p for p in set(raw_before) | set(raw_after) if is_blog_content(p)}
    paths |= {p for p in set(raw_before) | set(raw_after)
              if p.startswith("/articles/") and p != "/articles/"}
    rows = []
    for path in sorted(paths):
        meta = inventory.get(path)
        if meta is None:
            slug = path.strip("/").split("/")[-1]
            meta = {"title": _slug_title(slug),
                    "type": "essay" if path.startswith("/articles/")
                    else classify_blog_slug(slug)}
        before = window_metrics(raw_before.get(path), windows["before"]["days"])
        after = window_metrics(raw_after.get(path), windows["after"]["days"])
        rows.append({"path": path, "title": meta["title"], "type": meta["type"],
                     "before": before, "after": after,
                     "deltas": deltas(before, after)})
    rows.sort(key=lambda r: (-r["after"]["views"], -r["before"]["views"], r["path"]))
    return rows


def _sum_clicks(rows: list[dict], window: str, key: str) -> int | None:
    values = [r[window][key] for r in rows]
    if any(v is None for v in values):
        return None
    return sum(values)


def build_totals(rows: list[dict], windows: dict) -> dict:
    totals = {}
    for window in ("before", "after"):
        days = windows[window]["days"]
        views = sum(r[window]["views"] for r in rows)
        deep = sum(r[window]["events"]["article_deep_read"] for r in rows)
        plan = _sum_clicks(rows, window, "plan_clicks")
        coaching = _sum_clicks(rows, window, "coaching_clicks")
        totals[window] = {
            "views": views,
            "views_per_day": round(views / days, 2),
            "article_deep_read": deep,
            "article_cta_click": sum(r[window]["events"]["article_cta_click"] for r in rows),
            "cta_click": sum(r[window]["events"]["cta_click"] for r in rows),
            "plan_clicks": plan,
            "coaching_clicks": coaching,
            "plan_clicks_per_day": None if plan is None else round(plan / days, 2),
            "coaching_clicks_per_day": (None if coaching is None
                                        else round(coaching / days, 2)),
        }
    return totals


def build_report(inventory: dict[str, dict], reports_before: dict,
                 reports_after: dict, windows: dict, *, property_name: str,
                 mock: bool, warnings: list[str] | None = None) -> dict:
    raw_before = parse_window_reports(reports_before)
    raw_after = parse_window_reports(reports_after)
    rows = build_rows(inventory, raw_before, raw_after, windows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "property": property_name,
        "mock": mock,
        "redesign_date": REDESIGN_DATE.isoformat(),
        "windows": windows,
        "notes": [
            "Counts are also given per day (count / window days) because the "
            "after-window is short.",
            "active_users_per_day = window active users / days (users are not "
            "additive across days; read it as a rate, not daily actives).",
            "deep_read_rate = article_deep_read events / views; "
            "engagement_rate is view-weighted when trailing-slash variants merge.",
            "plan/coaching clicks = cta_click events by cta_name "
            "(custom_plan/season_plan/plan_intent… vs coaching).",
        ],
        "warnings": list(warnings or []),
        "totals": build_totals(rows, windows),
        "pages": rows,
    }


# ── Markdown summary ──────────────────────────────────────────────────────

def _fmt(value, suffix: str = "") -> str:
    if value is None:
        return "–"
    if isinstance(value, float):
        return f"{value:,.2f}{suffix}" if abs(value) < 100 else f"{value:,.0f}{suffix}"
    return f"{value:,}{suffix}"


def _rate(value) -> str:
    return "–" if value is None else f"{value * 100:.1f}%"


def _signed(value, suffix: str = "") -> str:
    if value is None:
        return "–"
    return f"{value:+,.1f}{suffix}"


def _md_title(row: dict) -> str:
    title = row["title"].replace("|", "/")
    return f"[{title}](https://gravelgodcycling.com{row['path']}) ({row['type']})"


def render_markdown(report: dict, top_n: int = 10, min_views: int = 20) -> str:
    w = report["windows"]
    rows = report["pages"]
    t = report["totals"]
    lines = [
        "# Gravel God blog performance",
        "",
        f"Redesign {report['redesign_date']}. Before: {w['before']['start']} → "
        f"{w['before']['end']} ({w['before']['days']} d). After: {w['after']['start']} → "
        f"{w['after']['end']} ({w['after']['days']} d). Per-day figures normalise the "
        "short after-window." + (" **MOCK DATA.**" if report["mock"] else ""),
        "",
    ]
    for warning in report["warnings"]:
        lines += [f"> Warning: {warning}", ""]
    lines += [
        "## Totals",
        "",
        "| | Before | After |",
        "|---|---:|---:|",
        f"| Pages tracked | {len(rows)} | {len(rows)} |",
        f"| Views / day | {_fmt(t['before']['views_per_day'])} | {_fmt(t['after']['views_per_day'])} |",
        f"| Deep reads | {_fmt(t['before']['article_deep_read'])} | {_fmt(t['after']['article_deep_read'])} |",
        f"| Plan clicks (cta_click) | {_fmt(t['before']['plan_clicks'])} | {_fmt(t['after']['plan_clicks'])} |",
        f"| Coaching clicks (cta_click) | {_fmt(t['before']['coaching_clicks'])} | {_fmt(t['after']['coaching_clicks'])} |",
        f"| Plan clicks / day | {_fmt(t['before']['plan_clicks_per_day'])} | {_fmt(t['after']['plan_clicks_per_day'])} |",
        f"| Coaching clicks / day | {_fmt(t['before']['coaching_clicks_per_day'])} | {_fmt(t['after']['coaching_clicks_per_day'])} |",
        f"| article_cta_click | {_fmt(t['before']['article_cta_click'])} | {_fmt(t['after']['article_cta_click'])} |",
        "",
        f"## Top {top_n} by views (after window)",
        "",
        "| Page | Views/day after | Views/day before | Δ % | Avg engagement (s) | Engagement rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in [r for r in rows if r["after"]["views"]][:top_n]:
        a, b, d = row["after"], row["before"], row["deltas"]
        lines.append(
            f"| {_md_title(row)} | {_fmt(a['views_per_day'])} | {_fmt(b['views_per_day'])} | "
            f"{_signed(d['views_per_day_pct'], '%')} | {_fmt(a['avg_engagement_seconds'])} | "
            f"{_rate(a['engagement_rate'])} |")
    deep = sorted((r for r in rows if r["after"]["views"] >= min_views
                   and r["after"]["deep_read_rate"] is not None),
                  key=lambda r: (-r["after"]["deep_read_rate"], r["path"]))[:top_n]
    lines += [
        "",
        f"## Top {top_n} by deep-read rate (after window, ≥{min_views} views)",
        "",
        "| Page | Deep-read rate | Before | Views |",
        "|---|---:|---:|---:|",
    ]
    if not deep:
        lines.append(f"| No page has ≥{min_views} views in the after window yet | | | |")
    for row in deep:
        lines.append(
            f"| {_md_title(row)} | {_rate(row['after']['deep_read_rate'])} | "
            f"{_rate(row['before']['deep_read_rate'])} | {row['after']['views']} |")
    movers = [r for r in rows if r["before"]["views"] + r["after"]["views"] >= min_views]
    movers.sort(key=lambda r: (-abs(r["deltas"]["views_per_day"] or 0), r["path"]))
    lines += [
        "",
        "## Biggest movers (views/day, either direction)",
        "",
        "| Page | Before/day | After/day | Δ/day | Δ % |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in movers[:top_n]:
        d = row["deltas"]
        lines.append(
            f"| {_md_title(row)} | {_fmt(row['before']['views_per_day'])} | "
            f"{_fmt(row['after']['views_per_day'])} | {_signed(d['views_per_day'])} | "
            f"{_signed(d['views_per_day_pct'], '%')} |")
    lines += ["", "Full per-page data (both windows, deltas) is in the JSON beside this file.", ""]
    return "\n".join(lines)


# ── CLI ───────────────────────────────────────────────────────────────────

def run(*, end: date, mock: bool, property_value: str | None,
        credentials: Path | None,
        session_factory: Callable[[Path], Any] | None = None) -> dict:
    windows = build_windows(end)
    inventory = load_inventory()
    post_paths = sorted(p for p, m in inventory.items() if m["type"] == "post")
    warnings: list[str] = []
    if mock:
        property_name = "properties/0"
        reports = {name: mock_reports(name, list(inventory)) for name in windows}
    else:
        if not property_value or not credentials:
            raise Ga4Error("--property and --credentials are required unless --mock")
        property_name = normalize_property(property_value)
        if not credentials.exists():
            raise Ga4Error("credentials file not found")
        factory = session_factory or (lambda p: _audit.authorized_session(p))
        session = factory(credentials)
        reports = {}
        for name, window in windows.items():
            reports[name], window_warnings = fetch_window(
                session, property_name, window, post_paths)
            warnings += [f"{name}: {w}" for w in window_warnings]
    return build_report(inventory, reports["before"], reports["after"], windows,
                        property_name=property_name, mock=mock, warnings=warnings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--mock", action="store_true",
                        help="Use deterministic sample data; no GA4 call")
    parser.add_argument("--property", help="GA4 property ID or properties/ID")
    parser.add_argument("--credentials", type=Path,
                        help="Service-account JSON path")
    parser.add_argument("--end-date", default=None,
                        help="Last day of the after-window (default: yesterday UTC)")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--stem", default=None,
                        help="Output file stem (default: run date, YYYY-MM-DD)")
    args = parser.parse_args(argv)

    today = datetime.now(timezone.utc).date()
    try:
        end = (date.fromisoformat(args.end_date) if args.end_date
               else today - timedelta(days=1))
    except ValueError:
        print("ERROR: --end-date must use YYYY-MM-DD", file=sys.stderr)
        return 2
    try:
        report = run(end=end, mock=args.mock, property_value=args.property,
                     credentials=args.credentials)
    except Ga4Error as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    stem = args.stem or today.isoformat()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{stem}.json"
    md_path = args.output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n")
    md_path.write_text(render_markdown(report))
    print(f"Wrote {json_path} and {md_path} ({len(report['pages'])} pages)")
    for warning in report["warnings"]:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
