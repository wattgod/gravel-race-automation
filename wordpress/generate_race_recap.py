#!/usr/bin/env python3
"""
Generate race recap articles from results data + race profiles.

Template-based (no AI API). Creates HTML recap articles for races
that have results data populated in their JSON profiles.

Usage:
    python wordpress/generate_race_recap.py --dry-run           # List candidates
    python wordpress/generate_race_recap.py --slug unbound-200 --year 2024
    python wordpress/generate_race_recap.py --all               # All with results
"""

import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "blog"
SITE_URL = "https://gravelgodcycling.com"

TIER_NAMES = {1: "Elite", 2: "Contender", 3: "Solid", 4: "Roster"}


def esc(text):
    """HTML-escape text."""
    return html.escape(str(text)) if text else ""


def load_race(slug):
    """Load a single race JSON."""
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get("race", data)


def has_results(race, year):
    """Check if a race has results data for a given year."""
    results = race.get("results", {})
    years = results.get("years", {})
    year_data = years.get(str(year), {})
    # Need at least a winner to generate a recap
    return bool(year_data.get("winner_male") or year_data.get("winner_female"))


def find_recap_candidates(year=None):
    """Find races with results data for the given year (or any year)."""
    candidates = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            race = data.get("race", data)
            results = race.get("results", {})
            years_data = results.get("years", {})

            if year:
                if has_results(race, year):
                    candidates.append({
                        "slug": f.stem,
                        "name": race.get("name", f.stem),
                        "year": year,
                        "tier": race.get("gravel_god_rating", {}).get("tier", 4),
                    })
            else:
                for yr in sorted(years_data.keys(), reverse=True):
                    yr_data = years_data[yr]
                    if yr_data.get("winner_male") or yr_data.get("winner_female"):
                        candidates.append({
                            "slug": f.stem,
                            "name": race.get("name", f.stem),
                            "year": int(yr),
                            "tier": race.get("gravel_god_rating", {}).get("tier", 4),
                        })
        except (json.JSONDecodeError, KeyError):
            continue

    candidates.sort(key=lambda c: (c.get("tier", 4), c["slug"]))
    return candidates


def generate_recap_html(slug, year):
    """Generate a recap article HTML for a single race+year."""
    race = load_race(slug)
    if not race:
        print(f"  SKIP  {slug}: JSON not found")
        return None

    if not has_results(race, year):
        print(f"  SKIP  {slug}: no results for {year}")
        return None

    name = race.get("name", slug)
    vitals = race.get("vitals", {})
    gravel_god = race.get("gravel_god_rating", {})
    results = race.get("results", {})
    year_data = results.get("years", {}).get(str(year), {})

    tier = gravel_god.get("tier", 4)
    score = gravel_god.get("overall_score", 0)
    tier_name = TIER_NAMES.get(tier, "Roster")
    location = vitals.get("location", "") or vitals.get("location_badge", "")
    distance = vitals.get("distance_mi", "")
    elevation = vitals.get("elevation_ft", "")

    winner_m = year_data.get("winner_male", "")
    winner_f = year_data.get("winner_female", "")
    time_m = year_data.get("winning_time_male", "")
    time_f = year_data.get("winning_time_female", "")
    conditions = year_data.get("conditions", "")
    field_size = year_data.get("field_size_actual")
    finisher_count = year_data.get("finisher_count")
    dnf_rate = year_data.get("dnf_rate_pct")
    takeaways = year_data.get("key_takeaways", [])

    profile_url = f"{SITE_URL}/race/{slug}/"
    prep_kit_url = f"{SITE_URL}/race/{slug}/prep-kit/"
    og_image_url = f"{SITE_URL}/og/{slug}.jpg"
    recap_slug = f"{slug}-recap"
    og_url = f"{SITE_URL}/blog/{recap_slug}/"

    # Publish date: use date_completed from results, or race date, or derive from year
    pub_date = None
    date_completed = year_data.get("date_completed", "")
    if date_completed:
        try:
            from datetime import datetime
            pub_date = datetime.strptime(date_completed, "%Y-%m-%d").date()
        except ValueError:
            pass
    if not pub_date:
        # Try race's date_specific
        date_str = vitals.get("date_specific", "")
        if date_str:
            import re
            m = re.match(r"(\d{4}).*?(\w+)\s+(\d+)", str(date_str))
            if m:
                month_nums = {
                    "january": 1, "february": 2, "march": 3, "april": 4,
                    "may": 5, "june": 6, "july": 7, "august": 8,
                    "september": 9, "october": 10, "november": 11, "december": 12,
                }
                mn = month_nums.get(m.group(2).lower())
                if mn:
                    try:
                        pub_date = date(int(m.group(1)), mn, int(m.group(3)))
                    except ValueError:
                        pass
    if not pub_date:
        # Fall back to July 1 of the recap year (mid-season)
        pub_date = date(year, 7, 1)
    # Cap at today
    if pub_date > date.today():
        pub_date = date.today()
    today_str = pub_date.strftime("%B %d, %Y")
    article_date_iso = pub_date.isoformat()

    # Headline based on available data
    headline_parts = []
    if winner_m:
        headline_parts.append(f"{winner_m} Takes the Win")
    elif winner_f:
        headline_parts.append(f"{winner_f} Wins")
    else:
        headline_parts.append("Race Results")
    headline = " — ".join(headline_parts)

    # Winners section
    winners_html = ""
    if winner_m or winner_f:
        rows = []
        if winner_m:
            time_display = f" ({esc(time_m)})" if time_m else ""
            rows.append(f"""
          <div class="gg-recap-winner">
            <span class="gg-recap-label">Men's Winner</span>
            <span class="gg-recap-value">{esc(winner_m)}{time_display}</span>
          </div>""")
        if winner_f:
            time_display = f" ({esc(time_f)})" if time_f else ""
            rows.append(f"""
          <div class="gg-recap-winner">
            <span class="gg-recap-label">Women's Winner</span>
            <span class="gg-recap-value">{esc(winner_f)}{time_display}</span>
          </div>""")
        winners_html = f"""
    <section class="gg-blog-section">
      <h2>Winners</h2>
      <div class="gg-recap-winners">{''.join(rows)}</div>
    </section>"""

    # Conditions section
    conditions_html = ""
    if conditions:
        conditions_html = f"""
    <section class="gg-blog-section">
      <h2>Conditions</h2>
      <p>{esc(conditions)}</p>
    </section>"""

    # Stats grid
    stats_items = []
    if distance:
        stats_items.append(f'<div class="gg-blog-stat"><span class="gg-blog-stat-val">{esc(str(distance))}</span><span class="gg-blog-stat-label">Miles</span></div>')
    if elevation:
        if isinstance(elevation, (int, float)):
            elev_display = f"{int(elevation):,}"
        else:
            elev_display = str(elevation)
        stats_items.append(f'<div class="gg-blog-stat"><span class="gg-blog-stat-val">{esc(elev_display)}</span><span class="gg-blog-stat-label">Ft Elevation</span></div>')
    if field_size:
        stats_items.append(f'<div class="gg-blog-stat"><span class="gg-blog-stat-val">{field_size:,}</span><span class="gg-blog-stat-label">Starters</span></div>')
    if finisher_count:
        stats_items.append(f'<div class="gg-blog-stat"><span class="gg-blog-stat-val">{finisher_count:,}</span><span class="gg-blog-stat-label">Finishers</span></div>')
    if dnf_rate is not None:
        stats_items.append(f'<div class="gg-blog-stat"><span class="gg-blog-stat-val">{dnf_rate}%</span><span class="gg-blog-stat-label">DNF Rate</span></div>')
    stats_html = ""
    if stats_items:
        stats_html = f"""
    <section class="gg-blog-section">
      <h2>Key Stats</h2>
      <div class="gg-blog-stats">{''.join(stats_items)}</div>
    </section>"""

    # Key takeaways
    takeaways_html = ""
    if takeaways:
        items = "".join(f"<li>{esc(t)}</li>" for t in takeaways)
        takeaways_html = f"""
    <section class="gg-blog-section">
      <h2>Key Takeaways</h2>
      <ul>{items}</ul>
    </section>"""

    # JSON-LD
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": f"{name} {year} Race Recap — {headline}",
        "author": {"@type": "Organization", "name": "Gravel God"},
        "publisher": {
            "@type": "Organization",
            "name": "Gravel God",
            "url": SITE_URL,
        },
        "datePublished": article_date_iso,
        "image": og_image_url,
        "about": {
            "@type": "SportsEvent",
            "name": f"{name} {year}",
            "url": profile_url,
        },
    }, separators=(",", ":"))

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(name)} {year} Race Recap — Gravel God</title>
  <meta name="description" content="{esc(name)} {year} recap: {esc(headline)}. Tier {tier} {tier_name} rated {score}/100.">
  <meta property="og:title" content="{esc(name)} {year} Race Recap — Gravel God">
  <meta property="og:description" content="{esc(headline)}. Tier {tier} {tier_name} gravel race.">
  <meta property="og:image" content="{og_image_url}">
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
    .gg-blog-container {{ max-width: 780px; margin: 0 auto; padding: 32px 24px; }}
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
    .gg-blog-section ul {{ margin: 12px 0 12px 24px; font-size: 15px; }}
    .gg-blog-section li {{ margin-bottom: 6px; }}
    .gg-blog-section a {{
      color: var(--gg-teal);
      text-decoration: none;
      font-weight: 600;
    }}
    .gg-blog-section a:hover {{ text-decoration: underline; }}
    .gg-recap-winners {{ display: flex; flex-direction: column; gap: 16px; }}
    .gg-recap-winner {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      border: 2px solid var(--gg-dark-brown);
      background: var(--gg-warm-paper);
    }}
    .gg-recap-label {{
      font-family: 'Sometype Mono', monospace;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      color: var(--gg-secondary-brown);
    }}
    .gg-recap-value {{
      font-family: 'Sometype Mono', monospace;
      font-size: 14px;
      font-weight: 700;
    }}
    .gg-blog-stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 16px;
    }}
    .gg-blog-stat {{
      text-align: center;
      padding: 16px;
      border: 2px solid var(--gg-dark-brown);
      background: var(--gg-warm-paper);
    }}
    .gg-blog-stat-val {{
      font-family: 'Sometype Mono', monospace;
      font-size: 20px;
      font-weight: 700;
      display: block;
    }}
    .gg-blog-stat-label {{
      font-family: 'Sometype Mono', monospace;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 1.5px;
      color: var(--gg-secondary-brown);
    }}
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
      margin: 6px;
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
      .gg-blog-section {{ padding: 16px; }}
      .gg-recap-winner {{ flex-direction: column; gap: 4px; text-align: center; }}
    }}
  </style>
</head>
<body>
  <div class="gg-blog-container">
    <div class="gg-blog-hero">
      <div class="gg-blog-hero-meta">Race Recap &middot; Tier {tier} {esc(tier_name)} &middot; {esc(location)}</div>
      <h1>{esc(name)} {year} Recap</h1>
      <div class="gg-blog-hero-sub">{esc(headline)} &middot; Published {today_str}</div>
    </div>
    {winners_html}
    {conditions_html}
    {stats_html}
    {takeaways_html}

    <div class="gg-blog-cta">
      <a href="{profile_url}">Full Race Profile &rarr;</a>
      <a href="{prep_kit_url}">Free Prep Kit &rarr;</a>
    </div>

    <div class="gg-blog-footer">
      <a href="{SITE_URL}">Gravel God</a> &middot; {today_str}
    </div>
  </div>
</body>
</html>"""

    return page_html


def main():
    parser = argparse.ArgumentParser(description="Generate race recap articles")
    parser.add_argument("--slug", help="Generate recap for a single race")
    parser.add_argument("--year", type=int, help="Year for the recap")
    parser.add_argument("--all", action="store_true", help="Generate all available recaps")
    parser.add_argument("--dry-run", action="store_true", help="List candidates without generating")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)

    if args.dry_run:
        candidates = find_recap_candidates(args.year)
        if not candidates:
            print("No races with results data found.")
            return
        print(f"{'SLUG':<40} {'YEAR':>4} {'TIER':>4}")
        print("-" * 50)
        for c in candidates:
            print(f"{c['slug']:<40} {c['year']:>4} T{c['tier']:>3}")
        print(f"\n{len(candidates)} candidates found.")
        return

    if args.slug:
        year = args.year
        if not year:
            # Try to get latest year from results
            race = load_race(args.slug)
            if race:
                year_str = race.get("results", {}).get("latest_year", "")
                year = int(year_str) if year_str else None
        if not year:
            parser.error("Provide --year for the recap")
            return

        html_content = generate_recap_html(args.slug, year)
        if html_content:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{args.slug}-recap.html"
            out_file.write_text(html_content)
            print(f"  OK    {out_file}")
        return

    if args.all:
        candidates = find_recap_candidates(args.year)
        if not candidates:
            print("No races with results data found.")
            return

        out_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for c in candidates:
            html_content = generate_recap_html(c["slug"], c["year"])
            if html_content:
                out_file = out_dir / f"{c['slug']}-recap.html"
                out_file.write_text(html_content)
                print(f"  OK    T{c['tier']} {c['slug']} ({c['year']})")
                count += 1

        print(f"\nGenerated {count} recap articles in {out_dir}/")
        return

    parser.error("Provide --slug NAME --year YYYY, --all, or --dry-run")


if __name__ == "__main__":
    main()
