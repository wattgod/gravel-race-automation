#!/usr/bin/env python3
"""Generate RSS 2.0 feed for the Gravel God race database.

Produces web/feed/races.xml with all 328 races as items, sorted by tier (T1 first)
then by score descending. Cycling blogs and aggregators can subscribe to get
race data in their feed readers.

Usage:
    python scripts/generate_rss_feed.py           # Generate feed
    python scripts/generate_rss_feed.py --dry-run  # Preview only
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
INDEX_FILE = PROJECT_ROOT / "web" / "race-index.json"
OUTPUT_DIR = PROJECT_ROOT / "web" / "feed"
OUTPUT_FILE = OUTPUT_DIR / "races.xml"
SITE_URL = "https://gravelgodcycling.com"


def _tier_label(tier):
    return f"Tier {tier}"


def _build_description(race, full_data):
    """Build an HTML description for a race RSS item."""
    r = full_data.get("race", full_data) if full_data else {}
    rating = r.get("gravel_god_rating", {})
    vitals = r.get("vitals", {})

    parts = []
    parts.append(f"<strong>{_tier_label(race['tier'])}</strong> &mdash; Score: {race['overall_score']}/100")

    if race.get("location"):
        parts.append(f"Location: {xml_escape(race['location'])}")

    date_str = vitals.get("date_specific", vitals.get("date", ""))
    if date_str:
        parts.append(f"Date: {xml_escape(date_str)}")

    if race.get("distance_mi"):
        parts.append(f"Distance: {race['distance_mi']} miles")
    if race.get("elevation_ft"):
        try:
            parts.append(f"Elevation: {int(race['elevation_ft']):,} ft")
        except (ValueError, TypeError):
            parts.append(f"Elevation: {race['elevation_ft']} ft")

    tagline = race.get("tagline", "")
    if tagline:
        parts.append(f"<em>{xml_escape(tagline)}</em>")

    final_verdict = rating.get("final_verdict", {})
    one_liner = final_verdict.get("one_liner", "")
    if one_liner:
        parts.append(xml_escape(one_liner))

    return "<br/>".join(parts)


def generate_rss():
    """Generate RSS 2.0 XML content."""
    index = json.loads(INDEX_FILE.read_text())

    # Sort: T1 first, then by score descending
    index.sort(key=lambda r: (r["tier"], -r["overall_score"]))

    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    items = []
    for race in index:
        slug = race["slug"]
        race_file = RACE_DATA_DIR / f"{slug}.json"
        full_data = None
        if race_file.exists():
            full_data = json.loads(race_file.read_text())

        profile_url = f"{SITE_URL}/race/{slug}/"
        title = f"{race['name']} — {_tier_label(race['tier'])}, {race['overall_score']}/100"
        description = _build_description(race, full_data)

        # Use file mtime as pubDate for freshness signal
        if race_file.exists():
            mtime = datetime.fromtimestamp(race_file.stat().st_mtime, tz=timezone.utc)
            pub_date = mtime.strftime("%a, %d %b %Y %H:%M:%S +0000")
        else:
            pub_date = now

        # Categories
        categories = [f"Tier {race['tier']}"]
        if race.get("region"):
            categories.append(race["region"])
        if race.get("month"):
            categories.append(race["month"])
        discipline = race.get("discipline", "gravel")
        if discipline:
            categories.append(discipline)

        cat_xml = "".join(f"      <category>{xml_escape(c)}</category>\n" for c in categories)

        items.append(f"""    <item>
      <title>{xml_escape(title)}</title>
      <link>{profile_url}</link>
      <guid isPermaLink="true">{profile_url}</guid>
      <description><![CDATA[{description}]]></description>
      <pubDate>{pub_date}</pubDate>
{cat_xml}    </item>""")

    items_xml = "\n".join(items)

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>Gravel God — Race Database</title>
    <link>{SITE_URL}/gravel-races/</link>
    <description>328 gravel races rated and ranked on 14 criteria. Tier ratings, scores, locations, dates, and course details.</description>
    <language>en-us</language>
    <lastBuildDate>{now}</lastBuildDate>
    <atom:link href="{SITE_URL}/feed/races.xml" rel="self" type="application/rss+xml"/>
    <image>
      <url>{SITE_URL}/wp-content/uploads/2023/01/gravel-god-logo.png</url>
      <title>Gravel God</title>
      <link>{SITE_URL}</link>
    </image>
{items_xml}
  </channel>
</rss>
"""
    return rss


def main():
    parser = argparse.ArgumentParser(description="Generate RSS feed for race database")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview only, don't write file")
    args = parser.parse_args()

    print("Generating RSS feed...")
    rss_content = generate_rss()
    print(f"  Feed size: {len(rss_content):,} bytes")

    # Count items
    item_count = rss_content.count("<item>")
    print(f"  Items: {item_count}")

    if args.dry_run:
        print(f"\n  [dry run] Would write to {OUTPUT_FILE}")
        return 0

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(rss_content)
    print(f"  Wrote: {OUTPUT_FILE}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
