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
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

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

# Fix #10: Whitelist — only these fields survive into the repo JSON
REVIEW_FIELDS = {
    "review_id", "stars", "width_ridden", "pressure_psi",
    "conditions", "race_used_at", "would_recommend",
    "review_text", "submitted_at",
}


def cf_headers() -> dict:
    return {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json",
    }


def list_kv_keys(prefix: str = "") -> list:
    """List all keys in the KV namespace, handling pagination.

    Skips dedup keys (prefixed with 'dedup:') — those are internal.
    """
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

        for key_entry in data.get("result", []):
            # Skip dedup keys — they're internal to the worker
            if key_entry["name"].startswith("dedup:"):
                continue
            keys.append(key_entry)

        cursor = data.get("result_info", {}).get("cursor")
        if not cursor:
            break

    return keys


# Fix #7: Bulk fetch KV values (up to 100 per request)
def get_kv_values_bulk(keys: list[str]) -> dict[str, dict | None]:
    """Fetch multiple KV values via individual requests with URL encoding.

    Cloudflare KV REST API doesn't have a true bulk GET for values,
    but we URL-encode keys properly and handle errors per-key.
    Returns: {key: value_dict_or_None}
    """
    results = {}
    for key in keys:
        # Fix #8: URL-encode the key for safe inclusion in the URL path
        encoded_key = quote(key, safe="")
        url = f"{BASE_URL}/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{encoded_key}"
        try:
            resp = requests.get(url, headers=cf_headers())
            if resp.status_code == 404:
                results[key] = None
                continue
            resp.raise_for_status()
            results[key] = resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"  WARNING: Failed to fetch '{key}': {e}")
            results[key] = None
    return results


# Fix #9: Validate review data pulled from KV
def validate_review(review: dict) -> str | None:
    """Validate a review dict from KV. Returns error string or None if valid."""
    if not isinstance(review, dict):
        return "not a dict"
    if not review.get("review_id"):
        return "missing review_id"
    stars = review.get("stars")
    if not isinstance(stars, int) or stars < 1 or stars > 5:
        return f"invalid stars: {stars}"
    if not review.get("submitted_at"):
        return "missing submitted_at"
    # Validate optional fields have correct types if present
    if review.get("width_ridden") is not None and not isinstance(review["width_ridden"], (int, float)):
        return f"invalid width_ridden type: {type(review['width_ridden'])}"
    if review.get("pressure_psi") is not None and not isinstance(review["pressure_psi"], (int, float)):
        return f"invalid pressure_psi type: {type(review['pressure_psi'])}"
    if review.get("conditions") is not None and not isinstance(review["conditions"], list):
        return f"invalid conditions type: {type(review['conditions'])}"
    return None


def sanitize_review(review: dict) -> dict:
    """Fix #10: Whitelist fields + strip PII. Only known fields survive into repo."""
    clean = {}
    for field in REVIEW_FIELDS:
        if field in review:
            clean[field] = review[field]
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
    rejected = 0
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

        # Filter to only new review keys
        new_keys = []
        for key_name in keys:
            review_id = key_name.split(":", 1)[1]
            if review_id not in existing_ids:
                new_keys.append(key_name)

        if not new_keys:
            continue

        if dry_run:
            print(f"  [dry-run] {tire_id}: would add {len(new_keys)} review(s)")
            synced += len(new_keys)
            continue

        # Fetch all new reviews
        fetched = get_kv_values_bulk(new_keys)

        new_reviews = []
        for key_name, review in fetched.items():
            if not review:
                print(f"  WARNING: Could not fetch {key_name}")
                skipped += 1
                continue

            # Fix #9: Validate before accepting
            error = validate_review(review)
            if error:
                print(f"  REJECTED: {key_name} — {error}")
                rejected += 1
                continue

            clean = sanitize_review(review)
            new_reviews.append(clean)

        if not new_reviews:
            continue

        # Fix #11: Sort new reviews by submitted_at before appending
        new_reviews.sort(key=lambda r: r.get("submitted_at", ""))

        # Append and write
        if "community_reviews" not in tire_data:
            tire_data["community_reviews"] = []
        tire_data["community_reviews"].extend(new_reviews)

        with open(tire_path, "w", encoding="utf-8") as f:
            json.dump(tire_data, f, indent=2, ensure_ascii=False)
            f.write("\n")

        synced += len(new_reviews)
        print(f"  {tire_id}: +{len(new_reviews)} review(s) (total: {len(tire_data['community_reviews'])})")

    print(f"\nDone. Synced {synced} new review(s), skipped {skipped}, rejected {rejected}.")
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
