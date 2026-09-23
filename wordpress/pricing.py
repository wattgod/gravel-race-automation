"""Single source of truth for prices shown anywhere on the site.

Loads `data/pricing.json` — see docs/specs/goals-2027-funnel-spec.md D18.
Every generator, template, and test that needs a price imports from here
instead of writing "$15" / "$249" / "$499" as a literal. Change the number
in data/pricing.json once; every consumer picks it up.

Money amounts are stored in `data/pricing.json` as integer cents. Display
strings ("$15", "$249") are also stored there so copy always matches what
Stripe actually charges — no `"$" + str(...)` formatting drift.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

PRICING_JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "pricing.json"

with open(PRICING_JSON_PATH, encoding="utf-8") as _f:
    PRICING = json.load(_f)

RACE_PLAN = PRICING["products"]["race_plan"]
SEASON_PLAN = PRICING["products"]["season_plan"]

# ── Race plan (backward-compatible names used across wordpress/generate_*.py) ──
PRICE_PER_WEEK = RACE_PLAN["weekly_rate_display"]           # "$15"
PRICE_CAP = RACE_PLAN["cap_display"]                        # "$249"
PRICE_PER_WEEK_CENTS = RACE_PLAN["weekly_rate_cents"]        # 1500
PRICE_CAP_CENTS = RACE_PLAN["cap_cents"]                     # 24900
MIN_WEEKS = RACE_PLAN["minimum_weeks"]                       # 4
RACE_PLAN_REFUND_DAYS = RACE_PLAN["refund_window_days"]      # 7
RACE_PLAN_DELIVERY_HOURS = RACE_PLAN["delivery_hours"]       # 24

# ── Season plan ──
SEASON_PLAN_PRICE_DISPLAY = SEASON_PLAN["price_display"]     # "$499"
SEASON_PLAN_PRICE_CENTS = SEASON_PLAN["price_cents"]          # 49900
SEASON_PLAN_MAX_WEEKS = SEASON_PLAN["max_weeks"]              # 52
SEASON_PLAN_REBUILDS = SEASON_PLAN["scheduled_rebuilds"]      # 4
SEASON_PLAN_REFUND_DAYS = SEASON_PLAN["refund_window_days"]   # 7


def compute_race_plan_price_cents(weeks: int) -> int:
    """Race-plan price in cents for a given number of weeks.

    Mirrors the checkout server's `compute_plan_price` (weeks-until-race
    logic lives there; this takes weeks directly so it can be shared by
    every page that needs to *display* a price without duplicating the
    date math). $15/week, 4-week minimum, $249 cap — never worth more than
    the cap no matter how many weeks out the race is.
    """
    weeks = max(MIN_WEEKS, int(weeks))
    return min(weeks * PRICE_PER_WEEK_CENTS, PRICE_CAP_CENTS)


def format_cents(cents: int) -> str:
    """Render whole-dollar cents as "$N" (every price in pricing.json is a whole dollar amount)."""
    if cents % 100:
        return f"${cents / 100:.2f}"
    return f"${cents // 100}"


def compute_season_plan_rebuild_dates(purchase_date: date) -> list[date]:
    """Four scheduled-rebuild dates for a Season Plan order, spread across
    the year from the purchase date (docs/specs/goals-2027-funnel-spec.md
    D2/D16). Data only — no scheduling side effect, no automation. The
    labour budget (SEASON_PLAN["labour_budget"]) only holds if a real
    engine (Motoren) performs each rebuild; that automation is out of
    scope here and belongs to the checkout/fulfilment system.

    Spaced at roughly 10, 23, 36, and 49 weeks out so no rebuild lands in
    the first ~10 weeks (too soon to need a rescale) or the last ~3 weeks
    (too close to matter) of a 52-week season.
    """
    offsets_weeks = (10, 23, 36, 49)
    return [purchase_date + timedelta(weeks=w) for w in offsets_weeks]
