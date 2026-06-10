#!/usr/bin/env python3
"""Indexing Audit — compare sitemap URLs against GSC indexed pages.

Parses sitemap.xml and queries Google Search Console to identify indexing
gaps. Categorizes URLs by page type and reports coverage percentages.

Usage:
    python scripts/indexing_audit.py                      # Live GSC query
    python scripts/indexing_audit.py --mock                # Mock data for testing
    python scripts/indexing_audit.py --output audit.json   # Save full results
    python scripts/indexing_audit.py --mock --output audit.json

Requires:
    - GOOGLE_APPLICATION_CREDENTIALS env var -> service account JSON
    - Service account needs GSC "Viewer" role on the property
    - pip install google-api-python-client google-auth
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SITE_URL = "sc-domain:gravelgodcycling.com"
BASE_URL = "https://gravelgodcycling.com"
SITEMAP_PATH = Path(__file__).resolve().parent.parent / "web" / "sitemap.xml"

# URL pattern rules — order matters (first match wins)
PAGE_TYPE_RULES = [
    ("state_hubs",    re.compile(r"^/race/best-gravel-races-")),
    ("tire_guides",   re.compile(r"^/race/.+/tires/$")),
    ("vs_comparisons", re.compile(r"^/race/.+-vs-.+/$")),
    ("tier_hubs",     re.compile(r"^/race/tier-\d+/$")),
    ("series_hubs",   re.compile(r"^/race/series/.+/$")),
    ("training_guides", re.compile(r"^/guide/")),
    ("articles",      re.compile(r"^/articles/")),
    ("blog_posts",    re.compile(r"^/blog/")),
    ("course_pages",  re.compile(r"^/course/")),
    ("race_profiles", re.compile(r"^/race/.+/$")),  # catch-all for /race/
]

# Possible indexing statuses
STATUS_INDEXED = "indexed"
STATUS_NOT_INDEXED = "not_indexed"
STATUS_CRAWLED_NOT_INDEXED = "crawled_not_indexed"
STATUS_ERROR = "error"


def parse_sitemap(sitemap_path: Path) -> list[str]:
    """Parse sitemap.xml and return list of URL paths (without base URL)."""
    if not sitemap_path.exists():
        print(f"  ERROR: Sitemap not found at {sitemap_path}")
        sys.exit(1)

    tree = ET.parse(sitemap_path)
    root = tree.getroot()

    # Handle namespace
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []
    for url_elem in root.findall("sm:url", ns):
        loc = url_elem.find("sm:loc", ns)
        if loc is not None and loc.text:
            path = loc.text.replace(BASE_URL, "")
            if not path:
                path = "/"
            urls.append(path)

    return sorted(urls)


def classify_url(path: str) -> str:
    """Classify a URL path into a page type."""
    for type_name, pattern in PAGE_TYPE_RULES:
        if pattern.search(path):
            return type_name
    return "other"


def get_gsc_service():
    """Build GSC API service from GOOGLE_APPLICATION_CREDENTIALS."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        return None

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    return build("searchconsole", "v1", credentials=creds)


def inspect_url_live(service, url_path: str) -> dict:
    """Query GSC URL Inspection API for a single URL.

    Returns dict with 'status' and 'details' keys.
    """
    full_url = BASE_URL + url_path
    try:
        result = service.urlInspection().index().inspect(
            body={
                "inspectionUrl": full_url,
                "siteUrl": SITE_URL,
            }
        ).execute()

        inspection = result.get("inspectionResult", {})
        index_status = inspection.get("indexStatusResult", {})
        verdict = index_status.get("verdict", "UNKNOWN")
        coverage = index_status.get("coverageState", "")

        if verdict == "PASS":
            status = STATUS_INDEXED
        elif "Crawled" in coverage and "not" in coverage.lower():
            status = STATUS_CRAWLED_NOT_INDEXED
        elif verdict == "FAIL" or verdict == "NEUTRAL":
            status = STATUS_NOT_INDEXED
        else:
            status = STATUS_NOT_INDEXED

        return {
            "url": url_path,
            "status": status,
            "verdict": verdict,
            "coverage_state": coverage,
            "last_crawl": index_status.get("lastCrawlTime", ""),
            "indexing_state": index_status.get("indexingState", ""),
        }
    except Exception as e:
        return {
            "url": url_path,
            "status": STATUS_ERROR,
            "verdict": "ERROR",
            "coverage_state": "",
            "last_crawl": "",
            "indexing_state": "",
            "error": str(e),
        }


def fetch_indexed_pages_via_analytics(service) -> set[str]:
    """Use Search Analytics API to find pages that have appeared in search.

    This is a practical proxy for 'indexed' -- if a page has had any
    impressions in the last 90 days, it is indexed. This avoids the
    URL Inspection API's heavy rate limits (2,000 req/day).
    """
    from datetime import date, timedelta

    end = date.today()
    start = end - timedelta(days=90)

    indexed_pages: set[str] = set()
    start_row = 0
    batch_size = 25000

    while True:
        resp = service.searchanalytics().query(
            siteUrl=SITE_URL,
            body={
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "dimensions": ["page"],
                "rowLimit": batch_size,
                "startRow": start_row,
            }
        ).execute()

        rows = resp.get("rows", [])
        if not rows:
            break

        for row in rows:
            page_url = row["keys"][0]
            path = page_url.replace(BASE_URL, "")
            if not path:
                path = "/"
            indexed_pages.add(path)

        if len(rows) < batch_size:
            break
        start_row += batch_size

    return indexed_pages


def generate_mock_data(urls: list[str]) -> list[dict]:
    """Generate realistic mock indexing data for testing."""
    random.seed(42)  # Reproducible results

    # Mock: most race profiles indexed, some gaps in newer page types
    type_index_rates = {
        "race_profiles":    0.82,
        "tire_guides":      0.45,
        "vs_comparisons":   0.60,
        "state_hubs":       0.90,
        "tier_hubs":        1.00,
        "series_hubs":      1.00,
        "training_guides":  0.95,
        "blog_posts":       0.80,
        "course_pages":     0.75,
        "other":            0.90,
    }

    results = []
    for url_path in urls:
        page_type = classify_url(url_path)
        rate = type_index_rates.get(page_type, 0.70)
        roll = random.random()

        if roll < rate:
            status = STATUS_INDEXED
        elif roll < rate + 0.05:
            status = STATUS_CRAWLED_NOT_INDEXED
        else:
            status = STATUS_NOT_INDEXED

        results.append({
            "url": url_path,
            "status": status,
            "page_type": page_type,
        })

    return results


def audit_with_analytics(service, urls: list[str]) -> list[dict]:
    """Audit indexing using Search Analytics API (impression-based)."""
    print("  Fetching indexed pages from Search Analytics (90-day window)...")
    indexed_pages = fetch_indexed_pages_via_analytics(service)
    print(f"  Found {len(indexed_pages):,} pages with search impressions\n")

    results = []
    for url_path in urls:
        page_type = classify_url(url_path)
        status = STATUS_INDEXED if url_path in indexed_pages else STATUS_NOT_INDEXED
        results.append({
            "url": url_path,
            "status": status,
            "page_type": page_type,
        })

    return results


def print_summary(results: list[dict]):
    """Print summary table grouped by page type."""
    # Aggregate by page type
    types: dict[str, dict] = {}
    for r in results:
        pt = r["page_type"]
        if pt not in types:
            types[pt] = {"total": 0, STATUS_INDEXED: 0, STATUS_NOT_INDEXED: 0,
                         STATUS_CRAWLED_NOT_INDEXED: 0, STATUS_ERROR: 0}
        types[pt]["total"] += 1
        types[pt][r["status"]] += 1

    # Display order
    display_order = [
        "race_profiles", "tire_guides", "vs_comparisons", "state_hubs",
        "tier_hubs", "series_hubs", "training_guides", "blog_posts",
        "course_pages", "other",
    ]
    ordered = [t for t in display_order if t in types]
    ordered += [t for t in types if t not in ordered]

    # Header
    print(f"\n{'=' * 78}")
    print(f"  INDEXING AUDIT REPORT")
    print(f"{'=' * 78}\n")

    header = (
        f"  {'Page Type':<20} {'Total':>6} {'Indexed':>8} "
        f"{'Not Idx':>8} {'Crawled':>8} {'Error':>6} {'Coverage':>9}"
    )
    print(header)
    print(f"  {'-' * 74}")

    grand = {"total": 0, STATUS_INDEXED: 0, STATUS_NOT_INDEXED: 0,
             STATUS_CRAWLED_NOT_INDEXED: 0, STATUS_ERROR: 0}

    for pt in ordered:
        d = types[pt]
        pct = (d[STATUS_INDEXED] / d["total"] * 100) if d["total"] else 0
        print(
            f"  {pt:<20} {d['total']:>6} {d[STATUS_INDEXED]:>8} "
            f"{d[STATUS_NOT_INDEXED]:>8} {d[STATUS_CRAWLED_NOT_INDEXED]:>8} "
            f"{d[STATUS_ERROR]:>6} {pct:>8.1f}%"
        )
        for key in grand:
            grand[key] += d[key]

    print(f"  {'-' * 74}")
    grand_pct = (grand[STATUS_INDEXED] / grand["total"] * 100) if grand["total"] else 0
    print(
        f"  {'TOTAL':<20} {grand['total']:>6} {grand[STATUS_INDEXED]:>8} "
        f"{grand[STATUS_NOT_INDEXED]:>8} {grand[STATUS_CRAWLED_NOT_INDEXED]:>8} "
        f"{grand[STATUS_ERROR]:>6} {grand_pct:>8.1f}%"
    )
    print()

    # Not-indexed breakdown (top offenders)
    not_indexed = [r for r in results if r["status"] != STATUS_INDEXED]
    if not_indexed:
        print(f"  {len(not_indexed)} URLs not indexed. Sample (up to 20):\n")
        for r in not_indexed[:20]:
            label = r["status"].replace("_", " ")
            print(f"    [{label:<22}] {r['url']}")
        if len(not_indexed) > 20:
            print(f"    ... and {len(not_indexed) - 20} more (use --output to see all)")
    print()


def save_results(results: list[dict], output_path: str):
    """Save full results as JSON."""
    output = {
        "total_urls": len(results),
        "indexed": sum(1 for r in results if r["status"] == STATUS_INDEXED),
        "not_indexed": sum(1 for r in results if r["status"] == STATUS_NOT_INDEXED),
        "crawled_not_indexed": sum(1 for r in results if r["status"] == STATUS_CRAWLED_NOT_INDEXED),
        "error": sum(1 for r in results if r["status"] == STATUS_ERROR),
        "results": results,
    }
    path = Path(output_path)
    path.write_text(json.dumps(output, indent=2) + "\n")
    print(f"  Full results saved to {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Audit sitemap URLs against GSC indexing status"
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Use mock data instead of querying GSC (for testing)"
    )
    parser.add_argument(
        "--output", metavar="FILE",
        help="Save full results as JSON to FILE"
    )
    parser.add_argument(
        "--sitemap", metavar="PATH",
        help=f"Path to sitemap.xml (default: {SITEMAP_PATH})"
    )
    args = parser.parse_args()

    sitemap = Path(args.sitemap) if args.sitemap else SITEMAP_PATH

    # Parse sitemap(s)
    urls = parse_sitemap(sitemap)
    blog_sitemap = sitemap.parent / "blog-sitemap.xml"
    if blog_sitemap.exists():
        blog_urls = parse_sitemap(blog_sitemap)
        urls = sorted(set(urls + blog_urls))
    print(f"\n  Parsed {len(urls):,} URLs from sitemap(s)")

    # Classify all URLs
    for url in urls:
        classify_url(url)  # warm-up / validation

    if args.mock:
        print("  Running in MOCK mode (sample data)\n")
        results = generate_mock_data(urls)
    else:
        service = get_gsc_service()
        if service is None:
            print("\n  GOOGLE_APPLICATION_CREDENTIALS not set.")
            print("\n  Setup steps:")
            print("    1. Create a GCP service account with Search Console API enabled")
            print("    2. Download the JSON key file")
            print("    3. Add the service account email as a Viewer in GSC")
            print("    4. export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
            print("\n  Use --mock to test with sample data.\n")
            sys.exit(1)

        results = audit_with_analytics(service, urls)

    # Ensure page_type is set on all results
    for r in results:
        if "page_type" not in r:
            r["page_type"] = classify_url(r["url"])

    print_summary(results)

    if args.output:
        save_results(results, args.output)


if __name__ == "__main__":
    main()
