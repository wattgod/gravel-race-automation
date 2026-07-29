"""Contract tests for the deterministic weekly SEO update-candidates collector."""

from __future__ import annotations

import json
import subprocess as subprocess_module
from datetime import date, datetime, timedelta, timezone

import pytest

from scripts import daily_intel, seo_weekly as sw


# ── Fake GSC service ─────────────────────────────────────────────────────

class FakeGSCService:
    """Minimal stand-in for the googleapiclient searchconsole resource.

    `responses` maps (dimensions_tuple, startDate, endDate) -> list of pages
    (each page a list of row dicts), consumed in order by startRow.
    """

    def __init__(self, responses: dict):
        self._responses = responses
        self.calls: list[dict] = []

    def searchanalytics(self):
        return self

    def query(self, siteUrl, body):
        self._pending = body
        return self

    def execute(self):
        body = self._pending
        self.calls.append(dict(body))
        dims = tuple(body.get("dimensions", []))
        key = (dims, body["startDate"], body["endDate"])
        pages = self._responses.get(key, [[]])
        start_row = body.get("startRow", 0)
        index = start_row // sw.PAGE_SIZE
        rows = pages[index] if index < len(pages) else []
        return {"rows": rows}


class FailingGSCService(FakeGSCService):
    """Raises for one specific pull key; used for the API-error contract."""

    def __init__(self, responses: dict, fail_key: tuple):
        super().__init__(responses)
        self.fail_key = fail_key

    def execute(self):
        body = self._pending
        dims = tuple(body.get("dimensions", []))
        key = (dims, body["startDate"], body["endDate"])
        if key == self.fail_key:
            raise RuntimeError("GSC API error")
        return super().execute()


def _probe_key(run_date: date) -> tuple:
    start = (run_date - timedelta(days=13)).isoformat()
    return (("date",), start, run_date.isoformat())


def _base_responses(run_date: date, boundary: date):
    """A complete, empty-rows response set for the probe + all 8 pulls."""
    current, prior = sw.compute_windows(boundary)
    responses = {
        _probe_key(run_date): [[{"keys": [boundary.isoformat()]}]],
        ((), current["start"], current["end"]): [[]],
        (("query",), current["start"], current["end"]): [[]],
        (("query", "page"), current["start"], current["end"]): [[]],
        (("page",), current["start"], current["end"]): [[]],
        ((), prior["start"], prior["end"]): [[]],
        (("query",), prior["start"], prior["end"]): [[]],
        (("query", "page"), prior["start"], prior["end"]): [[]],
        (("page",), prior["start"], prior["end"]): [[]],
    }
    return current, prior, responses


# ── Pagination ───────────────────────────────────────────────────────────

def test_paginated_query_loops_until_short_page_and_counts_requests(monkeypatch):
    monkeypatch.setattr(sw, "PAGE_SIZE", 2)
    pages = [
        [{"keys": ["a"], "clicks": 1}, {"keys": ["b"], "clicks": 2}],
        [{"keys": ["c"], "clicks": 3}, {"keys": ["d"], "clicks": 4}],
        [{"keys": ["e"], "clicks": 5}],
    ]
    service = FakeGSCService({(("query",), "2026-06-29", "2026-07-26"): pages})

    rows, requests = sw._paginated_query(
        service, sw.SITE_URL, "2026-06-29", "2026-07-26", ["query"])

    assert requests == 3
    assert [r["keys"][0] for r in rows] == ["a", "b", "c", "d", "e"]
    assert [call["startRow"] for call in service.calls] == [0, 2, 4]


def test_collect_weekly_records_per_pull_rows_and_requests(monkeypatch):
    monkeypatch.setattr(sw, "PAGE_SIZE", 2)
    run_date = date(2026, 7, 27)
    boundary = date(2026, 7, 26)
    current, prior, responses = _base_responses(run_date, boundary)
    # Current query+page pull spans two pages of the (patched) page size.
    responses[(("query", "page"), current["start"], current["end"])] = [
        [
            {"keys": ["q1", "https://gravelgodcycling.com/race/a"],
             "clicks": 1, "impressions": 20, "ctr": 0.05, "position": 5.0},
            {"keys": ["q2", "https://gravelgodcycling.com/race/b"],
             "clicks": 1, "impressions": 20, "ctr": 0.05, "position": 5.0},
        ],
        [
            {"keys": ["q3", "https://gravelgodcycling.com/race/c"],
             "clicks": 1, "impressions": 20, "ctr": 0.05, "position": 5.0},
        ],
    ]
    service = FakeGSCService(responses)

    artifact = sw.collect_weekly(
        now=datetime(2026, 7, 27, 11, 20, tzinfo=timezone.utc), service=service)

    qp_pull = next(
        p for p in artifact["pulls"]
        if p["dimensions"] == ["query", "page"] and p["window"] == "current")
    assert qp_pull == {
        "dimensions": ["query", "page"], "window": "current", "rows": 3, "requests": 2}
    assert len(artifact["pulls"]) == 8


# ── API error / incomplete pull → no artifact ───────────────────────────

def test_api_error_raises_and_writes_no_artifact(tmp_path, monkeypatch):
    run_date = date(2026, 7, 27)
    boundary = date(2026, 7, 26)
    _, _, responses = _base_responses(run_date, boundary)
    fail_key = (("page",), *sw.compute_windows(boundary)[0].values())
    service = FailingGSCService(responses, fail_key)

    with pytest.raises(RuntimeError):
        sw.collect_weekly(
            now=datetime(2026, 7, 27, 11, 20, tzinfo=timezone.utc),
            service=service, output_dir=tmp_path)

    assert list(tmp_path.glob("seo-weekly-*.json")) == []


def test_main_exits_1_and_writes_nothing_on_api_error(tmp_path, monkeypatch, capsys):
    run_date = date(2026, 7, 27)
    boundary = date(2026, 7, 26)
    _, _, responses = _base_responses(run_date, boundary)
    fail_key = _probe_key(run_date)
    service = FailingGSCService(responses, fail_key)

    monkeypatch.setattr(sw, "get_gsc_service", lambda: service)
    monkeypatch.setattr(
        "sys.argv",
        ["seo_weekly.py", "--date", run_date.isoformat(),
         "--output-dir", str(tmp_path)])

    exit_code = sw.main()

    assert exit_code == 1
    assert list(tmp_path.glob("seo-weekly-*.json")) == []
    assert "ERROR" in capsys.readouterr().err


def test_probe_with_no_rows_hard_fails():
    service = FakeGSCService({})
    with pytest.raises(RuntimeError, match="no rows"):
        sw.probe_data_boundary(service, date(2026, 7, 27))


# ── expected_ctr piecewise-linear interpolation ─────────────────────────

@pytest.mark.parametrize(("position", "expected"), [
    (1, 0.28), (2, 0.15), (3, 0.10), (4, 0.075), (5, 0.06), (6, 0.045),
    (7, 0.035), (8, 0.03), (9, 0.025), (10, 0.02), (12, 0.02), (20, 0.01),
])
def test_expected_ctr_at_anchors(position, expected):
    assert sw.expected_ctr(position) == pytest.approx(expected)


def test_expected_ctr_midpoints_interpolate_linearly():
    assert sw.expected_ctr(1.5) == pytest.approx(0.28 + 0.5 * (0.15 - 0.28))
    assert sw.expected_ctr(11) == pytest.approx(0.02)  # flat between 10 and 12
    assert sw.expected_ctr(16) == pytest.approx(0.02 + 0.5 * (0.01 - 0.02))


def test_expected_ctr_out_of_range_clamps_to_endpoints():
    assert sw.expected_ctr(0.2) == pytest.approx(0.28)
    assert sw.expected_ctr(50) == pytest.approx(0.01)


# ── URL normalization ────────────────────────────────────────────────────

@pytest.mark.parametrize(("raw", "path"), [
    ("https://gravelgodcycling.com/race/test", "/race/test/"),
    ("https://www.gravelgodcycling.com/race/test/", "/race/test/"),
    ("https://gravelgodcycling.com/", "/"),
    ("https://gravelgodcycling.com", "/"),
    ("https://gravelgodcycling.com/race/test/?utm=1#frag", "/race/test/"),
])
def test_normalize_page_url_canonical_cases(raw, path):
    normalized, host_key = sw.normalize_page_url(raw)
    assert normalized == path
    assert host_key is None


@pytest.mark.parametrize(("raw", "host_key"), [
    ("http://gravelgodcycling.com/race/test/", "http://gravelgodcycling.com"),
    ("https://staging.gravelgodcycling.com/race/test/",
     "https://staging.gravelgodcycling.com"),
])
def test_normalize_page_url_noncanonical_cases(raw, host_key):
    normalized, key = sw.normalize_page_url(raw)
    assert normalized is None
    assert key == host_key


# ── Bucket construction helpers ──────────────────────────────────────────

def _qp_row(query, page, *, clicks, impressions, ctr, position):
    return {
        "query": query, "page": page, "clicks": clicks,
        "impressions": impressions, "ctr": ctr, "position": position,
    }


def _query_row(query, *, clicks, impressions, ctr, position):
    return {
        "query": query, "clicks": clicks, "impressions": impressions,
        "ctr": ctr, "position": position,
    }


def _page_row(page, *, clicks, impressions, ctr, position):
    return {
        "page": page, "clicks": clicks, "impressions": impressions,
        "ctr": ctr, "position": position,
    }


def _empty_buckets(**overrides):
    args = dict(
        current_qp=[], prior_qp=[], current_page=[], prior_page=[],
        current_query=[])
    args.update(overrides)
    return sw.build_buckets(**args)


# ── striking_distance edges ──────────────────────────────────────────────

def test_striking_distance_include_exclude_edges():
    included = _qp_row(
        "q", "/race/a/", clicks=1, impressions=30, ctr=0.01, position=4.0)
    excluded_low_position = _qp_row(
        "q", "/race/b/", clicks=1, impressions=30, ctr=0.01, position=3.9)
    included_high_position = _qp_row(
        "q", "/race/c/", clicks=1, impressions=30, ctr=0.01, position=20.0)
    excluded_high_position = _qp_row(
        "q", "/race/d/", clicks=1, impressions=30, ctr=0.01, position=20.1)
    excluded_low_impressions = _qp_row(
        "q", "/race/e/", clicks=1, impressions=29, ctr=0.01, position=6.0)

    buckets = _empty_buckets(current_qp=[
        included, excluded_low_position, included_high_position,
        excluded_high_position, excluded_low_impressions,
    ])

    pages = {e["page"] for e in buckets["striking_distance"]}
    assert pages == {"/race/a/", "/race/c/"}


def test_striking_distance_target_position_split_at_10():
    at_ten = _qp_row(
        "q", "/race/at-ten/", clicks=1, impressions=30, ctr=0.01, position=10.0)
    above_ten = _qp_row(
        "q", "/race/above-ten/", clicks=1, impressions=30, ctr=0.01, position=10.1)

    buckets = _empty_buckets(current_qp=[at_ten, above_ten])
    by_page = {e["page"]: e for e in buckets["striking_distance"]}
    assert by_page["/race/at-ten/"]["score"] == pytest.approx(
        30 * max(0.0, sw.expected_ctr(3) - 0.01))
    assert by_page["/race/above-ten/"]["score"] == pytest.approx(
        30 * max(0.0, sw.expected_ctr(8) - 0.01))


# ── ctr_underperformers edges ────────────────────────────────────────────

def test_ctr_underperformers_include_exclude_edges():
    exp_at_12 = sw.expected_ctr(12)
    included = _qp_row(
        "q", "/race/a/", clicks=1, impressions=50, ctr=0.4 * exp_at_12 - 0.0001,
        position=12.0)
    excluded_at_threshold = _qp_row(
        "q", "/race/b/", clicks=1, impressions=50, ctr=0.4 * exp_at_12,
        position=12.0)
    excluded_position = _qp_row(
        "q", "/race/c/", clicks=1, impressions=50, ctr=0.0001, position=12.1)
    excluded_impressions = _qp_row(
        "q", "/race/d/", clicks=1, impressions=49, ctr=0.0001, position=12.0)

    buckets = _empty_buckets(current_qp=[
        included, excluded_at_threshold, excluded_position, excluded_impressions,
    ])

    pages = {e["page"] for e in buckets["ctr_underperformers"]}
    assert pages == {"/race/a/"}


# ── decliners floors ──────────────────────────────────────────────────────

def test_decliners_clicks_dropped_floor_boundaries():
    # prior_clicks == 10, drop exactly 40% -> qualifies.
    current_page = [_page_row(
        "/race/a/", clicks=6, impressions=100, ctr=0.06, position=6.0)]
    prior_page = [_page_row(
        "/race/a/", clicks=10, impressions=100, ctr=0.10, position=6.0)]
    buckets = _empty_buckets(current_page=current_page, prior_page=prior_page)
    assert {e["page"] for e in buckets["decliners"]} == {"/race/a/"}


def test_decliners_below_prior_clicks_floor_does_not_qualify_on_clicks_alone():
    # prior_clicks == 9 (below the >=10 floor), even a 100% drop should not
    # qualify via the clicks-dropped path; position is unchanged so the
    # position-worsened path also does not fire.
    current_page = [_page_row(
        "/race/a/", clicks=0, impressions=100, ctr=0.0, position=6.0)]
    prior_page = [_page_row(
        "/race/a/", clicks=9, impressions=100, ctr=0.09, position=6.0)]
    buckets = _empty_buckets(current_page=current_page, prior_page=prior_page)
    assert buckets["decliners"] == []


def test_decliners_position_worsened_floor_boundaries():
    # Exactly 3.0 worse, impressions exactly 50 in both windows -> qualifies.
    current_page = [_page_row(
        "/race/a/", clicks=5, impressions=50, ctr=0.1, position=9.0)]
    prior_page = [_page_row(
        "/race/a/", clicks=5, impressions=50, ctr=0.1, position=6.0)]
    buckets = _empty_buckets(current_page=current_page, prior_page=prior_page)
    assert {e["page"] for e in buckets["decliners"]} == {"/race/a/"}

    # 2.9 worse -> excluded.
    current_page2 = [_page_row(
        "/race/b/", clicks=5, impressions=50, ctr=0.1, position=8.9)]
    prior_page2 = [_page_row(
        "/race/b/", clicks=5, impressions=50, ctr=0.1, position=6.0)]
    buckets2 = _empty_buckets(current_page=current_page2, prior_page=prior_page2)
    assert buckets2["decliners"] == []

    # 3.0 worse but impressions only 49 in current window -> excluded.
    current_page3 = [_page_row(
        "/race/c/", clicks=5, impressions=49, ctr=0.1, position=9.0)]
    prior_page3 = [_page_row(
        "/race/c/", clicks=5, impressions=50, ctr=0.1, position=6.0)]
    buckets3 = _empty_buckets(current_page=current_page3, prior_page=prior_page3)
    assert buckets3["decliners"] == []


def test_decliners_requires_page_present_in_both_windows():
    current_page = [_page_row(
        "/race/new/", clicks=1, impressions=100, ctr=0.01, position=6.0)]
    buckets = _empty_buckets(current_page=current_page, prior_page=[])
    assert buckets["decliners"] == []


# ── content_gaps edges + duplicate targets ──────────────────────────────

def test_content_gaps_include_exclude_edges():
    below_floor = _query_row(
        "no impressions", clicks=0, impressions=49, ctr=0.0, position=9.0)
    homepage_gap = _query_row(
        "homepage query", clicks=1, impressions=50, ctr=0.02, position=9.0)
    hub_gap = _query_row(
        "hub query", clicks=1, impressions=50, ctr=0.02, position=9.0)
    absent_gap = _query_row(
        "absent query", clicks=1, impressions=50, ctr=0.02, position=9.0)
    real_page_query = _query_row(
        "covered query", clicks=10, impressions=100, ctr=0.10, position=3.0)

    current_qp = [
        _qp_row("homepage query", "/", clicks=1, impressions=50, ctr=0.02, position=9.0),
        _qp_row("hub query", "/gravel-race-search/", clicks=1, impressions=50,
                ctr=0.02, position=9.0),
        _qp_row("covered query", "/race/real/", clicks=10, impressions=100,
                ctr=0.10, position=3.0),
    ]
    buckets = _empty_buckets(
        current_query=[below_floor, homepage_gap, hub_gap, absent_gap, real_page_query],
        current_qp=current_qp,
    )
    queries = {e["query"] for e in buckets["content_gaps"]}
    assert queries == {"homepage query", "hub query", "absent query"}


def test_content_gaps_duplicate_recommended_targets_stay_distinct():
    # Two different queries slugify to the same recommended_target_path;
    # dedupe is by query, so both must survive independently.
    row_a = _query_row("Foo Bar!", clicks=1, impressions=50, ctr=0.02, position=9.0)
    row_b = _query_row("foo-bar", clicks=2, impressions=60, ctr=0.02, position=9.0)

    buckets = _empty_buckets(current_query=[row_a, row_b])
    assert len(buckets["content_gaps"]) == 2
    targets = {e["recommended_target_path"] for e in buckets["content_gaps"]}
    assert targets == {"/articles/foo-bar/"}
    queries = {e["query"] for e in buckets["content_gaps"]}
    assert queries == {"Foo Bar!", "foo-bar"}

    top_candidates, _ = sw._rank_top_candidates(buckets, set())
    assert len(top_candidates) == 2
    assert {c["query"] for c in top_candidates} == {"Foo Bar!", "foo-bar"}


# ── dedupe / supporting_queries / combined_upside / tie-break ──────────

def test_dedupe_keeps_max_score_and_attaches_supporting_queries():
    page = "/race/example/"
    lower = _qp_row(
        "alpha query", page, clicks=5, impressions=100, ctr=0.05, position=6.0)
    higher = _qp_row(
        "beta query", page, clicks=4, impressions=200, ctr=0.02, position=6.0)

    buckets = _empty_buckets(current_qp=[lower, higher])
    top_candidates, cooldown_excluded = sw._rank_top_candidates(buckets, set())

    assert cooldown_excluded == []
    assert len(top_candidates) == 1
    candidate = top_candidates[0]
    assert candidate["page"] == page
    assert candidate["query"] == "beta query"  # higher score wins
    assert candidate["score"] == pytest.approx(200 * (sw.expected_ctr(3) - 0.02))
    assert candidate["supporting_queries"] == [{
        "query": "alpha query", "clicks": 5, "impressions": 100,
        "ctr": 0.05, "position": 6.0,
    }]
    assert candidate["combined_upside"] == pytest.approx(
        candidate["score"] + 100 * (sw.expected_ctr(3) - 0.05))
    assert candidate["rank"] == 1


def test_deterministic_tie_break_by_page_ascending():
    entries = [
        {"page": "/race/zulu/", "query": "q1", "clicks": 1, "impressions": 50,
         "ctr": 0.01, "position": 6.0, "score": 10.0, "reason": "r1"},
        {"page": "/race/alpha/", "query": "q2", "clicks": 1, "impressions": 50,
         "ctr": 0.01, "position": 6.0, "score": 10.0, "reason": "r2"},
    ]
    buckets = {
        "striking_distance": entries, "ctr_underperformers": [],
        "decliners": [], "content_gaps": [],
    }
    top_candidates, _ = sw._rank_top_candidates(buckets, set())
    assert [c["page"] for c in top_candidates] == ["/race/alpha/", "/race/zulu/"]


def test_empty_and_fewer_than_five_top_candidates():
    empty_buckets = _empty_buckets()
    top_candidates, cooldown_excluded = sw._rank_top_candidates(empty_buckets, set())
    assert top_candidates == []
    assert cooldown_excluded == []

    entries = [
        {"page": f"/race/{i}/", "query": f"q{i}", "clicks": 1, "impressions": 50,
         "ctr": 0.01, "position": 6.0, "score": float(10 - i), "reason": "r"}
        for i in range(3)
    ]
    buckets = {
        "striking_distance": entries, "ctr_underperformers": [],
        "decliners": [], "content_gaps": [],
    }
    top_candidates, _ = sw._rank_top_candidates(buckets, set())
    assert len(top_candidates) == 3
    assert [c["rank"] for c in top_candidates] == [1, 2, 3]


# ── cooldown exclusion + malformed log lines ────────────────────────────

def test_cooldown_excludes_recent_applied_pages_and_skips_malformed_lines(tmp_path):
    boundary = date(2026, 7, 26)
    log_path = tmp_path / "updates-log.jsonl"
    log_path.write_text("\n".join([
        json.dumps({
            "date": "2026-07-10", "page": "/race/recent/", "query": "q",
            "bucket": "striking_distance", "action": "improve_ranking",
            "artifact": "seo-weekly-2026-07-05.json", "status": "applied",
        }),
        json.dumps({
            "date": "2026-06-01", "page": "/race/old/", "query": "q",
            "bucket": "decliners", "action": "refresh_content",
            "artifact": "seo-weekly-2026-05-30.json", "status": "applied",
        }),
        json.dumps({
            "date": "2026-07-20", "page": "/race/skipped/", "query": "q",
            "bucket": "content_gaps", "action": "create_or_link_content",
            "artifact": "seo-weekly-2026-07-19.json", "status": "skipped",
        }),
        "{not valid json",
        "",
    ]))

    pages, warnings = sw._load_cooldown_pages(boundary, tmp_path)

    assert pages == {"/race/recent/"}
    assert len(warnings) == 1
    assert "malformed" in warnings[0]


def test_cooldown_missing_log_file_is_empty(tmp_path):
    pages, warnings = sw._load_cooldown_pages(date(2026, 7, 26), tmp_path)
    assert pages == set()
    assert warnings == []


def test_cooldown_excludes_from_top_candidates_but_buckets_keep_the_entry():
    entry = {
        "page": "/race/cooling/", "query": "q", "clicks": 1, "impressions": 50,
        "ctr": 0.01, "position": 6.0, "score": 10.0, "reason": "r",
    }
    buckets = {
        "striking_distance": [entry], "ctr_underperformers": [],
        "decliners": [], "content_gaps": [],
    }
    top_candidates, cooldown_excluded = sw._rank_top_candidates(
        buckets, {"/race/cooling/"})

    assert top_candidates == []
    assert cooldown_excluded == ["/race/cooling/"]
    assert buckets["striking_distance"] == [entry]  # buckets remain untouched


# ── Artifact validation ──────────────────────────────────────────────────

def _valid_artifact(boundary_str: str = "2026-07-26") -> dict:
    boundary = date.fromisoformat(boundary_str)
    current, prior = sw.compute_windows(boundary)
    return {
        "schema_version": 1,
        "score_version": 1,
        "generated_at_utc": f"{boundary_str}T11:20:00Z",
        "site": sw.SITE_URL,
        "data_boundary": boundary_str,
        "current_window": current,
        "prior_window": prior,
        "overall": {
            "clicks": 100, "impressions": 5000, "ctr": 0.02, "position": 8.0,
            "prior": {"clicks": 90, "impressions": 4800, "ctr": 0.0187, "position": 8.5},
        },
        "pulls": [
            {"dimensions": [], "window": "current", "rows": 1, "requests": 1},
            {"dimensions": ["query"], "window": "current", "rows": 0, "requests": 1},
            {"dimensions": ["query", "page"], "window": "current", "rows": 0, "requests": 1},
            {"dimensions": ["page"], "window": "current", "rows": 0, "requests": 1},
            {"dimensions": [], "window": "prior", "rows": 1, "requests": 1},
            {"dimensions": ["query"], "window": "prior", "rows": 0, "requests": 1},
            {"dimensions": ["query", "page"], "window": "prior", "rows": 0, "requests": 1},
            {"dimensions": ["page"], "window": "prior", "rows": 0, "requests": 1},
        ],
        "noncanonical": {},
        "cooldown_excluded": [],
        "buckets": {
            "striking_distance": [], "ctr_underperformers": [],
            "decliners": [], "content_gaps": [],
        },
        "top_candidates": [],
    }


def test_validate_artifact_good():
    assert sw.validate_artifact(_valid_artifact()) == []


def test_validate_artifact_missing_key():
    artifact = _valid_artifact()
    del artifact["cooldown_excluded"]
    errors = sw.validate_artifact(artifact)
    assert any("missing required key: cooldown_excluded" in e for e in errors)


def test_validate_artifact_future_generated_at():
    artifact = _valid_artifact()
    artifact["generated_at_utc"] = "2099-01-01T00:00:00Z"
    errors = sw.validate_artifact(artifact)
    assert any("future" in e for e in errors)


def test_validate_artifact_bad_window():
    artifact = _valid_artifact()
    artifact["current_window"] = {"start": "2020-01-01", "end": "2020-01-28"}
    errors = sw.validate_artifact(artifact)
    assert any("current_window does not match data_boundary" in e for e in errors)


def test_validate_artifact_ctr_out_of_range_100x_unit_error():
    artifact = _valid_artifact()
    # A 100x unit error (percentage stored instead of fraction) must fail.
    artifact["overall"]["ctr"] = 2.1
    errors = sw.validate_artifact(artifact)
    assert any("fraction" in e for e in errors)


def test_validate_artifact_ctr_out_of_range_in_bucket_entry():
    artifact = _valid_artifact()
    artifact["buckets"]["striking_distance"] = [{
        "page": "/race/a/", "query": "q", "clicks": 1, "impressions": 50,
        "ctr": 21.0, "position": 6.0, "score": 1.0, "reason": "r",
    }]
    errors = sw.validate_artifact(artifact)
    assert any("ctr outside" in e for e in errors)


def test_validate_artifact_filename_mismatch():
    artifact = _valid_artifact()
    errors = sw.validate_artifact(
        artifact, path=__import__("pathlib").Path("/tmp/seo-weekly-2020-01-01.json"))
    assert any("does not match" in e for e in errors)


def test_validate_artifact_require_all_ok_needs_eight_complete_pulls():
    artifact = _valid_artifact()
    artifact["pulls"] = artifact["pulls"][:7]
    errors = sw.validate_artifact(artifact, require_all_ok=True)
    assert any("exactly 8 entries" in e for e in errors)
    assert sw.validate_artifact(artifact, require_all_ok=False) == []


def test_write_artifact_round_trip(tmp_path):
    artifact = _valid_artifact()
    path = sw.write_artifact(artifact, tmp_path)
    assert path.name == "seo-weekly-2026-07-26.json"
    loaded = json.loads(path.read_text())
    assert loaded == artifact
    assert sw.validate_artifact(loaded, path=path) == []


# ── CLI --validate-latest / --require-all-ok / --date ───────────────────

def test_cli_validate_latest_on_good_artifact(tmp_path, monkeypatch, capsys):
    artifact = _valid_artifact()
    sw.write_artifact(artifact, tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        ["seo_weekly.py", "--validate-latest", "--require-all-ok",
         "--output-dir", str(tmp_path)])
    assert sw.main() == 0
    assert "valid artifact" in capsys.readouterr().out


def test_cli_validate_latest_no_artifacts_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        ["seo_weekly.py", "--validate-latest", "--output-dir", str(tmp_path)])
    assert sw.main() == 1
    assert "no SEO artifacts found" in capsys.readouterr().err


# ── daily_intel.collect_seo states ──────────────────────────────────────

def _write_seo_artifact(directory, artifact):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"seo-weekly-{artifact['data_boundary']}.json"
    path.write_text(json.dumps(artifact))
    return path


def test_collect_seo_missing_state_is_ok_and_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_intel, "SEO_DIR", tmp_path)
    result = daily_intel.collect_seo(today=date(2026, 7, 27))
    assert result == {"state": "missing", "ok": True}


def test_collect_seo_ok_state_and_render_with_candidates(tmp_path, monkeypatch):
    artifact = _valid_artifact("2026-07-26")
    artifact["overall"]["clicks"] = 120
    artifact["overall"]["prior"]["clicks"] = 100
    artifact["top_candidates"] = [{
        "rank": 1, "bucket": "striking_distance", "action": "improve_ranking",
        "target_path": "/race/x/", "query": "some query", "page": "/race/x/",
        "source_hint": "race-data/x.json", "reason": "push it up",
        "clicks": 12, "impressions": 480, "ctr": 0.021, "position": 6.2,
        "score": 9.0, "supporting_queries": [], "combined_upside": 9.0,
    }]
    _write_seo_artifact(tmp_path, artifact)
    monkeypatch.setattr(daily_intel, "SEO_DIR", tmp_path)

    result = daily_intel.collect_seo(today=date(2026, 7, 27))
    assert result["state"] == "ok"
    assert result["overall"]["clicks_delta"] == 20

    report = daily_intel.render_report({"seo": result})
    assert "## SEO (WEEKLY)" in report
    assert '#1 [striking_distance] /race/x/ — "some query" pos 6.2, 480 impr, CTR 2.1% — push it up' in report
    assert "Run /seo-updates to draft these." in report


def test_collect_seo_ok_state_empty_candidates_render_text(tmp_path, monkeypatch):
    artifact = _valid_artifact("2026-07-26")
    _write_seo_artifact(tmp_path, artifact)
    monkeypatch.setattr(daily_intel, "SEO_DIR", tmp_path)

    result = daily_intel.collect_seo(today=date(2026, 7, 27))
    report = daily_intel.render_report({"seo": result})
    assert "no qualifying candidates this week" in report


def test_collect_seo_stale_state_produces_one_broken_line(tmp_path, monkeypatch):
    artifact = _valid_artifact("2026-07-01")
    _write_seo_artifact(tmp_path, artifact)
    monkeypatch.setattr(daily_intel, "SEO_DIR", tmp_path)

    result = daily_intel.collect_seo(today=date(2026, 7, 20))
    assert result["state"] == "stale"
    report = daily_intel.render_report({"seo": result})
    assert "## SEO (WEEKLY)" not in report
    assert report.count("SEO weekly artifact stale (19 days)") == 1


def test_collect_seo_invalid_json_never_raises(tmp_path, monkeypatch):
    path = tmp_path / "seo-weekly-2026-07-26.json"
    tmp_path.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json")
    monkeypatch.setattr(daily_intel, "SEO_DIR", tmp_path)

    result = daily_intel.collect_seo(today=date(2026, 7, 27))
    assert result["state"] == "invalid"
    assert result["ok"] is False
    assert "SEO weekly artifact invalid" in result["error"]


def test_collect_seo_future_generated_at_is_invalid(tmp_path, monkeypatch):
    artifact = _valid_artifact("2026-07-26")
    artifact["generated_at_utc"] = "2026-08-01T00:00:00Z"
    _write_seo_artifact(tmp_path, artifact)
    monkeypatch.setattr(daily_intel, "SEO_DIR", tmp_path)

    result = daily_intel.collect_seo(today=date(2026, 7, 27))
    assert result["state"] == "invalid"


def test_collect_workflows_includes_seo_weekly(monkeypatch):
    calls = []

    class FakeCompleted:
        stdout = "[]"

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return FakeCompleted()

    monkeypatch.setattr(subprocess_module, "run", fake_run)
    daily_intel.collect_workflows()

    workflows = [cmd[cmd.index("--workflow") + 1] for cmd in calls]
    assert "seo-weekly.yml" in workflows
