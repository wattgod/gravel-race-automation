#!/usr/bin/env python3
"""
Generate the Gravel God /athletes/ page (receipts spec §5.5 and §6.1).

Everything about athletes comes from the receipts ledger (receipts_data.py):
TrainingPeaks comment exchanges, the age x ability grid, stories, results
and the opt-out-inclusive count. Nothing renders unless the ledger approves
it, and with no approved athletes the page shows an honest empty state.

The ledger is private. Builds read GG_RECEIPTS_PATH; without it (CI, local
dev) they read the synthetic fixture and the page is marked synthetic so
push_wordpress.py refuses to ship it. GG_BUILD=production refuses the
fixture and refuses unwritten copy.

COPY: every sentence in Matti's voice lives in COPY below and is written by
Matti (CLAUDE.md, docs/AI_WRITING_POLICY.md). Until he writes them they are
"[MATTI WRITES: ...]" briefs, and production builds fail.

Usage:
    python generate_athletes.py
    GG_RECEIPTS_PATH=../gravel-god-training-plans/db/receipts.json \\
        GG_BUILD=production python generate_athletes.py
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from generate_neo_brutalist import (
    SITE_BASE_URL,
    get_page_css,
    build_inline_js,
    write_shared_assets,
)
from brand_tokens import (
    get_ga4_head_snippet,
    get_font_face_css,
    get_preload_hints,
)
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_html
from cookie_consent import get_consent_banner_html
from scroll_animations import get_scroll_animation_css, get_scroll_animation_js
import receipts_data
from receipts_components import (
    esc,
    get_exchange_carousel_js,
    get_receipts_css,
    render_archetype_grid,
    render_count_line,
    render_exchange_carousel,
    render_stories,
    render_verification_line,
)

OUTPUT_DIR = Path(__file__).parent / "output"
PAGE_PATH = "/athletes/"
CHANNEL = "gravelgod"
COPY_PLACEHOLDER = "[MATTI WRITES"

# ── Matti's words. Claude does not write these. ─────────────────────────
# Replace each value with Matti's own text. Anything still starting with
# "[MATTI WRITES" fails a production build (test_athletes_page.py).
COPY = {
    "hero_headline": "[MATTI WRITES: hero headline — angle: more fun than your "
                     "other coach, a chatbot, or your inner dialogue]",
    "hero_dek": "[MATTI WRITES: one or two lines under the headline — what this "
                "page is: real comment threads and real athletes, every kind]",
    "exchanges_intro": "[MATTI WRITES: one line above the TrainingPeaks comment "
                       "screenshots — what a post-workout comment thread with "
                       "you is like]",
    "archetypes_intro": "[MATTI WRITES: one line above the age x ability grid — "
                        "experience with every kind of athlete; empty cells "
                        "stay empty]",
    "stories_intro": "[MATTI WRITES: one line above the athlete stories]",
    "empty_state": "[MATTI WRITES: empty state for zero approved athletes — "
                   "honest: stories are being collected with written approval]",
    "cta_body": "[MATTI WRITES: one line before the coaching link]",
    "meta_description": "[MATTI WRITES: meta description, under 155 characters]",
}

# Neutral labels (not Matti's voice): headings, button text, carousel label.
LABELS = {
    "title": "Athletes",
    "kicker": "ATHLETES",
    "exchanges": "Training-log comments",
    "exchanges_aria": "TrainingPeaks comment threads",
    "archetypes": "By age and level",
    "archetypes_caption": "Athletes by age band and level",
    "stories": "Stories",
    "cta": "Coaching",
    "cta_button": "SEE COACHING",
}


def unwritten_copy() -> list:
    """COPY keys that are still briefs, not Matti's words."""
    return sorted(k for k, v in COPY.items() if str(v).lstrip().startswith(COPY_PLACEHOLDER))


def check_production_ready(ledger) -> None:
    """GG_BUILD=production: no briefs, no synthetic ledger."""
    if not receipts_data.is_production():
        return
    missing = unwritten_copy()
    if missing:
        raise SystemExit(
            f"generate_athletes: GG_BUILD=production but COPY is unwritten: {missing}. "
            "Matti writes these in wordpress/generate_athletes.py.")
    if ledger.synthetic:
        raise SystemExit("generate_athletes: GG_BUILD=production refuses the synthetic ledger")


# ── Sections ─────────────────────────────────────────────────────────────


def build_nav() -> str:
    return get_site_header_html(active="about") + f'''
  <div class="gg-breadcrumb">
    <a href="{SITE_BASE_URL}/">Home</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <span class="gg-breadcrumb-current">{esc(LABELS["title"])}</span>
  </div>'''


def build_hero() -> str:
    headline = COPY["hero_headline"]
    return f'''<div class="gg-hero gg-athletes-hero">
    <div class="gg-hero-tier" style="background:var(--gg-color-gold)">{esc(LABELS["kicker"])}</div>
    <h1>{esc(headline)}</h1>
    <p class="gg-hero-tagline">{esc(COPY["hero_dek"])}</p>
  </div>'''


def _section(section_id: str, kicker: str, title: str, intro_key: str, body: str,
             animate: bool = False) -> str:
    anim = ' data-animate="fade-stagger"' if animate else ""
    intro = f'<p class="gg-athletes-intro">{esc(COPY[intro_key])}</p>' if intro_key else ""
    return f'''<div class="gg-section" id="{section_id}">
    <div class="gg-section-header">
      <span class="gg-section-kicker">{kicker}</span>
      <h2 class="gg-section-title">{esc(title)}</h2>
    </div>
    <div class="gg-section-body">
      {intro}
      <div class="gg-athletes-block"{anim}>{body}</div>
    </div>
  </div>'''


def build_exchanges(ledger) -> str:
    carousel = render_exchange_carousel(ledger.receipts, label=LABELS["exchanges_aria"])
    if not carousel:
        return ""
    return _section("exchanges", "01", LABELS["exchanges"], "exchanges_intro", carousel)


def build_archetypes(ledger) -> str:
    grid = render_archetype_grid(ledger.receipts, caption=LABELS["archetypes_caption"])
    return _section("archetypes", "02", LABELS["archetypes"], "archetypes_intro", grid)


def build_stories(ledger) -> str:
    stories = f'<div class="gg-receipt-stories">{render_stories(ledger.receipts)}</div>'
    # Not animated: a long story list is taller than the observer's 20%
    # threshold could ever reach, so it would stay hidden.
    return _section("stories", "03", LABELS["stories"], "stories_intro", stories)


def build_proof_lines(ledger, *, with_verification: bool) -> str:
    count = render_count_line(ledger.coached_count, ledger.coached_since,
                              ledger.coached_count_as_of)
    verify = render_verification_line() if with_verification else ""
    if not (count or verify):
        return ""
    return f'''<div class="gg-section gg-athletes-proof" id="count">
    <div class="gg-section-body" data-animate="fade-stagger">{count}{verify}</div>
  </div>'''


def build_empty_state() -> str:
    return f'''<div class="gg-section" id="empty">
    <div class="gg-section-body">
      <p class="gg-athletes-empty">{esc(COPY["empty_state"])}</p>
    </div>
  </div>'''


def build_cta() -> str:
    return f'''<div class="gg-section" id="cta">
    <div class="gg-section-header">
      <h2 class="gg-section-title">{esc(LABELS["cta"])}</h2>
    </div>
    <div class="gg-section-body">
      <p class="gg-athletes-intro">{esc(COPY["cta_body"])}</p>
      <a href="{SITE_BASE_URL}/coaching/" class="gg-athletes-cta-btn" data-cta="athletes_coaching">{esc(LABELS["cta_button"])}</a>
    </div>
  </div>'''


def build_athletes_css() -> str:
    return '''<style>
.gg-neo-brutalist-page .gg-athletes-hero { background: var(--gg-color-warm-paper); border-bottom: 3px double var(--gg-color-dark-brown); }
.gg-neo-brutalist-page .gg-athletes-hero h1 { color: var(--gg-color-dark-brown); }
.gg-neo-brutalist-page .gg-athletes-hero .gg-hero-tagline { color: var(--gg-color-secondary-brown); }
.gg-neo-brutalist-page .gg-athletes-intro, .gg-neo-brutalist-page .gg-athletes-empty { font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-base); line-height: var(--gg-line-height-prose); color: var(--gg-color-dark-brown); margin: 0 0 var(--gg-spacing-md); max-width: 640px; }
.gg-neo-brutalist-page .gg-athletes-cta-btn { display: inline-block; background: var(--gg-color-teal); color: var(--gg-color-warm-paper); font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: var(--gg-font-weight-bold); text-transform: uppercase; letter-spacing: var(--gg-letter-spacing-wider); padding: var(--gg-spacing-sm) var(--gg-spacing-lg); border: 3px solid var(--gg-color-teal); text-decoration: none; transition: background-color var(--gg-transition-hover), border-color var(--gg-transition-hover); }
.gg-neo-brutalist-page .gg-athletes-cta-btn:hover { background-color: var(--gg-color-dark-brown); border-color: var(--gg-color-dark-brown); }
''' + get_receipts_css() + get_scroll_animation_css(["fade-stagger"]) + '''
</style>'''


def build_athletes_js(with_carousel: bool = True) -> str:
    """User-initiated GA events only: CTA and result-link clicks, carousel
    buttons/keys. No timers."""
    carousel_js = get_exchange_carousel_js() if with_carousel else ""
    return carousel_js + '''
<script>
document.querySelectorAll('[data-cta]').forEach(function(el) {
  el.addEventListener('click', function() {
    if (typeof gtag === 'function') gtag('event', 'cta_click', { source: 'athletes', cta_name: el.getAttribute('data-cta') });
  });
});
document.querySelectorAll('[data-proof]').forEach(function(el) {
  el.addEventListener('click', function() {
    if (typeof gtag === 'function') gtag('event', 'proof_link_click', { proof_type: el.getAttribute('data-proof') });
  });
});
''' + get_scroll_animation_js() + '''
</script>'''


def build_jsonld(description: str) -> str:
    webpage = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": "Athletes — Gravel God Cycling",
        "description": description,
        "url": f"{SITE_BASE_URL}{PAGE_PATH}",
        "isPartOf": {"@type": "WebSite", "name": "Gravel God Cycling", "url": SITE_BASE_URL},
    }
    payload = json.dumps(webpage, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/ld+json">{payload}</script>'


# ── Assemble ─────────────────────────────────────────────────────────────


def generate_athletes_page(ledger=None, external_assets: dict = None) -> str:
    if ledger is None:
        ledger = receipts_data.load_ledger(CHANNEL)
    check_production_ready(ledger)

    canonical_url = f"{SITE_BASE_URL}{PAGE_PATH}"
    title = "Athletes — Gravel God Cycling"
    description = COPY["meta_description"]
    has_receipts = bool(ledger.receipts)

    if has_receipts:
        body = "\n\n  ".join(s for s in (
            build_exchanges(ledger),
            build_archetypes(ledger),
            build_stories(ledger),
            build_proof_lines(ledger, with_verification=True),
        ) if s)
    else:
        body = build_empty_state() + "\n\n  " + build_proof_lines(ledger, with_verification=False)

    if external_assets:
        page_css = f'<style>{get_font_face_css("/race/assets/fonts")}</style>\n  ' + external_assets["css_tag"]
        inline_js = external_assets["js_tag"]
    else:
        page_css = get_page_css()
        inline_js = build_inline_js()

    synthetic_meta = ('<meta name="gg-receipts-source" content="synthetic">\n  '
                      '<meta name="robots" content="noindex, nofollow">'
                      if ledger.synthetic else '<meta name="robots" content="index, follow">')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  {synthetic_meta}
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {get_preload_hints()}
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  {build_jsonld(description)}
  {page_css}
  {build_athletes_css()}
  {get_ga4_head_snippet()}
</head>
<body>

<div class="gg-neo-brutalist-page">
  {build_nav()}

  {build_hero()}

  {body}

  {build_cta()}

  {get_mega_footer_html()}
</div>

{inline_js}
{build_athletes_js(with_carousel=bool(ledger.exchanges))}

{get_consent_banner_html()}
</body>
</html>'''


def strip_image_metadata(src: Path, dst: Path) -> bool:
    """Re-encode `src` to `dst` from pixels only: no EXIF, GPS, text chunks,
    ICC or XMP. Returns False when Pillow isn't installed."""
    try:
        from PIL import Image
    except ImportError:
        return False
    with Image.open(src) as im:
        has_alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
        mode = "RGBA" if has_alpha else "RGB"
        pixels = im.convert(mode)
        clean = Image.frombytes(mode, pixels.size, pixels.tobytes())
    suffix = dst.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        clean.convert("RGB").save(dst, "JPEG", quality=90)
    elif suffix == ".webp":
        clean.save(dst, "WEBP", quality=90)
    else:
        clean.save(dst, "PNG", optimize=True)
    return True


def copy_exchange_media(ledger, output_dir: Path) -> list:
    """Write each approved exchange image to output/athletes/media/ under its
    published (hashed) name, metadata stripped. Files no longer approved are
    removed (withdrawal). Production builds fail without Pillow."""
    media_dir = output_dir / "athletes" / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    wanted = {ex.media_name: ex.image_path for ex in ledger.exchanges}
    for old in media_dir.iterdir():
        if old.is_file() and old.name not in wanted:
            old.unlink()
    for name, src in sorted(wanted.items()):
        if not strip_image_metadata(src, media_dir / name):
            if receipts_data.is_production():
                raise SystemExit("generate_athletes: Pillow is required in production to strip "
                                 "screenshot metadata (pip install Pillow)")
            print(f"  WARNING: Pillow missing; copied {name} with its metadata (dev build only)",
                  file=sys.stderr)
            shutil.copyfile(src, media_dir / name)
    return sorted(wanted)


def main():
    parser = argparse.ArgumentParser(description="Generate the Gravel God /athletes/ page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        ledger = receipts_data.load_ledger(CHANNEL, verbose=True)
    except (receipts_data.ReceiptsConfigError, receipts_data.ReceiptValidationError) as e:
        raise SystemExit(f"generate_athletes: {e}")
    check_production_ready(ledger)

    assets = write_shared_assets(output_dir)
    html_content = generate_athletes_page(ledger, external_assets=assets)
    media = copy_exchange_media(ledger, output_dir)
    output_file = output_dir / "athletes.html"
    output_file.write_text(html_content, encoding="utf-8")
    source = "SYNTHETIC fixture" if ledger.synthetic else str(ledger.path)
    print(f"Generated {output_file} ({len(html_content):,} bytes) from {source}: "
          f"{len(ledger.receipts)} athletes, {len(media)} exchange images")
    if unwritten_copy():
        print(f"  COPY still unwritten: {', '.join(unwritten_copy())}", file=sys.stderr)


if __name__ == "__main__":
    main()
