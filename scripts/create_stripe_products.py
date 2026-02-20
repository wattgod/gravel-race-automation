"""
Create Stripe products and prices for Gravel God Cycling.

Products:
  1. Custom Training Plan — 14 one-time prices ($60–$249, $15/week increments)
  2. Coaching Min — $199/month subscription
  3. Coaching Mid — $299/month subscription
  4. Coaching Max — $1,200/month subscription
  5. Coaching Setup Fee — $99 one-time (added to all coaching checkouts)
  6. Consulting — $150/hour one-time

Also creates:
  - "Waive Setup Fee" coupon ($99 off, applies to setup fee product only)
  - "NOSETUP" promotion code (customers enter at checkout to waive fee)

Usage:
  export STRIPE_SECRET_KEY=sk_live_...
  python scripts/create_stripe_products.py --dry-run   # preview what will be created
  python scripts/create_stripe_products.py              # create in Stripe
"""
from __future__ import annotations

import argparse
import json
import os
import sys

try:
    import stripe
except ImportError:
    print("ERROR: stripe package not installed. Run: pip install stripe")
    sys.exit(1)


# =============================================================================
# PRODUCT DEFINITIONS
# =============================================================================

TRAINING_PLAN_PRODUCT = {
    "name": "Custom Training Plan",
    "description": "Race-specific training plan built for your A-race. Includes structured workouts, 30+ page guide, heat/altitude protocols, nutrition plan, and strength training.",
    "metadata": {"category": "training_plan"},
}

# $15/week, min 4 weeks ($60), cap $249
# 4 weeks = $60, 5 = $75, ..., 16 = $240, 17+ = $249
TRAINING_PLAN_PRICES = []
for weeks in range(4, 17):  # 4–16 weeks
    amount = weeks * 15
    TRAINING_PLAN_PRICES.append({
        "unit_amount": amount * 100,  # cents
        "currency": "usd",
        "nickname": f"{weeks}-week plan (${amount})",
        "metadata": {"weeks": str(weeks), "type": "training_plan"},
    })
# Cap price: $249 for 17+ weeks
TRAINING_PLAN_PRICES.append({
    "unit_amount": 249 * 100,
    "currency": "usd",
    "nickname": "17+ week plan ($249 cap)",
    "metadata": {"weeks": "17+", "type": "training_plan"},
})


COACHING_PRODUCTS = [
    {
        "product": {
            "name": "Coaching — Min",
            "description": "Weekly training review, light file analysis, quarterly strategy calls, structured .zwo workouts, race-optimized nutrition plan, custom training guide.",
            "metadata": {"category": "coaching", "tier": "min"},
        },
        "price": {
            "unit_amount": 199 * 100,
            "currency": "usd",
            "recurring": {"interval": "week", "interval_count": 4},
            "nickname": "Coaching Min — $199/4wk",
            "metadata": {"tier": "min", "type": "coaching"},
        },
    },
    {
        "product": {
            "name": "Coaching — Mid",
            "description": "Everything in Min, plus thorough file analysis (WKO), monthly strategy calls, weekly plan adjustments, direct message access, blindspot detection.",
            "metadata": {"category": "coaching", "tier": "mid"},
        },
        "price": {
            "unit_amount": 299 * 100,
            "currency": "usd",
            "recurring": {"interval": "week", "interval_count": 4},
            "nickname": "Coaching Mid — $299/4wk",
            "metadata": {"tier": "mid", "type": "coaching"},
        },
    },
    {
        "product": {
            "name": "Coaching — Max",
            "description": "Everything in Mid, plus daily file review, on-demand calls, race-week strategy, multi-race season planning, priority response.",
            "metadata": {"category": "coaching", "tier": "max"},
        },
        "price": {
            "unit_amount": 1200 * 100,
            "currency": "usd",
            "recurring": {"interval": "week", "interval_count": 4},
            "nickname": "Coaching Max — $1,200/4wk",
            "metadata": {"tier": "max", "type": "coaching"},
        },
    },
]

COACHING_SETUP_FEE_PRODUCT = {
    "product": {
        "name": "Coaching Setup Fee",
        "description": "One-time onboarding fee for coaching subscription. Covers intake analysis, training history review, and initial plan setup.",
        "metadata": {"category": "coaching", "type": "setup_fee"},
    },
    "price": {
        "unit_amount": 99 * 100,
        "currency": "usd",
        "nickname": "Coaching Setup Fee — $99",
        "metadata": {"type": "coaching_setup_fee"},
    },
}

CONSULTING_PRODUCT = {
    "product": {
        "name": "Consulting",
        "description": "One-on-one consulting session. Race strategy, training methodology review, performance analysis, or custom coaching consultation.",
        "metadata": {"category": "consulting"},
    },
    "price": {
        "unit_amount": 150 * 100,
        "currency": "usd",
        "nickname": "Consulting — $150/hr",
        "metadata": {"type": "consulting", "unit": "hour"},
    },
}


def dry_run():
    """Print what would be created without making API calls."""
    print("=" * 60)
    print("DRY RUN — Products and prices that will be created:")
    print("=" * 60)

    print(f"\n1. {TRAINING_PLAN_PRODUCT['name']}")
    print(f"   {TRAINING_PLAN_PRODUCT['description'][:80]}...")
    print(f"   Prices ({len(TRAINING_PLAN_PRICES)}):")
    for p in TRAINING_PLAN_PRICES:
        print(f"     - {p['nickname']}: ${p['unit_amount'] / 100:.0f} (one-time)")

    print()
    for i, c in enumerate(COACHING_PRODUCTS, 2):
        print(f"{i}. {c['product']['name']}")
        print(f"   {c['product']['description'][:80]}...")
        p = c["price"]
        print(f"   Price: ${p['unit_amount'] / 100:.0f}/{p['recurring']['interval']}")

    n = len(COACHING_PRODUCTS) + 2
    print(f"\n{n}. {COACHING_SETUP_FEE_PRODUCT['product']['name']}")
    print(f"   {COACHING_SETUP_FEE_PRODUCT['product']['description'][:80]}...")
    p = COACHING_SETUP_FEE_PRODUCT["price"]
    print(f"   Price: ${p['unit_amount'] / 100:.0f} (one-time, added to all coaching checkouts)")

    n += 1
    print(f"\n{n}. {CONSULTING_PRODUCT['product']['name']}")
    print(f"   {CONSULTING_PRODUCT['product']['description'][:80]}...")
    p = CONSULTING_PRODUCT["price"]
    print(f"   Price: ${p['unit_amount'] / 100:.0f}/session (one-time)")

    print(f"\n   + Coupon: \"Waive Setup Fee\" ($99 off setup fee product)")
    print(f"   + Promo code: NOSETUP")

    total_products = 1 + len(COACHING_PRODUCTS) + 1 + 1  # training + coaching tiers + setup fee + consulting
    total_prices = len(TRAINING_PLAN_PRICES) + len(COACHING_PRODUCTS) + 1 + 1
    print(f"\nTotal: {total_products} products, {total_prices} prices, 1 coupon, 1 promo code")


def create_products():
    """Create all products and prices in Stripe."""
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        print("ERROR: STRIPE_SECRET_KEY not set")
        sys.exit(1)

    stripe.api_key = key
    created = {"products": [], "prices": []}

    # --- Training Plan product + 14 prices ---
    print(f"Creating product: {TRAINING_PLAN_PRODUCT['name']}...")
    tp_product = stripe.Product.create(**TRAINING_PLAN_PRODUCT)
    created["products"].append({"id": tp_product.id, "name": tp_product.name})
    print(f"  ✓ Product created: {tp_product.id}")

    for price_data in TRAINING_PLAN_PRICES:
        p = stripe.Price.create(product=tp_product.id, **price_data)
        created["prices"].append({
            "id": p.id,
            "product": tp_product.id,
            "nickname": price_data["nickname"],
            "amount": price_data["unit_amount"],
        })
        print(f"  ✓ Price: {price_data['nickname']} → {p.id}")

    # --- Coaching products (1 product + 1 price each) ---
    for coaching in COACHING_PRODUCTS:
        print(f"\nCreating product: {coaching['product']['name']}...")
        product = stripe.Product.create(**coaching["product"])
        created["products"].append({"id": product.id, "name": product.name})
        print(f"  ✓ Product created: {product.id}")

        p = stripe.Price.create(product=product.id, **coaching["price"])
        created["prices"].append({
            "id": p.id,
            "product": product.id,
            "nickname": coaching["price"]["nickname"],
            "amount": coaching["price"]["unit_amount"],
        })
        print(f"  ✓ Price: {coaching['price']['nickname']} → {p.id}")

        # Set as default price
        stripe.Product.modify(product.id, default_price=p.id)
        print(f"  ✓ Set as default price")

    # --- Coaching Setup Fee product + price ---
    print(f"\nCreating product: {COACHING_SETUP_FEE_PRODUCT['product']['name']}...")
    sf_product = stripe.Product.create(**COACHING_SETUP_FEE_PRODUCT["product"])
    created["products"].append({"id": sf_product.id, "name": sf_product.name})
    print(f"  ✓ Product created: {sf_product.id}")

    p = stripe.Price.create(product=sf_product.id, **COACHING_SETUP_FEE_PRODUCT["price"])
    created["prices"].append({
        "id": p.id,
        "product": sf_product.id,
        "nickname": COACHING_SETUP_FEE_PRODUCT["price"]["nickname"],
        "amount": COACHING_SETUP_FEE_PRODUCT["price"]["unit_amount"],
    })
    print(f"  ✓ Price: {COACHING_SETUP_FEE_PRODUCT['price']['nickname']} → {p.id}")

    stripe.Product.modify(sf_product.id, default_price=p.id)
    print(f"  ✓ Set as default price")

    # --- Coupon + Promo Code for waiving setup fee ---
    print(f"\nCreating coupon: Waive Setup Fee...")
    coupon = stripe.Coupon.create(
        amount_off=9900,
        currency="usd",
        name="Waive Setup Fee",
        duration="once",
        metadata={"type": "setup_fee_waiver"},
        applies_to={"products": [sf_product.id]},
    )
    created["coupons"] = [{"id": coupon.id, "name": coupon.name}]
    print(f"  ✓ Coupon created: {coupon.id}")

    promo = stripe.PromotionCode.create(
        coupon=coupon.id,
        code="NOSETUP",
        metadata={"type": "setup_fee_waiver"},
    )
    created["promotion_codes"] = [{"id": promo.id, "code": promo.code}]
    print(f"  ✓ Promo code: NOSETUP → {promo.id}")

    # --- Consulting product + price ---
    print(f"\nCreating product: {CONSULTING_PRODUCT['product']['name']}...")
    con_product = stripe.Product.create(**CONSULTING_PRODUCT["product"])
    created["products"].append({"id": con_product.id, "name": con_product.name})
    print(f"  ✓ Product created: {con_product.id}")

    p = stripe.Price.create(product=con_product.id, **CONSULTING_PRODUCT["price"])
    created["prices"].append({
        "id": p.id,
        "product": con_product.id,
        "nickname": CONSULTING_PRODUCT["price"]["nickname"],
        "amount": CONSULTING_PRODUCT["price"]["unit_amount"],
    })
    print(f"  ✓ Price: {CONSULTING_PRODUCT['price']['nickname']} → {p.id}")

    stripe.Product.modify(con_product.id, default_price=p.id)
    print(f"  ✓ Set as default price")

    # --- Summary ---
    print("\n" + "=" * 60)
    print(f"DONE: {len(created['products'])} products, {len(created['prices'])} prices, "
          f"{len(created.get('coupons', []))} coupons, "
          f"{len(created.get('promotion_codes', []))} promo codes created")
    print("=" * 60)

    # Save manifest for reference
    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data", "stripe-products.json"
    )
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(created, f, indent=2)
    print(f"\nManifest saved: {manifest_path}")

    return created


def main():
    parser = argparse.ArgumentParser(description="Create Stripe products for Gravel God")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating")
    args = parser.parse_args()

    if args.dry_run:
        dry_run()
    else:
        create_products()


if __name__ == "__main__":
    main()
