#!/usr/bin/env python3
"""
Push landing page JSON or race index to WordPress.
"""

import argparse
import json
import os
import shutil
import subprocess
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

    html_files = sorted(pages_path.glob("*.html"))
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

# /page/N/ → / (homepage pagination is meaningless, prevents noindex gap)
RewriteRule ^page/\\d+/?$ / [R=301,L]

# /guide.html → /guide/ (old URL from search engines / bookmarks)
RewriteRule ^guide\\.html$ /guide/ [R=301,L]

# /race/ directory index → search page (prevents 403)
RewriteRule ^race/?$ /gravel-races/ [R=301,L]

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

# Broken URL from GSC → parent page (404 fix)
RewriteRule ^training-plans-faq/gravelgodcoaching@gmail\\.com$ /training-plans-faq/ [R=301,L]
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
    except Exception as e:
        print(f"✗ Failed to read remote .htaccess: {e}")
        return False

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
        print("  5 utility redirects + 27 duplicate content redirects (301)")
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
        print("✓ Deployed sitemap index (sitemap.xml)")
        print("  → race-sitemap.xml (328 race pages)")
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
    parser.add_argument(
        "--sync-about", action="store_true",
        help="Upload about page to /about/ via SCP"
    )
    parser.add_argument(
        "--about-file", default="wordpress/output/about.html",
        help="Path to about page HTML (default: wordpress/output/about.html)"
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
        "--sync-ga4", action="store_true",
        help="Deploy GA4 analytics mu-plugin to wp-content/mu-plugins/"
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
        "--prep-kit-dir", default="wordpress/output/prep-kit",
        help="Path to prep kit directory (default: wordpress/output/prep-kit)"
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
        "--sync-ab", action="store_true",
        help="Deploy A/B test assets (JS, config, mu-plugin) to /ab/"
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
        args.purge_cache = True
    if args.deploy_all:
        args.sync_pages = True
        args.sync_index = True
        args.sync_widget = True
        args.sync_og = True
        args.sync_homepage = True
        args.sync_about = True
        args.sync_sitemap = True
        args.sync_redirects = True
        args.sync_noindex = True
        args.sync_ctas = True
        args.sync_ga4 = True
        args.sync_prep_kits = True
        args.sync_series = True
        args.sync_blog = True
        args.sync_blog_index = True
        args.sync_photos = True
        args.sync_ab = True
        args.purge_cache = True

    has_action = any([args.json, args.sync_index, args.sync_widget, args.sync_training,
                      args.sync_guide, args.sync_og, args.sync_homepage, args.sync_about, args.sync_pages,
                      args.sync_sitemap, args.sync_redirects,
                      args.sync_noindex, args.sync_ctas, args.sync_ga4, args.sync_prep_kits,
                      args.sync_series, args.sync_blog,
                      args.sync_blog_index, args.sync_photos, args.sync_ab, args.purge_cache])
    if not has_action:
        parser.error("Provide a sync flag (--sync-pages, --sync-index, etc.), --deploy-content, or --deploy-all")

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
    if args.sync_about:
        sync_about(args.about_file)
    if args.sync_pages:
        sync_pages(args.pages_dir)
    if args.sync_sitemap:
        sync_sitemap()
    if args.sync_redirects:
        sync_redirects()
    if args.sync_noindex:
        sync_noindex()
    if args.sync_ctas:
        sync_ctas()
    if args.sync_ga4:
        sync_ga4()
    if args.sync_photos:
        sync_photos(args.photos_dir)
    if args.sync_prep_kits:
        sync_prep_kits(args.prep_kit_dir)
    if args.sync_series:
        sync_series(args.series_dir)
    if args.sync_blog:
        sync_blog(args.blog_dir)
    if args.sync_blog_index:
        sync_blog_index(args.blog_index_page, args.blog_index_json)
    if args.sync_ab:
        sync_ab()
    if args.purge_cache:
        purge_cache()
