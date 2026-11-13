"""Copy for the custom training plan billed every 4 weeks (2026-11-13).

The plan replaces the one-off race plan on every Gravel God page
(bbs-race-dataset research/SUBSCRIPTION_DESIGN.md §8.7). Every page that
offers the plan builds its lines from here, and every number comes from
pricing.py (data/pricing.json).

Source of the terms: the checkout server's race_plan_subscription.terms_text
(shown at Stripe checkout, Matti-approved 2026-11-12) and its rider payment
email (race_plan_emails.TEMPLATES['payment_confirmation'], approved the same
day). Nothing here promises more than those two say. Rules: "every 4 weeks",
never "monthly" or "/mo"; never call the plan coaching.

``stale_offer_phrases`` is the guard: tests/test_plan_offer_copy.py and
scripts/check_questionnaire_parity.py fail a page that still shows the
retired one-off offer next to the plan.
"""
from __future__ import annotations

import html as _html
import re

from pricing import (
    BLOCK_PRICE,
    BLOCK_PRICE_CENTS,
    BLOCK_WEEKS,
    PLAN_DELIVERY_HOURS,
    PLAN_PRICE_LINE,
    PLAN_REFUND_DAYS,
    WEEK_PRICE,
    money,
)

# "$49.99 every 4 weeks"
PRICE_LINE = PLAN_PRICE_LINE
# Button suffix, upper case: "$49.99 EVERY 4 WEEKS"
CTA_PRICE = PLAN_PRICE_LINE.upper()
# "$49.99 every 4 weeks until race week"
PRICE_TO_RACE = f"{PLAN_PRICE_LINE} until race week"
# A 4-week block spread over its 28 days, rounded up to the cent ("$1.79").
PER_DAY_PRICE = money(-(-BLOCK_PRICE_CENTS // (BLOCK_WEEKS * 7)))

BLOCKS_LINE = (f"Your plan goes on your TrainingPeaks calendar one {BLOCK_WEEKS}-week "
               "block at a time, and I look over every block before it goes on.")
LAST_BLOCK_LINE = (f"If your race isn't a whole number of {BLOCK_WEEKS}-week blocks away, "
                   f"the last, shorter block costs {WEEK_PRICE} a week.")
ENDS_LINE = "It ends after race week. Nothing is charged after that."
FIRST_BLOCK_LINE = (f"Block 1 arrives within {PLAN_DELIVERY_HOURS} hours of your payment "
                    "or of you connecting TrainingPeaks, whichever is later.")
CANCEL_LINE = "Cancel any time from your plan page; you keep any block you've paid for."
REFUND_LINE = f"Full refund within {PLAN_REFUND_DAYS} days of your first payment."
# One-line terms under a button.
TERMS_SHORT = (f"{PRICE_TO_RACE}. {REFUND_LINE} Cancel any time from your plan page.")

__all__ = [
    "BLOCK_PRICE", "PRICE_LINE", "PER_DAY_PRICE", "CTA_PRICE", "PRICE_TO_RACE", "BLOCKS_LINE",
    "LAST_BLOCK_LINE", "ENDS_LINE", "FIRST_BLOCK_LINE", "CANCEL_LINE",
    "REFUND_LINE", "TERMS_SHORT", "PLAN_PRICE_LINE", "stale_offer_phrases",
    "STALE_OFFER_PATTERNS",
]


# ── Guard: the retired one-off offer must not reappear next to the plan ──

# Phrases that only ever described the one-off plan (or that the 4-weekly
# plan must never use). Matched case-insensitively against visible text.
STALE_OFFER_PATTERNS: dict[str, re.Pattern] = {
    "$249": re.compile(r"\$249\b"),
    "One-time payment": re.compile(r"\bone[- ]time payment", re.I),
    "One payment": re.compile(r"\bone payment\b(?!\s+per\b)", re.I),
    "paid once": re.compile(r"\bpaid once\b", re.I),
    "no subscription": re.compile(r"\bno subscription\b", re.I),
    "/mo": re.compile(r"/\s?mo\b", re.I),
    "monthly": re.compile(r"\bmonthly\b", re.I),
    "per month": re.compile(r"\bper month\b", re.I),
    "7-day": re.compile(r"\b7[- ]day\b", re.I),
    "within 7 days": re.compile(r"\bwithin 7 days\b", re.I),
    "$15 a week": re.compile(r"\$15\s*(?:/\s*(?:wk|week)\b|a week|per week)", re.I),
}

# Where the plan is offered: text near any of these is "next to the offer".
_OFFER_ANCHORS = re.compile(
    r"\$49\.99|every 4 weeks|build my plan|custom (?:training )?plan|training plan",
    re.I,
)
# Characters of visible text on each side of an anchor that count as
# "next to the plan offer".
OFFER_WINDOW = 300


def visible_text(page_html: str) -> str:
    """Rough visible text: scripts/styles dropped, tags removed, entities
    decoded, whitespace collapsed."""
    text = re.sub(r"<(script|style)\b[\s\S]*?</\1>", " ", page_html, flags=re.I)
    text = re.sub(r"<!--[\s\S]*?-->", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = _html.unescape(text)
    return re.sub(r"\s+", " ", text)


def stale_offer_phrases(page_html: str, *, window: int = OFFER_WINDOW) -> list[str]:
    """Retired-offer phrases that appear within ``window`` characters of
    the plan offer in the page's visible text. A "monthly calendar" far
    from any plan offer is not flagged; "$249" near "BUILD MY PLAN" is."""
    text = visible_text(page_html)
    spans = [(max(0, m.start() - window), m.end() + window)
             for m in _OFFER_ANCHORS.finditer(text)]
    if not spans:
        return []
    found = []
    for label, pattern in STALE_OFFER_PATTERNS.items():
        for m in pattern.finditer(text):
            if any(a <= m.start() < b for a, b in spans):
                found.append(label)
                break
    return found
