#!/usr/bin/env python3
"""Generate the tires index at /tire/.

/tire/ is already the breadcrumb parent of every /tire/{slug}/ review page
(generate_tire_pages.py BreadcrumbList). The index links every race tire guide
(/race/{slug}/tires/, grouped by tier) and every tire review page. /tires/ and
/race/tires/ 301 here (scripts/push_wordpress.py REDIRECT_BLOCK).

Output: wordpress/output/tire/index.html, beside the review pages.
generate_tire_pages.py writes it too, so --sync-tire-pages always ships it.

Usage:
    python wordpress/generate_tire_index.py
    python wordpress/generate_tire_index.py --output-dir /tmp/tire
"""

import argparse
import html as html_mod
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from brand_tokens import (  # noqa: E402
    SITE_BASE_URL,
    TIER_NAMES,
    get_favicon_head_snippet,
    get_font_face_css,
    get_ga4_head_snippet,
    get_tokens_css,
)
from cookie_consent import get_consent_banner_html  # noqa: E402
from season import season_year  # noqa: E402
from shared_footer import get_mega_footer_css, get_mega_footer_html  # noqa: E402
from shared_header import get_site_header_css, get_site_header_html, get_site_header_js  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "tire"
SEASON_YEAR = season_year()


def esc(text) -> str:
    return html_mod.escape(str(text)) if text is not None else ""


def race_guides(race_index: list) -> dict:
    """tier -> races with a tire guide (every published guide), by name."""
    by_tier = {}
    for race in race_index:
        if race.get("has_tire_guide") and race.get("slug"):
            by_tier.setdefault(race.get("tier") or 4, []).append(race)
    return {t: sorted(rs, key=lambda r: r.get("name", "").lower())
            for t, rs in sorted(by_tier.items())}


def build_method_section() -> str:
    """How picks, widths and pressures are made, read from the constants the
    generators use, so the published method can't drift from the code."""
    import generate_tire_guide as g
    lab = json.loads((PROJECT_ROOT / "data" / "tires" / "lab" / "brr-cx-gravel.json")
                     .read_text(encoding="utf-8"))
    brr = f'<a href="{esc(lab["source"])}" target="_blank" rel="noopener">bicyclerollingresistance.com</a>'
    silca = ('<a href="https://silca.cc/pages/pro-tire-pressure-calculator" '
             'target="_blank" rel="noopener">SILCA\'s calculator</a>')
    widths = g.WIDTH_TARGETS
    rows = [
        ("Rolling", "BRR watts at the pick width", "Always"),
        ("Puncture", f"{g.PUNCTURE_W_BASE:g} W per point below {g.PUNCTURE_REF}; "
                     f"{g.PUNCTURE_W_LONG:g} W at {g.COMFORT_DISTANCE_MI}+ miles; "
                     f"{g.PUNCTURE_W_SHARP:g} W with sharp rock", "Always"),
        ("Wet grip", f"{g.WET_W:g} W per point below {g.WET_REF}",
         f"Wet courses, or rain on {g.PRECIP_WET_THRESHOLD}%+ of race-month days"),
        ("Shoulder knobs", f"{g.KNOB_EDGE_W_ROUGH:g} W per mm below {g.KNOB_EDGE_REF:g}mm; "
                           f"{g.KNOB_EDGE_W_TECH:g} W on technical courses", "Rough courses"),
        ("Center knobs", f"{g.MUD_KNOB_W:g} W per mm below {g.MUD_KNOB_REF:g}mm; "
                         f"{g.MUD_KNOB_W_RISK:g} W if mud is possible", "Mud"),
        ("Width", f"{g.WIDTH_SHORT_W:g} W per mm below the course width", "Mixed and rough courses"),
        ("Untested size", f"{g.UNTESTED_WIDTH_W:g} W", "BRR didn't test that width"),
    ]
    table = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>"
                    for a, b, c in rows)
    return f'''<h2 id="method">How We Pick</h2>
  <div class="gg-tidx-method">
    <p><strong>Measured.</strong> Rolling resistance, tread puncture score, wet grip, knob height, weight and width come from {brr}'s gravel test table, saved {esc(lab["fetched"])}. {esc(lab["protocol"])} We don't test tires ourselves, and a tire BRR hasn't tested at 38mm or wider is never picked.</p>
    <p><strong>Our call.</strong> Tread type, mud clearance, what each course punishes (read from its course notes and weather), and the watt prices below.</p>
    <p><strong>Width.</strong> Smooth courses get {widths[1]}mm, mixed {widths[2]}mm, rough and technical {widths[3]}mm, or the organizer's minimum if that's wider.</p>
    <p><strong>Score.</strong> Each tire costs its rolling watts plus a watt price for what the course punishes. Lowest total wins. Picks 1 and 2 are the two cheapest; pick 3 is the cheapest with the other tread (file or knobs). Technical courses get no file treads; mud courses get only tires with real mud clearance.</p>
    <table class="gg-tidx-table">
      <thead><tr><th>Charge</th><th>Price</th><th>When</th></tr></thead>
      <tbody>{table}</tbody>
    </table>
    <p><strong>Pressure.</strong> Front and rear psi come from our model fitted to {silca}: rider weight plus {g.BIKE_AND_KIT_LB} lb of bike and kit, tire width, and SILCA's gravel category from the course's tech rating. It lands within 0.5 psi of SILCA for 130 to 230 lb riders on 38 to 53mm tires.</p>
    <p><strong>Podiums.</strong> Where a bike check, race report or brand race page says what a podium rider ran, the race's tire guide lists it next to our picks with the source linked. Brand pages are marked as brand. We leave widths and pressures blank unless the source states them.</p>
    <p><strong>Setup.</strong> Sealant volumes are Stan's; insert weights and fits are Vittoria's and Tannus's. Whether a course needs inserts is our call from its course notes.</p>
    <p><strong>What it misses.</strong> BRR's free table has no sidewall strength, so a tough casing can rank below a lighter one on a sharp course.</p>
  </div>'''


def build_tire_index_page(race_index: list, tires: list) -> str:
    guides = race_guides(race_index)
    guide_count = sum(len(rs) for rs in guides.values())
    tires = sorted(tires, key=lambda t: (t.get("brand", "").lower(), t.get("name", "").lower()))

    tier_sections = []
    for tier, races in guides.items():
        items = "\n        ".join(
            f'<li><a href="/race/{esc(r["slug"])}/tires/">{esc(r.get("name", r["slug"]))}</a></li>'
            for r in races)
        tier_sections.append(
            f'<section class="gg-tidx-group" id="tier-{tier}">'
            f'<h3>Tier {tier}: {esc(TIER_NAMES.get(tier, ""))} '
            f'<span class="gg-tidx-count">{len(races)}</span></h3>\n'
            f'      <ul class="gg-tidx-list">\n        {items}\n      </ul></section>')

    tire_items = "\n      ".join(
        f'<li><a href="/tire/{esc(t["id"])}/">{esc(t.get("name", t["id"]))}</a>'
        f'<span class="gg-tidx-meta">{esc((t.get("tread_type") or "").title())}</span></li>'
        for t in tires)

    canonical = f"{SITE_BASE_URL}/tire/"
    title = f"Gravel Tire Guides {SEASON_YEAR}: {guide_count} Races, {len(tires)} Tires | Gravel God"
    description = (f"Tire picks and pressures for {guide_count} gravel races, plus reviews "
                   f"of {len(tires)} gravel tires.")
    jsonld = json.dumps([
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Tires", "item": canonical},
        ]},
    ], ensure_ascii=False).replace("</", "<\\/")
    tiers_html = "\n\n    ".join(tier_sections)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{canonical}">
  {get_favicon_head_snippet()}
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{canonical}">
  <script type="application/ld+json">{jsonld}</script>
  <style>
{get_font_face_css()}
{get_tokens_css()}
body {{ margin: 0; background: var(--gg-color-warm-paper); }}
*, *::before, *::after {{ border-radius: 0 !important; box-shadow: none !important; }}
.gg-tidx-page {{ max-width: 1100px; margin: 0 auto; padding: 0 16px; font-family: var(--gg-font-data); color: var(--gg-color-dark-brown); }}
{get_site_header_css()}
.gg-tidx-breadcrumb {{ font-size: 11px; padding: 12px 0; letter-spacing: 0.5px; color: var(--gg-color-secondary-brown); }}
.gg-tidx-breadcrumb a {{ color: var(--gg-color-secondary-brown); text-decoration: none; }}
.gg-tidx-page h1 {{ font-size: 32px; margin: 16px 0 24px; }}
.gg-tidx-page h2 {{ font-size: 13px; letter-spacing: 2px; text-transform: uppercase; border-bottom: 3px solid var(--gg-color-dark-brown); padding-bottom: 6px; margin-top: 32px; }}
.gg-tidx-group h3 {{ font-size: 15px; margin: 24px 0 8px; }}
.gg-tidx-count, .gg-tidx-meta {{ font-size: 11px; font-weight: 400; color: var(--gg-color-secondary-brown); }}
.gg-tidx-list {{ list-style: none; margin: 0; padding: 0; columns: 3 240px; column-gap: 24px; }}
.gg-tidx-list li {{ break-inside: avoid; padding: 6px 0; border-bottom: 2px solid var(--gg-color-tan); display: flex; justify-content: space-between; gap: 8px; }}
.gg-tidx-list a {{ color: var(--gg-color-dark-brown); text-decoration: none; font-family: var(--gg-font-editorial); font-weight: 700; }}
.gg-tidx-list a:hover {{ color: var(--gg-color-teal); }}
.gg-tidx-page h2 {{ scroll-margin-top: calc(var(--gg-header-height, 64px) + 12px); }}
.gg-tidx-method {{ max-width: 760px; }}
.gg-tidx-method p {{ font-size: 14px; line-height: 1.6; margin: 0 0 14px; }}
.gg-tidx-method a {{ color: var(--gg-color-teal); }}
.gg-tidx-table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin: 4px 0 18px; }}
.gg-tidx-table th, .gg-tidx-table td {{ text-align: left; vertical-align: top; padding: 6px 8px; border-bottom: 2px solid var(--gg-color-tan); }}
.gg-tidx-table th {{ font-size: 11px; letter-spacing: 1px; text-transform: uppercase; border-bottom: 3px solid var(--gg-color-dark-brown); }}{get_mega_footer_css()}
  </style>
  {get_ga4_head_snippet()}
</head>
<body>
<div class="gg-tidx-page">
  {get_site_header_html(active="races")}
  <div class="gg-tidx-breadcrumb"><a href="/">Home</a> &rsaquo; <span>Tires</span></div>
  <h1>Gravel Tire Guides</h1>

  <h2 id="races">Tires by Race <span class="gg-tidx-count">{guide_count}</span></h2>
    {tiers_html}

  <h2 id="reviews">Tire Reviews <span class="gg-tidx-count">{len(tires)}</span></h2>
    <ul class="gg-tidx-list">
      {tire_items}
    </ul>

  {build_method_section()}
</div>
{get_mega_footer_html()}
{get_site_header_js()}
{get_consent_banner_html()}
</body>
</html>'''


def write_tire_index(output_dir: Path, tires: list = None) -> Path:
    """Write {output_dir}/index.html. generate_tire_pages.py calls this, so the
    /tire/ staging tree always carries its index."""
    race_index = json.loads((PROJECT_ROOT / "web" / "race-index.json").read_text(encoding="utf-8"))
    if tires is None:
        from generate_tire_guide import load_tire_database
        tires = load_tire_database()
    out = Path(output_dir) / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_tire_index_page(race_index, tires), encoding="utf-8")
    print(f"Generated tire/index.html ({sum(len(r) for r in race_guides(race_index).values())} "
          f"race guides, {len(tires)} tires)")
    return out


def main():
    parser = argparse.ArgumentParser(description="Generate the /tire/ index page")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: wordpress/output/tire/)")
    args = parser.parse_args()
    write_tire_index(Path(args.output_dir) if args.output_dir else OUTPUT_DIR)


if __name__ == "__main__":
    main()
