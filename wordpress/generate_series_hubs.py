#!/usr/bin/env python3
"""
Generate series hub landing pages for SEO.

Creates one page per series at /race/series/{slug}/index.html with
hero, overview, history, format, event calendar, and JSON-LD.

Usage:
    python wordpress/generate_series_hubs.py
    python wordpress/generate_series_hubs.py --output-dir /tmp/gg-test
"""

import argparse
import html as html_mod
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import COLORS, GA_MEASUREMENT_ID, get_font_face_css, get_tokens_css

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERIES_DIR = PROJECT_ROOT / "series-data"
SITE_BASE_URL = "https://gravelgodcycling.com"

# Month order for sorting events chronologically
MONTH_ORDER = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
    "TBD": 99,
}


def esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def load_race_index() -> dict:
    """Load race index and return dict keyed by slug."""
    index_path = PROJECT_ROOT / "web" / "race-index.json"
    if not index_path.exists():
        return {}
    with open(index_path, "r", encoding="utf-8") as f:
        races = json.load(f)
    return {r["slug"]: r for r in races if r.get("slug")}


def build_event_card(event: dict, race_lookup: dict) -> str:
    """Build an event card for the calendar section."""
    name = event.get("name", "")
    slug = event.get("slug")
    location = event.get("location", "")
    month = event.get("month", "TBD")
    has_profile = event.get("has_profile", False)

    # Pull tier from index if available
    tier_badge = ""
    score_html = ""
    if slug and slug in race_lookup:
        race = race_lookup[slug]
        tier = race.get("tier", 0)
        score = race.get("overall_score", 0)
        if tier:
            tier_badge = f'<span class="gg-series-event-tier gg-tier-{tier}">T{tier}</span>'
        if score:
            score_html = f'<span class="gg-series-event-score">{score}</span>'

    if has_profile and slug:
        name_html = f'<a href="/race/{esc(slug)}/" class="gg-series-event-name">{esc(name)}</a>'
        link_icon = ' <span class="gg-series-event-link">&#8599;</span>'
    else:
        name_html = f'<span class="gg-series-event-name">{esc(name)}</span>'
        link_icon = ""

    return f'''<div class="gg-series-event-card">
      <div class="gg-series-event-month">{esc(month)}</div>
      {name_html}{link_icon}
      <div class="gg-series-event-location">{esc(location)}</div>
      <div class="gg-series-event-badges">{tier_badge}{score_html}</div>
    </div>'''


def build_collapsible_section(title: str, content: str, section_id: str) -> str:
    """Build a collapsible content section."""
    if not content:
        return ""
    # Split into paragraphs
    paragraphs = content.strip().split("\n\n") if "\n\n" in content else [content]
    p_html = "\n".join(f"<p>{esc(p.strip())}</p>" for p in paragraphs if p.strip())
    return f'''<details class="gg-series-section" open>
    <summary class="gg-series-section-title">{esc(title)}</summary>
    <div class="gg-series-section-body">
      {p_html}
    </div>
  </details>'''


def build_hub_page(series: dict, race_lookup: dict) -> str:
    """Generate a full series hub page."""
    name = series.get("display_name") or series.get("name", "")
    slug = series.get("slug", "")
    tagline = series.get("tagline", "")
    founded = series.get("founded", "")
    organizer = series.get("organizer", "")
    website = series.get("website", "")
    description = series.get("description", "")
    history = series.get("history", "")
    format_overview = series.get("format_overview", "")
    events = series.get("events", [])
    key_stats = series.get("key_stats", {})

    total_events = key_stats.get("total_events", len(events))
    countries = key_stats.get("countries", 1)

    # Sort events by month
    sorted_events = sorted(events, key=lambda e: MONTH_ORDER.get(e.get("month", "TBD"), 99))

    # Build event cards
    cards_html = []
    for event in sorted_events:
        cards_html.append(build_event_card(event, race_lookup))
    cards = "\n    ".join(cards_html)

    # Build JSON-LD: SportsOrganization + ItemList
    item_list_entries = []
    for i, event in enumerate(sorted_events, 1):
        event_slug = event.get("slug")
        event_url = f"{SITE_BASE_URL}/race/{event_slug}/" if event_slug and event.get("has_profile") else ""
        entry = {
            "@type": "ListItem",
            "position": i,
            "name": event.get("name", ""),
        }
        if event_url:
            entry["url"] = event_url
        item_list_entries.append(json.dumps(entry, ensure_ascii=False))
    item_list_json = ",\n      ".join(item_list_entries)

    canonical = f"{SITE_BASE_URL}/race/series/{slug}/"
    page_title = f"{name} — All Events & Series Guide | Gravel God"
    meta_desc = tagline if tagline else f"Complete guide to the {name} race series."

    # Stats line for hero
    country_text = f"{countries} {'country' if countries == 1 else 'countries'}"
    stats_parts = [f"{total_events} events", country_text]
    if founded:
        stats_parts.append(f"Est. {founded}")
    stats_line = " &middot; ".join(stats_parts)

    # Website button
    site_btn = ""
    if website:
        site_btn = f'\n    <a href="{esc(website)}" class="gg-btn gg-btn--series-site" target="_blank" rel="noopener">OFFICIAL SITE &rarr;</a>'

    # Sections
    overview_section = build_collapsible_section("Overview", description, "overview")
    history_section = build_collapsible_section("History", history, "history")
    format_section = build_collapsible_section("Format", format_overview, "format")

    font_face = get_font_face_css()
    tokens = get_tokens_css()

    teal = COLORS["teal"]

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(page_title)}</title>
  <meta name="description" content="{esc(meta_desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='%233a2e25'/><text x='16' y='24' text-anchor='middle' font-family='serif' font-size='24' font-weight='700' fill='%239a7e0a'>G</text></svg>">
  <meta property="og:title" content="{esc(page_title)}">
  <meta property="og:description" content="{esc(meta_desc)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical)}">
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "SportsOrganization",
    "name": "{esc(name)}",
    "description": "{esc(meta_desc)}",
    "url": "{esc(canonical)}",
    "sport": "Cycling",
    "foundingDate": "{founded}"
  }}
  </script>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{
        "@type": "ListItem",
        "position": 1,
        "name": "Home",
        "item": "{SITE_BASE_URL}/"
      }},
      {{
        "@type": "ListItem",
        "position": 2,
        "name": "Gravel Races",
        "item": "{SITE_BASE_URL}/gravel-races/"
      }},
      {{
        "@type": "ListItem",
        "position": 3,
        "name": "Series",
        "item": "{SITE_BASE_URL}/race/series/"
      }},
      {{
        "@type": "ListItem",
        "position": 4,
        "name": "{esc(name)}",
        "item": "{esc(canonical)}"
      }}
    ]
  }}
  </script>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": "{esc(name)} Events",
    "numberOfItems": {len(events)},
    "itemListElement": [
      {item_list_json}
    ]
  }}
  </script>
  <style>
{font_face}
{tokens}

.gg-series-page {{
  max-width: 960px;
  margin: 0 auto;
  padding: 0 24px;
  font-family: var(--gg-font-data);
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-warm-paper);
  min-height: 100vh;
}}
.gg-series-page *, .gg-series-page *::before, .gg-series-page *::after {{
  border-radius: 0 !important;
  box-shadow: none !important;
}}

/* Site header */
.gg-site-header {{
  padding: 16px 24px;
  border-bottom: 4px solid var(--gg-color-dark-brown);
}}
.gg-site-header-inner {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 960px;
  margin: 0 auto;
}}
.gg-site-header-logo img {{
  display: block;
  height: 50px;
  width: auto;
}}
.gg-site-header-nav {{
  display: flex;
  gap: 28px;
}}
.gg-site-header-nav a {{
  color: var(--gg-color-dark-brown);
  text-decoration: none;
  font-family: 'Sometype Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
}}
.gg-site-header-nav a:hover {{
  color: var(--gg-color-gold);
}}

/* Breadcrumb */
.gg-series-breadcrumb {{
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  padding: 12px 0;
  letter-spacing: 0.5px;
}}
.gg-series-breadcrumb a {{
  color: var(--gg-color-secondary-brown);
  text-decoration: none;
}}
.gg-series-breadcrumb a:hover {{
  color: var(--gg-color-dark-brown);
}}

/* Hero */
.gg-series-hero {{
  background: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
  padding: 48px 32px;
  margin: 0 -24px;
  border-bottom: 4px double var(--gg-color-dark-brown);
}}
.gg-series-hero-badge {{
  display: inline-block;
  background: transparent;
  color: {teal};
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  border: 2px solid {teal};
  margin-bottom: 16px;
}}
.gg-series-hero-founded {{
  display: inline-block;
  margin-left: 12px;
  font-size: 11px;
  color: var(--gg-color-tan);
  letter-spacing: 1px;
}}
.gg-series-hero h1 {{
  font-family: var(--gg-font-editorial);
  font-size: 36px;
  font-weight: 700;
  line-height: 1.1;
  margin: 0 0 12px 0;
}}
.gg-series-hero-stats {{
  font-size: 13px;
  color: var(--gg-color-tan);
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 12px;
}}
.gg-series-hero-tagline {{
  font-family: var(--gg-font-editorial);
  font-size: 16px;
  line-height: 1.5;
  color: var(--gg-color-sand);
  max-width: 720px;
  margin-bottom: 16px;
}}
.gg-btn--series-site {{
  display: inline-block;
  padding: 8px 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  text-decoration: none;
  color: var(--gg-color-warm-paper);
  border: 2px solid var(--gg-color-warm-paper);
  transition: background 0.15s, color 0.15s;
}}
.gg-btn--series-site:hover {{
  background: var(--gg-color-warm-paper);
  color: var(--gg-color-dark-brown);
}}

/* Collapsible sections */
.gg-series-section {{
  border-bottom: 2px solid var(--gg-color-sand);
  padding: 0;
}}
.gg-series-section-title {{
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  padding: 16px 0;
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.gg-series-section-title::after {{
  content: "\\25BC";
  font-size: 9px;
  transition: transform 0.2s;
}}
.gg-series-section[open] .gg-series-section-title::after {{
  transform: rotate(180deg);
}}
.gg-series-section-title::-webkit-details-marker {{
  display: none;
}}
.gg-series-section-body {{
  padding: 0 0 20px 0;
}}
.gg-series-section-body p {{
  font-family: var(--gg-font-editorial);
  font-size: 16px;
  line-height: 1.7;
  color: var(--gg-color-dark-brown);
  max-width: 720px;
  margin: 0 0 16px 0;
}}
.gg-series-section-body p:last-child {{
  margin-bottom: 0;
}}

/* Event calendar */
.gg-series-calendar-title {{
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  padding: 24px 0 16px;
  border-bottom: 2px solid var(--gg-color-dark-brown);
}}
.gg-series-calendar {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0;
}}
.gg-series-event-card {{
  padding: 16px;
  border-bottom: 2px solid var(--gg-color-sand);
  border-right: 2px solid var(--gg-color-sand);
  transition: background 0.15s;
}}
.gg-series-event-card:hover {{
  background: var(--gg-color-sand);
}}
.gg-series-event-month {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: {teal};
  margin-bottom: 6px;
}}
.gg-series-event-name {{
  font-family: var(--gg-font-editorial);
  font-size: 15px;
  font-weight: 700;
  color: var(--gg-color-dark-brown);
  text-decoration: none;
  display: block;
  margin-bottom: 4px;
}}
a.gg-series-event-name:hover {{
  color: var(--gg-color-gold);
}}
.gg-series-event-link {{
  font-size: 12px;
  color: var(--gg-color-gold);
}}
.gg-series-event-location {{
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}}
.gg-series-event-badges {{
  display: flex;
  gap: 6px;
  align-items: center;
}}
.gg-series-event-tier {{
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 2px 6px;
  border: 1px solid var(--gg-color-secondary-brown);
  color: var(--gg-color-secondary-brown);
}}
.gg-series-event-score {{
  font-family: var(--gg-font-editorial);
  font-size: 14px;
  font-weight: 700;
  color: var(--gg-color-dark-brown);
}}

/* Footer */
.gg-series-footer {{
  padding: 24px 0;
  margin-top: 32px;
  border-top: 4px double var(--gg-color-dark-brown);
  text-align: center;
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 1px;
  text-transform: uppercase;
}}
.gg-series-footer a {{
  color: var(--gg-color-secondary-brown);
  text-decoration: none;
}}
.gg-series-footer a:hover {{
  color: var(--gg-color-dark-brown);
}}

/* Mobile */
@media (max-width: 768px) {{
  .gg-series-hero {{ padding: 32px 20px; }}
  .gg-series-hero h1 {{ font-size: 28px; }}
  .gg-site-header-nav {{ gap: 12px; }}
  .gg-site-header-nav a {{ font-size: 10px; letter-spacing: 1.5px; }}
  .gg-series-calendar {{ grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); }}
}}
@media (max-width: 480px) {{
  .gg-series-page {{ padding: 0 12px; }}
  .gg-series-hero {{ padding: 24px 12px; margin: 0 -12px; }}
  .gg-series-hero h1 {{ font-size: 22px; }}
  .gg-series-calendar {{ grid-template-columns: 1fr; }}
  .gg-series-event-card {{ border-right: none; }}
  .gg-site-header {{ padding: 12px 16px; }}
  .gg-site-header-inner {{ flex-wrap: wrap; justify-content: center; gap: 10px; }}
  .gg-site-header-logo img {{ height: 40px; }}
  .gg-site-header-nav {{ flex-wrap: wrap; justify-content: center; gap: 8px; }}
}}
  </style>
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>
</head>
<body style="margin:0;background:var(--gg-color-warm-paper)">

<div class="gg-series-page">

  <header class="gg-site-header">
    <div class="gg-site-header-inner">
      <a href="/" class="gg-site-header-logo">
        <img src="https://gravelgodcycling.com/wp-content/uploads/2021/09/cropped-Gravel-God-logo.png" alt="Gravel God" width="50" height="50">
      </a>
      <nav class="gg-site-header-nav">
        <a href="/gravel-races/">RACES</a>
        <a href="/coaching/">COACHING</a>
        <a href="/articles/">ARTICLES</a>
        <a href="/about/">ABOUT</a>
      </nav>
    </div>
  </header>

  <div class="gg-series-breadcrumb">
    <a href="/">Home</a> &rsaquo;
    <a href="/gravel-races/">Gravel Races</a> &rsaquo;
    <a href="/race/series/">Series</a> &rsaquo;
    <span>{esc(name)}</span>
  </div>

  <section class="gg-series-hero">
    <span class="gg-series-hero-badge">SERIES</span>
    {"<span class='gg-series-hero-founded'>Founded: " + str(founded) + "</span>" if founded else ""}
    <h1>{esc(name)}</h1>
    <div class="gg-series-hero-stats">{stats_line}</div>
    <p class="gg-series-hero-tagline">{esc(tagline)}</p>{site_btn}
  </section>

  {overview_section}
  {history_section}
  {format_section}

  <div class="gg-series-calendar-title">2026 Event Calendar</div>
  <div class="gg-series-calendar">
    {cards}
  </div>

  <footer class="gg-series-footer">
    <a href="/">Gravel God</a> &middot;
    <a href="/gravel-races/">Search All Races</a> &middot;
    <a href="/race/methodology/">Methodology</a>
  </footer>

</div>

</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate series hub landing pages")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: wordpress/output/race/series/)")
    args = parser.parse_args()

    output_base = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / "wordpress" / "output" / "race" / "series"
    output_base.mkdir(parents=True, exist_ok=True)

    if not SERIES_DIR.exists():
        print("ERROR: series-data/ not found. Create series definitions first.", file=sys.stderr)
        sys.exit(1)

    # Load race index for enriching event cards
    race_lookup = load_race_index()
    if race_lookup:
        print(f"Loaded {len(race_lookup)} races from index")
    else:
        print("WARN: No race index found. Event cards will lack tier/score data.")

    series_files = sorted(SERIES_DIR.glob("*.json"))
    if not series_files:
        print("ERROR: No series JSON files found in series-data/", file=sys.stderr)
        sys.exit(1)

    for path in series_files:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        series = data.get("series", {})
        slug = series.get("slug", "")
        if not slug:
            print(f"  SKIP {path.name} (no slug)")
            continue

        hub_dir = output_base / slug
        hub_dir.mkdir(parents=True, exist_ok=True)

        page_html = build_hub_page(series, race_lookup)
        out_path = hub_dir / "index.html"
        out_path.write_text(page_html, encoding="utf-8")

        event_count = len(series.get("events", []))
        print(f"  Generated series/{slug}/index.html ({event_count} events)")

    print(f"\nDone. {len(series_files)} series hub pages in {output_base}/")


if __name__ == "__main__":
    main()
