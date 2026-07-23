#!/usr/bin/env python3
"""
Push landing page JSON or race index to WordPress.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date

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

    # Validate credentials to prevent command injection
    _bad_chars = re.compile(r'[;\s|&`$]')
    if _bad_chars.search(host):
        print(f"⚠️  SSH_HOST contains invalid characters: {host!r}")
        return None
    if _bad_chars.search(user):
        print(f"⚠️  SSH_USER contains invalid characters: {user!r}")
        return None
    if not port.isdigit():
        print(f"⚠️  SSH_PORT must be numeric: {port!r}")
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
    """Upload gravel-race-search.html, .js, and external CSS to WP uploads via SCP."""
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

    # Upload external CSS file (gg-search.{hash}.css)
    css_files = list(widget_path.parent.glob("gg-search.*.css"))
    if css_files:
        css_path = css_files[0]  # Should be exactly one
        remote_css = f"{WP_UPLOADS}/{css_path.name}"
        try:
            subprocess.run(
                [
                    "scp", "-i", str(SSH_KEY), "-P", port,
                    str(css_path),
                    f"{user}@{host}:{remote_css}",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            css_url = f"{wp_url}/wp-content/uploads/{css_path.name}"
            print(f"✓ Uploaded widget CSS: {css_url}")
        except subprocess.CalledProcessError as e:
            print(f"✗ SCP failed for widget CSS: {e.stderr.strip()}")
        except Exception as e:
            print(f"✗ Error uploading widget CSS: {e}")
    else:
        print(f"⚠ No gg-search.*.css found in {widget_path.parent} (CSS may be inline)")

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
    # Media lives at project_root/guide/media/, not in the output dir
    project_root = Path(__file__).resolve().parent.parent
    media_dir = project_root / "guide" / "media"
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


def sync_guide_cluster(cluster_dir: str):
    """Upload guide cluster pages (pillar + 8 chapters) to /guide/ on SiteGround via tar+ssh.

    Each page is structured as {slug}/index.html under the cluster output directory.
    The pillar page is at index.html (root of cluster_dir).
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    cluster_path = Path(cluster_dir)
    if not cluster_path.exists():
        print(f"✗ Guide cluster directory not found: {cluster_path}")
        print("  Run: python3 wordpress/generate_guide_cluster.py first")
        return None

    # Verify pillar page exists
    pillar = cluster_path / "index.html"
    if not pillar.exists():
        print(f"✗ Guide pillar page not found: {pillar}")
        return None

    # Find all chapter directories with index.html
    chapter_dirs = sorted([
        d for d in cluster_path.iterdir()
        if d.is_dir() and (d / "index.html").exists()
    ])
    if not chapter_dirs:
        print(f"✗ No guide chapter pages found in {cluster_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/guide"

    # Create remote directory structure
    chapter_mkdir = " ".join(f"{remote_base}/{d.name}" for d in chapter_dirs)
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"mkdir -p {remote_base} {chapter_mkdir}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create remote directories: {e.stderr.strip()}")
        return None

    page_count = 1 + len(chapter_dirs)
    print(f"  Uploading {page_count} guide cluster pages via tar+ssh...")

    # Build list of items to tar: index.html + each chapter dir
    items = ["index.html"] + [d.name for d in chapter_dirs]
    try:
        tar_cmd = ["tar", "-cf", "-", "-C", str(cluster_path)] + items
        ssh_cmd = [
            "ssh", "-i", str(SSH_KEY), "-p", port,
            f"{user}@{host}",
            f"tar -xf - -C {remote_base}",
        ]

        tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
        ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_proc.stdout.close()
        stdout, stderr = ssh_proc.communicate(timeout=300)

        if ssh_proc.returncode != 0:
            print(f"✗ tar+ssh failed: {stderr.decode().strip()}")
            return None
    except subprocess.TimeoutExpired:
        print("✗ Upload timed out (300s)")
        tar_proc.kill()
        ssh_proc.kill()
        return None
    except Exception as e:
        print(f"✗ Error uploading guide cluster pages: {e}")
        return None

    # Fix permissions
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"chmod -R 755 {remote_base}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError:
        print("⚠️  Warning: could not fix /guide/ permissions — verify manually")

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded {page_count} guide cluster pages to {wp_url}/guide/")
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


def sync_gravel_tv(gtv_file: str):
    """Upload gravel-tv.html to /gravel-tv/index.html on SiteGround via SSH+SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    html_path = Path(gtv_file)
    if not html_path.exists():
        print(f"✗ Gravel TV HTML not found: {html_path}")
        print("  Run: python3 wordpress/generate_gravel_tv.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/gravel-tv"

    try:
        subprocess.run(
            ["ssh", "-i", str(SSH_KEY), "-p", port, f"{user}@{host}",
             f"mkdir -p {remote_base}"],
            check=True, capture_output=True, text=True, timeout=15,
        )
        subprocess.run(
            ["scp", "-i", str(SSH_KEY), "-P", port, str(html_path),
             f"{user}@{host}:{remote_base}/index.html"],
            check=True, capture_output=True, text=True, timeout=30,
        )
        wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
        print(f"✓ Uploaded Gravel TV: {wp_url}/gravel-tv/")
        return f"{wp_url}/gravel-tv/"
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for Gravel TV: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading Gravel TV: {e}")
        return None


def sync_about(about_file: str):
    """Upload about.html to /about/index.html on SiteGround via SSH+SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    html_path = Path(about_file)
    if not html_path.exists():
        print(f"✗ About page HTML not found: {html_path}")
        print("  Run: python3 wordpress/generate_about.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/about"

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

    # Upload about.html as index.html
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
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for about page: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading about page: {e}")
        return None

    # Upload avatar image if present
    avatar_path = html_path.parent / "matti-avatar.png"
    if avatar_path.exists():
        try:
            subprocess.run(
                [
                    "scp", "-i", str(SSH_KEY), "-P", port,
                    str(avatar_path),
                    f"{user}@{host}:{remote_base}/matti-avatar.png",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.CalledProcessError:
            print("  ⚠ Could not upload matti-avatar.png (non-fatal)")

    # Upload shared CSS/JS assets (about page references them via /race/assets/)
    assets_dir = html_path.parent / "assets"
    remote_assets = "~/www/gravelgodcycling.com/public_html/race/assets"
    for pattern in ("gg-styles.*.css", "gg-scripts.*.js"):
        for asset in assets_dir.glob(pattern):
            try:
                subprocess.run(
                    [
                        "scp", "-i", str(SSH_KEY), "-P", port,
                        str(asset),
                        f"{user}@{host}:{remote_assets}/{asset.name}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError:
                print(f"  ⚠ Could not upload {asset.name} (non-fatal)")

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded about page: {wp_url}/about/")
    return f"{wp_url}/about/"


def sync_coaching(coaching_file: str):
    """Upload coaching.html to /coaching/index.html on SiteGround via SSH+SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    html_path = Path(coaching_file)
    if not html_path.exists():
        print(f"✗ Coaching page HTML not found: {html_path}")
        print("  Run: python3 wordpress/generate_coaching.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/coaching"

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

    # Upload coaching.html as index.html
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
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for coaching page: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading coaching page: {e}")
        return None

    # Upload shared CSS/JS assets (coaching page references them via /race/assets/)
    assets_dir = html_path.parent / "assets"
    remote_assets = "~/www/gravelgodcycling.com/public_html/race/assets"
    for pattern in ("gg-styles.*.css", "gg-scripts.*.js"):
        for asset in assets_dir.glob(pattern):
            try:
                subprocess.run(
                    [
                        "scp", "-i", str(SSH_KEY), "-P", port,
                        str(asset),
                        f"{user}@{host}:{remote_assets}/{asset.name}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError:
                print(f"  ⚠ Could not upload {asset.name} (non-fatal)")

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded coaching page: {wp_url}/coaching/")
    return f"{wp_url}/coaching/"


def sync_success(output_dir: str):
    """Upload success pages to SiteGround via SSH+SCP.

    Deploys 3 pages:
      - training-plans-success.html -> /training-plans/success/index.html
      - coaching-welcome.html       -> /coaching/welcome/index.html
      - consulting-confirmed.html   -> /consulting/confirmed/index.html
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    pages = [
        ("training-plans-success.html", "training-plans/success"),
        ("coaching-welcome.html", "coaching/welcome"),
        ("consulting-confirmed.html", "consulting/confirmed"),
    ]

    out_dir = Path(output_dir)
    remote_root = "~/www/gravelgodcycling.com/public_html"
    uploaded = []

    for filename, remote_path in pages:
        html_path = out_dir / filename
        if not html_path.exists():
            print(f"✗ Success page not found: {html_path}")
            print("  Run: python3 wordpress/generate_success_pages.py first")
            continue

        remote_dir = f"{remote_root}/{remote_path}"

        # Create remote directory
        try:
            subprocess.run(
                [
                    "ssh", "-i", str(SSH_KEY), "-p", port,
                    f"{user}@{host}",
                    f"mkdir -p {remote_dir}",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to create {remote_path}/: {e.stderr.strip()}")
            continue

        # Upload as index.html
        try:
            subprocess.run(
                [
                    "scp", "-i", str(SSH_KEY), "-P", port,
                    str(html_path),
                    f"{user}@{host}:{remote_dir}/index.html",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            uploaded.append(remote_path)
        except subprocess.CalledProcessError as e:
            print(f"✗ SCP failed for {filename}: {e.stderr.strip()}")
            continue

    # Upload shared CSS/JS assets
    assets_dir = out_dir / "assets"
    remote_assets = f"{remote_root}/race/assets"
    for pattern in ("gg-styles.*.css", "gg-scripts.*.js"):
        for asset in assets_dir.glob(pattern):
            try:
                subprocess.run(
                    [
                        "scp", "-i", str(SSH_KEY), "-P", port,
                        str(asset),
                        f"{user}@{host}:{remote_assets}/{asset.name}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError:
                print(f"  ⚠ Could not upload {asset.name} (non-fatal)")

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    for path in uploaded:
        print(f"✓ Uploaded success page: {wp_url}/{path}/")

    if len(uploaded) == len(pages):
        print(f"✓ All {len(uploaded)} success pages deployed")
    elif uploaded:
        print(f"⚠ {len(uploaded)}/{len(pages)} success pages deployed")
    else:
        print("✗ No success pages deployed")
        return None

    return uploaded


def sync_consulting(consulting_file: str):
    """Upload consulting.html to /consulting/index.html on SiteGround via SSH+SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    html_path = Path(consulting_file)
    if not html_path.exists():
        print(f"✗ Consulting page HTML not found: {html_path}")
        print("  Run: python3 wordpress/generate_consulting.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/consulting"

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

    # Upload consulting.html as index.html
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
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for consulting page: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading consulting page: {e}")
        return None

    # Upload shared CSS/JS assets (consulting page references them via /race/assets/)
    assets_dir = html_path.parent / "assets"
    remote_assets = "~/www/gravelgodcycling.com/public_html/race/assets"
    for pattern in ("gg-styles.*.css", "gg-scripts.*.js"):
        for asset in assets_dir.glob(pattern):
            try:
                subprocess.run(
                    [
                        "scp", "-i", str(SSH_KEY), "-P", port,
                        str(asset),
                        f"{user}@{host}:{remote_assets}/{asset.name}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError:
                print(f"  ⚠ Could not upload {asset.name} (non-fatal)")

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded consulting page: {wp_url}/consulting/")
    return f"{wp_url}/consulting/"


def sync_legal(output_dir: str):
    """Upload privacy.html, terms.html, cookies.html to /privacy/, /terms/, /cookies/ on SiteGround."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    out = Path(output_dir)
    pages = {"privacy": "privacy.html", "terms": "terms.html", "cookies": "cookies.html"}
    uploaded = []

    for slug, filename in pages.items():
        html_path = out / filename
        if not html_path.exists():
            print(f"✗ Legal page not found: {html_path}")
            print("  Run: python3 wordpress/generate_legal_pages.py first")
            continue

        remote_dir = f"~/www/gravelgodcycling.com/public_html/{slug}"
        try:
            subprocess.run(
                ["ssh", "-i", str(SSH_KEY), "-p", port, f"{user}@{host}", f"mkdir -p {remote_dir}"],
                check=True, capture_output=True, text=True, timeout=15,
            )
            subprocess.run(
                ["scp", "-i", str(SSH_KEY), "-P", port, str(html_path), f"{user}@{host}:{remote_dir}/index.html"],
                check=True, capture_output=True, text=True, timeout=30,
            )
            uploaded.append(slug)
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to upload {slug}: {e.stderr.strip()}")

    if uploaded:
        wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
        for slug in uploaded:
            print(f"✓ Uploaded legal page: {wp_url}/{slug}/")

    # Upload shared CSS/JS assets
    assets_dir = out / "assets"
    remote_assets = "~/www/gravelgodcycling.com/public_html/race/assets"
    for pattern in ("gg-styles.*.css", "gg-scripts.*.js"):
        for asset in assets_dir.glob(pattern):
            try:
                subprocess.run(
                    ["scp", "-i", str(SSH_KEY), "-P", port, str(asset), f"{user}@{host}:{remote_assets}/{asset.name}"],
                    check=True, capture_output=True, text=True, timeout=30,
                )
            except subprocess.CalledProcessError:
                pass

    return uploaded or None


def sync_consent():
    """Upload gg-cookie-consent.php mu-plugin to SiteGround."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    mu_plugin = Path(__file__).parent.parent / "wordpress" / "mu-plugins" / "gg-cookie-consent.php"
    if not mu_plugin.exists():
        print(f"✗ Cookie consent mu-plugin not found: {mu_plugin}")
        return None

    remote = "~/www/gravelgodcycling.com/public_html/wp-content/mu-plugins/gg-cookie-consent.php"
    try:
        subprocess.run(
            ["scp", "-i", str(SSH_KEY), "-P", port, str(mu_plugin), f"{user}@{host}:{remote}"],
            check=True, capture_output=True, text=True, timeout=30,
        )
        print("✓ Deployed gg-cookie-consent.php mu-plugin")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to deploy cookie consent: {e.stderr.strip()}")
        return None


def sync_training_plans(training_plans_file: str):
    """Upload training-plans/index.html to /products/training-plans/ on SiteGround via SSH+SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    html_path = Path(training_plans_file)
    if not html_path.exists():
        print(f"✗ Training plans page HTML not found: {html_path}")
        print("  Run: python3 wordpress/generate_training_plans.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/products/training-plans"

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

    # Upload training-plans/index.html as index.html
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
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for training plans page: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading training plans page: {e}")
        return None

    # Upload shared CSS/JS assets (training plans page references them via /race/assets/)
    assets_dir = html_path.parent.parent / "assets"
    if not assets_dir.exists():
        assets_dir = html_path.parent / "assets"
    remote_assets = "~/www/gravelgodcycling.com/public_html/race/assets"
    for pattern in ("gg-styles.*.css", "gg-scripts.*.js"):
        for asset in assets_dir.glob(pattern):
            try:
                subprocess.run(
                    [
                        "scp", "-i", str(SSH_KEY), "-P", port,
                        str(asset),
                        f"{user}@{host}:{remote_assets}/{asset.name}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError:
                print(f"  ⚠ Could not upload {asset.name} (non-fatal)")

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded training plans page: {wp_url}/products/training-plans/")
    return f"{wp_url}/products/training-plans/"


def sync_coaching_apply(apply_file: str):
    """Upload coaching-apply.html to /coaching/apply/index.html on SiteGround via SSH+SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    html_path = Path(apply_file)
    if not html_path.exists():
        print(f"✗ Coaching apply HTML not found: {html_path}")
        print("  Run: python3 wordpress/generate_coaching_apply.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/coaching/apply"

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

    # Upload coaching-apply.html as index.html
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
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for coaching apply page: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading coaching apply page: {e}")
        return None

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded coaching apply page: {wp_url}/coaching/apply/")
    return f"{wp_url}/coaching/apply/"


def sync_og(og_dir: str):
    """Upload OG images to /og/ on SiteGround via tar+ssh pipe.

    Only syncs *.jpg files (ignores stale .png artifacts).
    Uses tar pipe for efficiency — all files in one connection.
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


def sync_tp(tp_dir: str):
    """Upload TP-listing images (header + includes-grid) to /tp/ on
    SiteGround via tar+ssh pipe. Same pattern as sync_og — only syncs
    *.jpg files (ignores stale artifacts), tar pipe for one connection.
    Does NOT upload manifest.json (that's a build-time artifact, not a
    hosted asset the TP descriptions reference).
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    tp_path = Path(tp_dir)
    if not tp_path.exists():
        print(f"✗ TP listing image directory not found: {tp_path}")
        return None

    jpg_files = list(tp_path.glob("*.jpg"))
    if not jpg_files:
        print(f"✗ No .jpg files found in {tp_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/tp"

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
    print(f"  Uploading {len(filenames)} TP listing images via tar+ssh...")

    try:
        tar_cmd = ["tar", "-cf", "-", "-C", str(tp_path)] + filenames
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
        print(f"✓ Uploaded {len(filenames)} TP listing images to {wp_url}/tp/")
        return f"{wp_url}/tp/"
    except subprocess.TimeoutExpired:
        print("✗ Upload timed out (120s)")
        tar_proc.kill()
        ssh_proc.kill()
        return None
    except Exception as e:
        print(f"✗ Error uploading TP listing images: {e}")
        return None


# Utility pages whose canonical URL is the site ROOT — sync_pages must not
# ship them under /race/ (duplicate content; removed + 301'd 2026-07-23).
ROOT_CANONICAL_SLUGS = frozenset({
    "about", "articles", "coaching", "consulting", "cookies", "course",
    "gravel-tv", "guide", "homepage", "insights", "privacy", "terms",
    "training-plans",
})


def sync_pages(pages_dir: str):
    """Upload race pages to /race/ on SiteGround via tar+ssh pipe.

    Converts flat {slug}.html files to {slug}/index.html directory structure.
    Also uploads shared assets/ directory. Ensures /race/ directory has 755
    permissions so Apache/Googlebot can access the pages.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    pages_path = Path(pages_dir)
    if not pages_path.exists():
        print(f"✗ Pages directory not found: {pages_path}")
        return None

    html_files = sorted(f for f in pages_path.glob("*.html")
                        if f.stem not in ROOT_CANONICAL_SLUGS)
    # Also check for pre-built subdirectories (vs pages, state hubs, etc.)
    SKIP_DIRS = {"assets", "og", "prep-kit", "blog", "race"}
    subdirs_with_pages = [
        d for d in sorted(pages_path.iterdir())
        if d.is_dir() and d.name not in SKIP_DIRS
        and ((d / "index.html").exists() or any(d.rglob("index.html")))
    ]
    if not html_files and not subdirs_with_pages:
        print(f"✗ No .html files or page subdirectories found in {pages_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/race"

    # Create remote directory with correct permissions
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"mkdir -p {remote_base} && chmod 755 {remote_base}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create remote directory: {e.stderr.strip()}")
        return None

    # Build tar archive with {slug}/index.html directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        page_count = 0
        for html_file in html_files:
            slug = html_file.stem
            slug_dir = tmpdir / slug
            slug_dir.mkdir()
            shutil.copy2(html_file, slug_dir / "index.html")
            page_count += 1

        # Also include pre-built subdirectories (e.g., tier-1/, vs pages, state hubs, calendar)
        SKIP_DIRS = {"assets", "og", "prep-kit", "blog", "race"}
        for subdir in sorted(pages_path.iterdir()):
            if subdir.is_dir() and subdir.name not in SKIP_DIRS:
                # Check for index.html directly or in nested subdirs (e.g., calendar/2026/)
                has_index = (subdir / "index.html").exists()
                has_nested = any(subdir.rglob("index.html")) if not has_index else False
                if has_index or has_nested:
                    dst = tmpdir / subdir.name
                    shutil.copytree(subdir, dst, dirs_exist_ok=True)
                    page_count += 1

        # Also include assets/ if present
        assets_src = pages_path / "assets"
        if assets_src.exists():
            shutil.copytree(assets_src, tmpdir / "assets", dirs_exist_ok=True)
            print(f"  Including shared assets/")

        print(f"  Uploading {page_count} race pages via tar+ssh...")

        try:
            # List all items in tmpdir for tar
            items = [p.name for p in sorted(tmpdir.iterdir())]
            tar_cmd = ["tar", "-cf", "-", "-C", str(tmpdir)] + items
            ssh_cmd = [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"tar -xf - -C {remote_base}",
            ]

            tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
            ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            tar_proc.stdout.close()
            stdout, stderr = ssh_proc.communicate(timeout=300)

            if ssh_proc.returncode != 0:
                print(f"✗ tar+ssh failed: {stderr.decode().strip()}")
                return None
        except subprocess.TimeoutExpired:
            print("✗ Upload timed out (300s)")
            tar_proc.kill()
            ssh_proc.kill()
            return None
        except Exception as e:
            print(f"✗ Error uploading race pages: {e}")
            return None

    # Fix permissions on /race/ directory (prevents 403 for Googlebot)
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"chmod 755 {remote_base}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError:
        print("⚠️  Warning: could not fix /race/ permissions — verify manually")

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded {page_count} race pages to {wp_url}/race/")
    return f"{wp_url}/race/"


REDIRECT_BLOCK = """\
# BEGIN Gravel God Redirects
<IfModule mod_rewrite.c>
RewriteEngine On

# /llms.txt → repo-generated file, not AIOSEO's. All in One SEO v4.9 writes
# its own physical llms.txt to this same webroot path on its own schedule
# (confirmed 2026-07-18: served content was literally "Generated by All in
# One SEO v4.9.10..." with a same-day last-modified, clobbering our upload —
# it's a last-write-wins race on one physical filename, not a WP rewrite
# intercepting a real file). Confirmed .htaccess RewriteRules here fire
# ahead of physical-file resolution regardless (race/sagan-fondo/ still
# 301s via the rule below despite its index.html existing on disk), so this
# internal rewrite reliably wins the race by always serving a filename
# AIOSEO doesn't know about. See scripts/push_wordpress.py::sync_llms_txt()
# for the upload side (uploads web/llms.txt content to llms-repo.txt too).
RewriteRule ^llms\\.txt$ /llms-repo.txt [L]

# /page/N/ → / (homepage pagination is meaningless, prevents noindex gap)
RewriteRule ^page/\\d+/?$ / [R=301,L]

# /guide.html → /guide/ (old URL from search engines / bookmarks)
RewriteRule ^guide\\.html$ /guide/ [R=301,L]

# /race/ directory index → search page (prevents 403)
RewriteRule ^race/?$ /gravel-races/ [R=301,L]

# /methodology/ → canonical location under /race/ (bare path 404s otherwise)
RewriteRule ^methodology/?$ /race/methodology/ [R=301,L]

# WP race guide pages → static race pages (duplicate content fix)
RewriteRule ^barry-roubaix-race-guide/?$ /race/barry-roubaix/ [R=301,L]
RewriteRule ^belgian-waffle-ride-race-guide/?$ /race/bwr-california/ [R=301,L]
RewriteRule ^traka-360-race-guide/?$ /race/the-traka/ [R=301,L]
RewriteRule ^unbound-gravel-200-race-guide/?$ /race/unbound-200/ [R=301,L]
RewriteRule ^the-rad-race-guide/?$ /race/the-rad/ [R=301,L]
RewriteRule ^sbt-grvl-race-guide/?$ /race/steamboat-gravel/ [R=301,L]
RewriteRule ^rooted-vermont-race-guide/?$ /race/rooted-vermont/ [R=301,L]
RewriteRule ^ned-gravel-race-guide/?$ /race/ned-gravel/ [R=301,L]
RewriteRule ^mid-south-race-guide/?$ /race/mid-south/ [R=301,L]
RewriteRule ^leadville-trail-100-mtb-race-guide/?$ /race/leadville-100/ [R=301,L]
RewriteRule ^gravel-worlds-race-guide/?$ /race/gravel-worlds/ [R=301,L]
RewriteRule ^gravel-locos-race-guide/?$ /race/gravel-locos/ [R=301,L]
RewriteRule ^dirty-reiver-race-guide/?$ /race/dirty-reiver/ [R=301,L]
RewriteRule ^crusher-tushar-race-guide/?$ /race/crusher-in-the-tushar/ [R=301,L]
RewriteRule ^big-sugar-race-guide/?$ /race/big-sugar/ [R=301,L]
RewriteRule ^big-horn-gravel-race-guide/?$ /race/big-horn-gravel/ [R=301,L]
RewriteRule ^bwr-cedar-city-race-guide/?$ /race/bwr-cedar-city/ [R=301,L]
RewriteRule ^oregon-trail-gravel-race-guide/?$ /race/oregon-trail-gravel/ [R=301,L]
RewriteRule ^rebeccas-private-idaho-race-guide/?$ /race/rebeccas-private-idaho/ [R=301,L]
RewriteRule ^migration-gravel-race-guide/?$ /race/migration-gravel-race/ [R=301,L]
RewriteRule ^the-rift-race-guide/?$ /race/the-rift/ [R=301,L]
RewriteRule ^sea-otter-gravel-race-guide/?$ /race/sea-otter-gravel/ [R=301,L]

# Short WP pages → static race pages (duplicate content fix)
RewriteRule ^barry-roubaix/?$ /race/barry-roubaix/ [R=301,L]
RewriteRule ^belgian-waffle-ride/?$ /race/bwr-california/ [R=301,L]
RewriteRule ^sbt-grvl/?$ /race/steamboat-gravel/ [R=301,L]
RewriteRule ^mid-south/?$ /race/mid-south/ [R=301,L]
RewriteRule ^unbound-200-2/?$ /race/unbound-200/ [R=301,L]
RewriteRule ^unbound-200/?$ /race/unbound-200/ [R=301,L]
RewriteRule ^crusher-in-the-tushar/?$ /race/crusher-in-the-tushar/ [R=301,L]
RewriteRule ^gravel-worlds/?$ /race/gravel-worlds/ [R=301,L]
RewriteRule ^big-sugar/?$ /race/big-sugar/ [R=301,L]

# /midsouth → TrainingPeaks plan (was PrettyLinks, now static redirect)
RewriteRule ^midsouth/?$ https://www.trainingpeaks.com/training-plans/cycling/gran-fondo-century/tp-260379/gravel-god-the-midsouth-base-to-race [R=307,L]

# /about-me/ → /about/ (old WP page trashed, consolidate 1,169 impressions)
RewriteRule ^about-me/?$ /about/ [R=301,L]

# WP media attachment slugs hijacking /race/ paths
RewriteRule ^race/dirty-kanza/?$ /race/unbound-200/ [R=301,L]
RewriteRule ^race/oregon-trail-gravel-grinder/?$ /race/oregon-trail-gravel/ [R=301,L]

# /training-plans/ directory → product page (prevents 403)
RewriteRule ^training-plans/?$ /products/training-plans/ [R=301,L]

# Broken URL from GSC → parent page (404 fix)
RewriteRule ^training-plans-faq/gravelgodcoaching@gmail\\.com$ /training-plans-faq/ [R=301,L]

# Bare calendar has no index page — send to the current-year calendar
# (update the year segment at each season rollover).
RewriteRule ^race/calendar/?$ /race/calendar/2026/ [R=301,L]

# Fabricated race pages removed (SITE-SYNC S3, 2026-07) → state/region best-of hubs
RewriteRule ^race/black-forest-gravel/?$ /race/best-gravel-races-germany/ [R=301,L]
RewriteRule ^race/ozark-gravel/?$ /race/best-gravel-races-arkansas/ [R=301,L]
RewriteRule ^race/pirate-cycling-league-gravel/?$ /race/best-gravel-races-california/ [R=301,L]
RewriteRule ^race/grasslands-100/?$ /race/best-gravel-races-texas/ [R=301,L]
RewriteRule ^race/balkan-gravel/?$ /race/calendar/2026/ [R=301,L]
# greek-gravel: /race/best-gravel-races-greece/ no longer generates — removing
# greek-gravel drops Greece to 2 real races, below the state-hub MIN_RACES=3
# floor (wordpress/generate_state_hubs.py) — fall back to calendar instead.
RewriteRule ^race/greek-gravel/?$ /race/calendar/2026/ [R=301,L]
RewriteRule ^race/natchez-trace-gran-fondo/?$ /race/best-gravel-races-tennessee/ [R=301,L]
RewriteRule ^race/walburg-dirty-30/?$ /race/best-gravel-races-texas/ [R=301,L]
RewriteRule ^race/flint-hills-death-ride/?$ /race/best-gravel-races-kansas/ [R=301,L]
RewriteRule ^race/kal-tour-dirty-100/?$ /race/best-gravel-races-michigan/ [R=301,L]
# chiang-mai-gran-fondo: fabricated-as-named (2026-07-23 audit — GFNY never ran
# Chiang Mai; all references were circular self-sourcing). Subpaths covered.
RewriteRule ^race/chiang-mai-gran-fondo/?$ /race/calendar/2026/ [R=301,L]
RewriteRule ^race/chiang-mai-gran-fondo/(.*)$ /race/calendar/2026/ [R=301,L]
# gfny-bali -> gfny-belitung (event relocated/rebranded 2026; bali.gfny.com
# itself 301s to belitung.gfny.com). Subpaths preserved.
RewriteRule ^race/gfny-bali/?$ /race/gfny-belitung/ [R=301,L]
RewriteRule ^race/gfny-bali/(.*)$ /race/gfny-belitung/$1 [R=301,L]

# Race renames (2026-07, Matti-approved): event rebrands, slug follows.
# VS rules MUST precede the wildcards (the old slug is a prefix of the VS slugs).
RewriteRule ^race/badlands-vs-gravel-fondo-switzerland/?$ /race/the-majestics/ [R=301,L]
RewriteRule ^race/gravel-fondo-switzerland-vs-the-traka/?$ /race/the-majestics/ [R=301,L]
RewriteRule ^race/gravel-fondo-switzerland-vs-torino-nice-rally/?$ /race/the-majestics/ [R=301,L]
RewriteRule ^race/gravel-fondo-switzerland-vs-transcontinental-race/?$ /race/the-majestics/ [R=301,L]
RewriteRule ^race/gravel-fondo-switzerland-vs-uci-gravel-worlds/?$ /race/the-majestics/ [R=301,L]
RewriteRule ^race/sagan-fondo/?$ /race/truckee-tahoe-gravel/ [R=301,L]
RewriteRule ^race/sagan-fondo/(.*)$ /race/truckee-tahoe-gravel/$1 [R=301,L]
RewriteRule ^race/gravel-fondo-switzerland/?$ /race/the-majestics/ [R=301,L]
RewriteRule ^race/gravel-fondo-switzerland/(.*)$ /race/the-majestics/$1 [R=301,L]

# Serbia hub retired 2026-07-22: deleting fabricated balkan-gravel dropped
# Serbia below the state-hub MIN_RACES floor.
RewriteRule ^race/best-gravel-races-serbia/?$ /gravel-races/ [R=301,L]
# Thailand hub retired 2026-07-23: chiang-mai-gran-fondo tombstone dropped
# Thailand's parseable races below the hub floor.
RewriteRule ^race/best-gravel-races-thailand/?$ /gravel-races/ [R=301,L]

# Duplicate-race removals (immune-surfaced, commits e18dafba + road-tail):
# old slug 301s to the kept canonical twin, subpaths preserved.
# Live dirs deleted 2026-07-22 (deploy-parity first run).
RewriteRule ^race/big-horn-gravel/?$ /race/bighorn-gravel/ [R=301,L]
RewriteRule ^race/big-horn-gravel/(.*)$ /race/bighorn-gravel/$1 [R=301,L]
RewriteRule ^race/dreilaendergiro/?$ /race/dreilander-giro/ [R=301,L]
RewriteRule ^race/dreilaendergiro/(.*)$ /race/dreilander-giro/$1 [R=301,L]
RewriteRule ^race/gran-fondo-felice-gimondi/?$ /race/granfondo-felice-gimondi/ [R=301,L]
RewriteRule ^race/gran-fondo-felice-gimondi/(.*)$ /race/granfondo-felice-gimondi/$1 [R=301,L]
RewriteRule ^race/gran-fondo-guadeloupe/?$ /race/granfondo-la-guadeloupe/ [R=301,L]
RewriteRule ^race/gran-fondo-guadeloupe/(.*)$ /race/granfondo-la-guadeloupe/$1 [R=301,L]
RewriteRule ^race/gran-fondo-novi-sad/?$ /race/granfondo-novi-sad/ [R=301,L]
RewriteRule ^race/gran-fondo-novi-sad/(.*)$ /race/granfondo-novi-sad/$1 [R=301,L]
RewriteRule ^race/gran-fondo-via-del-sale/?$ /race/granfondo-via-del-sale/ [R=301,L]
RewriteRule ^race/gran-fondo-via-del-sale/(.*)$ /race/granfondo-via-del-sale/$1 [R=301,L]
RewriteRule ^race/gran-fondo-vosges/?$ /race/granfondo-vosges/ [R=301,L]
RewriteRule ^race/gran-fondo-vosges/(.*)$ /race/granfondo-vosges/$1 [R=301,L]
RewriteRule ^race/granfondo-strade-bianche/?$ /race/strade-bianche-gran-fondo/ [R=301,L]
RewriteRule ^race/granfondo-strade-bianche/(.*)$ /race/strade-bianche-gran-fondo/$1 [R=301,L]
RewriteRule ^race/istria-gran-fondo/?$ /race/istria-granfondo/ [R=301,L]
RewriteRule ^race/istria-gran-fondo/(.*)$ /race/istria-granfondo/$1 [R=301,L]
RewriteRule ^race/oetztaler-radmarathon/?$ /race/otztaler-radmarathon/ [R=301,L]
RewriteRule ^race/oetztaler-radmarathon/(.*)$ /race/otztaler-radmarathon/$1 [R=301,L]
RewriteRule ^race/tour-de-tucson/?$ /race/el-tour-de-tucson/ [R=301,L]
RewriteRule ^race/tour-de-tucson/(.*)$ /race/el-tour-de-tucson/$1 [R=301,L]
RewriteRule ^race/gran-fondo-greece-loutraki/?$ /race/gran-fondo-loutraki/ [R=301,L]
RewriteRule ^race/gran-fondo-greece-loutraki/(.*)$ /race/gran-fondo-loutraki/$1 [R=301,L]
RewriteRule ^race/granfondo-stelvio-santini/?$ /race/la-stelvio-santini/ [R=301,L]
RewriteRule ^race/granfondo-stelvio-santini/(.*)$ /race/la-stelvio-santini/$1 [R=301,L]
RewriteRule ^race/hotternhell-hundred/?$ /race/hottern-hell-hundred/ [R=301,L]
RewriteRule ^race/hotternhell-hundred/(.*)$ /race/hottern-hell-hundred/$1 [R=301,L]
# Greece hub retired (greek-gravel removal dropped Greece below the floor)
RewriteRule ^race/best-gravel-races-greece/?$ /gravel-races/ [R=301,L]

# /race/{utility} duplicate copies removed 2026-07-23 (deploy-parity review:
# sync_pages ships every flat output/*.html under /race/, duplicating pages
# whose canonical is the site root). 301 to the root originals.
RewriteRule ^race/(about|articles|coaching|consulting|cookies|course|gravel-tv|guide|insights|privacy|terms|training-plans)/?$ /$1/ [R=301,L]
RewriteRule ^race/homepage/?$ / [R=301,L]

# Dead-reference self-healing (2026-07-22 link audit: 215 stale /tires/ +
# 24 undeployed VS URLs sat in the sitemap 404ing). If the page exists on
# disk these rules never fire; if it doesn't, 301 to the parent race page
# (or the races hub) instead of 404ing. MUST stay after the specific VS
# rename rules above — those pages also don't exist on disk and would be
# misrouted by these generic fallbacks.
RewriteCond %{DOCUMENT_ROOT}/race/$1/tires/index.html !-f
RewriteRule ^race/([^/]+)/tires/?$ /race/$1/ [R=301,L]
RewriteCond %{DOCUMENT_ROOT}/race/$1-vs-$2/index.html !-f
RewriteCond %{DOCUMENT_ROOT}/race/$1/index.html -f
RewriteRule ^race/([^/]+?)-vs-([^/]+?)/?$ /race/$1/ [R=301,L]
RewriteCond %{DOCUMENT_ROOT}/race/$1-vs-$2/index.html !-f
RewriteRule ^race/([^/]+?)-vs-([^/]+?)/?$ /gravel-races/ [R=301,L]

# Fabricated-race blog previews pulled 2026-07-22 (stale deploys of pre-S3
# template previews; race pages were already 301'd in SITE-SYNC S3).
RewriteRule ^blog/balkan-gravel/?$ /blog/ [R=301,L]
RewriteRule ^blog/flint-hills-death-ride/?$ /blog/ [R=301,L]
RewriteRule ^blog/grasslands-100/?$ /blog/ [R=301,L]
RewriteRule ^blog/greek-gravel/?$ /blog/ [R=301,L]
RewriteRule ^blog/natchez-trace-gran-fondo/?$ /blog/ [R=301,L]

# Self-healing for stale blog URLs (2026-07-22 reconcile: server /blog/ had
# 109 orphan dirs from older preview generations). A /blog/ URL that exists
# as neither dir nor file 301s to the blog index instead of 404ing.
RewriteCond %{DOCUMENT_ROOT}/blog/$1 !-d
RewriteCond %{DOCUMENT_ROOT}/blog/$1 !-f
RewriteRule ^blog/([^/]+?)/?$ /blog/ [R=301,L]

# WP's default blog feed is 403-blocked; send /feed/ to the maintained race
# RSS instead of a dead end. Anchored so /feed/races.xml itself is untouched.
RewriteRule ^feed/?$ /feed/races.xml [R=301,L]
</IfModule>
# END Gravel God Redirects
"""

REDIRECT_MARKER = "# BEGIN Gravel God Redirects"


def sync_redirects():
    """Add redirect rules to the root .htaccess on SiteGround.

    Reads the current .htaccess, prepends our redirect block if not already
    present, and uploads the updated file. Safe: never touches the WordPress
    section or SGO directives.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return False
    host, user, port = ssh

    remote_htaccess = "~/www/gravelgodcycling.com/public_html/.htaccess"

    # Read current .htaccess
    try:
        result = subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"cat {remote_htaccess}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        current = result.stdout
        # A failed read must NEVER be treated as an empty .htaccess — the
        # write below would erase the WordPress/SGO directives (sol review
        # 2026-07-22). Require a clean exit AND recognizable content.
        if result.returncode != 0 or "# BEGIN WordPress" not in current:
            print("✗ Refusing to write: remote .htaccess read failed or "
                  f"content unrecognized (rc={result.returncode}, "
                  f"{len(current)} bytes)")
            return False
    except Exception as e:
        print(f"✗ Failed to read remote .htaccess: {e}")
        return False

    # Keep a dated remote backup so a bad block is one `cp` from reverted.
    subprocess.run(
        [
            "ssh", "-i", str(SSH_KEY), "-p", port,
            f"{user}@{host}",
            f"cp {remote_htaccess} {remote_htaccess}.bak-$(date +%Y%m%d)",
        ],
        capture_output=True, text=True, timeout=15,
    )

    # Check if our block already exists
    if REDIRECT_MARKER in current:
        # Replace existing block
        import re
        pattern = r"# BEGIN Gravel God Redirects.*?# END Gravel God Redirects\n?"
        updated = re.sub(pattern, "", current, flags=re.DOTALL)
        updated = REDIRECT_BLOCK + "\n" + updated
        print("  Updating existing redirect block...")
    else:
        # Prepend our block before WordPress rules
        updated = REDIRECT_BLOCK + "\n" + current
        print("  Adding new redirect block...")

    # Upload via stdin to avoid temp file issues
    try:
        proc = subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"cat > {remote_htaccess}",
            ],
            input=updated,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode != 0:
            print(f"✗ Failed to write .htaccess: {proc.stderr.strip()}")
            return False
        print("✓ Redirect rules deployed to .htaccess")
        print("  6 utility redirects + 27 duplicate content redirects + 10 fabricated-race redirects (301)"
              " + 1 llms.txt AIOSEO-override rule (internal rewrite, no redirect)")
        return True
    except Exception as e:
        print(f"✗ Failed to upload .htaccess: {e}")
        return False


def sync_sitemap():
    """Deploy race-sitemap.xml and a sitemap index to the server.

    Uploads the generated race sitemap as race-sitemap.xml, then creates a
    sitemap index at sitemap.xml that references race-sitemap.xml plus
    AIOSEO-generated sitemaps (post-sitemap.xml, page-sitemap.xml,
    category-sitemap.xml).
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return False
    host, user, port = ssh

    project_root = Path(__file__).resolve().parent.parent
    race_sitemap = project_root / "web" / "sitemap.xml"
    if not race_sitemap.exists():
        print(f"✗ Race sitemap not found: {race_sitemap}")
        print("  Run: python scripts/generate_sitemap.py")
        return False

    remote_root = "~/www/gravelgodcycling.com/public_html"
    today = date.today().isoformat()

    # 1. Upload race sitemap as race-sitemap.xml
    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(race_sitemap),
                f"{user}@{host}:{remote_root}/race-sitemap.xml",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        print("✓ Uploaded race-sitemap.xml")
    except Exception as e:
        print(f"✗ Failed to upload race-sitemap.xml: {e}")
        return False

    # 1b. Upload blog sitemap if it exists
    blog_sitemap = project_root / "web" / "blog-sitemap.xml"
    has_blog_sitemap = blog_sitemap.exists()
    if has_blog_sitemap:
        try:
            subprocess.run(
                [
                    "scp", "-i", str(SSH_KEY), "-P", port,
                    str(blog_sitemap),
                    f"{user}@{host}:{remote_root}/blog-sitemap.xml",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            print("✓ Uploaded blog-sitemap.xml")
        except Exception as e:
            print(f"  WARN: Failed to upload blog-sitemap.xml: {e}")
            has_blog_sitemap = False

    # 2. Create sitemap index referencing all sub-sitemaps
    blog_sitemap_entry = ""
    if has_blog_sitemap:
        blog_sitemap_entry = f"""  <sitemap>
    <loc>https://gravelgodcycling.com/blog-sitemap.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
"""
    sitemap_index = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://gravelgodcycling.com/race-sitemap.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
{blog_sitemap_entry}  <sitemap>
    <loc>https://gravelgodcycling.com/post-sitemap.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://gravelgodcycling.com/page-sitemap.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://gravelgodcycling.com/category-sitemap.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
</sitemapindex>
"""

    # 3. Upload sitemap index as sitemap.xml
    try:
        proc = subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"cat > {remote_root}/sitemap.xml",
            ],
            input=sitemap_index,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode != 0:
            print(f"✗ Failed to write sitemap.xml: {proc.stderr.strip()}")
            return False
        # Count actual page URLs (exclude image:loc entries)
        try:
            import re as _re
            sitemap_text = race_sitemap.read_text()
            # Count <url> elements, not <loc> (which includes image entries)
            race_url_count = len(_re.findall(r'<url>', sitemap_text))
        except Exception:
            race_url_count = '?'
        print("✓ Deployed sitemap index (sitemap.xml)")
        print(f"  → race-sitemap.xml ({race_url_count} URLs)")
        if has_blog_sitemap:
            print("  → blog-sitemap.xml (blog content)")
        print("  → post-sitemap.xml (AIOSEO blog posts)")
        print("  → page-sitemap.xml (AIOSEO WP pages)")
        print("  → category-sitemap.xml (AIOSEO categories)")
        return True
    except Exception as e:
        print(f"✗ Failed to upload sitemap.xml: {e}")
        return False


def sync_noindex():
    """Deploy the noindex mu-plugin to WordPress.

    Uploads gg-noindex.php to wp-content/mu-plugins/ via SCP.
    This adds <meta name="robots" content="noindex, follow"> to junk pages
    (date archives, pagination, categories, WooCommerce, LearnDash, feeds).
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return False
    host, user, port = ssh

    project_root = Path(__file__).resolve().parent.parent
    plugin_file = project_root / "wordpress" / "mu-plugins" / "gg-noindex.php"
    if not plugin_file.exists():
        print(f"✗ mu-plugin not found: {plugin_file}")
        return False

    remote_path = "~/www/gravelgodcycling.com/public_html/wp-content/mu-plugins"

    # Ensure mu-plugins directory exists
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"mkdir -p {remote_path}",
            ],
            capture_output=True, text=True, timeout=15, check=True,
        )
    except Exception:
        pass  # Directory likely already exists

    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(plugin_file),
                f"{user}@{host}:{remote_path}/gg-noindex.php",
            ],
            capture_output=True, text=True, timeout=15, check=True,
        )
        print("✓ Deployed gg-noindex.php mu-plugin")
        print("  Noindex: date archives, pagination, categories, feeds, search")
        print("  Noindex: WooCommerce (cart, my-account), LearnDash (lessons, courses)")
        print("  Noindex: dashboard, xAPI content, WC-AJAX endpoints")
        return True
    except Exception as e:
        print(f"✗ Failed to deploy mu-plugin: {e}")
        return False


def sync_meta_descriptions():
    """Deploy meta description mu-plugin + JSON data to WordPress.

    Uploads:
      1. gg-meta-descriptions.php → wp-content/mu-plugins/
      2. meta-descriptions.json → wp-content/uploads/gg-meta-descriptions.json

    The mu-plugin reads the JSON and overrides AIOSEO meta descriptions
    via filter hooks for all WordPress pages and posts.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return False
    host, user, port = ssh

    project_root = Path(__file__).resolve().parent.parent
    plugin_file = project_root / "wordpress" / "mu-plugins" / "gg-meta-descriptions.php"
    json_file = project_root / "seo" / "meta-descriptions.json"

    if not plugin_file.exists():
        print(f"✗ mu-plugin not found: {plugin_file}")
        return False
    if not json_file.exists():
        print(f"✗ JSON data not found: {json_file}")
        print("  Run: python scripts/generate_meta_descriptions.py")
        return False

    # Validate JSON before uploading
    try:
        data = json.loads(json_file.read_text())
        count = len(data.get("entries", []))
        if count < 100:
            print(f"✗ Only {count} entries in JSON (expected 131+)")
            return False
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON: {e}")
        return False

    mu_plugins_path = "~/www/gravelgodcycling.com/public_html/wp-content/mu-plugins"
    uploads_path = "~/www/gravelgodcycling.com/public_html/wp-content/uploads"

    # Ensure directories exist
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"mkdir -p {mu_plugins_path} {uploads_path}",
            ],
            capture_output=True, text=True, timeout=15, check=True,
        )
    except Exception:
        pass  # Directories likely already exist

    # Upload JSON data FIRST — mu-plugin reads it on activation, so data
    # must be present before the PHP file arrives to avoid a race condition.
    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(json_file),
                f"{user}@{host}:{uploads_path}/gg-meta-descriptions.json",
            ],
            capture_output=True, text=True, timeout=15, check=True,
        )
    except Exception as e:
        print(f"✗ Failed to upload JSON data: {e}")
        return False

    # Upload mu-plugin
    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(plugin_file),
                f"{user}@{host}:{mu_plugins_path}/gg-meta-descriptions.php",
            ],
            capture_output=True, text=True, timeout=15, check=True,
        )
    except Exception as e:
        print(f"✗ Failed to upload mu-plugin: {e}")
        return False

    # Set file permissions (644 = owner rw, group/others read)
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"chmod 644 {mu_plugins_path}/gg-meta-descriptions.php "
                f"{uploads_path}/gg-meta-descriptions.json",
            ],
            capture_output=True, text=True, timeout=10, check=True,
        )
    except Exception:
        pass  # Non-fatal — SCP usually sets sane defaults

    print(f"✓ Deployed meta descriptions ({count} entries)")
    print("  → gg-meta-descriptions.json (data file, uploaded first)")
    print("  → gg-meta-descriptions.php (mu-plugin)")
    return True


def sync_ctas():
    """Deploy the race CTA mu-plugin to WordPress.

    Uploads gg-race-ctas.php to wp-content/mu-plugins/ via SCP.
    This appends race profile + prep kit CTAs to blog posts that reference
    specific races in the database.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return False
    host, user, port = ssh

    project_root = Path(__file__).resolve().parent.parent
    plugin_file = project_root / "wordpress" / "mu-plugins" / "gg-race-ctas.php"
    if not plugin_file.exists():
        print(f"✗ mu-plugin not found: {plugin_file}")
        return False

    remote_path = "~/www/gravelgodcycling.com/public_html/wp-content/mu-plugins"

    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(plugin_file),
                f"{user}@{host}:{remote_path}/gg-race-ctas.php",
            ],
            capture_output=True, text=True, timeout=15, check=True,
        )
        print("✓ Deployed gg-race-ctas.php mu-plugin")
        print("  Race CTAs: 14 race posts + 1 hydration post → race profiles + prep kits")
        return True
    except Exception as e:
        print(f"✗ Failed to deploy CTA mu-plugin: {e}")
        return False


def sync_training_form():
    """Deploy the training-form mu-plugin to WordPress.

    Uploads gg-training-form.php to wp-content/mu-plugins/ via SCP.
    Enqueues training-plans-form.js on the questionnaire page (ID 5017);
    without it the Submit & Pay button does nothing. The JS itself deploys
    separately via --sync-training.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return False
    host, user, port = ssh

    project_root = Path(__file__).resolve().parent.parent
    plugin_file = project_root / "wordpress" / "mu-plugins" / "gg-training-form.php"
    if not plugin_file.exists():
        print(f"✗ mu-plugin not found: {plugin_file}")
        return False

    remote_path = "~/www/gravelgodcycling.com/public_html/wp-content/mu-plugins"

    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(plugin_file),
                f"{user}@{host}:{remote_path}/gg-training-form.php",
            ],
            capture_output=True, text=True, timeout=15, check=True,
        )
        print("✓ Deployed gg-training-form.php mu-plugin")
        print("  Questionnaire page JS loader (Submit & Pay path)")
        return True
    except Exception as e:
        print(f"✗ Failed to deploy training-form mu-plugin: {e}")
        return False


def sync_ga4():
    """Deploy the GA4 analytics mu-plugin to WordPress.

    Uploads gg-ga4.php to wp-content/mu-plugins/ via SCP.
    Lightweight replacement for MonsterInsights Pro + 6 addons.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return False
    host, user, port = ssh

    project_root = Path(__file__).resolve().parent.parent
    plugin_file = project_root / "wordpress" / "mu-plugins" / "gg-ga4.php"
    if not plugin_file.exists():
        print(f"✗ mu-plugin not found: {plugin_file}")
        return False

    remote_path = "~/www/gravelgodcycling.com/public_html/wp-content/mu-plugins"

    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(plugin_file),
                f"{user}@{host}:{remote_path}/gg-ga4.php",
            ],
            capture_output=True, text=True, timeout=15, check=True,
        )
        print("✓ Deployed gg-ga4.php mu-plugin")
        print("  GA4 tracking: G-EJJZ9T6M52 (replaces MonsterInsights)")
        return True
    except Exception as e:
        print(f"✗ Failed to deploy GA4 mu-plugin: {e}")
        return False


def sync_header():
    """Deploy the shared header mu-plugin to WordPress.

    Uploads gg-header.php to wp-content/mu-plugins/ via SCP.
    Injects dropdown nav on WordPress-managed pages (e.g. /gravel-races/).
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return False
    host, user, port = ssh

    project_root = Path(__file__).resolve().parent.parent
    plugin_file = project_root / "wordpress" / "mu-plugins" / "gg-header.php"
    if not plugin_file.exists():
        print(f"✗ mu-plugin not found: {plugin_file}")
        return False

    remote_path = "~/www/gravelgodcycling.com/public_html/wp-content/mu-plugins"

    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(plugin_file),
                f"{user}@{host}:{remote_path}/gg-header.php",
            ],
            capture_output=True, text=True, timeout=15, check=True,
        )
        print("✓ Deployed gg-header.php mu-plugin (shared dropdown header)")
        return True
    except Exception as e:
        print(f"✗ Failed to deploy header mu-plugin: {e}")
        return False


def sync_ab():
    """Deploy A/B test assets: JS (hashed + unhashed), config JSON, and mu-plugin.

    Uploads:
      - web/gg-ab-tests.js       → /ab/gg-ab-tests.js (for mu-plugin)
      - web/gg-ab-tests.js       → /ab/gg-ab-tests.{hash}.js (for static pages)
      - web/ab/experiments.json   → /ab/experiments.json
      - wordpress/mu-plugins/gg-ab.php → wp-content/mu-plugins/gg-ab.php
    """
    import hashlib

    ssh = get_ssh_credentials()
    if not ssh:
        return False
    host, user, port = ssh

    project_root = Path(__file__).resolve().parent.parent
    js_file = project_root / "web" / "gg-ab-tests.js"
    config_file = project_root / "web" / "ab" / "experiments.json"
    plugin_file = project_root / "wordpress" / "mu-plugins" / "gg-ab.php"

    for f, label in [(js_file, "gg-ab-tests.js"), (config_file, "experiments.json"),
                     (plugin_file, "gg-ab.php")]:
        if not f.exists():
            print(f"✗ A/B file not found: {f}")
            print(f"  Run: python wordpress/ab_experiments.py first")
            return False

    # Compute content hash for cache-busted JS filename
    js_content = js_file.read_text()
    js_hash = hashlib.md5(js_content.encode()).hexdigest()[:8]
    hashed_js_name = f"gg-ab-tests.{js_hash}.js"

    remote_base = "~/www/gravelgodcycling.com/public_html"
    remote_ab = f"{remote_base}/ab"
    remote_mu = f"{remote_base}/wp-content/mu-plugins"

    # Create /ab/ directory and clean old hashed JS files
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"mkdir -p {remote_ab} && chmod 755 {remote_ab} && "
                f"rm -f {remote_ab}/gg-ab-tests.*.js",
            ],
            check=True, capture_output=True, text=True, timeout=15,
        )
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create /ab/ directory: {e.stderr.strip()}")
        return False

    # Upload: unhashed (for mu-plugin) + hashed (for static pages) + config + plugin
    uploads = [
        (js_file, f"{remote_ab}/gg-ab-tests.js"),
        (js_file, f"{remote_ab}/{hashed_js_name}"),
        (config_file, f"{remote_ab}/experiments.json"),
        (plugin_file, f"{remote_mu}/gg-ab.php"),
    ]
    for local, remote in uploads:
        try:
            subprocess.run(
                [
                    "scp", "-i", str(SSH_KEY), "-P", port,
                    str(local),
                    f"{user}@{host}:{remote}",
                ],
                capture_output=True, text=True, timeout=15, check=True,
            )
        except Exception as e:
            print(f"✗ Failed to upload {local.name}: {e}")
            return False

    print("✓ Deployed A/B testing assets:")
    print(f"  /ab/gg-ab-tests.js (unhashed, for mu-plugin)")
    print(f"  /ab/{hashed_js_name} (cache-busted, for static pages)")
    print("  /ab/experiments.json")
    print("  wp-content/mu-plugins/gg-ab.php")
    return True


def purge_cache():
    """Purge all SiteGround caches via wp-cli (static, dynamic, memcached, opcache)."""
    ssh = get_ssh_credentials()
    if not ssh:
        return False
    host, user, port = ssh

    wp_path = "$HOME/www/gravelgodcycling.com/public_html"
    try:
        result = subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"wp --path={wp_path} sg purge 2>&1",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        if result.returncode == 0:
            print(f"✓ SiteGround cache purged (static, dynamic, memcached, opcache)")
            return True
        else:
            print(f"✗ Cache purge failed: {output}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ Cache purge timed out (30s)")
        return False
    except Exception as e:
        print(f"✗ Cache purge error: {e}")
        return False




def sync_photos(photos_dir: str):
    """Upload race photos to /race-photos/ on SiteGround via tar+ssh.

    Uploads {slug}/ directories containing optimized JPG photos.
    Photos are served from /race-photos/{slug}/{filename}.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    photos_path = Path(photos_dir)
    if not photos_path.exists():
        print(f"✗ Photos directory not found: {photos_path}")
        return None

    # Find slug directories that contain photos
    slug_dirs = [d for d in sorted(photos_path.iterdir())
                 if d.is_dir() and any(d.glob("*.jpg"))]
    if not slug_dirs:
        print(f"✗ No photo directories found in {photos_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/race-photos"

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

    # tar+ssh pipe: upload all slug directories
    items = [d.name for d in slug_dirs]
    total_photos = sum(len(list(d.glob("*.jpg"))) for d in slug_dirs)
    print(f"  Uploading {total_photos} photos from {len(slug_dirs)} races via tar+ssh...")

    try:
        tar_cmd = ["tar", "-cf", "-", "-C", str(photos_path)] + items
        ssh_cmd = [
            "ssh", "-i", str(SSH_KEY), "-p", port,
            f"{user}@{host}",
            f"tar -xf - -C {remote_base}",
        ]

        tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
        ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_proc.stdout.close()
        stdout, stderr = ssh_proc.communicate(timeout=300)

        if ssh_proc.returncode != 0:
            print(f"✗ tar+ssh failed: {stderr.decode().strip()}")
            return None
    except subprocess.TimeoutExpired:
        print("✗ Upload timed out (300s)")
        tar_proc.kill()
        ssh_proc.kill()
        return None
    except Exception as e:
        print(f"✗ Error uploading photos: {e}")
        return None

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded {total_photos} photos ({len(slug_dirs)} races) to {wp_url}/race-photos/")
    return f"{wp_url}/race-photos/"


def sync_prep_kits(prep_kit_dir: str):
    """Upload prep kit pages to /race/{slug}/prep-kit/ on SiteGround via tar+ssh.

    Converts flat {slug}.html files to {slug}/prep-kit/index.html directory
    structure under /race/. Same tar+ssh pattern as sync_pages().
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    pk_path = Path(prep_kit_dir)
    if not pk_path.exists():
        print(f"✗ Prep kit directory not found: {pk_path}")
        return None

    html_files = sorted(pk_path.glob("*.html"))
    if not html_files:
        print(f"✗ No .html files found in {pk_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/race"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        page_count = 0
        for html_file in html_files:
            slug = html_file.stem
            pk_dir = tmpdir / slug / "prep-kit"
            pk_dir.mkdir(parents=True)
            shutil.copy2(html_file, pk_dir / "index.html")
            page_count += 1

        print(f"  Uploading {page_count} prep kit pages via tar+ssh...")

        try:
            items = [p.name for p in sorted(tmpdir.iterdir())]
            tar_cmd = ["tar", "-cf", "-", "-C", str(tmpdir)] + items
            ssh_cmd = [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"tar -xf - -C {remote_base}",
            ]

            tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
            ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            tar_proc.stdout.close()
            stdout, stderr = ssh_proc.communicate(timeout=300)

            if ssh_proc.returncode != 0:
                print(f"✗ tar+ssh failed: {stderr.decode().strip()}")
                return None
        except subprocess.TimeoutExpired:
            print("✗ Upload timed out (300s)")
            tar_proc.kill()
            ssh_proc.kill()
            return None
        except Exception as e:
            print(f"✗ Error uploading prep kit pages: {e}")
            return None

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded {page_count} prep kit pages to {wp_url}/race/*/prep-kit/")
    return f"{wp_url}/race/"

def sync_plan_pages(plan_dir: str):
    """Upload training-plan pages to /race/{slug}/training-plan/ on SiteGround via tar+ssh.

    Converts flat {slug}.html files to {slug}/training-plan/index.html directory
    structure under /race/. Same tar+ssh pattern as sync_pages().
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    plan_path = Path(plan_dir)
    if not plan_path.exists():
        print(f"✗ Prep kit directory not found: {plan_path}")
        return None

    html_files = sorted(plan_path.glob("*.html"))
    if not html_files:
        print(f"✗ No .html files found in {plan_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/race"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        page_count = 0
        for html_file in html_files:
            slug = html_file.stem
            plan_dir_tmp = tmpdir / slug / "training-plan"
            plan_dir_tmp.mkdir(parents=True)
            shutil.copy2(html_file, plan_dir_tmp / "index.html")
            page_count += 1

        print(f"  Uploading {page_count} training-plan pages via tar+ssh...")

        try:
            items = [p.name for p in sorted(tmpdir.iterdir())]
            tar_cmd = ["tar", "-cf", "-", "-C", str(tmpdir)] + items
            ssh_cmd = [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"tar -xf - -C {remote_base}",
            ]

            tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
            ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            tar_proc.stdout.close()
            stdout, stderr = ssh_proc.communicate(timeout=300)

            if ssh_proc.returncode != 0:
                print(f"✗ tar+ssh failed: {stderr.decode().strip()}")
                return None
        except subprocess.TimeoutExpired:
            print("✗ Upload timed out (300s)")
            tar_proc.kill()
            ssh_proc.kill()
            return None
        except Exception as e:
            print(f"✗ Error uploading training-plan pages: {e}")
            return None

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded {page_count} training-plan pages to {wp_url}/race/*/training-plan/")
    return f"{wp_url}/race/"


def sync_tire_pages(tire_pages_dir: str):
    """Deploy /tire/ review + comparison pages from a FRESH staging tree and
    RECONCILE: after upload, remote dirs not present in the staging set are
    deleted. tar+ssh alone only adds — stale trees caused three incidents on
    2026-07-22 (sitemap tires/VS, /blog/, /tire/ fabricated mentions).

    Staging tree layout: {slug}/index.html per page (as emitted by
    generate_tire_pages.py / generate_tire_vs_pages.py --output-dir).
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    src = Path(tire_pages_dir)
    dirs = sorted(d.name for d in src.iterdir()
                  if d.is_dir() and (d / "index.html").exists()) if src.exists() else []
    if not dirs:
        print(f"✗ No page dirs with index.html in {src}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/tire"

    print(f"  Uploading {len(dirs)} /tire/ pages via tar+ssh...")
    try:
        tar_cmd = ["tar", "-cf", "-", "-C", str(src)] + dirs
        ssh_cmd = ["ssh", "-i", str(SSH_KEY), "-p", port, f"{user}@{host}",
                   f"mkdir -p {remote_base} && tar -xf - -C {remote_base}"]
        tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
        ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_proc.stdout.close()
        _, err = ssh_proc.communicate(timeout=300)
        if ssh_proc.returncode != 0:
            print(f"✗ Upload failed: {err.decode().strip()}")
            return None
    except Exception as e:  # noqa: BLE001
        print(f"✗ Upload failed: {e}")
        return None

    # Reconcile: delete remote orphan dirs (bounded to /tire/, name-validated).
    try:
        result = subprocess.run(
            ["ssh", "-i", str(SSH_KEY), "-p", port, f"{user}@{host}",
             f"ls {remote_base}"],
            capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print("  (reconcile skipped: could not list remote /tire/)")
        else:
            import re as _re
            remote = set(result.stdout.split())
            orphans = sorted(d for d in remote - set(dirs)
                             if _re.fullmatch(r"[a-z0-9][a-z0-9-]*", d))
            if orphans:
                # names are regex-validated ([a-z0-9-]) so no quoting needed;
                # quoting the ~-path would suppress tilde expansion and no-op.
                rm_names = " ".join(orphans)
                rm = subprocess.run(
                    ["ssh", "-i", str(SSH_KEY), "-p", port, f"{user}@{host}",
                     f"cd {remote_base} && rm -rf {rm_names} && ls | wc -l"],
                    capture_output=True, text=True, timeout=60)
                if rm.returncode != 0:
                    print(f"✗ Reconcile rm FAILED: {rm.stderr.strip()}")
                else:
                    print(f"  Reconciled: removed {len(orphans)} stale remote dirs "
                          f"(remote now has {rm.stdout.strip()} entries): "
                          f"{' '.join(orphans[:6])}{' …' if len(orphans) > 6 else ''}")
            else:
                print("  Reconciled: no stale remote dirs")
    except Exception as e:  # noqa: BLE001
        print(f"  (reconcile skipped: {e})")

    print(f"✓ Uploaded {len(dirs)} pages to https://gravelgodcycling.com/tire/")
    return len(dirs)


def sync_tire_guides(tire_guide_dir: str):
    """Upload tire guide pages to /race/{slug}/tires/ on SiteGround via tar+ssh.

    Converts flat {slug}.html files to {slug}/tires/index.html directory
    structure under /race/. Same tar+ssh pattern as sync_prep_kits().
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    tg_path = Path(tire_guide_dir)
    if not tg_path.exists():
        print(f"✗ Tire guide directory not found: {tg_path}")
        return None

    html_files = sorted(tg_path.glob("*.html"))
    if not html_files:
        print(f"✗ No .html files found in {tg_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/race"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        page_count = 0
        for html_file in html_files:
            slug = html_file.stem
            tg_dir = tmpdir / slug / "tires"
            tg_dir.mkdir(parents=True)
            shutil.copy2(html_file, tg_dir / "index.html")
            page_count += 1

        print(f"  Uploading {page_count} tire guide pages via tar+ssh...")

        try:
            items = [p.name for p in sorted(tmpdir.iterdir())]
            tar_cmd = ["tar", "-cf", "-", "-C", str(tmpdir)] + items
            ssh_cmd = [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"tar -xf - -C {remote_base}",
            ]

            tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
            ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            tar_proc.stdout.close()
            stdout, stderr = ssh_proc.communicate(timeout=300)

            if ssh_proc.returncode != 0:
                print(f"✗ tar+ssh failed: {stderr.decode().strip()}")
                return None
        except subprocess.TimeoutExpired:
            print("✗ Upload timed out (300s)")
            tar_proc.kill()
            ssh_proc.kill()
            return None
        except Exception as e:
            print(f"✗ Error uploading tire guide pages: {e}")
            return None

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded {page_count} tire guide pages to {wp_url}/race/*/tires/")
    return f"{wp_url}/race/"


def sync_series(series_dir: str):
    """Upload series hub pages to /race/series/{slug}/ on SiteGround via tar+ssh.

    Each series hub is already structured as {slug}/index.html under the
    series output directory. Deploys to /race/series/ on the server.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    series_path = Path(series_dir)
    if not series_path.exists():
        print(f"✗ Series directory not found: {series_path}")
        return None

    # Find all series hub directories with index.html
    series_dirs = sorted([
        d for d in series_path.iterdir()
        if d.is_dir() and (d / "index.html").exists()
    ])
    if not series_dirs:
        print(f"✗ No series hub pages found in {series_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/race/series"

    # Create remote directory with correct permissions
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"mkdir -p {remote_base} && chmod 755 {remote_base}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create remote directory: {e.stderr.strip()}")
        return None

    page_count = len(series_dirs)
    print(f"  Uploading {page_count} series hub pages via tar+ssh...")

    try:
        items = [d.name for d in series_dirs]
        tar_cmd = ["tar", "-cf", "-", "-C", str(series_path)] + items
        ssh_cmd = [
            "ssh", "-i", str(SSH_KEY), "-p", port,
            f"{user}@{host}",
            f"tar -xf - -C {remote_base}",
        ]

        tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
        ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_proc.stdout.close()
        stdout, stderr = ssh_proc.communicate(timeout=300)

        if ssh_proc.returncode != 0:
            print(f"✗ tar+ssh failed: {stderr.decode().strip()}")
            return None
    except subprocess.TimeoutExpired:
        print("✗ Upload timed out (300s)")
        tar_proc.kill()
        ssh_proc.kill()
        return None
    except Exception as e:
        print(f"✗ Error uploading series hub pages: {e}")
        return None

    # Fix permissions
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"chmod 755 {remote_base}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError:
        print("⚠️  Warning: could not fix /race/series/ permissions — verify manually")

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded {page_count} series hub pages to {wp_url}/race/series/")
    return f"{wp_url}/race/series/"


def sync_blog_index(index_page: str, index_json: str):
    """Upload blog index page and JSON to /blog/ on SiteGround via SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    page_path = Path(index_page)
    json_path = Path(index_json)

    if not page_path.exists():
        print(f"✗ Blog index page not found: {page_path}")
        print("  Run: python wordpress/generate_blog_index_page.py first")
        return None
    if not json_path.exists():
        print(f"✗ Blog index JSON not found: {json_path}")
        print("  Run: python scripts/generate_blog_index.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/blog"

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
        print(f"✗ Failed to create /blog/ directory: {e.stderr.strip()}")
        return None

    # Upload index.html
    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(page_path),
                f"{user}@{host}:{remote_base}/index.html",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        print("✓ Uploaded blog index.html")
    except Exception as e:
        print(f"✗ SCP failed for blog index.html: {e}")
        return None

    # Upload blog-index.json
    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(json_path),
                f"{user}@{host}:{remote_base}/blog-index.json",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        print("✓ Uploaded blog-index.json")
    except Exception as e:
        print(f"✗ SCP failed for blog-index.json: {e}")
        return None

    # Fix permissions
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"chmod 755 {remote_base}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        pass  # Non-critical

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Blog index live at {wp_url}/blog/")
    return f"{wp_url}/blog/"


def sync_blog(blog_dir: str):
    """Upload blog preview pages to /blog/{slug}/ on SiteGround via tar+ssh.

    Converts flat {slug}.html files to {slug}/index.html directory
    structure under /blog/. Same tar+ssh pattern as sync_prep_kits().
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    blog_path = Path(blog_dir)
    if not blog_path.exists():
        print(f"✗ Blog directory not found: {blog_path}")
        return None

    html_files = sorted(blog_path.glob("*.html"))
    if not html_files:
        print(f"✗ No .html files found in {blog_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/blog"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        page_count = 0
        for html_file in html_files:
            slug = html_file.stem
            slug_dir = tmpdir / slug
            slug_dir.mkdir(parents=True)
            shutil.copy2(html_file, slug_dir / "index.html")
            page_count += 1

        print(f"  Uploading {page_count} blog pages via tar+ssh...")

        try:
            items = [p.name for p in sorted(tmpdir.iterdir())]
            tar_cmd = ["tar", "-cf", "-", "-C", str(tmpdir)] + items
            ssh_cmd = [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"mkdir -p {remote_base} && tar -xf - -C {remote_base} && chmod 755 {remote_base}",
            ]

            tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
            ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            tar_proc.stdout.close()
            stdout, stderr = ssh_proc.communicate(timeout=300)

            if ssh_proc.returncode != 0:
                print(f"✗ tar+ssh failed: {stderr.decode().strip()}")
                return None
        except subprocess.TimeoutExpired:
            print("✗ Upload timed out (300s)")
            tar_proc.kill()
            ssh_proc.kill()
            return None
        except Exception as e:
            print(f"✗ Error uploading blog pages: {e}")
            return None

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded {page_count} blog pages to {wp_url}/blog/")
    return f"{wp_url}/blog/"


def sync_courses(course_dir: str):
    """Upload course pages to /course/ on SiteGround via tar+ssh.

    Course output is already structured as:
      course/index.html                            (course index)
      course/{slug}/index.html                     (landing page)
      course/{slug}/lesson/{lesson-id}/index.html  (lesson pages)

    Deploys entire directory tree to /course/ on the server.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    course_path = Path(course_dir)
    if not course_path.exists():
        print(f"✗ Course directory not found: {course_path}")
        return None

    # Count pages
    html_files = list(course_path.rglob("index.html"))
    if not html_files:
        print(f"✗ No index.html files found in {course_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/course"

    # Create remote directory with correct permissions
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"mkdir -p {remote_base}",
            ],
            check=True, capture_output=True, text=True, timeout=15,
        )
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create remote directory: {e.stderr.strip()}")
        return None

    print(f"  Uploading {len(html_files)} course pages via tar+ssh...")

    try:
        items = [p.name for p in sorted(course_path.iterdir())]
        tar_cmd = ["tar", "-cf", "-", "-C", str(course_path)] + items
        ssh_cmd = [
            "ssh", "-i", str(SSH_KEY), "-p", port,
            f"{user}@{host}",
            f"tar -xf - -C {remote_base} && find {remote_base} -type d -exec chmod 755 {{}} \\;",
        ]

        tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
        ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_proc.stdout.close()
        stdout, stderr = ssh_proc.communicate(timeout=300)

        if ssh_proc.returncode != 0:
            print(f"✗ tar+ssh failed: {stderr.decode().strip()}")
            return None
    except subprocess.TimeoutExpired:
        print("✗ Upload timed out (300s)")
        tar_proc.kill()
        ssh_proc.kill()
        return None
    except Exception as e:
        print(f"✗ Error uploading course pages: {e}")
        return None

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded {len(html_files)} course pages to {wp_url}/course/")
    return f"{wp_url}/course/"


def sync_mission_control(mc_file: str):
    """Upload mission-control/index.html to /mission-control/ on SiteGround via SSH+SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    html_path = Path(mc_file)
    if not html_path.exists():
        print(f"✗ Mission Control HTML not found: {html_path}")
        print("  Run: python3 wordpress/generate_mission_control.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/mission-control"

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

    # Upload mission-control/index.html
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
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for mission control: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading mission control: {e}")
        return None

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded mission control: {wp_url}/mission-control/")
    return f"{wp_url}/mission-control/"


def sync_insights(insights_file: str):
    """Upload insights.html to /insights/index.html on SiteGround via SSH+SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    html_path = Path(insights_file)
    if not html_path.exists():
        print(f"✗ Insights page HTML not found: {html_path}")
        print("  Run: python3 wordpress/generate_insights.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/insights"

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

    # Upload insights.html as index.html
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
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for insights page: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading insights page: {e}")
        return None

    # Upload shared CSS/JS assets (insights page references them via /race/assets/)
    assets_dir = html_path.parent / "assets"
    remote_assets = "~/www/gravelgodcycling.com/public_html/race/assets"
    for pattern in ("gg-styles.*.css", "gg-scripts.*.js"):
        for asset in assets_dir.glob(pattern):
            try:
                subprocess.run(
                    [
                        "scp", "-i", str(SSH_KEY), "-P", port,
                        str(asset),
                        f"{user}@{host}:{remote_assets}/{asset.name}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError:
                pass  # Asset may already exist

    # Fix permissions
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"chmod 755 {remote_base} && chmod 644 {remote_base}/index.html",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError:
        pass

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded insights page: {wp_url}/insights/")
    return f"{wp_url}/insights/"


def sync_whitepaper(whitepaper_file: str):
    """Upload whitepaper-fueling.html to /fueling-methodology/index.html on SiteGround via SSH+SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    html_path = Path(whitepaper_file)
    if not html_path.exists():
        print(f"✗ White paper HTML not found: {html_path}")
        print("  Run: python3 wordpress/generate_whitepaper_fueling.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/fueling-methodology"

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

    # Upload whitepaper-fueling.html as index.html
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
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for white paper page: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading white paper page: {e}")
        return None

    # Upload shared CSS/JS assets (white paper page references them via /race/assets/)
    assets_dir = html_path.parent / "assets"
    remote_assets = "~/www/gravelgodcycling.com/public_html/race/assets"
    for pattern in ("gg-styles.*.css", "gg-scripts.*.js"):
        for asset in assets_dir.glob(pattern):
            try:
                subprocess.run(
                    [
                        "scp", "-i", str(SSH_KEY), "-P", port,
                        str(asset),
                        f"{user}@{host}:{remote_assets}/{asset.name}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError as e:
                print(f"⚠ Asset upload skipped ({asset.name}): {e}")

    # Fix permissions
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"chmod 755 {remote_base} && chmod 644 {remote_base}/index.html",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError as e:
        print(f"⚠ Permission fix failed: {e}")

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded white paper page: {wp_url}/fueling-methodology/")
    return f"{wp_url}/fueling-methodology/"


def sync_embed():
    """Upload embed widget files (JS, data JSON, demo) to /embed/ on SiteGround via SSH+SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    embed_dir = Path("web/embed")
    if not embed_dir.exists():
        print(f"✗ Embed directory not found: {embed_dir}")
        print("  Run: python3 scripts/generate_embed_widget.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/embed"

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

    # Upload all embed files
    files = list(embed_dir.glob("*"))
    for fpath in files:
        if fpath.is_file():
            try:
                subprocess.run(
                    [
                        "scp", "-i", str(SSH_KEY), "-P", port,
                        str(fpath),
                        f"{user}@{host}:{remote_base}/{fpath.name}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                print(f"✓ Uploaded embed: /embed/{fpath.name}")
            except subprocess.CalledProcessError as e:
                print(f"✗ SCP failed for {fpath.name}: {e.stderr.strip()}")
            except Exception as e:
                print(f"✗ Error uploading {fpath.name}: {e}")

    # Fix permissions
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"chmod 755 {remote_base} && chmod 644 {remote_base}/*",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError:
        pass

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Embed widget deployed: {wp_url}/embed/demo.html")
    return f"{wp_url}/embed/"


def sync_rss():
    """Upload RSS feed to /feed/ on SiteGround via SSH+SCP."""
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    feed_file = Path("web/feed/races.xml")
    if not feed_file.exists():
        print(f"✗ RSS feed not found: {feed_file}")
        print("  Run: python3 scripts/generate_rss_feed.py first")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/feed"

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

    # Upload RSS feed
    try:
        subprocess.run(
            [
                "scp", "-i", str(SSH_KEY), "-P", port,
                str(feed_file),
                f"{user}@{host}:{remote_base}/races.xml",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.CalledProcessError as e:
        print(f"✗ SCP failed for RSS feed: {e.stderr.strip()}")
        return None
    except Exception as e:
        print(f"✗ Error uploading RSS feed: {e}")
        return None

    # Fix permissions
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"chmod 755 {remote_base} && chmod 644 {remote_base}/races.xml",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError:
        pass

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ RSS feed deployed: {wp_url}/feed/races.xml")
    return f"{wp_url}/feed/races.xml"


def sync_llms_txt():
    """Regenerate then upload llms.txt, llms-full.txt, the llms-repo.txt
    AIOSEO-override copy, and the IndexNow key file to site root on
    SiteGround via SCP.

    Regenerating here (rather than trusting whatever's on disk) keeps the
    "Last generated" date in llms.txt at deploy time instead of going stale
    between manual `generate_llms_txt.py` runs.

    llms-repo.txt is a second copy of llms.txt's content uploaded under a
    filename AIOSEO doesn't touch. All in One SEO v4.9 writes its own
    physical llms.txt to this same webroot path on its own schedule,
    clobbering ours in a last-write-wins race — the .htaccess rule added by
    sync_redirects() (REDIRECT_BLOCK) rewrites public /llms.txt requests to
    /llms-repo.txt so our content wins regardless of which file was written
    most recently.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    try:
        subprocess.run(
            [sys.executable, "scripts/generate_llms_txt.py"],
            check=True, capture_output=True, text=True, timeout=60,
        )
        print("  Regenerated llms.txt + llms-full.txt")
    except subprocess.CalledProcessError as e:
        print(f"⚠ llms.txt regeneration failed, uploading existing files: {e.stderr.strip()}")
    except Exception as e:
        print(f"⚠ llms.txt regeneration failed, uploading existing files: {e}")

    remote_base = "~/www/gravelgodcycling.com/public_html"
    uploaded = 0

    # (local_filename, remote_filename) — llms-repo.txt is llms.txt's content
    # uploaded a second time under the AIOSEO-immune filename (see docstring).
    uploads = [("llms.txt", "llms.txt"), ("llms-full.txt", "llms-full.txt"), ("llms.txt", "llms-repo.txt")]
    filenames = [remote for _, remote in uploads]
    try:
        import indexnow_ping
        key_filename = f"{indexnow_ping.INDEXNOW_KEY}.txt"
        key_path = Path("web") / key_filename
        if key_path.exists():
            uploads.append((key_filename, key_filename))
            filenames.append(key_filename)
        else:
            print(f"⚠ IndexNow key file not found, skipping: {key_path}")
    except Exception as e:
        print(f"⚠ Could not resolve IndexNow key filename, skipping: {e}")

    for local_filename, remote_filename in uploads:
        local_path = Path("web") / local_filename
        if not local_path.exists():
            print(f"✗ {local_filename} not found: {local_path}")
            if local_filename in ("llms.txt", "llms-full.txt"):
                print(f"  Run: python3 scripts/generate_llms_txt.py first")
            continue

        try:
            subprocess.run(
                [
                    "scp", "-i", str(SSH_KEY), "-P", port,
                    str(local_path),
                    f"{user}@{host}:{remote_base}/{remote_filename}",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            uploaded += 1
        except subprocess.CalledProcessError as e:
            print(f"✗ SCP failed for {remote_filename}: {e.stderr.strip()}")
        except Exception as e:
            print(f"✗ Error uploading {remote_filename}: {e}")

    # Fix permissions (only the files this function targets, not the whole root)
    remote_targets = " ".join(f"{remote_base}/{f}" for f in filenames)
    try:
        subprocess.run(
            [
                "ssh", "-i", str(SSH_KEY), "-p", port,
                f"{user}@{host}",
                f"chmod 644 {remote_targets} 2>/dev/null",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.CalledProcessError:
        pass

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded {uploaded} text files to {wp_url}/")
    return f"{wp_url}/llms.txt"


def sync_markdown(markdown_dir: str):
    """Upload markdown race profiles to /race/{slug}.md on SiteGround via tar+ssh.

    Files are already named {slug}.md in markdown_dir, so they upload as flat
    files straight into the existing /race/ directory tree (alongside the
    {slug}/ page directories) — this is what makes them resolvable at
    https://gravelgodcycling.com/race/{slug}.md.

    Returns the list of uploaded .md URLs on success (for IndexNow pinging),
    or None on failure.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    md_path = Path(markdown_dir)
    if not md_path.exists():
        print(f"✗ Markdown directory not found: {md_path}")
        print("  Run: python3 scripts/generate_markdown_profiles.py first")
        return None

    md_files = sorted(md_path.glob("*.md"))
    if not md_files:
        print(f"✗ No .md files found in {md_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/race"

    print(f"  Uploading {len(md_files)} markdown profiles via tar+ssh...")

    try:
        items = [f.name for f in md_files]
        tar_cmd = ["tar", "-cf", "-", "-C", str(md_path)] + items
        ssh_cmd = [
            "ssh", "-i", str(SSH_KEY), "-p", port,
            f"{user}@{host}",
            f"tar -xf - -C {remote_base}",
        ]

        tar_proc = subprocess.Popen(tar_cmd, stdout=subprocess.PIPE)
        ssh_proc = subprocess.Popen(ssh_cmd, stdin=tar_proc.stdout,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tar_proc.stdout.close()
        stdout, stderr = ssh_proc.communicate(timeout=300)

        if ssh_proc.returncode != 0:
            print(f"✗ tar+ssh failed: {stderr.decode().strip()}")
            return None
    except subprocess.TimeoutExpired:
        print("✗ Upload timed out (300s)")
        tar_proc.kill()
        ssh_proc.kill()
        return None
    except Exception as e:
        print(f"✗ Error uploading markdown profiles: {e}")
        return None

    wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
    print(f"✓ Uploaded {len(md_files)} markdown profiles to {wp_url}/race/*.md")
    return [f"{wp_url}/race/{f.stem}.md" for f in md_files]


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
        help="Upload training guide (monolith) to /guide/ via SCP"
    )
    parser.add_argument(
        "--guide-dir", default="wordpress/output",
        help="Path to guide output directory (default: wordpress/output)"
    )
    parser.add_argument(
        "--sync-guide-cluster", action="store_true",
        help="Upload guide cluster pages (pillar + 8 chapters) to /guide/ via tar+ssh"
    )
    parser.add_argument(
        "--guide-cluster-dir", default="wordpress/output/guide",
        help="Path to guide cluster directory (default: wordpress/output/guide)"
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
        "--sync-tp", action="store_true",
        help="Upload TP-listing images (header + includes-grid) to /tp/ via tar+ssh"
    )
    parser.add_argument(
        "--tp-dir", default="wordpress/output/tp",
        help="Path to TP-listing image directory (default: wordpress/output/tp)"
    )
    parser.add_argument(
        "--sync-gravel-tv", action="store_true",
        help="Upload gravel-tv.html to /gravel-tv/ via SCP"
    )
    parser.add_argument(
        "--sync-homepage", action="store_true",
        help="Upload homepage to /homepage/ via SCP"
    )
    parser.add_argument(
        "--homepage-file", default="wordpress/output/homepage.html",
        help="Path to homepage HTML (default: wordpress/output/homepage.html)"
    )
    parser.add_argument(
        "--sync-about", action="store_true",
        help="Upload about page to /about/ via SCP"
    )
    parser.add_argument(
        "--about-file", default="wordpress/output/about.html",
        help="Path to about page HTML (default: wordpress/output/about.html)"
    )
    parser.add_argument(
        "--sync-coaching", action="store_true",
        help="Upload coaching page to /coaching/ via SCP"
    )
    parser.add_argument(
        "--coaching-file", default="wordpress/output/coaching.html",
        help="Path to coaching page HTML (default: wordpress/output/coaching.html)"
    )
    parser.add_argument(
        "--sync-coaching-apply", action="store_true",
        help="Upload coaching apply page to /coaching/apply/ via SCP"
    )
    parser.add_argument(
        "--coaching-apply-file", default="wordpress/output/coaching-apply.html",
        help="Path to coaching apply HTML (default: wordpress/output/coaching-apply.html)"
    )
    parser.add_argument(
        "--sync-consulting", action="store_true",
        help="Upload consulting page to /consulting/ via SCP"
    )
    parser.add_argument(
        "--consulting-file", default="wordpress/output/consulting.html",
        help="Path to consulting page HTML (default: wordpress/output/consulting.html)"
    )
    parser.add_argument(
        "--sync-legal", action="store_true",
        help="Upload legal pages (privacy, terms, cookies) via SCP"
    )
    parser.add_argument(
        "--sync-consent", action="store_true",
        help="Upload cookie consent mu-plugin to WordPress"
    )
    parser.add_argument(
        "--sync-insights", action="store_true",
        help="Upload insights page to /insights/ via SCP"
    )
    parser.add_argument(
        "--insights-file", default="wordpress/output/insights.html",
        help="Path to insights page HTML (default: wordpress/output/insights.html)"
    )
    parser.add_argument(
        "--sync-whitepaper", action="store_true",
        help="Upload white paper page to /fueling-methodology/ via SCP"
    )
    parser.add_argument(
        "--whitepaper-file", default="wordpress/output/whitepaper-fueling.html",
        help="Path to white paper HTML (default: wordpress/output/whitepaper-fueling.html)"
    )
    parser.add_argument(
        "--sync-training-plans", action="store_true",
        help="Upload training plans page to /products/training-plans/ via SCP"
    )
    parser.add_argument(
        "--training-plans-file", default="wordpress/output/training-plans/index.html",
        help="Path to training plans page HTML (default: wordpress/output/training-plans/index.html)"
    )
    parser.add_argument(
        "--sync-success", action="store_true",
        help="Upload success pages (training-plans/success, coaching/welcome, consulting/confirmed)"
    )
    parser.add_argument(
        "--success-dir", default="wordpress/output",
        help="Path to success pages output directory (default: wordpress/output)"
    )
    parser.add_argument(
        "--sync-pages", action="store_true",
        help="Upload race pages to /race/ via tar+ssh (with correct permissions)"
    )
    parser.add_argument(
        "--pages-dir", default="wordpress/output",
        help="Path to race pages directory (default: wordpress/output)"
    )
    parser.add_argument(
        "--sync-sitemap", action="store_true",
        help="Deploy race-sitemap.xml + sitemap index to server"
    )
    parser.add_argument(
        "--sync-redirects", action="store_true",
        help="Deploy redirect rules to .htaccess"
    )
    parser.add_argument(
        "--sync-noindex", action="store_true",
        help="Deploy noindex mu-plugin to wp-content/mu-plugins/"
    )
    parser.add_argument(
        "--sync-ctas", action="store_true",
        help="Deploy race CTA mu-plugin to wp-content/mu-plugins/"
    )
    parser.add_argument(
        "--sync-training-form", action="store_true",
        help="Deploy training-form mu-plugin (questionnaire JS loader) to wp-content/mu-plugins/"
    )
    parser.add_argument(
        "--sync-ga4", action="store_true",
        help="Deploy GA4 analytics mu-plugin to wp-content/mu-plugins/"
    )
    parser.add_argument(
        "--sync-header", action="store_true",
        help="Deploy shared header mu-plugin to wp-content/mu-plugins/"
    )
    parser.add_argument(
        "--sync-photos", action="store_true",
        help="Upload race photos to /race-photos/ via tar+ssh"
    )
    parser.add_argument(
        "--photos-dir", default="race-photos",
        help="Path to race photos directory (default: race-photos)"
    )
    parser.add_argument(
        "--sync-prep-kits", action="store_true",
        help="Upload prep kit pages to /race/{slug}/prep-kit/ via tar+ssh"
    )
    parser.add_argument(
        "--sync-plan-pages", action="store_true",
        help="Upload training-plan pages to /race/{slug}/training-plan/ via tar+ssh"
    )
    parser.add_argument(
        "--prep-kit-dir", default="wordpress/output/prep-kit",
        help="Path to prep kit directory (default: wordpress/output/prep-kit)"
    )
    parser.add_argument(
        "--plan-dir", default="wordpress/output/training-plan",
        help="Path to training-plan pages dir (default: wordpress/output/training-plan)"
    )
    parser.add_argument(
        "--sync-tire-pages", action="store_true",
        help="Deploy /tire/ review+comparison pages from --tire-pages-dir (fresh staging) with remote reconcile")
    parser.add_argument(
        "--tire-pages-dir", default=None,
        help="Fresh staging dir of {slug}/index.html trees for --sync-tire-pages")
    parser.add_argument(
        "--sync-tire-guides", action="store_true",
        help="Upload tire guide pages to /race/{slug}/tires/ via tar+ssh"
    )
    parser.add_argument(
        "--tire-guide-dir", default="wordpress/output/tires",
        help="Path to tire guide directory (default: wordpress/output/tires)"
    )
    parser.add_argument(
        "--sync-series", action="store_true",
        help="Upload series hub pages to /race/series/{slug}/ via tar+ssh"
    )
    parser.add_argument(
        "--series-dir", default="wordpress/output/race/series",
        help="Path to series hub directory (default: wordpress/output/race/series)"
    )
    parser.add_argument(
        "--sync-blog", action="store_true",
        help="Upload blog preview pages to /blog/{slug}/ via tar+ssh"
    )
    parser.add_argument(
        "--blog-dir", default="wordpress/output/blog",
        help="Path to blog directory (default: wordpress/output/blog)"
    )
    parser.add_argument(
        "--sync-blog-index", action="store_true",
        help="Upload blog index page + JSON to /blog/ via SCP"
    )
    parser.add_argument(
        "--blog-index-page", default="wordpress/output/blog-index.html",
        help="Path to blog index HTML (default: wordpress/output/blog-index.html)"
    )
    parser.add_argument(
        "--blog-index-json", default="web/blog-index.json",
        help="Path to blog index JSON (default: web/blog-index.json)"
    )
    parser.add_argument(
        "--sync-courses", action="store_true",
        help="Upload course pages to /course/ via tar+ssh"
    )
    parser.add_argument(
        "--course-dir", default="wordpress/output/course",
        help="Path to course output directory (default: wordpress/output/course)"
    )
    parser.add_argument(
        "--sync-embed", action="store_true",
        help="Upload embed widget files (JS, data JSON, demo) to /embed/"
    )
    parser.add_argument(
        "--sync-rss", action="store_true",
        help="Upload RSS feed to /feed/"
    )
    parser.add_argument(
        "--sync-llms-txt", action="store_true",
        help="Upload llms.txt + llms-full.txt to site root"
    )
    parser.add_argument(
        "--sync-markdown", action="store_true",
        help="Upload markdown race profiles to /race/{slug}.md via tar+ssh"
    )
    parser.add_argument(
        "--markdown-dir", default="web/markdown",
        help="Path to markdown profiles directory (default: web/markdown)"
    )
    parser.add_argument(
        "--ping-indexnow", action="store_true",
        help="After a successful --sync-markdown, POST the synced .md URLs to IndexNow "
             "(never fails the deploy — a ping failure only prints a warning)"
    )
    parser.add_argument(
        "--sync-meta-descriptions", action="store_true",
        help="Deploy meta description mu-plugin + JSON data to WordPress"
    )
    parser.add_argument(
        "--sync-ab", action="store_true",
        help="Deploy A/B test assets (JS, config, mu-plugin) to /ab/"
    )
    parser.add_argument(
        "--sync-mission-control", action="store_true",
        help="Upload mission control dashboard to /mission-control/ via SCP"
    )
    parser.add_argument(
        "--mission-control-file",
        default="wordpress/output/mission-control/index.html",
        help="Path to mission control HTML (default: wordpress/output/mission-control/index.html)"
    )
    parser.add_argument(
        "--purge-cache", action="store_true",
        help="Purge all SiteGround caches (static, dynamic, memcached, opcache)"
    )
    parser.add_argument(
        "--deploy-content", action="store_true",
        help="Shortcut: --sync-pages --sync-index --sync-widget --purge-cache"
    )
    parser.add_argument(
        "--deploy-all", action="store_true",
        help="Shortcut: all --sync-* flags + --purge-cache"
    )
    args = parser.parse_args()

    # Expand composite flags
    if args.deploy_content:
        args.sync_pages = True
        args.sync_index = True
        args.sync_widget = True
        args.sync_llms_txt = True
        args.sync_markdown = True
        args.purge_cache = True
    if args.deploy_all:
        args.sync_pages = True
        args.sync_index = True
        args.sync_widget = True
        args.sync_og = True
        args.sync_tp = True
        args.sync_homepage = True
        args.sync_about = True
        args.sync_coaching = True
        args.sync_coaching_apply = True
        args.sync_consulting = True
        args.sync_training_plans = True
        args.sync_success = True
        args.sync_sitemap = True
        args.sync_redirects = True
        args.sync_noindex = True
        args.sync_ctas = True
        args.sync_training_form = True
        args.sync_ga4 = True
        args.sync_prep_kits = True
        args.sync_tire_guides = True
        args.sync_series = True
        args.sync_blog = True
        args.sync_blog_index = True
        args.sync_photos = True
        args.sync_ab = True
        args.sync_header = True
        args.sync_courses = True
        args.sync_meta_descriptions = True
        args.sync_insights = True
        args.sync_whitepaper = True
        args.sync_embed = True
        args.sync_rss = True
        args.sync_llms_txt = True
        args.sync_markdown = True
        args.sync_guide_cluster = True
        args.sync_legal = True
        args.sync_consent = True
        args.purge_cache = True

    has_action = any([args.json, args.sync_index, args.sync_widget, args.sync_training,
                      args.sync_guide, args.sync_guide_cluster, args.sync_og, args.sync_tp, args.sync_homepage, args.sync_gravel_tv, args.sync_about,
                      args.sync_coaching, args.sync_coaching_apply, args.sync_consulting,
                      args.sync_training_plans, args.sync_success, args.sync_pages,
                      args.sync_sitemap, args.sync_redirects,
                      args.sync_noindex, args.sync_ctas, args.sync_training_form, args.sync_ga4, args.sync_header, args.sync_prep_kits, args.sync_plan_pages, args.sync_tire_guides,
                      args.sync_series, args.sync_blog,
                      args.sync_blog_index, args.sync_photos, args.sync_ab, args.sync_courses,
                      args.sync_meta_descriptions, args.sync_mission_control,
                      args.sync_insights, args.sync_whitepaper, args.sync_embed, args.sync_rss,
                      args.sync_llms_txt, args.sync_markdown, args.ping_indexnow,
                      args.purge_cache])
    if not has_action:
        parser.error("Provide a sync flag (--sync-pages, --sync-index, etc.), --deploy-content, or --deploy-all")

    # Any sync returning falsy marks the whole run failed — a deploy that
    # half-happens must exit non-zero so CI cannot report silent success.
    _failures: list = []

    def _run(name, fn, *fn_args):
        if fn(*fn_args) is False:
            _failures.append(name)

    if args.json:
        _run("json", push_to_wordpress, args.json)
    if args.sync_index:
        _run("sync-index", sync_index, args.index_file)
    if args.sync_widget:
        _run("sync-widget", sync_widget, args.widget_file)
    if args.sync_training:
        _run("sync-training", sync_training, args.training_file)
    if args.sync_guide:
        _run("sync-guide", sync_guide, args.guide_dir)
    if args.sync_guide_cluster:
        _run("sync-guide-cluster", sync_guide_cluster, args.guide_cluster_dir)
    if args.sync_og:
        _run("sync-og", sync_og, args.og_dir)
    if args.sync_tp:
        _run("sync-tp", sync_tp, args.tp_dir)
    if args.sync_homepage:
        _run("sync-homepage", sync_homepage, args.homepage_file)
    if args.sync_gravel_tv:
        _run("sync-gravel-tv", sync_gravel_tv, "wordpress/output/gravel-tv.html")
    if args.sync_about:
        _run("sync-about", sync_about, args.about_file)
    if args.sync_coaching:
        _run("sync-coaching", sync_coaching, args.coaching_file)
    if args.sync_coaching_apply:
        _run("sync-coaching-apply", sync_coaching_apply, args.coaching_apply_file)
    if args.sync_consulting:
        _run("sync-consulting", sync_consulting, args.consulting_file)
    if args.sync_legal:
        _run("sync-legal", sync_legal, "wordpress/output")
    if args.sync_consent:
        _run("sync-consent", sync_consent)
    if args.sync_training_plans:
        _run("sync-training-plans", sync_training_plans, args.training_plans_file)
    if args.sync_success:
        _run("sync-success", sync_success, args.success_dir)
    if args.sync_pages:
        _run("sync-pages", sync_pages, args.pages_dir)
    if args.sync_sitemap:
        _run("sync-sitemap", sync_sitemap)
    if args.sync_redirects:
        _run("sync-redirects", sync_redirects)
    if args.sync_noindex:
        _run("sync-noindex", sync_noindex)
    if args.sync_ctas:
        _run("sync-ctas", sync_ctas)
    if args.sync_training_form:
        _run("sync-training-form", sync_training_form)
    if args.sync_ga4:
        _run("sync-ga4", sync_ga4)
    if args.sync_header:
        _run("sync-header", sync_header)
    if args.sync_photos:
        _run("sync-photos", sync_photos, args.photos_dir)
    if args.sync_prep_kits:
        _run("sync-prep-kits", sync_prep_kits, args.prep_kit_dir)
    if args.sync_plan_pages:
        _run("sync-plan-pages", sync_plan_pages, args.plan_dir)
    if args.sync_tire_guides:
        _run("sync-tire-guides", sync_tire_guides, args.tire_guide_dir)
    if args.sync_tire_pages:
        if not args.tire_pages_dir:
            print("✗ --sync-tire-pages requires --tire-pages-dir (fresh staging tree)")
        else:
            _run("sync-tire-pages", sync_tire_pages, args.tire_pages_dir)
    if args.sync_series:
        _run("sync-series", sync_series, args.series_dir)
    if args.sync_blog:
        _run("sync-blog", sync_blog, args.blog_dir)
    if args.sync_blog_index:
        _run("sync-blog-index", sync_blog_index, args.blog_index_page, args.blog_index_json)
    if args.sync_ab:
        _run("sync-ab", sync_ab)
    if args.sync_meta_descriptions:
        _run("sync-meta-descriptions", sync_meta_descriptions)
    if args.sync_courses:
        _run("sync-courses", sync_courses, args.course_dir)
    if args.sync_mission_control:
        _run("sync-mission-control", sync_mission_control, args.mission_control_file)
    if args.sync_insights:
        _run("sync-insights", sync_insights, args.insights_file)
    if args.sync_whitepaper:
        _run("sync-whitepaper", sync_whitepaper, args.whitepaper_file)
    if args.sync_embed:
        _run("sync-embed", sync_embed)
    if args.sync_rss:
        _run("sync-rss", sync_rss)
    if args.sync_llms_txt:
        _run("sync-llms-txt", sync_llms_txt)
    synced_markdown_urls = None
    if args.sync_markdown:
        synced_markdown_urls = sync_markdown(args.markdown_dir)
        if synced_markdown_urls is False:
            _failures.append("sync-markdown")
    if args.ping_indexnow:
        if synced_markdown_urls:
            try:
                import indexnow_ping
                indexnow_ping.ping(synced_markdown_urls)
            except Exception as e:
                print(f"⚠ IndexNow ping failed (non-fatal): {e}")
        else:
            print("⚠ --ping-indexnow had no synced URLs to ping (did --sync-markdown succeed?)")
    if args.purge_cache:
        _run("purge-cache", purge_cache)

    if _failures:
        print(f"\n✗ DEPLOY FAILED — {len(_failures)} step(s): {', '.join(_failures)}")
        sys.exit(1)
