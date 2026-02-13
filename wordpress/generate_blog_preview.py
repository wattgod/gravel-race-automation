#!/usr/bin/env python3
"""
Generate race preview blog articles from race JSON data.

Template-based (no Claude API needed). Creates HTML preview articles
for races with upcoming dates, timed to registration windows.

Usage:
    python wordpress/generate_blog_preview.py --dry-run       # List candidates
    python wordpress/generate_blog_preview.py --slug mid-south # Single preview
    python wordpress/generate_blog_preview.py --all            # All upcoming races
"""

import argparse
import html
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "blog"
SITE_URL = "https://gravelgodcycling.com"

TIER_NAMES = {1: "Elite", 2: "Contender", 3: "Solid", 4: "Roster"}
MONTH_NUMBERS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def esc(text):
    """HTML-escape text."""
    return html.escape(str(text)) if text else ""


def parse_race_date(date_str):
    """Parse date_specific string like '2026: June 6' into a date object."""
    if not date_str:
        return None
    match = re.match(r"(\d{4}).*?(\w+)\s+(\d+)", str(date_str))
    if not match:
        return None
    year, month_name, day = match.groups()
    month_num = MONTH_NUMBERS.get(month_name.lower())
    if not month_num:
        return None
    try:
        return date(int(year), month_num, int(day))
    except ValueError:
        return None


def load_race(slug):
    """Load a single race JSON."""
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return data.get("race", data)


def load_all_races():
    """Load all race JSONs."""
    races = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            rd = data.get("race", data)
            rd["_slug"] = f.stem
            races.append(rd)
        except (json.JSONDecodeError, KeyError):
            continue
    return races


def find_candidates(min_days=30, max_days=120):
    """Find races with dates in the registration window.

    Returns races whose date is 30-120 days from now,
    sorted by tier (T1 first) then by date proximity.
    """
    today = date.today()
    candidates = []

    for race in load_all_races():
        date_str = race.get("vitals", {}).get("date_specific", "")
        race_date = parse_race_date(date_str)
        if not race_date:
            continue

        days_until = (race_date - today).days
        if min_days <= days_until <= max_days:
            gravel_god = race.get("gravel_god_rating", {})
            candidates.append({
                "slug": race["_slug"],
                "name": race.get("name", race["_slug"]),
                "date": race_date,
                "days_until": days_until,
                "tier": gravel_god.get("tier", 4),
                "score": gravel_god.get("overall_score", 0),
            })

    # Sort: T1 first, then by date proximity
    candidates.sort(key=lambda c: (c["tier"], c["days_until"]))
    return candidates


def generate_preview_html(slug):
    """Generate a preview article HTML for a single race."""
    rd = load_race(slug)
    if not rd:
        print(f"  SKIP  {slug}: JSON not found")
        return None

    name = rd.get("name", slug)
    vitals = rd.get("vitals", {})
    gravel_god = rd.get("gravel_god_rating", {})
    biased = rd.get("biased_opinion", {})
    final_verdict = rd.get("final_verdict", {})
    course_desc = rd.get("course_description", {})
    history = rd.get("history", {})
    logistics = rd.get("logistics", {})
    non_negotiables = rd.get("non_negotiables", [])

    tier = gravel_god.get("tier", 4)
    score = gravel_god.get("overall_score", 0)
    tier_name = TIER_NAMES.get(tier, "Roster")
    location = vitals.get("location", "") or vitals.get("location_badge", "")
    date_str = vitals.get("date_specific", "") or vitals.get("date", "")
    distance = vitals.get("distance_mi", "")
    elevation = vitals.get("elevation_ft", "")
    field_size = vitals.get("field_size", "")
    terrain_types = vitals.get("terrain_types", "")
    registration = vitals.get("registration", "")
    official_site = logistics.get("official_site", "")
    if official_site and not str(official_site).startswith("http"):
        official_site = ""

    profile_url = f"{SITE_URL}/race/{slug}/"
    prep_kit_url = f"{SITE_URL}/race/{slug}/prep-kit/"
    og_image_url = f"{SITE_URL}/og/{slug}.jpg"

    # Article date — use race date, not today's date
    race_date_obj = parse_race_date(date_str)
    if race_date_obj:
        # Publish preview ~60 days before the race
        preview_date = race_date_obj - timedelta(days=60)
        # But never future-date (cap at today)
        if preview_date > date.today():
            preview_date = date.today()
    else:
        preview_date = date.today()
    article_date_str = preview_date.strftime("%B %d, %Y")
    article_date_iso = preview_date.isoformat()

    # Build sections
    why_section = ""
    should_race = final_verdict.get("should_you_race", "")
    biased_summary = biased.get("summary", "")
    if should_race or biased_summary:
        why_section = f"""
    <section class="gg-blog-section">
      <h2>Why Race {esc(name)}?</h2>
      {f'<p>{esc(should_race)}</p>' if should_race else ''}
      {f'<p>{esc(biased_summary)}</p>' if biased_summary else ''}
    </section>"""

    course_section = ""
    character = course_desc.get("character", "")
    suffering = course_desc.get("suffering_zones", "")
    if character or suffering:
        course_section = f"""
    <section class="gg-blog-section">
      <h2>Course Preview</h2>
      {f'<p>{esc(character)}</p>' if character else ''}
      {f'<p><strong>Key challenges:</strong> {esc(suffering)}</p>' if suffering else ''}
    </section>"""

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
        stats_items.append(f'<div class="gg-blog-stat"><span class="gg-blog-stat-val">{esc(str(field_size))}</span><span class="gg-blog-stat-label">Field Size</span></div>')
    if terrain_types:
        stats_items.append(f'<div class="gg-blog-stat"><span class="gg-blog-stat-val">{esc(str(terrain_types))}</span><span class="gg-blog-stat-label">Terrain</span></div>')
    stats_section = ""
    if stats_items:
        stats_section = f"""
    <section class="gg-blog-section">
      <h2>Key Stats</h2>
      <div class="gg-blog-stats">{''.join(stats_items)}</div>
    </section>"""

    training_section = ""
    if non_negotiables:
        top3 = non_negotiables[:3]
        items = "".join(f"<li>{esc(n)}</li>" for n in top3)
        training_section = f"""
    <section class="gg-blog-section">
      <h2>Training Focus</h2>
      <p>To be competitive at {esc(name)}, prioritize these non-negotiables:</p>
      <ol>{items}</ol>
    </section>"""

    history_section = ""
    origin = history.get("origin_story", "")
    notable = history.get("notable_moments", "")
    if origin or notable:
        history_section = f"""
    <section class="gg-blog-section">
      <h2>History</h2>
      {f'<p>{esc(origin)}</p>' if origin else ''}
      {f'<p><strong>Notable moments:</strong> {esc(notable)}</p>' if notable else ''}
    </section>"""

    reg_section = ""
    if registration or official_site:
        reg_section = f"""
    <section class="gg-blog-section">
      <h2>Registration &amp; Info</h2>
      {f'<p><strong>Registration:</strong> {esc(str(registration))}</p>' if registration else ''}
      {f'<p><a href="{esc(official_site)}">Official Website &rarr;</a></p>' if official_site else ''}
    </section>"""

    # JSON-LD Article schema
    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": f"{name} Race Preview — What to Expect in {preview_date.year}",
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
            "name": name,
            "url": profile_url,
        },
    }, separators=(",", ":"))

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(name)} Race Preview — Gravel God</title>
  <meta name="description" content="Everything you need to know about {esc(name)}: course preview, key stats, training tips, and registration info. Tier {tier} {tier_name} rated {score}/100.">
  <meta property="og:title" content="{esc(name)} Race Preview — Gravel God">
  <meta property="og:description" content="Tier {tier} {tier_name} gravel race. {esc(location)}. Rated {score}/100.">
  <meta property="og:image" content="{og_image_url}">
  <meta property="og:url" content="{SITE_URL}/blog/{slug}/">
  <link rel="canonical" href="{SITE_URL}/blog/{slug}/">
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
    .gg-blog-section ol, .gg-blog-section ul {{ margin: 12px 0 12px 24px; font-size: 15px; }}
    .gg-blog-section li {{ margin-bottom: 6px; }}
    .gg-blog-section a {{
      color: var(--gg-teal);
      text-decoration: none;
      font-weight: 600;
    }}
    .gg-blog-section a:hover {{ text-decoration: underline; }}
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
    }}
  </style>
</head>
<body>
  <div class="gg-blog-container">
    <div class="gg-blog-hero">
      <div class="gg-blog-hero-meta">Tier {tier} {esc(tier_name)} &middot; {esc(location)} &middot; {esc(date_str)}</div>
      <h1>{esc(name)} Race Preview</h1>
      <div class="gg-blog-hero-sub">Rated {score} / 100 &middot; Published {article_date_str}</div>
    </div>
    {why_section}
    {course_section}
    {stats_section}
    {training_section}
    {history_section}
    {reg_section}

    <div class="gg-blog-cta">
      <a href="{profile_url}">Full Race Profile &rarr;</a>
      <a href="{prep_kit_url}">Free Prep Kit &rarr;</a>
    </div>

    <div class="gg-blog-footer">
      <a href="{SITE_URL}">Gravel God</a> &middot; {article_date_str}
    </div>
  </div>
</body>
</html>"""

    return page_html


def main():
    parser = argparse.ArgumentParser(description="Generate race preview blog articles")
    parser.add_argument("--slug", help="Generate preview for a single race slug")
    parser.add_argument("--all", action="store_true", help="Generate for all upcoming races")
    parser.add_argument("--dry-run", action="store_true", help="List candidates without generating")
    parser.add_argument("--min-days", type=int, default=30, help="Minimum days until race (default: 30)")
    parser.add_argument("--max-days", type=int, default=120, help="Maximum days until race (default: 120)")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)

    if args.dry_run:
        candidates = find_candidates(args.min_days, args.max_days)
        if not candidates:
            print("No races found in the registration window "
                  f"({args.min_days}-{args.max_days} days from now).")
            return
        print(f"{'SLUG':<40} {'TIER':>4} {'SCORE':>5} {'DATE':>12} {'DAYS':>5}")
        print("-" * 70)
        for c in candidates:
            print(f"{c['slug']:<40} T{c['tier']:>3} {c['score']:>5} "
                  f"{c['date'].isoformat():>12} {c['days_until']:>5}")
        print(f"\n{len(candidates)} candidates found.")
        return

    if args.slug:
        html_content = generate_preview_html(args.slug)
        if html_content:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_file = out_dir / f"{args.slug}.html"
            out_file.write_text(html_content)
            print(f"  OK    {out_file}")
        return

    if args.all:
        candidates = find_candidates(args.min_days, args.max_days)
        if not candidates:
            print("No races found in the registration window.")
            return

        out_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for c in candidates:
            html_content = generate_preview_html(c["slug"])
            if html_content:
                out_file = out_dir / f"{c['slug']}.html"
                out_file.write_text(html_content)
                print(f"  OK    T{c['tier']} {c['slug']}")
                count += 1

        print(f"\nGenerated {count} preview articles in {out_dir}/")
        return

    parser.error("Provide --slug NAME, --all, or --dry-run")


if __name__ == "__main__":
    main()
