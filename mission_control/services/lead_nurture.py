"""Gmail-to-Mission-Control lead conversation and approval loop.

The bridge is intentionally conservative:
- Gmail remains the communication record.
- Mission Control stores a private, queryable snapshot and attribution.
- A real reply pauses marketing sequences immediately.
- Suggestions are editable and never send email.
- Only suggestions explicitly approved by Matti may become Gmail drafts.
"""

from __future__ import annotations

import hashlib
import html
import re
import statistics
from difflib import SequenceMatcher
from datetime import timedelta
from datetime import datetime, timezone
from email.utils import parseaddr

from mission_control import supabase_client as db
from mission_control.sequences import get_sequence


MAX_BODY_CHARS = 30_000
MAX_SUBJECT_CHARS = 500
MAX_THREADS_PER_SYNC = 100
MAX_MESSAGES_PER_THREAD = 50

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")
_REPLY_TOKEN_RE = re.compile(
    r"\+lead\.([a-f0-9]{32})@", re.IGNORECASE,
)
_QUOTED_LINE_RE = re.compile(
    r"^(?:On .+ wrote:|From:\s|Sent:\s|To:\s|Subject:\s|-{2,}\s*Original Message)",
    re.IGNORECASE,
)

_POST_PURCHASE_TRIGGERS = {"plan_purchased"}

_SUPPORT_TERMS = (
    "never received", "didn't receive", "did not receive", "no guide",
    "no attachment", "not attached", "missing attachment", "broken link",
    "can't open", "cannot open", "refund", "charged", "unsubscribe",
)
_BUYING_TERMS = (
    "how much", "price", "cost of coaching", "hire you", "work with you",
    "coaching", "training plan", "sign up", "subscribe",
)
_HEALTH_TERMS = (
    "injury", "injured", "pain", "sick", "illness", "covid", "knee",
    "back", "neck", "physical therapy", " pt ", "injection", "doctor",
)
_RACE_DECISION_TERMS = (
    "still deciding", "which race", "between", "enter", "register",
    "shortlist", "leaning toward", "overnight", "travel", "hotel",
)
_POSITIVE_TRAINING_TERMS = (
    "training is going well", "training was great", "feeling good",
    "going well", "going pretty well", "back training", "back!", "on track",
)
_DEFERRED_TERMS = ("deferred", "defer", "dns", "didn't race", "did not race")

_QUESTION_RULES = (
    ("resource_feedback", ("did it cover", "how did you like", "how'd the prep kit land", "how did the prep kit land")),
    ("workout_feedback", ("first rides feel", "how's it feeling", "numbers feel right")),
    ("health", ("anything hurt", "does it hurt", "pain")),
    ("favorite_workout", ("favorite workout", "workout do you", "look forward to")),
    ("frustration", ("frustrat", "most annoying", "bothering you")),
    ("challenge", ("challenge", "hardest", "get right", "holding you back")),
    ("race_decision", ("which race", "still deciding", "what matters most", "registered")),
    ("race_goal", ("training toward", "training for", "main goal", "a race")),
    ("race_outcome", ("how did it go", "how'd it go", "what went well", "what went badly")),
    ("training_status", ("how's training", "how is training", "where is the training")),
    ("schedule", ("weekly hours", "schedule", "your week", "time do you have")),
    ("fueling", ("fuel", "nutrition", "carb", "eat and drink")),
)


def normalize_email(value: str) -> str:
    """Extract and normalize one mailbox address."""
    address = parseaddr(value or "")[1].strip().lower()
    return address if _EMAIL_RE.match(address) else ""


def strip_quoted_reply(raw: str) -> str:
    """Keep the newly authored portion of a Gmail message."""
    text = html.unescape(raw or "").replace("\r", "")
    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">") or _QUOTED_LINE_RE.match(stripped):
            break
        if stripped:
            kept.append(stripped)
    cleaned = "\n".join(kept).strip()
    return cleaned[:MAX_BODY_CHARS]


def classify_question(text: str) -> str:
    folded = (text or "").casefold()
    for label, terms in _QUESTION_RULES:
        if any(term in folded for term in terms):
            return label
    return "other"


def _reply_quality(text: str) -> tuple[str, int]:
    words = re.findall(r"\b[\w'-]+\b", text or "")
    # Twenty words is enough to contain actionable training/race context,
    # while one-line answers remain correctly classified as brief.
    return ("substantive" if len(words) >= 20 else "brief", len(words))


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    folded = f" {(text or '').casefold()} "
    return any(term in folded for term in terms)


def classify_intent(text: str) -> str:
    if _contains_any(text, _SUPPORT_TERMS):
        return "support"
    if _contains_any(text, _BUYING_TERMS):
        return "buying"
    if _contains_any(text, _HEALTH_TERMS):
        return "health_constraint"
    if _contains_any(text, _RACE_DECISION_TERMS):
        return "race_decision"
    if _contains_any(text, _DEFERRED_TERMS):
        return "deferred"
    if _contains_any(text, _POSITIVE_TRAINING_TERMS):
        return "training_positive"
    return "conversation"


def _stable_choice(seed: str, choices: tuple[tuple[str, str], ...]) -> tuple[str, str]:
    index = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) % len(choices)
    return choices[index]


def _conversation_next_move(
    text: str, *, prior_question_type: str = "", seed: str = "",
) -> tuple[str, str, str]:
    """Choose a grounded next move without trying to perform a persona."""
    folded = (text or "").casefold()
    hours = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b", folded)
    mentions_climbing = any(term in folded for term in ("climb", "climbing", "uphill"))
    mentions_fueling = any(term in folded for term in ("fuel", "carb", "eat", "nutrition"))

    if mentions_climbing and mentions_fueling:
        return (
            "That makes sense. Long climbs are pretty honest about late fueling.",
            "fueling",
            "When the climbs come apart, what goes first — legs, breathing, or fueling?",
        )
    if mentions_fueling:
        return (
            "Yep. Fueling can turn a good day sideways pretty quietly.",
            "fueling",
            "Where does fueling usually start to get away from you?",
        )
    if mentions_climbing:
        return (
            "Got it. Climbs are not especially subtle about the weak link.",
            "challenge",
            "When a climb goes bad, what goes first — legs, breathing, or pacing?",
        )

    acknowledgement = "Good to hear."
    if hours:
        acknowledgement = f"Good to hear. {hours.group(1)} hours is a real week."
    ladder = {
        "challenge": ("favorite_workout", "What kind of workout do you actually look forward to?"),
        "frustration": ("favorite_workout", "What kind of workout has been feeling best lately?"),
        "favorite_workout": ("race_goal", "What are you training toward right now?"),
        "race_goal": ("schedule", "How much training time can you actually protect most weeks?"),
        "schedule": ("workout_feedback", "What kind of session has been clicking lately?"),
    }
    question_type, question = ladder.get(
        prior_question_type,
        _stable_choice(seed or text, (
            ("challenge", "What part of training feels hardest to get right right now?"),
            ("favorite_workout", "What kind of workout do you actually look forward to?"),
        )),
    )
    return acknowledgement, question_type, question


def build_reply_suggestion(
    *, text: str, first_name: str = "", seed: str = "",
    prior_question_type: str = "", lead_turn: int = 1,
) -> dict:
    """Build a deliberately plain Reflect → Ask starting point.

    No product pitch is generated. An explicit question, operational problem,
    or buying signal requires a coach answer before the draft can be approved.
    """
    intent = classify_intent(text)
    needs_answer = "?" in text or intent in {"support", "buying"}

    answer_placeholder = ""
    if intent == "support":
        acknowledgement = "Thanks for flagging that."
        question_type = "support_resolution"
        question = ""
        answer_placeholder = "[Say exactly what you did or will do next.]"
    elif intent == "buying":
        acknowledgement = "Yep — happy to give you a straight answer."
        question_type = "buying_context"
        question = "What are you hoping the plan or coaching solves for you?"
        answer_placeholder = "[Answer their question directly first.]"
    elif intent == "health_constraint":
        acknowledgement = "That sounds frustrating."
        question_type = "frustration"
        question = "What's the biggest thing keeping you from training normally right now?"
    elif intent == "race_decision":
        acknowledgement = "That makes sense."
        question_type = "race_decision"
        question = "What matters most in the choice — the course, the travel, or how it fits your training?"
    elif intent == "deferred":
        acknowledgement = "Got it."
        question_type = "challenge"
        question = "What ended up getting in the way?"
    elif intent == "training_positive":
        acknowledgement, question_type, question = _conversation_next_move(
            text, prior_question_type=prior_question_type, seed=seed,
        )
    else:
        acknowledgement = "Got it."
        ladder = {
            "challenge": ("favorite_workout", "What kind of workout has been feeling best lately?"),
            "favorite_workout": ("race_goal", "What are you training toward right now?"),
            "race_goal": ("schedule", "How much training time can you actually protect most weeks?"),
            "schedule": ("challenge", "What keeps getting in the way most often?"),
        }
        question_type, question = ladder.get(
            prior_question_type,
            ("challenge", "What's the biggest training challenge you're trying to sort out right now?"),
        )

    if needs_answer and not answer_placeholder:
        answer_placeholder = "[Answer their question directly first.]"
    elif lead_turn >= 3 and not answer_placeholder:
        # Do not turn the relationship into an intake form. By the third lead
        # turn, Matti should add value before asking for more context.
        answer_placeholder = "[Add one useful observation or practical suggestion from this thread.]"
        needs_answer = True

    greeting = f"{first_name}," if first_name else "Hey —"
    parts = [greeting, acknowledgement]
    if answer_placeholder:
        parts.append(answer_placeholder)
    if question:
        parts.append(question)
    parts.append("— Matti")
    draft = "\n\n".join(parts)
    move = (
        f"one easy {question_type.replace('_', ' ')} question"
        if question else "a direct service resolution before any nurture question"
    )
    rationale = f"Intent: {intent}. {move}; no pitch and no invented coaching claim."
    return {
        "intent": intent,
        "question_type": question_type,
        "suggested_question": question,
        "draft_text": draft,
        "needs_coach_answer": needs_answer,
        "rationale": rationale,
    }


def get_sync_candidates(limit: int = 500) -> list[dict]:
    """Return open lead mailboxes for the account-local Apps Script relay."""
    contacts: dict[str, dict] = {}
    deals = db.select("gg_deals", limit=limit)
    converted_emails = {
        normalize_email(row.get("contact_email", ""))
        for row in deals if row.get("stage") == "closed_won"
    }
    for enrollment in db.select("gg_sequence_enrollments", limit=limit):
        email = normalize_email(enrollment.get("contact_email", ""))
        if not email or email in converted_emails:
            continue
        seq = get_sequence(enrollment.get("sequence_id", "")) or {}
        if seq.get("trigger") in _POST_PURCHASE_TRIGGERS:
            continue
        contacts[email] = {
            "email": email,
            "name": enrollment.get("contact_name", ""),
            "brand": seq.get("brand", "gravelgod"),
        }
    for deal in deals:
        if deal.get("stage") in {"closed_won", "closed_lost"}:
            continue
        email = normalize_email(deal.get("contact_email", ""))
        if not email:
            continue
        existing = contacts.setdefault(email, {"email": email, "name": "", "brand": "gravelgod"})
        existing["name"] = existing.get("name") or deal.get("contact_name", "")
    return sorted(contacts.values(), key=lambda row: row["email"])[:limit]


def _contact_record(email: str) -> dict | None:
    # Existing rows predate strict lower-casing; compare normalized addresses.
    deal = next((
        row for row in db.select("gg_deals", limit=1000)
        if normalize_email(row.get("contact_email", "")) == email
    ), None)
    enrollments = [
        row for row in db.select("gg_sequence_enrollments", limit=1000)
        if normalize_email(row.get("contact_email", "")) == email
    ]
    if not deal and not enrollments:
        return None
    enrollment = enrollments[-1] if enrollments else {}
    seq = get_sequence(enrollment.get("sequence_id", "")) or {}
    return {
        "email": email,
        "name": (deal or {}).get("contact_name") or enrollment.get("contact_name", ""),
        "brand": seq.get("brand", "gravelgod"),
        "deal_id": (deal or {}).get("id"),
        "enrollments": enrollments,
    }


def _message_contact(message: dict, candidate_emails: set[str]) -> str:
    addresses = [normalize_email(message.get("from", ""))]
    addresses.extend(normalize_email(v) for v in message.get("to", []) or [])
    addresses.extend(normalize_email(v) for v in message.get("cc", []) or [])
    return next((address for address in addresses if address in candidate_emails), "")


def _direction(message: dict, contact_email: str) -> str:
    if message.get("is_draft"):
        return "draft"
    if normalize_email(message.get("from", "")) == contact_email:
        return "inbound"
    return "outbound"


def _parse_message_at(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _reply_token(message: dict) -> str:
    for value in (message.get("to", []) or []) + (message.get("cc", []) or []):
        match = _REPLY_TOKEN_RE.search(value or "")
        if match:
            return match.group(1).lower()
    return ""


def _sequence_attribution(contact: dict, message: dict) -> tuple[dict | None, str]:
    token = _reply_token(message)
    if token:
        exact = db.select_one("gg_sequence_sends", match={"reply_token": token})
        if exact:
            return exact, "exact"

    inbound_at = _parse_message_at(message.get("date", "")).isoformat()
    candidates: list[dict] = []
    for enrollment in contact.get("enrollments", []):
        for send in db.select("gg_sequence_sends", match={"enrollment_id": enrollment.get("id")}):
            sent_at = send.get("sent_at") or ""
            if not sent_at or sent_at <= inbound_at:
                candidates.append(send)
    if not candidates:
        return None, "none"
    candidates.sort(key=lambda row: row.get("sent_at") or "")
    return candidates[-1], "email_time"


def _pause_marketing_sequences(contact: dict) -> int:
    paused = 0
    for enrollment in contact.get("enrollments", []):
        if enrollment.get("status") != "active":
            continue
        seq = get_sequence(enrollment.get("sequence_id", "")) or {}
        if seq.get("trigger") in _POST_PURCHASE_TRIGGERS:
            continue
        db.update("gg_sequence_enrollments", {"status": "paused_reply"}, {"id": enrollment["id"]})
        enrollment["status"] = "paused_reply"
        paused += 1
    return paused


def _conversation(thread_id: str, contact: dict) -> dict:
    existing = db.select_one("gg_lead_conversations", match={"gmail_thread_id": thread_id})
    if existing:
        return existing
    return db.insert("gg_lead_conversations", {
        "gmail_thread_id": thread_id,
        "contact_email": contact["email"],
        "contact_name": contact.get("name", ""),
        "brand": contact.get("brand", "gravelgod"),
        "deal_id": contact.get("deal_id"),
        "status": "needs_reply",
    })


def _record_suggestion(conversation: dict, message: dict, body: str) -> dict:
    existing = db.select_one(
        "gg_lead_reply_suggestions", match={"inbound_message_id": message["id"]},
    )
    if existing:
        return existing
    prior_messages = db.select(
        "gg_lead_messages", match={"conversation_id": conversation["id"]},
        order="message_at", order_desc=True, limit=12,
    )
    prior_outbound = next((
        row for row in prior_messages
        if row.get("direction") == "outbound"
        and row.get("gmail_message_id") != message["id"]
    ), {})
    lead_turn = sum(1 for row in prior_messages if row.get("direction") == "inbound")

    # Consecutive inbound messages are one editor job. Approved or drafted work
    # remains visible, but older unapproved alternatives leave the queue.
    now = datetime.now(timezone.utc).isoformat()
    for pending in db.select(
        "gg_lead_reply_suggestions", match={"conversation_id": conversation["id"]},
    ):
        if pending.get("status") in {"suggested", "needs_coach_answer"}:
            db.update("gg_lead_reply_suggestions", {
                "status": "superseded", "updated_at": now,
            }, {"id": pending["id"]})
    first_name = (conversation.get("contact_name") or "").split(" ", 1)[0]
    suggestion = build_reply_suggestion(
        text=body,
        first_name=first_name,
        seed=f"{conversation.get('contact_email')}:{message['id']}",
        prior_question_type=prior_outbound.get("question_type") or "",
        lead_turn=lead_turn,
    )
    status = "needs_coach_answer" if suggestion["needs_coach_answer"] else "suggested"
    return db.insert("gg_lead_reply_suggestions", {
        "conversation_id": conversation["id"],
        "inbound_message_id": message["id"],
        "initial_draft_text": suggestion["draft_text"],
        "draft_text": suggestion["draft_text"],
        "suggested_question": suggestion["suggested_question"],
        "question_type": suggestion["question_type"],
        "needs_coach_answer": suggestion["needs_coach_answer"],
        "rationale": suggestion["rationale"],
        "status": status,
    })


def _record_existing_draft_conflict(
    conversation: dict, message: dict, body: str,
) -> dict | None:
    """Surface an untracked Gmail draft without ever replacing or duplicating it."""
    tracked = next((
        row for row in db.select(
            "gg_lead_reply_suggestions", match={"conversation_id": conversation["id"]},
        )
        if row.get("gmail_draft_message_id") == message["id"]
    ), None)
    if tracked:
        return None
    existing = db.select_one(
        "gg_lead_reply_suggestions", match={"inbound_message_id": message["id"]},
    )
    if existing:
        return existing
    return db.insert("gg_lead_reply_suggestions", {
        "conversation_id": conversation["id"],
        # The schema uses this as the unique source-message key. For a conflict,
        # the source is deliberately the existing Gmail draft itself.
        "inbound_message_id": message["id"],
        "initial_draft_text": body,
        "draft_text": body,
        "suggested_question": "",
        "question_type": classify_question(body),
        "needs_coach_answer": False,
        "rationale": (
            "An existing Gmail draft was found in this lead thread. Review it "
            "in Gmail; do not approve or create another version here."
        ),
        "status": "draft_conflict",
        "gmail_draft_message_id": message["id"],
    })


def _ingest_thread(thread: dict, candidate_map: dict[str, dict]) -> dict:
    thread_id = str(thread.get("id", ""))[:255]
    messages = (thread.get("messages") or [])[:MAX_MESSAGES_PER_THREAD]
    if not thread_id or not messages:
        return {"status": "ignored", "reason": "empty_thread"}

    candidate_emails = set(candidate_map)
    contact_email = ""
    for message in messages:
        contact_email = _message_contact(message, candidate_emails)
        if contact_email:
            break
    if not contact_email:
        return {"status": "ignored", "reason": "not_a_known_lead"}
    contact = _contact_record(contact_email)
    if not contact:
        return {"status": "ignored", "reason": "not_a_known_lead"}

    conversation = _conversation(thread_id, contact)
    inserted = 0
    latest_direction = None
    latest_message_id = None
    latest_at = None
    latest_intent = conversation.get("intent", "unknown")
    latest_question_type = conversation.get("latest_question_type", "other")
    last_sequence_send_id = conversation.get("last_sequence_send_id")
    first_reply_latency_seconds = conversation.get("first_reply_latency_seconds")
    inbound_delta = 0
    outbound_delta = 0
    substantive_delta = 0
    paused = 0

    for message in sorted(messages, key=lambda row: row.get("date", "")):
        message_id = str(message.get("id", ""))[:255]
        if not message_id or db.select_one("gg_lead_messages", match={"gmail_message_id": message_id}):
            continue
        direction = _direction(message, contact_email)
        message_at = _parse_message_at(message.get("date", ""))
        body = strip_quoted_reply(message.get("body", ""))
        quality, word_count = _reply_quality(body)
        sequence_send, confidence = (None, "none")
        if direction == "inbound":
            # Pause before any downstream drafting work. A suggestion failure
            # must never leave the marketing sequence free to send again.
            paused += _pause_marketing_sequences(contact)
            sequence_send, confidence = _sequence_attribution(contact, message)
        question_type = classify_question(body) if direction in {"outbound", "draft"} else "other"

        db.insert("gg_lead_messages", {
            "gmail_message_id": message_id,
            "conversation_id": conversation["id"],
            "gmail_thread_id": thread_id,
            "direction": direction,
            "from_address": normalize_email(message.get("from", "")),
            "to_addresses": [normalize_email(v) for v in message.get("to", []) or [] if normalize_email(v)],
            "cc_addresses": [normalize_email(v) for v in message.get("cc", []) or [] if normalize_email(v)],
            "subject": str(message.get("subject", ""))[:MAX_SUBJECT_CHARS],
            "body_text": body,
            "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "message_at": message_at.isoformat(),
            "sequence_send_id": (sequence_send or {}).get("id"),
            "attribution_confidence": confidence,
            "question_type": question_type,
            "reply_quality": quality,
            "word_count": word_count,
            "is_trash": bool(message.get("is_trash")),
        })
        inserted += 1
        latest_direction = direction
        latest_message_id = message_id
        latest_at = message_at

        if direction == "inbound":
            inbound_delta += 1
            substantive_delta += int(quality == "substantive")
            suggestion = _record_suggestion(conversation, message, body)
            latest_intent = classify_intent(body)
            latest_question_type = suggestion.get("question_type", "other")
            if sequence_send:
                current_send = db.select_one(
                    "gg_sequence_sends", match={"id": sequence_send["id"]},
                ) or sequence_send
                updates = {"reply_count": int(current_send.get("reply_count") or 0) + 1}
                if not current_send.get("first_reply_at"):
                    updates["first_reply_at"] = message_at.isoformat()
                    try:
                        sent_at = datetime.fromisoformat(
                            (current_send.get("sent_at") or "").replace("Z", "+00:00")
                        )
                        first_reply_latency_seconds = max(
                            0, int((message_at - sent_at).total_seconds()),
                        )
                    except (TypeError, ValueError):
                        pass
                db.update("gg_sequence_sends", updates, {"id": sequence_send["id"]})
                last_sequence_send_id = sequence_send["id"]
        elif direction == "outbound":
            outbound_delta += 1
            # A real sent reply supersedes every still-pending suggestion in this thread.
            for pending in db.select("gg_lead_reply_suggestions", match={"conversation_id": conversation["id"]}):
                if pending.get("status") in {"suggested", "needs_coach_answer", "approved_for_gmail", "gmail_drafted"}:
                    db.update("gg_lead_reply_suggestions", {
                        "status": "sent", "sent_at": message_at.isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }, {"id": pending["id"]})
        elif direction == "draft":
            _record_existing_draft_conflict(conversation, message, body)

    if inserted:
        now = datetime.now(timezone.utc).isoformat()
        status = conversation.get("status", "needs_reply")
        if latest_direction == "inbound":
            status = "suggested"
        elif latest_direction == "draft":
            tracked = next((
                row for row in db.select(
                    "gg_lead_reply_suggestions", match={"conversation_id": conversation["id"]},
                )
                if row.get("gmail_draft_message_id") == latest_message_id
                and row.get("status") == "gmail_drafted"
            ), None)
            status = "gmail_drafted" if tracked else "draft_conflict"
        elif latest_direction == "outbound":
            status = "waiting_on_lead"
        updates = {
            "status": status,
            "intent": latest_intent,
            "latest_question_type": latest_question_type,
            "last_sequence_send_id": last_sequence_send_id,
            "first_reply_latency_seconds": first_reply_latency_seconds,
            "inbound_count": int(conversation.get("inbound_count") or 0) + inbound_delta,
            "outbound_count": int(conversation.get("outbound_count") or 0) + outbound_delta,
            "substantive_reply_count": int(conversation.get("substantive_reply_count") or 0) + substantive_delta,
            "updated_at": now,
        }
        if latest_at and latest_direction == "inbound":
            updates["last_inbound_at"] = latest_at.isoformat()
        elif latest_at and latest_direction == "outbound":
            updates["last_outbound_at"] = latest_at.isoformat()
        db.update("gg_lead_conversations", updates, {"id": conversation["id"]})
        db.log_action(
            "gmail_lead_sync", "lead_conversation", conversation["id"],
            f"{inserted} new message(s); {paused} marketing enrollment(s) paused",
        )
    return {"status": "recorded", "messages": inserted, "paused": paused}


def ingest_gmail_sync(payload: dict) -> dict:
    threads = (payload.get("threads") or [])[:MAX_THREADS_PER_SYNC]
    candidates = get_sync_candidates()
    candidate_map = {row["email"]: row for row in candidates}
    results = [_ingest_thread(thread, candidate_map) for thread in threads]
    return {
        "threads": len(results),
        "recorded": sum(1 for row in results if row["status"] == "recorded"),
        "messages": sum(row.get("messages", 0) for row in results),
        "paused": sum(row.get("paused", 0) for row in results),
        "ignored": sum(1 for row in results if row["status"] == "ignored"),
    }


def get_approved_drafts(limit: int = 25) -> list[dict]:
    rows = db.select(
        "gg_lead_reply_suggestions",
        match={"status": "approved_for_gmail"},
        order="approved_at", limit=limit,
    )
    output = []
    for row in rows:
        inbound = db.select_one("gg_lead_messages", match={"gmail_message_id": row["inbound_message_id"]})
        conversation = db.select_one("gg_lead_conversations", match={"id": row["conversation_id"]})
        if not inbound or not conversation:
            continue
        newer_inbound = next((
            message for message in db.select(
                "gg_lead_messages", match={"conversation_id": row["conversation_id"]},
            )
            if message.get("direction") == "inbound"
            and (message.get("message_at") or "") > (inbound.get("message_at") or "")
        ), None)
        if newer_inbound:
            db.update("gg_lead_reply_suggestions", {
                "status": "superseded", "updated_at": datetime.now(timezone.utc).isoformat(),
            }, {"id": row["id"]})
            continue
        output.append({
            "suggestion_id": row["id"],
            "gmail_thread_id": conversation["gmail_thread_id"],
            "inbound_message_id": row["inbound_message_id"],
            "contact_email": conversation["contact_email"],
            "draft_text": row["draft_text"],
        })
    return output


def record_draft_receipt(suggestion_id: str, payload: dict) -> dict | None:
    suggestion = db.select_one("gg_lead_reply_suggestions", match={"id": suggestion_id})
    if not suggestion or suggestion.get("status") != "approved_for_gmail":
        return None
    receipt_status = payload.get("status")
    if receipt_status == "draft_conflict":
        status = "draft_conflict"
        conversation_status = "draft_conflict"
    elif receipt_status == "gmail_drafted":
        status = "gmail_drafted"
        conversation_status = "gmail_drafted"
    else:
        return None
    now = datetime.now(timezone.utc).isoformat()
    db.update("gg_lead_reply_suggestions", {
        "status": status,
        "gmail_draft_id": str(payload.get("gmail_draft_id", ""))[:255] or None,
        "gmail_draft_message_id": str(payload.get("gmail_draft_message_id", ""))[:255] or None,
        "drafted_at": now if status == "gmail_drafted" else None,
        "updated_at": now,
    }, {"id": suggestion_id})
    db.update("gg_lead_conversations", {
        "status": conversation_status, "updated_at": now,
    }, {"id": suggestion["conversation_id"]})
    db.log_action(status, "lead_reply_suggestion", suggestion_id)
    return {"status": status}


def get_reply_queue(limit: int = 100) -> list[dict]:
    """Return the editor queue with source message and conversation context."""
    actionable = {
        "suggested", "needs_coach_answer", "approved_for_gmail",
        "gmail_drafted", "draft_conflict",
    }
    rows = db.select(
        "gg_lead_reply_suggestions", order="created_at", order_desc=True, limit=limit,
    )
    output = []
    for row in rows:
        if row.get("status") not in actionable:
            continue
        inbound = db.select_one(
            "gg_lead_messages", match={"gmail_message_id": row["inbound_message_id"]},
        )
        conversation = db.select_one(
            "gg_lead_conversations", match={"id": row["conversation_id"]},
        )
        if not inbound or not conversation:
            continue
        thread_messages = db.select(
            "gg_lead_messages", match={"conversation_id": row["conversation_id"]},
            order="message_at", order_desc=True, limit=8,
        )
        output.append({
            **row,
            "contact_email": conversation.get("contact_email", ""),
            "contact_name": conversation.get("contact_name", ""),
            "brand": conversation.get("brand", "gravelgod"),
            "intent": conversation.get("intent", "unknown"),
            "subject": inbound.get("subject", ""),
            "inbound_body": inbound.get("body_text", ""),
            "message_at": inbound.get("message_at"),
            "thread_context": list(reversed(thread_messages)),
        })
    return output


def approve_reply_suggestion(suggestion_id: str, draft_text: str) -> dict | None:
    suggestion = db.select_one("gg_lead_reply_suggestions", match={"id": suggestion_id})
    if not suggestion or suggestion.get("status") not in {"suggested", "needs_coach_answer"}:
        return None
    draft_text = (draft_text or "").strip()[:10_000]
    if not draft_text:
        return None
    if suggestion.get("needs_coach_answer"):
        initial = (suggestion.get("initial_draft_text") or "").strip()
        if (
            draft_text == initial
            or "[Answer " in draft_text
            or "[Say exactly " in draft_text
            or "[Add one useful " in draft_text
        ):
            return None
    now = datetime.now(timezone.utc).isoformat()
    updated = db.update("gg_lead_reply_suggestions", {
        "draft_text": draft_text,
        "question_type": classify_question(draft_text),
        "status": "approved_for_gmail",
        "approved_at": now,
        "updated_at": now,
    }, {"id": suggestion_id})
    db.update("gg_lead_conversations", {
        "status": "approved_for_gmail", "updated_at": now,
    }, {"id": suggestion["conversation_id"]})
    db.log_action("lead_reply_approved", "lead_reply_suggestion", suggestion_id)
    return updated


def dismiss_reply_suggestion(suggestion_id: str) -> dict | None:
    suggestion = db.select_one("gg_lead_reply_suggestions", match={"id": suggestion_id})
    if not suggestion or suggestion.get("status") in {"sent", "dismissed"}:
        return None
    now = datetime.now(timezone.utc).isoformat()
    updated = db.update("gg_lead_reply_suggestions", {
        "status": "dismissed", "updated_at": now,
    }, {"id": suggestion_id})
    db.update("gg_lead_conversations", {
        "status": "closed", "updated_at": now,
    }, {"id": suggestion["conversation_id"]})
    db.log_action("lead_reply_dismissed", "lead_reply_suggestion", suggestion_id)
    return updated


def get_learning_metrics(days: int = 90) -> dict:
    """Compute conversation outcomes without pretending tiny samples are verdicts."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    sends = db.select("gg_sequence_sends")
    sends = [row for row in sends if (row.get("sent_at") or "") >= since]
    messages = db.select("gg_lead_messages")
    messages = [row for row in messages if (row.get("message_at") or "") >= since]
    suggestions = db.select("gg_lead_reply_suggestions")
    conversations = db.select("gg_lead_conversations")
    enrollments = db.select("gg_sequence_enrollments")
    deals = {row.get("id"): row for row in db.select("gg_deals")}
    conversations_by_id = {row.get("id"): row for row in conversations}

    sends_by_id = {row.get("id"): row for row in sends}
    messages_by_conversation: dict[str, list[dict]] = {}
    for message in messages:
        messages_by_conversation.setdefault(message.get("conversation_id"), []).append(message)
    for conversation_messages in messages_by_conversation.values():
        conversation_messages.sort(key=lambda row: row.get("message_at") or "")
    inbound_by_send: dict[str, list[dict]] = {}
    for message in messages:
        send_id = message.get("sequence_send_id")
        if message.get("direction") == "inbound" and send_id in sends_by_id:
            inbound_by_send.setdefault(send_id, []).append(message)

    by_question: dict[str, dict] = {}
    latencies: list[float] = []
    coach_response_latencies: list[float] = []

    def bucket_for(question_type: str) -> dict:
        return by_question.setdefault(question_type or "other", {
            "question_type": question_type or "other",
            "sends": 0,
            "replies": 0,
            "substantive_replies": 0,
            "assisted_wins": 0,
            "latencies": [],
        })

    for send in sends:
        question_type = send.get("question_type") or "other"
        bucket = bucket_for(question_type)
        bucket["sends"] += 1
        replies = []
        for reply in inbound_by_send.get(send.get("id"), []):
            # Once Matti has replied manually, the next lead reply measures that
            # manual question—not the older sequence email.
            sent_at_text = send.get("sent_at") or ""
            reply_at_text = reply.get("message_at") or ""
            intervening_manual = any(
                candidate.get("direction") == "outbound"
                and sent_at_text < (candidate.get("message_at") or "") < reply_at_text
                for candidate in messages_by_conversation.get(reply.get("conversation_id"), [])
            )
            if not intervening_manual:
                replies.append(reply)
        if replies:
            bucket["replies"] += 1
            bucket["substantive_replies"] += int(any(
                row.get("reply_quality") == "substantive" for row in replies
            ))
            won = any(
                deals.get(conversations_by_id.get(row.get("conversation_id"), {}).get("deal_id"), {}).get("stage")
                == "closed_won"
                for row in replies
            )
            bucket["assisted_wins"] += int(won)
            try:
                sent_at = datetime.fromisoformat((send.get("sent_at") or "").replace("Z", "+00:00"))
                reply_at = min(
                    datetime.fromisoformat(row["message_at"].replace("Z", "+00:00"))
                    for row in replies
                )
                seconds = max(0.0, (reply_at - sent_at).total_seconds())
                bucket["latencies"].append(seconds)
                latencies.append(seconds)
            except (KeyError, TypeError, ValueError):
                pass

    # Manual Gmail replies are experiments too. Attribute the next inbound in
    # the same thread to the question Matti actually sent.
    for conversation_messages in messages_by_conversation.values():
        for index, message in enumerate(conversation_messages):
            if message.get("direction") != "outbound":
                continue
            question_type = message.get("question_type") or "other"
            bucket = bucket_for(question_type)
            bucket["sends"] += 1
            next_event = next((
                candidate for candidate in conversation_messages[index + 1:]
                if candidate.get("direction") in {"inbound", "outbound"}
            ), None)
            # When Matti sends twice before the lead answers, only the most
            # recent question gets credit.
            if not next_event or next_event.get("direction") != "inbound":
                continue
            reply = next_event
            bucket["replies"] += 1
            bucket["substantive_replies"] += int(reply.get("reply_quality") == "substantive")
            conversation = conversations_by_id.get(reply.get("conversation_id"), {})
            bucket["assisted_wins"] += int(
                deals.get(conversation.get("deal_id"), {}).get("stage") == "closed_won"
            )
            try:
                sent_at = datetime.fromisoformat(message["message_at"].replace("Z", "+00:00"))
                reply_at = datetime.fromisoformat(reply["message_at"].replace("Z", "+00:00"))
                seconds = max(0.0, (reply_at - sent_at).total_seconds())
                bucket["latencies"].append(seconds)
                latencies.append(seconds)
            except (KeyError, TypeError, ValueError):
                pass

        # Responsiveness is a service KPI: time from each inbound to Matti's
        # next sent reply, without counting drafts.
        for index, message in enumerate(conversation_messages):
            if message.get("direction") != "inbound":
                continue
            next_event = next((
                candidate for candidate in conversation_messages[index + 1:]
                if candidate.get("direction") in {"inbound", "outbound"}
            ), None)
            # Consecutive inbound messages form one lead turn; measure response
            # time from the final message before Matti replies.
            if not next_event or next_event.get("direction") != "outbound":
                continue
            outbound = next_event
            try:
                inbound_at = datetime.fromisoformat(message["message_at"].replace("Z", "+00:00"))
                outbound_at = datetime.fromisoformat(outbound["message_at"].replace("Z", "+00:00"))
                coach_response_latencies.append(max(0.0, (outbound_at - inbound_at).total_seconds()))
            except (KeyError, TypeError, ValueError):
                pass

    question_rows = []
    for bucket in by_question.values():
        sends_count = bucket["sends"]
        replies_count = bucket["replies"]
        sample_state = "enough_to_review" if sends_count >= 30 else "keep_collecting"
        question_rows.append({
            "question_type": bucket["question_type"],
            "sends": sends_count,
            "replies": replies_count,
            "reply_rate": round(replies_count / sends_count * 100, 1) if sends_count else 0.0,
            "substantive_replies": bucket["substantive_replies"],
            "assisted_wins": bucket["assisted_wins"],
            "median_reply_hours": round(statistics.median(bucket["latencies"]) / 3600, 1)
            if bucket["latencies"] else None,
            "sample_state": sample_state,
        })
    question_rows.sort(key=lambda row: (-row["sends"], row["question_type"]))

    replies = sum(row["replies"] for row in question_rows)
    total_sends = sum(row["sends"] for row in question_rows)
    open_after_reply = 0
    replied_contacts = {
        (row.get("contact_email") or "").strip().lower()
        for row in conversations if row.get("last_inbound_at")
    }
    for enrollment in enrollments:
        if enrollment.get("status") != "active":
            continue
        if (enrollment.get("contact_email") or "").strip().lower() not in replied_contacts:
            continue
        seq = get_sequence(enrollment.get("sequence_id", "")) or {}
        if seq.get("trigger") not in _POST_PURCHASE_TRIGGERS:
            open_after_reply += 1

    enough = [row for row in question_rows if row["sample_state"] == "enough_to_review"]
    recommendations = []
    draft_conflicts = sum(1 for row in suggestions if row.get("status") == "draft_conflict")
    editor_decisions = [
        row for row in suggestions
        if row.get("approved_at")
        or row.get("status") in {"dismissed", "superseded"}
    ]
    accepted = [
        row for row in editor_decisions if row.get("approved_at")
    ]
    edit_ratios = [
        1.0 - SequenceMatcher(
            None, row.get("initial_draft_text") or "", row.get("draft_text") or "",
        ).ratio()
        for row in accepted if row.get("initial_draft_text")
    ]
    if open_after_reply:
        recommendations.append(
            f"Safety: {open_after_reply} marketing enrollment(s) remain active after a reply; pause before another send."
        )
    if draft_conflicts:
        recommendations.append(
            f"Workflow: resolve {draft_conflicts} Gmail draft conflict(s); do not create another version."
        )
    if len(enough) >= 2:
        best = max(enough, key=lambda row: (row["reply_rate"], row["substantive_replies"]))
        recommendations.append(
            f"Review {best['question_type'].replace('_', ' ')} as the current leader "
            f"({best['reply_rate']}% replies across {best['sends']} sends). "
            "Run one approval-gated copy test; do not change every sequence."
        )
    else:
        recommendations.append(
            "Keep collecting. No question type has enough comparative volume for a copy verdict yet."
        )
    if len(edit_ratios) >= 20 and statistics.median(edit_ratios) >= 0.35:
        recommendations.append(
            "Voice fit: approved drafts are being substantially rewritten. Review the last 20 edits "
            "and update the suggestion rules only after Matti approves the pattern."
        )

    return {
        "days": days,
        "sends": total_sends,
        "replies": replies,
        "reply_rate": round(replies / total_sends * 100, 1) if total_sends else 0.0,
        "median_reply_hours": round(statistics.median(latencies) / 3600, 1) if latencies else None,
        "median_coach_response_hours": round(
            statistics.median(coach_response_latencies) / 3600, 1,
        ) if coach_response_latencies else None,
        "substantive_replies": sum(row["substantive_replies"] for row in question_rows),
        "second_reply_conversations": sum(
            1 for rows in messages_by_conversation.values()
            if sum(1 for row in rows if row.get("direction") == "inbound") >= 2
        ),
        "assisted_wins": len({
            row.get("conversation_id") for row in messages
            if row.get("direction") == "inbound"
            and deals.get(
                conversations_by_id.get(row.get("conversation_id"), {}).get("deal_id"), {},
            ).get("stage") == "closed_won"
        }),
        "unsubscribes": sum(1 for row in enrollments if row.get("status") == "unsubscribed"),
        "spam_complaints": sum(1 for row in sends if row.get("status") == "complained"),
        "active_after_reply": open_after_reply,
        "draft_conflicts": draft_conflicts,
        "pending_editor": sum(1 for row in suggestions if row.get("status") in {"suggested", "needs_coach_answer"}),
        "editor_decisions": len(editor_decisions),
        "suggestion_acceptance_rate": round(len(accepted) / len(editor_decisions) * 100, 1)
        if editor_decisions else None,
        "median_edit_percent": round(statistics.median(edit_ratios) * 100, 1)
        if edit_ratios else None,
        "question_rows": question_rows,
        "recommendations": recommendations,
        "measurement_note": (
            "Question types need at least 30 attributed sends before review. "
            "Recommendations never change live copy automatically."
        ),
    }
