#!/usr/bin/env python3
"""
Push landing page JSON or race index to WordPress.
"""

import argparse
import json
import os
import subprocess
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

SSH_KEY = Path.home() / ".ssh" / "siteground_key"
WP_UPLOADS = "~/www/gravelgodcycling.com/public_html/wp-content/uploads"


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


def get_ssh_credentials():
    """Return (host, user, port) or None with warning."""
    host = os.environ.get("SSH_HOST")
    user = os.environ.get("SSH_USER")
    port = os.environ.get("SSH_PORT", "18765")

    if not all([host, user]):
        print("⚠️  SSH credentials not set. Required env vars:")
        print("   SSH_HOST, SSH_USER (optional: SSH_PORT)")
        return None
    if not SSH_KEY.exists():
        print(f"⚠️  SSH key not found: {SSH_KEY}")
        return None
    return host, user, port


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
    """Upload race-index.json to WP uploads via SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    index_path = Path(index_file)
    if not index_path.exists():
        print(f"✗ Index file not found: {index_path}")
        return None

    remote_path = f"{WP_UPLOADS}/{index_path.name}"
    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(index_path),
                f"{user}@{host}:{remote_path}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
        public_url = f"{wp_url}/wp-content/uploads/{index_path.name}"
        print(f"✓ Uploaded: {public_url}")
        return public_url
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading: {e}")
        return None


def sync_widget(widget_file: str):
    """Upload gravel-race-search.html and gravel-race-search.js to WP uploads via SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    widget_path = Path(widget_file)
    if not widget_path.exists():
        print(f"✗ Widget file not found: {widget_path}")
        return None

    # Upload HTML widget
    remote_path = f"{WP_UPLOADS}/{widget_path.name}"
    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(widget_path),
                f"{user}@{host}:{remote_path}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
        public_url = f"{wp_url}/wp-content/uploads/{widget_path.name}"
        print(f"✓ Uploaded widget: {public_url}")
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for widget HTML: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading widget HTML: {e}")
        return None

    # Upload companion JS file (same directory as HTML)
    js_path = widget_path.parent / "gravel-race-search.js"
    if js_path.exists():
        remote_js = f"{WP_UPLOADS}/{js_path.name}"
        try:
            subprocess.run(
                [
                    "scp", "-i", str(SSH_KEY), "-P", port,
                    str(js_path),
                    f"{user}@{host}:{remote_js}",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            js_url = f"{wp_url}/wp-content/uploads/{js_path.name}"
            print(f"✓ Uploaded widget JS: {js_url}")
        except subprocess.CalledProcessError as e:
            print(f"✗ SCP failed for widget JS: {e.stderr.strip()}")
        except Exception as e:
            print(f"✗ Error uploading widget JS: {e}")
    else:
        print(f"⚠ Widget JS not found: {js_path} (widget may not work without it)")

    return public_url


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Push race pages or sync race index to WordPress"
    )
    parser.add_argument("--json", help="Path to landing page JSON")
    parser.add_argument(
        "--sync-index", action="store_true",
        help="Upload race-index.json to WP uploads via SCP"
    )
    parser.add_argument(
        "--index-file", default="web/race-index.json",
        help="Path to index file (default: web/race-index.json)"
    )
    parser.add_argument(
        "--sync-widget", action="store_true",
        help="Upload search widget HTML to WP uploads via SCP"
    )
    parser.add_argument(
        "--widget-file", default="web/gravel-race-search.html",
        help="Path to widget file (default: web/gravel-race-search.html)"
    )
    args = parser.parse_args()

    if not args.json and not args.sync_index and not args.sync_widget:
        parser.error("Provide --json, --sync-index, and/or --sync-widget")

    if args.json:
        push_to_wordpress(args.json)
    if args.sync_index:
        sync_index(args.index_file)
    if args.sync_widget:
        sync_widget(args.widget_file)
