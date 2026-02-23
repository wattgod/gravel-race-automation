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
        ("/about/", "About page"),
        ("/coaching/", "Coaching page"),
        ("/coaching/apply/", "Coaching apply page"),
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
    """Verify deployed blog pages are accessible, categorized by type."""
    print("\n[Blog Pages]")
    project_root = Path(__file__).resolve().parent.parent
    blog_dir = project_root / "wordpress" / "output" / "blog"

    if not blog_dir.exists():
        v.warn("Blog output directory not found",
               "Run generate_blog_preview.py --all to generate blog pages")
        return

    html_files = sorted(blog_dir.glob("*.html"))
    if not html_files:
        v.warn("No blog pages generated",
               "Run generate_blog_preview.py --all to generate blog pages")
        return

    # Categorize by type
    previews = [f for f in html_files if not f.stem.startswith("roundup-") and not f.stem.endswith("-recap")]
    roundups = [f for f in html_files if f.stem.startswith("roundup-")]
    recaps = [f for f in html_files if f.stem.endswith("-recap")]

    v.check(True, f"{len(html_files)} blog pages found locally "
            f"({len(previews)} previews, {len(roundups)} roundups, {len(recaps)} recaps)", "")

    if not QUICK:
        # Sample 1 from each category for HTTP check
        samples = []
        if previews:
            samples.append(previews[0])
        if roundups:
            samples.append(roundups[0])
        if recaps:
            samples.append(recaps[0])
        for f in samples:
            slug = f.stem
            url = f"{BASE_URL}/blog/{slug}/"
            code = curl_status(url)
            v.check(code == "200", f"Blog page accessible: /blog/{slug}/",
                    f"HTTP {code}")


def check_blog_index(v):
    """Verify blog index page is accessible."""
    print("\n[Blog Index]")
    if QUICK:
        return

    code = curl_status(f"{BASE_URL}/blog/")
    v.check(code == "200", "/blog/ returns 200", f"HTTP {code}")

    if code == "200":
        body = curl_body(f"{BASE_URL}/blog/")
        v.check("blog-index.json" in body, "/blog/ references blog-index.json",
                "Missing blog-index.json fetch")
        v.check("gg-blog-index" in body or "gg-bi-grid" in body,
                "/blog/ contains expected CSS class",
                "Missing expected CSS class")


def check_blog_sitemap(v):
    """Verify blog sitemap is accessible and referenced in sitemap index."""
    print("\n[Blog Sitemap]")
    project_root = Path(__file__).resolve().parent.parent
    blog_sitemap = project_root / "web" / "blog-sitemap.xml"

    if not blog_sitemap.exists():
        v.warn("Blog sitemap not generated locally",
               "Run: python scripts/generate_sitemap.py --blog")
        return

    v.check(True, "blog-sitemap.xml exists locally", "")

    if not QUICK:
        code = curl_status(f"{BASE_URL}/blog-sitemap.xml")
        v.check(code == "200", "/blog-sitemap.xml accessible", f"HTTP {code}")

        body = curl_body(f"{BASE_URL}/sitemap.xml")
        v.check("blog-sitemap.xml" in body,
                "sitemap.xml references blog-sitemap.xml",
                "Missing blog-sitemap.xml entry in sitemap index")


def check_permissions(v):
    """Verify /race/ directory is accessible (not 403)."""
    print("\n[Permissions]")
    # /race/ should redirect to /gravel-races/, not 403
    code = curl_status(f"{BASE_URL}/race/")
    v.check(code in ("301", "302"), "/race/ redirects (not 403)", f"HTTP {code}")


def check_ab_testing_assets(v):
    """Verify A/B testing assets are deployed and accessible."""
    print("\n[A/B Testing]")
    # JS file must return 200
    code = curl_status(f"{BASE_URL}/ab/gg-ab-tests.js")
    v.check(code == "200", "/ab/gg-ab-tests.js accessible", f"HTTP {code}")

    # Config JSON must return 200 and be valid JSON
    code = curl_status(f"{BASE_URL}/ab/experiments.json")
    v.check(code == "200", "/ab/experiments.json accessible", f"HTTP {code}")

    if code == "200":
        body = curl_body(f"{BASE_URL}/ab/experiments.json")
        try:
            data = json.loads(body)
            v.check("experiments" in data,
                    "/ab/experiments.json has experiments key",
                    "Missing 'experiments' key in JSON")
            v.check(len(data.get("experiments", [])) > 0,
                    "/ab/experiments.json has active experiments",
                    "No active experiments in config")
        except json.JSONDecodeError:
            v.check(False, "/ab/experiments.json is valid JSON",
                    "Invalid JSON response")


def check_coaching(v):
    """Verify coaching page is deployed with expected content."""
    print("\n[Coaching Page]")
    code = curl_status(f"{BASE_URL}/coaching/")
    v.check(code == "200", "/coaching/ accessible", f"HTTP {code}")

    if code == "200":
        body = curl_body(f"{BASE_URL}/coaching/")
        v.check("gg-coach-hero" in body, "Coaching page has hero section", "Missing hero")
        v.check("gg-coach-tier" in body, "Coaching page has tier comparison", "Missing tiers")
        v.check("coaching_page_view" in body, "Coaching page has GA4 tracking", "Missing GA4 events")
        v.check("application/ld+json" in body, "Coaching page has JSON-LD", "Missing JSON-LD")
        v.check("$199" in body or "$299" in body, "Coaching page has pricing info", "Missing pricing")
        v.check("gg-coach-faq" in body, "Coaching page has FAQ section", "Missing FAQ")


def check_coaching_apply(v):
    """Verify coaching apply page is deployed with expected content."""
    print("\n[Coaching Apply Page]")
    code = curl_status(f"{BASE_URL}/coaching/apply/")
    v.check(code == "200", "/coaching/apply/ accessible", f"HTTP {code}")

    if code == "200":
        body = curl_body(f"{BASE_URL}/coaching/apply/")
        v.check("intake-form" in body, "Apply page has intake form", "Missing form")
        v.check("gg-apply-progress" in body, "Apply page has progress bar", "Missing progress bar")
        v.check("apply_page_view" in body, "Apply page has GA4 tracking", "Missing GA4 events")
        v.check("application/ld+json" in body, "Apply page has JSON-LD", "Missing JSON-LD")
        v.check("inferTraits" in body, "Apply page has blindspot inference", "Missing inference")
        v.check("noindex" in body, "Apply page is noindexed", "Missing noindex")


def check_success_pages(v):
    """Verify post-checkout success pages are deployed."""
    print("\n[Success Pages]")
    success_pages = [
        ("/training-plans/success/", "training-plans", "gg-success"),
        ("/coaching/welcome/", "coaching", "gg-success"),
        ("/consulting/confirmed/", "consulting", "gg-success"),
    ]
    for path, product, css_prefix in success_pages:
        url = f"{BASE_URL}{path}"
        code = curl_status(url)
        v.check(code == "200", f"{path} accessible", f"HTTP {code}")
        if code == "200":
            body = curl_body(url)
            v.check(css_prefix in body, f"{path} has success CSS", f"Missing {css_prefix}")
            v.check("noindex" in body, f"{path} is noindexed", "Missing noindex")
            v.check("session_id" in body, f"{path} has session_id tracking", "Missing session_id")


def check_insights(v):
    """Verify insights page is deployed with expected content."""
    print("\n[Insights Page]")
    code = curl_status(f"{BASE_URL}/insights/")
    v.check(code == "200", "/insights/ accessible", f"HTTP {code}")

    if code == "200":
        body = curl_body(f"{BASE_URL}/insights/")
        v.check("State of Gravel" in body, "Insights page has title", "Missing title")
        v.check("gg-ins-map-grid" in body, "Insights page has geography map", "Missing tile grid map")
        v.check("data-counter" in body, "Insights page has counter animations", "Missing data-counter")
        v.check("insights_page_view" in body, "Insights page has GA4 tracking", "Missing GA4 events")


def check_meta_descriptions(v):
    """Verify meta descriptions are deployed and appearing on pages."""
    import html as html_mod
    print("\n[Meta Descriptions]")
    project_root = Path(__file__).resolve().parent.parent
    json_path = project_root / "seo" / "meta-descriptions.json"

    if not json_path.exists():
        v.warn("meta-descriptions.json not found locally",
               "Run: python scripts/generate_meta_descriptions.py")
        return

    data = json.loads(json_path.read_text())
    entries = data.get("entries", [])
    v.check(len(entries) >= 100, f"meta-descriptions.json has {len(entries)} entries",
            f"Too few entries (expected 131)")

    if QUICK:
        return

    # Spot-check 5 key pages for meta description presence.
    # These are WordPress-managed pages where the mu-plugin injects our descriptions.
    spot_checks = [
        (448, "/", "home"),
        (5018, "/gravel-races/", "gravel-races"),
        (5016, "/products/training-plans/", "training-plans"),
        (5043, "/coaching/", "coaching"),
        (5045, "/articles/", "articles"),
    ]

    entries_by_id = {e["wp_id"]: e for e in entries}
    for wp_id, path, name in spot_checks:
        if wp_id not in entries_by_id:
            v.warn(f"wp_id={wp_id} ({name}) not in meta-descriptions.json", "")
            continue

        expected_desc = entries_by_id[wp_id]["description"]
        body = curl_body(f"{BASE_URL}{path}")

        # HTML encodes special chars in attribute values (&→&amp; "→&quot; etc.)
        escaped_desc = html_mod.escape(expected_desc, quote=True)
        # Check for exact match in content attr, or partial match (first 50 chars)
        has_meta = (f'content="{escaped_desc}"' in body
                    or html_mod.escape(expected_desc[:50], quote=True) in body)
        v.check(has_meta, f"Meta description on {path}",
                f"Expected: {expected_desc[:60]}...")

        # Spot-check title override if present
        expected_title = entries_by_id[wp_id].get("title")
        if expected_title:
            escaped_title = html_mod.escape(expected_title, quote=True)
            has_title = (escaped_title in body
                         or f"<title>{escaped_title}</title>" in body)
            v.check(has_title, f"Title override on {path}",
                    f"Expected: {expected_title}")


def check_legal_pages(v):
    """Verify legal pages are deployed with expected content."""
    print("\n[Legal Pages]")
    legal_pages = [
        ("/privacy/", "Privacy Policy", "privacy-policy"),
        ("/terms/", "Terms of Service", "terms-of-service"),
        ("/cookies/", "Cookie Policy", "cookie-policy"),
    ]
    for path, name, slug in legal_pages:
        url = f"{BASE_URL}{path}"
        code = curl_status(url)
        v.check(code == "200", f"{path} accessible", f"HTTP {code}")
        if code == "200":
            body = curl_body(url)
            v.check("noindex" in body, f"{path} is noindexed", "Missing noindex")
            v.check("gg-consent-banner" in body, f"{path} has consent banner", "Missing consent banner")
            v.check("gg_consent=accepted" in body, f"{path} has consent cookie check", "Missing cookie logic")
            v.check("gg-site-header" in body, f"{path} has site header", "Missing header")
            v.check("gg-mega-footer" in body, f"{path} has mega footer", "Missing footer")
            v.check("og:image" in body, f"{path} has og:image", "Missing og:image meta tag")
            # Consent defaults must use regex, not indexOf
            v.check("indexOf" not in body, f"{path} consent uses regex not indexOf",
                    "Found indexOf — must use regex pattern")


def check_guide_cluster(v):
    """Verify guide cluster pages (pillar + 8 chapters) are deployed."""
    print("\n[Guide Cluster]")
    guide_pages = [
        ("/guide/", "Guide pillar"),
        ("/guide/what-is-gravel-racing/", "Ch 1: What Is Gravel Racing"),
        ("/guide/race-selection/", "Ch 2: Race Selection"),
        ("/guide/training-fundamentals/", "Ch 3: Training Fundamentals"),
        ("/guide/workout-execution/", "Ch 4: Workout Execution"),
        ("/guide/nutrition-fueling/", "Ch 5: Nutrition & Fueling"),
        ("/guide/mental-training-race-tactics/", "Ch 6: Mental Training"),
        ("/guide/race-week/", "Ch 7: Race Week"),
        ("/guide/post-race/", "Ch 8: Post-Race"),
        ("/guide/race-prep-configurator/", "Race Prep Configurator"),
    ]
    for path, name in guide_pages:
        code = curl_status(f"{BASE_URL}{path}")
        v.check(code == "200", f"{name} ({path})", f"HTTP {code}")

    # Spot-check SEO elements on pillar
    body = curl_body(f"{BASE_URL}/guide/")
    if body:
        v.check("application/ld+json" in body, "Guide pillar has JSON-LD", "Missing JSON-LD")
        v.check("canonical" in body.lower(), "Guide pillar has canonical", "Missing canonical")
        v.check("gg-site-header" in body, "Guide pillar has site header", "Missing header")
        v.check("gg-mega-footer" in body, "Guide pillar has mega footer", "Missing footer")

    # Spot-check a chapter page
    ch_body = curl_body(f"{BASE_URL}/guide/training-fundamentals/")
    if ch_body:
        v.check("application/ld+json" in ch_body, "Chapter page has JSON-LD", "Missing JSON-LD")
        v.check("canonical" in ch_body.lower(), "Chapter page has canonical", "Missing canonical")
        v.check("breadcrumb" in ch_body.lower() or "BreadcrumbList" in ch_body,
                "Chapter page has breadcrumb", "Missing breadcrumb")


def check_series_hubs(v):
    """Verify series hub pages are deployed and accessible."""
    print("\n[Series Hubs]")
    series_slugs = [
        "belgian-waffle-ride",
        "life-time-grand-prix",
        "grinduro",
        "grasshopper-adventure-series",
        "gravel-earth-series",
    ]
    for slug in series_slugs:
        url = f"{BASE_URL}/race/series/{slug}/"
        code = curl_status(url)
        v.check(code == "200", f"/race/series/{slug}/ accessible", f"HTTP {code}")


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
    check_blog_index(v)
    check_blog_sitemap(v)
    check_photo_infrastructure(v)
    check_ab_testing_assets(v)
    check_coaching(v)
    check_coaching_apply(v)
    check_success_pages(v)
    check_series_hubs(v)
    check_guide_cluster(v)
    check_insights(v)
    check_legal_pages(v)
    check_meta_descriptions(v)

    check_search_schema(v)
    check_featured_slugs(v)

    if not QUICK:
        check_sample_race_pages(v)

    sys.exit(v.summary())


if __name__ == "__main__":
    main()
