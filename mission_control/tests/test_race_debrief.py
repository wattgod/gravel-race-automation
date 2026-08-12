"""Race-debrief trigger — window math, suppressions, cap, brand routing."""

import asyncio
from datetime import date
from unittest.mock import patch

from mission_control.sequences import SEQUENCES, get_sequences_for_trigger, sequence_brand
from mission_control.services.race_debrief import run_race_debrief, when_phrase


def _run(coro):
    return asyncio.run(coro)


class TestWhenPhrase:
    def test_fresh_race(self):
        assert when_phrase(3, date(2026, 8, 6)) == "the other weekend"
        assert when_phrase(10, date(2026, 7, 30)) == "the other weekend"

    def test_weeks_ago(self):
        assert when_phrase(11, date(2026, 7, 29)) == "a few weeks back"
        assert when_phrase(45, date(2026, 6, 25)) == "a few weeks back"

    def test_months_ago_names_the_month(self):
        assert when_phrase(71, date(2026, 5, 30)) == "back in May"


class TestDebriefSequences:
    def test_registered_and_brand_scoped(self):
        assert sequence_brand(SEQUENCES["race_debrief_v1"]) == "gravelgod"
        assert sequence_brand(SEQUENCES["road_race_debrief_v1"]) == "roadielabs"

    def test_gravel_ab_variants_split_evenly_same_subject(self):
        """A/B tests the body only — subject held constant so the split
        isolates one variable. Road stays single-variant (no test power)."""
        variants = SEQUENCES["race_debrief_v1"]["variants"]
        assert set(variants) == {"A", "B"}
        assert variants["A"]["weight"] == variants["B"]["weight"] == 50
        subjects = {v["steps"][0]["subject"] for v in variants.values()}
        assert len(subjects) == 1
        templates = {v["steps"][0]["template"] for v in variants.values()}
        assert templates == {"race_debrief", "race_debrief_minimal"}
        assert set(SEQUENCES["road_race_debrief_v1"]["variants"]) == {"A"}

    def test_all_variant_templates_exist(self):
        from mission_control.config import WEB_TEMPLATES_DIR
        for seq_id in ("race_debrief_v1", "road_race_debrief_v1"):
            for v in SEQUENCES[seq_id]["variants"].values():
                for step in v["steps"]:
                    path = (WEB_TEMPLATES_DIR / "emails" / "sequences"
                            / f"{step['template']}.html")
                    assert path.exists(), f"missing template: {step['template']}"

    def test_not_reachable_from_subscriber_triggers(self):
        for trigger in ("new_subscriber", "prep_kit_download", "quiz_completed"):
            for brand in ("gravelgod", "roadielabs"):
                ids = {s["id"] for s in get_sequences_for_trigger(trigger, brand=brand)}
                assert not any("debrief" in i for i in ids)


class TestRunRaceDebrief:
    def _base_patches(self, dates, enrollments, customer=None):
        return (
            patch("mission_control.services.race_debrief._fetch_dates_sync",
                  return_value=dates),
            patch("mission_control.services.race_debrief.db.select",
                  return_value=enrollments),
            patch("mission_control.services.race_debrief.db.select_one",
                  return_value=customer),
            patch("mission_control.services.race_debrief.db.log_action"),
        )

    def test_enrolls_after_race_with_brand_routing(self):
        today = date(2026, 8, 9)
        dates = {"gravelgod": {"unbound-200": "2026-05-30"},     # 71 days ago
                 "roadielabs": {"mallorca-312": "2026-08-01"}}   # 8 days ago
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
                "mission_control.services.race_debrief.enroll",
                return_value={"id": 1}) as mock_enroll:
            summary = _run(run_race_debrief(today=today))
        assert summary["enrolled"] == 2
        called_ids = {c.args[2] for c in mock_enroll.call_args_list}
        assert called_ids == {"race_debrief_v1", "road_race_debrief_v1"}
        # source_data contract: the template substitutes these directly
        for c in mock_enroll.call_args_list:
            sd = c.kwargs["source_data"]
            assert {"race_name", "race_date", "when_phrase", "brand"} <= set(sd)

    def test_window_edges(self):
        today = date(2026, 8, 9)
        dates = {"gravelgod": {
            "too-fresh": "2026-08-07",     # 2 days — dust not settled
            "too-old": "2025-12-01",       # >180 days — premise gone stale
            "future": "2026-10-01",        # upcoming: infers ~313d ago, still out of window
        }, "roadielabs": {}}
        rows = [
            {"contact_email": f"{slug}@x.com", "contact_name": "X", "status": "completed",
             "source_data": {"race_slug": slug, "brand": "gravelgod"}}
            for slug in ("too-fresh", "too-old", "future")
        ]
        p1, p2, p3, p4 = self._base_patches(dates, rows)
        with p1, p2, p3, p4, patch(
                "mission_control.services.race_debrief.enroll") as mock_enroll:
            summary = _run(run_race_debrief(today=today))
        assert summary["skipped_window"] == 3
        mock_enroll.assert_not_called()

    def test_rolled_date_infers_previous_edition(self):
        """Catalog cleanup rolled past races to their 2027 dates, which
        would orphan those leads forever. The job infers the previous
        edition and debriefs with a month-free phrase."""
        today = date(2026, 8, 12)
        dates = {"gravelgod": {
            "unbound-200": "2027-06-05",   # rolled; prev edition ~68d ago
            "next-spring": "2026-10-01",   # genuinely upcoming — must NOT infer
        }, "roadielabs": {}}
        rows = [
            {"contact_email": "rolled@x.com", "contact_name": "R", "status": "completed",
             "source_data": {"race_slug": "unbound-200", "race_name": "Unbound 200",
                             "brand": "gravelgod"}},
            {"contact_email": "upcoming@x.com", "contact_name": "U", "status": "completed",
             "source_data": {"race_slug": "next-spring", "brand": "gravelgod"}},
        ]
        p1, p2, p3, p4 = self._base_patches(dates, rows)
        with p1, p2, p3, p4, patch(
                "mission_control.services.race_debrief.enroll",
                return_value={"id": 1}) as mock_enroll:
            summary = _run(run_race_debrief(today=today))
        assert summary["enrolled"] == 1
        assert summary["enrolled_inferred"] == 1
        assert summary["skipped_window"] == 1
        sd = mock_enroll.call_args.kwargs["source_data"]
        assert sd["when_phrase"] == "this season"
        assert sd["date_inferred"] == "true"

    def test_true_past_date_does_not_get_inferred_phrase(self):
        today = date(2026, 8, 12)
        dates = {"gravelgod": {"watermoo": "2026-08-08"}, "roadielabs": {}}
        rows = [{"contact_email": "raced@x.com", "contact_name": "W", "status": "completed",
                 "source_data": {"race_slug": "watermoo", "brand": "gravelgod"}}]
        p1, p2, p3, p4 = self._base_patches(dates, rows)
        with p1, p2, p3, p4, patch(
                "mission_control.services.race_debrief.enroll",
                return_value={"id": 1}) as mock_enroll:
            summary = _run(run_race_debrief(today=today))
        assert summary["enrolled"] == 1
        assert summary["enrolled_inferred"] == 0
        sd = mock_enroll.call_args.kwargs["source_data"]
        assert sd["when_phrase"] == "the other weekend"
        assert "date_inferred" not in sd

    def test_feb29_rolled_date_does_not_crash(self):
        today = date(2027, 3, 15)
        dates = {"gravelgod": {"leap-race": "2028-02-29"}, "roadielabs": {}}
        rows = [{"contact_email": "leap@x.com", "contact_name": "L", "status": "completed",
                 "source_data": {"race_slug": "leap-race", "brand": "gravelgod"}}]
        p1, p2, p3, p4 = self._base_patches(dates, rows)
        with p1, p2, p3, p4, patch(
                "mission_control.services.race_debrief.enroll",
                return_value={"id": 1}):
            summary = _run(run_race_debrief(today=today))
        assert summary["enrolled"] == 1  # inferred 2027-02-28, 15d ago

    def test_suppressions_and_unknown_brand(self):
        today = date(2026, 8, 9)
        dates = {"gravelgod": {"unbound-200": "2026-05-30"}, "roadielabs": {}}
        rows = [
            # mid-sequence — skipped
            {"contact_email": "busy@x.com", "contact_name": "B", "status": "active",
             "source_data": {"race_slug": "unbound-200", "brand": "gravelgod"}},
            # brand with no debrief sequence — skipped, not KeyError
            {"contact_email": "xc@x.com", "contact_name": "X", "status": "completed",
             "source_data": {"race_slug": "birkie", "brand": "xcskilabs"}},
            # race not in dates file — skipped
            {"contact_email": "tbd@x.com", "contact_name": "T", "status": "completed",
             "source_data": {"race_slug": "no-date-race", "brand": "gravelgod"}},
        ]
        p1, p2, p3, p4 = self._base_patches(dates, rows)
        with p1, p2, p3, p4, patch(
                "mission_control.services.race_debrief.enroll") as mock_enroll:
            summary = _run(run_race_debrief(today=today))
        assert summary["skipped_mid_sequence"] == 1
        assert summary["skipped_no_sequence"] == 1
        assert summary["skipped_no_date"] == 1
        mock_enroll.assert_not_called()

    def test_customer_suppression(self):
        today = date(2026, 8, 9)
        dates = {"gravelgod": {"unbound-200": "2026-05-30"}, "roadielabs": {}}
        rows = [{"contact_email": "cust@x.com", "contact_name": "C", "status": "completed",
                 "source_data": {"race_slug": "unbound-200", "brand": "gravelgod"}}]
        p1, p2, p3, p4 = self._base_patches(dates, rows,
                                            customer={"plan_status": "delivered"})
        with p1, p2, p3, p4, patch(
                "mission_control.services.race_debrief.enroll") as mock_enroll:
            summary = _run(run_race_debrief(today=today))
        assert summary["skipped_customer"] == 1
        mock_enroll.assert_not_called()

    def test_daily_cap_defers_backlog(self):
        """The backlog (~66 leads) must drain over days, not land in one
        inbox-flooding batch — every reply is handled personally."""
        today = date(2026, 8, 9)
        dates = {"gravelgod": {"unbound-200": "2026-05-30"}, "roadielabs": {}}
        rows = [
            {"contact_email": f"lead{i}@x.com", "contact_name": "L", "status": "completed",
             "source_data": {"race_slug": "unbound-200", "brand": "gravelgod"}}
            for i in range(20)
        ]
        p1, p2, p3, p4 = self._base_patches(dates, rows)
        with p1, p2, p3, p4, patch(
                "mission_control.services.race_debrief.enroll",
                return_value={"id": 1}) as mock_enroll:
            summary = _run(run_race_debrief(today=today))
        assert summary["enrolled"] == 12
        assert summary["capped"] is True
        assert mock_enroll.call_count == 12

    def test_aborts_and_surfaces_when_no_dates(self):
        p1, p2, p3, p4 = self._base_patches({"gravelgod": {}, "roadielabs": {}}, [])
        with p1, p2, p3, p4 as mock_log, patch(
                "mission_control.services.race_debrief.enroll") as mock_enroll:
            summary = _run(run_race_debrief(today=date(2026, 8, 9)))
        assert summary["enrolled"] == 0
        mock_enroll.assert_not_called()
        actions = {c.args[0] for c in mock_log.call_args_list}
        assert "race_debrief_aborted" in actions
