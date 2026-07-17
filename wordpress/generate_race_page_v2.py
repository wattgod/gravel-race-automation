#!/usr/bin/env python3
"""
Race detail page generator — "real map card" redesign (pilot).

Sibling module to generate_neo_brutalist.py, NOT a replacement or rewrite of it.
Per docs/specs/race-page-redesign/IMPLEMENTATION_PLAN.md §4: the DATA layer
(normalize_race_data, scoring, JSON-LD, GA4/font/header helpers) and every
content section outside this pilot's visual scope (history, verdict, training,
plan-ladder, prep-strip, similar-races, FAQ, citations, footer, etc.) are
imported UNCHANGED from generate_neo_brutalist.py. generate_neo_brutalist.py
itself is not modified — running this module has zero effect on the other 734
live race pages, which are still produced by generate_neo_brutalist.py --all.

The one genuinely new piece is the real route-map treatment: a per-race SVG
line rendered from cached RideWithGPS geometry (data/route-geometry/{slug}.json,
built by scripts/fetch_route_geometry.py — never fetched live at generate time),
injected into the existing Course Overview section ahead of its stat cards and
the RWGPS iframe (which is kept, unchanged, as the interactive/authoritative
map for races that have one). Races without cached geometry get an explicit
"no verified route on file" placeholder — never a fabricated line.

Per §1's corrected finding, no new brand-token colors are introduced — every
color reference here is an existing --gg-color-* custom property.

Usage:
    python3 generate_race_page_v2.py steamboat-gravel --output-dir ../wordpress/output_v2_pilot
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_neo_brutalist as v1  # noqa: E402

# ── Re-exported DATA layer + unrelated sections (imported, not duplicated) ──
normalize_race_data = v1.normalize_race_data
esc = v1.esc
_safe_json_for_script = v1._safe_json_for_script
build_sports_event_jsonld = v1.build_sports_event_jsonld
build_faq_jsonld = v1.build_faq_jsonld
build_breadcrumb_jsonld = v1.build_breadcrumb_jsonld
build_webpage_jsonld = v1.build_webpage_jsonld
build_nav_header = v1.build_nav_header
build_hero = v1.build_hero
build_course_overview = v1.build_course_overview
build_history = v1.build_history
build_pullquote = v1.build_pullquote
build_course_route = v1.build_course_route
build_from_the_field = v1.build_from_the_field
build_ratings = v1.build_ratings
build_verdict = v1.build_verdict
build_racer_reviews = v1.build_racer_reviews
build_email_capture = v1.build_email_capture
build_visible_faq = v1.build_visible_faq
build_news_section = v1.build_news_section
build_training = v1.build_training
build_plan_ladder = v1.build_plan_ladder
build_train_for_race = v1.build_train_for_race
build_prep_strip = v1.build_prep_strip
build_logistics_section = v1.build_logistics_section
build_tire_picks = v1.build_tire_picks
build_tire_guide_callout = v1.build_tire_guide_callout
build_coaching_teaser = v1.build_coaching_teaser
build_date_reminder = v1.build_date_reminder
build_similar_races = v1.build_similar_races
build_citations_section = v1.build_citations_section
build_footer = v1.build_footer
build_sticky_cta = v1.build_sticky_cta
build_toc = v1.build_toc
build_inline_js = v1.build_inline_js
get_ga4_head_snippet = v1.get_ga4_head_snippet
get_font_face_css = v1.get_font_face_css
get_preload_hints = v1.get_preload_hints
get_page_css = v1.get_page_css
build_seo_title = v1.build_seo_title
build_seo_description = v1.build_seo_description
find_data_file = v1.find_data_file
load_race_data = v1.load_race_data
REMOVED_FABRICATED_SLUGS = v1.REMOVED_FABRICATED_SLUGS
SITE_BASE_URL = v1.SITE_BASE_URL

GEOMETRY_DIR = Path(__file__).resolve().parent.parent / "data" / "route-geometry"


# ── Net-new: real route-map component ───────────────────────────

def load_route_geometry(slug: str) -> Optional[dict]:
    """Read cached RWGPS geometry for a race, if present. No live API calls."""
    path = GEOMETRY_DIR / f"{slug}.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def build_route_map_v2(rd: dict) -> str:
    """Build the real-map card/hero treatment: cached RWGPS route line SVG,
    or an explicit no-verified-route placeholder. Exactly one, never both,
    never a fabricated line. Uses only existing brand tokens (no new colors —
    see IMPLEMENTATION_PLAN.md §1/§5)."""
    geometry = load_route_geometry(rd["slug"])

    if geometry and geometry.get("path_d") and geometry.get("viewbox"):
        vb_parts = geometry["viewbox"].split()
        aspect = f"{vb_parts[2]}/{vb_parts[3]}" if len(vb_parts) == 4 else "4/3"
        path_d = esc(geometry["path_d"])
        viewbox = esc(geometry["viewbox"])
        route_name = esc(geometry.get("route_name") or rd["name"])
        source_url = esc(geometry.get("source_url", ""))
        return f'''<figure class="gg-route-map" style="aspect-ratio:{aspect}">
        <svg viewBox="{viewbox}" class="gg-route-map__svg" role="img" aria-label="Real course route for {esc(rd['name'])}, sourced from RideWithGPS" preserveAspectRatio="xMidYMid meet">
          <path d="{path_d}" class="gg-route-map__glow"/>
          <path d="{path_d}" class="gg-route-map__line"/>
        </svg>
        <figcaption class="gg-route-map__caption">Real course route — <a href="{source_url}" target="_blank" rel="noopener nofollow">{route_name} via RideWithGPS</a></figcaption>
      </figure>'''

    return f'''<div class="gg-route-map gg-route-map--empty">
        <svg class="gg-route-map__pin" width="28" height="28" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2C7.6 2 4 5.6 4 10c0 6 8 12 8 12s8-6 8-12c0-4.4-3.6-8-8-8zm0 11a3 3 0 110-6 3 3 0 010 6z" fill="var(--gg-color-warm-brown)"/></svg>
        <div class="gg-route-map__empty-label">NO VERIFIED ROUTE ON FILE</div>
      </div>'''


def build_course_overview_v2(rd: dict, race_index: list = None) -> str:
    """Course Overview section with the real-map treatment injected ahead of
    the existing stat cards / RWGPS iframe / difficulty gauge / nearby races —
    all of which are reused unchanged from build_course_overview()."""
    base_html = build_course_overview(rd, race_index)
    route_map_html = build_route_map_v2(rd)
    marker = '<div class="gg-section-body">'
    if marker in base_html:
        return base_html.replace(
            marker, f'{marker}\n      {route_map_html}', 1
        )
    return base_html  # defensive fallback — never crash the page on a marker miss


# ── CSS: existing tokens/layout + the new route-map component only ─────────

ROUTE_MAP_CSS = '''<style>
.gg-neo-brutalist-page .gg-route-map { position: relative; background: var(--gg-color-near-black); margin: var(--gg-spacing-md) 0; overflow: hidden; }
.gg-neo-brutalist-page .gg-route-map__svg { width: 100%; height: 100%; display: block; }
.gg-neo-brutalist-page .gg-route-map__glow { fill: none; stroke: var(--gg-color-light-teal); stroke-width: 7; stroke-linecap: round; stroke-linejoin: round; opacity: 0.2; }
.gg-neo-brutalist-page .gg-route-map__line { fill: none; stroke: var(--gg-color-teal); stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
.gg-neo-brutalist-page .gg-route-map__caption { font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; color: var(--gg-color-secondary-brown); padding: var(--gg-spacing-sm) var(--gg-spacing-md); background: var(--gg-color-warm-paper); border-top: var(--gg-border-standard); margin: 0; }
.gg-neo-brutalist-page .gg-route-map__caption a { color: var(--gg-color-teal); text-decoration: underline; text-underline-offset: 2px; }
.gg-neo-brutalist-page .gg-route-map--empty { aspect-ratio: 4/3; background: var(--gg-color-sand); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--gg-spacing-sm); border: var(--gg-border-standard); }
.gg-neo-brutalist-page .gg-route-map__empty-label { font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; color: var(--gg-color-warm-brown); }
</style>'''


def get_page_css_v2() -> str:
    """Existing page CSS (unchanged tokens/layout) plus the new route-map
    component rules. No new color tokens (IMPLEMENTATION_PLAN.md §1/§5)."""
    return get_page_css() + "\n" + ROUTE_MAP_CSS


def _extract_css_content_v2() -> str:
    raw = get_page_css_v2()
    return raw.replace('<style>', '').replace('</style>', '\n').strip()


def write_shared_assets_v2(output_dir: Path) -> dict:
    """Same as generate_neo_brutalist.write_shared_assets() but hashes the v2
    CSS (which differs, so it gets a new filename — never overwrites the v1
    hashed asset, per repo pitfall #9). JS is unchanged (no new client-side
    behavior needed for a static SVG), so it reuses the v1 JS content/hash."""
    import hashlib
    import shutil as _shutil

    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    fonts_dir = assets_dir / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    for font_file in v1.FONT_FILES:
        src = v1.BRAND_FONTS_DIR / font_file
        dst = fonts_dir / font_file
        if src.exists():
            _shutil.copy2(src, dst)

    css_content = _extract_css_content_v2()
    js_content = v1._extract_js_content()

    css_hash = hashlib.md5(css_content.encode()).hexdigest()[:8]
    js_hash = hashlib.md5(js_content.encode()).hexdigest()[:8]

    css_file = f"gg-styles.{css_hash}.css"
    js_file = f"gg-scripts.{js_hash}.js"

    (assets_dir / css_file).write_text(css_content, encoding="utf-8")
    (assets_dir / js_file).write_text(js_content, encoding="utf-8")

    return {
        "css_tag": f'<link rel="stylesheet" href="/race/assets/{css_file}">',
        "js_tag": f'<script src="/race/assets/{js_file}"></script>',
    }


# ── Page assembly (same contract/section order as generate_page) ───────────

def generate_page_v2(rd: dict, race_index: list = None, external_assets: dict = None) -> str:
    race_index = race_index or []
    canonical_url = f"{SITE_BASE_URL}/race/{rd['slug']}/"

    jsonld_parts = []
    sports_event = build_sports_event_jsonld(rd)
    if sports_event is not None:
        jsonld_parts.append(_safe_json_for_script(sports_event, ensure_ascii=False, separators=(',', ':')))
    faq = build_faq_jsonld(rd)
    if faq:
        jsonld_parts.append(_safe_json_for_script(faq, ensure_ascii=False, separators=(',', ':')))
    if race_index:
        breadcrumb = build_breadcrumb_jsonld(rd, race_index)
        jsonld_parts.append(_safe_json_for_script(breadcrumb, ensure_ascii=False, separators=(',', ':')))
    webpage = build_webpage_jsonld(rd)
    jsonld_parts.append(_safe_json_for_script(webpage, ensure_ascii=False, separators=(',', ':')))
    jsonld_html = '\n'.join(f'<script type="application/ld+json">{j}</script>' for j in jsonld_parts)

    nav_header = build_nav_header(rd, race_index)
    hero = build_hero(rd)
    course_overview = build_course_overview_v2(rd, race_index)
    history = build_history(rd)
    pullquote = build_pullquote(rd)
    course_route = build_course_route(rd)
    from_the_field = build_from_the_field(rd)
    ratings = build_ratings(rd)
    verdict = build_verdict(rd, race_index)
    racer_reviews = build_racer_reviews(rd)
    email_capture = build_email_capture(rd)
    visible_faq = build_visible_faq(rd)
    news = build_news_section(rd)
    training = build_training(rd)
    plan_ladder = build_plan_ladder(rd)
    train_for_race = build_train_for_race(rd)
    prep_strip = build_prep_strip(rd) if train_for_race else ''
    logistics_sec = build_logistics_section(rd)
    tire_picks = build_tire_picks(rd)
    tire_callout = build_tire_guide_callout(rd)
    coaching_teaser = build_coaching_teaser(rd)
    date_reminder = build_date_reminder(rd)
    similar = build_similar_races(rd, race_index)
    citations_sec = build_citations_section(rd)
    footer = build_footer(rd)
    sticky_cta = build_sticky_cta(rd['name'], rd['slug'])

    active = {'course', 'ratings', 'training'}
    if history:
        active.add('history')
    if course_route:
        active.add('route')
    if from_the_field:
        active.add('from-the-field')
    if verdict:
        active.add('verdict')
    if logistics_sec:
        active.add('logistics')
    if tire_picks:
        active.add('tires')
    if train_for_race:
        active.add('train-for-race')
    if citations_sec:
        active.add('citations')
    toc = build_toc(active)

    if external_assets:
        fonts_inline = get_font_face_css("/race/assets/fonts")
        critical_css = f'<style>{fonts_inline}</style>'
        css = critical_css + '\n  ' + external_assets['css_tag']
        inline_js = external_assets['js_tag']
    else:
        css = get_page_css_v2()
        inline_js = build_inline_js()

    content_sections = []
    for section in [course_overview, history, pullquote,
                    course_route, tire_callout, from_the_field, ratings, verdict,
                    racer_reviews, email_capture, date_reminder, news, training,
                    plan_ladder, coaching_teaser, train_for_race,
                    logistics_sec, tire_picks, similar, visible_faq,
                    citations_sec]:
        if section:
            content_sections.append(section)
    content = '\n\n  '.join(content_sections)

    seo_title = build_seo_title(rd)
    seo_description = build_seo_description(rd)
    og_image_url = f"{SITE_BASE_URL}/og/{rd['slug']}.jpg"
    og_tags = f'''<meta property="og:title" content="{esc(seo_title)}">
  <meta property="og:description" content="{esc(seo_description)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{esc(og_image_url)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(seo_title)}">
  <meta name="twitter:description" content="{esc(seo_description)}">
  <meta name="twitter:image" content="{esc(og_image_url)}">'''

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(seo_title)}</title>
  <meta name="description" content="{esc(seo_description)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="icon" type="image/svg+xml" href="https://gravelgodcycling.com/gg-logo.svg">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  <link rel="dns-prefetch" href="https://ridewithgps.com">
  <link rel="dns-prefetch" href="https://api.rss2json.com">
  <link rel="dns-prefetch" href="https://i.ytimg.com">
  {preload}
  {og_tags}
  {jsonld_html}
  {css}
  {get_ga4_head_snippet()}
</head>
<body>

<a href="#course" class="gg-skip-link">Skip to content</a>
<div class="gg-neo-brutalist-page">
  {nav_header}

  {hero}

  {prep_strip}

  {toc}

  {content}

  {footer}
</div>

{sticky_cta}
<button class="gg-back-to-top" id="gg-back-to-top" aria-label="Back to top">&uarr;</button>
{inline_js}

{v1.get_consent_banner_html()}
</body>
</html>'''


# ── CLI (single-slug only — this pilot module never generates --all) ───────

def main():
    parser = argparse.ArgumentParser(
        description="Generate the race-page-redesign pilot page (v2 template). Single slug only."
    )
    parser.add_argument('slug', help='Race slug (e.g., steamboat-gravel)')
    parser.add_argument('--data-dir', help='Primary data directory (default: auto-detect)')
    parser.add_argument('--output-dir', required=True,
                         help='Output directory — MUST be isolated from wordpress/output/ '
                              '(that dir is generate_neo_brutalist.py --all\'s territory)')
    args = parser.parse_args()

    if Path(args.output_dir).resolve() == (Path(__file__).resolve().parent / "output").resolve():
        print("ERROR: refusing to write into wordpress/output/ — use an isolated pilot dir.", file=sys.stderr)
        sys.exit(1)

    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    data_dirs = []
    if args.data_dir:
        data_dirs.append(Path(args.data_dir))
    data_dirs.append(project_root / 'race-data')
    data_dirs.append(project_root / 'data')

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    index_path = project_root / 'web' / 'race-index.json'
    race_index = []
    if index_path.exists():
        with open(index_path, encoding='utf-8') as f:
            race_index = json.load(f)

    if args.slug in REMOVED_FABRICATED_SLUGS:
        print(f"ERROR: '{args.slug}' is a removed fabricated race slug.", file=sys.stderr)
        sys.exit(1)

    filepath = find_data_file(args.slug, data_dirs)
    if not filepath:
        print(f"ERROR: No data file found for slug '{args.slug}'", file=sys.stderr)
        sys.exit(1)

    assets = write_shared_assets_v2(output_dir)
    rd = load_race_data(filepath)
    page_html = generate_page_v2(rd, race_index, external_assets=assets)
    out = output_dir / f"{args.slug}.html"
    out.write_text(page_html, encoding='utf-8')
    print(f"Generated {out} ({len(page_html):,} bytes)")


if __name__ == '__main__':
    main()
