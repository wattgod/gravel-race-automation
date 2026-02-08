#!/usr/bin/env python3
"""
Push landing page JSON or race index to WordPress.
"""

import argparse
import json
import os
import requests
from pathlib import Path


def get_wp_credentials():
    """Return (wp_url, wp_user, wp_password) or exit with warning."""
    wp_url = os.environ.get("WP_URL")
    wp_user = os.environ.get("WP_USER")
    wp_password = os.environ.get("WP_APP_PASSWORD")

    if not all([wp_url, wp_user, wp_password]):
        print("⚠️  WordPress credentials not set. Required env vars:")
        print("   WP_URL, WP_USER, WP_APP_PASSWORD")
        return None
    return wp_url, wp_user, wp_password


def push_to_wordpress(json_path: str):
    """Push JSON to WordPress."""
    creds = get_wp_credentials()
    if not creds:
        return None
    wp_url, wp_user, wp_password = creds

    data = json.loads(Path(json_path).read_text())

    # Extract race name for page title
    race_name = data.get("race", {}).get("name", "Race Landing Page")
    display_name = data.get("race", {}).get("display_name", race_name)

    # Create page via WordPress REST API
    endpoint = f"{wp_url}/wp-json/wp/v2/pages"

    page_data = {
        "title": display_name,
        "content": "",  # Elementor uses its own data
        "status": "draft",  # Start as draft for review
        "meta": {
            "_yoast_wpseo_title": f"{display_name} – Gravel Race Info & Training Guide | Gravel God",
            "_yoast_wpseo_metadesc": f"Complete guide to {display_name}: race vitals, route, history, and how to train for success.",
        }
    }

    try:
        response = requests.post(
            endpoint,
            json=page_data,
            auth=(wp_user, wp_password),
            timeout=30
        )

        if response.status_code in [200, 201]:
            page_id = response.json()["id"]
            page_url = response.json()["link"]
            print(f"✓ Page created: {page_url}")
            print(f"  ID: {page_id}")
            print(f"  Status: draft (review before publishing)")
            return page_id
        else:
            print(f"✗ Failed to create page: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"✗ Error pushing to WordPress: {e}")
        return None


def sync_index(index_file: str):
    """Upload or replace race-index.json in WP Media Library."""
    creds = get_wp_credentials()
    if not creds:
        return None
    wp_url, wp_user, wp_password = creds
    auth = (wp_user, wp_password)

    index_path = Path(index_file)
    if not index_path.exists():
        print(f"✗ Index file not found: {index_path}")
        return None

    filename = index_path.name
    media_endpoint = f"{wp_url}/wp-json/wp/v2/media"

    # Check for existing attachment
    try:
        search_resp = requests.get(
            media_endpoint,
            params={"search": index_path.stem},
            auth=auth,
            timeout=30,
        )
        search_resp.raise_for_status()
        existing = [
            m for m in search_resp.json()
            if m.get("source_url", "").endswith(f"/{filename}")
        ]
    except Exception as e:
        print(f"✗ Error searching WP media: {e}")
        return None

    file_data = index_path.read_bytes()
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "application/json",
    }

    try:
        if existing:
            media_id = existing[0]["id"]
            resp = requests.post(
                f"{media_endpoint}/{media_id}",
                data=file_data,
                headers=headers,
                auth=auth,
                timeout=30,
            )
        else:
            resp = requests.post(
                media_endpoint,
                data=file_data,
                headers=headers,
                auth=auth,
                timeout=30,
            )

        if resp.status_code in [200, 201]:
            url = resp.json().get("source_url", "(unknown)")
            action = "Updated" if existing else "Uploaded"
            print(f"✓ {action}: {url}")
            return url
        else:
            print(f"✗ Failed to upload index: {resp.status_code}")
            print(resp.text)
            return None
    except Exception as e:
        print(f"✗ Error uploading to WordPress: {e}")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Push race pages or sync race index to WordPress"
    )
    parser.add_argument("--json", help="Path to landing page JSON")
    parser.add_argument(
        "--sync-index", action="store_true",
        help="Upload/replace race-index.json in WP Media Library"
    )
    parser.add_argument(
        "--index-file", default="web/race-index.json",
        help="Path to index file (default: web/race-index.json)"
    )
    args = parser.parse_args()

    if not args.json and not args.sync_index:
        parser.error("Provide --json and/or --sync-index")

    if args.json:
        push_to_wordpress(args.json)
    if args.sync_index:
        sync_index(args.index_file)
