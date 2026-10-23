"""TrainingPeaks store sales -> post_purchase (services/tp_store_sales.py).

Every fixture here is synthetic: invented buyers at example.com / example.org,
invented ids and prices. Plan names reuse the catalog's naming shapes only.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from mission_control.services.tp_store_sales import (
    PROCESSED_ACTION, SOURCE, TP_SALE_SENDER, TP_SALE_SUBJECT,
    ingest_tp_sale_messages, parse_tp_sale_email, plan_weeks_from_name,
    race_name_from_plan, sender_is_trainingpeaks,
)
from mission_control.tests.conftest import make_athlete, make_enrollment

NOW = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
SOLD = "2026-10-20T12:30:00.000Z"
AUTH_OK = ("Authentication-Results: mx.google.com; dkim=pass header.i=@trainingpeaks.com "
           "header.s=s1 header.b=abc; spf=pass smtp.mailfrom=bounces.trainingpeaks.com; "
           "dmarc=pass (p=NONE sp=NONE dis=NONE) header.from=trainingpeaks.com")


def plain(plan, name, email, price):
    lines = ["TrainingPeaks", "", "Coach Matti,", "",
             "Congratulations, one of your training plans was just purchased through TrainingPeaks!",
             "", plan, name]
    if email:
        lines.append(email)
    lines += [price, "", "You will receive payment via the payout method on file.",
              "", "The TrainingPeaks Team"]
    return "\n".join(lines)


def html(plan, name, email, price):
    email_cell = f'<tr><td><a href="mailto:{email}">{email}</a></td></tr>' if email else ""
    return (
        "<html><head><style>td{color:#333}</style><title>TP</title></head><body>"
        "<table><tr><td><img alt=''/></td></tr>"
        "<tr><td>Coach Matti,</td></tr>"
        "<tr><td>Congratulations, one of your training plans was just purchased "
        "through TrainingPeaks!</td></tr>"
        f"<tr><td><strong>{plan}</strong></td></tr>"
        f"<tr><td>{name}</td></tr>{email_cell}"
        f"<tr><td>{price}</td></tr>"
        "<tr><td>You will receive payment via the payout method on file.</td></tr>"
        "</table></body></html>")


PLAN_SHAPES = [
    # (plan name, plan_weeks, race_name)
    ("Cycling - Badass Base - 10 hours/week", None, None),
    ("Gravel God - A Year In Gravel", None, None),
    ("8. Mid South - Finisher - Masters 50+ (12 weeks)", 12, "Mid South"),
    ("GFNY San Luis Potosí · Finisher · 12wk", 12, "GFNY San Luis Potosí"),
    ("Example Gravel 100 · Compete · 16wk", 16, "Example Gravel 100"),
]


class TestParser:
    @pytest.mark.parametrize("plan,weeks,race", PLAN_SHAPES)
    def test_plain_text_each_plan_shape(self, plan, weeks, race):
        sale = parse_tp_sale_email(subject=TP_SALE_SUBJECT, date=SOLD,
                                   text=plain(plan, "Pat Example", "pat.buyer@example.com", "$49.00"))
        assert sale == {
            "plan_name": plan, "buyer_name": "Pat Example",
            "buyer_email": "pat.buyer@example.com", "price": "49.00",
            "sold_at": "2026-10-20T12:30:00+00:00", "plan_weeks": weeks, "race_name": race,
        }

    @pytest.mark.parametrize("plan,weeks,race", PLAN_SHAPES)
    def test_html_only_each_plan_shape(self, plan, weeks, race):
        sale = parse_tp_sale_email(subject=TP_SALE_SUBJECT, date=SOLD,
                                   html=html(plan, "Pat Example", "Pat.Buyer@Example.com", "$1,249.99"))
        assert sale["plan_name"] == plan
        assert sale["buyer_name"] == "Pat Example"
        assert sale["buyer_email"] == "pat.buyer@example.com"
        assert sale["price"] == "1249.99"
        assert (sale["plan_weeks"], sale["race_name"]) == (weeks, race)

    def test_html_entities_decode(self):
        sale = parse_tp_sale_email(subject=TP_SALE_SUBJECT,
                                   html=html("Example Gravel &amp; Grit &middot; Finisher &middot; 8wk",
                                             "Sam O&#39;Example", "sam@example.org", "$29"))
        assert sale["plan_name"] == "Example Gravel & Grit · Finisher · 8wk"
        assert sale["buyer_name"] == "Sam O'Example"
        assert sale["race_name"] == "Example Gravel & Grit"
        assert sale["price"] == "29"

    def test_plain_text_preferred_but_html_used_when_plain_unreadable(self):
        sale = parse_tp_sale_email(subject=TP_SALE_SUBJECT, text="(no plain part)",
                                   html=html("Gravel God - A Year In Gravel", "Pat Example",
                                             "pat@example.com", "$99.00"))
        assert sale["buyer_email"] == "pat@example.com"

    def test_missing_email(self):
        sale = parse_tp_sale_email(subject=TP_SALE_SUBJECT, date=SOLD,
                                   text=plain("Cycling - Badass Base - 10 hours/week",
                                              "Pat Example", None, "$49.00"))
        assert sale["buyer_email"] is None
        assert sale["buyer_name"] == "Pat Example"
        assert sale["plan_name"] == "Cycling - Badass Base - 10 hours/week"

    def test_email_on_name_line(self):
        sale = parse_tp_sale_email(subject=TP_SALE_SUBJECT, text=plain(
            "Gravel God - A Year In Gravel", "Pat Example <pat@example.com>", None, "$99.00"))
        assert (sale["buyer_name"], sale["buyer_email"]) == ("Pat Example", "pat@example.com")

    def test_labelled_lines(self):
        body = ("Congratulations, one of your training plans was just purchased through TrainingPeaks!\n"
                "Plan: Example Gravel 100 · Compete · 12wk\nAthlete: Pat Example\n"
                "Email: pat@example.com\nPrice: $59.00\nYou will receive payment via ...")
        sale = parse_tp_sale_email(subject=TP_SALE_SUBJECT, text=body)
        assert sale["plan_name"] == "Example Gravel 100 · Compete · 12wk"
        assert sale["buyer_name"] == "Pat Example"
        assert sale["price"] == "59.00"

    def test_naive_and_missing_dates(self):
        text = plain("Gravel God - A Year In Gravel", "Pat Example", "pat@example.com", "$99")
        assert parse_tp_sale_email(subject=TP_SALE_SUBJECT, text=text,
                                   date="2026-10-20T12:30:00")["sold_at"] == "2026-10-20T12:30:00+00:00"
        assert parse_tp_sale_email(subject=TP_SALE_SUBJECT, text=text)["sold_at"] is None
        assert parse_tp_sale_email(subject=TP_SALE_SUBJECT, text=text, date="garbage")["sold_at"] is None

    @pytest.mark.parametrize("subject,text", [
        # Wrong subject (and a forward of the real one)
        ("Your weekly TrainingPeaks summary",
         plain("Gravel God - A Year In Gravel", "Pat Example", "pat@example.com", "$99")),
        ("Fwd: " + TP_SALE_SUBJECT,
         plain("Gravel God - A Year In Gravel", "Pat Example", "pat@example.com", "$99")),
        # Right subject, no sale block
        (TP_SALE_SUBJECT, "Hi Coach, thanks for being a TrainingPeaks coach."),
        # No price line
        (TP_SALE_SUBJECT, "Congratulations, one of your training plans was just purchased through "
                          "TrainingPeaks!\nGravel God - A Year In Gravel\nPat Example\n"
                          "You will receive payment via ..."),
        # Only one line before the price: plan vs buyer cannot be told apart
        (TP_SALE_SUBJECT, "Congratulations, one of your training plans was just purchased through "
                          "TrainingPeaks!\nPat Example\npat@example.com\n$49.00\n"
                          "You will receive payment via ..."),
        (TP_SALE_SUBJECT, ""),
    ])
    def test_non_matching_mail_returns_none(self, subject, text):
        assert parse_tp_sale_email(subject=subject, text=text) is None

    def test_plan_weeks_helper(self):
        assert plan_weeks_from_name("Example · Finisher · 12wk") == 12
        assert plan_weeks_from_name("Example - Finisher (8 weeks)") == 8
        assert plan_weeks_from_name("Example 20-week Build") == 20
        assert plan_weeks_from_name("Cycling - Badass Base - 10 hours/week") is None
        assert plan_weeks_from_name("Example · Finisher · 99wk") is None
        assert plan_weeks_from_name("") is None

    def test_race_name_helper(self):
        assert race_name_from_plan("Example Gravel · Time-Crunched · 8wk") == "Example Gravel"
        assert race_name_from_plan("Example Gravel - Save My Race - 4wk") == "Example Gravel"
        assert race_name_from_plan("Gravel God - Finisher - 12wk") is None  # brand, not race
        assert race_name_from_plan("Example Gravel Base Plan") is None
        assert race_name_from_plan("Example Gravel - Base - 12wk") is None


class TestSender:
    def test_accepts_tp_with_passing_auth(self):
        assert sender_is_trainingpeaks(f"TrainingPeaks <{TP_SALE_SENDER}>", AUTH_OK)

    def test_dkim_alone_is_enough(self):
        assert sender_is_trainingpeaks(TP_SALE_SENDER,
                                       "Authentication-Results: mx.google.com; dkim=pass header.d=trainingpeaks.com")

    @pytest.mark.parametrize("from_header,auth", [
        ("someone@example.com", AUTH_OK),
        (TP_SALE_SENDER, ""),
        (TP_SALE_SENDER, "Authentication-Results: mx.google.com; dkim=fail header.i=@trainingpeaks.com; "
                         "dmarc=fail header.from=trainingpeaks.com"),
        (TP_SALE_SENDER, "Authentication-Results: mx.google.com; dkim=pass header.i=@trainingpeaks.com.evil.example"),
        (TP_SALE_SENDER, "Authentication-Results: mx.google.com; dkim=pass header.d=nottrainingpeaks.com"),
    ])
    def test_rejects(self, from_header, auth):
        assert not sender_is_trainingpeaks(from_header, auth)


def message(msg_id="msgSynthetic001", plan="Example Gravel 100 · Compete · 12wk",
            name="Pat Example", email="pat.buyer@example.com", price="$49.00",
            date=SOLD, auth=AUTH_OK, sender=f"TrainingPeaks <{TP_SALE_SENDER}>"):
    return {"id": msg_id, "from": sender, "subject": TP_SALE_SUBJECT, "date": date,
            "auth_results": auth, "body": plain(plan, name, email, price), "html_body": ""}


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("TP_BUYER_INGEST_ENABLED", "true")
    monkeypatch.delenv("TP_BUYER_MAX_AGE_DAYS", raising=False)


def _processed(fake_db):
    return [r for r in fake_db.store["gg_audit_log"] if r.get("action") == PROCESSED_ACTION]


class TestIngestion:
    def test_off_by_default(self, fake_db, monkeypatch):
        monkeypatch.delenv("TP_BUYER_INGEST_ENABLED", raising=False)
        out = ingest_tp_sale_messages([message()], now=NOW)
        assert out["status"] == "disabled"
        assert fake_db.store["gg_sequence_enrollments"] == []
        assert fake_db.store["gg_audit_log"] == []

    @pytest.mark.parametrize("value", ["", "false", "0", "no", "enabled", "TRUE "])
    def test_only_explicit_truthy_values_enable(self, fake_db, monkeypatch, value):
        from mission_control.config import tp_buyer_ingest_enabled
        monkeypatch.setenv("TP_BUYER_INGEST_ENABLED", value)
        assert tp_buyer_ingest_enabled() is (value.strip().lower() == "true")

    def test_enrolls_buyer_with_source_and_plan_context(self, fake_db, enabled):
        out = ingest_tp_sale_messages([message()], now=NOW)
        assert out["counts"] == {"enrolled": 1}
        [enr] = fake_db.store["gg_sequence_enrollments"]
        assert enr["sequence_id"] == "post_purchase_v1"
        assert enr["source"] == SOURCE == "trainingpeaks_store"
        assert enr["contact_email"] == "pat.buyer@example.com"
        assert enr["contact_name"] == "Pat Example"
        sd = enr["source_data"]
        assert sd["plan_name"] == "Example Gravel 100 · Compete · 12wk"
        assert sd["plan_weeks"] == 12
        assert sd["race_name"] == "Example Gravel 100"
        assert sd["brand"] == "gravelgod"
        assert sd["tp_gmail_message_id"] == "msgSynthetic001"
        assert "race_slug" not in sd  # would pull them into countdown/debrief marketing
        [row] = _processed(fake_db)
        assert row["entity_id"] == "msgSynthetic001"
        assert '"outcome": "enrolled"' in row["details"]
        # Post-purchase never opens a sales deal
        assert fake_db.store["gg_deals"] == []

    def test_base_plan_has_no_race_or_weeks(self, fake_db, enabled):
        ingest_tp_sale_messages([message(plan="Cycling - Badass Base - 10 hours/week")], now=NOW)
        sd = fake_db.store["gg_sequence_enrollments"][0]["source_data"]
        assert "race_name" not in sd and "plan_weeks" not in sd

    def test_dedup_by_gmail_message_id(self, fake_db, enabled):
        ingest_tp_sale_messages([message()], now=NOW)
        out = ingest_tp_sale_messages([message(), message()], now=NOW)
        assert [r["outcome"] for r in out["results"]] == ["duplicate", "duplicate"]
        assert len(fake_db.store["gg_sequence_enrollments"]) == 1
        assert len(_processed(fake_db)) == 1

    def test_same_message_twice_in_one_batch(self, fake_db, enabled):
        out = ingest_tp_sale_messages([message(), message()], now=NOW)
        assert [r["outcome"] for r in out["results"]] == ["enrolled", "duplicate"]

    def test_no_email_is_skipped_and_recorded(self, fake_db, enabled):
        out = ingest_tp_sale_messages([message(email=None)], now=NOW)
        assert out["counts"] == {"skipped_no_email": 1}
        assert fake_db.store["gg_sequence_enrollments"] == []
        [row] = _processed(fake_db)
        assert "Pat Example" in row["details"]
        # recorded, so the next run does not log it again
        again = ingest_tp_sale_messages([message(email=None)], now=NOW)
        assert again["counts"] == {"duplicate": 1}

    def test_second_purchase_by_same_buyer_is_not_re_enrolled(self, fake_db, enabled):
        ingest_tp_sale_messages([message()], now=NOW)
        out = ingest_tp_sale_messages([message(msg_id="msgSynthetic002",
                                               plan="Gravel God - A Year In Gravel")], now=NOW)
        assert out["counts"] == {"skipped_already_purchased": 1}
        assert len(fake_db.store["gg_sequence_enrollments"]) == 1

    def test_existing_post_purchase_from_another_source_blocks(self, fake_db, enabled):
        fake_db.store["gg_sequence_enrollments"].append(make_enrollment(
            sequence_id="road_post_purchase_v1", contact_email="pat.buyer@example.com",
            source="stripe_plan", status="completed"))
        out = ingest_tp_sale_messages([message()], now=NOW)
        assert out["counts"] == {"skipped_already_purchased": 1}

    def test_coached_athlete_blocks(self, fake_db, enabled):
        fake_db.store["gg_athletes"].append(make_athlete(email="pat.buyer@example.com"))
        out = ingest_tp_sale_messages([message()], now=NOW)
        assert out["counts"] == {"skipped_already_purchased": 1}

    def test_unsubscribed_contact_is_not_enrolled(self, fake_db, enabled):
        fake_db.store["gg_sequence_enrollments"].append(make_enrollment(
            sequence_id="welcome_v1", contact_email="pat.buyer@example.com", status="unsubscribed"))
        out = ingest_tp_sale_messages([message()], now=NOW)
        assert out["counts"] == {"skipped_unsubscribed": 1}
        assert len(fake_db.store["gg_sequence_enrollments"]) == 1

    def test_opted_out_receipt_flag_is_honoured(self, fake_db, enabled):
        fake_db.store["gg_sequence_enrollments"].append(make_enrollment(
            sequence_id="athlete_review_v1", contact_email="pat.buyer@example.com",
            status="completed", source_data={"opted_out_at": "2026-01-01T00:00:00+00:00"}))
        out = ingest_tp_sale_messages([message()], now=NOW)
        assert out["counts"] == {"skipped_unsubscribed": 1}

    def test_lead_in_marketing_is_still_enrolled(self, fake_db, enabled):
        fake_db.store["gg_sequence_enrollments"].append(make_enrollment(
            sequence_id="welcome_v1", contact_email="pat.buyer@example.com", status="active"))
        out = ingest_tp_sale_messages([message()], now=NOW)
        assert out["counts"] == {"enrolled": 1}

    def test_stale_sale_is_recorded_not_mailed(self, fake_db, enabled):
        old = (NOW - timedelta(days=8)).isoformat()
        out = ingest_tp_sale_messages([message(date=old)], now=NOW)
        assert out["counts"] == {"skipped_stale": 1}
        assert fake_db.store["gg_sequence_enrollments"] == []
        assert len(_processed(fake_db)) == 1

    def test_max_age_is_configurable(self, fake_db, enabled, monkeypatch):
        monkeypatch.setenv("TP_BUYER_MAX_AGE_DAYS", "10")
        old = (NOW - timedelta(days=8)).isoformat()
        assert ingest_tp_sale_messages([message(date=old)], now=NOW)["counts"] == {"enrolled": 1}

    def test_missing_date_is_treated_as_stale(self, fake_db, enabled):
        out = ingest_tp_sale_messages([message(date=None)], now=NOW)
        assert out["counts"] == {"skipped_stale": 1}

    def test_unverified_sender_is_rejected_and_not_recorded(self, fake_db, enabled):
        out = ingest_tp_sale_messages([message(auth="")], now=NOW)
        assert out["counts"] == {"unverified_sender": 1}
        out = ingest_tp_sale_messages([message(sender="support@trainingpeaks.example")], now=NOW)
        assert out["counts"] == {"unverified_sender": 1}
        assert fake_db.store["gg_sequence_enrollments"] == []
        assert fake_db.store["gg_audit_log"] == []

    def test_unparsed_is_not_recorded_so_a_fix_can_retry(self, fake_db, enabled):
        bad = {**message(), "body": "Congratulations, one of your training plans was just "
                                    "purchased through TrainingPeaks!\nsomething else"}
        out = ingest_tp_sale_messages([bad], now=NOW)
        assert out["counts"] == {"unparsed": 1}
        assert fake_db.store["gg_audit_log"] == []

    def test_invalid_message_id(self, fake_db, enabled):
        out = ingest_tp_sale_messages([message(msg_id="x"), "not-a-dict"], now=NOW)
        assert out["counts"] == {"invalid_id": 1}
        assert fake_db.store["gg_sequence_enrollments"] == []

    def test_dry_run_writes_nothing_even_when_disabled(self, fake_db, monkeypatch):
        monkeypatch.delenv("TP_BUYER_INGEST_ENABLED", raising=False)
        out = ingest_tp_sale_messages([message(), message(msg_id="msgSynthetic003", email=None)],
                                      dry_run=True, now=NOW)
        assert out["status"] == "dry_run"
        assert [r["outcome"] for r in out["results"]] == ["would_enroll", "skipped_no_email"]
        assert "pat.buyer@example.com" not in str(out)  # report carries no buyer address
        assert fake_db.store["gg_sequence_enrollments"] == []
        assert fake_db.store["gg_audit_log"] == []


class TestSourceAwareStepZero:
    def _send(self, fake_db, enrollment):
        from mission_control.services.sequence_engine import _send_next_step

        fake_db.store["gg_sequence_enrollments"].append(enrollment)
        with patch("mission_control.services.sequence_engine.RESEND_API_KEY", "fake-key"), \
                patch("mission_control.services.sequence_engine._send_email_sync",
                      return_value="resend-synthetic") as send:
            assert asyncio.new_event_loop().run_until_complete(_send_next_step(enrollment))
        _to, subject, html_out, _brand, _token = send.call_args.args
        return subject, html_out, fake_db.store["gg_sequence_sends"][-1]

    def test_tp_buyer_gets_tp_welcome(self, fake_db):
        enr = make_enrollment(sequence_id="post_purchase_v1", source=SOURCE,
                              contact_name="Pat Example", contact_email="pat.buyer@example.com",
                              source_data={"plan_name": "Example Gravel 100 · Compete · 12wk",
                                           "plan_weeks": 12, "race_name": "Example Gravel 100"})
        subject, body, send = self._send(fake_db, enr)
        assert subject == "did the plan land on your calendar?"
        assert send["template"] == "tp_purchase_welcome"
        assert "Pat — saw you picked up Example Gravel 100 · Compete · 12wk on TrainingPeaks." in body
        assert "Easier to fix in week one than week six." in body
        assert "Did you set the start date so it ends on race day?" in body
        assert "questionnaire" not in body and "24 hours" not in body
        assert "{{" not in body and "{plan_name}" not in body
        # the schedule is the sequence's own: next step is day 3
        nxt = datetime.fromisoformat(enr["next_send_at"])
        assert abs((nxt - datetime.now(timezone.utc)) - timedelta(days=3)) < timedelta(seconds=30)

    def test_plan_name_fallback(self, fake_db):
        enr = make_enrollment(sequence_id="post_purchase_v1", source=SOURCE, contact_name="",
                              source_data={})
        _subject, body, _send = self._send(fake_db, enr)
        assert "Hey — saw you picked up the plan on TrainingPeaks." in body

    def test_plan_name_is_escaped(self, fake_db):
        enr = make_enrollment(sequence_id="post_purchase_v1", source=SOURCE,
                              source_data={"plan_name": '<a href="https://evil.example">x</a>'})
        _subject, body, _send = self._send(fake_db, enr)
        assert "evil.example\">" not in body and "&lt;a href=" in body

    @pytest.mark.parametrize("source", ["plan_purchased", "stripe_plan", ""])
    def test_other_buyers_keep_questionnaire_receipt(self, fake_db, source):
        enr = make_enrollment(sequence_id="post_purchase_v1", source=source, source_data={})
        subject, body, send = self._send(fake_db, enr)
        assert subject == "got your questionnaire"
        assert send["template"] == "purchase_welcome"

    def test_base_plan_welcome_does_not_assume_a_race(self, fake_db):
        enr = make_enrollment(sequence_id="post_purchase_v1", source=SOURCE,
                              source_data={"plan_name": "Example Base - 10 hours/week"})
        _subject, body, _send = self._send(fake_db, enr)
        assert "race day" not in body
        assert "When are you starting it?" in body

    @pytest.mark.parametrize("step,template,subject", [
        (1, "tp_week1_check", "started yet?"),
        (2, "tp_checkin", "is the schedule surviving your week?"),
        (3, "tp_progress", "the easy weeks"),
        (4, "tp_nps", "how's the plan treating you?"),
    ])
    def test_later_steps_do_not_assume_the_plan_started(self, fake_db, step, template, subject):
        enr = make_enrollment(sequence_id="post_purchase_v1", source=SOURCE, current_step=step,
                              source_data={"plan_name": "Example Base - 10 hours/week"})
        got_subject, body, send = self._send(fake_db, enr)
        assert (got_subject, send["template"]) == (subject, template)
        assert "{{" not in body and "{plan_name}" not in body
        assert "your race" not in body

    @pytest.mark.parametrize("step,template", [
        (1, "week1_tips"), (2, "checkin_week2"), (3, "progress_update"),
    ])
    def test_other_buyers_keep_the_standard_steps(self, fake_db, step, template):
        enr = make_enrollment(sequence_id="post_purchase_v1", source="plan_purchased",
                              current_step=step, source_data={"race_name": "Example Gravel 100"})
        _subject, _body, send = self._send(fake_db, enr)
        assert send["template"] == template

    def test_other_buyers_keep_the_standard_nps_step(self):
        # Checked on the resolved step, not a send: whether nps_request sends
        # also depends on the race-date premise, which has its own tests.
        from mission_control.services.sequence_engine import _resolve_step
        from mission_control.sequences.post_purchase import SEQUENCE
        last = SEQUENCE["variants"]["A"]["steps"][-1]
        assert _resolve_step(last, {"source": "plan_purchased"})["template"] == "nps_request"

    def test_override_cannot_change_timing(self):
        from mission_control.services.sequence_engine import _resolve_step

        step = {"delay_days": 0, "template": "a", "subject": "s",
                "source_overrides": {"x": {"template": "b", "subject": "t", "delay_days": 99}}}
        resolved = _resolve_step(step, {"source": "x"})
        assert (resolved["template"], resolved["subject"], resolved["delay_days"]) == ("b", "t", 0)
        assert _resolve_step(step, {"source": "y"}) is step

    def test_tp_nps_drops_the_base_race_premise(self):
        from mission_control.services.sequence_engine import _resolve_step
        from mission_control.sequences.post_purchase import SEQUENCE
        steps = SEQUENCE["variants"]["A"]["steps"]
        base = {**steps[-1], "race_premise": "passed"}
        tp = _resolve_step(base, {"source": "trainingpeaks_store"})
        assert tp["template"] == "tp_nps" and tp["race_premise"] is None
        stripe = _resolve_step(base, {"source": "stripe"})
        assert stripe["race_premise"] == "passed"

    def test_override_templates_exist(self):
        from mission_control.config import WEB_TEMPLATES_DIR
        from mission_control.sequences import SEQUENCES

        tdir = WEB_TEMPLATES_DIR / "emails" / "sequences"
        for seq in SEQUENCES.values():
            for variant in seq["variants"].values():
                for step in variant["steps"]:
                    for ov in (step.get("source_overrides") or {}).values():
                        assert (tdir / f"{ov['template']}.html").exists(), ov["template"]
                        assert ov.get("subject"), "subjects live in the sequence defs"


class TestEndpoints:
    AUTH = {"Authorization": "Bearer test-secret-123"}

    def test_config_requires_secret(self, client):
        assert client.get("/webhooks/tp-store-sales/config",
                          headers={"Authorization": "Bearer wrong"}).status_code == 401

    def test_config_reports_disabled_by_default(self, client, monkeypatch):
        monkeypatch.delenv("TP_BUYER_INGEST_ENABLED", raising=False)
        resp = client.get("/webhooks/tp-store-sales/config", headers=self.AUTH)
        assert resp.status_code == 200
        assert resp.json() == {"enabled": False, "sender": TP_SALE_SENDER, "subject": TP_SALE_SUBJECT}

    def test_post_disabled_does_nothing(self, client, fake_db, monkeypatch):
        monkeypatch.delenv("TP_BUYER_INGEST_ENABLED", raising=False)
        resp = client.post("/webhooks/tp-store-sales", json={"messages": [message()]},
                           headers=self.AUTH)
        assert resp.json()["status"] == "disabled"
        assert fake_db.store["gg_sequence_enrollments"] == []

    def test_post_enabled_enrolls(self, client, fake_db, monkeypatch):
        monkeypatch.setenv("TP_BUYER_INGEST_ENABLED", "1")
        fresh = datetime.now(timezone.utc).isoformat()
        resp = client.post("/webhooks/tp-store-sales", json={"messages": [message(date=fresh)]},
                           headers=self.AUTH)
        assert resp.status_code == 200
        assert resp.json()["counts"] == {"enrolled": 1}
        assert fake_db.store["gg_sequence_enrollments"][0]["source"] == SOURCE

    def test_post_rejects_bad_payload_and_secret(self, client):
        assert client.post("/webhooks/tp-store-sales", json={"messages": "x"},
                           headers=self.AUTH).status_code == 400
        assert client.post("/webhooks/tp-store-sales", json={"messages": []},
                           headers={"Authorization": "Bearer wrong"}).status_code == 401
