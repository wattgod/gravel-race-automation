"""
Brand token helpers for Gravel God CSS generation.

Provides CSS custom properties (:root block), @font-face declarations,
and color mapping from the gravel-god-brand design system.
"""

from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────
BRAND_DIR = Path(__file__).resolve().parent.parent.parent / "gravel-god-brand"
BRAND_FONTS_DIR = BRAND_DIR / "assets" / "fonts"

# 8 woff2 font files to self-host
FONT_FILES = [
    "SometypeMono-normal-latin.woff2",
    "SometypeMono-normal-latin-ext.woff2",
    "SometypeMono-italic-latin.woff2",
    "SometypeMono-italic-latin-ext.woff2",
    "SourceSerif4-normal-latin.woff2",
    "SourceSerif4-normal-latin-ext.woff2",
    "SourceSerif4-italic-latin.woff2",
    "SourceSerif4-italic-latin-ext.woff2",
]


# ── Analytics ─────────────────────────────────────────────────
GA_MEASUREMENT_ID = "G-EJJZ9T6M52"

# ── Site ──────────────────────────────────────────────────────
SITE_BASE_URL = "https://gravelgodcycling.com"


def get_tokens_css() -> str:
    """Return the :root CSS custom properties block."""
    return """:root {
  /* color */
  --gg-color-dark-brown: #3a2e25;
  --gg-color-primary-brown: #59473c;
  --gg-color-secondary-brown: #7d695d;
  --gg-color-warm-brown: #A68E80;
  --gg-color-tan: #d4c5b9;
  --gg-color-sand: #ede4d8;
  --gg-color-warm-paper: #f5efe6;
  --gg-color-gold: #9a7e0a;
  --gg-color-light-gold: #c9a92c;
  --gg-color-teal: #178079;
  --gg-color-light-teal: #4ECDC4;
  --gg-color-near-black: #1a1613;
  --gg-color-white: #ffffff;
  --gg-color-error: #c0392b;
  --gg-color-tier-1: #59473c;
  --gg-color-tier-2: #7d695d;
  --gg-color-tier-3: #766a5e;
  --gg-color-tier-4: #5e6868;

  /* font */
  --gg-font-data: 'Sometype Mono', monospace;
  --gg-font-editorial: 'Source Serif 4', Georgia, serif;
  --gg-font-size-2xs: 10px;
  --gg-font-size-xs: 13px;
  --gg-font-size-sm: 14px;
  --gg-font-size-base: 16px;
  --gg-font-size-md: 18px;
  --gg-font-size-lg: 20px;
  --gg-font-size-xl: 24px;
  --gg-font-size-2xl: 28px;
  --gg-font-size-3xl: 42px;
  --gg-font-size-4xl: 48px;
  --gg-font-size-5xl: 56px;
  --gg-font-weight-regular: 400;
  --gg-font-weight-semibold: 600;
  --gg-font-weight-bold: 700;

  /* line-height */
  --gg-line-height-tight: 1.1;
  --gg-line-height-normal: 1.5;
  --gg-line-height-relaxed: 1.7;
  --gg-line-height-prose: 1.75;

  /* letter-spacing */
  --gg-letter-spacing-tight: -0.5px;
  --gg-letter-spacing-normal: 0;
  --gg-letter-spacing-wide: 1px;
  --gg-letter-spacing-wider: 2px;
  --gg-letter-spacing-ultra-wide: 3px;
  --gg-letter-spacing-extreme: 4px;

  /* spacing */
  --gg-spacing-2xs: 4px;
  --gg-spacing-xs: 8px;
  --gg-spacing-sm: 12px;
  --gg-spacing-md: 16px;
  --gg-spacing-lg: 24px;
  --gg-spacing-xl: 32px;
  --gg-spacing-2xl: 48px;
  --gg-spacing-3xl: 64px;
  --gg-spacing-4xl: 96px;

  /* border */
  --gg-border-width-subtle: 2px;
  --gg-border-width-standard: 3px;
  --gg-border-width-heavy: 4px;
  --gg-border-color-default: #3a2e25;
  --gg-border-color-brand: #59473c;
  --gg-border-color-secondary: #7d695d;
  --gg-border-color-gold: #9a7e0a;
  --gg-border-radius: 0;

  /* animation */
  --gg-animation-duration-instant: 0ms;
  --gg-animation-duration-fast: 150ms;
  --gg-animation-duration-normal: 300ms;
  --gg-animation-duration-slow: 500ms;
  --gg-animation-easing-sharp: cubic-bezier(0.4, 0, 0.2, 1);
}

/* Composite tokens (derived) */
:root {
  --gg-border-subtle: var(--gg-border-width-subtle) solid var(--gg-border-color-default);
  --gg-border-standard: var(--gg-border-width-standard) solid var(--gg-border-color-default);
  --gg-border-heavy: var(--gg-border-width-heavy) solid var(--gg-border-color-default);
  --gg-border-double: var(--gg-border-width-heavy) double var(--gg-border-color-default);
  --gg-border-gold: var(--gg-border-width-standard) solid var(--gg-border-color-gold);
  --gg-border-brand: var(--gg-border-width-standard) solid var(--gg-border-color-brand);
  --gg-border-secondary: var(--gg-border-width-standard) solid var(--gg-border-color-secondary);
  --gg-transition-hover: var(--gg-animation-duration-normal) var(--gg-animation-easing-sharp);
}"""


def get_font_face_css(font_path_prefix: str = "/race/assets/fonts") -> str:
    """Return @font-face declarations for self-hosted fonts.

    Args:
        font_path_prefix: URL prefix for font files (no trailing slash).
    """
    p = font_path_prefix.rstrip("/")
    return f"""/* Sometype Mono — Normal — Latin Extended */
@font-face {{
  font-family: 'Sometype Mono';
  font-style: normal;
  font-weight: 400 700;
  font-display: swap;
  src: url('{p}/SometypeMono-normal-latin-ext.woff2') format('woff2');
  unicode-range: U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF;
}}
/* Sometype Mono — Normal — Latin */
@font-face {{
  font-family: 'Sometype Mono';
  font-style: normal;
  font-weight: 400 700;
  font-display: swap;
  src: url('{p}/SometypeMono-normal-latin.woff2') format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}}
/* Sometype Mono — Italic — Latin Extended */
@font-face {{
  font-family: 'Sometype Mono';
  font-style: italic;
  font-weight: 400 700;
  font-display: swap;
  src: url('{p}/SometypeMono-italic-latin-ext.woff2') format('woff2');
  unicode-range: U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF;
}}
/* Sometype Mono — Italic — Latin */
@font-face {{
  font-family: 'Sometype Mono';
  font-style: italic;
  font-weight: 400 700;
  font-display: swap;
  src: url('{p}/SometypeMono-italic-latin.woff2') format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}}
/* Source Serif 4 — Normal — Latin Extended */
@font-face {{
  font-family: 'Source Serif 4';
  font-style: normal;
  font-weight: 400 700;
  font-display: swap;
  src: url('{p}/SourceSerif4-normal-latin-ext.woff2') format('woff2');
  unicode-range: U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF;
}}
/* Source Serif 4 — Normal — Latin */
@font-face {{
  font-family: 'Source Serif 4';
  font-style: normal;
  font-weight: 400 700;
  font-display: swap;
  src: url('{p}/SourceSerif4-normal-latin.woff2') format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}}
/* Source Serif 4 — Italic — Latin Extended */
@font-face {{
  font-family: 'Source Serif 4';
  font-style: italic;
  font-weight: 400 700;
  font-display: swap;
  src: url('{p}/SourceSerif4-italic-latin-ext.woff2') format('woff2');
  unicode-range: U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF;
}}
/* Source Serif 4 — Italic — Latin */
@font-face {{
  font-family: 'Source Serif 4';
  font-style: italic;
  font-weight: 400 700;
  font-display: swap;
  src: url('{p}/SourceSerif4-italic-latin.woff2') format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}}"""


def get_preload_hints(font_path_prefix: str = "/race/assets/fonts") -> str:
    """Return <link rel=preload> tags for the Latin (most common) font subsets."""
    p = font_path_prefix.rstrip("/")
    return f"""<link rel="preload" href="{p}/SometypeMono-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{p}/SourceSerif4-normal-latin.woff2" as="font" type="font/woff2" crossorigin>"""


# ── Color mapping for SVG attributes (can't use CSS vars) ────

# Direct hex values from the brand tokens, for use in SVG attributes
# and Python functions that generate inline color values.
COLORS = {
    "dark_brown": "#3a2e25",
    "primary_brown": "#59473c",
    "secondary_brown": "#7d695d",
    "warm_brown": "#A68E80",
    "tan": "#d4c5b9",
    "sand": "#ede4d8",
    "warm_paper": "#f5efe6",
    "gold": "#9a7e0a",
    "light_gold": "#c9a92c",
    "teal": "#178079",
    "light_teal": "#4ECDC4",
    "near_black": "#1a1613",
    "white": "#ffffff",
    "tier_1": "#59473c",
    "tier_2": "#7d695d",
    "tier_3": "#766a5e",
    "tier_4": "#5e6868",
}


# ── A/B Testing ──────────────────────────────────────────────


def get_ab_bootstrap_js() -> str:
    """Return the minified inline bootstrap JS (shared with gg-ab.php)."""
    return (
        '(function(){var s=localStorage.getItem("gg_ab_assign");'
        'if(!s)return;try{var a=JSON.parse(s);'
        'var c=localStorage.getItem("gg_ab_cache");'
        'if(!c)return;var cache=JSON.parse(c);'
        'for(var eid in a){if(!cache[eid])continue;'
        'var el=document.querySelector(cache[eid].sel);'
        'if(el)el.textContent=cache[eid].txt;}'
        '}catch(e){}})();'
    )


def get_ab_js_filename() -> str:
    """Return the cache-busted AB JS filename based on content hash."""
    import hashlib
    js_path = Path(__file__).resolve().parent.parent / "web" / "gg-ab-tests.js"
    if not js_path.exists():
        return "gg-ab-tests.js"
    content = js_path.read_text()
    js_hash = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"gg-ab-tests.{js_hash}.js"


def get_ab_head_snippet() -> str:
    """Return inline bootstrap + deferred script tag for A/B tests.

    The inline script synchronously swaps text for returning visitors
    from localStorage cache (zero flicker). The deferred script handles
    new visitor assignment, GA4 events, and cache refresh.
    """
    bootstrap = get_ab_bootstrap_js()
    js_filename = get_ab_js_filename()
    return (
        f'<script>{bootstrap}</script>\n'
        f'  <script defer src="/ab/{js_filename}"></script>'
    )


# ── Racer Rating ─────────────────────────────────────────────
# Minimum number of ratings before displaying the racer score.
# Used by all generators (race profiles, state hubs, homepage, series hubs).
RACER_RATING_THRESHOLD = 3
