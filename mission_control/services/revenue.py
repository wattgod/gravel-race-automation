"""Revenue service — payment tracking + revenue calculations."""

from datetime import datetime, timezone

from mission_control import supabase_client as db


def record_payment(
    deal_id: str,
    amount: float,
    source: str = "manual",
    stripe_payment_id: str = "",
    description: str = "",
) -> dict:
    """Record a payment for a deal."""
    deal = db.select_one("gg_deals", match={"id": deal_id})
    if not deal:
        return {}

    payment = db.insert("gg_payments", {
        "deal_id": deal_id,
        "athlete_id": deal.get("athlete_id"),
        "amount": amount,
        "source": source,
        "stripe_payment_id": stripe_payment_id,
        "description": description,
    })

    db.log_action(
        "payment_recorded", "deal", deal_id,
        f"${amount} via {source}",
    )

    return payment


def monthly_revenue(year: int, month: int) -> float:
    """Sum of payments for a given month."""
    start = f"{year}-{month:02d}-01T00:00:00Z"
    if month == 12:
        end = f"{year + 1}-01-01T00:00:00Z"
    else:
        end = f"{year}-{month + 1:02d}-01T00:00:00Z"

    q = db._table("gg_payments").select("amount")
    q = q.gte("paid_at", start).lt("paid_at", end)
    result = q.execute()

    return sum(float(p["amount"]) for p in (result.data or []))


def revenue_vs_target(target: float = 10395.0) -> dict:
    """Current month actual revenue vs target."""
    now = datetime.now(timezone.utc)
    actual = monthly_revenue(now.year, now.month)
    return {
        "actual": actual,
        "target": target,
        "pct": round(actual / target * 100, 1) if target else 0,
        "remaining": max(0, target - actual),
        "month": now.strftime("%B %Y"),
    }


def monthly_trend(months: int = 6) -> list[dict]:
    """Revenue for the last N months."""
    now = datetime.now(timezone.utc)
    trend = []
    for i in range(months - 1, -1, -1):
        # Calculate month offset
        month = now.month - i
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        rev = monthly_revenue(year, month)
        trend.append({
            "month": f"{year}-{month:02d}",
            "label": datetime(year, month, 1).strftime("%b"),
            "revenue": rev,
        })
    return trend


def plans_sold_this_month() -> int:
    """Count deals closed_won this month."""
    now = datetime.now(timezone.utc)
    start = f"{now.year}-{now.month:02d}-01T00:00:00Z"
    q = db._table("gg_deals").select("id", count="exact")
    q = q.eq("stage", "closed_won").gte("closed_at", start)
    result = q.execute()
    return result.count or 0


def total_open_pipeline_value() -> float:
    """Total value of deals not yet closed."""
    q = db._table("gg_deals").select("value")
    q = q.not_.in_("stage", ["closed_won", "closed_lost"])
    result = q.execute()
    return sum(float(d["value"]) for d in (result.data or []))
