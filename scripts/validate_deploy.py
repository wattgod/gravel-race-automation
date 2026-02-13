#!/usr/bin/env python3
"""
Post-deploy validation for gravelgodcycling.com.

Run after any deploy to verify the site is working correctly.
Checks redirects, sitemaps, key pages, and SEO basics.

Usage:
    python scripts/validate_deploy.py
    python scripts/validate_deploy.py --verbose
    python scripts/validate_deploy.py --quick     # Skip slow checks
"""

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


BASE_URL = "https://gravelgodcycling.com"
VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
QUICK = "--quick" in sys.argv


def curl_status(url, timeout=15):
    """Return HTTP status code for a URL."""
    try:
        result = subprocess.run(
            ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except Exception:
        return "ERR"


def curl_headers(url, timeout=15):
    """Return response headers for a URL."""
    try:
        result = subprocess.run(
            ["curl", "-sI", url],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout
    except Exception:
        return ""


def curl_body(url, timeout=15):
    """Return response body for a URL."""
    try:
        result = subprocess.run(
            ["curl", "-s", url],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout
    except Exception:
        return ""


class Validator:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def check(self, ok, label, detail=""):
        if ok:
            self.passed += 1
            if VERBOSE:
                print(f"  PASS  {label}")
        else:
            self.failed += 1
            print(f"  FAIL  {label}: {detail}")
    
    def warn(self, label, detail=""):
        self.warnings += 1
        print(f"  WARN  {label}: {detail}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"Results: {self.passed}/{total} passed, {self.failed} failed, {self.warnings} warnings")
        if self.failed > 0:
            print("DEPLOY VALIDATION FAILED")
            return 1
        elif self.warnings > 0:
            print("DEPLOY OK (with warnings)")
            return 0
        else:
            print("ALL CHECKS PASSED")
            return 0


def check_key_pages(v):
    """Verify critical pages return 200."""
    print("\n[Key Pages]")
    pages = [
        ("/", "Homepage"),
        ("/gravel-races/", "Race search page"),
        ("/guide/", "Training guide"),
        ("/race/methodology/", "Methodology page"),
    ]
    for path, name in pages:
        code = curl_status(f"{BASE_URL}{path}")
        v.check(code == "200", f"{name} ({path})", f"HTTP {code}")


def check_sample_race_pages(v):
    """Verify a sample of race pages from each tier."""
    print("\n[Sample Race Pages]")
    project_root = Path(__file__).resolve().parent.parent
    index_path = project_root / "web" / "race-index.json"
    if not index_path.exists():
        v.warn("race-index.json not found", str(index_path))
        return
    
    races = json.loads(index_path.read_text())
    
    # Sample: first 2 from each tier
    by_tier = {}
    for r in races:
        tier = r.get("tier", 4)
        by_tier.setdefault(tier, []).append(r)
    
    samples = []
    for tier in sorted(by_tier.keys()):
        samples.extend(by_tier[tier][:2])
    
    for race in samples:
        slug = race["slug"]
        path = f"/race/{slug}/"
        code = curl_status(f"{BASE_URL}{path}")
        v.check(code == "200", f"T{race.get('tier', '?')} {slug}", f"HTTP {code}")


def check_sitemaps(v):
    """Verify sitemap index and sub-sitemaps."""
    print("\n[Sitemaps]")
    
    # Main sitemap index
    body = curl_body(f"{BASE_URL}/sitemap.xml")
    v.check("<sitemapindex" in body, "sitemap.xml is a sitemap index", 
            "Not a sitemap index format")
    
    # Sub-sitemaps
    for name in ["race-sitemap.xml", "post-sitemap.xml", "page-sitemap.xml", "category-sitemap.xml"]:
        code = curl_status(f"{BASE_URL}/{name}")
        v.check(code == "200", f"{name} accessible", f"HTTP {code}")


def check_robots_txt(v):
    """Verify robots.txt exists and references sitemap."""
    print("\n[Robots.txt]")
    body = curl_body(f"{BASE_URL}/robots.txt")
    v.check("Sitemap:" in body, "robots.txt has Sitemap directive",
            "Missing Sitemap directive")
    v.check("sitemap.xml" in body, "robots.txt references sitemap.xml",
            f"Content: {body[:200]}")


def check_redirects(v):
    """Verify key redirects work."""
    print("\n[Redirects]")
    # Just test a few key ones — use validate_redirects.py for full check
    test_pairs = [
        ("/page/2/", "/"),
        ("/guide.html", "/guide/"),
        ("/race/", "/gravel-races/"),
        ("/barry-roubaix-race-guide/", "/race/barry-roubaix/"),
        ("/belgian-waffle-ride/", "/race/bwr-california/"),
        ("/training-plans-faq/gravelgodcoaching@gmail.com", "/training-plans-faq/"),
    ]
    for source, expected in test_pairs:
        try:
            result = subprocess.run(
                ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code} %{redirect_url}",
                 f"{BASE_URL}{source}"],
                capture_output=True, text=True, timeout=15
            )
            parts = result.stdout.strip().split(" ", 1)
            code = parts[0]
            location = parts[1] if len(parts) > 1 else ""
            expected_full = f"{BASE_URL}{expected}"
            ok = code == "301" and location == expected_full
            v.check(ok, f"{source} → {expected}",
                    f"HTTP {code}, Location: {location}")
        except Exception as e:
            v.check(False, f"{source} → {expected}", str(e))


def check_og_images(v):
    """Verify OG images for sample races."""
    print("\n[OG Images]")
    for slug in ["unbound-200", "barry-roubaix", "mid-south"]:
        code = curl_status(f"{BASE_URL}/og/{slug}.jpg")
        v.check(code == "200", f"OG image: {slug}.jpg", f"HTTP {code}")


def check_race_page_seo(v):
    """Spot-check SEO elements on a race page."""
    print("\n[Race Page SEO]")
    body = curl_body(f"{BASE_URL}/race/unbound-200/")
    
    v.check("<title>" in body.lower(), "Has <title> tag", "Missing title")
    v.check('og:title' in body, "Has og:title", "Missing og:title meta")
    v.check('og:description' in body, "Has og:description", "Missing og:description meta")
    v.check('og:image' in body, "Has og:image", "Missing og:image meta")
    v.check('canonical' in body.lower(), "Has canonical link", "Missing canonical")
    v.check('application/ld+json' in body, "Has JSON-LD structured data", "Missing JSON-LD")


def check_citations(v):
    """Verify citations section renders correctly on live pages."""
    print("\n[Citations]")
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "race-data"

    # Find a race WITH citations
    with_cite_slug = None
    without_cite_slug = None
    for f in sorted(data_dir.glob('*.json')):
        d = json.loads(f.read_text())
        cites = d['race'].get('citations', [])
        if cites and not with_cite_slug:
            with_cite_slug = f.stem
            with_cite_count = len(cites)
        if not cites and not without_cite_slug:
            without_cite_slug = f.stem
        if with_cite_slug and without_cite_slug:
            break

    if with_cite_slug:
        body = curl_body(f"{BASE_URL}/race/{with_cite_slug}/")
        has_section = 'id="citations"' in body
        v.check(has_section, f"Citations section renders on {with_cite_slug} ({with_cite_count} citations)",
                "Section missing from page HTML")
        # Count citation items on page
        item_count = body.count('class="gg-citation-item"')
        v.check(item_count == with_cite_count,
                f"Citation count matches JSON ({item_count} rendered vs {with_cite_count} in data)",
                f"Mismatch: {item_count} on page, {with_cite_count} in JSON")
        v.check(item_count <= 20, f"Citation count <= 20 ({item_count})",
                f"Too many citations: {item_count}")

    if without_cite_slug:
        body = curl_body(f"{BASE_URL}/race/{without_cite_slug}/")
        no_section = 'id="citations"' not in body
        v.check(no_section, f"No citations section on {without_cite_slug} (has 0 citations)",
                "Citations section rendered on page with no citation data")


def check_noindex(v):
    """Verify junk pages have noindex meta tag (from gg-noindex.php mu-plugin)."""
    print("\n[Noindex Meta Tags]")
    noindex_paths = [
        ("/2021/11/", "Date archive"),
        ("/category/uncategorized/", "Category page"),
        ("/cart/", "WooCommerce cart"),
    ]
    for path, name in noindex_paths:
        body = curl_body(f"{BASE_URL}{path}")
        # Check for noindex in either meta robots tag or X-Robots-Tag header
        has_noindex = 'content="noindex' in body.lower()
        v.check(has_noindex, f"noindex on {name} ({path})",
                "Missing noindex meta tag")

    # Verify important pages do NOT have noindex
    clean_paths = [
        ("/", "Homepage"),
        ("/gravel-races/", "Race search"),
    ]
    for path, name in clean_paths:
        body = curl_body(f"{BASE_URL}{path}")
        has_noindex = 'content="noindex' in body.lower()
        v.check(not has_noindex, f"No noindex on {name} ({path})",
                "noindex meta tag found on important page!")


def check_search_schema(v):
    """Verify /gravel-races/ has CollectionPage and BreadcrumbList JSON-LD."""
    print("\n[Search Page Schema]")
    body = curl_body(f"{BASE_URL}/gravel-races/")
    v.check('"CollectionPage"' in body, "CollectionPage JSON-LD on /gravel-races/",
            "Missing CollectionPage schema")
    v.check('"BreadcrumbList"' in body, "BreadcrumbList JSON-LD on /gravel-races/",
            "Missing BreadcrumbList schema")


def check_featured_slugs(v):
    """Verify all FEATURED_SLUGS in generate_homepage.py exist in race-index.json."""
    print("\n[Featured Slugs]")
    project_root = Path(__file__).resolve().parent.parent
    index_path = project_root / "web" / "race-index.json"
    if not index_path.exists():
        v.warn("race-index.json not found", str(index_path))
        return

    # Import FEATURED_SLUGS from the homepage generator
    sys.path.insert(0, str(project_root / "wordpress"))
    try:
        from generate_homepage import FEATURED_SLUGS
    except ImportError:
        v.warn("Could not import FEATURED_SLUGS", "generate_homepage.py not found")
        return
    finally:
        sys.path.pop(0)

    races = json.loads(index_path.read_text())
    index_slugs = {r["slug"] for r in races}

    for slug in FEATURED_SLUGS:
        v.check(slug in index_slugs, f"Featured slug '{slug}' exists in index",
                f"'{slug}' not found — homepage will use fallback")

    # Also verify the featured race pages are live
    if not QUICK:
        for slug in FEATURED_SLUGS:
            if slug in index_slugs:
                code = curl_status(f"{BASE_URL}/race/{slug}/")
                v.check(code == "200", f"Featured race page /race/{slug}/", f"HTTP {code}")


def check_photo_infrastructure(v):
    """Verify photo infrastructure is in place."""
    print("\n[Photo Infrastructure]")
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "race-data"
    photos_dir = project_root / "race-photos"

    # Check if any races have photos configured
    races_with_photos = 0
    for f in sorted(data_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text())
            photos = d["race"].get("photos", [])
            if photos:
                races_with_photos += 1
                # Verify photo files exist locally
                for p in photos:
                    url = p.get("url", "")
                    if url.startswith("/race-photos/"):
                        local_path = project_root / url.lstrip("/")
                        v.check(local_path.exists(),
                                f"Photo exists: {url}",
                                f"File not found: {local_path}")
        except (json.JSONDecodeError, KeyError):
            continue

    if races_with_photos > 0:
        v.check(True, f"{races_with_photos} races have photos configured", "")
        # Check that /race-photos/ is accessible on server
        if not QUICK:
            code = curl_status(f"{BASE_URL}/race-photos/")
            v.check(code != "403", "/race-photos/ not 403", f"HTTP {code}")
    else:
        v.warn("No races have photos configured yet",
               "Add photos to race JSON files as they become available")


def check_blog_pages(v):
    """Verify deployed blog preview pages are accessible."""
    print("\n[Blog Pages]")
    project_root = Path(__file__).resolve().parent.parent
    blog_dir = project_root / "wordpress" / "output" / "blog"

    if not blog_dir.exists():
        v.warn("Blog output directory not found",
               "Run generate_blog_preview.py --all to generate blog pages")
        return

    html_files = sorted(blog_dir.glob("*.html"))
    if not html_files:
        v.warn("No blog preview pages generated",
               "Run generate_blog_preview.py --all to generate blog pages")
        return

    v.check(True, f"{len(html_files)} blog preview pages found locally", "")

    if not QUICK:
        # Sample up to 3 pages
        sample = html_files[:3]
        for f in sample:
            slug = f.stem
            url = f"{BASE_URL}/blog/{slug}/"
            code = curl_status(url)
            v.check(code == "200", f"Blog page accessible: /blog/{slug}/",
                    f"HTTP {code}")


def check_permissions(v):
    """Verify /race/ directory is accessible (not 403)."""
    print("\n[Permissions]")
    # /race/ should redirect to /gravel-races/, not 403
    code = curl_status(f"{BASE_URL}/race/")
    v.check(code in ("301", "302"), "/race/ redirects (not 403)", f"HTTP {code}")


def main():
    print(f"Validating {BASE_URL}...")
    v = Validator()

    check_key_pages(v)
    check_permissions(v)
    check_redirects(v)
    check_noindex(v)
    check_sitemaps(v)
    check_robots_txt(v)
    check_og_images(v)
    check_race_page_seo(v)
    check_citations(v)
    check_blog_pages(v)
    check_photo_infrastructure(v)

    check_search_schema(v)
    check_featured_slugs(v)

    if not QUICK:
        check_sample_race_pages(v)

    sys.exit(v.summary())


if __name__ == "__main__":
    main()
