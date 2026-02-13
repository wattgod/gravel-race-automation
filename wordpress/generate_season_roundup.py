#!/usr/bin/env python3
"""
Generate season roundup articles from race-index.json.

Template-based (no AI API). Three roundup types:
  - Monthly: "March 2026 Gravel Calendar: N Races to Watch"
  - Regional: "Best Southeast Gravel Races for Spring 2026"
  - Tier: "2026 Elite Gravel Races: The Complete T1 Calendar"

Usage:
    python wordpress/generate_season_roundup.py --dry-run
    python wordpress/generate_season_roundup.py --monthly 2026 3
    python wordpress/generate_season_roundup.py --regional southeast spring 2026
    python wordpress/generate_season_roundup.py --tier 1 2026
    python wordpress/generate_season_roundup.py --all-monthly 2026
    python wordpress/generate_season_roundup.py --all
"""

import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = PROJECT_ROOT / "web" / "race-index.json"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "blog"
SITE_URL = "https://gravelgodcycling.com"

TIER_NAMES = {1: "Elite", 2: "Contender", 3: "Solid", 4: "Roster"}
TIER_COLORS = {1: "#59473c", 2: "#7d695d", 3: "#766a5e", 4: "#5e6868"}

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}
MONTH_NUMBERS = {v.lower(): k for k, v in MONTH_NAMES.items()}

REGIONS = {
    "southeast": ["South"],
    "midwest": ["Midwest"],
    "west": ["West"],
    "northeast": ["Northeast"],
    "europe": ["Europe"],
    "international": ["Europe", "Oceania", "Africa", "Asia", "South America", "North America"],
}

SEASONS = {
    "spring": [3, 4, 5],
    "summer": [6, 7, 8],
    "fall": [9, 10, 11],
    "winter": [12, 1, 2],
}

MIN_RACES_FOR_ROUNDUP = 3


def esc(text):
    """HTML-escape text."""
    return html.escape(str(text)) if text else ""


def load_race_index(index_path=None):
    """Load race-index.json."""
    path = index_path or INDEX_PATH
    if not path.exists():
        print(f"ERROR: Race index not found: {path}")
        sys.exit(1)
    return json.loads(path.read_text())


def classify_blog_slug(slug):
    """Classify a blog slug by content type.

    Returns 'roundup', 'recap', or 'preview'.
    """
    if slug.startswith("roundup-"):
        return "roundup"
    if slug.endswith("-recap"):
        return "recap"
    return "preview"


def filter_by_month(races, year, month):
    """Filter races by year and month.

    Matches on the 'month' field (e.g. "June") from race-index.json.
    Year filtering requires date_specific or assumes current year races.
    """
    month_name = MONTH_NAMES.get(month, "").lower()
    if not month_name:
        return []
    return [r for r in races if (r.get("month") or "").lower() == month_name]


def filter_by_region(races, region_key):
    """Filter races by region key (e.g. 'southeast')."""
    region_values = REGIONS.get(region_key, [])
    if not region_values:
        return []
    return [r for r in races if (r.get("region") or "") in region_values]


def filter_by_tier(races, tier):
    """Filter races by tier number."""
    return [r for r in races if r.get("tier") == tier]


def build_race_card_html(race):
    """Build a single race card HTML for roundup listings."""
    slug = race.get("slug", "")
    name = esc(race.get("name", slug))
    location = esc(race.get("location", ""))
    tier = race.get("tier", 4)
    tier_name = TIER_NAMES.get(tier, "Roster")
    tier_color = TIER_COLORS.get(tier, "#5e6868")
    score = race.get("overall_score", 0)
    month = esc(race.get("month", ""))
    distance = race.get("distance_mi", "")
    elevation = race.get("elevation_ft", "")
    tagline = esc(race.get("tagline", ""))
    profile_url = f"{SITE_URL}/race/{slug}/"

    distance_str = f"{distance} mi" if distance else ""
    if isinstance(elevation, (int, float)):
        elevation_str = f"{int(elevation):,} ft"
    elif isinstance(elevation, str) and elevation:
        elevation_str = f"{elevation} ft"
    else:
        elevation_str = ""
    vitals_parts = [p for p in [distance_str, elevation_str, month] if p]
    vitals_line = " &middot; ".join(vitals_parts)

    return f"""
    <div class="gg-roundup-card">
      <div class="gg-roundup-card-header">
        <span class="gg-roundup-tier" style="background:{tier_color}">T{tier} {esc(tier_name)}</span>
        <span class="gg-roundup-score">{score}/100</span>
      </div>
      <h3><a href="{profile_url}">{name}</a></h3>
      <div class="gg-roundup-location">{location}</div>
      <div class="gg-roundup-vitals">{vitals_line}</div>
      {f'<p class="gg-roundup-tagline">{tagline}</p>' if tagline else ''}
      <a href="{profile_url}" class="gg-roundup-link">Full Race Profile &rarr;</a>
    </div>"""


def build_roundup_stats(races):
    """Build stats summary for a set of races."""
    if not races:
        return {"count": 0, "avg_score": 0, "tier_breakdown": {}}
    scores = [r.get("overall_score", 0) for r in races]
    avg = round(sum(scores) / len(scores)) if scores else 0
    breakdown = {}
    for t in [1, 2, 3, 4]:
        count = sum(1 for r in races if r.get("tier") == t)
        if count:
            breakdown[t] = count
    return {"count": len(races), "avg_score": avg, "tier_breakdown": breakdown}


def build_stats_bar_html(stats):
    """Build the stats bar HTML."""
    parts = [f'<span class="gg-roundup-stat">{stats["count"]} Races</span>']
    parts.append(f'<span class="gg-roundup-stat">Avg Score: {stats["avg_score"]}/100</span>')
    for t, count in sorted(stats["tier_breakdown"].items()):
        tier_name = TIER_NAMES.get(t, "")
        parts.append(f'<span class="gg-roundup-stat">T{t} {esc(tier_name)}: {count}</span>')
    return '<div class="gg-roundup-stats-bar">' + "".join(parts) + "</div>"


def generate_roundup_html(title, subtitle, intro, races, slug, category_tag,
                          publish_date=None):
    """Generate a complete roundup article HTML.

    Args:
        title: Main heading (e.g. "March 2026 Gravel Calendar")
        subtitle: Secondary heading (e.g. "12 Races to Watch")
        intro: Paragraph of intro text
        races: List of race dicts from race-index.json
        slug: Output slug (e.g. "roundup-march-2026")
        category_tag: Display tag (e.g. "Monthly Calendar")
        publish_date: date object for datePublished (defaults to today)
    """
    stats = build_roundup_stats(races)
    stats_bar = build_stats_bar_html(stats)

    # Sort races by tier (ascending) then score (descending)
    sorted_races = sorted(races, key=lambda r: (r.get("tier", 4), -r.get("overall_score", 0)))
    cards = "".join(build_race_card_html(r) for r in sorted_races)

    pub_date = publish_date or date.today()
    today_str = pub_date.strftime("%B %d, %Y")
    og_url = f"{SITE_URL}/blog/{slug}/"

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": f"{title}: {subtitle}",
        "author": {"@type": "Organization", "name": "Gravel God"},
        "publisher": {
            "@type": "Organization",
            "name": "Gravel God",
            "url": SITE_URL,
        },
        "datePublished": pub_date.isoformat(),
        "about": {
            "@type": "ItemList",
            "numberOfItems": len(races),
        },
    }, separators=(",", ":"))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}: {esc(subtitle)} — Gravel God</title>
  <meta name="description" content="{esc(title)}: {esc(subtitle)}. {stats['count']} races rated and ranked by Gravel God.">
  <meta property="og:title" content="{esc(title)}: {esc(subtitle)} — Gravel God">
  <meta property="og:description" content="{stats['count']} gravel races rated and ranked. Average score: {stats['avg_score']}/100.">
  <meta property="og:url" content="{og_url}">
  <link rel="canonical" href="{og_url}">
  <script type="application/ld+json">{jsonld}</script>
  <style>
    :root {{
      --gg-dark-brown: #3a2e25;
      --gg-primary-brown: #59473c;
      --gg-secondary-brown: #7d695d;
      --gg-teal: #178079;
      --gg-warm-paper: #f5efe6;
      --gg-sand: #ede4d8;
      --gg-white: #ffffff;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; border-radius: 0; }}
    body {{
      font-family: 'Source Serif 4', Georgia, serif;
      background: var(--gg-warm-paper);
      color: var(--gg-dark-brown);
      line-height: 1.7;
    }}
    .gg-blog-container {{ max-width: 900px; margin: 0 auto; padding: 32px 24px; }}
    .gg-blog-hero {{
      background: var(--gg-primary-brown);
      color: var(--gg-warm-paper);
      padding: 48px 32px;
      border: 3px solid var(--gg-dark-brown);
      margin-bottom: 32px;
    }}
    .gg-blog-hero-meta {{
      font-family: 'Sometype Mono', monospace;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 2px;
      opacity: 0.8;
      margin-bottom: 12px;
    }}
    .gg-blog-hero h1 {{
      font-size: 28px;
      font-weight: 700;
      line-height: 1.2;
      margin-bottom: 8px;
    }}
    .gg-blog-hero-sub {{
      font-family: 'Sometype Mono', monospace;
      font-size: 13px;
      opacity: 0.7;
    }}
    .gg-blog-section {{
      margin-bottom: 32px;
      padding: 24px;
      border: 2px solid var(--gg-dark-brown);
      background: var(--gg-white);
    }}
    .gg-blog-section h2 {{
      font-family: 'Sometype Mono', monospace;
      font-size: 14px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 2px;
      margin-bottom: 16px;
      padding-bottom: 8px;
      border-bottom: 2px solid var(--gg-dark-brown);
    }}
    .gg-blog-section p {{ margin-bottom: 12px; font-size: 15px; }}
    .gg-roundup-stats-bar {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 32px;
      padding: 16px;
      border: 2px solid var(--gg-dark-brown);
      background: var(--gg-white);
    }}
    .gg-roundup-stat {{
      font-family: 'Sometype Mono', monospace;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .gg-roundup-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 20px;
      margin-bottom: 32px;
    }}
    .gg-roundup-card {{
      border: 2px solid var(--gg-dark-brown);
      background: var(--gg-white);
      padding: 20px;
    }}
    .gg-roundup-card-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }}
    .gg-roundup-tier {{
      font-family: 'Sometype Mono', monospace;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      color: var(--gg-warm-paper);
      padding: 3px 8px;
    }}
    .gg-roundup-score {{
      font-family: 'Sometype Mono', monospace;
      font-size: 12px;
      font-weight: 700;
      color: var(--gg-secondary-brown);
    }}
    .gg-roundup-card h3 {{
      font-size: 18px;
      font-weight: 700;
      margin-bottom: 4px;
      line-height: 1.3;
    }}
    .gg-roundup-card h3 a {{
      color: var(--gg-dark-brown);
      text-decoration: none;
    }}
    .gg-roundup-card h3 a:hover {{ text-decoration: underline; }}
    .gg-roundup-location {{
      font-family: 'Sometype Mono', monospace;
      font-size: 11px;
      color: var(--gg-secondary-brown);
      margin-bottom: 4px;
    }}
    .gg-roundup-vitals {{
      font-family: 'Sometype Mono', monospace;
      font-size: 11px;
      color: var(--gg-secondary-brown);
      margin-bottom: 8px;
    }}
    .gg-roundup-tagline {{
      font-size: 14px;
      color: var(--gg-secondary-brown);
      margin-bottom: 8px;
      line-height: 1.5;
    }}
    .gg-roundup-link {{
      font-family: 'Sometype Mono', monospace;
      font-size: 12px;
      font-weight: 700;
      color: var(--gg-teal);
      text-decoration: none;
      text-transform: uppercase;
      letter-spacing: 1px;
    }}
    .gg-roundup-link:hover {{ text-decoration: underline; }}
    .gg-blog-cta {{
      text-align: center;
      padding: 32px;
      border: 3px solid var(--gg-dark-brown);
      background: var(--gg-dark-brown);
      margin-bottom: 32px;
    }}
    .gg-blog-cta a {{
      display: inline-block;
      padding: 12px 32px;
      background: var(--gg-teal);
      color: var(--gg-white);
      font-family: 'Sometype Mono', monospace;
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 2px;
      text-decoration: none;
      border: 2px solid var(--gg-teal);
    }}
    .gg-blog-cta a:hover {{ background: var(--gg-primary-brown); border-color: var(--gg-primary-brown); }}
    .gg-blog-footer {{
      text-align: center;
      font-family: 'Sometype Mono', monospace;
      font-size: 11px;
      color: var(--gg-secondary-brown);
      padding: 24px;
      text-transform: uppercase;
      letter-spacing: 1.5px;
    }}
    .gg-blog-footer a {{ color: var(--gg-teal); text-decoration: none; }}
    @media (max-width: 600px) {{
      .gg-blog-hero {{ padding: 32px 20px; }}
      .gg-blog-hero h1 {{ font-size: 22px; }}
      .gg-roundup-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="gg-blog-container">
    <div class="gg-blog-hero">
      <div class="gg-blog-hero-meta">{esc(category_tag)} &middot; {stats['count']} Races</div>
      <h1>{esc(title)}</h1>
      <div class="gg-blog-hero-sub">{esc(subtitle)} &middot; Published {today_str}</div>
    </div>

    <div class="gg-blog-section">
      <p>{esc(intro)}</p>
    </div>

    {stats_bar}

    <div class="gg-roundup-grid">
      {cards}
    </div>

    <div class="gg-blog-cta">
      <a href="{SITE_URL}/gravel-races/">Explore All 328 Races &rarr;</a>
    </div>

    <div class="gg-blog-footer">
      <a href="{SITE_URL}">Gravel God</a> &middot; {today_str}
    </div>
  </div>
</body>
</html>"""


def generate_monthly_roundup(races, year, month, output_dir):
    """Generate a monthly roundup article."""
    month_name = MONTH_NAMES.get(month, "")
    if not month_name:
        print(f"  SKIP  Invalid month: {month}")
        return None

    filtered = filter_by_month(races, year, month)
    if len(filtered) < MIN_RACES_FOR_ROUNDUP:
        return None

    slug = f"roundup-{month_name.lower()}-{year}"
    title = f"{month_name} {year} Gravel Calendar"
    subtitle = f"{len(filtered)} Races to Watch"
    intro = (
        f"Here are the {len(filtered)} gravel races happening in {month_name} {year}, "
        f"rated and ranked by the Gravel God database. From elite-tier classics to "
        f"hidden gems, this is your complete calendar for the month."
    )

    # Publish date: first of the month, capped at today
    pub_date = date(year, month, 1)
    if pub_date > date.today():
        pub_date = date.today()

    html_content = generate_roundup_html(
        title, subtitle, intro, filtered, slug, "Monthly Calendar",
        publish_date=pub_date,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{slug}.html"
    out_file.write_text(html_content)
    print(f"  OK    {slug} ({len(filtered)} races)")
    return slug


def generate_regional_roundup(races, region_key, season, year, output_dir):
    """Generate a regional+seasonal roundup article."""
    season_months = SEASONS.get(season, [])
    if not season_months:
        print(f"  SKIP  Invalid season: {season}")
        return None

    region_display = region_key.replace("-", " ").title()
    season_display = season.title()

    # Filter by region then by season months
    regional = filter_by_region(races, region_key)
    filtered = [r for r in regional
                if MONTH_NUMBERS.get((r.get("month") or "").lower(), 0) in season_months]

    if len(filtered) < MIN_RACES_FOR_ROUNDUP:
        return None

    slug = f"roundup-{region_key}-{season}-{year}"
    title = f"Best {region_display} Gravel Races for {season_display} {year}"
    subtitle = f"{len(filtered)} Races Rated & Ranked"
    intro = (
        f"Looking for gravel races in the {region_display} this {season_display.lower()}? "
        f"We found {len(filtered)} events happening between "
        f"{MONTH_NAMES[season_months[0]]} and {MONTH_NAMES[season_months[-1]]} {year}, "
        f"all rated by the Gravel God scoring system."
    )

    # Publish date: first day of the season's first month, capped at today
    pub_date = date(year, season_months[0], 1)
    if pub_date > date.today():
        pub_date = date.today()

    html_content = generate_roundup_html(
        title, subtitle, intro, filtered, slug, "Regional Roundup",
        publish_date=pub_date,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{slug}.html"
    out_file.write_text(html_content)
    print(f"  OK    {slug} ({len(filtered)} races)")
    return slug


def generate_tier_roundup(races, tier, year, output_dir):
    """Generate a tier-based roundup article."""
    tier_name = TIER_NAMES.get(tier, "")
    if not tier_name:
        print(f"  SKIP  Invalid tier: {tier}")
        return None

    filtered = filter_by_tier(races, tier)
    if len(filtered) < MIN_RACES_FOR_ROUNDUP:
        return None

    slug = f"roundup-tier-{tier}-{year}"
    title = f"{year} {tier_name} Gravel Races"
    subtitle = f"The Complete T{tier} Calendar"
    intro = (
        f"Every Tier {tier} ({tier_name}) gravel race in the Gravel God database for {year}. "
        f"These {len(filtered)} races earned their {tier_name} rating through our "
        f"14-criteria scoring system covering logistics, terrain, prestige, and more."
    )

    # Publish date: Jan 1 of the year, capped at today
    pub_date = date(year, 1, 1)
    if pub_date > date.today():
        pub_date = date.today()

    html_content = generate_roundup_html(
        title, subtitle, intro, filtered, slug, f"T{tier} {tier_name}",
        publish_date=pub_date,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{slug}.html"
    out_file.write_text(html_content)
    print(f"  OK    {slug} ({len(filtered)} races)")
    return slug


def generate_all(races, year, output_dir, dry_run=False):
    """Generate all roundup types."""
    generated = []

    # Monthly roundups
    for month in range(1, 13):
        month_name = MONTH_NAMES[month]
        filtered = filter_by_month(races, year, month)
        if len(filtered) >= MIN_RACES_FOR_ROUNDUP:
            slug = f"roundup-{month_name.lower()}-{year}"
            if dry_run:
                print(f"  CANDIDATE  {slug} ({len(filtered)} races)")
            else:
                result = generate_monthly_roundup(races, year, month, output_dir)
                if result:
                    generated.append(result)

    # Regional + seasonal roundups
    for region_key in REGIONS:
        for season in SEASONS:
            season_months = SEASONS[season]
            regional = filter_by_region(races, region_key)
            filtered = [r for r in regional
                        if MONTH_NUMBERS.get((r.get("month") or "").lower(), 0) in season_months]
            if len(filtered) >= MIN_RACES_FOR_ROUNDUP:
                slug = f"roundup-{region_key}-{season}-{year}"
                if dry_run:
                    print(f"  CANDIDATE  {slug} ({len(filtered)} races)")
                else:
                    result = generate_regional_roundup(
                        races, region_key, season, year, output_dir
                    )
                    if result:
                        generated.append(result)

    # Tier roundups
    for tier in [1, 2, 3, 4]:
        filtered = filter_by_tier(races, tier)
        if len(filtered) >= MIN_RACES_FOR_ROUNDUP:
            slug = f"roundup-tier-{tier}-{year}"
            if dry_run:
                print(f"  CANDIDATE  {slug} ({len(filtered)} races)")
            else:
                result = generate_tier_roundup(races, tier, year, output_dir)
                if result:
                    generated.append(result)

    return generated


def main():
    parser = argparse.ArgumentParser(description="Generate season roundup articles")
    parser.add_argument("--monthly", nargs=2, metavar=("YEAR", "MONTH"),
                        help="Generate monthly roundup (e.g. --monthly 2026 3)")
    parser.add_argument("--regional", nargs=3, metavar=("REGION", "SEASON", "YEAR"),
                        help="Generate regional roundup (e.g. --regional southeast spring 2026)")
    parser.add_argument("--tier", nargs=2, metavar=("TIER", "YEAR"),
                        help="Generate tier roundup (e.g. --tier 1 2026)")
    parser.add_argument("--all-monthly", metavar="YEAR",
                        help="Generate all monthly roundups for a year")
    parser.add_argument("--all", action="store_true",
                        help="Generate all roundups for current year")
    parser.add_argument("--dry-run", action="store_true",
                        help="List candidates without generating")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR),
                        help="Output directory")
    parser.add_argument("--index-file", default=str(INDEX_PATH),
                        help="Path to race-index.json")
    args = parser.parse_args()

    races = load_race_index(Path(args.index_file))
    out_dir = Path(args.output_dir)

    if args.monthly:
        year, month = int(args.monthly[0]), int(args.monthly[1])
        result = generate_monthly_roundup(races, year, month, out_dir)
        if not result:
            print(f"  SKIP  Not enough races for {MONTH_NAMES.get(month, '?')} {year} "
                  f"(need {MIN_RACES_FOR_ROUNDUP})")
        return

    if args.regional:
        region_key, season, year_str = args.regional
        result = generate_regional_roundup(races, region_key, season, int(year_str), out_dir)
        if not result:
            print(f"  SKIP  Not enough races for {region_key} {season} {year_str}")
        return

    if args.tier:
        tier, year_str = int(args.tier[0]), int(args.tier[1])
        result = generate_tier_roundup(races, tier, year_str, out_dir)
        if not result:
            print(f"  SKIP  Not enough T{tier} races for {year_str}")
        return

    if args.all_monthly:
        year = int(args.all_monthly)
        count = 0
        for month in range(1, 13):
            if args.dry_run:
                filtered = filter_by_month(races, year, month)
                if len(filtered) >= MIN_RACES_FOR_ROUNDUP:
                    print(f"  CANDIDATE  roundup-{MONTH_NAMES[month].lower()}-{year} "
                          f"({len(filtered)} races)")
                    count += 1
            else:
                result = generate_monthly_roundup(races, year, month, out_dir)
                if result:
                    count += 1
        print(f"\n{'Found' if args.dry_run else 'Generated'} {count} monthly roundups.")
        return

    if args.all:
        year = date.today().year
        if args.dry_run:
            generate_all(races, year, out_dir, dry_run=True)
        else:
            generated = generate_all(races, year, out_dir)
            print(f"\nGenerated {len(generated)} roundup articles in {out_dir}/")
        return

    parser.error("Provide --monthly, --regional, --tier, --all-monthly, or --all")


if __name__ == "__main__":
    main()
