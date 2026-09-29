"""A plan buyer's race debrief (/race-debrief/, source=plan_debrief).

The exit survey's sibling, with the same guarantees: the answers are stored on
a plan_debrief_v1 (Gravel God) or road_plan_debrief_v1 (Roadie Labs)
enrollment, the rider gets one receipt and nothing else (no nurture, no deal,
no Gmail lead sync, no race countdown or post-race email), Matti gets a backup
alert with Next actions first, and a consent record in the receipts ledger's
vocabulary. The chain class carries a real page submission through the real
worker into this router and out as Matti's alerts and the rider's receipt,
for both brands.
"""
from __future__ import annotations

import asyncio
import html as html_lib
import json
import os
import re
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
from season_review_variants import RACE_DEBRIEF  # noqa: E402

SUBMISSION = json.loads((ROOT / "tests" / "fixtures" / "race_debrief_submission.json").read_text())
ROADIE = json.loads((ROOT / "tests" / "fixtures" / "race_debrief_submission_roadie.json").read_text())
ANSWERS = SUBMISSION["goal_answers"]
EMAIL = SUBMISSION["email"]
TEMPLATES = ROOT / "mission_control" / "templates" / "emails" / "sequences"


@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch):
    """Nothing in these tests reaches Resend. Tests that read mail re-patch."""
    import mission_control.services.sequence_engine as se
    monkeypatch.setattr(se, "_send_email_sync", lambda *a, **k: "rs-test")


def _post(client, body):
    return client.post("/webhooks/subscriber", json=body,
                       headers={"Authorization": "Bearer test-secret-123"})


def _body(answers=None, fixture=SUBMISSION, **extra):
    body = {"email": fixture["email"], "name": fixture["name"], "source": "plan_debrief",
            "brand": fixture["brand"], "plan": fixture["plan"],
            "goal_answers": dict(fixture["goal_answers"] if answers is None else answers)}
    body.update(extra)
    return body


def _enrollments(fake_db, email=EMAIL):
    return [e for e in fake_db.store["gg_sequence_enrollments"] if e["contact_email"] == email]


def _capture_sends(monkeypatch):
    import mission_control.services.sequence_engine as se
    sent = []
    monkeypatch.setattr(se, "RESEND_API_KEY", "test-key")
    monkeypatch.setattr(se, "_send_email_sync",
                        lambda to, subject, html, brand="gravelgod", *a: sent.append(
                            {"to": to, "subject": subject, "html": html, "brand": brand}) or "rs-1")
    return sent


def _send_receipt(enrollment, monkeypatch):
    import mission_control.services.sequence_engine as se
    sent = _capture_sends(monkeypatch)
    assert asyncio.run(se._send_next_step(enrollment))
    return sent


class TestSequence:
    def test_one_receipt_same_day_per_brand(self):
        gg = get_sequences_for_trigger("plan_debrief", "gravelgod")
        rl = get_sequences_for_trigger("plan_debrief", "roadielabs")
        assert [s["id"] for s in gg] == ["plan_debrief_v1"]
        assert [s["id"] for s in rl] == ["road_plan_debrief_v1"]
        assert gg[0]["variants"]["A"]["steps"] == [
            {"delay_days": 0, "template": "plan_debrief_receipt", "subject": "got it"}]
        assert rl[0]["variants"]["A"]["steps"] == [
            {"delay_days": 0, "template": "road_plan_debrief_receipt", "subject": "got it"}]

    def test_no_other_brand_or_trigger_reaches_it(self):
        assert get_sequences_for_trigger("plan_debrief", "xcskilabs") == []
        assert sorted(s["id"] for s in SEQUENCES.values() if s.get("trigger") == "plan_debrief") == [
            "plan_debrief_v1", "road_plan_debrief_v1"]
        # not the post-race marketing email, which shares the word "debrief"
        assert all(s.get("trigger") != "plan_debrief" for k, s in SEQUENCES.items() if k.startswith("race_debrief"))

    def test_receipt_templates_exist_and_carry_their_brand(self):
        gg = (TEMPLATES / "plan_debrief_receipt.html").read_text()
        rl = (TEMPLATES / "road_plan_debrief_receipt.html").read_text()
        assert "Matti Rowe &middot; Gravel God Cycling" in gg
        assert "Roadie Labs" in rl and "Gravel God" not in rl and "gravelgod" not in rl.lower()

    def test_transactional_in_the_engine_and_the_lead_bridge(self):
        from mission_control.services import lead_nurture, sequence_engine
        assert "plan_debrief" in sequence_engine._POST_PURCHASE_TRIGGERS
        assert "plan_debrief" in lead_nurture._POST_PURCHASE_TRIGGERS

    def test_left_out_of_the_public_intel_snapshot(self):
        sys.path.insert(0, str(ROOT))
        from scripts.daily_intel import NOT_LEAD_SEQUENCES
        assert {"plan_debrief_v1", "road_plan_debrief_v1"} <= NOT_LEAD_SEQUENCES


class TestStorage:
    def test_every_field_on_the_form_arrives_stored(self, client, fake_db):
        keys = answer_keys(RACE_DEBRIEF)
        assert set(keys) == set(ANSWERS)
        resp = _post(client, _body({k: ANSWERS[k] for k in keys}))
        assert resp.status_code == 200
        assert resp.json()["enrolled"] == ["plan_debrief_v1"]
        stored = _enrollments(fake_db)[0]["source_data"]["goal_answers"]
        missing = [k for k in keys if stored.get(k) != ANSWERS[k]]
        assert missing == [], f"dropped or changed on the way in: {missing}"

    def test_a_full_form_at_every_cap_is_kept_whole(self, client, fake_db):
        full = {k: ("x" * 4000 if RACE_DEBRIEF_KINDS[k] in ("text", "area") else v) for k, v in ANSWERS.items()}
        _post(client, _body(full))
        assert _enrollments(fake_db)[0]["source_data"]["goal_answers"] == full

    def test_the_plan_is_stored_as_the_product(self, client, fake_db):
        _post(client, _body())
        sd = _enrollments(fake_db)[0]["source_data"]
        assert (sd["plan_id"], sd["product"], sd["brand"]) == ("123456", "tp_plan", "gravelgod")
        assert "ref" not in sd

    def test_a_custom_plan_ref(self, client, fake_db):
        _post(client, _body(plan=None, ref="test-ref-0001"))
        sd = _enrollments(fake_db)[0]["source_data"]
        assert (sd["ref"], sd["product"]) == ("test-ref-0001", "custom_plan") and "plan_id" not in sd

    @pytest.mark.parametrize("plan,ref", [("12ab34", "bad"), (" 123456", "test-ref-0001\n"), (123456, ["x" * 8]),
                                          ("1234567890123", "a" * 33), ("<b>1</b>", "has space1")])
    def test_a_plan_or_ref_that_does_not_match_whole_is_dropped(self, client, fake_db, plan, ref):
        _post(client, _body(plan=plan, ref=ref))
        sd = _enrollments(fake_db)[0]["source_data"]
        assert "plan_id" not in sd and "ref" not in sd and sd["product"] == "unknown"

    def test_no_lead_context_is_kept(self, client, fake_db):
        _post(client, _body(race_slug="unbound-200", race_name="Unbound 200", offer_variant="A",
                            entry_src="race", goal_type="finish", guide_chapter="Race Selection",
                            viewed_races=["Unbound"], athlete="someone"))
        sd = _enrollments(fake_db)[0]["source_data"]
        for key in ("race_slug", "race_name", "prep_kit_url", "offer_variant", "entry_src", "goal_type",
                    "guide_chapter", "wb_guide", "viewed_races", "wb_trail", "wb_race", "any_context",
                    "goal_line", "inner_obstacle", "poster_token", "poster_url", "athlete"):
            assert key not in sd, key

    def test_junk_keys_and_values_are_dropped(self, client, fake_db):
        _post(client, _body(dict(ANSWERS, **{"Bad Key": "x", "nested": {"a": 1}, "blank": "  "})))
        stored = _enrollments(fake_db)[0]["source_data"]["goal_answers"]
        assert not {"Bad Key", "nested", "blank"} & set(stored)


RACE_DEBRIEF_KINDS = {
    f["name"]: f["kind"] for sec in RACE_DEBRIEF["sections"] for g in sec["fields"]
    for f in g.get("fields", [g]) if f.get("name")
}
RACE_DEBRIEF_KINDS.update({key: "checks" for key in ANSWERS if key.startswith("where_")})


class TestNotAMarketingContact:
    def test_no_deal_is_opened(self, client, fake_db):
        _post(client, _body())
        assert fake_db.store.get("gg_deals", []) == []

    def test_enrolls_in_nothing_else(self, client, fake_db):
        _post(client, _body())
        assert [e["sequence_id"] for e in _enrollments(fake_db)] == ["plan_debrief_v1"]

    def test_an_unsubscribed_rider_still_gets_stored(self, client, fake_db):
        fake_db.store["gg_sequence_enrollments"].append({
            "id": "old-1", "sequence_id": "welcome_v1", "contact_email": EMAIL,
            "status": "unsubscribed", "source": "exit_intent", "source_data": {},
        })
        assert _post(client, _body()).json()["enrolled"] == ["plan_debrief_v1"]

    def test_a_customer_still_gets_the_receipt(self, client, fake_db, monkeypatch):
        fake_db.store["gg_athletes"].append({"email": EMAIL, "plan_status": "delivered"})
        _post(client, _body())
        sent = _send_receipt(_enrollments(fake_db)[0], monkeypatch)
        assert [s["subject"] for s in sent] == ["got it"]

    def test_not_a_gmail_lead_sync_candidate(self, client, fake_db):
        from mission_control.services.lead_nurture import get_sync_candidates
        _post(client, _body())
        assert EMAIL not in [c["email"] for c in get_sync_candidates()]

    def test_not_a_race_countdown_candidate(self, client, fake_db):
        from mission_control.services.race_countdown import gather_candidates
        _post(client, _body(race_slug="unbound-200", race_name="Unbound 200"))
        contacts, _ = gather_candidates(fake_db.store["gg_sequence_enrollments"])
        assert EMAIL not in contacts

    def test_not_a_post_race_email_candidate(self, client, fake_db):
        """The race_debrief job run end to end: a real lead whose race was 71
        days ago is enrolled, the debrief rider with the same race is not."""
        from datetime import date
        from unittest.mock import patch
        from mission_control.services.race_debrief import run_race_debrief

        _post(client, _body(race_slug="unbound-200", race_name="Unbound 200"))
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

    def test_mission_control_sends_an_inbox_safe_backup_alert(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        _post(client, _body())
        assert [s["subject"] for s in sent] == ["[GG] Race debrief filed · Test Rider B · plan 123456"]
        html = sent[0]["html"]
        assert "new lead" not in sent[0]["subject"]
        assert html.index("NEXT ACTIONS") < html.index("<table")
        for key in ANSWERS:
            assert f">{key}</td>" in html, key
        assert "Add to the talk-to-a-rider roster for plan 123456 (ask first)." in html
        assert "Wants coaching: reply personally." in html
        assert "file_athlete_review.py" not in html and "no athlete tag" not in html

    def test_roadie_backup_alert_is_tagged_and_sent_as_roadie(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        _post(client, _body(fixture=ROADIE))
        assert [(s["subject"], s["brand"]) for s in sent] == [
            ("[RL] Race debrief filed · Test Rider C · plan 654321", "roadielabs")]
        assert "channels: roadielabs.com, Roadie Labs social posts" in html_lib.unescape(sent[0]["html"])

    def test_custom_and_unknown_plans_in_the_backup_subject(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        _post(client, _body(plan="", ref="test-ref-0001"))
        _post(client, _body(fixture=dict(SUBMISSION, email="other.rider@example.com"), plan=""))
        assert [s["subject"] for s in sent] == [
            "[GG] Race debrief filed · Test Rider B · custom plan",
            "[GG] Race debrief filed · Test Rider B · plan unknown"]
        assert "custom plan (ref test-ref-0001)" in sent[0]["html"]

    def test_a_routing_failure_still_alerts(self, client, fake_db, monkeypatch):
        import mission_control.routers.webhooks as wh
        sent = _capture_sends(monkeypatch)
        monkeypatch.setattr(wh, "get_sequences_for_trigger", lambda *a, **k: [])
        _post(client, _body())
        assert any(s["subject"].startswith("[UNROUTED]") for s in sent)

    def test_season_plan_prefill_rejects_it(self, client, fake_db):
        fake_db.store["gg_sequence_enrollments"].append({
            "id": "debrief-1", "sequence_id": "plan_debrief_v1", "contact_email": EMAIL,
            "contact_name": "Test Rider B", "source": "plan_debrief",
            "source_data": {"poster_token": "debrief-token-abcdefghijklm", "goal_answers": ANSWERS},
        })
        assert client.get("/api/season-plan/prefill/debrief-token-abcdefghijklm").status_code == 404


class TestResubmission:
    def test_the_same_plan_replaces_the_record(self, client, fake_db, monkeypatch):
        _capture_sends(monkeypatch)
        _post(client, _body())
        assert _enrollments(fake_db)[0]["source_data"]["consent"]["assets"] == ["quote", "not_for"]
        second = {k: v for k, v in ANSWERS.items() if not k.startswith("where_")}
        second.update(share_as="private", worked="Test answer: changed my mind.")
        resp = _post(client, _body(second))
        rows = _enrollments(fake_db)
        assert len(rows) == 1 and resp.json()["enrolled"] == []
        sd = rows[0]["source_data"]
        assert sd["goal_answers"]["worked"] == "Test answer: changed my mind."
        assert "where_site" not in sd["goal_answers"] and "share_tier_plain" not in sd
        assert sd["consent"]["identity_tier"] == "count_only" and sd["consent"]["channels"] == []
        assert "earlier" not in sd

    def test_a_different_plan_keeps_the_one_before(self, client, fake_db, monkeypatch):
        _capture_sends(monkeypatch)
        _post(client, _body())
        _post(client, _body({"raced": "dnf", "last_word": "Test answer: second plan."}, plan="777777"))
        sd = _enrollments(fake_db)[0]["source_data"]
        assert sd["plan_id"] == "777777" and sd["goal_answers"]["raced"] == "dnf"
        assert [e["plan_id"] for e in sd["earlier"]] == ["123456"]
        assert sd["earlier"][0]["goal_answers"] == ANSWERS
        assert sd["earlier"][0]["consent"]["quote"] == ANSWERS["quote"]

    def test_earlier_debriefs_are_capped(self):
        from mission_control.services.plan_debrief import MAX_EARLIER, replace_record
        record = {}
        for n in range(MAX_EARLIER + 3):
            record = replace_record(record, {"plan_id": str(100000 + n), "goal_answers": {"raced": "finished"}})
        assert len(record["earlier"]) == MAX_EARLIER
        assert record["earlier"][0]["plan_id"] == str(100000 + MAX_EARLIER + 1)
        assert all("earlier" not in e for e in record["earlier"])

    def test_a_correction_resends_the_receipt(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        _post(client, _body())
        enrollment = _enrollments(fake_db)[0]
        fake_db.store["gg_sequence_sends"].append({
            "id": "s0", "enrollment_id": enrollment["id"], "step_index": 0,
            "template": "plan_debrief_receipt", "subject": "got it",
        })
        _post(client, _body(dict(ANSWERS, last_word="Test answer: one more thing.")))
        assert [s["subject"] for s in sent if s["to"] == EMAIL] == ["got it"]
        assert [s["subject"] for s in sent if s["to"] != EMAIL] == [
            "[GG] Race debrief filed · Test Rider B · plan 123456"]


class TestConsentRecord:
    """The exit survey's record (receipts spec §5.3, §6.2) plus the product."""

    def test_a_yes_is_consent_in_principle_not_approval(self):
        from mission_control.services.plan_debrief import consent_record
        now = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
        rec = consent_record(ANSWERS, "123456", "", "gravelgod", now)
        assert rec["source"] == "plan_debrief" and rec["consent_id"].startswith("plan_debrief:")
        assert (rec["product"], rec["plan_id"], rec["ref"]) == ("tp_plan", "123456", None)
        assert rec["identity_tier"] == "initial"
        assert rec["assets"] == ["quote", "not_for"]
        assert rec["quote"] == ANSWERS["quote"] and rec["not_for"] == ANSWERS["not_for"]
        assert rec["channels"] == ["gravelgod", "social", "email", "tp"]
        assert rec["material_connection"] == "none" and rec["reference"] == "ask"
        assert rec["age_group"] == "40_49" and rec["needs_parent_signoff"] is False
        assert rec["consented_at"] == now.isoformat() and rec["consent_expires"] == "2029-09-28"
        assert rec["quote_approved_at"] is None and rec["render_approved_at"] is None
        assert rec["withdrawn_at"] is None

    def test_the_same_shape_as_the_exit_record_plus_three_keys(self):
        from mission_control.services.athlete_exit import consent_record as exit_record
        from mission_control.services.plan_debrief import consent_record
        assert set(consent_record(ANSWERS, "123456")) == set(exit_record(ANSWERS)) | {"product", "plan_id", "ref"}

    def test_roadie_names_its_site_channel_roadie(self):
        from mission_control.services.plan_debrief import consent_record
        rec = consent_record(ROADIE["goal_answers"], "654321", "", "roadielabs")
        assert rec["channels"] == ["roadie", "social", "email", "tp"] and rec["identity_tier"] == "full"

    @pytest.mark.parametrize("plan,ref,product", [("123456", "", "tp_plan"), ("", "test-ref-0001", "custom_plan"),
                                                  ("", "", "unknown"), ("123456", "test-ref-0001", "tp_plan")])
    def test_product(self, plan, ref, product):
        from mission_control.services.plan_debrief import consent_record
        rec = consent_record(ANSWERS, plan, ref)
        assert (rec["product"], rec["plan_id"], rec["ref"]) == (product, plan or None, ref or None)

    def test_private_is_count_only_and_keeps_no_words(self):
        from mission_control.services.plan_debrief import consent_record
        rec = consent_record(dict(ANSWERS, share_as="private"), "123456")
        assert rec["identity_tier"] == "count_only" and rec["assets"] == [] and rec["channels"] == []

    def test_skipping_the_question_records_nothing(self):
        from mission_control.services.plan_debrief import consent_record
        assert consent_record({k: v for k, v in ANSWERS.items() if k != "share_as"}, "123456") is None

    def test_stored_on_the_enrollment(self, client, fake_db):
        _post(client, _body())
        consent = _enrollments(fake_db)[0]["source_data"]["consent"]
        assert consent["product"] == "tp_plan" and consent["plan_id"] == "123456"


class TestReceipt:
    def _receipt(self, client, fake_db, monkeypatch, answers, fixture=SUBMISSION):
        _post(client, _body(answers, fixture=fixture))
        sent = _send_receipt(_enrollments(fake_db, fixture["email"])[0], monkeypatch)
        assert len(sent) == 1 and sent[0]["to"] == fixture["email"] and sent[0]["subject"] == "got it"
        return sent[0]

    def test_the_sharing_paragraph_when_they_said_yes_and_wrote_something(self, client, fake_db, monkeypatch):
        mail = self._receipt(client, fake_db, monkeypatch, ANSWERS)
        html = mail["html"]
        assert mail["brand"] == "gravelgod"
        assert "Test — got it. Thanks for taking the time." in html
        assert ("You said I can share what you wrote, with your first name and last initial. "
                "Before anything goes up I&rsquo;ll send you the exact words") in html
        assert "Changed your mind? Reply and say so." in html
        assert "&mdash; Matti" in html and "Matti Rowe &middot; Gravel God Cycling" in html
        assert "{" not in html.split("<body>")[1].split("unsubscribe")[0]

    def test_a_yes_with_nothing_written_gets_no_sharing_paragraph(self, client, fake_db, monkeypatch):
        html = self._receipt(client, fake_db, monkeypatch, {"raced": "finished", "share_as": "full"})["html"]
        assert "got it. Thanks for taking the time." in html
        assert "share what you wrote" not in html

    def test_a_no_gets_no_sharing_paragraph(self, client, fake_db, monkeypatch):
        html = self._receipt(client, fake_db, monkeypatch, dict(ANSWERS, share_as="private"))["html"]
        assert "share what you wrote" not in html

    def test_roadie_receipt_is_roadies(self, client, fake_db, monkeypatch):
        mail = self._receipt(client, fake_db, monkeypatch, ROADIE["goal_answers"], fixture=ROADIE)
        assert mail["brand"] == "roadielabs"
        assert "You said I can share what you wrote, with your full name." in mail["html"]
        assert "Matti Rowe &middot; Roadie Labs" in mail["html"] and "Gravel God" not in mail["html"]

    def test_roadie_sender_is_roadies(self):
        from mission_control.config import BRAND_SEQUENCE_SENDERS
        assert "Roadie Labs" in BRAND_SEQUENCE_SENDERS["roadielabs"]["from_name"]


def _chain_ready() -> bool:
    sys.path.insert(0, str(ROOT))
    from tests.race_debrief_browser import has_playwright
    return has_playwright() and shutil.which("node") is not None


def _run_worker(body: dict, origin: str = "https://gravelgodcycling.com", now: str | None = None) -> dict:
    env = {**os.environ, "GG_ORIGIN": origin}
    if now:
        env["GG_NOW"] = now
    run = subprocess.run(["node", str(ROOT / "tests" / "helpers" / "run_lead_worker.mjs")],
                         input=json.dumps(body), capture_output=True, text=True, timeout=60, check=True, env=env)
    return json.loads(run.stdout)


def _check_hops(out, answers, subject, backup_subject, client, fake_db, monkeypatch, email, sequence):
    assert out["status"] == 200, out
    assert len(out["sent"]) == 2, [s["url"] for s in out["sent"]]
    to_mc = next(s["body"] for s in out["sent"] if s["url"].endswith("/webhooks/subscriber"))
    alert = next(s["body"] for s in out["sent"] if s["url"] == "https://api.resend.com/emails")
    assert to_mc["goal_answers"] == answers
    assert alert["subject"] == subject
    for key, value in answers.items():
        assert f">{key}</td>" in alert["html"], f"{key} missing from Matti's alert"
        shown = html_lib.unescape(alert["html"])
        assert (value in shown) if value != "yes" else ("ticked: " in shown), key

    backup = _capture_sends(monkeypatch)
    resp = _post(client, to_mc)
    assert resp.status_code == 200 and resp.json()["enrolled"] == [sequence]
    assert [m["subject"] for m in backup] == [backup_subject]
    for key in answers:
        assert f">{key}</td>" in backup[0]["html"], f"{key} missing from the backup alert"
    enrollment = _enrollments(fake_db, email)[0]
    assert enrollment["source_data"]["goal_answers"] == answers
    return to_mc, enrollment


@pytest.mark.skipif(not _chain_ready(), reason="needs playwright and node")
class TestTheWholeChain:
    """page -> worker -> Mission Control -> Matti's alerts -> the receipt,
    with the real page, the real worker and this router."""

    def test_every_field_survives_every_hop(self, client, fake_db, monkeypatch):
        from tests.race_debrief_browser import run_debrief

        page = run_debrief("?plan=123456&utm_source=trainingpeaks", SUBMISSION)
        assert page["errors"] == [] and page["formsubmit"] is False
        posted = page["worker"]
        assert posted["goal_answers"] == ANSWERS and posted["plan"] == "123456"

        out = _run_worker(posted)
        to_mc, enrollment = _check_hops(
            out, ANSWERS, "[GG] Race debrief · Test Rider B · plan 123456",
            "[GG] Race debrief filed · Test Rider B · plan 123456",
            client, fake_db, monkeypatch, EMAIL, "plan_debrief_v1")
        assert to_mc["plan"] == "123456"
        assert enrollment["source_data"]["consent"]["plan_id"] == "123456"

        receipt = _send_receipt(enrollment, monkeypatch)[0]
        assert receipt["brand"] == "gravelgod"
        assert "with your first name and last initial" in receipt["html"]

    def test_a_roadie_submission_survives_every_hop(self, client, fake_db, monkeypatch):
        """The Roadie page (road-race-automation) posts this same body with
        brand=roadielabs from https://roadielabs.com; its own Playwright run
        pins that. From the worker on, it is this chain."""
        body = {"source": "plan_debrief", "brand": "roadielabs", "email": ROADIE["email"], "name": ROADIE["name"],
                "athlete": "", "goal_answers": ROADIE["goal_answers"], "website": "", "offer_variant": "",
                "race_slug": "", "entry_src": "", "goal_type": "", "plan": ROADIE["plan"]}
        out = _run_worker(body, origin="https://roadielabs.com")
        _, enrollment = _check_hops(
            out, ROADIE["goal_answers"], "[RL] Race debrief · Test Rider C · plan 654321",
            "[RL] Race debrief filed · Test Rider C · plan 654321",
            client, fake_db, monkeypatch, ROADIE["email"], "road_plan_debrief_v1")
        assert enrollment["source_data"]["consent"]["channels"] == ["roadie", "social", "email", "tp"]
        receipt = _send_receipt(enrollment, monkeypatch)[0]
        assert receipt["brand"] == "roadielabs" and "Roadie Labs" in receipt["html"]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
class TestBothAlertsAgree:
    """The worker's alert and Mission Control's backup build their Next
    actions separately (JS and Python). Same answers, same list."""

    CASES = [
        (ANSWERS, "gravelgod", "123456", ""),
        (ROADIE["goal_answers"], "roadielabs", "654321", ""),
        (dict(ANSWERS, age_group="under_18", next_want="custom", next_race="Test answer: Unbound?"),
         "gravelgod", "", "test-ref-0001"),
        ({k: v for k, v in ANSWERS.items() if k not in ("age_group", "connection", "quote")}
         | {"share_as": "age_group", "reference": "yes"}, "roadielabs", "", ""),
        ({"raced": "dns", "next_want": "another_plan"}, "gravelgod", "123456", ""),
        ({"raced": "later", "connection": "boss", "share_as": "full", "not_for": "Test answer: nobody."},
         "gravelgod", "", ""),
    ]

    @pytest.mark.parametrize("answers,brand,plan,ref", CASES)
    def test_same_next_actions(self, answers, brand, plan, ref):
        from mission_control.services.plan_debrief import next_actions
        body = {"source": "plan_debrief", "brand": brand, "email": EMAIL, "name": SUBMISSION["name"],
                "goal_answers": answers, "plan": plan, "ref": ref}
        origin = "https://roadielabs.com" if brand == "roadielabs" else "https://gravelgodcycling.com"
        alert = next(s["body"] for s in _run_worker(body, origin)["sent"] if "resend" in s["url"])
        worker = [html_lib.unescape(li) for li in re.findall(r'<li style="margin:0 0 6px">(.*?)</li>', alert["html"])]
        assert worker == next_actions(answers, plan, ref, brand)
