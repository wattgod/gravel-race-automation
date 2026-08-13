#!/usr/bin/env python3
"""Generate the Gravel God change wire and its RSS feed."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET

from brand_tokens import get_font_face_css, get_ga4_head_snippet, get_tokens_css
from cookie_consent import get_consent_banner_html
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_css, get_site_header_html, get_site_header_js

ROOT = Path(__file__).resolve().parent.parent
INTEL_PATH = ROOT / "web" / "race-intel.json"
INDEX_PATH = ROOT / "web" / "race-index.json"
OUTPUT_PATH = ROOT / "wordpress" / "output" / "latest" / "index.html"
RSS_PATH = ROOT / "web" / "feed" / "latest.xml"
SITE = "https://gravelgodcycling.com"


def flatten_events(intel: dict, race_index: list[dict], today: date | None = None) -> list[dict]:
    """Return valid events newest-first, limited to the current 12-month window."""
    today = today or date.today()
    names = {r.get("slug"): r.get("name") for r in race_index}
    earliest_month = today.year * 12 + today.month - 11
    rows = []
    for slug, events in intel.items():
        if not names.get(slug) or not isinstance(events, list):
            continue
        for event in events:
            try:
                event_date = date.fromisoformat(str(event.get("date", "")))
            except (TypeError, ValueError):
                continue
            month_number = event_date.year * 12 + event_date.month
            text = event.get("text")
            if earliest_month <= month_number <= today.year * 12 + today.month and isinstance(text, str) and text.strip():
                rows.append({"date": event_date, "slug": slug, "name": names[slug], "text": text.strip()})
    return sorted(rows, key=lambda row: (row["date"], row["slug"], row["text"]), reverse=True)


def _wire_markup(events: list[dict]) -> str:
    if not events:
        return '<p class="gg-wire-empty">No verified changes yet.</p>'
    months: dict[str, dict[date, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for event in events:
        months[event["date"].strftime("%Y-%m")][event["date"]].append(event)
    sections = []
    for month, days in months.items():
        month_label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        day_rows = []
        for day, rows in days.items():
            entries = "".join(
                f'<li><time datetime="{day.isoformat()}">{day.strftime("%b %d")}</time>'
                f'<a href="/race/{escape(row["slug"], quote=True)}/">{escape(row["name"])}</a>'
                f'<span>{escape(row["text"])}</span></li>' for row in rows
            )
            day_rows.append(f'<ol class="gg-wire-day" aria-label="{day.isoformat()}">{entries}</ol>')
        sections.append(f'<section class="gg-wire-month" id="{month}"><h2>{month_label}</h2>{"".join(day_rows)}</section>')
    return "".join(sections)


def render_page(intel: dict, race_index: list[dict], today: date | None = None) -> str:
    events = flatten_events(intel, race_index, today)
    css = f"""<style>{get_tokens_css()}{get_font_face_css('/race/assets/fonts')}{get_site_header_css()}
body{{margin:0;background:var(--gg-color-cream);color:var(--gg-color-dark-brown)}}
.gg-wire{{max-width:1080px;margin:0 auto;padding:var(--gg-spacing-xl) var(--gg-spacing-md)}}
.gg-wire h1,.gg-wire h2{{font-family:var(--gg-font-data);text-transform:uppercase}}
.gg-wire h1{{font-size:clamp(2rem,8vw,5rem);margin:0;border-bottom:var(--gg-border-thick);padding-bottom:var(--gg-spacing-sm)}}
.gg-wire-intro{{font-family:var(--gg-font-editorial);font-size:var(--gg-font-size-lg);margin:var(--gg-spacing-md) 0 var(--gg-spacing-xl)}}
.gg-wire-month{{scroll-margin-top:var(--gg-header-height,80px);margin:0 0 var(--gg-spacing-xl)}}
.gg-wire-month h2{{font-size:var(--gg-font-size-lg);border-bottom:var(--gg-border-standard);padding-bottom:var(--gg-spacing-xs)}}
.gg-wire-day{{list-style:none;margin:0;padding:0}}
.gg-wire-day li{{display:grid;grid-template-columns:90px minmax(180px,260px) 1fr;gap:var(--gg-spacing-sm);padding:var(--gg-spacing-sm) 0;border-bottom:1px solid var(--gg-color-tan);font-family:var(--gg-font-data);font-size:var(--gg-font-size-sm);line-height:1.5}}
.gg-wire-day time{{color:var(--gg-color-secondary-brown)}}.gg-wire-day a{{color:var(--gg-color-dark-brown);font-weight:700;text-underline-offset:3px}}.gg-wire-empty{{font-family:var(--gg-font-data);border:var(--gg-border-standard);padding:var(--gg-spacing-md)}}
@media(max-width:700px){{.gg-wire-day li{{grid-template-columns:72px 1fr}}.gg-wire-day li span{{grid-column:1/-1}}}}
</style>"""
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Latest Race Database Changes | Gravel God</title><meta name="description" content="Every verified Gravel God race database change, newest first."><meta name="robots" content="index, follow">
<link rel="canonical" href="{SITE}/latest/"><link rel="alternate" type="application/rss+xml" title="Gravel God Latest" href="{SITE}/feed/latest.xml">
{css}{get_ga4_head_snippet()}</head><body>{get_site_header_html()}
<main class="gg-wire"><h1>Latest</h1><p class="gg-wire-intro">Every verified change to the race database, newest first.</p>{_wire_markup(events)}</main>
{get_mega_footer_html()}<script>{get_site_header_js()}</script>{get_consent_banner_html()}</body></html>'''


def render_rss(intel: dict, race_index: list[dict], today: date | None = None) -> str:
    events = flatten_events(intel, race_index, today)[:50]
    now = datetime.now(timezone.utc)
    rss = ET.Element("rss", {"version": "2.0", "xmlns:atom": "http://www.w3.org/2005/Atom"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Gravel God — Latest Race Database Changes"
    ET.SubElement(channel, "link").text = f"{SITE}/latest/"
    ET.SubElement(channel, "description").text = "Every verified change to the race database, newest first."
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(now)
    ET.SubElement(channel, "{http://www.w3.org/2005/Atom}link", {"href": f"{SITE}/feed/latest.xml", "rel": "self", "type": "application/rss+xml"})
    for event in events:
        anchor = event["date"].strftime("%Y-%m")
        url = f'{SITE}/race/{event["slug"]}/#{anchor}'
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f'{event["name"]}: {event["text"]}'
        ET.SubElement(item, "link").text = url
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = f'{url}:{event["date"].isoformat()}:{event["text"]}'
        ET.SubElement(item, "description").text = event["text"]
        dt = datetime.combine(event["date"], datetime.min.time(), tzinfo=timezone.utc)
        ET.SubElement(item, "pubDate").text = format_datetime(dt)
    ET.indent(rss)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode") + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intel", type=Path, default=INTEL_PATH)
    parser.add_argument("--index", type=Path, default=INDEX_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--rss-output", type=Path, default=RSS_PATH)
    args = parser.parse_args()
    intel = json.loads(args.intel.read_text()) if args.intel.exists() else {}
    race_index = json.loads(args.index.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.rss_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_page(intel, race_index), encoding="utf-8")
    args.rss_output.write_text(render_rss(intel, race_index), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {args.rss_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
