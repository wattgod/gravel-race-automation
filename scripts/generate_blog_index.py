#!/usr/bin/env python3
"""
generate_blog_index.py — Scan blog HTML files and generate blog-index.json.

Reads wordpress/output/blog/*.html, extracts metadata from each HTML file
(title, date, tier, category, excerpt, OG image), and outputs a JSON index
at web/blog-index.json.

Usage:
    python scripts/generate_blog_index.py                   # Generate index
    python scripts/generate_blog_index.py --stats           # Show stats summary
    python scripts/generate_blog_index.py --blog-dir DIR    # Custom blog directory
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BLOG_DIR = PROJECT_ROOT / "wordpress" / "output" / "blog"
OUTPUT_DIR = PROJECT_ROOT / "web"
SITE_URL = "https://gravelgodcycling.com"

TIER_NAMES = {1: "Elite", 2: "Contender", 3: "Solid", 4: "Roster"}


def classify_blog_slug(slug):
    """Classify a blog slug by content type.

    Returns 'roundup', 'recap', or 'preview'.
    """
    if slug.startswith("roundup-"):
        return "roundup"
    if slug.endswith("-recap"):
        return "recap"
    return "preview"


def extract_blog_metadata(html_path):
    """Extract metadata from a blog HTML file.

    Returns dict with slug, title, category, tier, date, excerpt, og_image, url.
    """
    slug = html_path.stem
    category = classify_blog_slug(slug)

    try:
        content = html_path.read_text(errors="replace")
    except Exception:
        return None

    # Extract title from <title> tag
    title_match = re.search(r'<title>(.*?)</title>', content, re.DOTALL)
    title = title_match.group(1).strip() if title_match else slug
    # Strip " — Gravel God" suffix
    title = re.sub(r'\s*[—–-]\s*Gravel God$', '', title)

    # Extract date from JSON-LD datePublished or Published text
    pub_date = date.today().isoformat()
    jsonld_match = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})"', content)
    if jsonld_match:
        pub_date = jsonld_match.group(1)
    else:
        pub_match = re.search(r'Published\s+(\w+\s+\d+,?\s+\d{4})', content)
        if pub_match:
            # Parse "February 12, 2026" format
            from datetime import datetime
            try:
                dt = datetime.strptime(pub_match.group(1).replace(",", ""), "%B %d %Y")
                pub_date = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Extract tier from hero meta or content
    tier = 0
    tier_match = re.search(r'Tier\s+(\d)', content)
    if tier_match:
        tier = int(tier_match.group(1))

    # Extract excerpt from <meta name="description">
    excerpt = ""
    desc_match = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', content)
    if desc_match:
        excerpt = desc_match.group(1).strip()

    # Extract OG image
    og_image = ""
    og_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]*)"', content)
    if og_match:
        og_image = og_match.group(1).strip()

    return {
        "slug": slug,
        "title": title,
        "category": category,
        "tier": tier,
        "date": pub_date,
        "excerpt": excerpt,
        "og_image": og_image,
        "url": f"/blog/{slug}/",
    }


def generate_blog_index(blog_dir=None, output_dir=None):
    """Scan blog HTML files and generate blog-index.json.

    Returns the list of blog entries.
    """
    blog_path = blog_dir or BLOG_DIR
    out_path = output_dir or OUTPUT_DIR

    if not blog_path.exists():
        print(f"ERROR: Blog directory not found: {blog_path}")
        return []

    html_files = sorted(blog_path.glob("*.html"))
    if not html_files:
        print("No blog HTML files found.")
        return []

    entries = []
    for f in html_files:
        meta = extract_blog_metadata(f)
        if meta:
            entries.append(meta)

    # Sort by date descending (newest first)
    entries.sort(key=lambda e: e["date"], reverse=True)

    # Write output
    out_path.mkdir(parents=True, exist_ok=True)
    index_file = out_path / "blog-index.json"
    index_file.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")

    return entries


def main():
    parser = argparse.ArgumentParser(description="Generate blog-index.json from blog HTML")
    parser.add_argument("--blog-dir", type=Path, default=BLOG_DIR,
                        help="Directory containing blog HTML files")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR,
                        help="Output directory for blog-index.json")
    parser.add_argument("--stats", action="store_true",
                        help="Show category/tier stats")
    args = parser.parse_args()

    entries = generate_blog_index(args.blog_dir, args.output_dir)

    if not entries:
        print("No blog entries generated.")
        return

    # Stats
    categories = {}
    tiers = {}
    for e in entries:
        cat = e["category"]
        categories[cat] = categories.get(cat, 0) + 1
        t = e["tier"]
        if t:
            tiers[t] = tiers.get(t, 0) + 1

    print(f"Generated blog-index.json: {len(entries)} entries")
    print(f"  Categories: {', '.join(f'{k}={v}' for k, v in sorted(categories.items()))}")

    if args.stats:
        print(f"  Tiers: {', '.join(f'T{k}={v}' for k, v in sorted(tiers.items()))}")
        print(f"  Date range: {entries[-1]['date']} to {entries[0]['date']}")
        print(f"  Output: {args.output_dir / 'blog-index.json'}")


if __name__ == "__main__":
    main()
