"""Send-time race freshness: a step whose copy depends on its race being
upcoming (or having passed) is re-checked against the race's current
published date right before it sends, and skipped, audit-logged, when the
premise no longer holds (sequence_engine._race_premise_failure)."""

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

import mission_control.services.race_countdown as rc
import mission_control.services.sequence_engine as se
from mission_control.sequences import SEQUENCES
from mission_control.tests.conftest import make_enrollment

SLUG = "test-race"


def _today():
    return datetime.now(timezone.utc).date()


def _in_days(days: int) -> str:
    return (_today() + timedelta(days=days)).isoformat()


@pytest.fixture
def race_dates():
    """Set the published race dates the check reads (per brand), restoring
    the process cache afterwards."""
    with patch.dict(rc._dates_cache, {}, clear=True):
        def _set(brand="gravelgod", **slug_dates):
            rc._dates_cache[brand] = dict(slug_dates)
        yield _set


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(se, "RESEND_API_KEY", "test-key")
    monkeypatch.setattr(se, "_send_email_sync",
                        lambda to, subject, html, *a: out.append(subject) or "rs-1")
    return out


def _run(fake_db, **enrollment):
    row = make_enrollment(**enrollment)
    fake_db.store["gg_sequence_enrollments"].append(row)
    assert asyncio.run(se._send_next_step(row)) is True
    return row


def _skips(fake_db):
    return [r for r in fake_db.store["gg_audit_log"] if r["action"] == "sequence_step_skipped"]


def _debrief(**source_data):
    return {"sequence_id": "race_debrief_v1", "variant": "A", "source": "race_debrief",
            "source_data": {"race_slug": SLUG, "race_name": "Test Race", **source_data}}


def _countdown_16(**source_data):
    return {"sequence_id": "race_countdown_16_v1", "variant": "A", "source": "race_countdown",
            "source_data": {"race_slug": SLUG, "race_name": "Test Race", "weeks_out": "16",
                            **source_data}}


def _kit_pitch():
    # nurture_v1 variant C, step 1 = kit_pitch (day 7), step 2 = kit_followup (day 11)
    return {"sequence_id": "nurture_v1", "variant": "C", "current_step": 1,
            "source": "prep_kit_gate",
            "source_data": {"race_slug": SLUG, "race_name": "Test Race"}}


class TestUpcoming:
    def test_pitch_sends_while_race_is_ahead(self, fake_db, race_dates, sent):
        race_dates(**{SLUG: _in_days(60)})
        row = _run(fake_db, **_kit_pitch())
        assert sent == ["the plan, for Test Race"]
        assert row["current_step"] == 2
        assert not _skips(fake_db)

    def test_pitch_skipped_once_race_has_passed(self, fake_db, race_dates, sent):
        race_dates(**{SLUG: _in_days(-2)})
        row = _run(fake_db, **_kit_pitch())
        assert sent == []
        # skipped like a send: on to the follow-up, four days on
        assert row["current_step"] == 2
        assert row["status"] == "active"
        next_send = datetime.fromisoformat(row["next_send_at"])
        assert abs((next_send - datetime.now(timezone.utc)) - timedelta(days=4)) < timedelta(seconds=5)
        [log] = _skips(fake_db)
        assert log["entity_id"] == row["id"]
        assert "nurture_v1 step 1 (kit_pitch) not sent" in log["details"]
        assert "not in the future" in log["details"]

    def test_race_day_itself_is_not_upcoming(self, fake_db, race_dates, sent):
        race_dates(**{SLUG: _in_days(0)})
        _run(fake_db, **_kit_pitch())
        assert sent == []
        assert _skips(fake_db)


class TestPassed:
    def test_debrief_sends_after_the_race(self, fake_db, race_dates, sent):
        race_dates(**{SLUG: _in_days(-5)})
        row = _run(fake_db, **_debrief(race_date=_in_days(-5)))
        assert sent == ["how'd Test Race go?"]
        assert row["status"] == "completed"
        assert not _skips(fake_db)

    def test_debrief_skipped_when_race_is_still_ahead(self, fake_db, race_dates, sent):
        # enrolled on a date that has since been corrected to a later one
        race_dates(**{SLUG: _in_days(30)})
        row = _run(fake_db, **_debrief(race_date=_in_days(-5)))
        assert sent == []
        assert row["status"] == "completed"  # one-step sequence: done, nothing sent
        assert not fake_db.store["gg_sequence_sends"]
        [log] = _skips(fake_db)
        assert "race_debrief_v1 step 0 (race_debrief) not sent" in log["details"]
        assert "has not passed" in log["details"]

    def test_nps_did_it_happen_skipped_before_the_race(self, fake_db, race_dates, sent):
        race_dates(**{SLUG: _in_days(40)})
        row = _run(fake_db, sequence_id="post_purchase_v1", current_step=4,
                   source="plan_purchased",
                   source_data={"race_slug": SLUG, "race_name": "Test Race"})
        assert sent == []
        assert row["status"] == "completed"
        assert "(nps_request) not sent" in _skips(fake_db)[0]["details"]

    def test_inferred_previous_edition_still_sends(self, fake_db, race_dates, sent):
        # race_debrief enrolls on the previous edition when the catalog has
        # already rolled the date forward to the next one
        race_dates(**{SLUG: _in_days(300)})
        _run(fake_db, **_debrief(race_date=_in_days(300), date_inferred="true"))
        assert sent == ["how'd Test Race go?"]

    def test_catalog_rolled_to_next_edition_still_sends(self, fake_db, race_dates, sent):
        race_dates(**{SLUG: _in_days(355)})
        _run(fake_db, **_debrief(race_date=_in_days(-10)))
        assert sent == ["how'd Test Race go?"]

    def test_postponed_race_is_not_a_next_edition(self, fake_db, race_dates, sent):
        race_dates(**{SLUG: _in_days(30)})
        _run(fake_db, **_debrief(race_date=_in_days(-10)))
        assert sent == []


class TestWeeksOutDrift:
    @pytest.mark.parametrize("days", [16 * 7, 15 * 7, 17 * 7])
    def test_countdown_sends_within_a_week_of_its_number(self, fake_db, race_dates, sent, days):
        race_dates(**{SLUG: _in_days(days)})
        _run(fake_db, **_countdown_16())
        assert sent == ["16 weeks to Test Race"]

    @pytest.mark.parametrize("days", [13 * 7, 15 * 7 - 1, 17 * 7 + 1])
    def test_countdown_skipped_when_its_number_is_off(self, fake_db, race_dates, sent, days):
        race_dates(**{SLUG: _in_days(days)})
        row = _run(fake_db, **_countdown_16())
        assert sent == []
        assert row["status"] == "completed"
        [log] = _skips(fake_db)
        assert "copy says 16 weeks out" in log["details"]

    def test_eight_week_countdown_checks_eight(self, fake_db, race_dates, sent):
        race_dates("roadielabs", **{SLUG: _in_days(8 * 7)})
        _run(fake_db, sequence_id="road_race_countdown_8_v1", source="race_countdown",
             source_data={"race_slug": SLUG, "race_name": "Test Race"})
        assert sent == ["8 weeks to Test Race"]


class TestMissingDate:
    def test_race_without_a_published_date_is_not_sent(self, fake_db, race_dates, sent):
        race_dates(**{"another-race": _in_days(-5)})
        _run(fake_db, **_debrief())
        assert sent == []
        assert "has no published date" in _skips(fake_db)[0]["details"]

    def test_unparseable_date_is_not_sent(self, fake_db, race_dates, sent):
        race_dates(**{SLUG: "2026: October TBD"})
        _run(fake_db, **_debrief())
        assert sent == []
        assert "is not a date" in _skips(fake_db)[0]["details"]

    def test_enrollment_without_race_slug_is_not_sent(self, fake_db, race_dates, sent):
        race_dates(**{SLUG: _in_days(-5)})
        _run(fake_db, sequence_id="race_debrief_v1", source="race_debrief",
             source_data={"race_name": "Test Race"})
        assert sent == []
        assert "no race_slug" in _skips(fake_db)[0]["details"]

    def test_no_dates_loaded_for_the_brand_is_not_sent(self, fake_db, race_dates, sent):
        race_dates("roadielabs", **{SLUG: _in_days(-5)})  # other brand only
        _run(fake_db, **_debrief())
        assert sent == []
        assert "no gravelgod race dates are loaded" in _skips(fake_db)[0]["details"]

    def test_falls_back_to_the_stored_copy_after_a_restart(self, fake_db, race_dates, sent):
        # empty process cache (a fresh deploy): the gg_settings copy is used
        fake_db.store["gg_settings"].append({"key": "race_dates_gravelgod", "value": json.dumps(
            {"fetched_at": "2026-01-01T00:00:00+00:00", "dates": {SLUG: _in_days(-5)}})})
        _run(fake_db, **_debrief())
        assert sent == ["how'd Test Race go?"]

    def test_unknown_premise_is_not_sent(self, fake_db, race_dates):
        race_dates(**{SLUG: _in_days(-5)})
        step = {"template": "x", "subject": "x", "race_premise": "soon"}
        failure = se._race_premise_failure(step, {"source_data": {"race_slug": SLUG}}, "gravelgod")
        assert "unknown race_premise" in failure


class TestNoPremise:
    def test_step_without_premise_ignores_race_dates(self, fake_db, race_dates, sent):
        # no dates loaded at all, and the race in source_data long gone:
        # a step that declares no premise sends exactly as before
        row = _run(fake_db, sequence_id="welcome_v1", variant="A", source="race_profile",
                   source_data={"race_slug": SLUG, "race_name": "Test Race",
                                "race_date": _in_days(-400)})
        assert sent == ["getting ready for one of these?"]
        assert row["current_step"] == 1
        assert not _skips(fake_db)

    def test_premise_check_returns_none_without_premise(self, race_dates):
        step = {"template": "x", "subject": "x"}
        assert se._race_premise_failure(step, {"source_data": {}}, "gravelgod") is None


class TestResendFirstStep:
    def test_resend_refused_when_premise_fails(self, fake_db, race_dates, sent):
        race_dates(**{SLUG: _in_days(30)})
        row = make_enrollment(**_debrief(), status="completed", current_step=1)
        fake_db.store["gg_sequence_enrollments"].append(row)
        fake_db.store["gg_sequence_sends"].append(
            {"id": "s1", "enrollment_id": row["id"], "step_index": 0, "status": "sent"})
        assert asyncio.run(se.resend_first_step(row)) is False
        assert sent == []
        assert "not resent" in _skips(fake_db)[0]["details"]


class TestDeclaredPremises:
    """The premise sits next to the copy it protects."""

    EXPECTED = {
        ("race_countdown_16_v1", "countdown_16w"): "upcoming",
        ("race_countdown_8_v1", "countdown_8w"): "upcoming",
        ("road_race_countdown_16_v1", "road_countdown_16w"): "upcoming",
        ("road_race_countdown_8_v1", "road_countdown_8w"): "upcoming",
        ("xc_race_countdown_16_v1", "xc_countdown_16w"): "upcoming",
        ("xc_race_countdown_8_v1", "xc_countdown_8w"): "upcoming",
        ("race_debrief_v1", "race_debrief"): "passed",
        ("race_debrief_v1", "race_debrief_minimal"): "passed",
        ("road_race_debrief_v1", "road_race_debrief"): "passed",
        ("xc_race_debrief_v1", "xc_race_debrief"): "passed",
        ("post_purchase_v1", "nps_request"): "passed",
        ("road_post_purchase_v1", "road_nps_request"): "passed",
        ("nurture_v1", "kit_pitch"): "upcoming",
        ("nurture_v1", "kit_followup"): "upcoming",
    }

    def _steps(self):
        for seq in SEQUENCES.values():
            for variant in seq["variants"].values():
                for step in variant["steps"]:
                    yield seq["id"], step

    def test_expected_steps_carry_their_premise(self):
        declared = {(sid, s["template"]): s.get("race_premise") for sid, s in self._steps()}
        for key, premise in self.EXPECTED.items():
            assert declared.get(key) == premise, key

    def test_no_other_step_declares_one(self):
        others = {(sid, s["template"]) for sid, s in self._steps()
                  if s.get("race_premise") and (sid, s["template"]) not in self.EXPECTED}
        assert not others

    def test_every_premise_is_known(self):
        for _sid, step in self._steps():
            assert step.get("race_premise") in (None, *se._RACE_PREMISES)

    def test_countdown_weeks_match_their_subject(self):
        for sid, step in self._steps():
            m = re.match(r"^(\d+) weeks to ", step["subject"])
            if m:
                assert step.get("race_premise") == "upcoming", sid
                assert step.get("race_weeks_out") == int(m.group(1)), sid
