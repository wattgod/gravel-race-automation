#!/usr/bin/env python3
"""
Generate a standalone race calendar page for SEO.

Creates /race/calendar/{year}/index.html showing all races organized by month.
Targets queries like "gravel race calendar 2026", "gravel racing schedule",
"gravel events this month".

Features:
  - Month-by-month sections with race cards
  - Filter by tier and region (JavaScript client-side)
  - Monthly race count summary
  - JSON-LD (CollectionPage + BreadcrumbList + Event schema per race)
  - Substack CTA for calendar updates

Usage:
    python wordpress/generate_calendar.py
"""

import argparse
import html as html_mod
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import COLORS, get_font_face_css, get_ga4_head_snippet, get_tokens_css, SITE_BASE_URL
from shared_header import get_site_header_css, get_site_header_html
from cookie_consent import get_consent_banner_html

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CURRENT_YEAR = date.today().year

TIER_NAMES = {1: "Elite", 2: "Contender", 3: "Solid", 4: "Roster"}
TIER_COLORS = {
    1: COLORS["primary_brown"],
    2: COLORS["secondary_brown"],
    3: COLORS["warm_brown"],
    4: "#5e6868",
}

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

REGIONS = ["West", "Midwest", "South", "Northeast", "Europe", "North America", "Oceania", "Africa", "Asia", "South America"]


def esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def build_calendar_page(races: list) -> str:
    """Generate the full calendar page."""
    # Group by month
    by_month = defaultdict(list)
    for r in races:
        month = r.get("month", "TBD")
        by_month[month].append(r)

    # Sort each month's races by score
    for month in by_month:
        by_month[month].sort(key=lambda x: -x.get("overall_score", 0))

    # Extract unique regions for filter
    regions = sorted(set(r.get("region", "") for r in races if r.get("region")))

    # Month summary bar
    summary_items = []
    for m in MONTHS:
        count = len(by_month.get(m, []))
        summary_items.append(f'<a href="#month-{m.lower()}" class="gg-cal-summary-item">'
                             f'<span class="gg-cal-summary-month">{m[:3]}</span>'
                             f'<span class="gg-cal-summary-count">{count}</span></a>')
    summary_bar = "\n    ".join(summary_items)

    # Month sections
    month_sections = []
    for m in MONTHS:
        month_races = by_month.get(m, [])
        if not month_races:
            month_sections.append(
                f'<section id="month-{m.lower()}" class="gg-cal-month" data-month="{m}">'
                f'<h2>{m} <span class="gg-cal-month-count">0 races</span></h2>'
                f'<p class="gg-cal-empty">No races scheduled in {m}.</p></section>'
            )
            continue

        cards = []
        for r in month_races:
            score = r.get("overall_score", 0)
            tier = r.get("tier", 3)
            tier_color = TIER_COLORS.get(tier, COLORS["warm_brown"])
            region = r.get("region", "")

            stat_parts = []
            dist = r.get("distance_mi")
            elev = r.get("elevation_ft")
            if dist:
                stat_parts.append(f"{dist} mi")
            if elev:
                try:
                    stat_parts.append(f"{int(elev):,} ft")
                except (ValueError, TypeError):
                    pass
            stats = " · ".join(stat_parts)

            cards.append(
                f'<a href="/race/{esc(r["slug"])}/" class="gg-cal-card" '
                f'data-tier="{tier}" data-region="{esc(region)}">'
                f'<div class="gg-cal-card-score" style="color:{tier_color}">{score}</div>'
                f'<div class="gg-cal-card-body">'
                f'<div class="gg-cal-card-tier" style="border-color:{tier_color}">T{tier}</div>'
                f'<div class="gg-cal-card-name">{esc(r["name"])}</div>'
                f'<div class="gg-cal-card-location">{esc(r.get("location",""))}</div>'
                f'<div class="gg-cal-card-stats">{esc(stats)}</div>'
                f'</div></a>'
            )

        cards_html = "\n      ".join(cards)
        month_sections.append(
            f'<section id="month-{m.lower()}" class="gg-cal-month" data-month="{m}">'
            f'<h2>{m} <span class="gg-cal-month-count">{len(month_races)} '
            f'{"race" if len(month_races) == 1 else "races"}</span></h2>'
            f'<div class="gg-cal-grid">{cards_html}</div></section>'
        )

    months_html = "\n\n  ".join(month_sections)

    # TBD races
    tbd_races = by_month.get("TBD", [])
    tbd_section = ""
    if tbd_races:
        tbd_cards = []
        for r in tbd_races:
            score = r.get("overall_score", 0)
            tier = r.get("tier", 3)
            tier_color = TIER_COLORS.get(tier, COLORS["warm_brown"])
            tbd_cards.append(
                f'<a href="/race/{esc(r["slug"])}/" class="gg-cal-card" data-tier="{tier}">'
                f'<div class="gg-cal-card-score" style="color:{tier_color}">{score}</div>'
                f'<div class="gg-cal-card-body">'
                f'<div class="gg-cal-card-name">{esc(r["name"])}</div>'
                f'<div class="gg-cal-card-location">{esc(r.get("location",""))}</div>'
                f'</div></a>'
            )
        tbd_section = (
            f'<section class="gg-cal-month"><h2>Date TBD '
            f'<span class="gg-cal-month-count">{len(tbd_races)} races</span></h2>'
            f'<div class="gg-cal-grid">{"".join(tbd_cards)}</div></section>'
        )

    canonical = f"{SITE_BASE_URL}/race/calendar/{CURRENT_YEAR}/"
    title = f"Gravel Race Calendar {CURRENT_YEAR} — All {len(races)} Events | Gravel God"
    description = (
        f"Complete {CURRENT_YEAR} gravel race calendar with {len(races)} events worldwide. "
        f"Filter by tier and region. Find your next race."
    )

    font_face = get_font_face_css()
    tokens = get_tokens_css()

    # Tier filter buttons
    tier_buttons = '<button class="gg-cal-filter-btn active" data-tier="all">All</button>'
    for t in [1, 2, 3, 4]:
        count = sum(1 for r in races if r.get("tier") == t)
        tier_buttons += f'<button class="gg-cal-filter-btn" data-tier="{t}">T{t} ({count})</button>'

    # Region filter
    region_options = '<option value="all">All Regions</option>'
    for reg in regions:
        count = sum(1 for r in races if r.get("region") == reg)
        region_options += f'<option value="{esc(reg)}">{esc(reg)} ({count})</option>'

    breadcrumb_jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Gravel Races", "item": f"{SITE_BASE_URL}/gravel-races/"},
            {"@type": "ListItem", "position": 3, "name": f"Calendar {CURRENT_YEAR}", "item": canonical},
        ],
    }, ensure_ascii=False, indent=2)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='%233a2e25'/><text x='16' y='24' text-anchor='middle' font-family='serif' font-size='24' font-weight='700' fill='%239a7e0a'>G</text></svg>">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical)}">
  <script type="application/ld+json">
  {breadcrumb_jsonld}
  </script>
  <style>
{font_face}
{tokens}

body {{ margin: 0; background: var(--gg-color-warm-paper); }}
*, *::before, *::after {{ border-radius: 0 !important; box-shadow: none !important; }}

.gg-cal-page {{
  max-width: 960px;
  margin: 0 auto;
  padding: 0 24px;
  font-family: var(--gg-font-data);
  color: var(--gg-color-dark-brown);
}}

{get_site_header_css()}

.gg-cal-breadcrumb {{ font-size: 11px; color: var(--gg-color-secondary-brown); padding: 12px 0; letter-spacing: 0.5px; }}
.gg-cal-breadcrumb a {{ color: var(--gg-color-secondary-brown); text-decoration: none; }}

.gg-cal-hero {{
  background: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
  padding: 48px 32px;
  margin: 0 -24px;
  text-align: center;
}}
.gg-cal-hero h1 {{ font-family: var(--gg-font-editorial); font-size: 36px; font-weight: 700; margin: 0 0 8px; }}
.gg-cal-hero-sub {{ font-size: 13px; color: var(--gg-color-tan); letter-spacing: 1px; }}

/* Summary bar */
.gg-cal-summary {{
  display: flex;
  border-bottom: 2px solid var(--gg-color-dark-brown);
  overflow-x: auto;
}}
.gg-cal-summary-item {{
  flex: 1;
  text-align: center;
  padding: 10px 4px;
  text-decoration: none;
  color: var(--gg-color-dark-brown);
  border-right: 1px solid var(--gg-color-sand);
  min-width: 50px;
}}
.gg-cal-summary-item:last-child {{ border-right: none; }}
.gg-cal-summary-item:hover {{ background: var(--gg-color-sand); }}
.gg-cal-summary-month {{ display: block; font-size: 10px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; }}
.gg-cal-summary-count {{ display: block; font-family: var(--gg-font-editorial); font-size: 20px; font-weight: 700; margin-top: 2px; }}

/* Filters */
.gg-cal-filters {{
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 0;
  border-bottom: 2px solid var(--gg-color-sand);
  flex-wrap: wrap;
}}
.gg-cal-filter-label {{ font-size: 10px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--gg-color-secondary-brown); }}
.gg-cal-filter-btn {{
  padding: 4px 10px;
  font-size: 11px;
  font-weight: 700;
  border: 2px solid var(--gg-color-dark-brown);
  background: transparent;
  color: var(--gg-color-dark-brown);
  cursor: pointer;
  font-family: var(--gg-font-data);
}}
.gg-cal-filter-btn.active {{ background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); }}
.gg-cal-filter-btn:hover:not(.active) {{ background: var(--gg-color-sand); }}
.gg-cal-filter-select {{
  padding: 4px 8px;
  font-size: 11px;
  border: 2px solid var(--gg-color-dark-brown);
  background: transparent;
  font-family: var(--gg-font-data);
  color: var(--gg-color-dark-brown);
}}

/* Month sections */
.gg-cal-month {{ margin: 32px 0; }}
.gg-cal-month h2 {{
  font-family: var(--gg-font-editorial);
  font-size: 24px;
  font-weight: 700;
  margin: 0 0 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--gg-color-dark-brown);
}}
.gg-cal-month-count {{ font-size: 13px; color: var(--gg-color-secondary-brown); font-weight: 400; }}
.gg-cal-empty {{ font-size: 13px; color: var(--gg-color-secondary-brown); font-style: italic; }}

/* Cards */
.gg-cal-grid {{ display: flex; flex-direction: column; gap: 0; }}
.gg-cal-card {{
  display: flex;
  align-items: stretch;
  border-bottom: 1px solid var(--gg-color-sand);
  text-decoration: none;
  color: inherit;
  transition: background 0.15s;
  padding: 0;
}}
.gg-cal-card:hover {{ background: var(--gg-color-sand); }}
.gg-cal-card-score {{
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  font-family: var(--gg-font-editorial);
  font-size: 18px;
  font-weight: 700;
  padding: 8px;
}}
.gg-cal-card-body {{ flex: 1; padding: 8px 12px; }}
.gg-cal-card-tier {{
  display: inline-block;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 0 4px;
  border: 1px solid;
  margin-right: 6px;
}}
.gg-cal-card-name {{ font-family: var(--gg-font-editorial); font-size: 14px; font-weight: 700; display: inline; }}
.gg-cal-card-location {{ font-size: 10px; color: var(--gg-color-secondary-brown); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px; }}
.gg-cal-card-stats {{ font-size: 10px; color: var(--gg-color-secondary-brown); }}
.gg-cal-card[data-hidden="true"] {{ display: none; }}

/* CTA */
.gg-cal-cta {{
  background: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
  padding: 32px;
  margin: 32px -24px;
  text-align: center;
}}
.gg-cal-cta h2 {{ font-family: var(--gg-font-editorial); font-size: 22px; color: var(--gg-color-warm-paper); margin: 0 0 12px; border: none; }}
.gg-cal-cta p {{ font-size: 14px; line-height: 1.6; margin: 0 0 16px; }}
.gg-cal-cta-btn {{
  display: inline-block;
  padding: 12px 28px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  text-decoration: none;
  border: 2px solid var(--gg-color-warm-paper);
  color: var(--gg-color-warm-paper);
  transition: all 0.2s;
}}
.gg-cal-cta-btn:hover {{ background: var(--gg-color-warm-paper); color: var(--gg-color-dark-brown); }}

.gg-cal-footer {{
  padding: 24px 0;
  margin-top: 32px;
  border-top: 4px double var(--gg-color-dark-brown);
  text-align: center;
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 1px;
  text-transform: uppercase;
}}
.gg-cal-footer a {{ color: var(--gg-color-secondary-brown); text-decoration: none; }}

@media (max-width: 768px) {{
  .gg-cal-hero {{ padding: 32px 20px; }}
  .gg-cal-hero h1 {{ font-size: 28px; }}
}}
@media (max-width: 480px) {{
  .gg-cal-page {{ padding: 0 12px; }}
  .gg-cal-hero {{ padding: 24px 12px; margin: 0 -12px; }}
  .gg-cal-hero h1 {{ font-size: 22px; }}
  .gg-cal-cta {{ margin: 32px -12px; padding: 24px 16px; }}
}}
  </style>
  {get_ga4_head_snippet()}
</head>
<body>

<div class="gg-cal-page">

  {get_site_header_html(active="races")}

  <div class="gg-cal-breadcrumb">
    <a href="/">Home</a> &rsaquo; <a href="/gravel-races/">Gravel Races</a> &rsaquo; Calendar {CURRENT_YEAR}
  </div>

  <section class="gg-cal-hero">
    <h1>{CURRENT_YEAR} Gravel Race Calendar</h1>
    <div class="gg-cal-hero-sub">{len(races)} events worldwide &middot; Updated live</div>
  </section>

  <div class="gg-cal-summary">
    {summary_bar}
  </div>

  <div class="gg-cal-filters">
    <span class="gg-cal-filter-label">Tier:</span>
    {tier_buttons}
    <span class="gg-cal-filter-label" style="margin-left:12px">Region:</span>
    <select class="gg-cal-filter-select" id="gg-cal-region-filter">
      {region_options}
    </select>
  </div>

  {months_html}

  {tbd_section}

  <section class="gg-cal-cta">
    <h2>Get Race Reminders</h2>
    <p>Subscribe to the Gravel God newsletter for registration alerts, training tips, and race previews delivered to your inbox.</p>
    <a href="https://gravelgodcycling.substack.com" class="gg-cal-cta-btn" target="_blank" rel="noopener">Subscribe Free</a>
  </section>

  <footer class="gg-cal-footer">
    <a href="/">Gravel God</a> &middot; {len(races)} races &middot;
    <a href="/gravel-races/">Search All</a> &middot;
    <a href="/race/methodology/">Methodology</a>
  </footer>

</div>

<script>
(function() {{
  var tierBtns = document.querySelectorAll('.gg-cal-filter-btn');
  var regionSel = document.getElementById('gg-cal-region-filter');
  var cards = document.querySelectorAll('.gg-cal-card');
  var activeTier = 'all';
  var activeRegion = 'all';

  function applyFilters() {{
    cards.forEach(function(card) {{
      var tierMatch = activeTier === 'all' || card.getAttribute('data-tier') === activeTier;
      var regionMatch = activeRegion === 'all' || card.getAttribute('data-region') === activeRegion;
      card.setAttribute('data-hidden', !(tierMatch && regionMatch));
    }});
    // Update month counts
    document.querySelectorAll('.gg-cal-month').forEach(function(section) {{
      var visible = section.querySelectorAll('.gg-cal-card:not([data-hidden="true"])').length;
      var countEl = section.querySelector('.gg-cal-month-count');
      if (countEl) countEl.textContent = visible + (visible === 1 ? ' race' : ' races');
    }});
  }}

  tierBtns.forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      tierBtns.forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      activeTier = btn.getAttribute('data-tier');
      applyFilters();
    }});
  }});

  if (regionSel) {{
    regionSel.addEventListener('change', function() {{
      activeRegion = regionSel.value;
      applyFilters();
    }});
  }}
}})();
</script>

{get_consent_banner_html()}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate race calendar page")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / "wordpress" / "output"

    index_path = PROJECT_ROOT / "web" / "race-index.json"
    if not index_path.exists():
        print("ERROR: web/race-index.json not found.", file=sys.stderr)
        sys.exit(1)

    with open(index_path, "r", encoding="utf-8") as f:
        all_races = json.load(f)
    print(f"Loaded {len(all_races)} races")

    page_dir = output_dir / "calendar" / str(CURRENT_YEAR)
    page_dir.mkdir(parents=True, exist_ok=True)

    page_html = build_calendar_page(all_races)
    out_path = page_dir / "index.html"
    out_path.write_text(page_html, encoding="utf-8")
    print(f"Generated calendar/{CURRENT_YEAR}/index.html ({len(all_races)} races)")


if __name__ == "__main__":
    main()
