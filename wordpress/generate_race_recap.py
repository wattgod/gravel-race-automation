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

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import TIER_NAMES
from blog_tracking import get_plan_intent_tracking_script
from editorial_shell import ArticleMeta, OgImage, render_editorial_page

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "blog"
SITE_URL = "https://gravelgodcycling.com"

# Recap-only blocks on top of editorial_shell.SHELL_CSS (shell tokens only).
# Winners and stats are measurements: mono labels, no chart, no glyphs.
RECAP_CSS = """
.gg-recap-winners{display:flex;flex-direction:column;gap:6px}
.gg-recap-winner{display:flex;justify-content:space-between;align-items:baseline;gap:16px;background:var(--sand);padding:16px 20px}
.gg-recap-label{font:700 13px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink3)}
.gg-recap-value{font:700 20px/1.35 var(--serif);text-align:right}
.gg-blog-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:6px}
.gg-blog-stat{background:var(--sand);padding:18px 20px}
.gg-blog-stat-val{display:block;font:700 30px/1.1 var(--mono);font-variant-numeric:tabular-nums;margin-bottom:6px}
.gg-blog-stat-label{display:block;font:700 12px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--ink3)}
.gg-blog-cta{display:flex;flex-wrap:wrap;gap:10px;margin:56px 0 0}
@media (max-width:640px){
  .gg-recap-winner{flex-direction:column;gap:4px;padding:14px 16px}
  .gg-recap-value{text-align:left;font-size:19px}
  .gg-blog-stats{grid-template-columns:1fr 1fr}
  .gg-blog-stat-val{font-size:26px}
}
"""


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
    tier_name = TIER_NAMES.get(tier, "Grassroots")
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

    # Winners: label + value rows (same copy as before the shell move)
    sections = []
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
        sections.append(f"""
    <section class="gg-blog-section">
      <h2>Winners</h2>
      <div class="gg-recap-winners">{''.join(rows)}</div>
    </section>""")

    if conditions:
        sections.append(f"""
    <section class="gg-blog-section">
      <h2>Conditions</h2>
      <p>{esc(conditions)}</p>
    </section>""")

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
    if stats_items:
        sections.append(f"""
    <section class="gg-blog-section">
      <h2>Key Stats</h2>
      <div class="gg-blog-stats">{''.join(stats_items)}</div>
    </section>""")

    if takeaways:
        items = "".join(f"<li>{esc(t)}</li>" for t in takeaways)
        sections.append(f"""
    <section class="gg-blog-section">
      <h2>Key Takeaways</h2>
      <ul>{items}</ul>
    </section>""")

    # The 1200x630 share card repeats the title, tier and score, so it sits
    # after the first section as a body image (the essays' inline-image
    # block), not in the hero. gg-blog-hero-img stays on the img: the blog
    # validator checks every non-roundup post for it.
    share_card = f"""
    <div class="gg-article-img-inline">
      <img class="gg-blog-hero-img" src="{esc(og_image_url)}" alt="{esc(f'{name} {year} race recap')}" width="1200" height="630" loading="lazy">
    </div>"""
    sections.insert(1 if sections else 0, share_card)

    # Race-specific CTAs: same hrefs and copy as before; real buttons, so chamfer.
    cta_html = f"""
    <div class="gg-blog-cta">
      <a class="btn" href="{profile_url}">Full Race Profile <span class="chev" aria-hidden="true">&rsaquo;</span></a>
      <a class="btn" href="{prep_kit_url}">Free Prep Kit <span class="chev" aria-hidden="true">&rsaquo;</span></a>
    </div>"""

    # JSON-LD (kept on recaps, as before; compact string passed through verbatim)
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

    title = f"{name} {year} Race Recap — Gravel God"
    meta = ArticleMeta(
        slug=recap_slug,
        canonical_url=og_url,
        title=title,
        description=f"{name} {year} recap: {headline}. Tier {tier} {tier_name} rated {score}/100.",
        headline=f"{name} {year} Recap",
        date_published=pub_date,
        kicker=f"Race Recap · Tier {tier} {tier_name}" + (f" · {location}" if location else ""),
        dek=headline,
        robots="noindex, follow",
        og_title=title,
        og_description=f"{headline}. Tier {tier} {tier_name} gravel race.",
        og_image=OgImage(url=og_image_url, width=1200, height=630),
        hero_class="gg-blog-hero",
        json_ld=(jsonld,),
        track_article_events=False,
        show_read_time=False,
    )
    return render_editorial_page(
        meta,
        "".join(sections) + cta_html,
        ladder=False,
        extra_css=RECAP_CSS,
        extra_body_end=get_plan_intent_tracking_script(),
    )


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
