#!/usr/bin/env python3
"""
Generate tier hub landing pages for SEO.

Creates 4 static pages at /race/tier-{1..4}/index.html with all races
in that tier. Targets "best gravel races", "bucket list gravel events",
"regional gravel races" type queries.

Usage:
    python wordpress/generate_tier_hubs.py
    python wordpress/generate_tier_hubs.py --output-dir /tmp/gg-test
"""

import argparse
import html as html_mod
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import COLORS, GA_MEASUREMENT_ID, get_font_face_css, get_tokens_css

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TIER_META = {
    1: {
        "name": "Elite",
        "slug": "tier-1",
        "title": "The 25 Best Gravel Races in the World | Gravel God",
        "h1": "Tier 1 — The Icons",
        "description": "The definitive gravel events. World-class fields, iconic courses, "
                       "and bucket-list status. These 25 races define the sport.",
        "intro": (
            "These are the races that define gravel cycling. Every Tier 1 event has earned "
            "its place through a combination of world-class competition, iconic terrain, "
            "deep community, and a reputation that transcends the sport. If you only race "
            "gravel a few times in your life, start here."
        ),
    },
    2: {
        "name": "Contender",
        "slug": "tier-2",
        "title": "73 Must-Do Gravel Races | Contender Tier | Gravel God",
        "h1": "Tier 2 — The Contenders",
        "description": "Established gravel races with strong reputations and competitive fields. "
                       "The next tier of must-do events for serious gravel riders.",
        "intro": (
            "Contender-tier races are the backbone of competitive gravel. Each one brings "
            "something distinctive — whether it's a legendary climb, a grassroots-to-big-time "
            "origin story, or a course that punches well above its profile. These are the races "
            "that regulars swear by and newcomers discover with delight."
        ),
    },
    3: {
        "name": "Solid",
        "slug": "tier-3",
        "title": "Regional Gravel Favorites | Solid Tier | Gravel God",
        "h1": "Tier 3 — Regional Favorites",
        "description": "Strong local scenes, genuine gravel character. Regional favorites "
                       "and emerging races worth the entry fee.",
        "intro": (
            "The Solid tier is where gravel gets personal. These are the races your local "
            "riding crew talks about all winter — the events that define a region's gravel "
            "identity. Smaller fields, raw courses, and the kind of post-race camaraderie "
            "that only happens when everyone shares the same mud-caked suffering."
        ),
    },
    4: {
        "name": "Roster",
        "slug": "tier-4",
        "title": "Grassroots Gravel Events | Roster Tier | Gravel God",
        "h1": "Tier 4 — Grassroots Gravel",
        "description": "Up-and-coming races and local grinders. Small fields, raw vibes, "
                       "and the future of the sport.",
        "intro": (
            "Every iconic race started somewhere. Tier 4 is the proving ground — the events "
            "where a handful of riders show up because someone with a Garmin and a dream "
            "mapped out a route. Low entry fees, zero pretense, and the purest expression "
            "of what gravel riding was always about."
        ),
    },
}


def esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def build_hub_page(tier: int, races: list, all_races: list) -> str:
    """Generate a full tier hub page."""
    meta = TIER_META[tier]
    tier_color = COLORS.get(f"tier_{tier}", COLORS["primary_brown"])

    # Sort races by score descending
    races = sorted(races, key=lambda r: r.get("overall_score", 0), reverse=True)

    # Build race cards
    cards_html = []
    for r in races:
        score = r.get("overall_score", 0)
        slug = r.get("slug", "")
        name = r.get("name", "")
        location = r.get("location", "")
        tagline = r.get("tagline", "")
        distance = r.get("distance_mi")
        elevation = r.get("elevation_ft")
        month = r.get("month", "")

        stat_parts = []
        if distance:
            stat_parts.append(f"{distance} mi")
        if elevation:
            try:
                stat_parts.append(f"{int(elevation):,} ft")
            except (ValueError, TypeError):
                stat_parts.append(f"{elevation} ft")
        if month:
            stat_parts.append(month)
        stats_line = " · ".join(stat_parts)

        cards_html.append(f'''<a href="/race/{esc(slug)}/" class="gg-hub-card">
      <div class="gg-hub-card-score">{score}</div>
      <div class="gg-hub-card-body">
        <div class="gg-hub-card-name">{esc(name)}</div>
        <div class="gg-hub-card-location">{esc(location)}</div>
        <div class="gg-hub-card-tagline">{esc(tagline)}</div>
        <div class="gg-hub-card-stats">{esc(stats_line)}</div>
      </div>
    </a>''')

    cards = "\n    ".join(cards_html)

    # Build ItemList JSON-LD
    item_list_entries = []
    for i, r in enumerate(races, 1):
        slug = r.get("slug", "")
        item_list_entries.append(json.dumps({
            "@type": "ListItem",
            "position": i,
            "name": r.get("name", ""),
            "url": "https://gravelgodcycling.com/race/" + slug + "/"
        }, ensure_ascii=False))
    item_list_json = ",\n      ".join(item_list_entries)

    # Tier navigation
    tier_nav_items = []
    for t in [1, 2, 3, 4]:
        tm = TIER_META[t]
        active = ' class="active"' if t == tier else ""
        count_t = sum(1 for r in all_races if r.get("tier") == t)
        tier_nav_items.append(
            f'<a href="/race/{tm["slug"]}/"{active}>T{t} {tm["name"]} ({count_t})</a>'
        )
    tier_nav = "\n      ".join(tier_nav_items)

    canonical = f"https://gravelgodcycling.com/race/{meta['slug']}/"

    font_face = get_font_face_css()
    tokens = get_tokens_css()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(meta["title"])}</title>
  <meta name="description" content="{esc(meta["description"])}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='%233a2e25'/><text x='16' y='24' text-anchor='middle' font-family='serif' font-size='24' font-weight='700' fill='%239a7e0a'>G</text></svg>">
  <meta property="og:title" content="{esc(meta["title"])}">
  <meta property="og:description" content="{esc(meta["description"])}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical)}">
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": "{esc(meta["h1"])}",
    "description": "{esc(meta["description"])}",
    "url": "{esc(canonical)}",
    "numberOfItems": {len(races)},
    "isPartOf": {{
      "@type": "WebSite",
      "name": "Gravel God",
      "url": "https://gravelgodcycling.com"
    }}
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
        "item": "https://gravelgodcycling.com/"
      }},
      {{
        "@type": "ListItem",
        "position": 2,
        "name": "Gravel Races",
        "item": "https://gravelgodcycling.com/gravel-races/"
      }},
      {{
        "@type": "ListItem",
        "position": 3,
        "name": "Tier {tier} — {esc(meta["name"])}",
        "item": "{esc(canonical)}"
      }}
    ]
  }}
  </script>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": "{esc(meta["h1"])}",
    "numberOfItems": {len(races)},
    "itemListOrder": "https://schema.org/ItemListOrderDescending",
    "itemListElement": [
      {item_list_json}
    ]
  }}
  </script>
  <style>
{font_face}
{tokens}

.gg-hub-page {{
  max-width: 960px;
  margin: 0 auto;
  padding: 0 24px;
  font-family: var(--gg-font-data);
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-warm-paper);
  min-height: 100vh;
}}
.gg-hub-page *, .gg-hub-page *::before, .gg-hub-page *::after {{
  border-radius: 0 !important;
  box-shadow: none !important;
}}

/* Nav */
.gg-hub-nav {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 2px solid var(--gg-color-dark-brown);
  margin-bottom: 0;
}}
.gg-hub-nav-brand {{
  font-family: var(--gg-font-editorial);
  font-size: 18px;
  font-weight: 700;
  color: var(--gg-color-dark-brown);
  text-decoration: none;
}}
.gg-hub-nav-links {{
  display: flex;
  gap: 16px;
}}
.gg-hub-nav-links a {{
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--gg-color-secondary-brown);
  text-decoration: none;
}}
.gg-hub-nav-links a:hover {{
  color: var(--gg-color-dark-brown);
}}

/* Breadcrumb */
.gg-hub-breadcrumb {{
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  padding: 12px 0;
  letter-spacing: 0.5px;
}}
.gg-hub-breadcrumb a {{
  color: var(--gg-color-secondary-brown);
  text-decoration: none;
}}
.gg-hub-breadcrumb a:hover {{
  color: var(--gg-color-dark-brown);
}}

/* Hero */
.gg-hub-hero {{
  background: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
  padding: 48px 32px;
  margin: 0 -24px;
  border-bottom: 4px double var(--gg-color-dark-brown);
}}
.gg-hub-hero-tier {{
  display: inline-block;
  background: {tier_color};
  color: var(--gg-color-warm-paper);
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  border: 2px solid var(--gg-color-warm-paper);
  margin-bottom: 16px;
}}
.gg-hub-hero h1 {{
  font-family: var(--gg-font-editorial);
  font-size: 36px;
  font-weight: 700;
  line-height: 1.1;
  margin-bottom: 12px;
}}
.gg-hub-hero-count {{
  font-size: 13px;
  color: var(--gg-color-tan);
  letter-spacing: 1px;
  text-transform: uppercase;
}}
.gg-hub-intro {{
  font-family: var(--gg-font-editorial);
  font-size: 16px;
  line-height: 1.7;
  color: var(--gg-color-dark-brown);
  max-width: 720px;
  padding: 24px 0;
  border-bottom: 2px solid var(--gg-color-sand);
}}

/* Tier nav */
.gg-hub-tier-nav {{
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--gg-color-dark-brown);
}}
.gg-hub-tier-nav a {{
  flex: 1;
  text-align: center;
  padding: 10px 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  text-decoration: none;
  color: var(--gg-color-secondary-brown);
  border-right: 2px solid var(--gg-color-dark-brown);
}}
.gg-hub-tier-nav a:last-child {{
  border-right: none;
}}
.gg-hub-tier-nav a.active {{
  background: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
}}
.gg-hub-tier-nav a:hover:not(.active) {{
  background: var(--gg-color-sand);
}}

/* Cards grid */
.gg-hub-grid {{
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0;
}}
.gg-hub-card {{
  display: flex;
  align-items: stretch;
  border-bottom: 2px solid var(--gg-color-dark-brown);
  text-decoration: none;
  color: inherit;
  transition: background 0.15s;
}}
.gg-hub-card:first-child {{
  border-top: 2px solid var(--gg-color-dark-brown);
}}
.gg-hub-card:hover {{
  background: var(--gg-color-sand);
}}
.gg-hub-card-score {{
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 64px;
  font-family: var(--gg-font-editorial);
  font-size: 24px;
  font-weight: 700;
  color: {tier_color};
  border-right: 2px solid var(--gg-color-dark-brown);
  padding: 12px 8px;
}}
.gg-hub-card-body {{
  flex: 1;
  padding: 12px 16px;
}}
.gg-hub-card-name {{
  font-family: var(--gg-font-editorial);
  font-size: 16px;
  font-weight: 700;
  color: var(--gg-color-dark-brown);
  margin-bottom: 2px;
}}
.gg-hub-card-location {{
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 4px;
}}
.gg-hub-card-tagline {{
  font-family: var(--gg-font-editorial);
  font-size: 13px;
  color: var(--gg-color-dark-brown);
  line-height: 1.4;
}}
.gg-hub-card-stats {{
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  margin-top: 4px;
  letter-spacing: 0.5px;
}}

/* Footer */
.gg-hub-footer {{
  padding: 24px 0;
  margin-top: 32px;
  border-top: 4px double var(--gg-color-dark-brown);
  text-align: center;
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 1px;
  text-transform: uppercase;
}}
.gg-hub-footer a {{
  color: var(--gg-color-secondary-brown);
  text-decoration: none;
}}
.gg-hub-footer a:hover {{
  color: var(--gg-color-dark-brown);
}}

/* Mobile */
@media (max-width: 768px) {{
  .gg-hub-hero {{ padding: 32px 20px; }}
  .gg-hub-hero h1 {{ font-size: 28px; }}
  .gg-hub-nav-links {{ gap: 10px; }}
  .gg-hub-nav-links a {{ font-size: 10px; }}
  .gg-hub-tier-nav a {{ font-size: 9px; padding: 8px 4px; }}
}}
@media (max-width: 480px) {{
  .gg-hub-page {{ padding: 0 12px; }}
  .gg-hub-hero {{ padding: 24px 12px; margin: 0 -12px; }}
  .gg-hub-hero h1 {{ font-size: 22px; }}
  .gg-hub-card-score {{ min-width: 48px; font-size: 18px; }}
  .gg-hub-card-body {{ padding: 10px 12px; }}
  .gg-hub-card-name {{ font-size: 14px; }}
  .gg-hub-nav {{ flex-wrap: wrap; gap: 8px; }}
}}
  </style>
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>
</head>
<body style="margin:0;background:var(--gg-color-warm-paper)">

<div class="gg-hub-page">

  <nav class="gg-hub-nav">
    <a href="/" class="gg-hub-nav-brand">Gravel God</a>
    <div class="gg-hub-nav-links">
      <a href="/gravel-races/">All Races</a>
      <a href="/race/methodology/">How We Rate</a>
    </div>
  </nav>

  <div class="gg-hub-breadcrumb">
    <a href="/">Home</a> &rsaquo; <a href="/gravel-races/">Gravel Races</a> &rsaquo; {esc(meta["name"])}
  </div>

  <div class="gg-hub-tier-nav">
    {tier_nav}
  </div>

  <section class="gg-hub-hero">
    <div class="gg-hub-hero-tier">Tier {tier}</div>
    <h1>{esc(meta["h1"])}</h1>
    <div class="gg-hub-hero-count">{len(races)} races &middot; Scored &amp; ranked by Gravel God</div>
  </section>

  <p class="gg-hub-intro">{esc(meta["intro"])}</p>

  <div class="gg-hub-grid">
    {cards}
  </div>

  <footer class="gg-hub-footer">
    <a href="/">Gravel God</a> &middot; {len(all_races)} races rated &middot;
    <a href="/gravel-races/">Search All</a> &middot;
    <a href="/race/methodology/">Methodology</a>
  </footer>

</div>

</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate tier hub landing pages")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: wordpress/output/)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / "wordpress" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load race index
    index_path = PROJECT_ROOT / "web" / "race-index.json"
    if not index_path.exists():
        print("ERROR: web/race-index.json not found. Run generate_index.py first.", file=sys.stderr)
        sys.exit(1)

    with open(index_path, "r", encoding="utf-8") as f:
        all_races = json.load(f)
    print(f"Loaded {len(all_races)} races from index")

    for tier in [1, 2, 3, 4]:
        meta = TIER_META[tier]
        tier_races = [r for r in all_races if r.get("tier") == tier]

        hub_dir = output_dir / meta["slug"]
        hub_dir.mkdir(parents=True, exist_ok=True)

        page_html = build_hub_page(tier, tier_races, all_races)
        out_path = hub_dir / "index.html"
        out_path.write_text(page_html, encoding="utf-8")
        print(f"  Generated {meta['slug']}/index.html ({len(tier_races)} races)")

    print(f"\nDone. 4 tier hub pages in {output_dir}/")


if __name__ == "__main__":
    main()
