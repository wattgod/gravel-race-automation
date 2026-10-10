"""Tests for scripts/blog_performance_report.py — mock data only, no GA4."""

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest


ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "blog_performance_report.py"
SPEC = importlib.util.spec_from_file_location("blog_performance_report", SCRIPT)
bp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bp)

WORKFLOW = ROOT / ".github" / "workflows" / "blog-performance-report.yml"


def report_body(dims, metrics, rows):
    return bp._mock_report(dims, metrics, rows)


def daily_reports(pages=(), events=(), cta=(), browsers=None):
    """GA4-shaped daily bodies. Rows: pages ([day, path], [views, users,
    seconds, rate]); events/cta ([day, path, name], [count])."""
    out = {
        "pages": report_body(["date", "pagePath"], list(bp.PAGE_METRICS), list(pages)),
        "events": report_body(["date", "pagePath", "eventName"], ["eventCount"],
                              list(events)),
        "cta": report_body(["date", "pagePath", "customEvent:cta_name"],
                           ["eventCount"], list(cta)),
        "browsers": report_body(["browser"], ["screenPageViews"], list(browsers or [])),
    }
    return out


def views_rows(path, days, views=10, seconds=300, rate=0.5):
    return [([d.strftime("%Y%m%d"), path], [views, views // 2, seconds, rate])
            for d in days]


def days_between(start, end):
    return bp.date_range(date.fromisoformat(start), date.fromisoformat(end))


POST = {"/a-post/": {"title": "A Post", "type": "post"}}
ESSAY = {"/articles/an-essay/": {"title": "An Essay", "type": "essay"}}


def build(inventory, reports, end, exclude=bp.DEFAULT_EXCLUDE_DATES,
          compare_redesign=False, cta=True):
    if not cta:
        reports = dict(reports, cta=None)
    windows = bp.build_windows(end, compare_redesign)
    return bp.build_report(inventory, reports, windows, property_name="properties/1",
                           mock=True, exclude_dates=exclude)


# ── Inventory ────────────────────────────────────────────────────────────

def test_inventory_covers_essays_posts_and_blog():
    inv = bp.load_inventory()
    types = {}
    for meta in inv.values():
        types[meta["type"]] = types.get(meta["type"], 0) + 1
    assert types.get("essay") == len(list(bp.ARTICLES_DIR.glob("*/index.html"))) >= 2
    assert types.get("post") == len(list(bp.POST_SOURCES.glob("*.json"))) >= 77
    assert all(p.startswith("/articles/") for p, m in inv.items() if m["type"] == "essay")
    assert all(p.count("/") == 2 and not p.startswith(("/blog/", "/articles/"))
               for p, m in inv.items() if m["type"] == "post")
    assert all(p.startswith("/blog/") for p, m in inv.items()
               if m["type"] in {"roundup", "recap", "preview"})
    assert not any(t.endswith("Gravel God") for t in (m["title"] for m in inv.values()))


def test_inventory_from_fixture_dirs(tmp_path):
    sources = tmp_path / "post_sources"
    sources.mkdir()
    (sources / "a-post.json").write_text(json.dumps(
        {"slug": "a-post", "live": {"title": "SEO | Gravel God", "headline": "A Post"}}))
    (sources / "b-post.json").write_text(json.dumps(
        {"slug": "b-post", "live": {"title": "B Title | Gravel God"}}))
    articles = tmp_path / "articles" / "an-essay"
    articles.mkdir(parents=True)
    (articles / "index.html").write_text("<title>An Essay | Gravel God</title>")
    index = tmp_path / "blog-index.json"
    index.write_text(json.dumps([
        {"url": "/blog/roundup-x/", "title": "Roundup &amp; X"},
        {"url": "/articles/an-essay/", "title": "ignored"},
    ]))
    inv = bp.load_inventory(sources, tmp_path / "articles", index)
    assert inv == {
        "/a-post/": {"title": "A Post", "type": "post"},
        "/b-post/": {"title": "B Title", "type": "post"},
        "/articles/an-essay/": {"title": "An Essay", "type": "essay"},
        "/blog/roundup-x/": {"title": "Roundup & X", "type": "roundup"},
    }


@pytest.mark.parametrize("slug,kind", [
    ("roundup-west-fall-2026", "roundup"),
    ("unbound-200-recap", "recap"),
    ("unbound-200", "preview"),
])
def test_classify_blog_slug(slug, kind):
    assert bp.classify_blog_slug(slug) == kind


@pytest.mark.parametrize("raw,expected", [
    ("/blog/x", "/blog/x/"),
    ("/blog/x/?utm=1", "/blog/x/"),
    ("blog/x/", "/blog/x/"),
    ("//a//", "/a/"),
])
def test_normalize_path(raw, expected):
    assert bp.normalize_path(raw) == expected


# ── Windows + usable days ────────────────────────────────────────────────

def test_windows_are_last_7_days_vs_previous_7():
    w = bp.build_windows(date(2026, 10, 25))
    assert w == {"current": {"start": "2026-10-19", "end": "2026-10-25", "days": 7},
                 "previous": {"start": "2026-10-12", "end": "2026-10-18", "days": 7}}


def test_redesign_windows_only_when_asked():
    w = bp.build_windows(date(2026, 10, 15), compare_redesign=True)
    assert w["redesign_before"] == {"start": "2026-09-09", "end": "2026-10-08", "days": 30}
    assert w["redesign_after"] == {"start": "2026-10-09", "end": "2026-10-15", "days": 7}
    with pytest.raises(bp.Ga4Error):
        bp.build_windows(date(2026, 10, 8), compare_redesign=True)


def test_tracking_start_posts_only():
    assert bp.tracking_start("post") == date(2026, 10, 9)
    for kind in ("essay", "preview", "recap", "roundup"):
        assert bp.tracking_start(kind) is None
        assert bp.tracked_before_redesign(kind)
    assert not bp.tracked_before_redesign("post")


def test_usable_dates_drop_pre_tracking_and_excluded_days():
    window = {"start": "2026-10-05", "end": "2026-10-12"}
    assert bp.usable_dates(window, "post", bp.DEFAULT_EXCLUDE_DATES) == [
        "2026-10-11", "2026-10-12"]
    assert bp.usable_dates(window, "essay", bp.DEFAULT_EXCLUDE_DATES) == [
        "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08",
        "2026-10-11", "2026-10-12"]
    assert len(bp.usable_dates(window, "essay", ())) == 8


@pytest.mark.parametrize("raw,expected", [
    (None, bp.DEFAULT_EXCLUDE_DATES),
    ("", bp.DEFAULT_EXCLUDE_DATES),
    ("none", ()),
    ("2026-10-12, 2026-10-11", (date(2026, 10, 11), date(2026, 10, 12))),
])
def test_parse_exclude_dates(raw, expected):
    assert bp.parse_exclude_dates(raw) == expected


# ── Required: post before tracking_start ─────────────────────────────────

def test_post_data_before_tracking_start_is_never_compared():
    """GA4 rows for a post before 2026-10-09 (stray hits, mis-attribution)
    must not become a baseline: the post reads 'tracking began', not a delta."""
    pre = views_rows("/a-post/", days_between("2026-09-26", "2026-10-08"), views=1)
    post = views_rows("/a-post/", days_between("2026-10-09", "2026-10-09"), views=4)
    report = build(POST, daily_reports(pages=pre + post), date(2026, 10, 9),
                   exclude=())
    row = report["pages"][0]
    assert row["tracking_start"] == "2026-10-09"
    assert row["comparable"] is False
    assert row["status"] == "tracking began 2026-10-09"
    assert row["previous"]["days"] == 0 and row["previous"]["views"] is None
    assert row["current"]["days"] == 1 and row["current"]["views"] == 4
    assert row["deltas"]["views_per_day_pct"] is None
    t = report["types"]["post"]
    assert t["status"] == "tracking began 2026-10-09"
    assert t["views_per_day_pct"] is None
    md = bp.render_markdown(report)
    assert "tracking began 2026-10-09" in md
    post_line = next(l for l in md.splitlines() if l.startswith("| [A Post]"))
    cells = [c.strip() for c in post_line.split("|")[1:-1]]
    assert cells[2:4] == ["–", "tracking began 2026-10-09"]  # last week, Δ %


def test_redesign_comparison_skips_posts():
    pre = views_rows("/a-post/", days_between("2026-09-09", "2026-10-08"), views=1)
    essay = views_rows("/articles/an-essay/", days_between("2026-09-09", "2026-10-15"))
    report = build({**POST, **ESSAY}, daily_reports(pages=pre + essay),
                   date(2026, 10, 15), compare_redesign=True)
    rows = {r["path"]: r for r in report["pages"]}
    assert rows["/a-post/"]["redesign"] is None
    assert report["types"]["post"]["redesign"] is None
    essay_r = rows["/articles/an-essay/"]["redesign"]
    assert essay_r["before"]["days"] == 30
    assert essay_r["after"]["days"] == 5  # 10-09..10-15 minus 10-09, 10-10
    assert essay_r["deltas"]["views_per_day_pct"] == 0.0
    md = bp.render_markdown(report)
    assert "Not compared: post (tracking began 2026-10-09)" in md


# ── Required: excluded dates ─────────────────────────────────────────────

def test_excluded_dates_are_dropped_and_reported():
    normal = views_rows("/articles/an-essay/", days_between("2026-10-05", "2026-10-15"),
                        views=10)
    qa = [([d, "/articles/an-essay/"], [500, 500, 0, 1.0])
          for d in ("20261009", "20261010")]
    reports = daily_reports(pages=[r for r in normal if r[0][0] not in
                                   ("20261009", "20261010")] + qa)
    report = build(ESSAY, reports, date(2026, 10, 15))
    row = report["pages"][0]
    assert row["current"]["days"] == 5  # 10-09..10-15 minus the two QA days
    assert row["current"]["views"] == 50
    assert row["current"]["views_per_day"] == 10.0
    assert report["exclude_dates"] == ["2026-10-09", "2026-10-10"]
    assert report["excluded"] == [{"date": "2026-10-09", "views": 500},
                                  {"date": "2026-10-10", "views": 500}]
    md = bp.render_markdown(report)
    assert "2026-10-09 (500 views), 2026-10-10 (500 views)" in md
    # Opting out counts the QA views.
    raw = build(ESSAY, reports, date(2026, 10, 15), exclude=())
    assert raw["pages"][0]["current"]["views"] == 1050
    assert raw["excluded"] == []


def test_week_with_only_excluded_days_says_so():
    reports = daily_reports(pages=views_rows(
        "/articles/an-essay/", days_between("2026-10-01", "2026-10-12")))
    exclude = tuple(bp.date_range(date(2026, 9, 29), date(2026, 10, 5)))
    report = build(ESSAY, reports, date(2026, 10, 12), exclude=exclude)
    row = report["pages"][0]
    assert row["comparable"] is False
    assert row["status"] == "no usable days last week (excluded dates)"


# ── Required: week over week ─────────────────────────────────────────────

def test_week_over_week_per_usable_day():
    end = date(2026, 10, 25)  # this week 10-19..25, last week 10-12..18
    last = views_rows("/a-post/", days_between("2026-10-12", "2026-10-18"),
                      views=10, seconds=200, rate=0.5)
    this = views_rows("/a-post/", days_between("2026-10-19", "2026-10-25"),
                      views=20, seconds=300, rate=0.6)
    events = ([([d[0][0], "/a-post/", "article_deep_read"], [1]) for d in last]
              + [([d[0][0], "/a-post/", "article_deep_read"], [4]) for d in this])
    cta = [(["20261020", "/a-post/", "custom_plan"], [2]),
           (["20261013", "/a-post/", "coaching"], [1])]
    report = build(POST, daily_reports(pages=last + this, events=events, cta=cta), end)
    row = report["pages"][0]
    assert row["comparable"] and row["status"] == "compared"
    assert (row["previous"]["days"], row["current"]["days"]) == (7, 7)
    assert row["previous"]["views_per_day"] == 10.0
    assert row["current"]["views_per_day"] == 20.0
    assert row["deltas"]["views_per_day_pct"] == 100.0
    assert row["deltas"]["deep_read_rate_pts"] == pytest.approx(0.2 - 0.1)
    assert row["deltas"]["engagement_rate_pts"] == pytest.approx(0.1)
    assert row["current"]["plan_clicks"] == 2 and row["previous"]["coaching_clicks"] == 1
    t = report["types"]["post"]
    assert t["status"] == "compared" and t["views_per_day_pct"] == 100.0
    md = bp.render_markdown(report)
    movers = md.split("## Biggest movers")[1]
    assert "A Post" in movers and "+100.0%" in movers


def test_week_over_week_uneven_usable_days_normalise():
    """First post comparison: last week has one usable day (10-11)."""
    end = date(2026, 10, 18)
    rows = views_rows("/a-post/", days_between("2026-10-09", "2026-10-18"), views=6)
    report = build(POST, daily_reports(pages=rows), end)
    row = report["pages"][0]
    assert (row["previous"]["days"], row["current"]["days"]) == (1, 7)
    assert row["previous"]["views"] == 6 and row["current"]["views"] == 42
    assert row["deltas"]["views_per_day_pct"] == 0.0


def test_first_week_over_week_end_for_posts():
    assert bp.first_week_over_week_end(
        "post", date(2026, 10, 11), bp.DEFAULT_EXCLUDE_DATES) == date(2026, 10, 18)
    assert bp.first_week_over_week_end("post", date(2026, 10, 11), ()) == date(
        2026, 10, 16)


# ── Requests ─────────────────────────────────────────────────────────────

def test_report_requests_are_daily_and_drop_headless_browsers():
    span = bp.query_span(bp.build_windows(date(2026, 10, 25)))
    assert span == {"start": "2026-10-12", "end": "2026-10-25"}
    reqs = bp.report_requests(span, ["/a-post/"])
    assert set(reqs) == {"pages", "events", "cta", "browsers"}
    for name, body in reqs.items():
        assert body["dateRanges"] == [{"startDate": "2026-10-12", "endDate": "2026-10-25"}]
        filt = json.dumps(body["dimensionFilter"])
        assert '"/blog/"' in filt and '"/a-post"' in filt
        if name != "browsers":
            assert body["dimensions"][0] == {"name": "date"}
            assert '"notExpression"' in filt and '"Headless"' in filt
    assert [d["name"] for d in reqs["cta"]["dimensions"]] == [
        "date", "pagePath", "customEvent:cta_name"]
    assert reqs["browsers"]["dimensions"] == [{"name": "browser"}]
    assert "notExpression" not in json.dumps(reqs["browsers"]["dimensionFilter"])


def test_headless_line_reflects_what_ga4_reported():
    base = daily_reports(pages=views_rows("/articles/an-essay/",
                                          days_between("2026-10-12", "2026-10-25")))
    found = build(ESSAY, dict(base, browsers=report_body(
        ["browser"], ["screenPageViews"], [(["Chrome"], [90]), (["HeadlessChrome"], [10])])),
        date(2026, 10, 25))
    assert found["headless_filter"]["headless_views_removed"] == 10
    assert "removed 10 of 100" in bp.render_markdown(found)
    none = build(ESSAY, dict(base, browsers=report_body(
        ["browser"], ["screenPageViews"], [(["Chrome"], [90])])), date(2026, 10, 25))
    assert "only the date exclusion removes them" in bp.render_markdown(none)
    failed = build(ESSAY, dict(base, browsers=None), date(2026, 10, 25))
    assert failed["headless_filter"]["headless_views_removed"] is None
    assert "unknown" in bp.render_markdown(failed)


# ── Parsing + metrics ────────────────────────────────────────────────────

def test_parse_daily_merges_trailing_slash_and_classifies_ctas():
    daily = bp.parse_daily_reports(daily_reports(
        pages=[(["20261012", "/a-post"], [10, 8, 400, 0.5]),
               (["20261012", "/a-post/"], [30, 20, 1200, 0.7])],
        events=[(["20261012", "/a-post/", "article_deep_read"], [12]),
                (["20261012", "/a-post", "article_scroll_depth"], [50]),
                (["20261012", "/a-post/", "page_view"], [99])],
        cta=[(["20261012", "/a-post/", "custom_plan"], [2]),
             (["20261012", "/a-post/", "season_plan"], [1]),
             (["20261012", "/a-post/", "coaching"], [4]),
             (["20261012", "/a-post/", "substack"], [9])],
    ))
    r = daily["2026-10-12"]["/a-post/"]
    assert r["views"] == 40 and r["active_users"] == 28
    assert r["engagement_seconds"] == 1600
    assert r["engaged_weight"] == pytest.approx(10 * 0.5 + 30 * 0.7)
    assert r["events"]["article_deep_read"] == 12
    assert r["events"]["article_scroll_depth"] == 50
    assert "page_view" not in r["events"]
    assert r["plan_clicks"] == 3 and r["coaching_clicks"] == 4


def test_window_metrics_normalise_per_usable_day():
    raw = bp._empty_raw()
    raw.update(views=40.0, active_users=20.0, engagement_seconds=1000.0,
               engaged_weight=24.0, plan_clicks=3.0, coaching_clicks=1.0)
    raw["events"]["article_deep_read"] = 10.0
    m = bp.window_metrics(raw, 4)
    assert m["days"] == 4 and m["views_per_day"] == 10.0
    assert m["active_users_per_day"] == 5.0
    assert m["avg_engagement_seconds"] == 50.0
    assert m["engagement_rate"] == 0.6
    assert m["deep_read_rate"] == 0.25
    assert m["events_per_day"]["article_deep_read"] == 2.5
    assert (m["plan_clicks"], m["coaching_clicks"]) == (3, 1)


def test_no_usable_days_is_none_not_zero():
    m = bp.window_metrics(None, 0)
    assert m["days"] == 0 and m["views"] is None and m["views_per_day"] is None
    z = bp.window_metrics(None, 7)
    assert z["views"] == 0 and z["deep_read_rate"] is None


def test_unknown_blog_paths_are_added_and_non_content_ignored():
    rows = [(["20261020", path], [v, v, 10, 0.5]) for path, v in (
        ("/blog/new-race-recap/", 5), ("/blog/", 100), ("/articles/", 10),
        ("/race/unbound/", 999))]
    report = build({}, daily_reports(pages=rows), date(2026, 10, 25))
    assert [(r["path"], r["type"]) for r in report["pages"]] == [
        ("/blog/new-race-recap/", "recap")]


def test_missing_cta_breakdown_marks_clicks_unavailable():
    reports = daily_reports(pages=views_rows("/a-post/", days_between(
        "2026-10-12", "2026-10-25")))
    report = build(POST, reports, date(2026, 10, 25), cta=False)
    report["warnings"] = ["x"]
    assert report["pages"][0]["current"]["plan_clicks"] is None
    assert report["types"]["post"]["current"]["plan_clicks"] is None
    assert "Warning: x" in bp.render_markdown(report)


# ── GA4 fetch (fake session, no network) ─────────────────────────────────

class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status
        self.content = b"{}"

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, fail=(), pages=None):
        self.calls = []
        self.fail = set(fail)
        self.pages = pages  # list of row-lists served in order for the pages report

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        dims = [d["name"] for d in json["dimensions"]]
        if any(d in self.fail for d in dims):
            return FakeResponse({"error": {"status": "INVALID_ARGUMENT"}}, 400)
        metrics = [m["name"] for m in json["metrics"]]
        if self.pages and dims == ["date", "pagePath"]:
            page = self.pages.pop(0)
            body = report_body(dims, metrics, page)
            body["rowCount"] = 3
            return FakeResponse(body)
        return FakeResponse(report_body(dims, metrics, []))


def test_fetch_reports_posts_four_reports_to_property():
    session = FakeSession()
    span = {"start": "2026-10-12", "end": "2026-10-25"}
    reports, warnings = bp.fetch_reports(session, "properties/42", span, ["/a/"])
    assert set(reports) == {"pages", "events", "cta", "browsers"} and warnings == []
    assert all(url.endswith("/properties/42:runReport") for url, _ in session.calls)
    assert len(session.calls) == 4


def test_fetch_reports_pages_through_row_count():
    session = FakeSession(pages=[
        [(["20261012", "/a/"], [1, 1, 1, 1]), (["20261013", "/a/"], [1, 1, 1, 1])],
        [(["20261014", "/a/"], [1, 1, 1, 1])]])
    span = {"start": "2026-10-12", "end": "2026-10-25"}
    reports, _ = bp.fetch_reports(session, "properties/42", span, [])
    assert len(reports["pages"]["rows"]) == 3
    page_calls = [b for _, b in session.calls
                  if [d["name"] for d in b["dimensions"]] == ["date", "pagePath"]]
    assert [b.get("offset") for b in page_calls] == [None, "2"]


@pytest.mark.parametrize("dim,key", [("customEvent:cta_name", "cta"),
                                     ("browser", "browsers")])
def test_fetch_reports_degrades_when_optional_report_fails(dim, key):
    span = {"start": "2026-10-12", "end": "2026-10-25"}
    reports, warnings = bp.fetch_reports(FakeSession(fail=[dim]), "properties/42",
                                         span, [])
    assert reports[key] is None
    assert len(warnings) == 1 and "HTTP 400" in warnings[0]


def test_required_report_failure_raises():
    span = {"start": "2026-10-12", "end": "2026-10-25"}
    with pytest.raises(bp.Ga4Error):
        bp.fetch_reports(FakeSession(fail=["eventName"]), "properties/42", span, [])


def test_run_live_path_uses_session_factory(tmp_path):
    creds = tmp_path / "c.json"
    creds.write_text("{}")
    session = FakeSession()
    report = bp.run(end=date(2026, 10, 25), mock=False, property_value="42",
                    credentials=creds, session_factory=lambda p: session)
    assert report["property"] == "properties/42" and report["mock"] is False
    assert len(session.calls) == 4  # one daily query per report over the span
    assert {r["type"] for r in report["pages"]} >= {"essay", "post"}


def test_run_requires_credentials_without_mock():
    with pytest.raises(bp.Ga4Error):
        bp.run(end=date(2026, 10, 12), mock=False, property_value=None,
               credentials=None)


# ── End to end (mock) ────────────────────────────────────────────────────

def test_cli_mock_writes_json_and_markdown(tmp_path):
    assert bp.main(["--mock", "--end-date", "2026-10-25",
                    "--output-dir", str(tmp_path), "--stem", "snap"]) == 0
    data = json.loads((tmp_path / "snap.json").read_text())
    md = (tmp_path / "snap.md").read_text()
    assert data["mock"] is True and data["comparison"] == "week_over_week"
    assert data["windows"]["current"]["days"] == 7
    assert "redesign_before" not in data["windows"]
    inv = bp.load_inventory()
    assert set(inv) <= {r["path"] for r in data["pages"]}
    row = data["pages"][0]
    assert {"path", "title", "type", "tracking_start", "status", "previous",
            "current", "deltas"} <= set(row)
    assert set(row["current"]["events"]) == set(bp.ARTICLE_EVENTS)
    assert data["types"]["post"]["tracking_start"] == "2026-10-09"
    assert data["types"]["post"]["status"] == "compared"
    assert md.index("## How to read this") < md.index("## By page type")
    for heading in ("## By page type", "## Top 10 by views", "## Top 10 by deep-read rate",
                    "## Biggest movers", "MOCK DATA", "Internal Traffic"):
        assert heading in md


def test_cli_mock_today_shows_tracking_began_not_a_delta(tmp_path):
    assert bp.main(["--mock", "--end-date", "2026-10-09", "--compare-redesign",
                    "--output-dir", str(tmp_path), "--stem", "snap"]) == 0
    data = json.loads((tmp_path / "snap.json").read_text())
    md = (tmp_path / "snap.md").read_text()
    for row in (r for r in data["pages"] if r["type"] == "post"):
        assert row["status"] == "tracking began 2026-10-09"
        assert row["deltas"]["views_per_day_pct"] is None
        assert row["redesign"] is None
    assert "| post (since 2026-10-09) | 77 | 0 / 0 | – / – | tracking began 2026-10-09 |" in md
    assert "## Before vs after the 2026-10-09 redesign" in md


def test_cli_rejects_bad_dates(tmp_path):
    assert bp.main(["--mock", "--exclude-dates", "10/09",
                    "--output-dir", str(tmp_path)]) == 2
    assert bp.main(["--mock", "--end-date", "2026-10-01", "--compare-redesign",
                    "--output-dir", str(tmp_path)]) == 1


# ── Workflow contract ────────────────────────────────────────────────────

def test_workflow_is_dispatchable_weekly_and_never_echoes_secrets():
    text = WORKFLOW.read_text()
    assert "workflow_dispatch" in text
    assert "cron:" in text and "* * 1" in text  # Mondays
    assert "scripts/blog_performance_report.py" in text
    assert "actions/upload-artifact" in text
    assert "data/blog-performance" in text
    assert "GG_GA4_PROPERTY_ID" in text
    assert "--exclude-dates" in text and "--compare-redesign" in text
    for line in text.splitlines():
        if "secrets." in line:
            assert "echo" not in line and "cat " not in line
    assert "chmod(0o600)" in text
