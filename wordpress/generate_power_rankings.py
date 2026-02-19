#!/usr/bin/env python3
"""
Generate annual power rankings page for SEO.

Creates /race/power-rankings-{year}/index.html showing all races ranked by
overall score with tier badges, score breakdowns, and Substack CTA.
Targets "best gravel races 2026", "gravel race rankings", "top gravel events".

Usage:
    python wordpress/generate_power_rankings.py
"""

import argparse
import html as html_mod
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import COLORS, GA_MEASUREMENT_ID, SITE_BASE_URL, get_font_face_css, get_tokens_css
from shared_header import get_site_header_css, get_site_header_html

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CURRENT_YEAR = date.today().year

TIER_NAMES = {1: "Elite", 2: "Contender", 3: "Solid", 4: "Roster"}
TIER_COLORS = {
    1: COLORS["primary_brown"],
    2: COLORS["secondary_brown"],
    3: COLORS["warm_brown"],
    4: "#5e6868",
}


def esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def build_power_rankings_page(races: list) -> str:
    """Generate the full power rankings page."""
    # Sort by score descending
    ranked = sorted(races, key=lambda x: -x.get("overall_score", 0))

    font_face = get_font_face_css()
    tokens = get_tokens_css()

    canonical = f"{SITE_BASE_URL}/race/power-rankings-{CURRENT_YEAR}/"
    title = f"Gravel Race Power Rankings {CURRENT_YEAR} — All {len(races)} Races Ranked | Gravel God"
    description = (
        f"The definitive {CURRENT_YEAR} gravel race power rankings. "
        f"All {len(races)} races ranked by our 14-dimension Gravel God Rating. "
        f"From the iconic Elite tier to grassroots gems."
    )

    # Stats
    t1_count = sum(1 for r in races if r.get("tier") == 1)
    t2_count = sum(1 for r in races if r.get("tier") == 2)
    avg_score = sum(r.get("overall_score", 0) for r in races) / max(len(races), 1)
    top_race = ranked[0] if ranked else None
    regions = len(set(r.get("region", "") for r in races))

    # Discipline counts for filter buttons
    gravel_count = sum(1 for r in races if r.get("discipline", "gravel") == "gravel")
    bp_count = sum(1 for r in races if r.get("discipline") == "bikepacking")
    mtb_count = sum(1 for r in races if r.get("discipline") == "mtb")

    # Build ranked list with position numbers and discipline data attributes
    cards = []
    prev_tier = None
    for i, r in enumerate(ranked, 1):
        score = r.get("overall_score", 0)
        tier = r.get("tier", 3)
        tier_color = TIER_COLORS.get(tier, COLORS["warm_brown"])
        discipline = r.get("discipline", "gravel")

        # Tier separator — tagged with tier number for JS to show/hide
        if tier != prev_tier:
            tier_name = TIER_NAMES.get(tier, "")
            tier_count = sum(1 for x in races if x.get("tier") == tier)
            cards.append(
                f'<div class="gg-pr-tier-sep" data-tier="{tier}" style="border-left-color:{tier_color}">'
                f'<span class="gg-pr-tier-badge" style="background:{tier_color}">Tier {tier}</span> '
                f'<span class="gg-pr-tier-label">{tier_name} — <span class="gg-pr-tier-count">{tier_count}</span> races</span></div>'
            )
            prev_tier = tier

        stat_parts = []
        dist = r.get("distance_mi")
        if dist:
            stat_parts.append(f"{dist} mi")
        elev = r.get("elevation_ft")
        if elev:
            try:
                stat_parts.append(f"{int(elev):,} ft")
            except (ValueError, TypeError):
                pass
        month = r.get("month", "")
        if month:
            stat_parts.append(month)
        stats = " · ".join(stat_parts)

        # Discipline badge for non-gravel races
        disc_badge = ""
        if discipline != "gravel":
            disc_badge = (f'<span class="gg-pr-disc-badge">'
                         f'{esc(discipline.upper())}</span>')

        cards.append(
            f'<a href="/race/{esc(r["slug"])}/" class="gg-pr-card" '
            f'data-discipline="{esc(discipline)}" data-tier="{tier}">'
            f'<div class="gg-pr-rank"></div>'
            f'<div class="gg-pr-score" style="color:{tier_color}">{score}</div>'
            f'<div class="gg-pr-body">'
            f'<div class="gg-pr-name">{disc_badge}{esc(r["name"])}</div>'
            f'<div class="gg-pr-location">{esc(r.get("location",""))}</div>'
            f'<div class="gg-pr-stats">{esc(stats)}</div>'
            f'</div></a>'
        )

    cards_html = "\n    ".join(cards)

    # Build ItemList schema for top 25 races (SERP carousel eligibility)
    top_25 = ranked[:25]
    item_list_elements = []
    for pos, r in enumerate(top_25, 1):
        item_list_elements.append({
            "@type": "ListItem",
            "position": pos,
            "name": r.get("name", ""),
            "url": f"{SITE_BASE_URL}/race/{r['slug']}/",
        })

    schema_graph = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_BASE_URL}/"},
                    {"@type": "ListItem", "position": 2, "name": "Gravel Races", "item": f"{SITE_BASE_URL}/gravel-races/"},
                    {"@type": "ListItem", "position": 3, "name": f"Power Rankings {CURRENT_YEAR}", "item": canonical},
                ],
            },
            {
                "@type": "ItemList",
                "name": f"Gravel Race Power Rankings {CURRENT_YEAR}",
                "description": description,
                "url": canonical,
                "numberOfItems": len(races),
                "itemListOrder": "https://schema.org/ItemListOrderDescending",
                "itemListElement": item_list_elements,
            },
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
  {schema_graph}
  </script>
  <style>
{font_face}
{tokens}

body {{ margin: 0; background: var(--gg-color-warm-paper); }}
*, *::before, *::after {{ border-radius: 0 !important; box-shadow: none !important; }}

.gg-pr-page {{
  max-width: 960px;
  margin: 0 auto;
  padding: 0 24px;
  font-family: var(--gg-font-data);
  color: var(--gg-color-dark-brown);
}}

{get_site_header_css()}

.gg-pr-breadcrumb {{ font-size: 11px; color: var(--gg-color-secondary-brown); padding: 12px 0; letter-spacing: 0.5px; }}
.gg-pr-breadcrumb a {{ color: var(--gg-color-secondary-brown); text-decoration: none; }}

.gg-pr-hero {{
  background: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
  padding: 48px 32px;
  margin: 0 -24px;
  text-align: center;
}}
.gg-pr-hero h1 {{ font-family: var(--gg-font-editorial); font-size: 36px; font-weight: 700; margin: 0 0 12px; }}
.gg-pr-hero-sub {{ font-size: 13px; color: var(--gg-color-tan); letter-spacing: 1px; }}

/* Stats strip */
.gg-pr-stats-strip {{
  display: flex;
  border-bottom: 2px solid var(--gg-color-dark-brown);
  text-align: center;
}}
.gg-pr-stat {{
  flex: 1;
  padding: 16px 8px;
  border-right: 1px solid var(--gg-color-sand);
}}
.gg-pr-stat:last-child {{ border-right: none; }}
.gg-pr-stat-val {{ font-family: var(--gg-font-editorial); font-size: 28px; font-weight: 700; }}
.gg-pr-stat-label {{ font-size: 9px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--gg-color-secondary-brown); margin-top: 2px; }}

/* Discipline filter */
.gg-pr-filters {{
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 0;
  border-bottom: 2px solid var(--gg-color-sand);
}}
.gg-pr-filter-label {{ font-size: 10px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--gg-color-secondary-brown); }}
.gg-pr-filter-btn {{
  padding: 5px 12px;
  font-size: 11px;
  font-weight: 700;
  border: 2px solid var(--gg-color-dark-brown);
  background: transparent;
  color: var(--gg-color-dark-brown);
  cursor: pointer;
  font-family: var(--gg-font-data);
  letter-spacing: 0.5px;
}}
.gg-pr-filter-btn.active {{ background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); }}
.gg-pr-filter-btn:hover:not(.active) {{ background: var(--gg-color-sand); }}

/* Discipline badge */
.gg-pr-disc-badge {{
  display: inline-block;
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1.5px;
  padding: 1px 5px;
  border: 1px solid var(--gg-color-teal);
  color: var(--gg-color-teal);
  margin-right: 6px;
  vertical-align: middle;
}}

/* Tier separators */
.gg-pr-tier-sep {{
  padding: 16px 12px 8px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  border-left: 4px solid;
  margin-top: 24px;
}}
.gg-pr-tier-sep[data-hidden="true"] {{ display: none; }}
.gg-pr-tier-badge {{
  display: inline-block;
  color: var(--gg-color-warm-paper);
  padding: 2px 8px;
  font-size: 10px;
  letter-spacing: 1.5px;
  margin-right: 6px;
}}

/* Cards */
.gg-pr-list {{ margin: 0; }}
.gg-pr-card {{
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--gg-color-sand);
  text-decoration: none;
  color: inherit;
  transition: background 0.15s;
  padding: 6px 0;
}}
.gg-pr-card:hover {{ background: var(--gg-color-sand); }}
.gg-pr-card[data-hidden="true"] {{ display: none; }}
.gg-pr-rank {{
  min-width: 44px;
  font-family: var(--gg-font-editorial);
  font-size: 13px;
  font-weight: 700;
  color: var(--gg-color-secondary-brown);
  text-align: center;
  padding: 0 4px;
}}
.gg-pr-score {{
  min-width: 44px;
  font-family: var(--gg-font-editorial);
  font-size: 20px;
  font-weight: 700;
  text-align: center;
}}
.gg-pr-body {{ flex: 1; padding: 4px 12px; }}
.gg-pr-name {{ font-family: var(--gg-font-editorial); font-size: 14px; font-weight: 700; }}
.gg-pr-location {{ font-size: 10px; color: var(--gg-color-secondary-brown); text-transform: uppercase; letter-spacing: 0.5px; }}
.gg-pr-stats {{ font-size: 10px; color: var(--gg-color-secondary-brown); }}

/* CTA */
.gg-pr-cta {{
  background: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
  padding: 32px;
  margin: 32px -24px;
  text-align: center;
}}
.gg-pr-cta h2 {{ font-family: var(--gg-font-editorial); font-size: 22px; color: var(--gg-color-warm-paper); margin: 0 0 12px; }}
.gg-pr-cta p {{ font-size: 14px; line-height: 1.6; margin: 0 0 16px; }}
.gg-pr-cta-btn {{
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
.gg-pr-cta-btn:hover {{ background: var(--gg-color-warm-paper); color: var(--gg-color-dark-brown); }}

.gg-pr-footer {{
  padding: 24px 0;
  margin-top: 32px;
  border-top: 4px double var(--gg-color-dark-brown);
  text-align: center;
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 1px;
  text-transform: uppercase;
}}
.gg-pr-footer a {{ color: var(--gg-color-secondary-brown); text-decoration: none; }}

@media (max-width: 768px) {{
  .gg-pr-hero {{ padding: 32px 20px; }}
  .gg-pr-hero h1 {{ font-size: 28px; }}
  .gg-pr-stat-val {{ font-size: 22px; }}
}}
@media (max-width: 480px) {{
  .gg-pr-page {{ padding: 0 12px; }}
  .gg-pr-hero {{ padding: 24px 12px; margin: 0 -12px; }}
  .gg-pr-hero h1 {{ font-size: 22px; }}
  .gg-pr-cta {{ margin: 32px -12px; padding: 24px 16px; }}
  .gg-pr-stats-strip {{ flex-wrap: wrap; }}
  .gg-pr-stat {{ min-width: 50%; }}
}}
  </style>
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>
</head>
<body>

<div class="gg-pr-page">

  {get_site_header_html(active="races")}

  <div class="gg-pr-breadcrumb">
    <a href="/">Home</a> &rsaquo; <a href="/gravel-races/">Gravel Races</a> &rsaquo; Power Rankings {CURRENT_YEAR}
  </div>

  <section class="gg-pr-hero">
    <h1>{CURRENT_YEAR} Power Rankings</h1>
    <div class="gg-pr-hero-sub">Every gravel race, ranked. Updated annually.</div>
  </section>

  <div class="gg-pr-stats-strip">
    <div class="gg-pr-stat">
      <div class="gg-pr-stat-val">{len(races)}</div>
      <div class="gg-pr-stat-label">Races Ranked</div>
    </div>
    <div class="gg-pr-stat">
      <div class="gg-pr-stat-val">{t1_count}</div>
      <div class="gg-pr-stat-label">Elite Tier</div>
    </div>
    <div class="gg-pr-stat">
      <div class="gg-pr-stat-val">{regions}</div>
      <div class="gg-pr-stat-label">Regions</div>
    </div>
    <div class="gg-pr-stat">
      <div class="gg-pr-stat-val">{avg_score:.0f}</div>
      <div class="gg-pr-stat-label">Avg Score</div>
    </div>
  </div>

  <div class="gg-pr-filters">
    <span class="gg-pr-filter-label">Show:</span>
    <button class="gg-pr-filter-btn active" data-disc="gravel">Gravel ({gravel_count})</button>
    <button class="gg-pr-filter-btn" data-disc="all">All Disciplines ({len(races)})</button>
    <button class="gg-pr-filter-btn" data-disc="bikepacking">Bikepacking ({bp_count})</button>
    <button class="gg-pr-filter-btn" data-disc="mtb">MTB ({mtb_count})</button>
  </div>

  <div class="gg-pr-list">
    {cards_html}
  </div>

  <section class="gg-pr-cta">
    <h2>Get Notified When Rankings Update</h2>
    <p>Subscribe to the Gravel God newsletter for ranking changes, new entries, and exclusive race analysis.</p>
    <a href="https://gravelgodcycling.substack.com" class="gg-pr-cta-btn" target="_blank" rel="noopener">Subscribe Free</a>
  </section>

  <footer class="gg-pr-footer">
    <a href="/">Gravel God</a> &middot;
    <a href="/gravel-races/">Search All</a> &middot;
    <a href="/race/methodology/">Methodology</a> &middot;
    <a href="/race/calendar/{CURRENT_YEAR}/">Calendar</a>
  </footer>

</div>

<script>
(function() {{
  var btns = document.querySelectorAll('.gg-pr-filter-btn');
  var cards = document.querySelectorAll('.gg-pr-card');
  var tierSeps = document.querySelectorAll('.gg-pr-tier-sep');
  var activeDisc = 'gravel';

  function applyFilter() {{
    var rank = 0;
    var visiblePerTier = {{}};

    cards.forEach(function(card) {{
      var disc = card.getAttribute('data-discipline');
      var show = (activeDisc === 'all') || (disc === activeDisc);
      card.setAttribute('data-hidden', !show);
      if (show) {{
        rank++;
        card.querySelector('.gg-pr-rank').textContent = '#' + rank;
        var tier = card.getAttribute('data-tier');
        visiblePerTier[tier] = (visiblePerTier[tier] || 0) + 1;
      }}
    }});

    // Update tier separators
    tierSeps.forEach(function(sep) {{
      var tier = sep.getAttribute('data-tier');
      var count = visiblePerTier[tier] || 0;
      sep.setAttribute('data-hidden', count === 0);
      var countEl = sep.querySelector('.gg-pr-tier-count');
      if (countEl) countEl.textContent = count;
    }});
  }}

  btns.forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      btns.forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      activeDisc = btn.getAttribute('data-disc');
      applyFilter();
    }});
  }});

  // Apply default filter (gravel only) on load
  applyFilter();
}})();
</script>

</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate power rankings page")
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

    page_dir = output_dir / f"power-rankings-{CURRENT_YEAR}"
    page_dir.mkdir(parents=True, exist_ok=True)

    page_html = build_power_rankings_page(all_races)
    out_path = page_dir / "index.html"
    out_path.write_text(page_html, encoding="utf-8")
    print(f"Generated power-rankings-{CURRENT_YEAR}/index.html ({len(all_races)} races)")


if __name__ == "__main__":
    main()
