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


def window_reports(pages=(), events=(), cta=()):
    return {
        "pages": report_body(["pagePath"], list(bp.PAGE_METRICS), list(pages)),
        "events": report_body(["pagePath", "eventName"], ["eventCount"], list(events)),
        "cta": report_body(["pagePath", "customEvent:cta_name"], ["eventCount"], list(cta)),
    }


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


# ── Windows ──────────────────────────────────────────────────────────────

def test_windows_are_30_days_before_and_redesign_to_end():
    w = bp.build_windows(date(2026, 10, 15))
    assert w["before"] == {"start": "2026-09-09", "end": "2026-10-08", "days": 30}
    assert w["after"] == {"start": "2026-10-09", "end": "2026-10-15", "days": 7}


def test_empty_after_window_is_an_error():
    with pytest.raises(bp.Ga4Error):
        bp.build_windows(date(2026, 10, 8))


# ── Requests ─────────────────────────────────────────────────────────────

def test_report_requests_filter_content_paths_and_events():
    w = bp.build_windows(date(2026, 10, 12))["after"]
    reqs = bp.report_requests(w, ["/a-post/"])
    assert set(reqs) == {"pages", "events", "cta"}
    for body in reqs.values():
        assert body["dateRanges"] == [{"startDate": "2026-10-09", "endDate": "2026-10-12"}]
    page_filter = json.dumps(reqs["pages"]["dimensionFilter"])
    assert '"/blog/"' in page_filter and '"/articles/"' in page_filter
    assert '"/a-post/"' in page_filter and '"/a-post"' in page_filter
    event_filter = json.dumps(reqs["events"]["dimensionFilter"])
    for name in bp.ARTICLE_EVENTS:
        assert name in event_filter
    assert [d["name"] for d in reqs["cta"]["dimensions"]] == [
        "pagePath", "customEvent:cta_name"]
    assert {m["name"] for m in reqs["pages"]["metrics"]} == set(bp.PAGE_METRICS)


# ── Parsing + metrics ────────────────────────────────────────────────────

def test_parse_merges_trailing_slash_and_classifies_ctas():
    raw = bp.parse_window_reports(window_reports(
        pages=[(["/a-post"], [10, 8, 400, 0.5]), (["/a-post/"], [30, 20, 1200, 0.7])],
        events=[(["/a-post/", "article_deep_read"], [12]),
                (["/a-post", "article_scroll_depth"], [50]),
                (["/a-post/", "page_view"], [99])],
        cta=[(["/a-post/", "custom_plan"], [2]), (["/a-post/", "season_plan"], [1]),
             (["/a-post/", "coaching"], [4]), (["/a-post/", "substack"], [9])],
    ))
    r = raw["/a-post/"]
    assert r["views"] == 40 and r["active_users"] == 28
    assert r["engagement_seconds"] == 1600
    assert r["engaged_weight"] == pytest.approx(10 * 0.5 + 30 * 0.7)
    assert r["events"]["article_deep_read"] == 12
    assert r["events"]["article_scroll_depth"] == 50
    assert "page_view" not in r["events"]
    assert r["plan_clicks"] == 3 and r["coaching_clicks"] == 4


def test_window_metrics_normalise_per_day_and_compute_rates():
    raw = bp._empty_raw()
    raw.update(views=40.0, active_users=20.0, engagement_seconds=1000.0,
               engaged_weight=24.0, plan_clicks=3.0, coaching_clicks=1.0)
    raw["events"]["article_deep_read"] = 10.0
    m = bp.window_metrics(raw, 4)
    assert m["views_per_day"] == 10.0
    assert m["active_users_per_day"] == 5.0
    assert m["avg_engagement_seconds"] == 50.0
    assert m["engagement_rate"] == 0.6
    assert m["deep_read_rate"] == 0.25
    assert m["events_per_day"]["article_deep_read"] == 2.5
    assert (m["plan_clicks"], m["coaching_clicks"]) == (3, 1)


def test_zero_view_page_has_null_ratios():
    m = bp.window_metrics(None, 30)
    assert m["views"] == 0 and m["views_per_day"] == 0.0
    assert m["deep_read_rate"] is None and m["engagement_rate"] is None
    assert m["avg_engagement_seconds"] is None


def test_deltas_use_per_day_values():
    windows = bp.build_windows(date(2026, 10, 12))  # after = 4 days
    inv = {"/a-post/": {"title": "A", "type": "post"}}
    before = window_reports(pages=[(["/a-post/"], [300, 100, 6000, 0.5])],
                            events=[(["/a-post/", "article_deep_read"], [30])])
    after = window_reports(pages=[(["/a-post/"], [80, 40, 2000, 0.6])],
                           events=[(["/a-post/", "article_deep_read"], [16])])
    report = bp.build_report(inv, before, after, windows,
                             property_name="properties/1", mock=True)
    row = report["pages"][0]
    assert row["before"]["views_per_day"] == 10.0
    assert row["after"]["views_per_day"] == 20.0
    assert row["deltas"]["views_per_day"] == 10.0
    assert row["deltas"]["views_per_day_pct"] == 100.0
    assert row["deltas"]["deep_read_rate_pts"] == pytest.approx(0.2 - 0.1)
    assert row["deltas"]["engagement_rate_pts"] == pytest.approx(0.1)
    assert row["deltas"]["avg_engagement_seconds"] == -10.0


def test_unknown_blog_paths_are_added_and_non_content_ignored():
    windows = bp.build_windows(date(2026, 10, 12))
    after = window_reports(pages=[
        (["/blog/new-race-recap/"], [5, 5, 50, 0.5]),
        (["/blog/"], [100, 90, 100, 0.5]),
        (["/articles/"], [10, 9, 10, 0.5]),
        (["/race/unbound/"], [999, 9, 10, 0.5]),
    ])
    report = bp.build_report({}, window_reports(), after, windows,
                             property_name="properties/1", mock=True)
    assert [(r["path"], r["type"]) for r in report["pages"]] == [
        ("/blog/new-race-recap/", "recap")]


def test_missing_cta_breakdown_marks_clicks_unavailable():
    windows = bp.build_windows(date(2026, 10, 12))
    inv = {"/a-post/": {"title": "A", "type": "post"}}
    reports = window_reports(pages=[(["/a-post/"], [10, 5, 100, 0.5])])
    reports["cta"] = None
    report = bp.build_report(inv, reports, reports, windows,
                             property_name="properties/1", mock=False,
                             warnings=["x"])
    assert report["pages"][0]["after"]["plan_clicks"] is None
    assert report["totals"]["after"]["plan_clicks"] is None
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
    def __init__(self, fail_cta=False):
        self.calls = []
        self.fail_cta = fail_cta

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        dims = [d["name"] for d in json["dimensions"]]
        if self.fail_cta and "customEvent:cta_name" in dims:
            return FakeResponse({"error": {"status": "INVALID_ARGUMENT"}}, 400)
        return FakeResponse(report_body(dims, [m["name"] for m in json["metrics"]], []))


def test_fetch_window_posts_three_reports_to_property():
    session = FakeSession()
    w = bp.build_windows(date(2026, 10, 12))["after"]
    reports, warnings = bp.fetch_window(session, "properties/42", w, ["/a/"])
    assert set(reports) == {"pages", "events", "cta"} and warnings == []
    assert all(url.endswith("/properties/42:runReport") for url, _ in session.calls)
    assert len(session.calls) == 3


def test_fetch_window_degrades_when_cta_dimension_fails():
    w = bp.build_windows(date(2026, 10, 12))["after"]
    reports, warnings = bp.fetch_window(FakeSession(fail_cta=True), "properties/42", w, [])
    assert reports["cta"] is None
    assert len(warnings) == 1 and "HTTP 400" in warnings[0]


def test_run_live_path_uses_session_factory(tmp_path):
    creds = tmp_path / "c.json"
    creds.write_text("{}")
    session = FakeSession()
    report = bp.run(end=date(2026, 10, 12), mock=False, property_value="42",
                    credentials=creds, session_factory=lambda p: session)
    assert report["property"] == "properties/42" and report["mock"] is False
    assert len(session.calls) == 6  # 3 reports x 2 windows
    assert {r["type"] for r in report["pages"]} >= {"essay", "post"}


def test_run_requires_credentials_without_mock():
    with pytest.raises(bp.Ga4Error):
        bp.run(end=date(2026, 10, 12), mock=False, property_value=None,
               credentials=None)


# ── End to end (mock) ────────────────────────────────────────────────────

def test_cli_mock_writes_json_and_markdown(tmp_path):
    assert bp.main(["--mock", "--end-date", "2026-10-12",
                    "--output-dir", str(tmp_path), "--stem", "snap"]) == 0
    data = json.loads((tmp_path / "snap.json").read_text())
    md = (tmp_path / "snap.md").read_text()
    assert data["mock"] is True
    assert data["windows"]["after"]["days"] == 4
    inv = bp.load_inventory()
    paths = {r["path"] for r in data["pages"]}
    assert set(inv) <= paths
    row = data["pages"][0]
    assert {"path", "title", "type", "before", "after", "deltas"} <= set(row)
    for key in ("views", "active_users", "avg_engagement_seconds",
                "engagement_rate", "events", "deep_read_rate",
                "plan_clicks", "coaching_clicks"):
        assert key in row["after"]
    assert set(row["after"]["events"]) == set(bp.ARTICLE_EVENTS)
    assert data["totals"]["after"]["plan_clicks"] is not None
    for heading in ("## Totals", "## Top 10 by views", "## Top 10 by deep-read rate",
                    "## Biggest movers", "MOCK DATA"):
        assert heading in md


def test_cli_rejects_end_before_redesign(tmp_path):
    assert bp.main(["--mock", "--end-date", "2026-10-01",
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
    for line in text.splitlines():
        if "secrets." in line:
            assert "echo" not in line and "cat " not in line
    assert "chmod(0o600)" in text
