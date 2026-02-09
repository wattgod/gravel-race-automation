#!/usr/bin/env python3
"""
Generate XML sitemap for gravel race landing pages.

Usage:
    python scripts/generate_sitemap.py
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


def generate_sitemap(race_index: list, output_path: Path, data_dir: Path = None) -> Path:
    today = date.today().isoformat()

    urlset = Element('urlset')
    urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')

    # Homepage
    url = SubElement(urlset, 'url')
    SubElement(url, 'loc').text = f"{SITE_BASE_URL}/"
    SubElement(url, 'lastmod').text = today
    SubElement(url, 'changefreq').text = 'weekly'
    SubElement(url, 'priority').text = '1.0'

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


def main():
    parser = argparse.ArgumentParser(description='Generate XML sitemap')
    parser.add_argument('--output-dir', type=Path, help='Output directory')
    parser.add_argument('--data-dir', type=Path, help='Race data directory for file-based lastmod dates')
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

    generate_sitemap(race_index, output_path, data_dir)
    print(f"Generated sitemap: {output_path} ({len(race_index) + 1} URLs)")
    if data_dir:
        print(f"  Using file mtimes from: {data_dir}")


if __name__ == '__main__':
    main()
