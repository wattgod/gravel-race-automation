"""Single source of truth for prices Mission Control shows or reasons about.

Loads `data/pricing.json` — the same file `wordpress/pricing.py` reads for
the generated pages. See docs/specs/goals-2027-funnel-spec.md D18. Money
amounts are stored as integer cents; display strings ("$15") are
stored alongside them so copy always matches what Stripe actually charges.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from mission_control.config import REPO_ROOT

PRICING_JSON_PATH = REPO_ROOT / "data" / "pricing.json"

with open(PRICING_JSON_PATH, encoding="utf-8") as _f:
    PRICING = json.load(_f)

RACE_PLAN = PRICING["products"]["race_plan"]
SEASON_PLAN = PRICING["products"]["season_plan"]
RACE_PLAN_4WEEKLY = PRICING["products"]["race_plan_4weekly"]

# ── Plan billed every 4 weeks (Gravel God, 2026-11-13) ──
# Same math as wordpress.pricing and the checkout server's
# race_plan_subscription.payment_plan.
BLOCK_WEEKS = RACE_PLAN_4WEEKLY["block_weeks"]                   # 4
BLOCK_PRICE_CENTS = RACE_PLAN_4WEEKLY["block_price_cents"]       # 4999
BLOCK_PRICE = RACE_PLAN_4WEEKLY["block_price_display"]           # "$49.99"
WEEK_PRICE_CENTS = -(-BLOCK_PRICE_CENTS // BLOCK_WEEKS)          # 1250
PLAN_PRICE_LINE = f"{BLOCK_PRICE} every {BLOCK_WEEKS} weeks"
RACE_PLAN_4WEEKLY_RECONCILIATION_LABEL = RACE_PLAN_4WEEKLY["reconciliation_label"]


def _money(cents: int) -> str:
    return f"${cents // 100:,}.{cents % 100:02d}"


def payment_plan(weeks: int) -> dict:
    """Payments and total for ``weeks`` of plan; mirrors
    wordpress.pricing.payment_plan."""
    if isinstance(weeks, bool) or not isinstance(weeks, int) or weeks < 1:
        raise ValueError("A plan needs at least one week")
    full_blocks, leftover_weeks = divmod(weeks, BLOCK_WEEKS)
    payments = [BLOCK_PRICE_CENTS] * full_blocks
    if leftover_weeks:
        payments.append(WEEK_PRICE_CENTS * leftover_weeks)
    total = sum(payments)
    return {
        "weeks": weeks,
        "full_blocks": full_blocks,
        "leftover_weeks": leftover_weeks,
        "payment_count": len(payments),
        "payments_cents": payments,
        "total_cents": total,
        "total_display": _money(total),
        "first_payment_cents": payments[0],
    }

# ── Retired one-off race plan: paid orders, reconciliation, Roadie Labs copy ──

PRICE_PER_WEEK = RACE_PLAN["weekly_rate_display"]            # "$15"
PRICE_PER_WEEK_CENTS = RACE_PLAN["weekly_rate_cents"]         # 1500
MIN_WEEKS = RACE_PLAN["minimum_weeks"]                         # 4
RACE_PLAN_REFUND_DAYS = RACE_PLAN["refund_window_days"]        # 7
RACE_PLAN_DELIVERY_HOURS = RACE_PLAN["delivery_hours"]         # 24
RACE_PLAN_RECONCILIATION_LABEL = RACE_PLAN["reconciliation_label"]   # "training_plan"

# Season Plan: RETIRED 2026-10-23. Kept so past charges still reconcile.
SEASON_PLAN_PRICE_DISPLAY = SEASON_PLAN["price_display"]       # "$499"
SEASON_PLAN_PRICE_CENTS = SEASON_PLAN["price_cents"]            # 49900
SEASON_PLAN_REBUILDS = SEASON_PLAN["scheduled_rebuilds"]        # 4
SEASON_PLAN_REFUND_DAYS = SEASON_PLAN["refund_window_days"]     # 7
SEASON_PLAN_DELIVERY_DAYS = SEASON_PLAN["delivery_days"]         # 3 (race plan stays 24h)
SEASON_PLAN_RECONCILIATION_LABEL = SEASON_PLAN["reconciliation_label"]  # "season_plan"


def compute_race_plan_price_cents(weeks: int) -> int:
    """Race-plan price in cents for a given number of weeks. $15/week,
    4-week minimum, no cap — mirrors wordpress.pricing's function of the
    same name and the checkout server's compute_plan_price."""
    weeks = max(MIN_WEEKS, int(weeks))
    return weeks * PRICE_PER_WEEK_CENTS


def compute_season_plan_rebuild_dates(purchase_date: date) -> list[date]:
    """Four scheduled-rebuild dates for a Season Plan order, spread across
    the year from the purchase date (docs/specs/goals-2027-funnel-spec.md
    D2/D16). Data only — no scheduling side effect, no automation. Mirrors
    wordpress.pricing's function of the same name."""
    offsets_weeks = (10, 23, 36, 49)
    return [purchase_date + timedelta(weeks=w) for w in offsets_weeks]


# ── Reconciliation registry ──────────────────────────────────────────
# Every product we ever sell needs a display label here, keyed by the
# `offer_family` a Stripe charge carries (docs/specs/goals-2027-funnel-spec.md
# D15). A charge whose offer_family isn't in this map shows up in revenue
# reporting as "Unattributed Stripe charge" instead of a real product name.
RECONCILIATION_LABELS = {
    RACE_PLAN_RECONCILIATION_LABEL: RACE_PLAN["name"],
    RACE_PLAN_4WEEKLY_RECONCILIATION_LABEL: f'{RACE_PLAN_4WEEKLY["name"]}, every 4 weeks',
    SEASON_PLAN_RECONCILIATION_LABEL: SEASON_PLAN["name"],
    "consulting": "Consulting",
    "consult_addon": "Consulting add-on",
    "coaching": "Coaching",
}
