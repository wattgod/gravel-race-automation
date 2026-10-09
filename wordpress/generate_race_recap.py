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
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import TIER_NAMES
from blog_tracking import get_plan_intent_tracking_script
from editorial_shell import ArticleMeta, Claim, OgImage, render_editorial_page

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


def newest_results_year(race):
    """The newest year (int) that has a winner, or None.

    Every recap of a race writes to the same {slug}-recap.html (one URL per
    race), so with no --year only the newest year may be generated: listing
    each year let whichever ran last, the oldest, overwrite the newest.
    """
    years = race.get("results", {}).get("years", {}) or {}
    eligible = [int(yr) for yr in years
                if str(yr).strip().isdigit() and has_results(race, int(yr))]
    return max(eligible) if eligible else None


def find_recap_candidates(year=None):
    """Races with results for the given year, or (no year) each race's newest results year."""
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
                newest = newest_results_year(race)
                if newest is not None:
                    candidates.append({
                        "slug": f.stem,
                        "name": race.get("name", f.stem),
                        "year": newest,
                        "tier": race.get("gravel_god_rating", {}).get("tier", 4),
                    })
        except (json.JSONDecodeError, KeyError):
            continue

    candidates.sort(key=lambda c: (c.get("tier", 4), c["slug"]))
    return candidates


_MONTHS = {
    name: num
    for num, names in enumerate((
        ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"),
        ("may",), ("june", "jun"), ("july", "jul"), ("august", "aug"),
        ("september", "sep", "sept"), ("october", "oct"), ("november", "nov"),
        ("december", "dec"),
    ), start=1)
    for name in names
}


def recap_publish_date(year_data, vitals, year):
    """A recap's publish date: stable for the same data, never read from today.

    See recap_date_parts() for the rules.
    """
    return recap_date_parts(year_data, vitals, year)[0]


def recap_date_parts(year_data, vitals, year):
    """(publish date, exact). exact is False for the December 31 fallback,
    which is a stand-in, not a day anything happened.

    1. results.years[year].date_completed (YYYY-MM-DD in the results year).
    2. vitals.date_specific when it names the results year ("2026: Aug 19-23"
       is that edition's own date; the last day of a range is when it ended).
    3. December 31 of the results year: after any race that season.

    date_specific for another year (usually the next edition) is never used:
    its month and day are not the date the results year's race ran.
    """
    completed = str(year_data.get("date_completed") or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", completed)
    if m and int(m.group(1)) == year:
        try:
            return date(year, int(m.group(2)), int(m.group(3))), True
        except ValueError:
            pass
    m = re.match(r"\s*(\d{4})\s*:\s*([A-Za-z]+)\.?\s+(\d{1,2})(?:\s*[-\u2013]\s*(\d{1,2}))?\b",
                 str(vitals.get("date_specific") or ""))
    if m and int(m.group(1)) == year:
        month = _MONTHS.get(m.group(2).lower())
        if month:
            try:
                return date(year, month, int(m.group(4) or m.group(3))), True
            except ValueError:
                pass
    return date(year, 12, 31), False


# ── "In short" (spec: ~/specs/gg-editorial-shell-2026-10-08/IN_SHORT_SPEC.md) ──
# Every claim is a fixed template over results fields, or the first sentence
# of a results string quoted as is. A claim that can't be built cleanly is
# skipped; fewer than IN_SHORT_MIN claims renders no "In short".
IN_SHORT_MIN = 2
IN_SHORT_MAX_WORDS = 25
# First sentence: ends at . or ? (plus closing quotes) followed by a new
# sentence or the end. No terminal punctuation = cut off, so no sentence.
_SENTENCE_END = re.compile(r"[.?][\"'\u2019\u201d)]*(?=\s+[\"\u201cA-Z0-9]|$)")
# Third person only: no "I", "we", "our", "my", "you", "your".
_FIRST_PERSON = re.compile(r"\bI\b|\b(?:[Ww][Ee]|[Oo]urs?|[Mm]y|[Yy]ou|[Yy]our)\b")
_BANNED_MARKS = ("!", "\u2014", " \u2013 ", " - ", "http", "](", "[", "\t", "\u2022", "...", "\u2026")
# A period after one of these (or after a single letter, as in initials)
# doesn't end a sentence: "St. George", "U.S. Open", "J. Smith".
_ABBREVIATIONS = {
    "st", "mt", "mr", "mrs", "ms", "dr", "jr", "sr", "vs", "approx", "est",
    "no", "ft", "mi", "km", "e.g", "i.e", "u.s", "u.k", "etc", "ave", "rd",
}


def _claim_ok(text):
    """Voice and size rules every claim must pass."""
    if len(text.split()) > IN_SHORT_MAX_WORDS:
        return False
    if any(mark in text for mark in _BANNED_MARKS):
        return False
    if _FIRST_PERSON.search(text):
        return False
    if re.search(r"\bnot\b[^.?]*\bbut\b", text, re.I):
        return False
    return True


def first_sentence(text):
    """The first complete sentence of a results string, or None.

    None when the string starts mid-sentence (lowercase, a bullet or a
    bracket) or has no terminal punctuation (cut off at extraction).
    """
    text = " ".join(str(text or "").split())
    if not text or not (text[0].isupper() or text[0].isdigit()):
        return None
    for m in _SENTENCE_END.finditer(text):
        candidate = text[:m.end()]
        word = re.search(r"(\S+?)[.?][\"'\u2019\u201d)]*$", candidate)
        token = (word.group(1) if word else "").lstrip("(\"'\u201c").lower()
        if m.group(0)[0] == "." and (token in _ABBREVIATIONS or len(token) == 1):
            continue
        return candidate
    return None


def _join_clauses(clauses):
    if len(clauses) == 1:
        return clauses[0]
    return ", ".join(clauses[:-1]) + " and " + clauses[-1]


def winners_claim(year_data):
    """ "{M} won the men's race in {t} and {F} won the women's race in {t}." """
    winner_m = str(year_data.get("winner_male") or "").strip()
    winner_f = str(year_data.get("winner_female") or "").strip()
    if winner_m and winner_m == winner_f:
        return None  # one name for both races contradicts itself; don't repeat it
    clauses = []
    for name, time, race in ((winner_m, year_data.get("winning_time_male"), "men's"),
                             (winner_f, year_data.get("winning_time_female"), "women's")):
        if name:
            clause = f"{name} won the {race} race"
            if time:
                clause += f" in {str(time).strip()}"
            clauses.append(clause)
    return _join_clauses(clauses) + "." if clauses else None


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def stat_claim(year_data):
    """Starters, finishers and DNF rate, whichever exist, in one sentence.

    The winning time is not repeated here: the winners claim carries it.
    """
    starters = _count(year_data.get("field_size_actual"))
    finishers = _count(year_data.get("finisher_count"))
    dnf = year_data.get("dnf_rate_pct")
    dnf = dnf if isinstance(dnf, (int, float)) and not isinstance(dnf, bool) else None
    clauses = []
    if starters:
        clauses.append(f"{starters:,} riders started")
    if finishers:
        clauses.append(f"{finishers:,} finished" if starters else f"{finishers:,} riders finished")
    if dnf is not None:
        clauses.append(f"the DNF rate was {dnf}%")
    if not clauses:
        return None
    text = _join_clauses(clauses)
    return text[0].upper() + text[1:] + "."


def build_in_short(year_data, section_index):
    """Recap "In short" claims, in spec order, skipping any that lack clean data.

    section_index maps h2 id -> (0-based h2 position, heading text); a claim
    is only built when its section is on the page. Returns a list of Claim.
    """
    takeaways = year_data.get("key_takeaways") or []
    takeaways = takeaways if isinstance(takeaways, list) else []
    candidates = (
        ("winners", winners_claim(year_data)),
        ("conditions", first_sentence(year_data.get("conditions"))),
        ("key-stats", stat_claim(year_data)),
        ("key-takeaways", first_sentence(takeaways[0]) if takeaways else None),
    )
    claims = []
    for section_id, text in candidates:
        if not text or section_id not in section_index or not _claim_ok(text):
            continue
        pos, heading = section_index[section_id]
        claims.append(Claim(esc(text), f"#{section_id}", f"{heading} · §{pos + 1:02d}", pos))
    return claims


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

    pub_date, pub_date_exact = recap_date_parts(year_data, vitals, year)
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
    # h2 id -> (0-based h2 position, heading): the "In short" link targets.
    section_index = {}

    def add_section(section_id, heading, section_html):
        section_index[section_id] = (len(section_index), heading)
        sections.append(section_html)

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
        add_section("winners", "Winners", f"""
    <section class="gg-blog-section">
      <h2 id="winners">Winners</h2>
      <div class="gg-recap-winners">{''.join(rows)}</div>
    </section>""")

    if conditions:
        add_section("conditions", "Conditions", f"""
    <section class="gg-blog-section">
      <h2 id="conditions">Conditions</h2>
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
        add_section("key-stats", "Key Stats", f"""
    <section class="gg-blog-section">
      <h2 id="key-stats">Key Stats</h2>
      <div class="gg-blog-stats">{''.join(stats_items)}</div>
    </section>""")

    if takeaways:
        items = "".join(f"<li>{esc(t)}</li>" for t in takeaways)
        add_section("key-takeaways", "Key Takeaways", f"""
    <section class="gg-blog-section">
      <h2 id="key-takeaways">Key Takeaways</h2>
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
        # The Dec 31 fallback keeps JSON-LD and the index stable, but the
        # byline shows only what's known: the results year.
        byline_date=None if pub_date_exact else f"{year} results",
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
    claims = build_in_short(year_data, section_index)
    return render_editorial_page(
        meta,
        "".join(sections) + cta_html,
        in_short=claims if len(claims) >= IN_SHORT_MIN else None,
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
