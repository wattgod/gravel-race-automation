"""
Create Stripe products, prices, and Payment Links for Gravel God courses.

Products:
  1. Gravel Hydration Mastery — $19 one-time
  2. Dirt Craft: Technical Gravel Mastery — $29 one-time
  3. Gravel Academy 2-Pack (both courses) — $39 one-time

Each product gets a Payment Link with metadata.course_id set so the
course-access Cloudflare Worker (workers/course-access/worker.js) can grant
enrollment from the checkout.session.completed webhook. The bundle uses a
comma-separated course_id list ("gravel-hydration-mastery,dirt-craft") —
the worker splits on commas and enrolls each course.

After creation, this script patches each course.json in data/courses/ with
the real stripe_payment_link and stripe_price_id, and saves a manifest to
data/stripe-course-products.json.

It also checks that a webhook endpoint pointing at the course-access worker
exists in Stripe; if missing, it prints setup instructions (it does NOT
auto-create one, because the new signing secret would need to be installed
in the worker via `wrangler secret put STRIPE_WEBHOOK_SECRET`).

Usage:
  export STRIPE_SECRET_KEY=sk_live_...
  python3 scripts/create_course_products.py --dry-run   # preview
  python3 scripts/create_course_products.py             # create + patch JSONs
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

REPO_ROOT = Path(__file__).resolve().parent.parent
COURSES_DIR = REPO_ROOT / "data" / "courses"
MANIFEST_PATH = REPO_ROOT / "data" / "stripe-course-products.json"
WORKER_WEBHOOK_URL = "https://course-access.gravelgodcoaching.workers.dev/webhook"
SITE_BASE_URL = "https://gravelgodcycling.com"

# =============================================================================
# COURSE PRODUCT DEFINITIONS
# =============================================================================
# price_usd is read from each course.json so the site and Stripe can't drift.

BUNDLE = {
    "id": "gravel-academy-2pack",
    "name": "Gravel Academy 2-Pack",
    "description": (
        "Gravel Hydration Mastery + Dirt Craft: Technical Gravel Mastery. "
        "20 interactive lessons, 6 calculators, 12 named technique tools, "
        "and the drills to build real skill. Lifetime access to both courses."
    ),
    "price_usd": 39,
    "course_ids": ["gravel-hydration-mastery", "dirt-craft"],
    # Bundle success redirect goes to the course index, not a single course
    "success_url": f"{SITE_BASE_URL}/course/?welcome=1",
}


def load_active_courses() -> list[dict]:
    courses = []
    for course_json in sorted(COURSES_DIR.glob("*/course.json")):
        with open(course_json) as f:
            course = json.load(f)
        if course.get("status") != "active":
            continue
        course["_path"] = course_json
        courses.append(course)
    return courses


def course_product_payload(course: dict) -> dict:
    lesson_count = sum(len(m["lessons"]) for m in course["modules"])
    return {
        "name": course["title"],
        "description": (course.get("description") or "")[:500]
        or f"{lesson_count}-lesson self-paced course from Gravel God Cycling.",
        "metadata": {"category": "course", "course_id": course["id"]},
    }


def dry_run(courses: list[dict]):
    print("=" * 60)
    print("DRY RUN — course products, prices, and payment links:")
    print("=" * 60)
    for i, course in enumerate(courses, 1):
        print(f"\n{i}. {course['title']} — ${course['price_usd']} (one-time)")
        print(f"   course_id metadata: {course['id']}")
        print(f"   success redirect:   {SITE_BASE_URL}/course/{course['id']}/?welcome=1")
        print(f"   will patch:         {course['_path']}")
    print(f"\n{len(courses) + 1}. {BUNDLE['name']} — ${BUNDLE['price_usd']} (one-time)")
    print(f"   course_id metadata: {','.join(BUNDLE['course_ids'])}")
    print(f"   success redirect:   {BUNDLE['success_url']}")
    print(f"\nTotal: {len(courses) + 1} products, {len(courses) + 1} prices, "
          f"{len(courses) + 1} payment links")
    print("\nAlso checks webhook endpoint:", WORKER_WEBHOOK_URL)


def create_payment_link(price_id: str, course_id_meta: str, success_url: str):
    return stripe.PaymentLink.create(
        line_items=[{"price": price_id, "quantity": 1}],
        metadata={"course_id": course_id_meta},
        allow_promotion_codes=True,
        after_completion={
            "type": "redirect",
            "redirect": {"url": success_url},
        },
    )


def check_webhook_endpoint():
    """Verify a webhook endpoint pointing at the course-access worker exists."""
    endpoints = stripe.WebhookEndpoint.list(limit=100)
    for ep in endpoints.auto_paging_iter():
        if ep.url == WORKER_WEBHOOK_URL:
            events = list(ep.enabled_events)
            ok = "checkout.session.completed" in events or "*" in events
            status = "OK" if (ep.status == "enabled" and ok) else "NEEDS ATTENTION"
            print(f"\nWebhook endpoint: {status}")
            print(f"  url:    {ep.url}")
            print(f"  status: {ep.status}, events: {events}")
            return True
    print("\nWARNING: No Stripe webhook endpoint points at the course-access worker.")
    print("Course purchases will NOT grant access until you create one:")
    print(f"  1. stripe.WebhookEndpoint.create(url='{WORKER_WEBHOOK_URL}',")
    print("       enabled_events=['checkout.session.completed'])")
    print("     (or via dashboard.stripe.com/webhooks)")
    print("  2. Copy the new signing secret, then:")
    print("     cd workers/course-access && npx wrangler secret put STRIPE_WEBHOOK_SECRET")
    return False


def patch_course_json(course: dict, payment_link_url: str, price_id: str):
    path = course["_path"]
    with open(path) as f:
        data = json.load(f)
    data["stripe_payment_link"] = payment_link_url
    data["stripe_price_id"] = price_id
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"  ✓ Patched {path.relative_to(REPO_ROOT)}")


def create_all(courses: list[dict]):
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        print("ERROR: STRIPE_SECRET_KEY not set")
        sys.exit(1)
    stripe.api_key = key

    manifest = {"products": [], "prices": [], "payment_links": []}

    for course in courses:
        print(f"\nCreating product: {course['title']}...")
        product = stripe.Product.create(**course_product_payload(course))
        print(f"  ✓ Product: {product.id}")

        price = stripe.Price.create(
            product=product.id,
            unit_amount=int(course["price_usd"]) * 100,
            currency="usd",
            nickname=f"{course['title']} — ${course['price_usd']}",
            metadata={"type": "course", "course_id": course["id"]},
        )
        stripe.Product.modify(product.id, default_price=price.id)
        print(f"  ✓ Price: {price.id} (${course['price_usd']})")

        link = create_payment_link(
            price.id,
            course["id"],
            f"{SITE_BASE_URL}/course/{course['id']}/?welcome=1",
        )
        print(f"  ✓ Payment link: {link.url}")

        manifest["products"].append({"id": product.id, "name": product.name})
        manifest["prices"].append({"id": price.id, "course_id": course["id"],
                                   "amount": int(course["price_usd"]) * 100})
        manifest["payment_links"].append({"id": link.id, "url": link.url,
                                          "course_id": course["id"]})
        patch_course_json(course, link.url, price.id)

    # --- Bundle ---
    print(f"\nCreating product: {BUNDLE['name']}...")
    b_product = stripe.Product.create(
        name=BUNDLE["name"],
        description=BUNDLE["description"],
        metadata={"category": "course_bundle",
                  "course_id": ",".join(BUNDLE["course_ids"])},
    )
    print(f"  ✓ Product: {b_product.id}")
    b_price = stripe.Price.create(
        product=b_product.id,
        unit_amount=BUNDLE["price_usd"] * 100,
        currency="usd",
        nickname=f"{BUNDLE['name']} — ${BUNDLE['price_usd']}",
        metadata={"type": "course_bundle"},
    )
    stripe.Product.modify(b_product.id, default_price=b_price.id)
    print(f"  ✓ Price: {b_price.id} (${BUNDLE['price_usd']})")
    b_link = create_payment_link(
        b_price.id, ",".join(BUNDLE["course_ids"]), BUNDLE["success_url"]
    )
    print(f"  ✓ Payment link: {b_link.url}")

    manifest["products"].append({"id": b_product.id, "name": b_product.name})
    manifest["prices"].append({"id": b_price.id, "course_id": "bundle",
                               "amount": BUNDLE["price_usd"] * 100})
    manifest["payment_links"].append({"id": b_link.id, "url": b_link.url,
                                      "course_id": ",".join(BUNDLE["course_ids"]),
                                      "bundle": True})

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    print(f"\nManifest saved: {MANIFEST_PATH.relative_to(REPO_ROOT)}")

    check_webhook_endpoint()

    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("  1. Re-deploy worker if bundle support was just added:")
    print("     cd workers/course-access && npx wrangler deploy")
    print("  2. Regenerate course pages: python3 wordpress/generate_courses.py")
    print("  3. Deploy + purge cache")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Create Stripe course products")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating")
    args = parser.parse_args()

    courses = load_active_courses()
    if not courses:
        print("ERROR: no active courses found in data/courses/")
        sys.exit(1)

    if args.dry_run:
        dry_run(courses)
    else:
        create_all(courses)


if __name__ == "__main__":
    main()
