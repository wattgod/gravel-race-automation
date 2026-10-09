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
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import TIER_NAMES
from blog_tracking import get_plan_intent_tracking_script
from editorial_shell import ArticleMeta, Claim, render_editorial_page

# Roundups indexable only via the owner-approved allowlist (WS5 Option A).
INDEXABLE_ROUNDUPS = frozenset(
    __import__("json").loads(
        (Path(__file__).resolve().parent.parent / "config" / "indexable-roundups.json")
        .read_text())["indexable"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = PROJECT_ROOT / "web" / "race-index.json"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "blog"
SITE_URL = "https://gravelgodcycling.com"
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

# "In short" (spec: ~/specs/gg-editorial-shell-2026-10-08/IN_SHORT_SPEC.md).
# Every claim is a fixed template over race-index.json fields; no prose source.
STATS_ID = "roundup-stats"  # the stats bar
RACES_ID = "roundup-races"  # the race grid on a single-tier page (no tier h2s)
MAX_CLAIM_WORDS = 25
MIN_CLAIMS = 2
# Banned: first person ("I ", "we " as words, so "UCI Gravel" passes),
# exclamation marks and em-dash asides. Checked on the template text only:
# a race name is data quoted as is ("Tour of Thekkady \u2014 Kerala Gran Fondo").
BANNED_CLAIM_RE = re.compile(r"(?<![A-Za-z])(?:I|[Ww]e) |!| \u2014 ")

# Roundup blocks on the editorial shell (its tokens: --ink, --sand, --mono...).
# The tier badge keeps TIER_COLORS (inline), since its colour encodes the tier.
ROUNDUP_CSS = """
.gg-roundup-stats-bar{display:flex;flex-wrap:wrap;gap:6px 22px;margin:4px 0 0;padding:14px 0 0;box-shadow:inset 0 2px 0 var(--sand2)}
.gg-roundup-stat{font:700 13px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--ink2)}
.gg-roundup-group .gg-roundup-grid{margin-top:8px}
.gg-roundup-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin:40px 0 0}
.gg-roundup-group h2 + .gg-roundup-grid{margin-top:0}
.gg-roundup-card{background:var(--sand);padding:18px 20px 16px;display:flex;flex-direction:column;min-width:0}
.gg-roundup-card-header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}
.gg-roundup-tier{font:700 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--paper);padding:4px 8px}
.gg-roundup-score{font:700 15px var(--mono);color:var(--ink);white-space:nowrap}
.article .gg-roundup-card h3{font:700 21px/1.25 var(--serif);margin:0 0 6px}
.gg-roundup-card h3 a{color:var(--ink);text-decoration:none}
.gg-roundup-card h3 a:hover{text-decoration:underline;text-underline-offset:3px}
.gg-roundup-location,.gg-roundup-vitals{font:500 13px/1.45 var(--mono);color:var(--ink2);margin-bottom:4px}
.article .gg-roundup-tagline{font-size:16px;line-height:1.5;color:var(--ink2);margin:6px 0 0}
.gg-roundup-links{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:auto;padding-top:12px}
.gg-roundup-link{font:700 13px var(--mono);letter-spacing:.05em;text-transform:uppercase;color:var(--teal-ink);text-decoration:none}
.gg-roundup-link:hover{text-decoration:underline;text-underline-offset:3px}
.gg-roundup-link--kit{color:var(--ink)}
.gg-blog-cta{margin:56px 0 0}
@media (max-width:640px){
  .gg-roundup-grid{grid-template-columns:1fr}
  .gg-roundup-card{padding:16px}
}
"""


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

    Month matches the 'month' field; year matches the index's 'year' field
    (parsed from date_specific). Races with unknown year are kept — a known
    DIFFERENT year (e.g. a stale 2025 date) is excluded, so a "June 2026"
    roundup never lists an event we can only date to 2025. (Fixed 2026-07-22:
    the year argument was previously ignored entirely.)
    """
    month_name = MONTH_NAMES.get(month, "").lower()
    if not month_name:
        return []
    return [r for r in races
            if (r.get("month") or "").lower() == month_name
            and (r.get("year") is None or r.get("year") == year)]


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
    tier_name = TIER_NAMES.get(tier, "Grassroots")
    tier_color = TIER_COLORS.get(tier, "#5e6868")
    score = race.get("overall_score", 0)
    month = esc(race.get("month", ""))
    distance = race.get("distance_mi", "")
    elevation = race.get("elevation_ft", "")
    tagline = esc(race.get("tagline", ""))
    profile_url = f"{SITE_URL}/race/{slug}/"
    prep_kit_url = f"{SITE_URL}/race/{slug}/prep-kit/"

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
      <div class="gg-roundup-links">
        <a href="{profile_url}" class="gg-roundup-link">Race Profile &rarr;</a>
        <a href="{prep_kit_url}" class="gg-roundup-link gg-roundup-link--kit">Free Prep Kit &rarr;</a>
      </div>
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
    """Build the stats bar HTML (id=STATS_ID)."""
    parts = [f'<span class="gg-roundup-stat">{stats["count"]} Races</span>']
    parts.append(f'<span class="gg-roundup-stat">Avg Score: {stats["avg_score"]}/100</span>')
    for t, count in sorted(stats["tier_breakdown"].items()):
        tier_name = TIER_NAMES.get(t, "")
        parts.append(f'<span class="gg-roundup-stat">T{t} {esc(tier_name)}: {count}</span>')
    return f'<div class="gg-roundup-stats-bar" id="{STATS_ID}">' + "".join(parts) + "</div>"


def group_races_by_tier(sorted_races):
    """Split tier-sorted races into [(tier, [races])] runs, order kept."""
    groups = []
    for race in sorted_races:
        tier = race.get("tier", 4)
        if groups and groups[-1][0] == tier:
            groups[-1][1].append(race)
        else:
            groups.append((tier, [race]))
    return groups


def tier_section_id(tier):
    """The tier h2's id (the slug the shell gave it before ids were explicit)."""
    name = TIER_NAMES.get(tier, "")
    return "-".join(f"t{tier} {name}".lower().split())


NAME_SLOT = "Race"  # stands in for a race name when a template is checked


def _claim_ok(text, template=None):
    """Word cap on the full plain text; banned patterns on the template.

    template is the claim with each race name replaced by NAME_SLOT; it
    defaults to text (a claim with no race name in it).
    """
    return (len(text.split()) <= MAX_CLAIM_WORDS
            and not BANNED_CLAIM_RE.search(text if template is None else template))


def _braces(text):
    """Escape str.format braces in generator text placed into a template."""
    return str(text).replace("{", "{{").replace("}", "}}")


def build_in_short_claims(races, scope):
    """The roundup "In short": 2-3 data-derived claims, or None.

    `races` is the page's race list; `scope` is the page's span as plain text
    ("August 2026", "West region, March to May 2026", "T1 The Icons").
    Claims, in order (each skipped when its data is missing):
      1. scope: "{N} races rated, {scope}."
      2. top-rated: "{name} rates highest at {score}/100 (T{n} {tier name})."
      3. tier split: "By tier: 4 T1, 12 T2 and 6 T4." (2+ tiers only)
    Spec claim 4 (earliest date / biggest field) is never rendered:
    race-index.json has month-level dates only and no field sizes.
    Tiers are written "T{n}", never "Tier {n}": generate_blog_index reads the
    first "Tier N" on a page as its tier. Links point at the first tier h2, or
    on a single-tier page (no h2) at the race grid.
    """
    if not races:
        return None
    groups = group_races_by_tier(
        sorted(races, key=lambda r: (r.get("tier", 4), -r.get("overall_score", 0))))
    titled = len(groups) > 1

    def target(tier):
        if not titled:
            return f"#{RACES_ID}", "See the races", 0
        idx = next(i for i, (t, _) in enumerate(groups) if t == tier)
        label = f"T{tier} {TIER_NAMES.get(tier, '')}".strip()
        return f"#{tier_section_id(tier)}", f"See {label} \u00b7 \u00a7{idx + 1:02d}", idx

    claims = []

    def add(template, tier, *names):
        """template takes the race names as {} slots."""
        text = template.format(*names)
        if _claim_ok(text, template.format(*[NAME_SLOT] * len(names))):
            href, label, sec = target(tier)
            claims.append(Claim(esc(text), href, label, sec))

    first_tier = groups[0][0]
    if scope:
        add(f"{len(races)} races rated, {_braces(scope)}.", first_tier)

    scored = [r for r in races if r.get("overall_score") and r.get("name")]
    if scored:
        top_score = max(r["overall_score"] for r in scored)
        top = [r for g in groups for r in g[1]
               if r in scored and r["overall_score"] == top_score]
        lead = top[0]
        tier = lead.get("tier", 4)
        if len(top) == 1:
            tier_label = f"T{tier} {TIER_NAMES.get(tier, '')}".strip()
            add(f"{{}} rates highest at {top_score}/100 ({tier_label}).", tier, lead["name"])
        elif len(top) == 2:
            add(f"{{}} and {{}} share the highest rating, {top_score}/100.", tier,
                top[0]["name"], top[1]["name"])
        else:
            add(f"{len(top)} races share the highest rating, {top_score}/100.", tier)

    if titled:
        parts = [f"{len(g)} T{t}" for t, g in groups]
        split = ", ".join(parts[:-1]) + f" and {parts[-1]}"
        add(f"By tier: {split}.", first_tier)

    return claims if len(claims) >= MIN_CLAIMS else None


def build_roundup_body(intro, stats_bar, sorted_races):
    """The roundup body for the editorial shell (trusted, escaped HTML).

    Intro + stats bar, then the race cards. With races in 2+ tiers, each tier
    is its own gg-blog-section with an h2, so the shell's Contents lists the
    tiers; a single-tier page (tier roundups) keeps one untitled grid, so it
    has no h2 and the shell hides Contents on its own (MIN_CONTENTS_HEADINGS).
    """
    groups = group_races_by_tier(sorted_races)
    parts = [
        '<div class="gg-blog-section gg-roundup-intro">\n'
        f"  <p>{esc(intro)}</p>\n"
        f"  {stats_bar}\n"
        "</div>"
    ]
    titled = len(groups) > 1
    for tier, group in groups:
        heading = (f'  <h2 id="{tier_section_id(tier)}">'
                   f"T{tier} {esc(TIER_NAMES.get(tier, ''))}</h2>\n") if titled else ""
        grid_id = "" if titled else f' id="{RACES_ID}"'
        cards = "".join(build_race_card_html(r) for r in group)
        parts.append(
            f'<div class="gg-blog-section gg-roundup-group"{grid_id}>\n'
            f'{heading}  <div class="gg-roundup-grid">{cards}\n  </div>\n'
            "</div>"
        )
    parts.append(
        '<div class="gg-blog-cta">\n'
        f'  <a class="btn" href="{SITE_URL}/gravel-races/">Explore All Races '
        '<span class="chev" aria-hidden="true">&rsaquo;</span></a>\n'
        "</div>"
    )
    return "\n\n".join(parts)


def generate_roundup_html(title, subtitle, intro, races, slug, category_tag,
                          publish_date=None, scope=""):
    """Generate a complete roundup article HTML on the editorial shell.

    Args:
        title: Main heading (e.g. "March 2026 Gravel Calendar")
        subtitle: Secondary heading (e.g. "12 Races to Watch")
        intro: Paragraph of intro text
        races: List of race dicts from race-index.json
        slug: Output slug (e.g. "roundup-march-2026")
        category_tag: Display tag (e.g. "Monthly Calendar")
        publish_date: date object for datePublished (defaults to today)
        scope: plain-text span for the "In short" scope claim; "" skips it
    """
    stats = build_roundup_stats(races)
    stats_bar = build_stats_bar_html(stats)

    # Sort races by tier (ascending) then score (descending)
    sorted_races = sorted(races, key=lambda r: (r.get("tier", 4), -r.get("overall_score", 0)))

    pub_date = publish_date or date.today()
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

    meta = ArticleMeta(
        slug=slug,
        canonical_url=og_url,
        title=f"{title}: {subtitle} — Gravel God",
        description=f"{title}: {subtitle}. {stats['count']} races rated and ranked by Gravel God.",
        og_description=(f"{stats['count']} gravel races rated and ranked. "
                        f"Average score: {stats['avg_score']}/100."),
        headline=title,
        dek=subtitle,
        kicker=f"{category_tag} · {stats['count']} Races",
        date_published=pub_date,
        robots="index, follow" if slug in INDEXABLE_ROUNDUPS else "noindex, follow",
        json_ld=(jsonld,),
        # Roundups are scanned, not read through, and must never feed the
        # article funnel (article_* events), indexable or not.
        track_article_events=False,
        show_read_time=False,
        nav_active="races",
    )
    body = build_roundup_body(intro, stats_bar, sorted_races)
    return render_editorial_page(
        meta,
        body,
        in_short=build_in_short_claims(races, scope),
        ladder=False,  # roundups never had a plans/coaching block
        extra_css=ROUNDUP_CSS,
        extra_body_end=get_plan_intent_tracking_script(),
    )


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
        publish_date=pub_date, scope=f"{month_name} {year}",
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
        scope=(f"{region_display} region, {MONTH_NAMES[season_months[0]]} to "
               f"{MONTH_NAMES[season_months[-1]]} {year}"),
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
        f"15-criteria scoring system covering logistics, terrain, prestige, and more."
    )

    # Publish date: Jan 1 of the year, capped at today
    pub_date = date(year, 1, 1)
    if pub_date > date.today():
        pub_date = date.today()

    html_content = generate_roundup_html(
        title, subtitle, intro, filtered, slug, f"T{tier} {tier_name}",
        publish_date=pub_date, scope=f"T{tier} {tier_name}",
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{slug}.html"
    out_file.write_text(html_content)
    print(f"  OK    {slug} ({len(filtered)} races)")
    return slug


def expected_roundup_slugs(races, year):
    """Pure, zero-render enumeration of the roundup slugs generate_all would
    produce — shared with scripts/deploy_parity.py so the parity manifest and
    the generator can never disagree (a unit test enforces the match)."""
    slugs = set()
    for month in range(1, 13):
        if len(filter_by_month(races, year, month)) >= MIN_RACES_FOR_ROUNDUP:
            slugs.add(f"roundup-{MONTH_NAMES[month].lower()}-{year}")
    for region_key in REGIONS:
        for season in SEASONS:
            season_months = SEASONS[season]
            regional = filter_by_region(races, region_key)
            n = sum(1 for r in regional
                    if MONTH_NUMBERS.get((r.get("month") or "").lower(), 0) in season_months)
            if n >= MIN_RACES_FOR_ROUNDUP:
                slugs.add(f"roundup-{region_key}-{season}-{year}")
    for tier in (1, 2, 3, 4):
        if len(filter_by_tier(races, tier)) >= MIN_RACES_FOR_ROUNDUP:
            slugs.add(f"roundup-tier-{tier}-{year}")
    return slugs


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
