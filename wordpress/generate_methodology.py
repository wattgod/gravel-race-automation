#!/usr/bin/env python3
"""
Generate the Gravel God Methodology page in neo-brutalist style.

Explains the scoring system, tier definitions, 15 dimensions, prestige
overrides, and FAQ. Reuses CSS/style patterns from generate_neo_brutalist.py.

Usage:
    python generate_methodology.py
    python generate_methodology.py --output-dir ./output
"""

import argparse
import html
import json
from pathlib import Path

# Import shared constants from the race page generator
from generate_neo_brutalist import (
    SITE_BASE_URL,
    SUBSTACK_URL,
    get_page_css,
    build_inline_js,
    write_shared_assets,
)
from brand_tokens import get_ga4_head_snippet, get_preload_hints
from shared_header import get_site_header_html
from cookie_consent import get_consent_banner_html

OUTPUT_DIR = Path(__file__).parent / "output"


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


# ── Page sections ─────────────────────────────────────────────


def build_nav() -> str:
    return get_site_header_html(active="races") + f'''
  <div class="gg-breadcrumb">
    <a href="{SITE_BASE_URL}/">Home</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <a href="{SITE_BASE_URL}/gravel-races/">Gravel Races</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <span class="gg-breadcrumb-current">Methodology</span>
  </div>'''


def build_hero() -> str:
    return '''<div class="gg-hero">
    <div class="gg-hero-tier" style="background:var(--gg-color-teal)">METHODOLOGY</div>
    <h1 data-text="How We Rate Gravel Races">How We Rate Gravel Races</h1>
    <p class="gg-hero-tagline">Every race in our database is scored across 15 dimensions by human editors. No algorithms. No sponsors. No pay-to-play. Here&#39;s exactly how it works.</p>
  </div>'''


def build_tier_system() -> str:
    return f'''<div class="gg-section" id="tier-system">
    <div class="gg-section-header">
      <span class="gg-section-kicker">01</span>
      <h2 class="gg-section-title">The Tier System</h2>
    </div>
    <div class="gg-section-body">
      <p style="margin-bottom:20px">Every race is assigned one of four tiers based on its overall score. Tiers determine how a race is grouped and displayed across the site.</p>

      <table class="gg-method-table">
        <thead>
          <tr><th>Tier</th><th>Name</th><th>Score</th><th>Description</th><th>Example</th></tr>
        </thead>
        <tbody>
          <tr>
            <td><span style="display:inline-block;padding:2px 10px;background:#000;color:#fff;font-weight:700;font-size:11px;letter-spacing:1.5px;border:2px solid #000">TIER 1</span></td>
            <td style="font-weight:700">The Icons</td>
            <td>&ge; 80</td>
            <td>The definitive gravel events. World-class fields, iconic courses, bucket-list status.</td>
            <td><a href="{SITE_BASE_URL}/race/unbound-200/" style="color:var(--gg-color-teal);font-weight:700">Unbound 200</a></td>
          </tr>
          <tr>
            <td><span style="display:inline-block;padding:2px 10px;background:#fff;color:#000;font-weight:700;font-size:11px;letter-spacing:1.5px;border:2px solid #000">TIER 2</span></td>
            <td style="font-weight:700">Elite</td>
            <td>&ge; 60</td>
            <td>Established races with strong reputations and competitive fields. The next tier of must-do events.</td>
            <td><a href="{SITE_BASE_URL}/race/barry-roubaix/" style="color:var(--gg-color-teal);font-weight:700">Barry-Roubaix</a></td>
          </tr>
          <tr>
            <td><span style="display:inline-block;padding:2px 10px;background:#fff;color:var(--gg-color-secondary-brown);font-weight:700;font-size:11px;letter-spacing:1.5px;border:2px solid #666">TIER 3</span></td>
            <td style="font-weight:700">Solid</td>
            <td>&ge; 45</td>
            <td>Regional favorites and emerging races. Strong local scenes, genuine gravel character.</td>
            <td><a href="{SITE_BASE_URL}/race/rooted-vermont/" style="color:var(--gg-color-teal);font-weight:700">Rooted Vermont</a></td>
          </tr>
          <tr>
            <td><span style="display:inline-block;padding:2px 10px;background:#fff;color:#5e6868;font-weight:700;font-size:11px;letter-spacing:1.5px;border:2px solid #5e6868">TIER 4</span></td>
            <td style="font-weight:700">Grassroots</td>
            <td>&lt; 45</td>
            <td>Up-and-coming races and local grinders. Small fields, raw vibes, grassroots gravel.</td>
            <td><a href="{SITE_BASE_URL}/race/114-gravel-race/" style="color:var(--gg-color-teal);font-weight:700">114 Gravel Race</a></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>'''


def build_dimensions() -> str:
    course_rows = '''
          <tr><td style="font-weight:700">Length</td><td>&lt;40 mi</td><td>40-60 mi</td><td>60-100 mi</td><td>100-150 mi</td><td>150+ mi</td></tr>
          <tr><td style="font-weight:700">Technicality</td><td>Smooth gravel</td><td>Some rough</td><td>Mixed terrain</td><td>Technical descents</td><td>Singletrack / extreme</td></tr>
          <tr><td style="font-weight:700">Elevation</td><td>&lt;2,000 ft</td><td>2-4K ft</td><td>4-6K ft</td><td>6-10K ft</td><td>10,000+ ft</td></tr>
          <tr><td style="font-weight:700">Climate</td><td>Mild / ideal</td><td>Slightly hard</td><td>Moderate</td><td>Significant</td><td>Extreme</td></tr>
          <tr><td style="font-weight:700">Altitude</td><td>Sea level</td><td>&lt;3,000 ft</td><td>3-6K ft</td><td>6-9K ft</td><td>9,000+ ft</td></tr>
          <tr><td style="font-weight:700">Logistics</td><td>Easy access</td><td>Minor travel</td><td>Moderate planning</td><td>Remote</td><td>Extreme remoteness</td></tr>
          <tr><td style="font-weight:700">Adventure</td><td>Standard race</td><td>Some character</td><td>Memorable</td><td>Epic scenery</td><td>Bucket list</td></tr>'''

    editorial_rows = '''
          <tr><td style="font-weight:700">Prestige</td><td>Unknown</td><td>Local recognition</td><td>Regional</td><td>National</td><td>World-class / iconic</td></tr>
          <tr><td style="font-weight:700">Race Quality</td><td>Basic</td><td>Adequate</td><td>Good</td><td>Professional</td><td>Elite / flawless</td></tr>
          <tr><td style="font-weight:700">Experience</td><td>Forgettable</td><td>Pleasant</td><td>Enjoyable</td><td>Memorable</td><td>Life-changing</td></tr>
          <tr><td style="font-weight:700">Community</td><td>Sparse</td><td>Small group</td><td>Good vibe</td><td>Strong community</td><td>Legendary culture</td></tr>
          <tr><td style="font-weight:700">Field Depth</td><td>Casual only</td><td>Some competition</td><td>Competitive</td><td>Strong pros</td><td>Elite field</td></tr>
          <tr><td style="font-weight:700">Value</td><td>Overpriced</td><td>Below average</td><td>Fair</td><td>Good value</td><td>Exceptional</td></tr>
          <tr><td style="font-weight:700">Expenses</td><td>Extreme ($2K+)</td><td>High ($1-2K)</td><td>Moderate ($500-1K)</td><td>Reasonable ($300-500)</td><td>Budget (&lt;$300)</td></tr>'''

    return f'''<div class="gg-section" id="dimensions">
    <div class="gg-section-header gg-section-header--dark">
      <span class="gg-section-kicker">02</span>
      <h2 class="gg-section-title">14 Base Dimensions + Cultural Impact</h2>
    </div>
    <div class="gg-section-body">
      <p style="margin-bottom:16px">Each race is evaluated across 14 base dimensions split into two categories, plus a Cultural Impact bonus. Every dimension is scored 1&ndash;5 by our editors with a written explanation.</p>

      <h3 style="font-size:13px;text-transform:uppercase;letter-spacing:2px;margin:24px 0 12px;color:var(--gg-color-primary-brown)">Course Profile (7 dimensions)</h3>
      <p style="margin-bottom:12px;font-size:12px;color:var(--gg-color-secondary-brown)">Physical and logistical demands of the race.</p>
      <div style="overflow-x:auto">
      <table class="gg-method-table gg-method-table--compact">
        <thead>
          <tr><th>Dimension</th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th></tr>
        </thead>
        <tbody>{course_rows}
        </tbody>
      </table>
      </div>

      <h3 style="font-size:13px;text-transform:uppercase;letter-spacing:2px;margin:32px 0 12px;color:var(--gg-color-primary-brown)">Editorial (7 dimensions)</h3>
      <p style="margin-bottom:12px;font-size:12px;color:var(--gg-color-secondary-brown)">Race quality and value proposition.</p>
      <div style="overflow-x:auto">
      <table class="gg-method-table gg-method-table--compact">
        <thead>
          <tr><th>Dimension</th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th></tr>
        </thead>
        <tbody>{editorial_rows}
        </tbody>
      </table>
      </div>

      <h3 style="font-size:13px;text-transform:uppercase;letter-spacing:2px;margin:32px 0 12px;color:var(--gg-color-primary-brown)">Cultural Impact (bonus dimension)</h3>
      <p style="margin-bottom:12px;font-size:12px;color:var(--gg-color-secondary-brown)">A bonus that captures attendance, media coverage, and cultural significance. Defaults to 0 for most races.</p>
      <div style="overflow-x:auto">
      <table class="gg-method-table gg-method-table--compact">
        <thead>
          <tr><th>Score</th><th>Level</th><th>Criteria</th></tr>
        </thead>
        <tbody>
          <tr><td style="font-weight:700">5</td><td>Global Icon</td><td>Defines gravel cycling. 2,000+ riders, massive media, cultural landmark.</td></tr>
          <tr><td style="font-weight:700">4</td><td>Major International</td><td>1,000+ riders, significant international draw, strong media presence.</td></tr>
          <tr><td style="font-weight:700">3</td><td>Notable National</td><td>Nationally recognized, growing media, strong regional significance.</td></tr>
          <tr><td style="font-weight:700">2</td><td>Established Regional</td><td>Quality event with dedicated following, limited broader footprint.</td></tr>
          <tr><td style="font-weight:700">1</td><td>Emerging</td><td>Building reputation, minimal media beyond local cycling communities.</td></tr>
          <tr><td style="font-weight:700">0</td><td>Default</td><td>No bonus. Most T3/T4 races.</td></tr>
        </tbody>
      </table>
      </div>
    </div>
  </div>'''


def build_formula() -> str:
    return '''<div class="gg-section" id="formula">
    <div class="gg-section-header">
      <span class="gg-section-kicker">03</span>
      <h2 class="gg-section-title">Scoring Formula</h2>
    </div>
    <div class="gg-section-body">
      <p style="margin-bottom:16px">The overall score is a simple, transparent calculation:</p>

      <div style="background:var(--gg-color-near-black);color:var(--gg-color-white);padding:24px 32px;border:var(--gg-border-standard);margin-bottom:20px;text-align:center">
        <code style="font-size:16px;letter-spacing:1px;font-family:var(--gg-font-data);color:var(--gg-color-light-teal)">overall_score = round( (sum of 14 base scores + cultural_impact) &divide; 70 &times; 100 )</code>
      </div>

      <p style="margin-bottom:12px;font-size:13px">The maximum possible base score is 70 (14 dimensions &times; 5 max each). The Cultural Impact bonus (0&ndash;5) adds to the numerator without increasing the denominator, allowing globally significant races to stretch above the base ceiling.</p>

      <ul style="font-size:13px;padding-left:20px;line-height:1.8">
        <li>A race scoring 3/5 across all 14 dimensions with no CI bonus gets a <strong>60</strong></li>
        <li>A race scoring 4/5 across all 14 dimensions with no CI bonus gets an <strong>80</strong></li>
        <li>A race scoring 4/5 across all 14 dimensions with CI=5 gets an <strong>87</strong></li>
        <li>The highest-scored race (Unbound 200) scores <strong>93</strong></li>
      </ul>
    </div>
  </div>'''


def build_prestige_override() -> str:
    return '''<div class="gg-section gg-section--accent" id="prestige">
    <div class="gg-section-header gg-section-header--dark">
      <span class="gg-section-kicker">04</span>
      <h2 class="gg-section-title">Prestige Override</h2>
    </div>
    <div class="gg-section-body">
      <p style="margin-bottom:16px">Some races carry outsized cultural significance that isn&#39;t fully captured by their raw score. The prestige override allows a limited tier promotion for these events.</p>

      <table class="gg-method-table">
        <thead>
          <tr><th>Prestige</th><th>Rule</th><th>Effect</th></tr>
        </thead>
        <tbody>
          <tr>
            <td style="font-weight:700">5 (World-class)</td>
            <td>Score &ge; 75</td>
            <td>Promoted to Tier 1</td>
          </tr>
          <tr>
            <td style="font-weight:700">5 (World-class)</td>
            <td>Score &lt; 75</td>
            <td>Capped at Tier 2 (not promoted to T1)</td>
          </tr>
          <tr>
            <td style="font-weight:700">4 (National)</td>
            <td>Any score</td>
            <td>Promoted 1 tier, but never into Tier 1</td>
          </tr>
          <tr>
            <td>1&ndash;3</td>
            <td>Any score</td>
            <td>No override &mdash; tier determined by score alone</td>
          </tr>
        </tbody>
      </table>

      <p style="margin-top:16px;font-size:12px;color:var(--gg-color-secondary-brown)">The &ge;75 floor for prestige-5 Tier 1 promotion prevents scores as low as 60 from reaching Elite status purely on name recognition. Every T1 race must earn its spot.</p>
    </div>
  </div>'''


def build_faq() -> str:
    faqs = [
        ("Who rates the races?",
         "All ratings are produced by our editorial team. We research each race using official sources, rider reports, community forums, and our own race experience. Every dimension is scored and explained by a human editor."),
        ("Can race organizers influence their score?",
         "No. We do not accept payment, sponsorship, or partnership in exchange for tier placement or score adjustments. Ratings are editorially independent. We may update scores when new information is available (e.g., a race significantly improves its organization)."),
        ("How often are scores updated?",
         "We review scores annually before each race season and make ad-hoc updates when significant changes occur (new ownership, course redesign, series affiliation changes). All changes are logged in the race profile."),
        ("Why isn&#39;t my favorite race rated higher?",
         "Our rubric prioritizes consistency. A race might be incredible for a specific niche but score lower on logistics, field depth, or global prestige. The scoring breakdown shows exactly where a race excels and where it loses points &mdash; check the full profile for details."),
        ("What about mountain bike and bikepacking races?",
         "We include a small number of iconic MTB events (like Leadville and Chequamegon) and ultra-endurance bikepacking races (like Tour Divide and Transcontinental) that are culturally significant to the gravel community. These are tagged with &ldquo;MTB&rdquo; or &ldquo;Bikepacking&rdquo; discipline labels so they&#39;re clearly identified. The same scoring rubric applies."),
    ]

    items = ""
    for q, a in faqs:
        items += f'''
      <div class="gg-accordion-item">
        <button class="gg-accordion-trigger" aria-expanded="false">
          <span>{q}</span>
          <span class="gg-accordion-icon">+</span>
        </button>
        <div class="gg-accordion-body">
          <p>{a}</p>
        </div>
      </div>'''

    return f'''<div class="gg-section" id="faq">
    <div class="gg-section-header">
      <span class="gg-section-kicker">05</span>
      <h2 class="gg-section-title">Frequently Asked Questions</h2>
    </div>
    <div class="gg-section-body">{items}
    </div>
  </div>'''


def build_footer() -> str:
    return '''<div class="gg-footer">
    <p class="gg-footer-disclaimer">This methodology page describes our scoring system. All ratings, opinions, and assessments represent our editorial views based on publicly available information and community research. We are not affiliated with, endorsed by, or officially connected to any race organizer, event, or governing body.</p>
  </div>'''


def build_methodology_css() -> str:
    """Additional CSS specific to the methodology page."""
    return '''<style>
/* Methodology tables */
.gg-neo-brutalist-page .gg-method-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--gg-font-data);
  font-size: 12px;
  border: var(--gg-border-subtle);
}
.gg-neo-brutalist-page .gg-method-table th {
  background: var(--gg-color-primary-brown);
  color: var(--gg-color-white);
  padding: 8px 12px;
  text-align: left;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  border: 1px solid var(--gg-color-dark-brown);
}
.gg-neo-brutalist-page .gg-method-table td {
  padding: 8px 12px;
  border: 1px solid var(--gg-color-sand);
  vertical-align: top;
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
}
.gg-neo-brutalist-page .gg-method-table tbody tr:nth-child(even) {
  background: var(--gg-color-sand);
}
.gg-neo-brutalist-page .gg-method-table--compact td {
  padding: 6px 8px;
  font-size: 11px;
}
.gg-neo-brutalist-page .gg-method-table--compact th {
  padding: 6px 8px;
}
</style>'''


def build_jsonld() -> str:
    """Build WebPage + FAQPage JSON-LD for the methodology page."""
    webpage = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": "How We Rate Gravel Races — Gravel God Methodology",
        "description": "The complete scoring methodology behind Gravel God race ratings. 15 dimensions, 4 tiers, transparent formula.",
        "url": f"{SITE_BASE_URL}/race/methodology/",
        "isPartOf": {
            "@type": "WebSite",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
        "speakable": {
            "@type": "SpeakableSpecification",
            "cssSelector": [".gg-hero-tagline", "#formula .gg-section-body"],
        },
    }
    faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "Who rates the races?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "All ratings are produced by our editorial team. We research each race using official sources, rider reports, community forums, and our own race experience. Every dimension is scored and explained by a human editor.",
                },
            },
            {
                "@type": "Question",
                "name": "Can race organizers influence their score?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "No. We do not accept payment, sponsorship, or partnership in exchange for tier placement or score adjustments. Ratings are editorially independent.",
                },
            },
            {
                "@type": "Question",
                "name": "How often are scores updated?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "We review scores annually before each race season and make ad-hoc updates when significant changes occur (new ownership, course redesign, series affiliation changes).",
                },
            },
            {
                "@type": "Question",
                "name": "Why isn't my favorite race rated higher?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "Our rubric prioritizes consistency. A race might be incredible for a specific niche but score lower on logistics, field depth, or global prestige. The 15-dimension breakdown shows exactly where a race excels and where it loses points.",
                },
            },
            {
                "@type": "Question",
                "name": "What about mountain bike and bikepacking races?",
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": "We include a small number of iconic MTB events (like Leadville and Chequamegon) and ultra-endurance bikepacking races (like Tour Divide and Transcontinental) that are culturally significant to the gravel community. These are tagged with MTB or Bikepacking discipline labels. The same 15-dimension rubric applies.",
                },
            },
        ],
    }
    wp_tag = f'<script type="application/ld+json">{json.dumps(webpage, separators=(",",":"))} </script>'
    faq_tag = f'<script type="application/ld+json">{json.dumps(faq, separators=(",",":"))} </script>'
    return f'{wp_tag}\n  {faq_tag}'


# ── Assemble page ──────────────────────────────────────────────


def generate_methodology_page(external_assets: dict = None) -> str:
    canonical_url = f"{SITE_BASE_URL}/race/methodology/"

    nav = build_nav()
    hero = build_hero()
    tier_system = build_tier_system()
    dimensions = build_dimensions()
    formula = build_formula()
    prestige = build_prestige_override()
    faq = build_faq()
    footer = build_footer()
    method_css = build_methodology_css()
    jsonld = build_jsonld()

    if external_assets:
        page_css = external_assets['css_tag']
        inline_js = external_assets['js_tag']
    else:
        page_css = get_page_css()
        inline_js = build_inline_js()

    og_tags = f'''<meta property="og:title" content="How We Rate Gravel Races — Gravel God Methodology">
  <meta property="og:description" content="The complete scoring methodology behind Gravel God race ratings.">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="How We Rate Gravel Races — Gravel God Methodology">
  <meta name="twitter:description" content="15 dimensions, 4 tiers, transparent formula. Here&#39;s how Gravel God scores every race.">
  <meta name="twitter:image" content="{SITE_BASE_URL}/og/homepage.jpg">'''

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>How We Rate Gravel Races — Gravel God Methodology</title>
  <meta name="description" content="The complete scoring methodology behind Gravel God race ratings. 15 dimensions, 4 tiers, transparent formula.">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {preload}
  {og_tags}
  {jsonld}
  {page_css}
  {method_css}
  {get_ga4_head_snippet()}
</head>
<body>

<div class="gg-neo-brutalist-page">
  {nav}

  {hero}

  {tier_system}

  {dimensions}

  {formula}

  {prestige}

  {faq}

  {footer}
</div>

{inline_js}

{get_consent_banner_html()}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God methodology page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Reuse shared assets if they exist, otherwise write them
    assets = write_shared_assets(output_dir)

    html_content = generate_methodology_page(external_assets=assets)
    output_file = output_dir / "methodology.html"
    output_file.write_text(html_content, encoding="utf-8")
    print(f"Generated {output_file} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
