"""The plan billed every 4 weeks: page math must equal what Stripe charges.

There is no quote endpoint. The checkout server
(athlete-custom-training-plan-pipeline webhook/race_plan_subscription.py)
computes the payments from the A-race date; every Gravel God page computes
them again from data/pricing.json (wordpress/pricing.py for Python, the
generated ggPlanQuote for the browser). These tests pin both copies to the
server's rule: $49.99 per full 4-week block, the last shorter block at
$12.50 a week, weeks = days to the race / 7 rounded up, no cap, no minimum.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

import pricing  # noqa: E402
from pricing import payment_plan, plan_quote_js, plan_summary, weeks_until  # noqa: E402

FORM_JS = (ROOT / "web" / "training-plans-form.js").read_text()

# Fixed cases from the switch brief (2026-11-13). Cents.
FIXED = [
    (4, [4999]),
    (6, [4999, 2500]),
    (8, [4999, 4999]),
    (30, [4999] * 7 + [2500]),
]


def test_pricing_json_holds_the_server_constants():
    product = json.loads((ROOT / "data" / "pricing.json").read_text())["products"]["race_plan_4weekly"]
    assert product["checkout_product"] == "race_plan_4weekly"
    assert product["block_weeks"] == 4
    assert product["block_price_cents"] == 4999
    assert product["block_price_display"] == "$49.99"
    assert product["refund_window_days"] == 14
    # Server: WEEK_PRICE_CENTS = ceil(BLOCK_PRICE_CENTS / BLOCK_WEEKS)
    assert pricing.WEEK_PRICE_CENTS == 1250
    assert pricing.WEEK_PRICE == "$12.50"


@pytest.mark.parametrize("weeks,payments", FIXED)
def test_fixed_cases(weeks, payments):
    plan = payment_plan(weeks)
    assert plan["payments_cents"] == payments
    assert plan["total_cents"] == sum(payments)
    assert plan["first_payment_cents"] == payments[0]


def test_fixed_case_totals_in_words():
    assert plan_summary(4) == "1 payment, $49.99 in all"
    assert plan_summary(6) == "2 payments, $74.99 in all"
    assert plan_summary(8) == "2 payments, $99.98 in all"
    assert plan_summary(30) == "8 payments, $374.93 in all"


def test_short_plans_have_no_minimum():
    assert payment_plan(1)["payments_cents"] == [1250]
    assert payment_plan(3)["payments_cents"] == [3750]


@pytest.mark.parametrize("bad", [0, -1, 2.5, True, "4"])
def test_payment_plan_refuses_non_weeks(bad):
    with pytest.raises(ValueError):
        payment_plan(bad)


def test_weeks_until_rounds_part_weeks_up_and_refuses_today_or_past():
    today = date(2026, 11, 13)
    assert weeks_until(today + timedelta(days=1), today) == 1
    assert weeks_until(today + timedelta(days=7), today) == 1
    assert weeks_until(today + timedelta(days=8), today) == 2
    assert weeks_until(today + timedelta(days=210), today) == 30
    for days in (0, -3):
        with pytest.raises(ValueError):
            weeks_until(today + timedelta(days=days), today)


# ── The browser copy ─────────────────────────────────────────


def _node_quotes(cases: list[tuple[str, str]]) -> list:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    script = plan_quote_js() + (
        "var cases = " + json.dumps(cases) + ";\n"
        "console.log(JSON.stringify(cases.map(function(c){return ggPlanQuote(c[0], c[1]);})));\n"
    )
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_js_quote_equals_python_for_every_offset():
    today = date(2026, 11, 13)
    offsets = list(range(1, 400))
    cases = [((today + timedelta(days=d)).isoformat(), today.isoformat()) for d in offsets]
    quotes = _node_quotes(cases)
    for d, quote in zip(offsets, quotes):
        weeks = weeks_until(today + timedelta(days=d), today)
        plan = payment_plan(weeks)
        assert quote["weeks"] == weeks, d
        assert quote["payments"] == plan["payment_count"], d
        assert quote["totalCents"] == plan["total_cents"], d
        assert quote["firstCents"] == plan["first_payment_cents"], d
        assert quote["summary"] == plan_summary(weeks), d


def test_js_quote_fixed_cases_and_refusals():
    today = "2026-11-13"
    cases = [("2026-12-11", today), ("2026-12-25", today), ("2027-01-08", today),
             ("2027-06-11", today), (today, today), ("2026-11-01", today),
             ("", today), ("not-a-date", today)]
    four, six, eight, thirty, same_day, past, empty, bad = _node_quotes(cases)
    assert (four["weeks"], four["first"], four["total"]) == (4, "$49.99", "$49.99")
    assert (six["weeks"], six["payments"], six["total"]) == (6, 2, "$74.99")
    assert (eight["weeks"], eight["payments"], eight["total"]) == (8, 2, "$99.98")
    assert (thirty["weeks"], thirty["payments"], thirty["total"]) == (30, 8, "$374.93")
    assert same_day is None and past is None and empty is None and bad is None


def test_js_quote_survives_a_dst_change():
    """2027-03-14 (US spring forward) sits inside this range; whole-day
    rounding keeps a 28-day race at 4 weeks."""
    (quote,) = _node_quotes([("2027-04-02", "2027-03-05")])
    assert quote["weeks"] == 4 and quote["payments"] == 1


# ── The questionnaire form ───────────────────────────────────


def test_form_pricing_block_is_current():
    """web/training-plans-form.js carries the generated block verbatim;
    regenerate with scripts/generate_pricing_js.py after a pricing change."""
    import generate_pricing_js
    assert generate_pricing_js.build_block() in FORM_JS


def test_form_sends_the_4weekly_product_on_the_one_page_path():
    assert "var PLAN_PRODUCT = 'race_plan_4weekly';" in FORM_JS
    assert "workerData.product = PLAN_PRODUCT;" in FORM_JS
    # The server refuses intake_flow for this product.
    assert "intake_flow" not in FORM_JS.replace(
        "the server refuses intake_flow for it", "")


def test_form_quotes_from_the_payment_plan_not_a_per_week_rate():
    assert "ggPlanQuote(raceDateStr)" in FORM_JS
    assert "PRICE_PER_WEEK" not in FORM_JS
    assert "MIN_WEEKS" not in FORM_JS
