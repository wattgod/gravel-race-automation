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
    if not html_files:
        print(f"✗ No .html files found in {pages_path}")
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

        # Also include pre-built subdirectories (e.g., tier-1/, tier-2/)
        for subdir in sorted(pages_path.iterdir()):
            if subdir.is_dir() and (subdir / "index.html").exists() and subdir.name != "assets":
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

# /guide.html → /guide/ (old URL from search engines / bookmarks)
RewriteRule ^guide\\.html$ /guide/ [R=301,L]

# /homepage/ → / (duplicate of WP homepage, splits SEO)
RewriteRule ^homepage/?$ / [R=301,L]

# /homepage/index.html → / (direct file access)
RewriteRule ^homepage/index\\.html$ / [R=301,L]

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

    # 2. Create sitemap index referencing all sub-sitemaps
    sitemap_index = f"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://gravelgodcycling.com/race-sitemap.xml</loc>
    <lastmod>{today}</lastmod>
  </sitemap>
  <sitemap>
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
    """Upload race photos to /photos/ on SiteGround via tar+ssh pipe.

    Syncs *.jpg files. Uses tar pipe for efficiency — up to 984 files.
    """
    ssh = get_ssh_credentials()
    if not ssh:
        return None
    host, user, port = ssh

    photos_path = Path(photos_dir)
    if not photos_path.exists():
        print(f"✗ Photos directory not found: {photos_path}")
        return None

    jpg_files = list(photos_path.glob("*.jpg"))
    if not jpg_files:
        print(f"✗ No .jpg files found in {photos_path}")
        return None

    remote_base = "~/www/gravelgodcycling.com/public_html/photos"

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

    # tar+ssh pipe
    filenames = [f.name for f in jpg_files]
    print(f"  Uploading {len(filenames)} race photos via tar+ssh...")

    try:
        tar_cmd = ["tar", "-cf", "-", "-C", str(photos_path)] + filenames
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

        wp_url = os.environ.get("WP_URL", "https://gravelgodcycling.com")
        print(f"✓ Uploaded {len(filenames)} race photos to {wp_url}/photos/")
        return f"{wp_url}/photos/"
    except subprocess.TimeoutExpired:
        print("✗ Upload timed out (300s)")
        tar_proc.kill()
        ssh_proc.kill()
        return None
    except Exception as e:
        print(f"✗ Error uploading race photos: {e}")
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
    parser.add_argument(
        "--sync-pages", action="store_true",
        help="Upload race pages to /race/ via tar+ssh (with correct permissions)"
    )
    parser.add_argument(
        "--pages-dir", default="wordpress/output",
        help="Path to race pages directory (default: wordpress/output)"
    )
    parser.add_argument(
        "--sync-photos", action="store_true",
        help="Upload race photos to /photos/ via tar+ssh"
    )
    parser.add_argument(
        "--photos-dir", default="wordpress/output/photos",
        help="Path to race photos directory (default: wordpress/output/photos)"
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
        "--purge-cache", action="store_true",
        help="Purge all SiteGround caches (static, dynamic, memcached, opcache)"
    )
    args = parser.parse_args()

    if not args.json and not args.sync_index and not args.sync_widget and not args.sync_training and not args.sync_guide and not args.sync_og and not args.sync_homepage and not args.sync_pages and not args.sync_photos and not args.sync_sitemap and not args.sync_redirects and not args.sync_noindex and not args.purge_cache:
        parser.error("Provide --json, --sync-index, --sync-widget, --sync-training, --sync-guide, --sync-og, --sync-homepage, --sync-pages, --sync-photos, --sync-redirects, --sync-noindex, and/or --purge-cache")

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
    if args.sync_pages:
        sync_pages(args.pages_dir)
    if args.sync_photos:
        sync_photos(args.photos_dir)
    if args.sync_sitemap:
        sync_sitemap()
    if args.sync_redirects:
        sync_redirects()
    if args.sync_noindex:
        sync_noindex()
    if args.purge_cache:
        purge_cache()
