"""Lead reply ingestion, approval safety, and measurement tests."""

from datetime import datetime, timedelta, timezone

from mission_control.tests.conftest import make_deal, make_enrollment, make_sequence_send


def _message(
    *, message_id="gmail-in-1", sender="Jane Lead <lead@example.com>",
    recipients=None, body="Training is going well.", is_draft=False,
    date=None,
):
    return {
        "id": message_id,
        "from": sender,
        "to": recipients or ["gravelgodcoaching+lead.0123456789abcdef0123456789abcdef@gmail.com"],
        "cc": [],
        "subject": "Re: how's training going?",
        "date": date or datetime.now(timezone.utc).isoformat(),
        "body": body,
        "is_draft": is_draft,
        "is_trash": False,
    }


class TestPlainMattiSuggestions:
    def test_positive_training_gets_one_easy_question_and_no_pitch(self):
        from mission_control.services.lead_nurture import build_reply_suggestion

        result = build_reply_suggestion(
            text="Training is going well so far.", first_name="Jane", seed="stable",
        )
        assert result["question_type"] in {"challenge", "favorite_workout"}
        assert result["draft_text"].count("?") == 1
        assert "buy" not in result["draft_text"].lower()
        assert "plan" not in result["draft_text"].lower()

    def test_explicit_question_requires_coach_answer(self):
        from mission_control.services.lead_nurture import build_reply_suggestion

        result = build_reply_suggestion(
            text="How much is coaching?", first_name="Jane", seed="stable",
        )
        assert result["needs_coach_answer"] is True
        assert result["intent"] == "buying"
        assert "[Answer their question directly first.]" in result["draft_text"]

    def test_support_problem_never_pretends_it_is_fixed(self):
        from mission_control.services.lead_nurture import build_reply_suggestion

        result = build_reply_suggestion(
            text="I never received the guide.", first_name="Jane", seed="stable",
        )
        assert result["needs_coach_answer"] is True
        assert "i fixed" not in result["draft_text"].lower()
        assert "resend" not in result["draft_text"].lower()
        assert result["draft_text"].count("?") == 0

    def test_specific_training_detail_gets_a_grounded_deadpan_move(self):
        from mission_control.services.lead_nurture import build_reply_suggestion

        result = build_reply_suggestion(
            text=(
                "Training is going pretty well. Long climbs still fall apart, "
                "and I am usually behind on fueling by hour three."
            ),
            first_name="Jane",
            seed="stable",
        )
        assert result["question_type"] == "fueling"
        assert "Long climbs are pretty honest" in result["draft_text"]
        assert "legs, breathing, or fueling" in result["draft_text"]
        assert result["draft_text"].count("?") == 1

    def test_question_ladder_continues_instead_of_restarting(self):
        from mission_control.services.lead_nurture import build_reply_suggestion

        result = build_reply_suggestion(
            text="Training is going well.",
            first_name="Jane",
            prior_question_type="challenge",
        )
        assert result["question_type"] == "favorite_workout"
        assert "look forward to" in result["draft_text"]

    def test_third_lead_turn_requires_value_before_more_questions(self):
        from mission_control.services.lead_nurture import build_reply_suggestion

        result = build_reply_suggestion(
            text="Tuesday is usually the hard day.",
            first_name="Jane",
            prior_question_type="schedule",
            lead_turn=3,
        )
        assert result["needs_coach_answer"] is True
        assert "[Add one useful observation" in result["draft_text"]


class TestGmailIngestion:
    def test_closed_won_contact_is_not_offered_to_lead_bridge(self, fake_db):
        from mission_control.services.lead_nurture import get_sync_candidates

        fake_db.store["gg_sequence_enrollments"].append(
            make_enrollment(contact_email="athlete@example.com"),
        )
        fake_db.store["gg_deals"].append(
            make_deal(contact_email="athlete@example.com", stage="closed_won"),
        )
        assert get_sync_candidates() == []

    def test_known_lead_reply_is_attributed_and_pauses_marketing(self, fake_db):
        from mission_control.services.lead_nurture import ingest_gmail_sync

        enrollment = make_enrollment(contact_email="lead@example.com", contact_name="Jane Lead")
        deal = make_deal(contact_email="lead@example.com", contact_name="Jane Lead")
        send = make_sequence_send(
            enrollment_id=enrollment["id"],
            reply_token="0123456789abcdef0123456789abcdef",
            reply_count=0,
            first_reply_at=None,
            question_type="training_status",
            sent_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        )
        fake_db.store["gg_sequence_enrollments"].append(enrollment)
        fake_db.store["gg_deals"].append(deal)
        fake_db.store["gg_sequence_sends"].append(send)

        result = ingest_gmail_sync({"threads": [{"id": "thread-1", "messages": [_message()]}]})

        assert result == {"threads": 1, "recorded": 1, "messages": 1, "paused": 1, "ignored": 0}
        assert enrollment["status"] == "paused_reply"
        stored = fake_db.store["gg_lead_messages"][0]
        assert stored["sequence_send_id"] == send["id"]
        assert stored["attribution_confidence"] == "exact"
        assert send["reply_count"] == 1
        assert send["first_reply_at"] is not None
        assert len(fake_db.store["gg_lead_reply_suggestions"]) == 1

    def test_post_purchase_service_sequence_is_not_paused(self, fake_db):
        from mission_control.services.lead_nurture import ingest_gmail_sync

        enrollment = make_enrollment(
            sequence_id="post_purchase_v1", contact_email="lead@example.com",
        )
        fake_db.store["gg_sequence_enrollments"].append(enrollment)
        fake_db.store["gg_deals"].append(make_deal(contact_email="lead@example.com"))
        result = ingest_gmail_sync({"threads": [{"id": "thread-2", "messages": [_message()]}]})
        assert result["paused"] == 0
        assert enrollment["status"] == "active"

    def test_unknown_mailbox_is_ignored_without_storing_body(self, fake_db):
        from mission_control.services.lead_nurture import ingest_gmail_sync

        result = ingest_gmail_sync({
            "threads": [{"id": "private-thread", "messages": [
                _message(sender="Other Person <other@example.com>", body="private unrelated email"),
            ]}],
        })
        assert result["ignored"] == 1
        assert fake_db.store["gg_lead_messages"] == []

    def test_overlap_is_idempotent(self, fake_db):
        from mission_control.services.lead_nurture import ingest_gmail_sync

        fake_db.store["gg_sequence_enrollments"].append(
            make_enrollment(contact_email="lead@example.com"),
        )
        payload = {"threads": [{"id": "thread-3", "messages": [_message()]}]}
        assert ingest_gmail_sync(payload)["messages"] == 1
        assert ingest_gmail_sync(payload)["messages"] == 0
        assert len(fake_db.store["gg_lead_messages"]) == 1
        assert len(fake_db.store["gg_lead_reply_suggestions"]) == 1

    def test_untracked_existing_draft_is_surfaced_as_conflict(self, fake_db):
        from mission_control.services.lead_nurture import ingest_gmail_sync

        fake_db.store["gg_sequence_enrollments"].append(
            make_enrollment(contact_email="lead@example.com"),
        )
        draft = _message(
            message_id="old-draft-1",
            sender="Gravel God <gravelgodcoaching@gmail.com>",
            recipients=["lead@example.com"],
            body="An old draft that needs review.",
            is_draft=True,
        )
        result = ingest_gmail_sync({"threads": [{"id": "thread-draft", "messages": [draft]}]})
        assert result["messages"] == 1
        suggestion = fake_db.store["gg_lead_reply_suggestions"][0]
        assert suggestion["status"] == "draft_conflict"
        assert suggestion["gmail_draft_message_id"] == "old-draft-1"

    def test_tracked_bridge_draft_is_not_duplicated_as_conflict(self, fake_db):
        from mission_control.services.lead_nurture import ingest_gmail_sync

        enrollment = make_enrollment(contact_email="lead@example.com")
        fake_db.store["gg_sequence_enrollments"].append(enrollment)
        conversation = {
            "id": "conv-1", "gmail_thread_id": "thread-tracked",
            "contact_email": "lead@example.com", "contact_name": "Jane",
            "brand": "gravelgod", "status": "gmail_drafted",
        }
        fake_db.store["gg_lead_conversations"].append(conversation)
        fake_db.store["gg_lead_reply_suggestions"].append({
            "id": "suggestion-1", "conversation_id": "conv-1",
            "inbound_message_id": "gmail-in-prior", "status": "gmail_drafted",
            "gmail_draft_message_id": "tracked-draft-1",
        })
        draft = _message(
            message_id="tracked-draft-1",
            sender="Gravel God <gravelgodcoaching@gmail.com>",
            recipients=["lead@example.com"], is_draft=True,
        )
        ingest_gmail_sync({"threads": [{"id": "thread-tracked", "messages": [draft]}]})
        assert len(fake_db.store["gg_lead_reply_suggestions"]) == 1
        assert conversation["status"] == "gmail_drafted"

    def test_consecutive_inbound_messages_supersede_older_unapproved_draft(self, fake_db):
        from mission_control.services.lead_nurture import ingest_gmail_sync

        fake_db.store["gg_sequence_enrollments"].append(
            make_enrollment(contact_email="lead@example.com"),
        )
        now = datetime.now(timezone.utc)
        payload = {"threads": [{"id": "thread-consecutive", "messages": [
            _message(
                message_id="in-first", body="Training is going well.",
                date=(now - timedelta(minutes=2)).isoformat(),
            ),
            _message(
                message_id="in-second", body="The climbs are the hard part.",
                date=now.isoformat(),
            ),
        ]}]}
        ingest_gmail_sync(payload)
        suggestions = fake_db.store["gg_lead_reply_suggestions"]
        assert [row["status"] for row in suggestions] == ["superseded", "suggested"]


class TestDraftApproval:
    def _seed(self, fake_db):
        from mission_control.services.lead_nurture import ingest_gmail_sync

        fake_db.store["gg_sequence_enrollments"].append(
            make_enrollment(contact_email="lead@example.com", contact_name="Jane Lead"),
        )
        ingest_gmail_sync({"threads": [{"id": "thread-4", "messages": [_message()]}]})
        return fake_db.store["gg_lead_reply_suggestions"][0]

    def test_approval_exposes_draft_to_relay_but_does_not_send(self, fake_db):
        from mission_control.services.lead_nurture import (
            approve_reply_suggestion, get_approved_drafts,
        )

        suggestion = self._seed(fake_db)
        approved = approve_reply_suggestion(suggestion["id"], suggestion["draft_text"])
        assert approved["status"] == "approved_for_gmail"
        ready = get_approved_drafts()
        assert len(ready) == 1
        assert ready[0]["inbound_message_id"] == "gmail-in-1"
        assert not fake_db.store["gg_lead_messages"][0].get("sent_at")

    def test_existing_gmail_draft_becomes_conflict(self, fake_db):
        from mission_control.services.lead_nurture import (
            approve_reply_suggestion, record_draft_receipt,
        )

        suggestion = self._seed(fake_db)
        approve_reply_suggestion(suggestion["id"], suggestion["draft_text"])
        receipt = record_draft_receipt(suggestion["id"], {
            "status": "draft_conflict", "gmail_draft_message_id": "existing-1",
        })
        assert receipt == {"status": "draft_conflict"}
        assert suggestion["status"] == "draft_conflict"

    def test_answer_required_draft_cannot_be_approved_unchanged(self, fake_db):
        from mission_control.services.lead_nurture import (
            approve_reply_suggestion, ingest_gmail_sync,
        )

        fake_db.store["gg_sequence_enrollments"].append(
            make_enrollment(contact_email="lead@example.com", contact_name="Jane Lead"),
        )
        ingest_gmail_sync({"threads": [{"id": "thread-question", "messages": [
            _message(body="How much is coaching?"),
        ]}]})
        suggestion = fake_db.store["gg_lead_reply_suggestions"][0]
        assert suggestion["status"] == "needs_coach_answer"
        assert approve_reply_suggestion(suggestion["id"], suggestion["draft_text"]) is None

        edited = suggestion["draft_text"].replace(
            "[Answer their question directly first.]",
            "I’ll give you the current rate and the exact checkout link below.",
        )
        assert approve_reply_suggestion(suggestion["id"], edited)["status"] == "approved_for_gmail"

    def test_newer_inbound_supersedes_approved_but_not_yet_created_draft(self, fake_db):
        from mission_control.services.lead_nurture import get_approved_drafts

        conversation_id = "conv-newer"
        now = datetime.now(timezone.utc)
        fake_db.store["gg_lead_conversations"].append({
            "id": conversation_id, "gmail_thread_id": "thread-newer",
            "contact_email": "lead@example.com",
        })
        fake_db.store["gg_lead_messages"].extend([
            {
                "gmail_message_id": "in-old", "conversation_id": conversation_id,
                "direction": "inbound", "message_at": (now - timedelta(minutes=2)).isoformat(),
            },
            {
                "gmail_message_id": "in-new", "conversation_id": conversation_id,
                "direction": "inbound", "message_at": now.isoformat(),
            },
        ])
        suggestion = {
            "id": "suggestion-newer", "conversation_id": conversation_id,
            "inbound_message_id": "in-old", "status": "approved_for_gmail",
            "approved_at": now.isoformat(), "draft_text": "Old approved text",
        }
        fake_db.store["gg_lead_reply_suggestions"].append(suggestion)
        assert get_approved_drafts() == []
        assert suggestion["status"] == "superseded"


class TestReplyToken:
    def test_tagged_reply_to_preserves_normal_gmail_delivery(self):
        from mission_control.services.sequence_engine import _tagged_reply_to

        tagged = _tagged_reply_to(
            "Gravel God <gravelgodcoaching@gmail.com>",
            "0123456789abcdef0123456789abcdef",
        )
        assert tagged == (
            "Gravel God <gravelgodcoaching+lead."
            "0123456789abcdef0123456789abcdef@gmail.com>"
        )

    def test_non_gmail_reply_to_is_not_assumed_to_support_plus_aliases(self):
        from mission_control.services.sequence_engine import _tagged_reply_to

        assert _tagged_reply_to(
            "Matti <coach@example.com>",
            "0123456789abcdef0123456789abcdef",
        ) == "Matti <coach@example.com>"

    def test_spam_complaint_unsubscribes_enrollment(self, fake_db):
        from mission_control.services.sequence_engine import record_event

        enrollment = make_enrollment()
        send = make_sequence_send(enrollment_id=enrollment["id"], resend_id="re-complaint")
        fake_db.store["gg_sequence_enrollments"].append(enrollment)
        fake_db.store["gg_sequence_sends"].append(send)
        assert record_event("re-complaint", "email.complained") is True
        assert send["status"] == "complained"
        assert send["complained_at"] is not None
        assert enrollment["status"] == "unsubscribed"


class TestLearningMetrics:
    def test_small_samples_are_explicitly_not_a_verdict(self, fake_db):
        from mission_control.services.lead_nurture import get_learning_metrics

        fake_db.store["gg_sequence_sends"].append(make_sequence_send(
            question_type="challenge",
            sent_at=datetime.now(timezone.utc).isoformat(),
        ))
        report = get_learning_metrics()
        assert report["question_rows"][0]["sample_state"] == "keep_collecting"
        assert "never change live copy automatically" in report["measurement_note"]

    def test_manual_question_and_next_reply_feed_learning_loop(self, fake_db):
        from mission_control.services.lead_nurture import get_learning_metrics

        now = datetime.now(timezone.utc)
        conversation = {"id": "conv-m", "deal_id": None, "inbound_count": 1}
        fake_db.store["gg_lead_conversations"].append(conversation)
        fake_db.store["gg_lead_messages"].extend([
            {
                "gmail_message_id": "out-1", "conversation_id": "conv-m",
                "direction": "outbound", "question_type": "favorite_workout",
                "message_at": (now - timedelta(hours=3)).isoformat(),
            },
            {
                "gmail_message_id": "in-2", "conversation_id": "conv-m",
                "direction": "inbound", "reply_quality": "substantive",
                "message_at": (now - timedelta(hours=1)).isoformat(),
            },
        ])
        report = get_learning_metrics()
        row = next(row for row in report["question_rows"] if row["question_type"] == "favorite_workout")
        assert row["sends"] == 1
        assert row["replies"] == 1
        assert row["substantive_replies"] == 1
        assert row["median_reply_hours"] == 2.0

    def test_only_latest_manual_question_gets_reply_credit(self, fake_db):
        from mission_control.services.lead_nurture import get_learning_metrics

        now = datetime.now(timezone.utc)
        fake_db.store["gg_lead_conversations"].append({"id": "conv-latest", "deal_id": None})
        fake_db.store["gg_lead_messages"].extend([
            {
                "gmail_message_id": "out-challenge", "conversation_id": "conv-latest",
                "direction": "outbound", "question_type": "challenge",
                "message_at": (now - timedelta(hours=4)).isoformat(),
            },
            {
                "gmail_message_id": "out-favorite", "conversation_id": "conv-latest",
                "direction": "outbound", "question_type": "favorite_workout",
                "message_at": (now - timedelta(hours=3)).isoformat(),
            },
            {
                "gmail_message_id": "in-reply", "conversation_id": "conv-latest",
                "direction": "inbound", "reply_quality": "brief",
                "message_at": (now - timedelta(hours=1)).isoformat(),
            },
        ])
        report = get_learning_metrics()
        rows = {row["question_type"]: row for row in report["question_rows"]}
        assert rows["challenge"]["replies"] == 0
        assert rows["favorite_workout"]["replies"] == 1

    def test_editor_metrics_capture_acceptance_and_rewrite(self, fake_db):
        from mission_control.services.lead_nurture import get_learning_metrics

        fake_db.store["gg_lead_reply_suggestions"].append({
            "id": "s-1", "status": "sent",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "initial_draft_text": "Original easy question?",
            "draft_text": "A completely different approved reply?",
        })
        report = get_learning_metrics()
        assert report["suggestion_acceptance_rate"] == 100.0
        assert report["median_edit_percent"] > 0


class TestGmailSyncEndpoints:
    def test_sync_requires_auth(self, client):
        assert client.post("/webhooks/gmail-sync", json={"threads": []}).status_code == 401

    def test_sync_accepts_empty_authorized_batch(self, client):
        response = client.post(
            "/webhooks/gmail-sync", json={"threads": []},
            headers={"Authorization": "Bearer test-secret-123"},
        )
        assert response.status_code == 200
        assert response.json()["messages"] == 0


class TestLeadReplyEditor:
    def test_editor_is_admin_protected_and_renders_when_authorized(self, client):
        assert client.get("/lead-replies").status_code == 401
        response = client.get(
            "/lead-replies",
            headers={"Authorization": "Bearer test-secret-for-tests"},
        )
        assert response.status_code == 200
        assert "Lead Replies" in response.text
        assert "Nothing was sent" not in response.text

    def test_existing_draft_conflict_cannot_be_approved(self, client, fake_db):
        conversation_id = "11111111-1111-4111-8111-111111111111"
        suggestion_id = "22222222-2222-4222-8222-222222222222"
        fake_db.store["gg_lead_conversations"].append({
            "id": conversation_id,
            "gmail_thread_id": "thread-conflict",
            "contact_email": "lead@example.com",
            "contact_name": "Jane Lead",
            "brand": "gravelgod",
            "intent": "conversation",
        })
        fake_db.store["gg_lead_messages"].append({
            "gmail_message_id": "draft-existing",
            "conversation_id": conversation_id,
            "subject": "Re: training",
            "body_text": "Old version",
            "message_at": datetime.now(timezone.utc).isoformat(),
        })
        fake_db.store["gg_lead_reply_suggestions"].append({
            "id": suggestion_id,
            "conversation_id": conversation_id,
            "inbound_message_id": "draft-existing",
            "draft_text": "Old version",
            "question_type": "other",
            "status": "draft_conflict",
            "needs_coach_answer": False,
            "rationale": "Existing Gmail draft.",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        response = client.get(
            "/lead-replies",
            headers={"Authorization": "Bearer test-secret-for-tests"},
        )
        assert response.status_code == 200
        card = response.text.split(f'id="reply-{suggestion_id}"', 1)[1]
        assert "Existing Gmail draft" in card
        assert "Approve Gmail Draft" not in card.split("</article>", 1)[0]

        approve = client.post(
            f"/lead-replies/{suggestion_id}/approve",
            data={"draft_text": "Do not allow this."},
            headers={"Authorization": "Bearer test-secret-for-tests"},
        )
        assert approve.status_code == 409
