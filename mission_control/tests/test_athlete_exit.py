"""The athlete exit survey (/coaching/exit/, source=athlete_exit).

A leaving athlete is not a lead. Their answers are stored on an
athlete_exit_v1 enrollment like a season review's, they get one receipt, and
nothing else: no nurture, no deal, no Gmail lead sync, no race countdown. The
last class carries one real page submission through the real worker into
this router and out as Matti's alert and the athlete's receipt, and checks
that no answer is dropped on the way (the handoff's two-whitelists bug).
"""
from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mission_control.sequences import SEQUENCES, get_sequences_for_trigger

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_season_review import answer_keys  # noqa: E402
from season_review_variants import EXIT  # noqa: E402

SUBMISSION = json.loads((ROOT / "tests" / "fixtures" / "exit_survey_submission.json").read_text())
ANSWERS = SUBMISSION["goal_answers"]
EMAIL = SUBMISSION["email"]


@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch):
    """Nothing in these tests reaches Resend (Mission Control now sends a
    backup alert on every new exit). Tests that read the mail re-patch this."""
    import mission_control.services.sequence_engine as se
    monkeypatch.setattr(se, "_send_email_sync", lambda *a, **k: "rs-test")


def _post(client, body):
    return client.post("/webhooks/subscriber", json=body,
                       headers={"Authorization": "Bearer test-secret-123"})


def _exit_body(answers=None, **extra):
    return {"email": EMAIL, "name": SUBMISSION["name"], "athlete": SUBMISSION["athlete"],
            "source": "athlete_exit", "brand": "gravelgod",
            "goal_answers": dict(ANSWERS if answers is None else answers), **extra}


def _enrollments(fake_db, email=EMAIL):
    return [e for e in fake_db.store["gg_sequence_enrollments"] if e["contact_email"] == email]


def _capture_sends(monkeypatch):
    import mission_control.services.sequence_engine as se
    sent = []
    monkeypatch.setattr(se, "RESEND_API_KEY", "test-key")
    monkeypatch.setattr(se, "_send_email_sync",
                        lambda to, subject, html, *a: sent.append({"to": to, "subject": subject, "html": html}) or "rs-1")
    return sent


def _send_receipt(enrollment, monkeypatch):
    import mission_control.services.sequence_engine as se
    sent = _capture_sends(monkeypatch)
    assert asyncio.run(se._send_next_step(enrollment))
    return sent


class TestSequence:
    def test_one_receipt_same_day(self):
        seqs = get_sequences_for_trigger("athlete_exit", "gravelgod")
        assert [s["id"] for s in seqs] == ["athlete_exit_v1"]
        steps = seqs[0]["variants"]["A"]["steps"]
        assert steps == [{"delay_days": 0, "template": "athlete_exit_receipt", "subject": "got it"}]

    def test_no_other_brand_or_trigger_reaches_it(self):
        assert get_sequences_for_trigger("athlete_exit", "roadielabs") == []
        assert [s for s in SEQUENCES.values() if s.get("trigger") == "athlete_exit"] == [SEQUENCES["athlete_exit_v1"]]

    def test_receipt_template_exists(self):
        assert (ROOT / "mission_control" / "templates" / "emails" / "sequences"
                / "athlete_exit_receipt.html").exists()

    def test_transactional_in_the_engine_and_the_lead_bridge(self):
        from mission_control.services import lead_nurture, sequence_engine
        assert "athlete_exit" in sequence_engine._POST_PURCHASE_TRIGGERS
        assert "athlete_exit" in lead_nurture._POST_PURCHASE_TRIGGERS


class TestStorage:
    def test_every_field_on_the_form_arrives_stored(self, client, fake_db):
        """One key per input on the page, straight from the variant, so a new
        question cannot be added without this noticing a whitelist drop."""
        keys = answer_keys(EXIT)
        assert set(keys) == set(ANSWERS)
        resp = _post(client, _exit_body({k: ANSWERS[k] for k in keys}))
        assert resp.status_code == 200
        assert resp.json()["enrolled"] == ["athlete_exit_v1"]
        stored = _enrollments(fake_db)[0]["source_data"]["goal_answers"]
        missing = [k for k in keys if stored.get(k) != ANSWERS[k]]
        assert missing == [], f"dropped or changed on the way in: {missing}"

    def test_athlete_tag_is_stored_like_a_season_review(self, client, fake_db):
        _post(client, _exit_body())
        row = _enrollments(fake_db)[0]
        assert row["source"] == "athlete_exit"
        assert row["source_data"]["athlete"] == "test-rider-a"
        assert row["contact_name"] == "Test Rider A"

    def test_no_poster_token_so_nothing_to_prefill(self, client, fake_db):
        resp = _post(client, _exit_body())
        sd = _enrollments(fake_db)[0]["source_data"]
        assert "poster_token" not in sd and "poster_url" not in sd
        assert "poster_token" not in resp.json()

    def test_no_lead_context_is_kept(self, client, fake_db):
        _post(client, _exit_body(race_slug="unbound-200", race_name="Unbound 200",
                                 offer_variant="A", entry_src="race", goal_type="finish",
                                 guide_chapter="Race Selection", viewed_races=["Unbound"]))
        sd = _enrollments(fake_db)[0]["source_data"]
        for key in ("race_slug", "race_name", "prep_kit_url", "offer_variant", "entry_src",
                    "goal_type", "guide_chapter", "wb_guide", "viewed_races", "wb_trail",
                    "wb_race", "any_context", "goal_line", "inner_obstacle"):
            assert key not in sd, key

    def test_junk_keys_and_values_are_dropped(self, client, fake_db):
        _post(client, _exit_body(dict(ANSWERS, **{"Bad Key": "x", "nested": {"a": 1}, "blank": "  "})))
        stored = _enrollments(fake_db)[0]["source_data"]["goal_answers"]
        assert not {"Bad Key", "nested", "blank"} & set(stored)


class TestNotAMarketingContact:
    def test_no_deal_is_opened(self, client, fake_db):
        _post(client, _exit_body())
        assert fake_db.store.get("gg_deals", []) == []

    def test_enrolls_in_nothing_else(self, client, fake_db):
        _post(client, _exit_body())
        assert [e["sequence_id"] for e in _enrollments(fake_db)] == ["athlete_exit_v1"]

    def test_an_unsubscribed_athlete_still_gets_stored(self, client, fake_db):
        fake_db.store["gg_sequence_enrollments"].append({
            "id": "old-1", "sequence_id": "welcome_v1", "contact_email": EMAIL,
            "status": "unsubscribed", "source": "exit_intent", "source_data": {},
        })
        assert _post(client, _exit_body()).json()["enrolled"] == ["athlete_exit_v1"]

    def test_a_customer_still_gets_the_receipt(self, client, fake_db, monkeypatch):
        fake_db.store["gg_athletes"].append({"email": EMAIL, "plan_status": "delivered"})
        _post(client, _exit_body())
        sent = _send_receipt(_enrollments(fake_db)[0], monkeypatch)
        assert [s["subject"] for s in sent] == ["got it"]

    def test_not_a_gmail_lead_sync_candidate(self, client, fake_db):
        from mission_control.services.lead_nurture import get_sync_candidates
        _post(client, _exit_body())
        assert EMAIL not in [c["email"] for c in get_sync_candidates()]

    def test_not_a_race_countdown_or_debrief_candidate(self, client, fake_db):
        from mission_control.services.race_countdown import gather_candidates
        _post(client, _exit_body(race_slug="unbound-200", race_name="Unbound 200"))
        contacts, _ = gather_candidates(fake_db.store["gg_sequence_enrollments"])
        assert EMAIL not in contacts

    def test_mission_control_sends_an_inbox_safe_backup_alert(self, client, fake_db, monkeypatch):
        # the worker's alert can fail on its own; two per exit is fine, none is not
        sent = _capture_sends(monkeypatch)
        _post(client, _exit_body())
        assert [s["subject"] for s in sent] == ["[GG] Exit survey filed · Test Rider A"]
        html = sent[0]["html"]
        assert "new lead" not in sent[0]["subject"]
        assert html.index("NEXT ACTIONS") < html.index("<table")
        for key in ANSWERS:
            assert f">{key}</td>" in html, key
        assert "Add to the talk-to-an-athlete roster (ask first)." in html
        assert "file_athlete_review.py" not in html

    def test_backup_alert_names_the_minor(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        _post(client, _exit_body(dict(ANSWERS, age_group="under_18")))
        assert "Under 18: needs a parent&#x27;s sign-off before anything renders." in sent[0]["html"]

    def test_backup_alert_names_them_by_name_then_slug_then_email(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        _post(client, _exit_body())
        _post(client, dict(_exit_body(), email="slug.only@example.com", name=""))
        _post(client, dict(_exit_body(), email="email.only@example.com", name="", athlete=""))
        assert [s["subject"] for s in sent] == [
            "[GG] Exit survey filed · Test Rider A",
            "[GG] Exit survey filed · test-rider-a",
            "[GG] Exit survey filed · email.only@example.com",
        ]

    def test_not_a_race_debrief_candidate_either(self, client, fake_db):
        """The debrief job runs end to end: a real lead whose race was 71 days
        ago is enrolled, the exit athlete with the same race is not."""
        from datetime import date
        from unittest.mock import patch
        from mission_control.services.race_debrief import run_race_debrief

        _post(client, _exit_body(race_slug="unbound-200", race_name="Unbound 200"))
        fake_db.store["gg_sequence_enrollments"].append({
            "id": "lead-1", "sequence_id": "welcome_v1", "contact_email": "control.lead@example.com",
            "contact_name": "Control", "status": "completed", "source": "race_profile",
            "source_data": {"brand": "gravelgod", "race_slug": "unbound-200", "race_name": "Unbound 200"},
        })
        with patch("mission_control.services.race_debrief._fetch_dates_sync",
                   return_value={"gravelgod": {"unbound-200": "2026-05-30"}}):
            summary = asyncio.run(run_race_debrief(today=date(2026, 8, 9)))
        debriefed = {e["contact_email"] for e in fake_db.store["gg_sequence_enrollments"]
                     if e["sequence_id"].startswith("race_debrief")}
        assert debriefed == {"control.lead@example.com"}, summary

    def test_a_routing_failure_still_alerts(self, client, fake_db, monkeypatch):
        import mission_control.routers.webhooks as wh
        sent = _capture_sends(monkeypatch)
        monkeypatch.setattr(wh, "get_sequences_for_trigger", lambda *a, **k: [])
        _post(client, _exit_body())
        assert any(s["subject"].startswith("[UNROUTED]") for s in sent)


class TestSeasonPlanPrefillRejectsIt:
    def test_an_exit_row_never_prefills_even_with_a_token(self, client, fake_db):
        fake_db.store["gg_sequence_enrollments"].append({
            "id": "exit-1", "sequence_id": "athlete_exit_v1", "contact_email": EMAIL,
            "contact_name": "Test Rider A", "source": "athlete_exit",
            "source_data": {"poster_token": "exit-token-abcdefghijklmnop", "goal_answers": ANSWERS},
        })
        assert client.get("/api/season-plan/prefill/exit-token-abcdefghijklmnop").status_code == 404


class TestResubmission:
    def test_replaces_the_record_and_withdraws_what_they_took_back(self, client, fake_db, monkeypatch):
        _capture_sends(monkeypatch)
        _post(client, _exit_body())
        first = _enrollments(fake_db)[0]["source_data"]
        assert first["share_tier_plain"] and first["needs_plain"] and first["consent"]["assets"] == ["quote", "not_for"]

        second = {k: v for k, v in ANSWERS.items() if not k.startswith(("need_", "where_"))}
        second.update(share_as="private", exit_story="Test answer: changed my mind.")
        resp = _post(client, _exit_body(second))
        rows = _enrollments(fake_db)
        assert len(rows) == 1 and resp.json()["enrolled"] == []
        sd = rows[0]["source_data"]
        assert sd["goal_answers"]["exit_story"] == "Test answer: changed my mind."
        assert "need_zones" not in sd["goal_answers"]
        assert "share_tier_plain" not in sd and "needs_plain" not in sd
        assert sd["consent"]["identity_tier"] == "count_only"
        assert sd["consent"]["quote"] == "" and sd["consent"]["channels"] == []

    def test_a_correction_resends_the_receipt(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        _post(client, _exit_body())
        enrollment = _enrollments(fake_db)[0]
        fake_db.store["gg_sequence_sends"].append({
            "id": "s0", "enrollment_id": enrollment["id"], "step_index": 0,
            "template": "athlete_exit_receipt", "subject": "got it",
        })
        _post(client, _exit_body(dict(ANSWERS, last_word="Test answer: one more thing.")))
        # to the athlete: the corrected receipt (Matti's backup alert went on the first post)
        assert [s["subject"] for s in sent if s["to"] == EMAIL] == ["got it"]
        assert [s["subject"] for s in sent if s["to"] != EMAIL] == [
            "[GG] Exit survey filed · Test Rider A", "[GG] Exit survey updated · Test Rider A"]


class TestResubmissionAlert:
    @pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
    def test_still_alerts_when_the_worker_cannot(self, client, fake_db, monkeypatch):
        """Second submission, worker's own alert unavailable: Mission Control's
        backup still goes out, marked as an update."""
        import os

        _post(client, _exit_body())
        sent = _capture_sends(monkeypatch)
        body = {"source": "athlete_exit", "brand": "gravelgod", "website": "", "email": EMAIL,
                "name": SUBMISSION["name"], "athlete": SUBMISSION["athlete"],
                "goal_answers": dict(ANSWERS, last_word="Test answer: one more thing.")}
        run = subprocess.run(
            ["node", str(ROOT / "tests" / "helpers" / "run_lead_worker.mjs")],
            input=json.dumps(body), capture_output=True, text=True, timeout=60, check=True,
            env={**os.environ, "GG_ENV_OVERRIDES": json.dumps({"RESEND_API_KEY": ""})},
        )
        out = json.loads(run.stdout)
        assert out["status"] == 200
        assert not any("resend" in s["url"] for s in out["sent"]), "the worker alert was meant to be unavailable"
        assert "Athlete exit alert NOT sent" in run.stderr
        to_mc = next(s["body"] for s in out["sent"] if s["url"].endswith("/webhooks/subscriber"))

        resp = _post(client, to_mc)
        assert resp.json()["enrolled"] == []  # updated in place, nothing new enrolled
        alerts = [m for m in sent if m["to"] != EMAIL]
        assert [m["subject"] for m in alerts] == ["[GG] Exit survey updated · Test Rider A"]
        assert "Test answer: one more thing." in alerts[0]["html"]
        assert alerts[0]["html"].index("NEXT ACTIONS") < alerts[0]["html"].index("<table")

    def test_a_season_review_resubmission_is_unchanged(self, client, fake_db, monkeypatch):
        body = {"email": "review@example.com", "name": "Test Rider B", "source": "athlete_review",
                "goal_answers": {"outcome_goal": "Test answer: first"}}
        _post(client, body)
        sent = _capture_sends(monkeypatch)
        _post(client, dict(body, goal_answers={"outcome_goal": "Test answer: second"}))
        assert not [m for m in sent if "Season review" in m["subject"]]


class TestUnsubscribeKeepsThePendingReceipt:
    """An unsubscribe (from any email) stops marketing, not the one-email
    receipt of a form they just sent. It still stops plan onboarding."""

    def _enroll(self, fake_db, seq, status="active", **extra):
        from mission_control.tests.conftest import make_enrollment
        row = make_enrollment(contact_email=EMAIL, sequence_id=seq, status=status, **extra)
        fake_db.store["gg_sequence_enrollments"].append(row)
        return row

    def test_receipt_still_sends_and_marketing_stops(self, client, fake_db, monkeypatch):
        from mission_control.services.sequence_engine import _send_next_step, unsubscribe
        _post(client, _exit_body())
        receipt = _enrollments(fake_db)[0]
        marketing = self._enroll(fake_db, "welcome_v1")

        assert unsubscribe(EMAIL) == 1
        assert marketing["status"] == "unsubscribed"
        assert receipt["status"] == "active"

        sent = _capture_sends(monkeypatch)
        assert asyncio.run(_send_next_step(receipt))
        assert [(m["to"], m["subject"]) for m in sent] == [(EMAIL, "got it")]
        assert receipt["status"] == "completed"

    def test_a_pending_season_review_receipt_is_kept_too(self, fake_db):
        from mission_control.services.sequence_engine import unsubscribe
        review = self._enroll(fake_db, "athlete_review_v1")
        marketing = self._enroll(fake_db, "nurture_v1")
        assert unsubscribe(EMAIL) == 1
        assert (review["status"], marketing["status"]) == ("active", "unsubscribed")

    def test_plan_onboarding_still_stops(self, fake_db):
        # post_purchase is transactional but weeks long; an unsubscribe ends it
        from mission_control.services.sequence_engine import unsubscribe
        onboarding = self._enroll(fake_db, "post_purchase_v1")
        receipt = self._enroll(fake_db, "athlete_exit_v1")
        assert unsubscribe(EMAIL) == 1
        assert (onboarding["status"], receipt["status"]) == ("unsubscribed", "active")

    def test_the_suppression_marker_still_lands_on_marketing(self, fake_db):
        from mission_control.services.sequence_engine import enroll, unsubscribe
        receipt = self._enroll(fake_db, "athlete_exit_v1")
        done = self._enroll(fake_db, "welcome_v1", status="completed")
        assert unsubscribe(EMAIL) == 1
        assert (receipt["status"], done["status"]) == ("active", "unsubscribed")
        assert enroll(EMAIL, "Test Rider A", "race_debrief_v1", source="race_debrief") is None


class TestCapsFitTheExitForm:
    """Every free-text answer at the page's 4000-character cap, every choice
    at its longest: all of it survives the worker and Mission Control."""

    @staticmethod
    def _longest_answers():
        from generate_season_review import MAX_ANSWER_LEN
        answers = {}
        for sec in EXIT["sections"]:
            for f in sec["fields"]:
                kind = f["kind"]
                if kind in ("text", "area") and f["name"] not in ("name", "email"):
                    answers[f["name"]] = f["name"][0] * MAX_ANSWER_LEN
                elif kind in ("radio", "select"):
                    answers[f["name"]] = max((o[0] for o in f["options"]), key=len)
                elif kind == "scale":
                    answers[f["name"]] = "10"
                elif kind == "checks":
                    answers.update({key: "yes" for key, _ in f["options"]})
        assert list(answers) == answer_keys(EXIT)
        return answers

    def test_mission_control_keeps_every_answer(self):
        from mission_control.routers.webhooks import _cap_goal_answers
        answers = self._longest_answers()
        assert sum(len(v) for v in answers.values()) > 30000  # the old budget would cut it
        assert _cap_goal_answers(answers) == answers

    @pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
    def test_the_worker_keeps_every_answer(self):
        answers = self._longest_answers()
        body = {"source": "athlete_exit", "email": EMAIL, "name": SUBMISSION["name"], "website": "",
                "goal_answers": answers}
        run = subprocess.run(["node", str(ROOT / "tests" / "helpers" / "run_lead_worker.mjs")],
                             input=json.dumps(body), capture_output=True, text=True, timeout=60, check=True)
        to_mc = next(s["body"] for s in json.loads(run.stdout)["sent"] if s["url"].endswith("/webhooks/subscriber"))
        assert to_mc["goal_answers"] == answers

    def test_the_stored_row_keeps_every_answer(self, client, fake_db):
        answers = self._longest_answers()
        _post(client, _exit_body(answers))
        assert _enrollments(fake_db)[0]["source_data"]["goal_answers"] == answers


class TestConsentRecord:
    """Shaped for the receipts ledger (receipts-social-proof-2026.md §5.3, §6.2)."""

    def test_a_yes_is_consent_in_principle_not_approval(self):
        from mission_control.services.athlete_exit import consent_record
        now = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
        rec = consent_record(ANSWERS, now)
        assert rec["identity_tier"] == "initial"
        # the question covers both texts above it
        assert rec["assets"] == ["quote", "not_for"]
        assert rec["quote"] == ANSWERS["quote"]
        assert rec["not_for"] == ANSWERS["not_for"]
        assert rec["age_group"] == "40_49"
        assert rec["needs_parent_signoff"] is False
        assert rec["channels"] == ["gravelgod", "social", "email", "tp"]
        assert rec["material_connection"] == "friend"
        assert rec["reference"] == "ask"
        assert rec["consent_id"].startswith("athlete_exit:")
        assert rec["consented_at"] == now.isoformat()
        assert rec["consent_expires"] == "2029-09-28"
        # the ledger validator rejects an entry until both are set (§6.2)
        assert rec["quote_approved_at"] is None and rec["render_approved_at"] is None
        assert rec["withdrawn_at"] is None

    def test_either_text_alone_is_an_asset(self):
        from mission_control.services.athlete_exit import consent_record
        only_not_for = {k: v for k, v in ANSWERS.items() if k != "quote"}
        rec = consent_record(only_not_for)
        assert rec["assets"] == ["not_for"] and rec["quote"] == "" and rec["not_for"] == ANSWERS["not_for"]

    def test_under_18_needs_a_parent(self):
        from mission_control.services.athlete_exit import consent_record
        rec = consent_record(dict(ANSWERS, age_group="under_18"))
        assert rec["age_group"] == "under_18" and rec["needs_parent_signoff"] is True

    def test_no_or_junk_age_group_is_none(self):
        from mission_control.services.athlete_exit import consent_record
        assert consent_record(dict(ANSWERS, age_group="12"))["age_group"] is None
        assert consent_record({k: v for k, v in ANSWERS.items() if k != "age_group"})["age_group"] is None

    def test_private_is_count_only_and_keeps_no_words(self):
        from mission_control.services.athlete_exit import consent_record
        rec = consent_record(dict(ANSWERS, share_as="private"))
        assert rec["identity_tier"] == "count_only"
        assert rec["assets"] == [] and rec["quote"] == "" and rec["not_for"] == "" and rec["channels"] == []

    def test_skipping_the_question_records_nothing(self):
        from mission_control.services.athlete_exit import consent_record
        assert consent_record({k: v for k, v in ANSWERS.items() if k != "share_as"}) is None

    def test_junk_enums_are_not_recorded(self):
        from mission_control.services.athlete_exit import consent_record
        rec = consent_record(dict(ANSWERS, connection="boss", reference="maybe"))
        assert rec["material_connection"] is None and rec["reference"] is None

    def test_stored_on_the_enrollment(self, client, fake_db):
        _post(client, _exit_body())
        assert _enrollments(fake_db)[0]["source_data"]["consent"]["identity_tier"] == "initial"


class TestReceipt:
    def _receipt(self, client, fake_db, monkeypatch, answers):
        _post(client, _exit_body(answers))
        sent = _send_receipt(_enrollments(fake_db)[0], monkeypatch)
        assert len(sent) == 1 and sent[0]["to"] == EMAIL and sent[0]["subject"] == "got it"
        return sent[0]["html"]

    def test_everything_they_asked_for(self, client, fake_db, monkeypatch):
        html = self._receipt(client, fake_db, monkeypatch, ANSWERS)
        assert "Test — got it. Thanks for taking the time." in html
        assert ("You said I can share what you wrote, with your first name and last initial. "
                "Before anything goes up I&rsquo;ll send you the exact words") in html
        assert "Changed your mind? Reply and say so." in html
        assert ("You asked for a summary of your zones and latest tests, notes for training on "
                "your own, confirmation that billing has stopped and help with your TrainingPeaks "
                "account. I&rsquo;ll send it over.") in html
        assert "&mdash; Matti" in html and "Matti Rowe &middot; Gravel God Cycling" in html
        assert "{" not in html.split("<body>")[1].split("unsubscribe")[0]

    def test_nothing_they_did_not_ask_for(self, client, fake_db, monkeypatch):
        html = self._receipt(client, fake_db, monkeypatch, {"exit_reason": "time", "share_as": "private"})
        assert "got it. Thanks for taking the time." in html
        assert "share what you wrote" not in html
        assert "You asked for" not in html

    def test_no_sharing_line_when_they_wrote_nothing_to_share(self, client, fake_db, monkeypatch):
        html = self._receipt(client, fake_db, monkeypatch, {"exit_reason": "done", "share_as": "full"})
        assert "share what you wrote" not in html

    def test_sharing_line_when_only_who_shouldnt_hire_me_was_written(self, client, fake_db, monkeypatch):
        html = self._receipt(client, fake_db, monkeypatch,
                             {"exit_reason": "done", "share_as": "full", "not_for": "Test answer: purists."})
        assert "You said I can share what you wrote, with your full name." in html

    def test_one_need_reads_as_one(self, client, fake_db, monkeypatch):
        html = self._receipt(client, fake_db, monkeypatch, {"exit_reason": "cost", "need_billing": "yes"})
        assert "You asked for confirmation that billing has stopped. I&rsquo;ll send it over." in html

    @pytest.mark.parametrize("tier,plain", [("full", "with your full name"),
                                            ("age_group", "with your first name and age group")])
    def test_each_sharing_tier_in_plain_words(self, client, fake_db, monkeypatch, tier, plain):
        html = self._receipt(client, fake_db, monkeypatch,
                             {"exit_reason": "done", "share_as": tier, "quote": "Test answer: good."})
        assert f"You said I can share what you wrote, {plain}." in html


def _chain_ready() -> bool:
    sys.path.insert(0, str(ROOT))
    from tests.exit_survey_browser import has_playwright
    return has_playwright() and shutil.which("node") is not None


@pytest.mark.skipif(not _chain_ready(), reason="needs playwright and node")
class TestTheWholeChain:
    """page -> worker -> Mission Control -> Matti's alert -> the receipt,
    with the real page, the real worker and this router. Every answer the
    page posts must be in the alert and on the stored record."""

    def test_every_field_survives_every_hop(self, client, fake_db, monkeypatch):
        from tests.exit_survey_browser import submit_exit_survey

        page = submit_exit_survey(SUBMISSION, width=390)
        assert page["errors"] == []
        posted = page["worker"]
        assert posted["goal_answers"] == ANSWERS

        run = subprocess.run(
            ["node", str(ROOT / "tests" / "helpers" / "run_lead_worker.mjs")],
            input=json.dumps(posted), capture_output=True, text=True, timeout=60, check=True,
        )
        out = json.loads(run.stdout)
        assert out["status"] == 200, out
        to_mc = next(s["body"] for s in out["sent"] if s["url"].endswith("/webhooks/subscriber"))
        alert = next(s["body"] for s in out["sent"] if s["url"] == "https://api.resend.com/emails")
        assert len(out["sent"]) == 2, [s["url"] for s in out["sent"]]

        assert to_mc["goal_answers"] == ANSWERS
        assert alert["subject"] == "[GG] Exit survey · Test Rider A · Life got full"
        for key, value in ANSWERS.items():
            assert f">{key}</td>" in alert["html"], f"{key} missing from Matti's alert"
            # free text verbatim, radio codes as "Label (code)", ticks as "ticked: Label"
            assert (value in alert["html"]) if value != "yes" else ("ticked: " in alert["html"]), key

        backup = _capture_sends(monkeypatch)
        resp = _post(client, to_mc)
        assert resp.status_code == 200 and resp.json()["enrolled"] == ["athlete_exit_v1"]
        assert [m["subject"] for m in backup] == ["[GG] Exit survey filed · Test Rider A"]
        for key in ANSWERS:
            assert f">{key}</td>" in backup[0]["html"], f"{key} missing from the backup alert"
        enrollment = _enrollments(fake_db)[0]
        assert enrollment["source_data"]["goal_answers"] == ANSWERS
        assert enrollment["source_data"]["athlete"] == "test-rider-a"

        receipt = _send_receipt(enrollment, monkeypatch)[0]["html"]
        assert "with your first name and last initial" in receipt
        assert "help with your TrainingPeaks account" in receipt


class TestBothAlertsAgree:
    """The worker's alert and Mission Control's backup build their Next
    actions separately (JS and Python). Same answers, same list."""

    NOW = "2026-11-30T12:00:00+00:00"
    CASES = [
        ANSWERS,
        dict(ANSWERS, age_group="under_18", checkin="3m"),
        {k: v for k, v in ANSWERS.items() if k not in ("age_group", "connection", "quote")} | {"share_as": "age_group"},
        {"exit_reason": "fit", "share_as": "age_group", "checkin": "preseason", "reference": "yes"},
        {"exit_reason": "cost", "need_billing": "yes", "checkin": "none", "age_group": "18_29"},
        {"exit_reason": "other", "connection": "boss", "share_as": "full", "quote": "Test answer: fine."},
    ]

    @pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
    @pytest.mark.parametrize("answers", CASES)
    def test_same_next_actions(self, answers):
        import html as html_lib
        import os
        import re
        from mission_control.services.athlete_exit import next_actions

        body = {"source": "athlete_exit", "email": EMAIL, "name": SUBMISSION["name"], "goal_answers": answers}
        run = subprocess.run(
            ["node", str(ROOT / "tests" / "helpers" / "run_lead_worker.mjs")],
            input=json.dumps(body), capture_output=True, text=True, timeout=60, check=True,
            env={**os.environ, "GG_NOW": self.NOW},
        )
        alert = next(s["body"] for s in json.loads(run.stdout)["sent"] if "resend" in s["url"])
        worker = [html_lib.unescape(li) for li in re.findall(r'<li style="margin:0 0 6px">(.*?)</li>', alert["html"])]
        assert worker == next_actions(answers, datetime.fromisoformat(self.NOW))

    def test_python_labels_are_the_forms(self):
        import html as html_lib
        from mission_control.services import athlete_exit as ax

        def options(name):
            for sec in EXIT["sections"]:
                for f in sec["fields"]:
                    if f.get("name") == name:
                        return {o[0]: html_lib.unescape(o[1]) for o in f["options"]}
            raise KeyError(name)

        assert ax.CONNECTION_LABELS == options("connection")
        assert ax.CHANNEL_LABELS == options("share_where")
        assert ax.NEED_LABELS == options("needs")
        assert ax.CHECKIN_LABELS == {k: v for k, v in options("checkin").items() if k != "none"}
        assert set(ax.AGE_GROUPS) == set(options("age_group"))
        assert set(ax.SHARE_TIER_ALERT) == set(ax.SHARING_TIERS) == set(options("share_as")) - {"private"}
