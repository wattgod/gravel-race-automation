#!/usr/bin/env python3
"""
Sync tire reviews from Cloudflare KV to per-tire JSON files.

Pulls reviews from the tire-review-intake Worker's KV namespace
via Cloudflare REST API, strips PII (email), and appends to each
tire's community_reviews array.

Usage:
    python scripts/sync_tire_reviews.py              # sync all
    python scripts/sync_tire_reviews.py --dry-run     # preview
    python scripts/sync_tire_reviews.py --tire maxxis-rambler  # single tire
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install: pip install requests")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIRE_DIR = PROJECT_ROOT / "data" / "tires"

# Load .env if present (simple key=value, no quotes handling needed)
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
CF_KV_NAMESPACE_ID = os.environ.get("CF_KV_NAMESPACE_ID", "")

BASE_URL = "https://api.cloudflare.com/client/v4"


def cf_headers() -> dict:
    return {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json",
    }


def list_kv_keys(prefix: str = "") -> list:
    """List all keys in the KV namespace, handling pagination."""
    keys = []
    cursor = None
    while True:
        url = f"{BASE_URL}/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/keys"
        params = {"limit": 1000}
        if prefix:
            params["prefix"] = prefix
        if cursor:
            params["cursor"] = cursor

        resp = requests.get(url, headers=cf_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("success"):
            print(f"ERROR: KV list failed: {data.get('errors', [])}")
            break

        keys.extend(data.get("result", []))

        cursor = data.get("result_info", {}).get("cursor")
        if not cursor:
            break

    return keys


def get_kv_value(key: str) -> dict | None:
    """Fetch a single KV value by key."""
    url = f"{BASE_URL}/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{key}"
    resp = requests.get(url, headers=cf_headers())
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def strip_pii(review: dict) -> dict:
    """Remove email from review for storage in repo."""
    clean = {k: v for k, v in review.items() if k != "email"}
    # Ensure approved flag
    clean["approved"] = True
    return clean


def sync(tire_filter: str | None = None, dry_run: bool = False) -> None:
    if not CF_ACCOUNT_ID or not CF_API_TOKEN or not CF_KV_NAMESPACE_ID:
        print("ERROR: Missing environment variables. Set CF_ACCOUNT_ID, CF_API_TOKEN, CF_KV_NAMESPACE_ID")
        print("  Either in .env or as environment variables.")
        sys.exit(1)

    # List all KV keys (optionally filtered by tire prefix)
    prefix = f"{tire_filter}:" if tire_filter else ""
    print(f"Listing KV keys{f' with prefix: {prefix}' if prefix else ''}...")
    kv_keys = list_kv_keys(prefix)
    print(f"Found {len(kv_keys)} review(s) in KV")

    if not kv_keys:
        print("No reviews to sync.")
        return

    # Group keys by tire_id (key format: {tire_id}:{review_id})
    tire_reviews: dict[str, list] = {}
    for key_entry in kv_keys:
        key_name = key_entry["name"]
        parts = key_name.split(":", 1)
        if len(parts) != 2:
            print(f"  WARNING: Skipping malformed key: {key_name}")
            continue
        tire_id = parts[0]
        if tire_id not in tire_reviews:
            tire_reviews[tire_id] = []
        tire_reviews[tire_id].append(key_name)

    print(f"Reviews span {len(tire_reviews)} tire(s)")

    # Process each tire
    synced = 0
    skipped = 0
    for tire_id, keys in sorted(tire_reviews.items()):
        tire_path = TIRE_DIR / f"{tire_id}.json"
        if not tire_path.exists():
            print(f"  WARNING: No tire JSON for '{tire_id}' — skipping {len(keys)} review(s)")
            skipped += len(keys)
            continue

        # Load existing tire data
        tire_data = json.loads(tire_path.read_text(encoding="utf-8"))
        existing_ids = {
            r["review_id"] for r in tire_data.get("community_reviews", [])
        }

        new_reviews = []
        for key_name in keys:
            review_id = key_name.split(":", 1)[1]
            if review_id in existing_ids:
                continue

            # Fetch full review from KV
            review = get_kv_value(key_name)
            if not review:
                print(f"  WARNING: Could not fetch {key_name}")
                continue

            clean = strip_pii(review)
            new_reviews.append(clean)

        if not new_reviews:
            continue

        if dry_run:
            print(f"  [dry-run] {tire_id}: would add {len(new_reviews)} review(s)")
            synced += len(new_reviews)
            continue

        # Append and write
        if "community_reviews" not in tire_data:
            tire_data["community_reviews"] = []
        tire_data["community_reviews"].extend(new_reviews)

        with open(tire_path, "w", encoding="utf-8") as f:
            json.dump(tire_data, f, indent=2, ensure_ascii=False)
            f.write("\n")

        synced += len(new_reviews)
        print(f"  {tire_id}: +{len(new_reviews)} review(s) (total: {len(tire_data['community_reviews'])})")

    print(f"\nDone. Synced {synced} new review(s), skipped {skipped}.")
    if dry_run:
        print("  (dry-run — no files written)")


def main():
    parser = argparse.ArgumentParser(description="Sync tire reviews from Cloudflare KV")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--tire", default=None, help="Sync a single tire by ID (e.g. maxxis-rambler)")
    args = parser.parse_args()
    sync(tire_filter=args.tire, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
