#!/usr/bin/env python3
"""
Push landing page JSON to WordPress/Elementor.
"""

import argparse
import json
import os
import requests
from pathlib import Path


def push_to_wordpress(json_path: str):
    """Push JSON to WordPress."""
    wp_url = os.environ.get("WP_URL")
    wp_user = os.environ.get("WP_USER")
    wp_password = os.environ.get("WP_APP_PASSWORD")
    
    if not all([wp_url, wp_user, wp_password]):
        print("⚠️  WordPress credentials not set, skipping push")
        return None
    
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="Path to landing page JSON")
    args = parser.parse_args()
    
    push_to_wordpress(args.json)

