"""Win-back (lead_cold_30d): who is selected, the env gate, and the cap.

All addresses are example.com fixtures — no real lead data.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from mission_control.services import win_back as wb

NOW = datetime(2026, 10, 23, 15, 30, tzinfo=timezone.utc)


def _iso(days_ago: float) -> str:
    return (NOW - timedelta(days=days_ago)).isoformat()


def _enr(email, seq="welcome_v1", status="completed", days_ago=60, source="exit_intent",
         source_data=None, name="Test Rider", completed_days_ago=None):
    return {
        "id": str(uuid.uuid4()), "sequence_id": seq, "variant": "A",
        "contact_email": email, "contact_name": name, "source": source,
        "source_data": source_data or {}, "status": status, "current_step": 0,
        "enrolled_at": _iso(days_ago),
        "completed_at": _iso(completed_days_ago if completed_days_ago is not None else days_ago - 10)
        if status == "completed" else None,
        "next_send_at": None,
    }


def _send(enrollment, days_ago=50, **cols):
    row = {"id": str(uuid.uuid4()), "enrollment_id": enrollment["id"], "status": "sent",
           "sent_at": _iso(days_ago), "opened_at": None, "clicked_at": None,
           "first_reply_at": None, "complained_at": None}
    row.update(cols)
    return row


def _select(enrollments, sends=(), conversations=(), buyers=(), race_dates=None):
    return wb.select_cold_leads(list(enrollments), list(sends), list(conversations),
                                set(buyers), NOW, race_dates or {})


class TestSelection:
    def test_finished_and_quiet_for_30_days_is_selected(self):
        e = _enr("cold@example.com")
        out, _ = _select([e], [_send(e, 50)])
        assert [c["email"] for c in out] == ["cold@example.com"]
        assert out[0]["sequence_id"] == "win_back_v1"
        assert "race_name" not in out[0]["source_data"]

    @pytest.mark.parametrize("col", ["sent_at", "opened_at", "clicked_at", "first_reply_at"])
    def test_any_recent_send_open_click_or_reply_keeps_them_warm(self, col):
        e = _enr("warm@example.com")
        s = _send(e, 50, **{col: _iso(10)})
        out, skips = _select([e], [s])
        assert out == [] and skips["recent_activity"] == 1

    def test_recent_gmail_conversation_keeps_them_warm(self):
        e = _enr("talking@example.com")
        conv = {"contact_email": "Talking@Example.com", "status": "closed",
                "last_inbound_at": _iso(5), "last_outbound_at": None}
        out, skips = _select([e], [_send(e, 50)], [conv])
        assert out == [] and skips["recent_activity"] == 1

    @pytest.mark.parametrize("status", ["needs_reply", "gmail_drafted", "won", "lost"])
    def test_conversation_waiting_on_matti_or_decided_is_held(self, status):
        e = _enr("held@example.com")
        conv = {"contact_email": "held@example.com", "status": status,
                "last_inbound_at": _iso(90), "last_outbound_at": None}
        out, skips = _select([e], [_send(e, 50)], [conv])
        assert out == [] and skips["conversation"] == 1

    def test_still_mid_sequence_is_skipped(self):
        done = _enr("mid@example.com")
        active = _enr("mid@example.com", seq="nurture_v1", status="active", days_ago=40)
        out, skips = _select([done, active])
        assert out == [] and skips["active"] == 1

    def test_never_finished_a_sequence_is_skipped(self):
        # only a completed row of a sequence id no longer defined
        out, skips = _select([_enr("x@example.com", seq="retired_seq_v0")])
        assert out == [] and skips["no_finished_sequence"] == 1

    @pytest.mark.parametrize("status", ["unsubscribed", "paused"])
    def test_unsubscribed_or_paused_anywhere_is_skipped(self, status):
        done = _enr("gone@example.com")
        other = _enr("gone@example.com", seq="nurture_v1", status=status, days_ago=90)
        out, skips = _select([done, other])
        assert out == [] and skips["suppressed"] == 1

    def test_opt_out_flag_is_skipped(self):
        e = _enr("opt@example.com", source_data={"opted_out_at": _iso(80)})
        out, skips = _select([e])
        assert out == [] and skips["suppressed"] == 1

    @pytest.mark.parametrize("cols", [{"status": "bounced"}, {"status": "complained"},
                                      {"complained_at": "2026-01-01T00:00:00+00:00"}])
    def test_bounced_or_complained_is_skipped(self, cols):
        e = _enr("bad@example.com")
        out, skips = _select([e], [_send(e, 50, **cols)])
        assert out == [] and skips["suppressed"] == 1

    def test_buyer_is_skipped(self):
        e = _enr("Buyer@example.com")
        out, skips = _select([e], buyers={"buyer@example.com"})
        assert out == [] and skips["buyer"] == 1

    @pytest.mark.parametrize("seq,source", [("post_purchase_v1", "stripe_plan"),
                                            ("athlete_review_v1", "athlete_review")])
    def test_post_purchase_or_athlete_record_is_not_a_lead(self, seq, source):
        lead = _enr("athlete@example.com")
        other = _enr("athlete@example.com", seq=seq, source=source, days_ago=200)
        out, skips = _select([lead, other])
        assert out == [] and skips["not_lead"] == 1

    @pytest.mark.parametrize("seq", ["win_back_v1", "xc_win_back_v1"])
    def test_already_had_win_back_is_skipped(self, seq):
        lead = _enr("again@example.com", days_ago=400)
        prior = _enr("again@example.com", seq=seq, source="win_back", days_ago=200)
        out, skips = _select([lead, prior])
        assert out == [] and skips["had_win_back"] == 1

    def test_already_debriefed_is_skipped(self):
        lead = _enr("asked@example.com", days_ago=200)
        debrief = _enr("asked@example.com", seq="race_debrief_v1", source="race_debrief", days_ago=60)
        out, skips = _select([lead, debrief])
        assert out == [] and skips["had_debrief"] == 1

    def test_road_lead_has_no_win_back_definition(self):
        e = _enr("road@example.com", seq="road_welcome_v1")
        out, skips = _select([e])
        assert out == [] and skips["no_sequence_for_brand"] == 1

    def test_xc_lead_goes_to_xc_win_back(self):
        e = _enr("ski@example.com", seq="xc_welcome_v1")
        out, _ = _select([e])
        assert out[0]["sequence_id"] == "xc_win_back_v1" and out[0]["brand"] == "xcskilabs"

    def test_brand_follows_newest_marketing_enrollment(self):
        old = _enr("both@example.com", seq="xc_welcome_v1", days_ago=300)
        new = _enr("both@example.com", seq="welcome_v1", days_ago=100)
        out, _ = _select([old, new])
        assert out[0]["sequence_id"] == "win_back_v1"

    def test_newest_cold_first(self):
        a = _enr("a@example.com", days_ago=400, completed_days_ago=390)
        b = _enr("b@example.com", days_ago=45, completed_days_ago=35)
        out, _ = _select([a, b])
        assert [c["email"] for c in out] == ["b@example.com", "a@example.com"]


class TestRaceNamePremise:
    """"Did you end up racing it?" is only true after the race."""

    SD = {"race_slug": "big-sugar", "race_name": "Big Sugar"}

    def test_race_named_only_when_its_date_has_passed(self):
        e = _enr("r@example.com", seq="nurture_v1", source="prep_kit_gate", source_data=self.SD)
        out, _ = _select([e], race_dates={"gravelgod": {"big-sugar": "2026-05-01"}})
        assert out[0]["source_data"]["race_name"] == "Big Sugar"

    @pytest.mark.parametrize("dates", [{"gravelgod": {"big-sugar": "2027-10-17"}}, {}, None,
                                       {"gravelgod": {"big-sugar": "TBD"}}])
    def test_upcoming_or_unknown_date_drops_the_race(self, dates):
        e = _enr("r@example.com", seq="nurture_v1", source="prep_kit_gate", source_data=self.SD)
        out, _ = _select([e], race_dates=dates)
        assert "race_name" not in out[0]["source_data"]
        assert "race_slug" not in out[0]["source_data"]

    def test_rendered_fallback_has_no_race_and_no_placeholder(self, fake_db):
        from mission_control.services.sequence_engine import _render_template
        html = _render_template("win_back_value", {"contact_name": "Test Rider",
                                                   "source_data": {"brand": "gravelgod"}})
        assert "poking around the race database" in html
        assert "your race" not in html and "{" not in html.split("<body")[1]


class TestRunGate:
    def _seed(self, fake_db, n):
        for i in range(n):
            e = _enr(f"cold{i}@example.com", days_ago=60 + i)
            fake_db.store["gg_sequence_enrollments"].append(e)
            fake_db.store["gg_sequence_sends"].append(_send(e, 55 + i))

    def _on(self, monkeypatch, cap=20):
        from mission_control.sequences import SEQUENCES
        monkeypatch.setattr(wb.config, "WIN_BACK_ENABLED", True)
        monkeypatch.setattr(wb.config, "WIN_BACK_DAILY_CAP", cap)
        monkeypatch.setitem(SEQUENCES["win_back_v1"], "active", True)
        monkeypatch.setitem(SEQUENCES["xc_win_back_v1"], "active", True)
        monkeypatch.setattr(wb, "_fetch_dates_sync", lambda: {})

    def _winbacks(self, fake_db):
        return [e for e in fake_db.store["gg_sequence_enrollments"]
                if e["sequence_id"] in ("win_back_v1", "xc_win_back_v1")]

    def test_defaults_are_off(self):
        from mission_control.sequences import SEQUENCES
        import os
        if os.environ.get("WIN_BACK_ENABLED"):
            pytest.skip("WIN_BACK_ENABLED set in this environment")
        from mission_control import config
        assert config.WIN_BACK_ENABLED is False
        assert SEQUENCES["win_back_v1"]["active"] is False
        assert SEQUENCES["xc_win_back_v1"]["active"] is False

    def test_flag_off_enrolls_nobody(self, fake_db, monkeypatch):
        self._seed(fake_db, 3)
        monkeypatch.setattr(wb.config, "WIN_BACK_ENABLED", False)
        summary = asyncio.run(wb.run_win_back(now=NOW))
        assert summary["enabled"] is False and summary["enrolled"] == 0
        assert self._winbacks(fake_db) == []

    def test_inactive_sequence_enrolls_nobody_even_if_job_runs(self, fake_db, monkeypatch):
        self._seed(fake_db, 2)
        self._on(monkeypatch)
        from mission_control.sequences import SEQUENCES
        monkeypatch.setitem(SEQUENCES["win_back_v1"], "active", False)
        summary = asyncio.run(wb.run_win_back(now=NOW))
        assert summary["candidates"] == 2 and summary["enrolled"] == 0
        assert self._winbacks(fake_db) == []

    def test_flag_on_respects_the_daily_cap(self, fake_db, monkeypatch):
        self._seed(fake_db, 25)
        self._on(monkeypatch, cap=20)
        summary = asyncio.run(wb.run_win_back(now=NOW))
        assert summary["candidates"] == 25 and summary["enrolled"] == 20 and summary["capped"]
        rows = self._winbacks(fake_db)
        assert len(rows) == 20
        assert all(r["source"] == "win_back" and r["next_send_at"] for r in rows)
        # second day: the remaining 5, and nobody twice
        summary2 = asyncio.run(wb.run_win_back(now=NOW + timedelta(days=1)))
        assert summary2["enrolled"] == 5
        assert len({r["contact_email"] for r in self._winbacks(fake_db)}) == 25
        # third day: nobody left
        assert asyncio.run(wb.run_win_back(now=NOW + timedelta(days=2)))["enrolled"] == 0

    def test_pages_past_the_postgrest_row_cap(self, fake_db, monkeypatch):
        monkeypatch.setattr(wb, "_PAGE", 3)
        self._seed(fake_db, 7)
        self._on(monkeypatch)
        assert asyncio.run(wb.run_win_back(now=NOW))["enrolled"] == 7

    def test_buyer_from_deal_or_payment_is_never_enrolled(self, fake_db, monkeypatch):
        self._seed(fake_db, 2)
        fake_db.store["gg_deals"].extend([
            {"id": "d1", "contact_email": "cold0@example.com", "stage": "closed_won"},
            {"id": "d2", "contact_email": "cold1@example.com", "stage": "lead"},
        ])
        fake_db.store["gg_payments"].append({"id": "p1", "deal_id": "d2"})
        self._on(monkeypatch)
        assert asyncio.run(wb.run_win_back(now=NOW))["enrolled"] == 0

    def test_enrolled_win_back_sends_step_zero(self, fake_db, monkeypatch):
        from mission_control.services import sequence_engine as se
        self._seed(fake_db, 1)
        self._on(monkeypatch)
        asyncio.run(wb.run_win_back(now=NOW))
        monkeypatch.setattr(se, "RESEND_API_KEY", "test-key")
        monkeypatch.setattr(se, "_send_email_sync", lambda *a, **k: "resend-test-id")
        (row,) = self._winbacks(fake_db)
        assert asyncio.run(se._send_next_step(row)) is True
        sends = [s for s in fake_db.store["gg_sequence_sends"] if s["enrollment_id"] == row["id"]]
        assert [s["template"] for s in sends] == ["win_back_value"]
        assert row["status"] == "completed"

    def test_unreadable_history_aborts_closed(self, fake_db, monkeypatch):
        self._seed(fake_db, 2)
        self._on(monkeypatch)

        def boom():
            raise RuntimeError("relation gg_lead_conversations does not exist")
        monkeypatch.setattr(wb, "_load_sync", boom)
        summary = asyncio.run(wb.run_win_back(now=NOW))
        assert summary["aborted"] and summary["enrolled"] == 0
        assert self._winbacks(fake_db) == []


def test_scheduler_registers_daily_job():
    # conftest swaps mission_control.scheduler for a mock (client fixture),
    # so load the real module from its file under a private name.
    import importlib.util
    from pathlib import Path
    path = Path(wb.__file__).resolve().parent.parent / "scheduler.py"
    spec = importlib.util.spec_from_file_location("_mc_scheduler_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    job = mod.scheduler.get_job("win_back")
    assert job is not None and "hour='15'" in str(job.trigger) and "minute='30'" in str(job.trigger)
