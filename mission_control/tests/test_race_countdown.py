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

    def test_a_coached_or_leaving_athlete_is_never_a_candidate(self):
        """Intake strips race context from a season review and an exit; a
        record stored before it did (or merged from one) still carries a
        race_slug, and must not put the athlete in countdown or debrief."""
        rows = [
            {"contact_email": "b@x.com", "contact_name": "B", "status": "completed",
             "source": "athlete_review",
             "source_data": {"race_slug": "unbound-200", "brand": "gravelgod"}},
            {"contact_email": "e@x.com", "contact_name": "E", "status": "completed",
             "source": "athlete_exit",
             "source_data": {"race_slug": "unbound-200", "brand": "gravelgod"}},
            {"contact_email": "l@x.com", "contact_name": "L", "status": "completed",
             "source": "race_profile",
             "source_data": {"race_slug": "unbound-200", "brand": "gravelgod"}},
        ]
        contacts, _ = gather_candidates(rows)
        assert set(contacts) == {"l@x.com"}

    def test_brand_defaults_to_gravel(self):
        rows = [{"contact_email": "c@x.com", "contact_name": "C", "status": "completed",
                 "source_data": {"race_slug": "some-race"}}]
        contacts, _ = gather_candidates(rows)
        assert contacts["c@x.com"]["brand"] == "gravelgod"
        assert contacts["c@x.com"]["race_name"] == "some-race"  # falls back to slug


class TestCountdownSequences:
    def test_six_sequences_registered_and_brand_scoped(self):
        assert sequence_brand(SEQUENCES["race_countdown_16_v1"]) == "gravelgod"
        assert sequence_brand(SEQUENCES["road_race_countdown_8_v1"]) == "roadielabs"
        assert sequence_brand(SEQUENCES["xc_race_countdown_16_v1"]) == "xcskilabs"

    def test_not_reachable_from_subscriber_triggers(self):
        for trigger in ("new_subscriber", "prep_kit_download", "quiz_completed"):
            for brand in ("gravelgod", "roadielabs", "xcskilabs"):
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

    def test_enrolls_xc_in_both_windows(self):
        today = date(2026, 7, 1)
        dates = {"xcskilabs": {"birkie": "2026-10-21", "vasaloppet": "2026-08-26"}}
        rows = [
            {"contact_email": "x16@x.com", "contact_name": "X", "status": "completed",
             "source_data": {"race_slug": "birkie", "race_name": "Birkie", "brand": "xcskilabs"}},
            {"contact_email": "x8@x.com", "contact_name": "Y", "status": "completed",
             "source_data": {"race_slug": "vasaloppet", "race_name": "Vasaloppet", "brand": "xcskilabs"}},
        ]
        p1, p2, p3, p4 = self._base_patches(dates, rows)
        with p1, p2, p3, p4, patch("mission_control.services.race_countdown.enroll",
                                   return_value={"id": 1}) as mock_enroll:
            summary = _run(run_race_countdown(today=today))
        assert summary["enrolled"] == 2
        assert {c.args[2] for c in mock_enroll.call_args_list} == {
            "xc_race_countdown_16_v1", "xc_race_countdown_8_v1",
        }

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
        with p1, p2, p3, p4 as mock_log, patch(
                "mission_control.services.race_countdown.enroll") as mock_enroll:
            summary = _run(run_race_countdown(today=date(2026, 7, 1)))
        assert summary["enrolled"] == 0
        mock_enroll.assert_not_called()
        # The abort must surface in the audit log, not just process logs —
        # this exact path failed silently every day for weeks.
        actions = {c.args[0] for c in mock_log.call_args_list}
        assert "race_countdown_aborted" in actions


class TestFetchDatesUserAgent:
    def test_fetch_sends_identifying_user_agent(self):
        """SiteGround 403s Python-urllib's default UA. The fetch must send
        an identifying UA or the job aborts daily with an empty cache —
        which is exactly what happened in prod from the day this shipped."""
        from mission_control.services import race_countdown as rc

        captured = []

        class _Resp:
            def read(self):
                return b"{}"
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None):
            captured.append(req)
            return _Resp()

        with patch("mission_control.services.race_countdown.urllib.request.urlopen",
                   side_effect=fake_urlopen):
            rc._fetch_dates_sync()

        assert captured, "fetch made no requests"
        import urllib.request as ur
        for req in captured:
            assert isinstance(req, ur.Request), "must pass a Request (with headers), not a bare URL"
            ua = req.get_header("User-agent", "")
            assert ua == rc._USER_AGENT
            assert not ua.lower().startswith("python-urllib")


class TestFetchErrorSurfacing:
    def test_probe_names_the_exception_per_brand(self):
        """A fetch that fails in prod but passes locally is undiagnosable
        from the audit log unless the probe records the actual exception."""
        from mission_control.services import race_countdown as rc

        def fake_urlopen(req, timeout=None):
            raise OSError("HTTP Error 403: Forbidden")

        rc._dates_cache.clear()
        rc._last_errors.clear()
        with patch("mission_control.services.race_countdown.urllib.request.urlopen",
                   side_effect=fake_urlopen):
            detail = rc.probe_race_dates()
        assert "FAILED" in detail
        assert "403" in detail
        for brand in rc.RACE_DATES_URLS:
            assert brand in detail

    def test_probe_reports_ok_with_counts_and_clears_errors(self):
        from mission_control.services import race_countdown as rc

        rc._dates_cache.clear()
        rc._last_errors["gravelgod"] = "stale error from a previous pass"

        class _Resp:
            def read(self):
                return b'{"unbound-200": "2027-06-05"}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with patch("mission_control.services.race_countdown.urllib.request.urlopen",
                   return_value=_Resp()):
            detail = rc.probe_race_dates()
        assert "FAILED" not in detail
        assert "ok (1 entries)" in detail
        assert not rc._last_errors

    def test_success_writes_db_last_good_copy(self):
        from mission_control.services import race_countdown as rc

        rc._dates_cache.clear()
        rc._last_errors.clear()

        class _Resp:
            def read(self):
                return b'{"unbound-200": "2027-06-05"}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with patch("mission_control.services.race_countdown.urllib.request.urlopen",
                   return_value=_Resp()), \
             patch("mission_control.services.race_countdown.db.set_setting") as mock_set:
            rc._fetch_dates_sync()
        keys = {c.args[0] for c in mock_set.call_args_list}
        assert keys == {f"race_dates_{b}" for b in rc.RACE_DATES_URLS}
        import json as _json
        stored = _json.loads(mock_set.call_args_list[0].args[1])
        assert stored["dates"] == {"unbound-200": "2027-06-05"}
        assert "fetched_at" in stored

    def test_fetch_failure_falls_back_to_db_copy(self):
        """Railway restarts on every push, so the in-memory cache is often
        empty when a job fires. A flaky fetch must fall back to the
        gg_settings copy instead of aborting the run."""
        import json as _json
        from mission_control.services import race_countdown as rc

        rc._dates_cache.clear()
        rc._last_errors.clear()
        stored = _json.dumps({"fetched_at": "2026-08-11T14:00:00+00:00",
                              "dates": {"unbound-200": "2027-06-05"}})

        def fake_urlopen(req, timeout=None):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

        with patch("mission_control.services.race_countdown.urllib.request.urlopen",
                   side_effect=fake_urlopen), \
             patch("mission_control.services.race_countdown.db.get_setting",
                   return_value=stored):
            dates = rc._fetch_dates_sync()
        for brand in rc.RACE_DATES_URLS:
            assert dates[brand] == {"unbound-200": "2027-06-05"}
            assert "using DB copy from 2026-08-11" in rc._last_errors[brand]
        rc._dates_cache.clear()
        rc._last_errors.clear()

    def test_fetch_failure_with_no_db_copy_still_aborts(self):
        from mission_control.services import race_countdown as rc

        rc._dates_cache.clear()
        rc._last_errors.clear()
        with patch("mission_control.services.race_countdown.urllib.request.urlopen",
                   side_effect=OSError("HTTP Error 403: Forbidden")), \
             patch("mission_control.services.race_countdown.db.get_setting",
                   return_value=""):
            dates = rc._fetch_dates_sync()
        assert not any(dates.values())
        rc._last_errors.clear()

    def test_db_cache_write_failure_does_not_break_fetch(self):
        from mission_control.services import race_countdown as rc

        rc._dates_cache.clear()
        rc._last_errors.clear()

        class _Resp:
            def read(self):
                return b'{"a": "2026-09-01"}'
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with patch("mission_control.services.race_countdown.urllib.request.urlopen",
                   return_value=_Resp()), \
             patch("mission_control.services.race_countdown.db.set_setting",
                   side_effect=RuntimeError("db down")):
            dates = rc._fetch_dates_sync()
        for brand in rc.RACE_DATES_URLS:
            assert dates[brand] == {"a": "2026-09-01"}
        assert not rc._last_errors
        rc._dates_cache.clear()

    def test_abort_audit_entry_includes_fetch_errors(self):
        from mission_control.services import race_countdown as rc

        rc._last_errors.clear()
        rc._last_errors["gravelgod"] = "HTTPError('403: Forbidden')"
        with patch("mission_control.services.race_countdown._fetch_dates_sync",
                   return_value={"gravelgod": {}, "roadielabs": {}}), \
             patch("mission_control.services.race_countdown.db.select", return_value=[]), \
             patch("mission_control.services.race_countdown.db.log_action") as mock_log:
            _run(run_race_countdown(today=date(2026, 7, 1)))
        rc._last_errors.clear()
        abort = [c for c in mock_log.call_args_list
                 if c.args[0] == "race_countdown_aborted"]
        assert abort and "403" in abort[0].args[3]


# ── One bad published date never takes the run down (2026-09-30) ──
# xcskilabs.com/race-dates.json serves the date_specific display format
# ("2026: January 18"), and the first one crashed the whole countdown job
# with "Invalid isoformat string", for every brand.


def _row(email, slug, brand):
    return {"contact_email": email, "contact_name": email.split("@")[0], "status": "completed",
            "source_data": {"race_slug": slug, "race_name": slug.title(), "brand": brand}}


class TestParseRaceDate:
    def test_iso_and_the_prefixed_display_format(self):
        from mission_control.services.race_countdown import parse_race_date
        assert parse_race_date("2026-10-21") == date(2026, 10, 21)
        assert parse_race_date("2026: February 28") == date(2026, 2, 28)
        assert parse_race_date("2026: Sep 27") == date(2026, 9, 27)
        # multi-day: the start day is what the countdown needs
        assert parse_race_date("2026: March 26-28") == date(2026, 3, 26)
        assert parse_race_date("2026: January 31 (Skate), February 1 (Classic)") == date(2026, 1, 31)

    def test_anything_else_is_not_a_date_and_never_raises(self):
        from mission_control.services.race_countdown import parse_race_date
        for value in ("2026: Cancelled (returning 2027)", "2026: January-February series",
                      "2026: October TBD", "2026: February 30", "February 28", "TBD", "",
                      None, [], {"date": "2026-10-21"}):
            assert parse_race_date(value) is None, value


class TestBadDatesNeverAbortTheRun:
    def test_a_mixed_feed_still_enrolls_every_good_race(self, caplog):
        today = date(2026, 7, 1)
        dates = {
            "gravelgod": {"unbound-200": "2026-10-21", "broken": "not a date"},
            "roadielabs": {"mallorca-312": "2026-08-26"},
            # the live XC shape, a bad one listed first
            "xcskilabs": {"cancelled": "2026: Cancelled (returning 2027)",
                          "birkie": "2026: October 21"},
        }
        rows = [_row("bad@x.com", "cancelled", "xcskilabs"),
                _row("junk@x.com", "broken", "gravelgod"),
                _row("g@x.com", "unbound-200", "gravelgod"),
                _row("r@x.com", "mallorca-312", "roadielabs"),
                _row("x@x.com", "birkie", "xcskilabs")]
        with patch("mission_control.services.race_countdown._fetch_dates_sync", return_value=dates), \
             patch("mission_control.services.race_countdown.db.select", return_value=rows), \
             patch("mission_control.services.race_countdown.db.select_one", return_value=None), \
             patch("mission_control.services.race_countdown.db.log_action"), \
             patch("mission_control.services.race_countdown.enroll", return_value={"id": 1}) as mock_enroll, \
             caplog.at_level("WARNING", logger="mission_control.services.race_countdown"):
            summary = _run(run_race_countdown(today=today))
        assert summary["enrolled"] == 3
        assert summary["skipped_bad_date"] == 2
        assert {c.args[0] for c in mock_enroll.call_args_list} == {"g@x.com", "r@x.com", "x@x.com"}
        xc = next(c for c in mock_enroll.call_args_list if c.args[0] == "x@x.com")
        assert xc.args[2] == "xc_race_countdown_16_v1"
        assert xc.kwargs["source_data"]["race_date"] == "2026-10-21"  # ISO for the templates
        warnings = [r.getMessage() for r in caplog.records if "not dates" in r.getMessage()]
        assert len(warnings) == 1, warnings  # one aggregated warning, not one per race
        assert "skipped 2 race date(s)" in warnings[0] and "xcskilabs/cancelled" in warnings[0]

    def test_one_contact_failing_to_enroll_does_not_stop_the_rest(self):
        today = date(2026, 7, 1)
        dates = {"gravelgod": {"unbound-200": "2026-10-21"}}
        rows = [_row("first@x.com", "unbound-200", "gravelgod"),
                _row("second@x.com", "unbound-200", "gravelgod")]

        def flaky_enroll(email, *a, **k):
            if email == "first@x.com":
                raise RuntimeError("supabase timeout")
            return {"id": 1}

        with patch("mission_control.services.race_countdown._fetch_dates_sync", return_value=dates), \
             patch("mission_control.services.race_countdown.db.select", return_value=rows), \
             patch("mission_control.services.race_countdown.db.select_one", return_value=None), \
             patch("mission_control.services.race_countdown.db.log_action"), \
             patch("mission_control.services.race_countdown.enroll", side_effect=flaky_enroll):
            summary = _run(run_race_countdown(today=today))
        assert summary["errors"] == 1 and summary["enrolled"] == 1


class TestFetchSaysWhatCameBack:
    """MC logged 'Expecting value: line 1 column 1 (char 0)' for all three
    brands on 2026-09-30: a 2xx that wasn't JSON. The error now carries the
    status, content type and the start of the body."""

    class _Resp:
        def __init__(self, body, status=200, ctype="application/json"):
            self._body, self.status = body, status
            self.headers = {"Content-Type": ctype}

        def read(self):
            return self._body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fetch(self, **urlopen):
        from mission_control.services import race_countdown as rc
        rc._dates_cache.clear()
        rc._last_errors.clear()
        with patch("mission_control.services.race_countdown.urllib.request.urlopen", **urlopen), \
             patch("mission_control.services.race_countdown.db.get_setting", return_value=""), \
             patch("mission_control.services.race_countdown.db.set_setting"):
            rc._fetch_dates_sync()
        errors = dict(rc._last_errors)
        rc._dates_cache.clear()
        rc._last_errors.clear()
        return errors

    def test_a_challenge_page_is_named_with_status_type_and_body(self):
        page = (b'<html><head><meta http-equiv="refresh" content="0;/.well-known/sgcaptcha/'
                b'?r=%2Fwp-content%2Fuploads%2Frace-dates.json"></head></html>')
        errors = self._fetch(return_value=self._Resp(page, status=202, ctype="text/html"))
        for brand, err in errors.items():
            assert "Expecting value" in err
            assert "HTTP 202" in err and "text/html" in err
            assert "sgcaptcha" in err, err
        assert set(errors) == set(__import__(
            "mission_control.services.race_countdown", fromlist=["RACE_DATES_URLS"]).RACE_DATES_URLS)

    def test_an_http_error_is_named_with_its_body_too(self):
        import io
        import urllib.error

        def forbidden(req, timeout=None):
            raise urllib.error.HTTPError(req.full_url, 403, "Forbidden",
                                         {"Content-Type": "text/html"},
                                         io.BytesIO(b"403 - Forbidden | Access to this page is forbidden."))

        errors = self._fetch(side_effect=forbidden)
        assert errors and all("HTTP 403" in e and "Access to this page" in e for e in errors.values())

    def test_a_json_array_is_not_a_dates_map(self):
        errors = self._fetch(return_value=self._Resp(b'["2026-10-21"]'))
        assert errors and all("not a JSON object" in e for e in errors.values())

    def test_sends_a_browser_user_agent_and_asks_for_json(self):
        from mission_control.services import race_countdown as rc
        seen = []

        def capture(req, timeout=None):
            seen.append(req)
            return self._Resp(b'{"unbound-200": "2026-10-21"}')

        assert not self._fetch(side_effect=capture)
        for req in seen:
            ua = req.get_header("User-agent")
            assert ua.startswith("Mozilla/5.0 (") and "Chrome/" in ua
            # SiteGround 403s the bot-style "Mozilla/5.0 (compatible; ...)" shape
            assert "compatible;" not in ua and "GG-MissionControl" in ua
            assert req.get_header("Accept") == "application/json"
        assert len(seen) == len(rc.RACE_DATES_URLS)
