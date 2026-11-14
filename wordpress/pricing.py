"""Single source of truth for prices shown anywhere on the site.

Loads `data/pricing.json` — see docs/specs/goals-2027-funnel-spec.md D18.
Every generator, template, and test that needs a price imports from here
instead of writing "$15" or "$60" as a literal. Change the number
in data/pricing.json once; every consumer picks it up.

Money amounts are stored in `data/pricing.json` as integer cents. Display
strings ("$15") are also stored there so copy always matches what
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
RACE_PLAN_4WEEKLY = PRICING["products"]["race_plan_4weekly"]

# ── The plan offer: custom training plan billed every 4 weeks (2026-11-13) ──
# Replaces the one-off race plan on every Gravel God page (SUBSCRIPTION_DESIGN
# §8.7). The math mirrors the checkout server's race_plan_subscription.py
# exactly: there is no quote endpoint, so a price shown here that differs from
# what Stripe charges is a lie on the page. tests/test_race_plan_4weekly_pricing.py
# pins the fixed cases and runs the generated JS against the Python.
PLAN_CHECKOUT_PRODUCT = RACE_PLAN_4WEEKLY["checkout_product"]    # "race_plan_4weekly"
BLOCK_WEEKS = RACE_PLAN_4WEEKLY["block_weeks"]                   # 4
BLOCK_PRICE_CENTS = RACE_PLAN_4WEEKLY["block_price_cents"]       # 4999
BLOCK_PRICE = RACE_PLAN_4WEEKLY["block_price_display"]           # "$49.99"
# Last, shorter block: block price / 4, rounded to the cent above ($12.50).
WEEK_PRICE_CENTS = -(-BLOCK_PRICE_CENTS // BLOCK_WEEKS)
PLAN_REFUND_DAYS = RACE_PLAN_4WEEKLY["refund_window_days"]       # 14
PLAN_DELIVERY_HOURS = RACE_PLAN_4WEEKLY["delivery_hours"]        # 24
PLAN_PRICE_LINE = f"{BLOCK_PRICE} every {BLOCK_WEEKS} weeks"     # "$49.99 every 4 weeks"


def money(cents: int) -> str:
    """"$49.99" style, always two decimals (the server's money())."""
    cents = int(cents)
    return f"${cents // 100:,}.{cents % 100:02d}"


WEEK_PRICE = money(WEEK_PRICE_CENTS)                              # "$12.50"


def weeks_until(race_date: date, today: date) -> int:
    """Whole weeks from today to the race, a part week counting as one.
    Same rule as the server's weeks_until; a race today or earlier has no
    plan (ValueError)."""
    days = (race_date - today).days
    if days <= 0:
        raise ValueError("Race date must be after today")
    return -(-days // 7)


def payment_plan(weeks: int) -> dict:
    """Payments and total for ``weeks`` of plan: full 4-week blocks at the
    block price, then one shorter block at the week price. No cap, no
    minimum. Same shape as the server's payment_plan."""
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
        "total_display": money(total),
        "first_payment_cents": payments[0],
    }


def plan_summary(weeks: int) -> str:
    """"3 payments, $149.97 in all" for a given plan length."""
    plan = payment_plan(weeks)
    n = plan["payment_count"]
    return f'{n} payment{"s" if n != 1 else ""}, {plan["total_display"]} in all'


def plan_quote_js() -> str:
    """The browser copy of weeks_until + payment_plan, constants from
    data/pricing.json. Defines ``ggPlanQuote(raceDateStr[, todayStr])`` returning
    {weeks, payments, totalCents, total, firstCents, first, summary} or null (no date, bad
    date, race today or past). Days are counted with Math.round so a DST
    shift (N days +/- 1 hour) can't add a week."""
    return (
        "function ggPlanMoney(c){c=Math.round(c);var d=Math.floor(c/100),r=c%100;"
        "return '$'+d.toLocaleString('en-US')+'.'+(r<10?'0':'')+r;}\n"
        "function ggPlanQuote(raceDateStr,todayStr){\n"
        "  if(!raceDateStr||!/^\\d{4}-\\d{2}-\\d{2}$/.test(raceDateStr))return null;\n"
        "  var race=new Date(raceDateStr+'T00:00:00');if(isNaN(race.getTime()))return null;\n"
        "  var today=todayStr?new Date(todayStr+'T00:00:00'):new Date();today.setHours(0,0,0,0);\n"
        "  var days=Math.round((race-today)/86400000);if(days<=0)return null;\n"
        "  var weeks=Math.ceil(days/7);\n"
        f"  var full=Math.floor(weeks/{BLOCK_WEEKS}),left=weeks%{BLOCK_WEEKS};\n"
        "  var payments=full+(left?1:0);\n"
        f"  var total=full*{BLOCK_PRICE_CENTS}+left*{WEEK_PRICE_CENTS};\n"
        f"  var first=full?{BLOCK_PRICE_CENTS}:left*{WEEK_PRICE_CENTS};\n"
        "  return {weeks:weeks,payments:payments,totalCents:total,total:ggPlanMoney(total),\n"
        "    firstCents:first,first:ggPlanMoney(first),\n"
        "    summary:payments+(payments===1?' payment, ':' payments, ')+ggPlanMoney(total)+' in all'};\n"
        "}\n"
    )


# ── Retired one-off race plan (kept for paid orders, reconciliation, and the
# Roadie Labs copy that hasn't switched). Never quote on a Gravel God page. ──
PRICE_PER_WEEK = RACE_PLAN["weekly_rate_display"]           # "$15"
PRICE_PER_WEEK_CENTS = RACE_PLAN["weekly_rate_cents"]        # 1500
MIN_WEEKS = RACE_PLAN["minimum_weeks"]                       # 4
RACE_PLAN_REFUND_DAYS = RACE_PLAN["refund_window_days"]      # 7
RACE_PLAN_DELIVERY_HOURS = RACE_PLAN["delivery_hours"]       # 24

# ── Season plan (RETIRED 2026-10-23; kept for reconciliation and the success page) ──
SEASON_PLAN_PRICE_DISPLAY = SEASON_PLAN["price_display"]     # "$499"
SEASON_PLAN_PRICE_CENTS = SEASON_PLAN["price_cents"]          # 49900
SEASON_PLAN_MAX_WEEKS = SEASON_PLAN["max_weeks"]              # 52
SEASON_PLAN_REBUILDS = SEASON_PLAN["scheduled_rebuilds"]      # 4
SEASON_PLAN_REFUND_DAYS = SEASON_PLAN["refund_window_days"]   # 7
SEASON_PLAN_DELIVERY_DAYS = SEASON_PLAN["delivery_days"]       # 3 (race plan stays 24h)


def compute_race_plan_price_cents(weeks: int) -> int:
    """Race-plan price in cents for a given number of weeks.

    Mirrors the checkout server's `compute_plan_price` (weeks-until-race
    logic lives there; this takes weeks directly so it can be shared by
    every page that needs to *display* a price without duplicating the
    date math). $15/week, 4-week minimum, no cap (Matti, 2026-10-23: one
    product, $15 for every week until the race).
    """
    weeks = max(MIN_WEEKS, int(weeks))
    return weeks * PRICE_PER_WEEK_CENTS


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
