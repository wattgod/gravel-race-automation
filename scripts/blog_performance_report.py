#!/usr/bin/env python3
"""Per-post GA4 performance for Gravel God essays and blog posts.

Default comparison: the last 7 complete days vs the 7 days before them
(week over week). Every count is also given per usable day, where a usable
day is on or after the page type's tracking start and not an excluded date.

Tracking start matters: the 77 WordPress posts had no GA4 tag until
2026-10-09, so nothing before that date is a baseline for them. Essays
(/articles/) and /blog/ pages carried GA4 before the redesign and are
treated as tracked throughout. The optional --compare-redesign section
(30 days before 2026-10-09 vs after) therefore only covers those types.

QA noise: scripted headless-browser checks loaded many pages on
2026-10-09/10. Those dates are excluded by default (--exclude-dates), and
every GA4 query drops rows whose browser begins with "Headless".

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
    python scripts/blog_performance_report.py --property 123 \\
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
from typing import Any, Callable, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POST_SOURCES = PROJECT_ROOT / "wordpress" / "post_sources"
ARTICLES_DIR = PROJECT_ROOT / "wordpress" / "articles"
BLOG_INDEX = PROJECT_ROOT / "web" / "blog-index.json"

REDESIGN_DATE = date(2026, 10, 9)
BEFORE_DAYS = 30
WEEK_DAYS = 7

PAGE_TYPES = ("essay", "post", "preview", "recap", "roundup")
# First day GA4 data exists for a page type. Types not listed carried GA4
# before the redesign and are treated as tracked for the whole report span.
# The WordPress posts' live heads had no GA4/gtag/GTM before 2026-10-09
# (tests/fixtures/wp_posts/*.live-head.html).
TRACKING_START: dict[str, date] = {"post": REDESIGN_DATE}

# 2026-10-09/10: scripted headless QA loaded many pages at 390 and 1440 px
# (~2 views each, 0 s engagement). Not real readers.
DEFAULT_EXCLUDE_DATES = (date(2026, 10, 9), date(2026, 10, 10))

# GA4's `browser` dimension. If GA4 reports automation as its own browser
# (e.g. "HeadlessChrome"), every query drops it; the browsers report says
# how many views that removed.
HEADLESS_PREFIX = "Headless"

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
PAGE_LIMIT = 10000


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


# ── Windows, tracking start, usable days ──────────────────────────────────

def date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _window(start: date, end: date) -> dict:
    return {"start": start.isoformat(), "end": end.isoformat(),
            "days": (end - start).days + 1}


def build_windows(end: date, compare_redesign: bool = False) -> dict[str, dict]:
    """current = the 7 days ending on `end`; previous = the 7 days before.
    With compare_redesign, also the 30 days before REDESIGN_DATE and
    REDESIGN_DATE → end."""
    current_start = end - timedelta(days=WEEK_DAYS - 1)
    previous_end = current_start - timedelta(days=1)
    windows = {
        "current": _window(current_start, end),
        "previous": _window(previous_end - timedelta(days=WEEK_DAYS - 1),
                            previous_end),
    }
    if compare_redesign:
        if end < REDESIGN_DATE:
            raise Ga4Error(f"redesign comparison needs an end date on or after "
                           f"{REDESIGN_DATE}, got {end}")
        windows["redesign_before"] = _window(
            REDESIGN_DATE - timedelta(days=BEFORE_DAYS),
            REDESIGN_DATE - timedelta(days=1))
        windows["redesign_after"] = _window(REDESIGN_DATE, end)
    return windows


def query_span(windows: dict) -> dict:
    return {"start": min(w["start"] for w in windows.values()),
            "end": max(w["end"] for w in windows.values())}


def tracking_start(page_type: str) -> date | None:
    """None = tracked before anything this report looks at."""
    return TRACKING_START.get(page_type)


def tracked_before_redesign(page_type: str) -> bool:
    start = tracking_start(page_type)
    return start is None or start < REDESIGN_DATE


def usable_dates(window: dict, page_type: str,
                 exclude: Iterable[date] = ()) -> list[str]:
    """Days in `window` on/after the type's tracking start, minus excluded
    dates. Data before tracking start is never counted."""
    start = tracking_start(page_type)
    skip = set(exclude)
    return [d.isoformat() for d in date_range(date.fromisoformat(window["start"]),
                                              date.fromisoformat(window["end"]))
            if (start is None or d >= start) and d not in skip]


def week_status(page_type: str, windows: dict, exclude: Iterable[date]) -> str:
    exclude = tuple(exclude)
    days = {name: len(usable_dates(windows[name], page_type, exclude))
            for name in ("current", "previous")}
    if all(days.values()):
        return "compared"
    start = tracking_start(page_type)
    if start and start > date.fromisoformat(windows["previous"]["start"]):
        return f"tracking began {start.isoformat()}"
    missing = [label for name, label in (("current", "this week"),
                                         ("previous", "last week"))
               if not days[name]]
    return f"no usable days {' or '.join(missing)} (excluded dates)"


def first_week_over_week_end(page_type: str, end: date,
                             exclude: Iterable[date], horizon: int = 90) -> date | None:
    """First end date ≥ `end` whose two weeks both have usable days."""
    exclude = tuple(exclude)
    for offset in range(horizon):
        candidate = end + timedelta(days=offset)
        windows = build_windows(candidate)
        if all(usable_dates(windows[n], page_type, exclude)
               for n in ("current", "previous")):
            return candidate
    return None


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


HEADLESS_EXCLUSION = {"notExpression": {"filter": {
    "fieldName": "browser", "stringFilter": {
        "matchType": "BEGINS_WITH", "value": HEADLESS_PREFIX,
        "caseSensitive": False}}}}


def report_requests(span: dict, post_paths: list[str]) -> dict[str, dict]:
    """Daily (date-dimensioned) reports over the whole span, so tracking
    start and excluded dates can be applied per day in Python."""
    date_ranges = [{"startDate": span["start"], "endDate": span["end"]}]
    pages = _page_filter(post_paths)
    return {
        "pages": {
            "dateRanges": date_ranges,
            "dimensions": [{"name": "date"}, {"name": "pagePath"}],
            "metrics": [{"name": m} for m in PAGE_METRICS],
            "dimensionFilter": _and(pages, HEADLESS_EXCLUSION),
            "limit": str(PAGE_LIMIT),
        },
        "events": {
            "dateRanges": date_ranges,
            "dimensions": [{"name": "date"}, {"name": "pagePath"},
                           {"name": "eventName"}],
            "metrics": [{"name": "eventCount"}],
            "dimensionFilter": _and(pages, HEADLESS_EXCLUSION, {"filter": {
                "fieldName": "eventName",
                "inListFilter": {"values": list(ARTICLE_EVENTS)}}}),
            "limit": str(PAGE_LIMIT),
        },
        "cta": {
            "dateRanges": date_ranges,
            "dimensions": [{"name": "date"}, {"name": "pagePath"},
                           {"name": "customEvent:cta_name"}],
            "metrics": [{"name": "eventCount"}],
            "dimensionFilter": _and(pages, HEADLESS_EXCLUSION, {"filter": {
                "fieldName": "eventName",
                "stringFilter": {"matchType": "EXACT", "value": "cta_click"}}}),
            "limit": str(PAGE_LIMIT),
        },
        # Diagnostic, unfiltered by browser: how many views the headless
        # exclusion removes.
        "browsers": {
            "dateRanges": date_ranges,
            "dimensions": [{"name": "browser"}],
            "metrics": [{"name": "screenPageViews"}],
            "dimensionFilter": pages,
            "limit": "1000",
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


def ga4_date(value: str) -> str:
    """GA4 `date` is YYYYMMDD; return ISO YYYY-MM-DD."""
    value = str(value or "").strip()
    if re.fullmatch(r"\d{8}", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return value


def parse_daily_reports(reports: dict[str, dict | None]) -> dict[str, dict[str, dict]]:
    """Raw GA4 report bodies → ISO date → path → summed raw counts.

    Rows whose paths differ only by a trailing slash are merged.
    engagementRate is per-session, so it is recombined weighted by views."""
    daily: dict[str, dict[str, dict]] = {}

    def bucket(day: str, path: str) -> dict:
        return daily.setdefault(ga4_date(day), {}).setdefault(
            normalize_path(path), _empty_raw())

    for dims, vals in _rows(reports.get("pages") or {}):
        if len(dims) < 2:
            continue
        r = bucket(dims[0], dims[1])
        views = vals.get("screenPageViews", 0.0)
        r["views"] += views
        r["active_users"] += vals.get("activeUsers", 0.0)
        r["engagement_seconds"] += vals.get("userEngagementDuration", 0.0)
        r["engaged_weight"] += vals.get("engagementRate", 0.0) * views
    for dims, vals in _rows(reports.get("events") or {}):
        if len(dims) < 3 or dims[2] not in ARTICLE_EVENTS:
            continue
        bucket(dims[0], dims[1])["events"][dims[2]] += vals.get("eventCount", 0.0)
    for dims, vals in _rows(reports.get("cta") or {}):
        if len(dims) < 3:
            continue
        name = dims[2].strip().lower()
        r = bucket(dims[0], dims[1])
        if name in PLAN_CTA_NAMES:
            r["plan_clicks"] += vals.get("eventCount", 0.0)
        elif name in COACHING_CTA_NAMES:
            r["coaching_clicks"] += vals.get("eventCount", 0.0)
    return daily


def parse_browsers(report: dict | None) -> dict | None:
    if report is None:
        return None
    total = headless = 0.0
    for dims, vals in _rows(report):
        views = vals.get("screenPageViews", 0.0)
        total += views
        if dims and dims[0].lower().startswith(HEADLESS_PREFIX.lower()):
            headless += views
    return {"views": int(total), "headless_views": int(headless)}


def aggregate(daily: dict[str, dict[str, dict]], path: str,
              dates: Iterable[str]) -> dict:
    total = _empty_raw()
    for day in dates:
        r = (daily.get(day) or {}).get(path)
        if r is None:
            continue
        for key in ("views", "active_users", "engagement_seconds",
                    "engaged_weight", "plan_clicks", "coaching_clicks"):
            total[key] += r[key]
        for name in ARTICLE_EVENTS:
            total["events"][name] += r["events"][name]
    return total


def _run_paged(session: Any, property_name: str, body: dict,
               operation: str) -> dict:
    """runReport with offset paging up to rowCount."""
    first: dict | None = None
    rows: list = []
    offset = 0
    while True:
        page_body = dict(body, offset=str(offset)) if offset else body
        report = _audit._run_report(session, property_name, page_body, operation)
        if first is None:
            first = dict(report)
        page = report.get("rows") or []
        rows += page
        offset += len(page)
        if not page or offset >= int(report.get("rowCount") or 0):
            break
    first["rows"] = rows
    return first


OPTIONAL_REPORTS = {
    "cta": "plan/coaching click breakdown unavailable",
    "browsers": "headless-browser check unavailable",
}


def fetch_reports(session: Any, property_name: str, span: dict,
                  post_paths: list[str]) -> tuple[dict, list[str]]:
    """Run every report over the span. cta and browsers are optional: if
    either fails the report still ships and says what is missing."""
    warnings: list[str] = []
    reports: dict[str, dict | None] = {}
    for name, body in report_requests(span, post_paths).items():
        try:
            reports[name] = _run_paged(session, property_name, body,
                                       f"{name} report")
        except Ga4Error as exc:
            if name not in OPTIONAL_REPORTS:
                raise
            reports[name] = None
            warnings.append(f"{OPTIONAL_REPORTS[name]}: {exc}")
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


def mock_reports(span: dict, inventory: dict[str, dict]) -> dict[str, dict]:
    """Deterministic, GA4-shaped daily responses for --mock and tests.
    Posts only have data from their tracking start; the default excluded
    dates carry QA-shaped rows (2 views, 0 s)."""
    page_rows, event_rows, cta_rows = [], [], []
    days = date_range(date.fromisoformat(span["start"]),
                      date.fromisoformat(span["end"]))
    for i, path in enumerate(sorted(inventory)):
        start = tracking_start(inventory[path]["type"])
        seed = (sum(map(ord, path)) % 97) + 3
        # Exercise trailing-slash merging on one path.
        out_path = path.rstrip("/") if i == 0 else path
        for n, day in enumerate(days):
            if start and day < start:
                continue
            key = day.strftime("%Y%m%d")
            if day in DEFAULT_EXCLUDE_DATES:
                page_rows.append(([key, out_path], [2, 1, 0, 1.0]))
                continue
            views = (seed + n) % 6
            if not views:
                continue
            page_rows.append(([key, out_path], [views, max(1, views - 1),
                                                views * (40 + seed % 60),
                                                0.4 + (seed % 5) / 10]))
            event_rows.append(([key, path, "article_scroll_depth"], [views * 2]))
            event_rows.append(([key, path, "article_deep_read"],
                               [(seed + n) % 2]))
            event_rows.append(([key, path, "cta_click"], [int((seed + n) % 3 == 0)]))
            cta_rows.append(([key, path, "custom_plan"], [int((seed + n) % 5 == 0)]))
            cta_rows.append(([key, path, "coaching"], [int((seed + n) % 7 == 0)]))
    return {
        "pages": _mock_report(["date", "pagePath"], list(PAGE_METRICS), page_rows),
        "events": _mock_report(["date", "pagePath", "eventName"], ["eventCount"],
                               event_rows),
        "cta": _mock_report(["date", "pagePath", "customEvent:cta_name"],
                            ["eventCount"], cta_rows),
        "browsers": _mock_report(["browser"], ["screenPageViews"],
                                 [(["Chrome"], [400]), (["Safari"], [250]),
                                  (["HeadlessChrome"], [30])]),
    }


# ── Assembly ──────────────────────────────────────────────────────────────

def _r(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def window_metrics(raw: dict | None, days: int, clicks: bool = True) -> dict:
    """Metrics over `days` usable days. With no usable days every value is
    None: there is nothing to report, not a zero."""
    if not days:
        return {"days": 0, "views": None, "views_per_day": None,
                "active_users": None, "active_users_per_day": None,
                "avg_engagement_seconds": None, "engagement_rate": None,
                "events": {name: None for name in ARTICLE_EVENTS},
                "events_per_day": {name: None for name in ARTICLE_EVENTS},
                "deep_read_rate": None, "plan_clicks": None,
                "coaching_clicks": None}
    raw = raw or _empty_raw()
    views = raw["views"]
    users = raw["active_users"]
    events = raw["events"]
    deep = events["article_deep_read"]
    per_day = lambda v: _r(v / days, 2)  # noqa: E731
    return {
        "days": days,
        "views": int(views),
        "views_per_day": per_day(views),
        "active_users": int(users),
        "active_users_per_day": per_day(users),
        "avg_engagement_seconds": _r(raw["engagement_seconds"] / users, 1) if users else None,
        "engagement_rate": _r(raw["engaged_weight"] / views) if views else None,
        "events": {name: int(count) for name, count in events.items()},
        "events_per_day": {name: per_day(count) for name, count in events.items()},
        "deep_read_rate": _r(deep / views) if views else None,
        "plan_clicks": int(raw["plan_clicks"]) if clicks else None,
        "coaching_clicks": int(raw["coaching_clicks"]) if clicks else None,
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


def _metrics_for(daily: dict, path: str, window: dict, page_type: str,
                 exclude: tuple[date, ...], clicks: bool) -> dict:
    dates = usable_dates(window, page_type, exclude)
    return window_metrics(aggregate(daily, path, dates), len(dates), clicks)


def build_rows(inventory: dict[str, dict], daily: dict, windows: dict,
               exclude: tuple[date, ...], clicks: bool = True) -> list[dict]:
    seen = {p for day in daily.values() for p in day}
    paths = set(inventory)
    paths |= {p for p in seen if is_blog_content(p)}
    paths |= {p for p in seen if p.startswith("/articles/") and p != "/articles/"}
    redesign = "redesign_before" in windows
    rows = []
    for path in sorted(paths):
        meta = inventory.get(path)
        if meta is None:
            slug = path.strip("/").split("/")[-1]
            meta = {"title": _slug_title(slug),
                    "type": "essay" if path.startswith("/articles/")
                    else classify_blog_slug(slug)}
        kind = meta["type"]
        start = tracking_start(kind)
        previous = _metrics_for(daily, path, windows["previous"], kind, exclude, clicks)
        current = _metrics_for(daily, path, windows["current"], kind, exclude, clicks)
        status = week_status(kind, windows, exclude)
        row = {"path": path, "title": meta["title"], "type": kind,
               "tracking_start": start.isoformat() if start else None,
               "comparable": status == "compared", "status": status,
               "previous": previous, "current": current,
               "deltas": deltas(previous, current)}
        if redesign:
            row["redesign"] = None
            if tracked_before_redesign(kind):
                before = _metrics_for(daily, path, windows["redesign_before"],
                                      kind, exclude, clicks)
                after = _metrics_for(daily, path, windows["redesign_after"],
                                     kind, exclude, clicks)
                row["redesign"] = {"before": before, "after": after,
                                   "deltas": deltas(before, after)}
        rows.append(row)
    rows.sort(key=lambda r: (-(r["current"]["views"] or 0),
                             -(r["previous"]["views"] or 0), r["path"]))
    return rows


def _window_total(metrics: list[dict], days: int) -> dict:
    if not days:
        return {"days": 0, "views": None, "views_per_day": None,
                "article_deep_read": None, "article_cta_click": None,
                "cta_click": None, "plan_clicks": None, "coaching_clicks": None}
    views = sum(m["views"] for m in metrics)

    def clicks(key: str) -> int | None:
        values = [m[key] for m in metrics]
        return None if any(v is None for v in values) else sum(values)

    return {
        "days": days,
        "views": views,
        "views_per_day": round(views / days, 2),
        "article_deep_read": sum(m["events"]["article_deep_read"] for m in metrics),
        "article_cta_click": sum(m["events"]["article_cta_click"] for m in metrics),
        "cta_click": sum(m["events"]["cta_click"] for m in metrics),
        "plan_clicks": clicks("plan_clicks"),
        "coaching_clicks": clicks("coaching_clicks"),
    }


def build_type_summary(rows: list[dict], daily: dict, windows: dict,
                       exclude: tuple[date, ...], end: date) -> dict:
    """Per page type: tracking start, usable days, status, totals. Totals are
    per type because usable days differ by type."""
    path_type = {r["path"]: r["type"] for r in rows}
    first_data: dict[str, str] = {}
    for day in sorted(daily):
        for path, raw in daily[day].items():
            kind = path_type.get(path)
            if kind and raw["views"] and kind not in first_data:
                first_data[kind] = day
    summary = {}
    for kind in [t for t in PAGE_TYPES if t in path_type.values()]:
        trows = [r for r in rows if r["type"] == kind]
        start = tracking_start(kind)
        days = {name: len(usable_dates(w, kind, exclude))
                for name, w in windows.items()}
        current = _window_total([r["current"] for r in trows], days["current"])
        previous = _window_total([r["previous"] for r in trows], days["previous"])
        entry = {
            "pages": len(trows),
            "tracking_start": start.isoformat() if start else None,
            "first_date_with_data": first_data.get(kind),
            "usable_days": days,
            "status": week_status(kind, windows, exclude),
            "current": current,
            "previous": previous,
            "views_per_day_pct": _pct(current["views_per_day"],
                                      previous["views_per_day"]),
        }
        if entry["status"] != "compared":
            nxt = first_week_over_week_end(kind, end, exclude)
            entry["first_week_over_week_end"] = nxt.isoformat() if nxt else None
        if "redesign_before" in windows:
            entry["redesign"] = None
            if tracked_before_redesign(kind):
                before = _window_total([r["redesign"]["before"] for r in trows],
                                       days["redesign_before"])
                after = _window_total([r["redesign"]["after"] for r in trows],
                                      days["redesign_after"])
                entry["redesign"] = {
                    "before": before, "after": after,
                    "views_per_day_pct": _pct(after["views_per_day"],
                                              before["views_per_day"])}
        summary[kind] = entry
    return summary


def build_report(inventory: dict[str, dict], reports: dict, windows: dict, *,
                 property_name: str, mock: bool,
                 exclude_dates: Iterable[date] = DEFAULT_EXCLUDE_DATES,
                 warnings: list[str] | None = None) -> dict:
    exclude = tuple(sorted(set(exclude_dates)))
    daily = parse_daily_reports(reports)
    clicks = reports.get("cta") is not None
    rows = build_rows(inventory, daily, windows, exclude, clicks)
    end = date.fromisoformat(windows["current"]["end"])
    span = query_span(windows)
    browsers = parse_browsers(reports.get("browsers"))
    excluded = [{"date": d.isoformat(),
                 "views": int(sum(r["views"] for r in
                                  (daily.get(d.isoformat()) or {}).values()))}
                for d in exclude if span["start"] <= d.isoformat() <= span["end"]]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "property": property_name,
        "mock": mock,
        "comparison": "week_over_week",
        "redesign_date": REDESIGN_DATE.isoformat(),
        "windows": windows,
        "query_span": span,
        "exclude_dates": [d.isoformat() for d in exclude],
        "excluded": excluded,
        "headless_filter": {
            "applied": True,
            "rule": f'GA4 browser does not begin with "{HEADLESS_PREFIX}" '
                    "(case-insensitive), on every query",
            "views_in_span": None if browsers is None else browsers["views"],
            "headless_views_removed": (None if browsers is None
                                       else browsers["headless_views"]),
        },
        "notes": [
            "Usable day = on/after the page type's tracking_start and not in "
            "exclude_dates. Per-day figures divide by usable days.",
            "WordPress posts had no GA4 before 2026-10-09; earlier windows are "
            "never compared for them.",
            "active_users = sum of daily active users (users are not additive "
            "across days; read it as a rate, not unique readers).",
            "deep_read_rate = article_deep_read events / views; "
            "engagement_rate is view-weighted when trailing-slash variants merge.",
            "plan/coaching clicks = cta_click events by cta_name "
            "(custom_plan/season_plan/plan_intent… vs coaching).",
            "Recommended: define internal traffic in GA4 and activate the "
            "Internal Traffic data filter so QA runs never reach reports.",
        ],
        "warnings": list(warnings or []),
        "types": build_type_summary(rows, daily, windows, exclude, end),
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


def _pair(a, b) -> str:
    return f"{_fmt(a)} / {_fmt(b)}"


def _md_title(row: dict) -> str:
    title = row["title"].replace("|", "/")
    return f"[{title}](https://gravelgodcycling.com{row['path']}) ({row['type']})"


def _change(row_or_type: dict, pct) -> str:
    """Δ % when both weeks have usable days, otherwise the reason."""
    if row_or_type["status"] != "compared":
        return row_or_type["status"]
    return _signed(pct, "%")


def _headless_line(report: dict) -> str:
    h = report["headless_filter"]
    rule = f'every query drops rows whose GA4 browser begins with "{HEADLESS_PREFIX}"'
    if h["headless_views_removed"] is None:
        return (f"Headless filter: applied ({rule}), but the browsers check "
                "failed, so how many views it removed is unknown.")
    if h["headless_views_removed"]:
        return (f"Headless filter: applied ({rule}); it removed "
                f"{h['headless_views_removed']:,} of {h['views_in_span']:,} "
                "content views in the queried span.")
    return (f"Headless filter: applied ({rule}), but GA4 reported 0 such views: "
            "the QA runs are recorded as ordinary browsers, so only the date "
            "exclusion removes them.")


def render_how_to_read(report: dict) -> list[str]:
    w = report["windows"]
    types = report["types"]
    lines = [
        "## How to read this",
        "",
        f"- **Main comparison: week over week.** This week = {w['current']['start']} → "
        f"{w['current']['end']}; last week = {w['previous']['start']} → "
        f"{w['previous']['end']}. Δ % compares views per usable day.",
        "- **Usable day** = on or after the page type's tracking start and not an "
        "excluded date. The Days column says how many each week had.",
    ]
    post = types.get("post")
    if post:
        msg = (f"- **WordPress posts: tracking began {post['tracking_start']}.** "
               "Their earlier numbers are not a baseline (no GA4 tag), so they are "
               "never compared against days before that.")
        if post["status"] != "compared" and post.get("first_week_over_week_end"):
            msg += (" First week-over-week comparison: the report covering the week "
                    f"ending {post['first_week_over_week_end']}.")
        lines.append(msg)
    if report["excluded"]:
        dates = ", ".join(f"{e['date']} ({e['views']:,} views)"
                          for e in report["excluded"])
        lines.append(f"- **Excluded dates (scripted QA traffic):** {dates}. "
                     "Change with `--exclude-dates`.")
    elif report["exclude_dates"]:
        lines.append(f"- **Excluded dates:** {', '.join(report['exclude_dates'])} "
                     "(outside this report's span).")
    lines += [
        f"- {_headless_line(report)}",
        "- **Recommended:** in GA4, define internal traffic (Admin → Data streams → "
        "Configure tag settings → Define internal traffic) and activate the "
        "Internal Traffic data filter, so QA runs stop landing in reports.",
        "- \"–\" means no usable days, or no views to compute a rate from.",
        "",
    ]
    return lines


def _type_label(kind: str, info: dict) -> str:
    start = info["tracking_start"]
    return f"{kind} (since {start})" if start else kind


def render_markdown(report: dict, top_n: int = 10, min_views: int = 20) -> str:
    rows = report["pages"]
    types = report["types"]
    lines = ["# Gravel God blog performance", ""]
    if report["mock"]:
        lines += ["**MOCK DATA.**", ""]
    lines += render_how_to_read(report)
    for warning in report["warnings"]:
        lines += [f"> Warning: {warning}", ""]
    lines += [
        "## By page type (this week / last week)",
        "",
        "| Type | Pages | Days | Views/day | Δ % | Deep reads | Plan clicks | Coaching clicks |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for kind, info in types.items():
        c, p = info["current"], info["previous"]
        lines.append(
            f"| {_type_label(kind, info)} | {info['pages']} | "
            f"{_pair(c['days'], p['days'])} | "
            f"{_pair(c['views_per_day'], p['views_per_day'])} | "
            f"{_change(info, info['views_per_day_pct'])} | "
            f"{_pair(c['article_deep_read'], p['article_deep_read'])} | "
            f"{_pair(c['plan_clicks'], p['plan_clicks'])} | "
            f"{_pair(c['coaching_clicks'], p['coaching_clicks'])} |")
    lines += [
        "",
        f"## Top {top_n} by views (this week)",
        "",
        "| Page | Views/day this week | Last week | Δ % | Avg engagement (s) | Engagement rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    top = [r for r in rows if r["current"]["views"]][:top_n]
    if not top:
        lines.append("| No views on usable days this week | | | | | |")
    for row in top:
        c, p = row["current"], row["previous"]
        lines.append(
            f"| {_md_title(row)} | {_fmt(c['views_per_day'])} | "
            f"{_fmt(p['views_per_day'])} | "
            f"{_change(row, row['deltas']['views_per_day_pct'])} | "
            f"{_fmt(c['avg_engagement_seconds'])} | {_rate(c['engagement_rate'])} |")
    deep = sorted((r for r in rows if (r["current"]["views"] or 0) >= min_views
                   and r["current"]["deep_read_rate"] is not None),
                  key=lambda r: (-r["current"]["deep_read_rate"], r["path"]))[:top_n]
    lines += [
        "",
        f"## Top {top_n} by deep-read rate (this week, ≥{min_views} views)",
        "",
        "| Page | Deep-read rate | Last week | Views |",
        "|---|---:|---:|---:|",
    ]
    if not deep:
        lines.append(f"| No page has ≥{min_views} views this week | | | |")
    for row in deep:
        lines.append(
            f"| {_md_title(row)} | {_rate(row['current']['deep_read_rate'])} | "
            f"{_rate(row['previous']['deep_read_rate'])} | {row['current']['views']} |")
    movers = [r for r in rows if r["comparable"]
              and r["previous"]["views"] + r["current"]["views"] >= min_views]
    movers.sort(key=lambda r: (-abs(r["deltas"]["views_per_day"] or 0), r["path"]))
    lines += [
        "",
        "## Biggest movers (week over week, views/day)",
        "",
        "Only pages with usable days in both weeks.",
        "",
        "| Page | Last week/day | This week/day | Δ/day | Δ % |",
        "|---|---:|---:|---:|---:|",
    ]
    if not movers:
        lines.append(f"| No page has usable days in both weeks and ≥{min_views} "
                     "views yet | | | | |")
    for row in movers[:top_n]:
        d = row["deltas"]
        lines.append(
            f"| {_md_title(row)} | {_fmt(row['previous']['views_per_day'])} | "
            f"{_fmt(row['current']['views_per_day'])} | {_signed(d['views_per_day'])} | "
            f"{_signed(d['views_per_day_pct'], '%')} |")
    if "redesign_before" in report["windows"]:
        lines += render_redesign(report, top_n)
    lines += ["", "Full per-page data (both weeks, deltas, usable days) is in the "
              "JSON beside this file.", ""]
    return "\n".join(lines)


def render_redesign(report: dict, top_n: int) -> list[str]:
    w = report["windows"]
    eligible = {k: v for k, v in report["types"].items() if v.get("redesign")}
    skipped = [f"{k} (tracking began {v['tracking_start']})"
               for k, v in report["types"].items() if not v.get("redesign")]
    lines = [
        "",
        f"## Before vs after the {report['redesign_date']} redesign",
        "",
        f"Before {w['redesign_before']['start']} → {w['redesign_before']['end']}; "
        f"after {w['redesign_after']['start']} → {w['redesign_after']['end']}, "
        "excluded dates removed. Only page types tracked before the redesign."
        + (f" Not compared: {', '.join(skipped)}." if skipped else ""),
        "",
        "| Type | Days (after / before) | Views/day (after / before) | Δ % |",
        "|---|---:|---:|---:|",
    ]
    for kind, info in eligible.items():
        r = info["redesign"]
        lines.append(
            f"| {kind} | {_pair(r['after']['days'], r['before']['days'])} | "
            f"{_pair(r['after']['views_per_day'], r['before']['views_per_day'])} | "
            f"{_signed(r['views_per_day_pct'], '%')} |")
    rows = [r for r in report["pages"] if r.get("redesign")
            and r["redesign"]["after"]["views"]]
    rows.sort(key=lambda r: (-r["redesign"]["after"]["views"], r["path"]))
    lines += ["", "| Page | After/day | Before/day | Δ % |", "|---|---:|---:|---:|"]
    if not rows:
        lines.append("| No views after the redesign on usable days | | | |")
    for row in rows[:top_n]:
        r = row["redesign"]
        lines.append(
            f"| {_md_title(row)} | {_fmt(r['after']['views_per_day'])} | "
            f"{_fmt(r['before']['views_per_day'])} | "
            f"{_signed(r['deltas']['views_per_day_pct'], '%')} |")
    return lines


# ── CLI ───────────────────────────────────────────────────────────────────

def parse_exclude_dates(value: str | None) -> tuple[date, ...]:
    """None/blank → default QA dates; 'none' → nothing; else comma list."""
    if value is None or not value.strip():
        return DEFAULT_EXCLUDE_DATES
    if value.strip().lower() == "none":
        return ()
    return tuple(sorted({date.fromisoformat(part.strip())
                         for part in value.split(",") if part.strip()}))


def run(*, end: date, mock: bool, property_value: str | None,
        credentials: Path | None,
        exclude_dates: Iterable[date] = DEFAULT_EXCLUDE_DATES,
        compare_redesign: bool = False,
        session_factory: Callable[[Path], Any] | None = None) -> dict:
    windows = build_windows(end, compare_redesign)
    span = query_span(windows)
    inventory = load_inventory()
    post_paths = sorted(p for p, m in inventory.items() if m["type"] == "post")
    warnings: list[str] = []
    if mock:
        property_name = "properties/0"
        reports = mock_reports(span, inventory)
    else:
        if not property_value or not credentials:
            raise Ga4Error("--property and --credentials are required unless --mock")
        property_name = normalize_property(property_value)
        if not credentials.exists():
            raise Ga4Error("credentials file not found")
        factory = session_factory or (lambda p: _audit.authorized_session(p))
        session = factory(credentials)
        reports, warnings = fetch_reports(session, property_name, span, post_paths)
    return build_report(inventory, reports, windows, property_name=property_name,
                        mock=mock, exclude_dates=exclude_dates, warnings=warnings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--mock", action="store_true",
                        help="Use deterministic sample data; no GA4 call")
    parser.add_argument("--property", help="GA4 property ID or properties/ID")
    parser.add_argument("--credentials", type=Path,
                        help="Service-account JSON path")
    parser.add_argument("--end-date", default=None,
                        help="Last day of this week's window (default: yesterday UTC)")
    parser.add_argument("--exclude-dates", default=None,
                        help="Comma-separated YYYY-MM-DD dates to drop (default: "
                             + ",".join(d.isoformat() for d in DEFAULT_EXCLUDE_DATES)
                             + "; 'none' drops nothing)")
    parser.add_argument("--compare-redesign", action="store_true",
                        help="Add the 30-days-before vs after-redesign section "
                             "(page types tracked before the redesign only)")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--stem", default=None,
                        help="Output file stem (default: run date, YYYY-MM-DD)")
    args = parser.parse_args(argv)

    today = datetime.now(timezone.utc).date()
    try:
        end = (date.fromisoformat(args.end_date) if args.end_date
               else today - timedelta(days=1))
        exclude = parse_exclude_dates(args.exclude_dates)
    except ValueError:
        print("ERROR: --end-date and --exclude-dates must use YYYY-MM-DD",
              file=sys.stderr)
        return 2
    try:
        report = run(end=end, mock=args.mock, property_value=args.property,
                     credentials=args.credentials, exclude_dates=exclude,
                     compare_redesign=args.compare_redesign)
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
