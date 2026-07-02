"""Race-countdown trigger — window math, suppressions, brand routing."""

import asyncio
from datetime import date
from unittest.mock import patch

from mission_control.sequences import SEQUENCES, get_sequences_for_trigger, sequence_brand
from mission_control.services.race_countdown import (
    classify_weeks,
    gather_candidates,
    run_race_countdown,
)


class TestClassifyWeeks:
    def test_sixteen_week_window(self):
        assert classify_weeks(16.0) == 16
        assert classify_weeks(12.0) == 16
        assert classify_weeks(17.0) == 16

    def test_eight_week_window(self):
        assert classify_weeks(8.0) == 8
        assert classify_weeks(5.0) == 8
        assert classify_weeks(9.0) == 8

    def test_out_of_window(self):
        assert classify_weeks(20.0) is None   # too far out
        assert classify_weeks(10.5) is None   # between tiers
        assert classify_weeks(4.0) is None    # under the honesty line
        assert classify_weeks(-2.0) is None   # race passed


class TestGatherCandidates:
    def test_latest_race_wins_and_active_tracked(self):
        rows = [
            {"contact_email": "a@x.com", "contact_name": "A", "status": "completed",
             "source_data": {"race_slug": "old-race", "race_name": "Old", "brand": "gravelgod"}},
            {"contact_email": "a@x.com", "contact_name": "A", "status": "active",
             "source_data": {"race_slug": "new-race", "race_name": "New", "brand": "roadielabs"}},
            {"contact_email": "b@x.com", "contact_name": "B", "status": "completed",
             "source_data": {}},
        ]
        contacts, mid = gather_candidates(rows)
        assert contacts["a@x.com"]["race_slug"] == "new-race"
        assert contacts["a@x.com"]["brand"] == "roadielabs"
        assert "b@x.com" not in contacts          # no race supplied
        assert "a@x.com" in mid

    def test_brand_defaults_to_gravel(self):
        rows = [{"contact_email": "c@x.com", "contact_name": "C", "status": "completed",
                 "source_data": {"race_slug": "some-race"}}]
        contacts, _ = gather_candidates(rows)
        assert contacts["c@x.com"]["brand"] == "gravelgod"
        assert contacts["c@x.com"]["race_name"] == "some-race"  # falls back to slug


class TestCountdownSequences:
    def test_four_sequences_registered_and_brand_scoped(self):
        assert sequence_brand(SEQUENCES["race_countdown_16_v1"]) == "gravelgod"
        assert sequence_brand(SEQUENCES["road_race_countdown_8_v1"]) == "roadielabs"

    def test_not_reachable_from_subscriber_triggers(self):
        for trigger in ("new_subscriber", "prep_kit_download", "quiz_completed"):
            for brand in ("gravelgod", "roadielabs"):
                ids = {s["id"] for s in get_sequences_for_trigger(trigger, brand=brand)}
                assert not any("countdown" in i for i in ids)


def _run(coro):
    return asyncio.run(coro)


class TestRunRaceCountdown:
    def _base_patches(self, dates, enrollments, customer=None):
        return (
            patch("mission_control.services.race_countdown._fetch_dates_sync",
                  return_value=dates),
            patch("mission_control.services.race_countdown.db.select",
                  return_value=enrollments),
            patch("mission_control.services.race_countdown.db.select_one",
                  return_value=customer),
            patch("mission_control.services.race_countdown.db.log_action"),
        )

    def test_enrolls_in_window_with_brand_routing(self):
        today = date(2026, 7, 1)
        dates = {"gravelgod": {"unbound-200": "2026-10-21"},      # 16.0 weeks
                 "roadielabs": {"mallorca-312": "2026-08-26"}}    # 8.0 weeks
        rows = [
            {"contact_email": "g@x.com", "contact_name": "G", "status": "completed",
             "source_data": {"race_slug": "unbound-200", "race_name": "Unbound 200",
                             "brand": "gravelgod"}},
            {"contact_email": "r@x.com", "contact_name": "R", "status": "completed",
             "source_data": {"race_slug": "mallorca-312", "race_name": "Mallorca 312",
                             "brand": "roadielabs"}},
        ]
        p1, p2, p3, p4 = self._base_patches(dates, rows)
        with p1, p2, p3, p4, patch(
                "mission_control.services.race_countdown.enroll",
                return_value={"id": 1}) as mock_enroll:
            summary = _run(run_race_countdown(today=today))
        assert summary["enrolled"] == 2
        called_ids = {c.args[2] for c in mock_enroll.call_args_list}
        assert called_ids == {"race_countdown_16_v1", "road_race_countdown_8_v1"}
        # source_data contract: countdown emails may safely use these fields
        sd = mock_enroll.call_args_list[0].kwargs["source_data"]
        assert {"race_name", "race_date", "weeks_out", "brand"} <= set(sd)

    def test_suppressions(self):
        today = date(2026, 7, 1)
        dates = {"gravelgod": {"unbound-200": "2026-10-21"}, "roadielabs": {}}
        rows = [
            # mid-sequence contact — skipped
            {"contact_email": "busy@x.com", "contact_name": "B", "status": "active",
             "source_data": {"race_slug": "unbound-200", "brand": "gravelgod"}},
            # race not in dates file — skipped
            {"contact_email": "tbd@x.com", "contact_name": "T", "status": "completed",
             "source_data": {"race_slug": "no-date-race", "brand": "gravelgod"}},
            # out of window — skipped
            {"contact_email": "far@x.com", "contact_name": "F", "status": "completed",
             "source_data": {"race_slug": "unbound-200", "brand": "gravelgod"}},
        ]
        # make "far" out-of-window by moving today
        p1, p2, p3, p4 = self._base_patches(dates, rows[:2])
        with p1, p2, p3, p4, patch(
                "mission_control.services.race_countdown.enroll") as mock_enroll:
            summary = _run(run_race_countdown(today=today))
        assert summary["enrolled"] == 0
        assert summary["skipped_mid_sequence"] == 1
        assert summary["skipped_no_date"] == 1
        mock_enroll.assert_not_called()

    def test_customer_suppression(self):
        today = date(2026, 7, 1)
        dates = {"gravelgod": {"unbound-200": "2026-10-21"}, "roadielabs": {}}
        rows = [{"contact_email": "cust@x.com", "contact_name": "C", "status": "completed",
                 "source_data": {"race_slug": "unbound-200", "brand": "gravelgod"}}]
        p1, p2, p3, p4 = self._base_patches(dates, rows,
                                            customer={"plan_status": "delivered"})
        with p1, p2, p3, p4, patch(
                "mission_control.services.race_countdown.enroll") as mock_enroll:
            summary = _run(run_race_countdown(today=today))
        assert summary["skipped_customer"] == 1
        mock_enroll.assert_not_called()

    def test_aborts_when_no_dates(self):
        p1, p2, p3, p4 = self._base_patches({"gravelgod": {}, "roadielabs": {}}, [])
        with p1, p2, p3, p4, patch(
                "mission_control.services.race_countdown.enroll") as mock_enroll:
            summary = _run(run_race_countdown(today=date(2026, 7, 1)))
        assert summary["enrolled"] == 0
        mock_enroll.assert_not_called()
