"""Tests for scripts/goals_funnel_report.py.

Covers two bugs a live run against the real database turned up:
1. Mission Control's "by offer variant" breakdown was reading the
   enrollment's own `variant` column (sequence_engine.py's internal
   template-variant slot) instead of `source_data.offer_variant` (the
   /goals/ page's A/B/C offer-copy test) — same word, two different fields.
2. gg_sequence_sends was pulled unfiltered and matched client-side, which
   silently drops rows past Supabase's default 1000-row page size once the
   table (shared across every sequence, not just goal_2027) grows past that.

Plus the GA4 credentials-path fallback, which needs to find the main
checkout's ga4-credentials.json even when this script runs from a worktree,
and a third bug from sol's review: the Mission Control section ignored
--days entirely, always reporting everything ever while the GA4 section
above it respected the requested window.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import goals_funnel_report  # noqa: E402
from goals_funnel_report import (  # noqa: E402
    MC_SENDS_BATCH_SIZE,
    PROJECT_ROOT,
    _default_ga4_credentials_path,
    get_mission_control_numbers,
    get_mock_mission_control,
)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


# ── The real bug: offer_variant lives in source_data, not `variant` ────────


class TestOfferVariantSource:
    def test_reads_source_data_offer_variant_not_the_enrollment_variant_column(self, monkeypatch):
        """Reproduces the exact live-database shape that exposed the bug:
        one goal_2027_v1 enrollment with the sequence engine's own
        variant="A" (a different concept) and source_data.offer_variant="C"
        (the /goals/ offer copy the visitor actually saw)."""
        calls = []

        def fake_mc_req(path, params=""):
            calls.append((path, params))
            if path == "gg_sequence_enrollments":
                return [{
                    "id": "ed2e8fa8-d5b8-43d3-8a6b-f39a777d7464",
                    "sequence_id": "goal_2027_v1",
                    "variant": "A",
                    "status": "active",
                    "contact_email": "gravelgodcoaching@gmail.com",
                    "source_data": {"offer_variant": "C", "goal_line": "x"},
                }]
            if path == "gg_sequence_sends":
                return [{
                    "enrollment_id": "ed2e8fa8-d5b8-43d3-8a6b-f39a777d7464",
                    "step_index": 0, "opened_at": None, "clicked_at": None, "status": "sent",
                }]
            raise AssertionError(f"unexpected table {path!r}")

        monkeypatch.setattr(goals_funnel_report, "_mc_req", fake_mc_req)
        result = get_mission_control_numbers()

        assert result["by_offer_variant"] == {"C": 1}
        assert result["sends"] == 1

    def test_enrollment_with_no_offer_variant_is_bucketed_as_none(self, monkeypatch):
        def fake_mc_req(path, params=""):
            if path == "gg_sequence_enrollments":
                return [{"id": "x", "sequence_id": "goal_2027_v1", "variant": "B",
                         "status": "active", "contact_email": "a@example.com", "source_data": {}}]
            return []

        monkeypatch.setattr(goals_funnel_report, "_mc_req", fake_mc_req)
        result = get_mission_control_numbers()
        assert result["by_offer_variant"] == {"(none)": 1}


# ── The real bug: sends fetched unfiltered, dropped past the page limit ────


class TestSendsAreFilteredServerSide:
    def test_sends_query_is_scoped_to_the_known_enrollment_ids(self, monkeypatch):
        """The old code fetched ALL of gg_sequence_sends with no filter, then
        matched client-side — which silently misses rows past Supabase's
        default 1000-row page once the table (shared by every sequence)
        outgrows that. The fix must ask Postgres for only these ids."""
        seen_sends_params = []

        def fake_mc_req(path, params=""):
            if path == "gg_sequence_enrollments":
                return [
                    {"id": "e1", "sequence_id": "goal_2027_v1", "variant": "A",
                     "status": "active", "contact_email": "a@example.com",
                     "source_data": {"offer_variant": "A"}},
                    {"id": "e2", "sequence_id": "goal_2027_v1", "variant": "B",
                     "status": "active", "contact_email": "b@example.com",
                     "source_data": {"offer_variant": "B"}},
                ]
            if path == "gg_sequence_sends":
                seen_sends_params.append(params)
                return [{"enrollment_id": "e1", "step_index": 0,
                         "opened_at": "2026-01-01T00:00:00Z", "clicked_at": None, "status": "sent"}]
            raise AssertionError(f"unexpected table {path!r}")

        monkeypatch.setattr(goals_funnel_report, "_mc_req", fake_mc_req)
        result = get_mission_control_numbers()

        assert len(seen_sends_params) == 1
        assert "enrollment_id=in.(e1,e2)" in seen_sends_params[0]
        assert result["sends"] == 1
        assert result["opens"] == 1

    def test_batches_large_enrollment_id_lists(self, monkeypatch):
        """A future high-volume goal_2027 shouldn't build one URL with
        thousands of ids in it — confirm batching kicks in."""
        many_ids = [f"id-{i}" for i in range(MC_SENDS_BATCH_SIZE + 5)]
        seen_batches = []

        def fake_mc_req(path, params=""):
            if path == "gg_sequence_enrollments":
                return [{"id": i, "sequence_id": "goal_2027_v1", "variant": "A",
                         "status": "active", "contact_email": f"{i}@example.com",
                         "source_data": {}} for i in many_ids]
            if path == "gg_sequence_sends":
                seen_batches.append(params)
                return []
            raise AssertionError(f"unexpected table {path!r}")

        monkeypatch.setattr(goals_funnel_report, "_mc_req", fake_mc_req)
        get_mission_control_numbers()

        assert len(seen_batches) == 2  # 105 ids at batch size 100 -> two requests
        assert "id-0" in seen_batches[0]
        assert f"id-{MC_SENDS_BATCH_SIZE}" in seen_batches[1]

    def test_no_enrollments_skips_the_sends_query_entirely(self, monkeypatch):
        calls = []

        def fake_mc_req(path, params=""):
            calls.append(path)
            return []

        monkeypatch.setattr(goals_funnel_report, "_mc_req", fake_mc_req)
        result = get_mission_control_numbers()
        assert calls == ["gg_sequence_enrollments"]
        assert result == {
            "sequence_prefix": "goal_2027", "days": 30, "enrollments": 0, "unsubscribed": 0,
            "resends": 0, "sends": 0, "opens": 0, "clicks": 0, "by_offer_variant": {},
        }


# ── Mock data shape matches the real shape ─────────────────────────────────


def test_mock_mission_control_uses_the_same_keys_as_the_real_function():
    mock = get_mock_mission_control()
    assert "by_offer_variant" in mock
    assert "variant" not in mock  # the old, wrong key must not reappear


# ── GA4 credentials path: must not point inside a worktree ─────────────────


class TestDefaultCredentialsPath:
    def test_resolves_relative_to_the_main_checkout_not_this_script(self):
        # Whatever checkout this test runs from (worktree or plain), the
        # main checkout is what `git rev-parse --git-common-dir`'s parent
        # names — compute that independently and compare, rather than
        # hardcoding a path.
        common_dir = subprocess.run(
            ["git", "-C", str(SCRIPTS_DIR), "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        expected_root = Path(SCRIPTS_DIR, common_dir).resolve().parent
        result = _default_ga4_credentials_path()
        assert result.name == "ga4-credentials.json"
        if (expected_root / "ga4-credentials.json").exists():
            assert result.parent == expected_root

    def test_falls_back_to_project_root_when_git_lookup_fails(self, monkeypatch):
        def boom(*a, **k):
            raise FileNotFoundError("no git")

        monkeypatch.setattr(subprocess, "run", boom)
        result = _default_ga4_credentials_path()
        assert result == PROJECT_ROOT / "ga4-credentials.json"

    def test_falls_back_when_main_root_has_no_credentials_file(self, monkeypatch, tmp_path):
        class FakeResult:
            stdout = str(tmp_path / "nowhere" / ".git")

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())
        result = _default_ga4_credentials_path()
        assert result == PROJECT_ROOT / "ga4-credentials.json"


# ── Mission Control must respect --days like the GA4 section does ─────────


class TestMissionControlRespectsDays:
    def test_enrollments_query_is_scoped_to_the_requested_window(self, monkeypatch):
        seen_params = []

        def fake_mc_req(path, params=""):
            if path == "gg_sequence_enrollments":
                seen_params.append(params)
                return []
            return []

        monkeypatch.setattr(goals_funnel_report, "_mc_req", fake_mc_req)
        get_mission_control_numbers(days=7)

        expected_cutoff = (date.today() - timedelta(days=7)).isoformat()
        assert len(seen_params) == 1
        assert f"enrolled_at=gte.{expected_cutoff}" in seen_params[0]

    def test_default_window_is_thirty_days(self, monkeypatch):
        seen_params = []
        monkeypatch.setattr(goals_funnel_report, "_mc_req",
                            lambda path, params="": (seen_params.append(params) or []))
        get_mission_control_numbers()
        expected_cutoff = (date.today() - timedelta(days=30)).isoformat()
        assert f"enrolled_at=gte.{expected_cutoff}" in seen_params[0]

    def test_result_reports_which_window_it_used(self, monkeypatch):
        monkeypatch.setattr(goals_funnel_report, "_mc_req", lambda path, params="": [])
        result = get_mission_control_numbers(days=14)
        assert result["days"] == 14

    def test_mock_mission_control_accepts_and_reports_days(self):
        mock = get_mock_mission_control(days=7)
        assert mock["days"] == 7

    def test_main_forwards_args_days_to_mission_control(self):
        import inspect
        src = inspect.getsource(goals_funnel_report.main)
        assert "get_mission_control_numbers(days=args.days)" in src
        assert "get_mock_mission_control(days=args.days)" in src
