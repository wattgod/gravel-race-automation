#!/usr/bin/env python3
"""
Generate the Surge Check page (gravelgodcycling.com/surge-check/).

A rider drops easy-ride .fit files and gets the Surge Index for each: the
share of the ride's load that came in short surges (5-60 s at 90% FTP or
more). The files are read in the browser and never uploaded. The chosen ride
then shows in Endure's Analyze view (an iframe of endurelabs.app/embed/surge)
with every surge shaded; a plain chart stands in when that frame can't load.

The maths is Endure's own (wordpress/surge_check/surge-core.js is a line-for-
line port of src/lib/analysis/surge-index.ts), held to Endure's parity fixture
by tests/test_surge_check.py.

Output: wordpress/output/surge-check/ (index.html, surge-core.js,
surge-check.js, vendor/). Deploy: push_wordpress.py --sync-surge-check.

Usage:
    python generate_surge_check.py
    python generate_surge_check.py --output-dir ./output
"""
from __future__ import annotations

import argparse
import html
import shutil
from pathlib import Path

from generate_neo_brutalist import SITE_BASE_URL, get_page_css, write_shared_assets
from brand_tokens import get_ab_head_snippet, get_font_face_css, get_ga4_head_snippet, get_preload_hints
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_css, get_site_header_html, get_site_header_js
from cookie_consent import get_consent_banner_html

OUTPUT_DIR = Path(__file__).parent / "output"
SOURCE_DIR = Path(__file__).parent / "surge_check"
SLUG = "surge-check"
CANONICAL_URL = f"{SITE_BASE_URL}/{SLUG}/"
ENDURE_ORIGIN = "https://endurelabs.app"

TITLE = "Did You Surge Your Easy Rides? | Gravel God"
META_DESC = (
    "Drop in your easy-ride .fit files and see how much of each ride's load came in short surges. "
    "Your files stay on your device."
)

# Files copied next to index.html, as the page imports them.
ASSETS = ("surge-core.js", "surge-check.js", "vendor/fit-file-parser-2.1.0.js", "vendor/THIRD-PARTY-LICENSES.txt")


def esc(text) -> str:
    """HTML-escape a string (0 and "" stay visible: see CLAUDE.md pitfall 4)."""
    return "" if text is None else html.escape(str(text))


def build_nav() -> str:
    breadcrumb = f'''<div class="gg-wp-breadcrumb">
  <a href="{SITE_BASE_URL}/">Home</a>
  <span class="gg-wp-breadcrumb-sep">&rsaquo;</span>
  <span>Surge Check</span>
</div>'''
    return get_site_header_html("resources") + "\n" + breadcrumb


def build_tool() -> str:
    return f'''<main class="gg-sc" id="gg-sc" data-endure="{esc(ENDURE_ORIGIN)}">
  <span class="gg-sc-eyebrow">SURGE CHECK</span>
  <h1 class="gg-sc-title">Did you surge your easy rides?</h1>
  <div class="gg-sc-inputs">
    <label class="gg-sc-drop" id="gg-sc-drop" tabindex="0">
      Drop easy-ride .fit files
      <small>Several is better. They stay on your device.</small>
      <input type="file" id="gg-sc-file" accept=".fit,.FIT" multiple hidden>
    </label>
    <div class="gg-sc-ftp">
      <label for="gg-sc-ftp">FTP (W)</label>
      <input id="gg-sc-ftp" type="number" inputmode="numeric" min="50" max="1000" step="1">
    </div>
  </div>
  <noscript><p class="gg-sc-err">Surge Check reads your files in the browser, so it needs JavaScript.</p></noscript>
  <p class="gg-sc-status" id="gg-sc-status" role="status" hidden></p>
  <section id="gg-sc-out" aria-live="polite"></section>
  <section class="gg-sc-analyze" id="gg-sc-analyze" hidden>
    <div id="gg-sc-frame"></div>
    <div id="gg-sc-fallback" hidden></div>
  </section>
  {build_method()}
</main>'''


def build_method() -> str:
    """How it's read: the definitions a rider needs to trust the number, and the line's limits."""
    return '''<section class="gg-sc-method">
    <h2 class="gg-sc-label">How it's read</h2>
    <ul>
      <li><strong>Surge:</strong> 3-second power at 90% of FTP or more, lasting 5 to 60 seconds.</li>
      <li><strong>Surge Index:</strong> the share of the ride's load (each second weighted by (power &divide; FTP)&sup2;) that came in surges.</li>
      <li><strong>Easy ride:</strong> intensity factor 0.75 or lower, at least 45 minutes of 1-second power.</li>
      <li><strong>Extra load:</strong> how much more load the ride carried than the same work ridden smooth.</li>
      <li><strong>Bands:</strong> from 752 easy rides by 16 riders, May to October 2026. They describe that group, not a threshold for harm: next-morning heart rate variability showed no clear cost at any level.</li>
    </ul>
  </section>'''


def build_css() -> str:
    return '''<style>
.gg-sc { max-width: 760px; margin: 0 auto; padding: var(--gg-spacing-xl) var(--gg-spacing-md) var(--gg-spacing-3xl); color: var(--gg-color-dark-brown); font-family: var(--gg-font-editorial); }
.gg-sc *, .gg-sc *::before, .gg-sc *::after { box-sizing: border-box; border-radius: 0 !important; box-shadow: none !important; }
.gg-sc-eyebrow, .gg-sc-label { display: block; font: var(--gg-font-weight-semibold) var(--gg-font-size-2xs) var(--gg-font-data); letter-spacing: var(--gg-letter-spacing-ultra-wide); color: var(--gg-color-secondary-brown); text-transform: uppercase; margin: 0 0 var(--gg-spacing-xs); }
.gg-sc-title { font-size: clamp(30px, 6vw, var(--gg-font-size-3xl)); line-height: var(--gg-line-height-tight); letter-spacing: var(--gg-letter-spacing-tight); margin: var(--gg-spacing-xs) 0 var(--gg-spacing-xl); }
.gg-sc-inputs { display: flex; flex-wrap: wrap; gap: var(--gg-spacing-sm); align-items: stretch; }
.gg-sc-drop { flex: 1 1 320px; border: 3px dashed var(--gg-color-primary-brown); padding: 28px 20px; text-align: center; cursor: pointer; font: var(--gg-font-weight-semibold) var(--gg-font-size-sm) var(--gg-font-data); color: var(--gg-color-primary-brown); transition: background 150ms; }
.gg-sc-drop:hover, .gg-sc-drop.gg-sc-over { background: var(--gg-color-sand); }
.gg-sc-drop small { display: block; margin-top: 6px; font-weight: var(--gg-font-weight-regular); color: var(--gg-color-secondary-brown); }
.gg-sc-drop:focus-visible, .gg-sc input:focus-visible, .gg-sc tr:focus-visible, .gg-sc a:focus-visible { outline: 3px solid var(--gg-color-teal); outline-offset: 2px; }
.gg-sc-ftp { display: flex; flex-direction: column; justify-content: center; gap: 6px; border: 3px solid var(--gg-color-primary-brown); padding: var(--gg-spacing-sm) var(--gg-spacing-md); }
.gg-sc-ftp label { font: var(--gg-font-weight-semibold) var(--gg-font-size-2xs) var(--gg-font-data); letter-spacing: var(--gg-letter-spacing-wider); color: var(--gg-color-secondary-brown); }
.gg-sc-ftp input { width: 7ch; font: var(--gg-font-weight-semibold) var(--gg-font-size-xl) var(--gg-font-data); color: var(--gg-color-dark-brown); background: transparent; border: 0; border-bottom: 2px solid var(--gg-color-tan); padding: 0; }
#gg-sc-out { margin-top: var(--gg-spacing-2xl); }
.gg-sc-err { color: var(--gg-color-error); font: var(--gg-font-size-sm) var(--gg-font-data); }
.gg-sc-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 20px; }
.gg-sc-big { font: var(--gg-font-weight-bold) clamp(64px, 16vw, 112px)/1 var(--gg-font-data); letter-spacing: -2px; }
.gg-sc-band { font: var(--gg-font-weight-bold) clamp(22px, 5vw, var(--gg-font-size-2xl))/1.1 var(--gg-font-editorial); }
.gg-sc-verdict { font-size: var(--gg-font-size-md); line-height: var(--gg-line-height-normal); margin: var(--gg-spacing-md) 0 0; max-width: 60ch; }
.gg-sc-sub { font: var(--gg-font-size-sm) var(--gg-font-data); color: var(--gg-color-primary-brown); margin: var(--gg-spacing-xs) 0 0; }
.gg-sc-scale { position: relative; display: grid; grid-template-columns: 10fr 10fr 10fr 12fr; gap: 2px; margin: 28px 0 6px; }
.gg-sc-scale div { height: 10px; background: var(--gg-color-tan); }
.gg-sc-scale div.on { background: var(--gg-color-light-gold); }
.gg-sc-pin { position: absolute; top: -6px; width: 3px; height: 22px; background: var(--gg-color-dark-brown); transform: translateX(-1px); }
.gg-sc-ticks { display: grid; grid-template-columns: 10fr 10fr 10fr 12fr; font: var(--gg-font-size-2xs) var(--gg-font-data); color: var(--gg-color-secondary-brown); }
.gg-sc-ticks span { padding-left: 2px; }
.gg-sc-rides { margin-top: var(--gg-spacing-xl); }
.gg-sc table { width: 100%; border-collapse: collapse; font: var(--gg-font-size-xs) var(--gg-font-data); }
.gg-sc th { text-align: left; font-weight: var(--gg-font-weight-semibold); color: var(--gg-color-secondary-brown); padding: 6px 8px 6px 0; border-bottom: 2px solid var(--gg-color-primary-brown); }
.gg-sc td { padding: 8px 8px 8px 0; border-bottom: 1px solid var(--gg-color-tan); }
.gg-sc .gg-sc-num { text-align: right; }
.gg-sc .gg-sc-bandcol { padding-left: 20px; }
.gg-sc-pick { cursor: pointer; }
.gg-sc-rowbtn { all: unset; cursor: pointer; }
.gg-sc-rowbtn:focus-visible { outline: 3px solid var(--gg-color-teal); outline-offset: 2px; }
.gg-sc-status { margin-top: var(--gg-spacing-lg); font: var(--gg-font-size-sm) var(--gg-font-data); color: var(--gg-color-primary-brown); }
.gg-sc-pick:hover td, .gg-sc-sel td { background: var(--gg-color-sand); }
.gg-sc-sel td { font-weight: var(--gg-font-weight-semibold); }
.gg-sc-skip td { color: var(--gg-color-secondary-brown); }
.gg-sc-note { margin-top: var(--gg-spacing-lg); color: var(--gg-color-primary-brown); }
.gg-sc-analyze { margin-top: var(--gg-spacing-xl); border: 3px solid var(--gg-color-dark-brown); }
.gg-sc-iframe { display: block; width: 100%; height: 640px; border: 0; }
#gg-sc-fallback { padding: var(--gg-spacing-md); }
.gg-sc-chart { position: relative; }
.gg-sc-canvas { display: block; width: 100%; height: 200px; touch-action: none; }
.gg-sc-tip { position: absolute; top: 0; display: none; pointer-events: none; font: 12px var(--gg-font-data); background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); padding: 4px 8px; white-space: nowrap; }
.gg-sc-built { margin: var(--gg-spacing-sm) 0 0; font: var(--gg-font-size-xs) var(--gg-font-data); color: var(--gg-color-secondary-brown); }
.gg-sc-built a { color: inherit; }
.gg-sc-built a:hover { color: var(--gg-color-teal); }
.gg-sc-method { margin-top: var(--gg-spacing-3xl); border-top: 2px solid var(--gg-color-tan); padding-top: var(--gg-spacing-lg); font-size: var(--gg-font-size-sm); color: var(--gg-color-primary-brown); }
.gg-sc-method ul { margin: 0; padding-left: 1.2em; }
.gg-sc-method li { margin: 6px 0; }
.gg-wp-breadcrumb { max-width: 760px; margin: 0 auto; padding: var(--gg-spacing-sm) var(--gg-spacing-md); font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); color: var(--gg-color-secondary-brown); }
.gg-wp-breadcrumb a { color: var(--gg-color-secondary-brown); text-decoration: none; }
.gg-wp-breadcrumb a:hover { color: var(--gg-color-gold); }
.gg-wp-breadcrumb-sep { margin: 0 var(--gg-spacing-xs); }
.gg-wp-page { margin: 0; background: var(--gg-color-warm-paper); }
[hidden] { display: none !important; }
</style>'''


def generate_page(external_assets: dict | None = None) -> str:
    page_css = external_assets["css_tag"] if external_assets else get_page_css()
    og = f'''<meta property="og:title" content="{esc(TITLE)}">
  <meta property="og:description" content="{esc(META_DESC)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(CANONICAL_URL)}">
  <meta property="og:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">'''
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(TITLE)}</title>
  <meta name="description" content="{esc(META_DESC)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(CANONICAL_URL)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {get_preload_hints()}
  {og}
  {page_css}
  <style>{get_font_face_css()}</style>
  <style>{get_site_header_css()}</style>
  {build_css()}
  {get_ga4_head_snippet()}
  {get_ab_head_snippet()}
</head>
<body>
<a href="#gg-sc" class="gg-skip-link">Skip to content</a>
<div class="gg-wp-page">
  {build_nav()}
  {build_tool()}
  {get_mega_footer_html()}
</div>
<script>{get_site_header_js()}</script>
<script type="module" src="/{SLUG}/surge-check.js"></script>
{get_consent_banner_html()}
</body>
</html>'''


def write_output(output_dir: Path) -> Path:
    """Write index.html and the page's scripts to output_dir/surge-check/."""
    page_dir = output_dir / SLUG
    page_dir.mkdir(parents=True, exist_ok=True)
    assets = write_shared_assets(output_dir)
    for name in ASSETS:
        dst = page_dir / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE_DIR / name, dst)
    index = page_dir / "index.html"
    index.write_text(generate_page(external_assets=assets), encoding="utf-8")
    return index


def main():
    parser = argparse.ArgumentParser(description="Generate the Gravel God Surge Check page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()
    index = write_output(Path(args.output_dir))
    print(f"Generated {index} ({index.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
