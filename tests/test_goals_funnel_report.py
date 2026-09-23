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
checkout's ga4-credentials.json even when this script runs from a worktree.
"""
from __future__ import annotations

import subprocess
import sys
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
            "sequence_prefix": "goal_2027", "enrollments": 0, "unsubscribed": 0,
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
