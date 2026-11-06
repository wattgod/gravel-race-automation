"""TrainingPeaks store sales -> post_purchase onboarding.

A plan sold on the TrainingPeaks store produces one notification email to the
coaching inbox (sender support@trainingpeaks.com, subject "Congratulations,
You Just Sold a Training Plan"). Those buyers got no follow-up. This module
turns one of those notifications into a post_purchase enrollment with
source "trainingpeaks_store", whose day-0 step renders tp_purchase_welcome
instead of the questionnaire receipt (see the step's source_overrides).

Gmail is read by the account-local Apps Script (integrations/gmail-lead-bridge,
runTpStoreSalesSync), the same auth path as the lead reply loop: Mission
Control holds no Gmail credentials. The script POSTs candidate messages to
/webhooks/tp-store-sales and this module does the rest.

OFF by default: nothing is parsed, recorded or enrolled unless
TP_BUYER_INGEST_ENABLED is set (config.tp_buyer_ingest_enabled). A dry run
parses and reports but writes nothing, flag or not.

Dedup: every Gmail message that reaches a final outcome gets one gg_audit_log
row (action tp_store_sale_processed, entity_id = Gmail message id). No new
table, no migration. Outcomes that may succeed on a later run (unparsed,
unverified sender) are not recorded, so a parser fix picks them up again.

parse_tp_sale_email() is pure: no I/O, no clock.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from html import unescape
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

TP_SALE_SENDER = "support@trainingpeaks.com"
TP_SALE_SUBJECT = "Congratulations, You Just Sold a Training Plan"
SOURCE = "trainingpeaks_store"
PROCESSED_ACTION = "tp_store_sale_processed"
TP_BRAND = "gravelgod"
MAX_MESSAGES_PER_CALL = 50

# Recorded (final) outcomes: enrolled, skipped_no_email, skipped_stale,
# skipped_unsubscribed, skipped_already_purchased. Never recorded, so retried
# on the next run: unparsed, unverified_sender. Not processed: duplicate,
# invalid_id.


# ---------------------------------------------------------------------------
# Pure parsing
# ---------------------------------------------------------------------------

_ANCHOR_RE = re.compile(r"purchased\s+through\s+TrainingPeaks\s*[!.]?", re.I)
_END_RE = re.compile(r"You\s+will\s+receive\s+payment", re.I)
_PRICE_RE = re.compile(
    r"^(?:US\s*)?\$\s*(\d{1,6}(?:,\d{3})*(?:\.\d{1,2})?)(?:\s*USD)?$", re.I)
_EMAIL_IN_LINE_RE = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_EMAIL_FULL_RE = re.compile(r"^[^@\s<>()]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
_LABELS = (r"(?:training\s+plan|plan\s+name|plan|athlete(?:\s+name)?|buyer(?:\s+name)?|"
           r"customer(?:\s+name)?|purchased\s+by|name|e-?mail(?:\s+address)?|price|amount)")
_LABEL_RE = re.compile(r"^" + _LABELS + r"\s*:\s*", re.I)
_LABEL_ONLY_RE = re.compile(r"^" + _LABELS + r"\s*:?\s*$", re.I)
_WEEKS_RE = re.compile(r"(?<![\d.])(\d{1,2})\s*-?\s*(?:wks?|weeks?)\b", re.I)
_LEADING_NUMBER_RE = re.compile(r"^\s*\d{1,3}\s*[.)]\s*")
_PART_SPLIT_RE = re.compile(r"\s+[·|\-–—]\s+")

# Plan tiers as the TP catalog names them (scripts/sync_tp_race_plan_links.py
# TIER_ORDER), plus spelling variants. A plan name reads "<race> <sep> <tier>
# ..." only for race plans, so a tier in the second slot is what makes the
# first slot a race name.
_TIERS = {"finisher", "compete", "masters", "masters 50+", "time-crunched",
          "time crunched", "save my race"}
# A first slot that is the brand or a discipline is never a race.
_NOT_A_RACE = {"cycling", "gravel", "gravel god", "road", "roadie labs", "mtb",
               "xc ski labs", "training", "plan"}

_BLOCK_TAGS = {"p", "div", "br", "tr", "td", "th", "li", "ul", "ol", "table",
               "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "hr"}


class _HtmlText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script", "head", "title"):
            self._skip += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("style", "script", "head", "title"):
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _html_to_text(html: str) -> str:
    parser = _HtmlText()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        return ""
    return "".join(parser.parts)


def _clean_lines(text: str) -> list[str]:
    text = unescape(text or "").replace("\r", "\n").replace("\xa0", " ")
    lines = []
    for raw in text.split("\n"):
        line = re.sub(r"\s+", " ", raw).strip()
        if line:
            lines.append(line)
    return lines


def _sale_lines(text: str) -> list[str] | None:
    """Lines between the 'purchased through TrainingPeaks!' anchor and the
    'You will receive payment' line, or None when there is no anchor."""
    lines = _clean_lines(text)
    for i, line in enumerate(lines):
        m = _ANCHOR_RE.search(line)
        if not m:
            continue
        segment = [line[m.end():].strip()] + lines[i + 1:]
        out = []
        for seg_line in segment:
            end = _END_RE.search(seg_line)
            if end:
                head = seg_line[:end.start()].strip()
                if head:
                    out.append(head)
                break
            if seg_line:
                out.append(seg_line)
        return out
    return None


def plan_weeks_from_name(plan_name: str) -> int | None:
    """'12wk' / '(12 weeks)' / '12-week' -> 12. '10 hours/week' -> None."""
    m = _WEEKS_RE.search(plan_name or "")
    if not m:
        return None
    weeks = int(m.group(1))
    return weeks if 1 <= weeks <= 52 else None


def race_name_from_plan(plan_name: str) -> str | None:
    """The race a plan name names, or None when it names none.

    '8. Mid South - Finisher - Masters 50+ (12 weeks)' -> 'Mid South'
    'GFNY San Luis Potosí · Finisher · 12wk'          -> 'GFNY San Luis Potosí'
    'Cycling - Badass Base - 10 hours/week'           -> None
    """
    name = _LEADING_NUMBER_RE.sub("", plan_name or "").strip()
    parts = [p.strip() for p in _PART_SPLIT_RE.split(name) if p.strip()]
    if len(parts) < 2:
        return None
    tier = re.sub(r"\s*\(.*?\)\s*", " ", parts[1]).strip().casefold()
    if tier not in _TIERS:
        return None
    race = parts[0]
    if race.casefold() in _NOT_A_RACE or not re.search(r"[A-Za-z]", race):
        return None
    return race[:120]


def _iso_utc(value) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def is_tp_sale_subject(subject: str) -> bool:
    folded = re.sub(r"\s+", " ", subject or "").strip().casefold()
    # Gmail may prefix a forwarded copy ("Fwd: ..."): a forward is not TP's
    # own notification, so only the exact subject counts.
    return folded == TP_SALE_SUBJECT.casefold()


def _parse_lines(lines: list[str]) -> dict | None:
    lines = [_LABEL_RE.sub("", ln).strip() for ln in lines if not _LABEL_ONLY_RE.match(ln)]
    lines = [ln for ln in lines if ln]
    price_idx = next((i for i, ln in enumerate(lines) if _PRICE_RE.match(ln)), None)
    if price_idx is None:
        return None
    price = _PRICE_RE.match(lines[price_idx]).group(1).replace(",", "")

    email = None
    rest: list[str] = []
    for ln in lines[:price_idx]:
        found = _EMAIL_IN_LINE_RE.search(ln)
        if found and email is None:
            email = found.group(0)
            remainder = (ln[:found.start()] + ln[found.end():])
            remainder = re.sub(r"[<>()\[\]]|mailto:", " ", remainder)
            remainder = re.sub(r"\s+", " ", remainder).strip(" ,;-")
            if remainder:
                rest.append(remainder)
            continue
        rest.append(ln)
    if len(rest) < 2:
        return None
    plan_name = " ".join(rest[:-1]).strip()
    buyer_name = rest[-1].strip()
    if not plan_name or not buyer_name or len(plan_name) > 200 or len(buyer_name) > 120:
        return None
    if "$" in buyer_name or "@" in buyer_name:
        return None
    email = email.strip().lower() if email else None
    if email and not _EMAIL_FULL_RE.match(email):
        email = None
    return {"plan_name": plan_name, "buyer_name": buyer_name,
            "buyer_email": email, "price": price}


def parse_tp_sale_email(*, subject: str, text: str | None = None,
                        html: str | None = None, date=None) -> dict | None:
    """Parse one TrainingPeaks 'You Just Sold a Training Plan' email.

    Tries the plain-text body first, then the HTML body. Returns None for any
    mail that is not a TP sale notification or whose sale block cannot be
    read with confidence (a wrong split would greet a buyer by plan name).

    -> {plan_name, buyer_name, buyer_email|None, price, sold_at|None,
        plan_weeks|None, race_name|None}
    """
    if not is_tp_sale_subject(subject):
        return None
    parsed = None
    for body in (text, _html_to_text(html) if html else None):
        if not body:
            continue
        lines = _sale_lines(body)
        if lines:
            parsed = _parse_lines(lines)
        if parsed:
            break
    if not parsed:
        return None
    parsed["sold_at"] = _iso_utc(date)
    parsed["plan_weeks"] = plan_weeks_from_name(parsed["plan_name"])
    parsed["race_name"] = race_name_from_plan(parsed["plan_name"])
    return parsed


_AUTH_PASS_RE = re.compile(
    r"\b(?:dmarc=pass\b[^;]*?\bheader\.from=|dkim=pass\b[^;]*?\bheader\.[di]=@?)"
    r"(?:[A-Za-z0-9-]+\.)*trainingpeaks\.com(?![\w.-])", re.I)


def sender_is_trainingpeaks(from_header: str, auth_results: str) -> bool:
    """From: is TP's support address AND Gmail's own Authentication-Results
    shows DMARC or DKIM passing for trainingpeaks.com. A From: line alone is
    trivially forged, and a forged sale would mail whatever address it named
    from Matti's sending domain."""
    address = parseaddr(from_header or "")[1].strip().lower()
    if address != TP_SALE_SENDER:
        return False
    return bool(_AUTH_PASS_RE.search(auth_results or ""))


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

_MESSAGE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,128}$")


def _already_processed(message_ids: list[str]) -> set[str]:
    from mission_control import supabase_client as db

    if not message_ids:
        return set()
    rows = (db._table("gg_audit_log").select("entity_id")
            .eq("action", PROCESSED_ACTION).in_("entity_id", message_ids)
            .execute().data) or []
    return {r.get("entity_id") for r in rows}


def _record(message_id: str, outcome: str, detail: dict) -> None:
    from mission_control import supabase_client as db

    db.log_action(PROCESSED_ACTION, "gmail_message", message_id,
                  json.dumps({"outcome": outcome, **detail}, default=str)[:4000])


def _suppressed(email: str) -> bool:
    """Contact-level opt-out the engine already honours for marketing
    enrollments. plan_purchased is exempt from that guard inside enroll()
    (transactional), but a TP store buyer never asked us for email, so an
    earlier unsubscribe or spam complaint wins here."""
    from mission_control import supabase_client as db
    from mission_control.services.sequence_engine import OPT_OUT_FLAG

    rows = db.select("gg_sequence_enrollments", match={"contact_email": email})
    return any(r.get("status") == "unsubscribed" or (r.get("source_data") or {}).get(OPT_OUT_FLAG)
               for r in rows)


def _already_purchased(email: str) -> bool:
    """Any post-purchase enrollment (any brand, any source) or a coached
    athlete record means this person is already a customer we talk to."""
    from mission_control import supabase_client as db
    from mission_control.sequences import get_sequence

    for row in db.select("gg_sequence_enrollments", match={"contact_email": email}):
        if (get_sequence(row.get("sequence_id") or "") or {}).get("trigger") == "plan_purchased":
            return True
    return db.select_one("gg_athletes", columns="id", match={"email": email}) is not None


def enroll_post_purchase(email: str, name: str, source_data: dict) -> list[str]:
    """The existing enrollment path: every active plan_purchased sequence for
    the brand, through sequence_engine.enroll() (which refuses a second
    enrollment in the same sequence)."""
    from mission_control.sequences import get_sequences_for_trigger
    from mission_control.services.sequence_engine import enroll

    enrolled = []
    for seq in get_sequences_for_trigger("plan_purchased", brand=TP_BRAND):
        if enroll(email, name, seq["id"], source=SOURCE, source_data=dict(source_data)):
            enrolled.append(seq["id"])
    return enrolled


def ingest_tp_sale_messages(messages: list, *, dry_run: bool = False,
                            now: datetime | None = None) -> dict:
    """Enroll TP store buyers from Gmail message payloads.

    Each message: {id, from, subject, date, auth_results, body, html_body}.
    Returns {"status", "results": [{id, outcome, ...}], "counts"}.
    """
    from mission_control.config import tp_buyer_ingest_enabled, tp_buyer_max_age_days

    if not dry_run and not tp_buyer_ingest_enabled():
        return {"status": "disabled", "results": [], "counts": {}}

    now = now or datetime.now(timezone.utc)
    max_age = timedelta(days=tp_buyer_max_age_days())
    messages = [m for m in (messages or []) if isinstance(m, dict)][:MAX_MESSAGES_PER_CALL]
    ids = [str(m.get("id") or "") for m in messages]
    done = _already_processed([i for i in ids if _MESSAGE_ID_RE.match(i)])

    results = []
    seen: set[str] = set()
    for msg, message_id in zip(messages, ids):
        result = _ingest_one(msg, message_id, done | seen, dry_run=dry_run,
                             now=now, max_age=max_age)
        seen.add(message_id)
        results.append(result)

    counts: dict[str, int] = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    return {"status": "dry_run" if dry_run else "ok", "results": results, "counts": counts}


def _ingest_one(msg: dict, message_id: str, done: set[str], *, dry_run: bool,
                now: datetime, max_age: timedelta) -> dict:
    if not _MESSAGE_ID_RE.match(message_id):
        return {"id": message_id[:128], "outcome": "invalid_id"}
    if message_id in done:
        return {"id": message_id, "outcome": "duplicate"}
    if not sender_is_trainingpeaks(str(msg.get("from") or ""), str(msg.get("auth_results") or "")):
        logger.warning("tp sale %s: sender not verified as TrainingPeaks; skipped", message_id)
        return {"id": message_id, "outcome": "unverified_sender"}
    sale = parse_tp_sale_email(subject=str(msg.get("subject") or ""),
                               text=msg.get("body") or None,
                               html=msg.get("html_body") or None,
                               date=msg.get("date"))
    if not sale:
        logger.warning("tp sale %s: could not parse sale block; will retry", message_id)
        return {"id": message_id, "outcome": "unparsed"}

    preview = {"id": message_id, "plan_name": sale["plan_name"],
               "plan_weeks": sale["plan_weeks"], "race_name": sale["race_name"],
               "has_email": bool(sale["buyer_email"]), "sold_at": sale["sold_at"]}
    email = sale["buyer_email"]

    outcome = None
    sold_at = datetime.fromisoformat(sale["sold_at"]) if sale["sold_at"] else None
    if sold_at is None or now - sold_at > max_age:
        outcome = "skipped_stale"
    elif not email:
        outcome = "skipped_no_email"
    elif _suppressed(email):
        outcome = "skipped_unsubscribed"
    elif _already_purchased(email):
        outcome = "skipped_already_purchased"

    if dry_run:
        return {**preview, "outcome": outcome or "would_enroll"}

    detail = {"plan_name": sale["plan_name"], "sold_at": sale["sold_at"]}
    if outcome:
        if outcome == "skipped_no_email":
            # Nothing to mail; keep the name so Matti can find them in TP.
            detail["buyer_name"] = sale["buyer_name"]
            logger.info("tp sale %s: no buyer email; skipped", message_id)
        else:
            detail["email"] = email
        _record(message_id, outcome, detail)
        return {**preview, "outcome": outcome}

    source_data = {"brand": TP_BRAND, "plan_name": sale["plan_name"],
                   "price": sale["price"], "sold_at": sale["sold_at"],
                   "tp_gmail_message_id": message_id}
    if sale["plan_weeks"]:
        source_data["plan_weeks"] = sale["plan_weeks"]
    if sale["race_name"]:
        # race_name only, never race_slug: a slug would also put the buyer
        # in the race countdown and debrief marketing jobs.
        source_data["race_name"] = sale["race_name"]
    enrolled = enroll_post_purchase(email, sale["buyer_name"], source_data)
    outcome = "enrolled" if enrolled else "skipped_already_purchased"
    _record(message_id, outcome, {**detail, "email": email, "sequences": enrolled})
    return {**preview, "outcome": outcome}
