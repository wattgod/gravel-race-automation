#!/usr/bin/env python3
"""
Create Stripe product, price, and payment link for the Dirt Craft course.

Creates on the Gravel God Stripe account (gravelgodcycling.com):
  - Product: "Dirt Craft: Technical Gravel Mastery"
  - Price: $49 one-time
  - Payment Link: auto-generated, ready to embed

After creation, updates data/courses/dirt-craft/course.json with the
stripe_price_id and stripe_payment_link.

Usage:
  export STRIPE_SECRET_KEY=sk_live_...   # Gravel God account key (NOT the Endure Labs SaaS key)
  python scripts/create_dirt_craft_stripe_product.py --dry-run
  python scripts/create_dirt_craft_stripe_product.py

The script resolves the key from --key-file, then $STRIPE_SECRET_KEY, then the
macOS Keychain entry 'stripe-gg', then a no-echo prompt — so the live secret
never lands in shell history. It confirms the account name before creating, and
is idempotent (won't duplicate an existing dirt-craft product).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import stripe
except ImportError:
    print("ERROR: stripe package not installed. Run: pip install stripe")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSE_JSON_PATH = PROJECT_ROOT / "data" / "courses" / "dirt-craft" / "course.json"

DIRT_CRAFT_PRODUCT = {
    "name": "Dirt Craft: Technical Gravel Mastery",
    "description": (
        "A 7-module technical gravel skills course. 21 lessons of deliberate-practice "
        "drills, sensation targets, and honest physics — from fear to flow. Covers body "
        "position, braking, cornering, climbing, descending, pumping, hops, limit-finding, "
        "and the mental game, with embedded technique videos."
    ),
    "metadata": {
        "category": "course",
        "course_id": "dirt-craft",
    },
}

DIRT_CRAFT_PRICE = {
    "unit_amount": 49 * 100,  # $49.00 in cents
    "currency": "usd",
    "nickname": "Dirt Craft — $49 one-time",
    "metadata": {
        "type": "course",
        "course_id": "dirt-craft",
    },
}

PAYMENT_LINK_SETTINGS = {
    "after_completion": {
        "type": "redirect",
        "redirect": {
            # Worker enrolls the buyer via webhook before this redirect fires.
            "url": "https://gravelgodcycling.com/course/dirt-craft/?enrolled=1",
        },
    },
    "metadata": {
        "course_id": "dirt-craft",
    },
}


def dry_run():
    print("=" * 60)
    print("DRY RUN — Dirt Craft course Stripe product")
    print("=" * 60)
    print(f"\nProduct: {DIRT_CRAFT_PRODUCT['name']}")
    print(f"  {DIRT_CRAFT_PRODUCT['description'][:100]}...")
    print(f"  metadata: {DIRT_CRAFT_PRODUCT['metadata']}")
    print(f"\nPrice: ${DIRT_CRAFT_PRICE['unit_amount'] / 100:.0f} (one-time)")
    print(f"  nickname: {DIRT_CRAFT_PRICE['nickname']}")
    print(f"\nPayment Link:")
    print(f"  after_completion: redirect to {PAYMENT_LINK_SETTINGS['after_completion']['redirect']['url']}")
    print(f"\nWill update: {COURSE_JSON_PATH}")
    print(f"  stripe_price_id → <price_id>")
    print(f"  stripe_payment_link → <payment_link_url>")
    print(f"\nRe-run without --dry-run (with the Gravel God STRIPE_SECRET_KEY) to create.")


def _get_stripe_key(key_file: str | None = None) -> str:
    """Get Stripe key from file, env, keychain, or prompt (no shell history)."""
    import subprocess
    if key_file:
        path = Path(key_file).expanduser()
        if not path.exists():
            print(f"ERROR: Key file not found: {path}")
            sys.exit(1)
        key = path.read_text().strip()
        if key:
            return key
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if key:
        return key
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "stripe-gg", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    import getpass
    try:
        key = getpass.getpass("Stripe secret key (Gravel God account): ")
    except EOFError:
        print("ERROR: No TTY available and no key provided.")
        print("  Use --key-file /path/to/key.txt or save to Keychain:")
        print("  security add-generic-password -s stripe-gg -a gravel-god -w sk_live_...")
        sys.exit(1)
    if not key.strip():
        print("ERROR: No key provided.")
        sys.exit(1)
    save = input("Save to macOS Keychain as 'stripe-gg'? [y/N] ")
    if save.lower() == "y":
        subprocess.run([
            "security", "add-generic-password",
            "-s", "stripe-gg", "-a", "gravel-god", "-w", key.strip(),
        ])
        print("  Saved to Keychain.")
    return key.strip()


def create_product(*, yes: bool = False, key_file: str | None = None):
    key = _get_stripe_key(key_file=key_file)
    stripe.api_key = key

    if not key.startswith("sk_live_"):
        print(f"WARNING: key is {key[:8]}… — this is NOT a live key. A product created")
        print("  here will be in TEST mode and cannot take real payments.")
        if not yes:
            if input("Continue in test mode? [y/N] ").lower() != "y":
                print("Aborting. Export the live Gravel God STRIPE_SECRET_KEY (sk_live_...).")
                sys.exit(1)

    account = stripe.Account.retrieve()
    acct_name = account.get("business_profile", {}).get("name", account.id)
    print(f"Stripe account: {acct_name}")
    print(f"Account ID: {account.id}")
    if not yes:
        confirm = input("\nIs this the Gravel God Stripe account (gravelgodcycling.com)? [y/N] ")
        if confirm.lower() != "y":
            print("Aborting. Set STRIPE_SECRET_KEY to the Gravel God account key.")
            sys.exit(1)
    else:
        print("  (--yes flag: skipping confirmation)")

    existing = stripe.Product.search(query="metadata['course_id']:'dirt-craft'")
    if existing.data:
        print("\nWARNING: A product with course_id=dirt-craft already exists:")
        for p in existing.data:
            print(f"  {p.id}: {p.name}")
        existing_price = stripe.Price.list(product=existing.data[0].id, limit=1)
        if existing_price.data:
            print(f"  Using existing price: {existing_price.data[0].id}")
            _write_course_json(existing_price.data[0].id, None)
            return {"product_id": existing.data[0].id,
                    "price_id": existing_price.data[0].id, "skipped": True}
        if not yes and input("Create a price on it? [y/N] ").lower() != "y":
            print("Aborting.")
            sys.exit(0)
        product_id = existing.data[0].id
    else:
        print(f"\nCreating product: {DIRT_CRAFT_PRODUCT['name']}...")
        product = stripe.Product.create(**DIRT_CRAFT_PRODUCT)
        print(f"  Product created: {product.id}")
        product_id = product.id

    print(f"Creating price: ${DIRT_CRAFT_PRICE['unit_amount'] / 100:.0f}...")
    price = stripe.Price.create(product=product_id, **DIRT_CRAFT_PRICE)
    print(f"  Price created: {price.id}")

    stripe.Product.modify(product_id, default_price=price.id)
    print("  Set as default price")

    print("Creating payment link...")
    payment_link = stripe.PaymentLink.create(
        line_items=[{"price": price.id, "quantity": 1}],
        **PAYMENT_LINK_SETTINGS,
    )
    print(f"  Payment link: {payment_link.url}")

    _write_course_json(price.id, payment_link.url)
    print("\nDone. Next: flip course.json status to \"active\", regenerate, and deploy:")
    print("  python3 wordpress/generate_courses.py --course dirt-craft")
    print("  python3 scripts/push_wordpress.py --sync-courses")
    return {"product_id": product_id, "price_id": price.id,
            "payment_link": payment_link.url}


def _write_course_json(price_id: str, payment_link: str | None):
    if not COURSE_JSON_PATH.exists():
        print(f"\nWARNING: {COURSE_JSON_PATH} not found — update manually:")
        print(f"  stripe_price_id: {price_id}")
        if payment_link:
            print(f"  stripe_payment_link: {payment_link}")
        return
    course = json.loads(COURSE_JSON_PATH.read_text(encoding="utf-8"))
    course["stripe_price_id"] = price_id
    if payment_link:
        course["stripe_payment_link"] = payment_link
    COURSE_JSON_PATH.write_text(
        json.dumps(course, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nUpdated {COURSE_JSON_PATH}")
    print(f"  stripe_price_id: {price_id}")
    if payment_link:
        print(f"  stripe_payment_link: {payment_link}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true", help="skip confirmation prompts")
    ap.add_argument("--key-file", help="path to a file containing the Stripe secret key")
    args = ap.parse_args()
    if args.dry_run:
        dry_run()
    else:
        create_product(yes=args.yes, key_file=args.key_file)


if __name__ == "__main__":
    main()
