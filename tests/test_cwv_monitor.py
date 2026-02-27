"""Tests for scripts/cwv_monitor.py — CWV monitoring, alerting, and snapshot structure."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from cwv_monitor import (
    ALERT_THRESHOLDS,
    MONITORED_URLS,
    SNAPSHOT_DIR,
    THRESHOLDS,
    PSI_API_URL,
    check_alerts,
    extract_metrics,
    grade_metric,
    run_snapshot,
    save_snapshot,
    load_latest_snapshot,
    list_snapshots,
    print_report,
    _build_summary,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_psi_response(
    lcp=1200, cls=0.05, fcp=900, ttfb=300, speed_index=2000, perf_score=0.85,
    crux_inp=120, crux_fid=50, crux_lcp=None, crux_cls=None,
):
    """Build a realistic PSI API response for testing."""
    resp = {
        "lighthouseResult": {
            "audits": {
                "largest-contentful-paint": {"numericValue": lcp},
                "cumulative-layout-shift": {"numericValue": cls},
                "first-contentful-paint": {"numericValue": fcp},
                "server-response-time": {"numericValue": ttfb},
                "speed-index": {"numericValue": speed_index},
            },
            "categories": {
                "performance": {"score": perf_score},
            },
        },
        "loadingExperience": {
            "metrics": {},
        },
    }
    crux = resp["loadingExperience"]["metrics"]
    if crux_inp is not None:
        crux["INTERACTION_TO_NEXT_PAINT"] = {"percentile": crux_inp}
    if crux_fid is not None:
        crux["FIRST_INPUT_DELAY_MS"] = {"percentile": crux_fid}
    if crux_lcp is not None:
        crux["LARGEST_CONTENTFUL_PAINT_MS"] = {"percentile": crux_lcp}
    if crux_cls is not None:
        crux["CUMULATIVE_LAYOUT_SHIFT_SCORE"] = {"percentile": crux_cls}
    return resp


def _make_snapshot(results=None):
    """Build a minimal snapshot dict."""
    if results is None:
        results = [
            {
                "url": "https://gravelgodcycling.com/",
                "label": "Homepage",
                "strategy": "mobile",
                "metrics": {
                    "lcp_ms": 1800,
                    "cls": 0.04,
                    "inp_ms": 100,
                    "fid_ms": 30,
                    "fcp_ms": 900,
                    "ttfb_ms": 400,
                    "speed_index_ms": 2200,
                    "performance_score": 88,
                },
                "grades": {
                    "lcp_ms": "PASS",
                    "cls": "PASS",
                    "inp_ms": "PASS",
                    "fid_ms": "PASS",
                    "fcp_ms": "PASS",
                    "ttfb_ms": "PASS",
                    "speed_index_ms": "PASS",
                },
            },
        ]
    snapshot = {
        "timestamp": "2026-02-26T07:00:00Z",
        "strategies": ["mobile"],
        "results": results,
        "summary": {},
    }
    _build_summary(snapshot)
    return snapshot


# ---------------------------------------------------------------------------
# URL list
# ---------------------------------------------------------------------------

class TestMonitoredURLs:
    """Verify the monitored URL list is correct and complete."""

    EXPECTED_URLS = [
        "https://gravelgodcycling.com/",
        "https://gravelgodcycling.com/gravel-races/",
        "https://gravelgodcycling.com/race/unbound-200/",
        "https://gravelgodcycling.com/race/barry-roubaix/",
        "https://gravelgodcycling.com/race/big-sugar/",
        "https://gravelgodcycling.com/race/3-state-3-mountain-challenge/",
        "https://gravelgodcycling.com/coaching/",
    ]

    def test_url_count(self):
        assert len(MONITORED_URLS) == 7

    def test_all_urls_present(self):
        urls = [e["url"] for e in MONITORED_URLS]
        for expected in self.EXPECTED_URLS:
            assert expected in urls, f"Missing URL: {expected}"

    def test_all_entries_have_label(self):
        for entry in MONITORED_URLS:
            assert "url" in entry
            assert "label" in entry
            assert len(entry["label"]) > 0

    def test_labels_are_unique(self):
        labels = [e["label"] for e in MONITORED_URLS]
        assert len(labels) == len(set(labels)), "Duplicate labels found"

    def test_homepage_is_first(self):
        assert MONITORED_URLS[0]["url"] == "https://gravelgodcycling.com/"

    def test_all_urls_are_https(self):
        for entry in MONITORED_URLS:
            assert entry["url"].startswith("https://"), f"Non-HTTPS URL: {entry['url']}"

    def test_all_urls_have_trailing_slash(self):
        for entry in MONITORED_URLS:
            assert entry["url"].endswith("/"), f"Missing trailing slash: {entry['url']}"

    def test_tier_coverage(self):
        """At least one race page per tier (T1-T4)."""
        labels = [e["label"] for e in MONITORED_URLS]
        assert "T1 Race" in labels
        assert "T2 Race" in labels
        assert "T3 Race" in labels
        assert "T4 Race" in labels


# ---------------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------------

class TestExtractMetrics:
    """Test metric extraction from PSI API responses."""

    def test_extracts_lab_metrics(self):
        resp = _make_psi_response(lcp=2400, cls=0.08, fcp=1200, ttfb=500, speed_index=3000)
        m = extract_metrics(resp)
        assert m["lcp_ms"] == 2400.0
        assert m["cls"] == 0.08
        assert m["fcp_ms"] == 1200.0
        assert m["ttfb_ms"] == 500.0
        assert m["speed_index_ms"] == 3000.0

    def test_extracts_performance_score(self):
        resp = _make_psi_response(perf_score=0.72)
        m = extract_metrics(resp)
        assert m["performance_score"] == 72

    def test_score_100(self):
        resp = _make_psi_response(perf_score=1.0)
        m = extract_metrics(resp)
        assert m["performance_score"] == 100

    def test_score_zero(self):
        resp = _make_psi_response(perf_score=0.0)
        m = extract_metrics(resp)
        assert m["performance_score"] == 0

    def test_extracts_crux_inp(self):
        resp = _make_psi_response(crux_inp=180)
        m = extract_metrics(resp)
        assert m["inp_ms"] == 180

    def test_extracts_crux_fid(self):
        resp = _make_psi_response(crux_fid=25)
        m = extract_metrics(resp)
        assert m["fid_ms"] == 25

    def test_crux_lcp_overrides_lab(self):
        """CrUX LCP (field data) takes priority over lab LCP."""
        resp = _make_psi_response(lcp=2000, crux_lcp=1800)
        m = extract_metrics(resp)
        assert m["lcp_ms"] == 1800

    def test_crux_cls_overrides_lab(self):
        """CrUX CLS (field data) takes priority over lab CLS."""
        resp = _make_psi_response(cls=0.12, crux_cls=5)
        m = extract_metrics(resp)
        assert m["cls"] == 0.05  # 5/100

    def test_handles_missing_audits(self):
        resp = {"lighthouseResult": {"audits": {}, "categories": {}}, "loadingExperience": {"metrics": {}}}
        m = extract_metrics(resp)
        assert m["lcp_ms"] is None
        assert m["cls"] is None
        assert m["fcp_ms"] is None
        assert m["performance_score"] is None

    def test_handles_empty_response(self):
        m = extract_metrics({})
        assert all(v is None for v in m.values())

    def test_handles_null_numeric_values(self):
        resp = _make_psi_response()
        resp["lighthouseResult"]["audits"]["largest-contentful-paint"]["numericValue"] = None
        m = extract_metrics(resp)
        # Lab LCP is None; CrUX LCP not set, so stays None
        # (but crux_lcp defaults to None in fixture, so LCP should be None)
        # Since crux_lcp is None in _make_psi_response default, LCP should be None
        assert m["lcp_ms"] is None

    def test_all_metric_keys_present(self):
        """Every extraction returns all expected keys."""
        m = extract_metrics({})
        expected_keys = {"lcp_ms", "cls", "inp_ms", "fid_ms", "fcp_ms", "ttfb_ms", "speed_index_ms", "performance_score"}
        assert set(m.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Grading
# ---------------------------------------------------------------------------

class TestGradeMetric:
    """Test pass/fail grading against Google thresholds."""

    def test_lcp_pass(self):
        assert grade_metric("lcp_ms", 2000) == "PASS"

    def test_lcp_fail(self):
        assert grade_metric("lcp_ms", 3000) == "FAIL"

    def test_lcp_exact_threshold_passes(self):
        assert grade_metric("lcp_ms", 2500) == "PASS"

    def test_cls_pass(self):
        assert grade_metric("cls", 0.05) == "PASS"

    def test_cls_fail(self):
        assert grade_metric("cls", 0.25) == "FAIL"

    def test_cls_exact_threshold_passes(self):
        assert grade_metric("cls", 0.1) == "PASS"

    def test_inp_pass(self):
        assert grade_metric("inp_ms", 100) == "PASS"

    def test_inp_fail(self):
        assert grade_metric("inp_ms", 500) == "FAIL"

    def test_fid_pass(self):
        assert grade_metric("fid_ms", 50) == "PASS"

    def test_fid_fail(self):
        assert grade_metric("fid_ms", 150) == "FAIL"

    def test_fcp_pass(self):
        assert grade_metric("fcp_ms", 1500) == "PASS"

    def test_fcp_fail(self):
        assert grade_metric("fcp_ms", 2000) == "FAIL"

    def test_ttfb_pass(self):
        assert grade_metric("ttfb_ms", 600) == "PASS"

    def test_ttfb_fail(self):
        assert grade_metric("ttfb_ms", 1000) == "FAIL"

    def test_speed_index_pass(self):
        assert grade_metric("speed_index_ms", 3000) == "PASS"

    def test_speed_index_fail(self):
        assert grade_metric("speed_index_ms", 4000) == "FAIL"

    def test_none_value_returns_na(self):
        assert grade_metric("lcp_ms", None) == "N/A"

    def test_unknown_key_returns_na(self):
        assert grade_metric("unknown_metric", 500) == "N/A"

    def test_performance_score_not_graded(self):
        """performance_score has no threshold, should return N/A."""
        assert grade_metric("performance_score", 90) == "N/A"


# ---------------------------------------------------------------------------
# Snapshot structure
# ---------------------------------------------------------------------------

class TestSnapshotStructure:
    """Verify snapshot JSON structure matches expectations."""

    def test_top_level_keys(self):
        snap = _make_snapshot()
        assert "timestamp" in snap
        assert "strategies" in snap
        assert "results" in snap
        assert "summary" in snap

    def test_timestamp_format(self):
        snap = _make_snapshot()
        ts = snap["timestamp"]
        assert ts.endswith("Z")
        assert "T" in ts

    def test_strategies_is_list(self):
        snap = _make_snapshot()
        assert isinstance(snap["strategies"], list)

    def test_result_structure(self):
        snap = _make_snapshot()
        r = snap["results"][0]
        assert "url" in r
        assert "label" in r
        assert "strategy" in r
        assert "metrics" in r
        assert "grades" in r

    def test_metrics_has_all_keys(self):
        snap = _make_snapshot()
        m = snap["results"][0]["metrics"]
        for key in ["lcp_ms", "cls", "inp_ms", "fid_ms", "fcp_ms", "ttfb_ms", "speed_index_ms", "performance_score"]:
            assert key in m, f"Missing metric key: {key}"

    def test_grades_has_metric_keys(self):
        snap = _make_snapshot()
        g = snap["results"][0]["grades"]
        for key in ["lcp_ms", "cls", "inp_ms", "fid_ms", "fcp_ms", "ttfb_ms", "speed_index_ms"]:
            assert key in g, f"Missing grade key: {key}"
        # performance_score should NOT be graded
        assert "performance_score" not in g

    def test_summary_keys(self):
        snap = _make_snapshot()
        s = snap["summary"]
        assert "total_checks" in s
        assert "errors" in s
        assert "avg_performance_score" in s
        assert "pass_count" in s
        assert "fail_count" in s

    def test_summary_counts(self):
        snap = _make_snapshot()
        s = snap["summary"]
        assert s["total_checks"] == 1
        assert s["errors"] == 0
        assert s["pass_count"] == 7  # all 7 graded metrics pass
        assert s["fail_count"] == 0


# ---------------------------------------------------------------------------
# Summary computation
# ---------------------------------------------------------------------------

class TestBuildSummary:
    """Test the summary computation logic."""

    def test_avg_score_computed(self):
        snap = _make_snapshot()
        assert snap["summary"]["avg_performance_score"] == 88

    def test_min_max_scores(self):
        r1 = _make_snapshot()["results"][0].copy()
        r2 = {**r1, "metrics": {**r1["metrics"], "performance_score": 72}, "label": "Page2"}
        snap = _make_snapshot(results=[r1, r2])
        assert snap["summary"]["min_performance_score"] == 72
        assert snap["summary"]["max_performance_score"] == 88

    def test_error_results_excluded(self):
        good = _make_snapshot()["results"][0]
        bad = {"url": "https://x.com/", "label": "Bad", "strategy": "mobile", "error": "HTTP 429", "metrics": {}, "grades": {}}
        snap = _make_snapshot(results=[good, bad])
        assert snap["summary"]["errors"] == 1
        assert snap["summary"]["total_checks"] == 2
        assert snap["summary"]["avg_performance_score"] == 88  # only good result

    def test_all_errors(self):
        bad = {"url": "https://x.com/", "label": "Bad", "strategy": "mobile", "error": "timeout", "metrics": {}, "grades": {}}
        snap = _make_snapshot(results=[bad])
        assert snap["summary"]["errors"] == 1
        assert snap["summary"].get("avg_performance_score") is None


# ---------------------------------------------------------------------------
# Alert thresholds
# ---------------------------------------------------------------------------

class TestAlerts:
    """Test alert threshold checks."""

    def test_all_clear(self):
        snap = _make_snapshot()
        exit_code = check_alerts(snap)
        assert exit_code == 0

    def test_lcp_alert(self):
        r = _make_snapshot()["results"][0].copy()
        r["metrics"] = {**r["metrics"], "lcp_ms": 3500}
        snap = _make_snapshot(results=[r])
        exit_code = check_alerts(snap)
        assert exit_code == 1

    def test_cls_alert(self):
        r = _make_snapshot()["results"][0].copy()
        r["metrics"] = {**r["metrics"], "cls": 0.25}
        snap = _make_snapshot(results=[r])
        exit_code = check_alerts(snap)
        assert exit_code == 1

    def test_inp_alert(self):
        r = _make_snapshot()["results"][0].copy()
        r["metrics"] = {**r["metrics"], "inp_ms": 350}
        snap = _make_snapshot(results=[r])
        exit_code = check_alerts(snap)
        assert exit_code == 1

    def test_lcp_at_threshold_no_alert(self):
        r = _make_snapshot()["results"][0].copy()
        r["metrics"] = {**r["metrics"], "lcp_ms": 2500}
        snap = _make_snapshot(results=[r])
        exit_code = check_alerts(snap)
        assert exit_code == 0

    def test_cls_at_threshold_no_alert(self):
        r = _make_snapshot()["results"][0].copy()
        r["metrics"] = {**r["metrics"], "cls": 0.1}
        snap = _make_snapshot(results=[r])
        exit_code = check_alerts(snap)
        assert exit_code == 0

    def test_inp_at_threshold_no_alert(self):
        r = _make_snapshot()["results"][0].copy()
        r["metrics"] = {**r["metrics"], "inp_ms": 200}
        snap = _make_snapshot(results=[r])
        exit_code = check_alerts(snap)
        assert exit_code == 0

    def test_none_metrics_no_alert(self):
        r = _make_snapshot()["results"][0].copy()
        r["metrics"] = {k: None for k in r["metrics"]}
        snap = _make_snapshot(results=[r])
        exit_code = check_alerts(snap)
        assert exit_code == 0

    def test_error_results_skipped(self):
        bad = {"url": "https://x.com/", "label": "Bad", "strategy": "mobile", "error": "timeout", "metrics": {}, "grades": {}}
        snap = _make_snapshot(results=[bad])
        exit_code = check_alerts(snap)
        assert exit_code == 0

    def test_multiple_alerts(self):
        r = _make_snapshot()["results"][0].copy()
        r["metrics"] = {**r["metrics"], "lcp_ms": 5000, "cls": 0.5, "inp_ms": 600}
        snap = _make_snapshot(results=[r])
        exit_code = check_alerts(snap)
        assert exit_code == 1

    def test_no_snapshot_returns_zero(self):
        exit_code = check_alerts(None)
        assert exit_code == 0


# ---------------------------------------------------------------------------
# Snapshot save/load
# ---------------------------------------------------------------------------

class TestSnapshotIO:
    """Test snapshot save and load operations."""

    def test_save_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cwv_monitor.SNAPSHOT_DIR", tmp_path)
        snap = _make_snapshot()
        path = save_snapshot(snap)
        assert path.exists()
        assert path.suffix == ".json"

    def test_save_valid_json(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cwv_monitor.SNAPSHOT_DIR", tmp_path)
        snap = _make_snapshot()
        path = save_snapshot(snap)
        loaded = json.loads(path.read_text())
        assert loaded["timestamp"] == snap["timestamp"]
        assert len(loaded["results"]) == len(snap["results"])

    def test_load_latest(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cwv_monitor.SNAPSHOT_DIR", tmp_path)
        snap1 = _make_snapshot()
        snap1["timestamp"] = "2026-02-25T07:00:00Z"
        save_snapshot(snap1)
        snap2 = _make_snapshot()
        snap2["timestamp"] = "2026-02-26T07:00:00Z"
        save_snapshot(snap2)
        loaded = load_latest_snapshot()
        assert loaded["timestamp"] == "2026-02-26T07:00:00Z"

    def test_load_latest_no_snapshots(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cwv_monitor.SNAPSHOT_DIR", tmp_path)
        assert load_latest_snapshot() is None

    def test_list_snapshots_sorted(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cwv_monitor.SNAPSHOT_DIR", tmp_path)
        for ts in ["2026-02-24T07:00:00Z", "2026-02-26T07:00:00Z", "2026-02-25T07:00:00Z"]:
            snap = _make_snapshot()
            snap["timestamp"] = ts
            save_snapshot(snap)
        files = list_snapshots()
        assert len(files) == 3
        # Should be sorted ascending
        assert files[0].name < files[1].name < files[2].name

    def test_filename_format(self, tmp_path, monkeypatch):
        monkeypatch.setattr("cwv_monitor.SNAPSHOT_DIR", tmp_path)
        snap = _make_snapshot()
        snap["timestamp"] = "2026-02-26T07:00:00Z"
        path = save_snapshot(snap)
        assert path.name == "2026-02-26_07-00-00.json"


# ---------------------------------------------------------------------------
# Run snapshot (mocked API)
# ---------------------------------------------------------------------------

class TestRunSnapshot:
    """Test full snapshot run with mocked PSI API calls."""

    @patch("cwv_monitor.fetch_psi")
    def test_snapshot_has_all_urls(self, mock_fetch):
        mock_fetch.return_value = _make_psi_response()
        snap = run_snapshot(["mobile"])
        urls = [r["url"] for r in snap["results"]]
        for entry in MONITORED_URLS:
            assert entry["url"] in urls

    @patch("cwv_monitor.fetch_psi")
    def test_snapshot_both_strategies(self, mock_fetch):
        mock_fetch.return_value = _make_psi_response()
        snap = run_snapshot(["mobile", "desktop"])
        assert len(snap["results"]) == 14  # 7 URLs x 2 strategies
        strategies = {r["strategy"] for r in snap["results"]}
        assert strategies == {"mobile", "desktop"}

    @patch("cwv_monitor.fetch_psi")
    def test_snapshot_mobile_only(self, mock_fetch):
        mock_fetch.return_value = _make_psi_response()
        snap = run_snapshot(["mobile"])
        assert len(snap["results"]) == 7
        assert all(r["strategy"] == "mobile" for r in snap["results"])

    @patch("cwv_monitor.fetch_psi")
    def test_snapshot_desktop_only(self, mock_fetch):
        mock_fetch.return_value = _make_psi_response()
        snap = run_snapshot(["desktop"])
        assert len(snap["results"]) == 7
        assert all(r["strategy"] == "desktop" for r in snap["results"])

    @patch("cwv_monitor.fetch_psi")
    def test_api_error_captured(self, mock_fetch):
        import urllib.error
        mock_fetch.side_effect = urllib.error.HTTPError(
            url="http://test", code=429, msg="Too Many Requests", hdrs=None, fp=None
        )
        snap = run_snapshot(["mobile"])
        assert len(snap["results"]) == 7
        assert all("error" in r for r in snap["results"])
        assert snap["summary"]["errors"] == 7

    @patch("cwv_monitor.fetch_psi")
    def test_generic_exception_captured(self, mock_fetch):
        mock_fetch.side_effect = Exception("Network timeout")
        snap = run_snapshot(["mobile"])
        assert all("error" in r for r in snap["results"])

    @patch("cwv_monitor.fetch_psi")
    @patch("cwv_monitor.time.sleep")
    def test_rate_limiting_sleep(self, mock_sleep, mock_fetch):
        mock_fetch.return_value = _make_psi_response()
        run_snapshot(["mobile"])
        # Should sleep between requests (7 URLs, 6 sleeps)
        assert mock_sleep.call_count == 6

    @patch("cwv_monitor.fetch_psi")
    def test_api_key_passed_through(self, mock_fetch):
        mock_fetch.return_value = _make_psi_response()
        with patch.dict("os.environ", {"PAGESPEED_API_KEY": "test-key-123"}):
            run_snapshot(["mobile"])
        # Verify api_key was passed to fetch_psi
        for call in mock_fetch.call_args_list:
            assert call.kwargs.get("api_key") == "test-key-123" or call[1].get("api_key") == "test-key-123"


# ---------------------------------------------------------------------------
# Thresholds config
# ---------------------------------------------------------------------------

class TestThresholds:
    """Verify threshold constants are set to Google's documented values."""

    def test_lcp_threshold(self):
        assert THRESHOLDS["lcp_ms"] == 2500

    def test_cls_threshold(self):
        assert THRESHOLDS["cls"] == 0.1

    def test_inp_threshold(self):
        assert THRESHOLDS["inp_ms"] == 200

    def test_fid_threshold(self):
        assert THRESHOLDS["fid_ms"] == 100

    def test_fcp_threshold(self):
        assert THRESHOLDS["fcp_ms"] == 1800

    def test_ttfb_threshold(self):
        assert THRESHOLDS["ttfb_ms"] == 800

    def test_alert_thresholds_match_cwv(self):
        """Alert thresholds should match core CWV thresholds (LCP/CLS/INP)."""
        assert ALERT_THRESHOLDS["lcp_ms"] == THRESHOLDS["lcp_ms"]
        assert ALERT_THRESHOLDS["cls"] == THRESHOLDS["cls"]
        assert ALERT_THRESHOLDS["inp_ms"] == THRESHOLDS["inp_ms"]

    def test_alert_thresholds_only_core(self):
        """Alerts only fire on core CWV metrics (LCP, CLS, INP)."""
        assert set(ALERT_THRESHOLDS.keys()) == {"lcp_ms", "cls", "inp_ms"}


# ---------------------------------------------------------------------------
# Report output (smoke test)
# ---------------------------------------------------------------------------

class TestReport:
    """Verify report prints without crashing."""

    def test_report_with_snapshot(self, capsys):
        snap = _make_snapshot()
        print_report(snap)
        output = capsys.readouterr().out
        assert "CWV REPORT" in output
        assert "Homepage" in output
        assert "MOBILE" in output

    def test_report_no_snapshot(self, capsys):
        print_report(None)
        output = capsys.readouterr().out
        assert "No snapshots found" in output

    def test_report_with_error_result(self, capsys):
        good = _make_snapshot()["results"][0]
        bad = {"url": "https://x.com/", "label": "ErrorPage", "strategy": "mobile", "error": "HTTP 429", "metrics": {}, "grades": {}}
        snap = _make_snapshot(results=[good, bad])
        print_report(snap)
        output = capsys.readouterr().out
        assert "ERROR" in output
        assert "Homepage" in output

    def test_report_shows_thresholds(self, capsys):
        snap = _make_snapshot()
        print_report(snap)
        output = capsys.readouterr().out
        assert "2500ms" in output
        assert "0.1" in output

    def test_report_both_strategies(self, capsys):
        r_mobile = _make_snapshot()["results"][0].copy()
        r_desktop = {**r_mobile, "strategy": "desktop"}
        snap = _make_snapshot(results=[r_mobile, r_desktop])
        snap["strategies"] = ["mobile", "desktop"]
        print_report(snap)
        output = capsys.readouterr().out
        assert "MOBILE" in output
        assert "DESKTOP" in output

    def test_report_fail_marker(self, capsys):
        r = _make_snapshot()["results"][0].copy()
        r["metrics"] = {**r["metrics"], "lcp_ms": 5000}
        r["grades"] = {**r["grades"], "lcp_ms": "FAIL"}
        snap = _make_snapshot(results=[r])
        print_report(snap)
        output = capsys.readouterr().out
        assert "*" in output  # fail marker
