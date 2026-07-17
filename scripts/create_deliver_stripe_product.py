#!/usr/bin/env python3
"""
Create Stripe product, price, and payment link for the Deliver course.

Creates on the Gravel God Stripe account (gravelgodcycling.com):
  - Product: "Deliver: Unlock Your Brain"
  - Price: $79 one-time
  - Payment Link: auto-generated, ready to embed

After creation, updates data/courses/deliver/course.json with the
stripe_price_id and stripe_payment_link.

Usage:
  export STRIPE_SECRET_KEY=sk_live_...   # Gravel God account key
  python scripts/create_deliver_stripe_product.py --dry-run
  python scripts/create_deliver_stripe_product.py
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
COURSE_JSON_PATH = PROJECT_ROOT / "data" / "courses" / "deliver" / "course.json"

DELIVER_PRODUCT = {
    "name": "Deliver: Unlock Your Brain",
    "description": (
        "A 6-module sport psychology course for endurance athletes. "
        "38 lessons covering mental performance, identity, visualization, "
        "flow states, race-day protocols, and resilience. "
        "Includes guided audio exercises and downloadable tools."
    ),
    "metadata": {
        "category": "course",
        "course_id": "deliver",
    },
}

DELIVER_PRICE = {
    "unit_amount": 79 * 100,  # $79.00 in cents
    "currency": "usd",
    "nickname": "Deliver — $79 one-time",
    "metadata": {
        "type": "course",
        "course_id": "deliver",
    },
}

# Payment link settings
PAYMENT_LINK_SETTINGS = {
    "after_completion": {
        "type": "redirect",
        # Redirect to course after successful purchase.
        # The Worker will have already enrolled them via webhook by this point.
        "redirect": {
            "url": "https://gravelgodcycling.com/course/deliver/?enrolled=1",
        },
    },
    "metadata": {
        "course_id": "deliver",
    },
}


def dry_run():
    """Print what would be created without making API calls."""
    print("=" * 60)
    print("DRY RUN — Deliver course Stripe product")
    print("=" * 60)
    print(f"\nProduct: {DELIVER_PRODUCT['name']}")
    print(f"  {DELIVER_PRODUCT['description'][:100]}...")
    print(f"  metadata: {DELIVER_PRODUCT['metadata']}")
    print(f"\nPrice: ${DELIVER_PRICE['unit_amount'] / 100:.0f} (one-time)")
    print(f"  nickname: {DELIVER_PRICE['nickname']}")
    print(f"\nPayment Link:")
    print(f"  after_completion: redirect to {PAYMENT_LINK_SETTINGS['after_completion']['redirect']['url']}")
    print(f"\nWill update: {COURSE_JSON_PATH}")
    print(f"  stripe_price_id → <price_id>")
    print(f"  stripe_payment_link → <payment_link_url>")


def _get_stripe_key(key_file: str | None = None) -> str:
    """Get Stripe key from file, env, keychain, or prompt (no shell history)."""
    import subprocess
    # 0. Key file (most secure for non-interactive use)
    if key_file:
        path = Path(key_file).expanduser()
        if not path.exists():
            print(f"ERROR: Key file not found: {path}")
            sys.exit(1)
        key = path.read_text().strip()
        if key:
            return key
    # 1. Environment variable
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if key:
        return key
    # 2. macOS Keychain
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "stripe-gg", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    # 3. Secure prompt (getpass — no echo, no history)
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
    # Offer to save to keychain for next time
    save = input("Save to macOS Keychain as 'stripe-gg'? [y/N] ")
    if save.lower() == "y":
        subprocess.run([
            "security", "add-generic-password",
            "-s", "stripe-gg", "-a", "gravel-god", "-w", key.strip(),
        ])
        print("  Saved to Keychain.")
    return key.strip()


def create_product(*, yes: bool = False, key_file: str | None = None):
    """Create Deliver product, price, and payment link in Stripe."""
    key = _get_stripe_key(key_file=key_file)

    stripe.api_key = key

    # Verify we're on the right Stripe account
    account = stripe.Account.retrieve()
    acct_name = account.get("business_profile", {}).get("name", account.id)
    print(f"Stripe account: {acct_name}")
    print(f"Account ID: {account.id}")
    if not yes:
        confirm = input("\nIs this the Gravel God Stripe account? [y/N] ")
        if confirm.lower() != "y":
            print("Aborting. Set STRIPE_SECRET_KEY to the Gravel God account key.")
            sys.exit(1)
    else:
        print("  (--yes flag: skipping confirmation)")

    # Check for existing Deliver product (idempotency guard)
    existing = stripe.Product.search(query="metadata['course_id']:'deliver'")
    if existing.data:
        print(f"\nWARNING: A product with course_id=deliver already exists:")
        for p in existing.data:
            print(f"  {p.id}: {p.name}")
        if not yes:
            confirm = input("Create another one anyway? [y/N] ")
            if confirm.lower() != "y":
                print("Aborting.")
                sys.exit(0)
        else:
            print("  (--yes flag: skipping, product already exists)")
            # Return existing info instead of creating duplicate
            existing_price = stripe.Price.list(product=existing.data[0].id, limit=1)
            if existing_price.data:
                print(f"  Using existing price: {existing_price.data[0].id}")
                return {
                    "product_id": existing.data[0].id,
                    "price_id": existing_price.data[0].id,
                    "skipped": True,
                }
            print("  No price found on existing product — creating fresh.")

    # Create product
    print(f"\nCreating product: {DELIVER_PRODUCT['name']}...")
    product = stripe.Product.create(**DELIVER_PRODUCT)
    print(f"  Product created: {product.id}")

    # Create price
    print(f"Creating price: ${DELIVER_PRICE['unit_amount'] / 100:.0f}...")
    price = stripe.Price.create(product=product.id, **DELIVER_PRICE)
    print(f"  Price created: {price.id}")

    # Set as default price
    stripe.Product.modify(product.id, default_price=price.id)
    print(f"  Set as default price")

    # Create payment link
    print("Creating payment link...")
    payment_link = stripe.PaymentLink.create(
        line_items=[{"price": price.id, "quantity": 1}],
        **PAYMENT_LINK_SETTINGS,
    )
    print(f"  Payment link: {payment_link.url}")

    # Update course.json
    if COURSE_JSON_PATH.exists():
        course = json.loads(COURSE_JSON_PATH.read_text(encoding="utf-8"))
        course["stripe_price_id"] = price.id
        course["stripe_payment_link"] = payment_link.url
        COURSE_JSON_PATH.write_text(
            json.dumps(course, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nUpdated {COURSE_JSON_PATH}")
        print(f"  stripe_price_id: {price.id}")
        print(f"  stripe_payment_link: {payment_link.url}")
    else:
        print(f"\nWARNING: {COURSE_JSON_PATH} not found — update manually:")
        print(f"  stripe_price_id: {price.id}")
        print(f"  stripe_payment_link: {payment_link.url}")

    # Save to manifest
    manifest = {
        "product_id": product.id,
        "product_name": product.name,
        "price_id": price.id,
        "price_amount": DELIVER_PRICE["unit_amount"],
        "payment_link_id": payment_link.id,
        "payment_link_url": payment_link.url,
    }
    manifest_path = COURSE_JSON_PATH.parent / "stripe-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Manifest saved: {manifest_path}")

    print("\n" + "=" * 60)
    print("DONE. Next steps:")
    print("  1. Add Stripe webhook for payment_intent.succeeded")
    print("     pointing to the course-access Worker")
    print("  2. Run generate_courses.py to rebuild with payment link")
    print("=" * 60)

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Create Stripe product for Deliver course"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without creating")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip interactive confirmations")
    parser.add_argument("--key-file", type=str, default=None,
                        help="Path to file containing Stripe secret key")
    args = parser.parse_args()

    if args.dry_run:
        dry_run()
    else:
        create_product(yes=args.yes, key_file=args.key_file)


if __name__ == "__main__":
    main()
