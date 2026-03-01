#!/usr/bin/env python3
"""
Generate XML sitemaps for gravel race landing pages and blog content.

Usage:
    python scripts/generate_sitemap.py
    python scripts/generate_sitemap.py --blog
    python scripts/generate_sitemap.py --output-dir web/
    python scripts/generate_sitemap.py --data-dir race-data/
"""

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

SITE_BASE_URL = "https://gravelgodcycling.com"


def load_series_slugs(project_root: Path) -> list:
    """Load series slugs from series-data/ directory."""
    series_dir = project_root / "series-data"
    slugs = []
    if not series_dir.exists():
        return slugs
    for path in sorted(series_dir.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            slug = data.get("series", {}).get("slug", "")
            if slug:
                slugs.append(slug)
        except (json.JSONDecodeError, KeyError):
            continue
    return slugs


def load_vs_slugs(project_root: Path) -> list:
    """Load vs page slugs from wordpress/output/ directory."""
    output_dir = project_root / "wordpress" / "output"
    slugs = []
    if not output_dir.exists():
        return slugs
    for path in sorted(output_dir.iterdir()):
        if path.is_dir() and "-vs-" in path.name:
            slugs.append(path.name)
    return slugs


def load_state_slugs(project_root: Path) -> list:
    """Load state hub page slugs from wordpress/output/ directory."""
    output_dir = project_root / "wordpress" / "output"
    slugs = []
    if not output_dir.exists():
        return slugs
    for path in sorted(output_dir.iterdir()):
        if path.is_dir() and path.name.startswith("best-gravel-races-"):
            slugs.append(path.name)
    return slugs


def load_tire_slugs(project_root: Path) -> list:
    """Load tire guide page slugs from wordpress/output/tires/ directory."""
    tires_dir = project_root / "wordpress" / "output" / "tires"
    slugs = []
    if not tires_dir.exists():
        return slugs
    for path in sorted(tires_dir.glob("*.html")):
        slugs.append(path.stem)
    return slugs


def load_tire_page_slugs(project_root: Path) -> list:
    """Load per-tire page slugs from wordpress/output/tire/ directory."""
    tire_dir = project_root / "wordpress" / "output" / "tire"
    slugs = []
    if not tire_dir.exists():
        return slugs
    for path in sorted(tire_dir.iterdir()):
        if path.is_dir() and "-vs-" not in path.name:
            slugs.append(path.name)
    return slugs


def load_tire_vs_slugs(project_root: Path) -> list:
    """Load tire-vs-tire comparison page slugs from wordpress/output/tire/ directory."""
    tire_dir = project_root / "wordpress" / "output" / "tire"
    slugs = []
    if not tire_dir.exists():
        return slugs
    for path in sorted(tire_dir.iterdir()):
        if path.is_dir() and "-vs-" in path.name:
            slugs.append(path.name)
    return slugs


def load_special_pages(project_root: Path) -> list:
    """Load calendar/power-rankings/quiz page slugs."""
    output_dir = project_root / "wordpress" / "output"
    slugs = []
    for pattern in ["calendar", "power-rankings-*", "quiz"]:
        import glob as glob_mod
        for path in sorted(output_dir.glob(pattern)):
            if path.is_dir():
                # May be nested (calendar/2026)
                for sub in sorted(path.rglob("index.html")):
                    rel = sub.parent.relative_to(output_dir)
                    slugs.append(str(rel))
    return slugs


def generate_sitemap(race_index: list, output_path: Path, data_dir: Path = None,
                     series_slugs: list = None) -> Path:
    today = date.today().isoformat()

    urlset = Element('urlset')
    urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')

    # Homepage
    url = SubElement(urlset, 'url')
    SubElement(url, 'loc').text = f"{SITE_BASE_URL}/"
    SubElement(url, 'lastmod').text = today
    SubElement(url, 'changefreq').text = 'weekly'
    SubElement(url, 'priority').text = '1.0'

    # Gravel Races search page
    url = SubElement(urlset, 'url')
    SubElement(url, 'loc').text = f"{SITE_BASE_URL}/gravel-races/"
    SubElement(url, 'lastmod').text = today
    SubElement(url, 'changefreq').text = 'weekly'
    SubElement(url, 'priority').text = '0.9'

    # Methodology page
    url = SubElement(urlset, 'url')
    SubElement(url, 'loc').text = f"{SITE_BASE_URL}/race/methodology/"
    SubElement(url, 'lastmod').text = today
    SubElement(url, 'changefreq').text = 'monthly'
    SubElement(url, 'priority').text = '0.8'

    # Tier hub pages
    for t in [1, 2, 3, 4]:
        url = SubElement(urlset, 'url')
        SubElement(url, 'loc').text = f"{SITE_BASE_URL}/race/tier-{t}/"
        SubElement(url, 'lastmod').text = today
        SubElement(url, 'changefreq').text = 'weekly'
        SubElement(url, 'priority').text = '0.8'

    # Series hub pages
    for slug in (series_slugs or []):
        url = SubElement(urlset, 'url')
        SubElement(url, 'loc').text = f"{SITE_BASE_URL}/race/series/{slug}/"
        SubElement(url, 'lastmod').text = today
        SubElement(url, 'changefreq').text = 'monthly'
        SubElement(url, 'priority').text = '0.8'

    # VS comparison pages
    vs_slugs = load_vs_slugs(output_path.parent.parent)
    for slug in vs_slugs:
        url = SubElement(urlset, 'url')
        SubElement(url, 'loc').text = f"{SITE_BASE_URL}/race/{slug}/"
        SubElement(url, 'lastmod').text = today
        SubElement(url, 'changefreq').text = 'monthly'
        SubElement(url, 'priority').text = '0.6'

    # State/region hub pages
    state_slugs = load_state_slugs(output_path.parent.parent)
    for slug in state_slugs:
        url = SubElement(urlset, 'url')
        SubElement(url, 'loc').text = f"{SITE_BASE_URL}/race/{slug}/"
        SubElement(url, 'lastmod').text = today
        SubElement(url, 'changefreq').text = 'monthly'
        SubElement(url, 'priority').text = '0.7'

    # Special pages (calendar, power rankings)
    special_slugs = load_special_pages(output_path.parent.parent)
    for slug in special_slugs:
        url = SubElement(urlset, 'url')
        SubElement(url, 'loc').text = f"{SITE_BASE_URL}/race/{slug}/"
        SubElement(url, 'lastmod').text = today
        SubElement(url, 'changefreq').text = 'weekly'
        SubElement(url, 'priority').text = '0.8'

    # Tire guide pages
    tire_slugs = load_tire_slugs(output_path.parent.parent)
    for slug in tire_slugs:
        url = SubElement(urlset, 'url')
        SubElement(url, 'loc').text = f"{SITE_BASE_URL}/race/{slug}/tires/"
        SubElement(url, 'lastmod').text = today
        SubElement(url, 'changefreq').text = 'monthly'
        SubElement(url, 'priority').text = '0.6'

    # Per-tire review pages
    tire_page_slugs = load_tire_page_slugs(output_path.parent.parent)
    for slug in tire_page_slugs:
        url = SubElement(urlset, 'url')
        SubElement(url, 'loc').text = f"{SITE_BASE_URL}/tire/{slug}/"
        SubElement(url, 'lastmod').text = today
        SubElement(url, 'changefreq').text = 'monthly'
        SubElement(url, 'priority').text = '0.6'

    # Tire-vs-tire comparison pages
    tire_vs_slugs = load_tire_vs_slugs(output_path.parent.parent)
    for slug in tire_vs_slugs:
        url = SubElement(urlset, 'url')
        SubElement(url, 'loc').text = f"{SITE_BASE_URL}/tire/{slug}/"
        SubElement(url, 'lastmod').text = today
        SubElement(url, 'changefreq').text = 'monthly'
        SubElement(url, 'priority').text = '0.5'

    # Race pages
    for race in race_index:
        slug = race.get('slug', '')
        if not slug:
            continue
        tier = race.get('tier', 4)
        priority = {1: '0.9', 2: '0.8', 3: '0.6', 4: '0.5'}.get(tier, '0.5')

        # Use file mtime if data_dir provided
        lastmod = today
        if data_dir:
            data_file = data_dir / f"{slug}.json"
            if data_file.exists():
                mtime = os.path.getmtime(data_file)
                lastmod = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d')

        url = SubElement(urlset, 'url')
        SubElement(url, 'loc').text = f"{SITE_BASE_URL}/race/{slug}/"
        SubElement(url, 'lastmod').text = lastmod
        SubElement(url, 'changefreq').text = 'monthly'
        SubElement(url, 'priority').text = priority

    raw_xml = tostring(urlset, encoding='unicode')
    pretty = parseString(raw_xml).toprettyxml(indent='  ', encoding='UTF-8')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pretty)
    return output_path


def generate_blog_sitemap(blog_index: list, output_path: Path) -> Path:
    """Generate XML sitemap for blog content.

    Args:
        blog_index: List of blog entry dicts from blog-index.json.
        output_path: Path to write blog-sitemap.xml.
    """
    today = date.today().isoformat()

    urlset = Element('urlset')
    urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')

    # Blog index page
    url = SubElement(urlset, 'url')
    SubElement(url, 'loc').text = f"{SITE_BASE_URL}/blog/"
    SubElement(url, 'lastmod').text = today
    SubElement(url, 'changefreq').text = 'weekly'
    SubElement(url, 'priority').text = '0.8'

    # Blog entries
    priority_map = {"roundup": "0.7", "preview": "0.6", "recap": "0.6"}
    for entry in blog_index:
        slug = entry.get("slug", "")
        if not slug:
            continue
        category = entry.get("category", "preview")
        priority = priority_map.get(category, "0.6")
        lastmod = entry.get("date", today)

        url = SubElement(urlset, 'url')
        SubElement(url, 'loc').text = f"{SITE_BASE_URL}/blog/{slug}/"
        SubElement(url, 'lastmod').text = lastmod
        SubElement(url, 'changefreq').text = 'monthly'
        SubElement(url, 'priority').text = priority

    raw_xml = tostring(urlset, encoding='unicode')
    pretty = parseString(raw_xml).toprettyxml(indent='  ', encoding='UTF-8')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pretty)
    return output_path


def main():
    parser = argparse.ArgumentParser(description='Generate XML sitemaps')
    parser.add_argument('--output-dir', type=Path, help='Output directory')
    parser.add_argument('--data-dir', type=Path, help='Race data directory for file-based lastmod dates')
    parser.add_argument('--blog', action='store_true', help='Also generate blog-sitemap.xml')
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    index_path = project_root / 'web' / 'race-index.json'
    if not index_path.exists():
        print(f"ERROR: Race index not found: {index_path}")
        sys.exit(1)

    with open(index_path) as f:
        race_index = json.load(f)

    output_dir = args.output_dir or project_root / 'web'
    output_path = output_dir / 'sitemap.xml'

    data_dir = args.data_dir
    if data_dir:
        data_dir = data_dir.resolve()

    series_slugs = load_series_slugs(project_root)
    generate_sitemap(race_index, output_path, data_dir, series_slugs=series_slugs)
    vs_slugs = load_vs_slugs(project_root)
    state_slugs = load_state_slugs(project_root)
    special_slugs = load_special_pages(project_root)
    tire_slugs = load_tire_slugs(project_root)
    tire_page_slugs = load_tire_page_slugs(project_root)
    tire_vs_slugs = load_tire_vs_slugs(project_root)
    total_urls = (7 + len(series_slugs) + len(vs_slugs) + len(state_slugs)
                  + len(special_slugs) + len(tire_slugs)
                  + len(tire_page_slugs) + len(tire_vs_slugs) + len(race_index))
    print(f"Generated sitemap: {output_path} ({total_urls} URLs)")
    if series_slugs:
        print(f"  Including {len(series_slugs)} series hub pages")
    if vs_slugs:
        print(f"  Including {len(vs_slugs)} vs comparison pages")
    if state_slugs:
        print(f"  Including {len(state_slugs)} state hub pages")
    if special_slugs:
        print(f"  Including {len(special_slugs)} special pages (calendar, rankings)")
    if tire_slugs:
        print(f"  Including {len(tire_slugs)} tire guide pages")
    if tire_page_slugs:
        print(f"  Including {len(tire_page_slugs)} per-tire review pages")
    if tire_vs_slugs:
        print(f"  Including {len(tire_vs_slugs)} tire-vs-tire comparison pages")
    if data_dir:
        print(f"  Using file mtimes from: {data_dir}")

    if args.blog:
        blog_index_path = project_root / 'web' / 'blog-index.json'
        if blog_index_path.exists():
            with open(blog_index_path) as f:
                blog_index = json.load(f)
            blog_output = output_dir / 'blog-sitemap.xml'
            generate_blog_sitemap(blog_index, blog_output)
            # Count: blog index page + all entries
            blog_urls = 1 + len(blog_index)
            print(f"Generated blog sitemap: {blog_output} ({blog_urls} URLs)")
        else:
            print(f"  SKIP blog sitemap: {blog_index_path} not found")
            print(f"  Run: python scripts/generate_blog_index.py first")


if __name__ == '__main__':
    main()
