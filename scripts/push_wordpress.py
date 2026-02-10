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


def sync_training(js_file: str):
    """Upload training-plans.js and training-plans-form.js to WP uploads via SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    js_path = Path(js_file)
    if not js_path.exists():
        print(f"✗ Training plans JS not found: {js_path}")
        return None

    remote_path = f"{WP_UPLOADS}/{js_path.name}"
    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(js_path),
                f"{user}@{host}:{remote_path}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
        public_url = f"{wp_url}/wp-content/uploads/{js_path.name}"
        print(f"✓ Uploaded training plans JS: {public_url}")
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading: {e}")
        return None

    # Upload companion form JS file (same directory as landing JS)
    form_js_path = js_path.parent / "training-plans-form.js"
    if form_js_path.exists():
        remote_form = f"{WP_UPLOADS}/{form_js_path.name}"
        try:
            subprocess.run(
                [
                    "scp", "-i", str(SSH_KEY), "-P", port,
                    str(form_js_path),
                    f"{user}@{host}:{remote_form}",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            form_url = f"{wp_url}/wp-content/uploads/{form_js_path.name}"
            print(f"✓ Uploaded training form JS: {form_url}")
        except subprocess.CalledProcessError as e:
            print(f"✗ SCP failed for form JS: {e.stderr.strip()}")
        except Exception as e:
            print(f"✗ Error uploading form JS: {e}")
    else:
        print(f"⚠ Form JS not found: {form_js_path} (questionnaire page may not work without it)")

    return public_url


def sync_guide(guide_dir: str):
    """Upload guide/index.html + guide-assets/ to /guide/ on SiteGround via tar+ssh."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    guide_path = Path(guide_dir)
    html_file = guide_path / "guide.html"
    assets_dir = guide_path / "guide-assets"

    if not html_file.exists():
        print(f"✗ Guide HTML not found: {html_file}")
        print("  Run: python3 wordpress/generate_guide.py first")
        return None

    # Remote base: public_html/guide/
    remote_base = "~/www/gravelgodcycling.com/public_html/guide"

    # Create remote directory structure
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"mkdir -p {remote_base}/guide-assets {remote_base}/media",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create remote directory: {e.stderr.strip()}")
        return None

    # Upload guide.html as index.html
    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(html_file),
                f"{user}@{host}:{remote_base}/index.html",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        print(f"✓ Uploaded guide HTML: {SITE_BASE_URL}/guide/")
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for guide HTML: {e.stderr.strip()}")
        return None

    # Upload guide-assets/
    if assets_dir.exists():
        asset_files = list(assets_dir.iterdir())
        for asset_file in asset_files:
            try:
                subprocess.run(
                    [
                        "scp", "-i", str(SSH_KEY), "-P", port,
                        str(asset_file),
                        f"{user}@{host}:{remote_base}/guide-assets/{asset_file.name}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                print(f"✓ Uploaded asset: guide-assets/{asset_file.name}")
            except subprocess.CalledProcessError as e:
                print(f"✗ SCP failed for {asset_file.name}: {e.stderr.strip()}")
    else:
        print(f"⚠ No guide-assets/ directory found (inline mode?)")

    # Upload guide/media/ (generated images)
    media_dir = Path(guide_dir).parent / "guide" / "media"
    if not media_dir.exists():
        media_dir = guide_path / "media"
    if media_dir.exists():
        media_files = [f for f in media_dir.iterdir() if f.suffix in (".webp", ".mp4")]
        if media_files:
            # Create remote media directory
            try:
                subprocess.run(
                    [
                        "ssh", "-i", str(SSH_KEY), "-p", port,
                        f"{user}@{host}",
                        f"mkdir -p {remote_base}/media",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
            except subprocess.CalledProcessError as e:
                print(f"✗ Failed to create remote media directory: {e.stderr.strip()}")
                return None

            # Upload via tar+ssh pipe for efficiency
            file_list = [f.name for f in media_files]
            try:
                tar_cmd = subprocess.Popen(
                    ["tar", "-cf", "-", "-C", str(media_dir)] + file_list,
                    stdout=subprocess.PIPE,
                )
                ssh_cmd = subprocess.run(
                    [
                        "ssh", "-i", str(SSH_KEY), "-p", port,
                        f"{user}@{host}",
                        f"tar -xf - -C {remote_base}/media",
                    ],
                    stdin=tar_cmd.stdout,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                tar_cmd.wait()
                if ssh_cmd.returncode == 0:
                    print(f"✓ Uploaded {len(media_files)} media files to /guide/media/")
                else:
                    print(f"✗ Media upload failed: {ssh_cmd.stderr.strip()}")
            except Exception as e:
                print(f"✗ Media upload error: {e}")
        else:
            print(f"⚠ No .webp/.mp4 files in {media_dir}")
    else:
        print(f"⚠ No guide/media/ directory found (run generate_guide_media.py first)")

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    return f"{wp_url}/guide/"


SITE_BASE_URL = os.environ.get("WP_URL", "https://gravelgodcycling.com")


def sync_homepage(homepage_file: str):
    """Upload homepage.html to /homepage/index.html on SiteGround via SSH+SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    html_path = Path(homepage_file)
    if not html_path.exists():
        print(f"✗ Homepage HTML not found: {html_path}")
        print("  Run: python3 wordpress/generate_homepage.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/homepage"

    # Create remote directory
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"mkdir -p {remote_base}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create remote directory: {e.stderr.strip()}")
        return None

    # Upload homepage.html as index.html
    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(html_path),
                f"{user}@{host}:{remote_base}/index.html",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
        print(f"✓ Uploaded homepage: {wp_url}/homepage/")
        return f"{wp_url}/homepage/"
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for homepage: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading homepage: {e}")
        return None


def sync_og(og_dir: str):
    """Upload OG images to /og/ on SiteGround via tar+ssh pipe.

    Only syncs *.jpg files (ignores stale .png artifacts).
    Uses tar pipe for efficiency — 328 files in one connection.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    og_path = Path(og_dir)
    if not og_path.exists():
        print(f"✗ OG image directory not found: {og_path}")
        return None

    jpg_files = list(og_path.glob("*.jpg"))
    if not jpg_files:
        print(f"✗ No .jpg files found in {og_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/og"

    # Create remote directory
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"mkdir -p {remote_base}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create remote directory: {e.stderr.strip()}")
        return None

    # tar+ssh pipe: local tar → ssh → remote tar extract
    # Only include *.jpg files
    filenames = [f.name for f in jpg_files]
    print(f"  Uploading {len(filenames)} OG images via tar+ssh...")

    try:
        tar_cmd = ["tar", "-cf", "-", "-C", str(og_path)] + filenames
        ssh_cmd = [
            "ssh", "-i", str(SSH_KEY), "-p", port,
            f"{user}@{host}",
            f"tar -xf - -C {remote_base}",
        ]

        tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
        ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_proc.stdout.close()
        stdout, stderr = ssh_proc.communicate(timeout=120)

        if ssh_proc.returncode != 0:
            print(f"✗ tar+ssh failed: {stderr.decode().strip()}")
            return None

        wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
        print(f"✓ Uploaded {len(filenames)} OG images to {wp_url}/og/")
        return f"{wp_url}/og/"
    except subprocess.TimeoutExpired:
        print("✗ Upload timed out (120s)")
        tar_proc.kill()
        ssh_proc.kill()
        return None
    except Exception as e:
        print(f"✗ Error uploading OG images: {e}")
        return None


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
    parser.add_argument(
        "--sync-training", action="store_true",
        help="Upload training-plans.js to WP uploads via SCP"
    )
    parser.add_argument(
        "--training-file", default="web/training-plans.js",
        help="Path to training plans JS (default: web/training-plans.js)"
    )
    parser.add_argument(
        "--sync-guide", action="store_true",
        help="Upload training guide to /guide/ via SCP"
    )
    parser.add_argument(
        "--guide-dir", default="wordpress/output",
        help="Path to guide output directory (default: wordpress/output)"
    )
    parser.add_argument(
        "--sync-og", action="store_true",
        help="Upload OG images to /og/ via tar+ssh"
    )
    parser.add_argument(
        "--og-dir", default="wordpress/output/og",
        help="Path to OG image directory (default: wordpress/output/og)"
    )
    parser.add_argument(
        "--sync-homepage", action="store_true",
        help="Upload homepage to /homepage/ via SCP"
    )
    parser.add_argument(
        "--homepage-file", default="wordpress/output/homepage.html",
        help="Path to homepage HTML (default: wordpress/output/homepage.html)"
    )
    args = parser.parse_args()

    if not args.json and not args.sync_index and not args.sync_widget and not args.sync_training and not args.sync_guide and not args.sync_og and not args.sync_homepage:
        parser.error("Provide --json, --sync-index, --sync-widget, --sync-training, --sync-guide, --sync-og, and/or --sync-homepage")

    if args.json:
        push_to_wordpress(args.json)
    if args.sync_index:
        sync_index(args.index_file)
    if args.sync_widget:
        sync_widget(args.widget_file)
    if args.sync_training:
        sync_training(args.training_file)
    if args.sync_guide:
        sync_guide(args.guide_dir)
    if args.sync_og:
        sync_og(args.og_dir)
    if args.sync_homepage:
        sync_homepage(args.homepage_file)
