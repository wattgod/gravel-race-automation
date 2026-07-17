"""
Brand token helpers for Gravel God CSS generation.

Provides CSS custom properties (:root block), @font-face declarations,
and color mapping from the gravel-god-brand design system.
"""

from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────
BRAND_DIR = Path(__file__).resolve().parent.parent.parent / "gravel-god-brand"
BRAND_FONTS_DIR = BRAND_DIR / "assets" / "fonts"

# 10 woff2 font files to self-host
FONT_FILES = [
    "SometypeMono-normal-latin.woff2",
    "SometypeMono-normal-latin-ext.woff2",
    "SometypeMono-italic-latin.woff2",
    "SometypeMono-italic-latin-ext.woff2",
    "SourceSerif4-normal-latin.woff2",
    "SourceSerif4-normal-latin-ext.woff2",
    "SourceSerif4-italic-latin.woff2",
    "SourceSerif4-italic-latin-ext.woff2",
    "Unbounded-900-latin.woff2",
    "Unbounded-900-latin-ext.woff2",
]


# ── Analytics ─────────────────────────────────────────────────
GA_MEASUREMENT_ID = "G-EJJZ9T6M52"


def get_ga4_head_snippet() -> str:
    """Return consent defaults + GA4 loading scripts for <head>.

    Must be placed before </head>. Consent defaults fire synchronously
    before GA4 loads (async), ensuring Consent Mode v2 compliance.

    Returns raw HTML (not f-string safe). Use directly in string
    concatenation or .format(), NOT inside f-strings with {{ }}.

    Centralized here to eliminate 25+ copy-pasted blocks across generators.
    Parity with gg-cookie-consent.php enforced by test_cookie_consent_mu_plugin.py.
    """
    return (
        "<script>window.dataLayer=window.dataLayer||[];"
        "function gtag(){dataLayer.push(arguments)}"
        "gtag('consent','default',{"
        "'analytics_storage':/(^|; )gg_consent=accepted/.test(document.cookie)?'granted':'denied',"
        "'ad_storage':'denied','ad_user_data':'denied',"
        "'ad_personalization':'denied','wait_for_update':500});</script>\n"
        f'  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>\n'
        f"  <script>gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>"
    )

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
  --gg-font-display: 'Unbounded', sans-serif;
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
  --gg-font-weight-black: 900;

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
  --gg-letter-spacing-display: 6px;

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
}}
/* Unbounded — 900 (Black) — Latin Extended */
@font-face {{
  font-family: 'Unbounded';
  font-style: normal;
  font-weight: 900;
  font-display: swap;
  src: url('{p}/Unbounded-900-latin-ext.woff2') format('woff2');
  unicode-range: U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, U+2C60-2C7F, U+A720-A7FF;
}}
/* Unbounded — 900 (Black) — Latin */
@font-face {{
  font-family: 'Unbounded';
  font-style: normal;
  font-weight: 900;
  font-display: swap;
  src: url('{p}/Unbounded-900-latin.woff2') format('woff2');
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}}"""


def get_preload_hints(font_path_prefix: str = "/race/assets/fonts") -> str:
    """Return <link rel=preload> tags for the Latin (most common) font subsets."""
    p = font_path_prefix.rstrip("/")
    return f"""<link rel="preload" href="{p}/SometypeMono-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{p}/SourceSerif4-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{p}/Unbounded-900-latin.woff2" as="font" type="font/woff2" crossorigin>"""


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


# ── Tier Names ──────────────────────────────────────────────
# Canonical tier names used across all generators and the search widget.
# Badges always say "TIER 1" / "TIER 2" etc. These are the subtitle names.
TIER_NAMES = {1: "The Icons", 2: "Elite", 3: "Solid", 4: "Grassroots"}

TIER_DESCS = {
    1: "The definitive gravel events. World-class fields, iconic courses, bucket-list status.",
    2: "Established races with strong reputations and competitive fields. The next tier of must-do events.",
    3: "Regional favorites and emerging races. Strong local scenes, genuine gravel character.",
    4: "Up-and-coming races and local grinders. Small fields, raw vibes, grassroots gravel.",
}


# ── Clean Pro Theme (Deliver) ──────────────────────────────


CLEAN_PRO_COLORS = {
    "primary": "#1a1a1a",       # Near-black (headlines)
    "accent": "#4ECDC4",        # Turquoise (interactive states only)
    "bg": "#ffffff",            # White
    "bg_alt": "#fafafa",        # Off-white
    "text": "#1a1a1a",          # Headlines
    "text_body": "#4a4a4a",     # Body text
    "text_muted": "#767676",    # Metadata/labels (WCAG AA compliant on white)
    "border": "#e5e5e5",        # Hairlines
    "error": "#c0392b",         # Wrong answers
}


def get_clean_pro_tokens_css() -> str:
    """Return the :root CSS custom properties for Clean Pro theme (Deliver).

    Maps --gg-* variables to Clean Pro values so existing block renderers
    work without modification — they reference --gg-color-*, --gg-font-*,
    and the output just looks different.
    """
    return """:root {
  /* color — Clean Pro (Deliver) */
  --gg-color-dark-brown: #1a1a1a;
  --gg-color-primary-brown: #1a1a1a;
  --gg-color-secondary-brown: #767676;
  --gg-color-warm-brown: #767676;
  --gg-color-tan: #e5e5e5;
  --gg-color-sand: #fafafa;
  --gg-color-warm-paper: #fafafa;
  --gg-color-gold: #4ECDC4;
  --gg-color-light-gold: #4ECDC4;
  --gg-color-teal: #4ECDC4;
  --gg-color-light-teal: #4ECDC4;
  --gg-color-near-black: #1a1a1a;
  --gg-color-white: #ffffff;
  --gg-color-error: #c0392b;

  /* Clean Pro semantic tokens */
  --gl-primary: #1a1a1a;
  --gl-accent: #4ECDC4;
  --gl-bg: #ffffff;
  --gl-bg-alt: #fafafa;
  --gl-text: #1a1a1a;
  --gl-text-body: #4a4a4a;
  --gl-text-muted: #767676;
  --gl-border: #e5e5e5;

  /* font — Inter (3 weights) */
  --gg-font-display: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --gg-font-data: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --gg-font-editorial: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --gg-font-size-2xs: 10px;
  --gg-font-size-xs: 11px;
  --gg-font-size-sm: 14px;
  --gg-font-size-base: 16px;
  --gg-font-size-md: 18px;
  --gg-font-size-lg: 20px;
  --gg-font-size-xl: 24px;
  --gg-font-size-2xl: 28px;
  --gg-font-size-3xl: 40px;
  --gg-font-size-4xl: 48px;
  --gg-font-size-5xl: 56px;
  --gg-font-weight-regular: 400;
  --gg-font-weight-semibold: 600;
  --gg-font-weight-bold: 700;
  --gg-font-weight-black: 700;

  /* line-height */
  --gg-line-height-tight: 1.1;
  --gg-line-height-normal: 1.5;
  --gg-line-height-relaxed: 1.7;
  --gg-line-height-prose: 1.8;

  /* letter-spacing */
  --gg-letter-spacing-tight: -0.5px;
  --gg-letter-spacing-normal: 0;
  --gg-letter-spacing-wide: 1px;
  --gg-letter-spacing-wider: 1.5px;
  --gg-letter-spacing-ultra-wide: 2px;
  --gg-letter-spacing-extreme: 3px;
  --gg-letter-spacing-display: 4px;

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

  /* border — Clean Pro uses hairlines + 4px radius */
  --gg-border-width-subtle: 1px;
  --gg-border-width-standard: 1px;
  --gg-border-width-heavy: 2px;
  --gg-border-color-default: #e5e5e5;
  --gg-border-color-brand: #e5e5e5;
  --gg-border-color-secondary: #e5e5e5;
  --gg-border-color-gold: #4ECDC4;
  --gg-border-radius: 4px;

  /* animation */
  --gg-animation-duration-instant: 0ms;
  --gg-animation-duration-fast: 150ms;
  --gg-animation-duration-normal: 300ms;
  --gg-animation-duration-slow: 500ms;
  --gg-animation-easing-sharp: cubic-bezier(0.4, 0, 0.2, 1);
}

/* Composite tokens (derived) — Clean Pro */
:root {
  --gg-border-subtle: var(--gg-border-width-subtle) solid var(--gg-border-color-default);
  --gg-border-standard: var(--gg-border-width-standard) solid var(--gg-border-color-default);
  --gg-border-heavy: var(--gg-border-width-heavy) solid var(--gg-border-color-default);
  --gg-border-double: var(--gg-border-width-heavy) double var(--gg-border-color-default);
  --gg-border-gold: var(--gg-border-width-standard) solid var(--gg-border-color-gold);
  --gg-border-brand: var(--gg-border-width-standard) solid var(--gg-border-color-brand);
  --gg-border-secondary: var(--gg-border-width-standard) solid var(--gg-border-color-secondary);
  --gg-transition-hover: var(--gg-animation-duration-normal) var(--gg-animation-easing-sharp);
}

/* Clean Pro body overrides */
body {
  background: var(--gl-bg, #ffffff);
  color: var(--gl-text-body, #4a4a4a);
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-base);
  line-height: var(--gg-line-height-prose);
}"""


def get_clean_pro_font_face_css(font_path_prefix: str = "/course/assets/fonts") -> str:
    """Return @font-face declarations for Inter (Google Fonts variable font).

    Inter is loaded from Google Fonts CDN. No self-hosted woff2 needed.
    Returns a <link> import instead of @font-face blocks.
    """
    return """/* Inter — Variable Weight — Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');"""


def get_clean_pro_preload_hints() -> str:
    """Return preconnect hints for Google Fonts (Inter)."""
    return """<link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>"""


def get_clean_pro_overrides_css() -> str:
    """Return CSS overrides that make Røkt-themed components render in Clean Pro style.

    These override hardcoded color values in the course CSS that don't use
    CSS variables (e.g., inline background:#3a2e25 in hero sections).
    """
    return """/* ── Clean Pro Overrides ── */

/* Hero: white bg, dark text instead of dark bg, light text */
.gg-course-hero{background:#ffffff;color:#1a1a1a;border-bottom:1px solid #e5e5e5}
.gg-course-hero h1{color:#1a1a1a}
.gg-course-hero-subtitle{color:#4a4a4a}
.gg-course-hero-badge{border-color:#4ECDC4;color:#4ECDC4}
.gg-course-hero-price{color:#1a1a1a;font-weight:700}
.gg-course-hero-cta{background:#1a1a1a;color:#ffffff;border-radius:4px}
.gg-course-hero-cta:hover{background:#333333}

/* Lesson header: clean light instead of dark brown */
.gg-course-lesson-header{background:#fafafa;color:#1a1a1a;border-bottom:1px solid #e5e5e5}
.gg-course-lesson-header h1{color:#1a1a1a}
.gg-course-lesson-num{color:#4ECDC4}
.gg-course-lesson-breadcrumb{color:#767676}
.gg-course-lesson-breadcrumb a{color:#4a4a4a}

/* Gate: clean white */
.gg-course-gate{background:rgba(255,255,255,.97)}
.gg-course-gate-inner{background:#ffffff;border:1px solid #e5e5e5;border-radius:4px}
.gg-course-gate h2{color:#1a1a1a}
.gg-course-gate p{color:#4a4a4a}
.gg-course-gate-badge{border-color:#4ECDC4;color:#4ECDC4}
.gg-course-gate-cta{background:#1a1a1a;border-radius:4px}
.gg-course-gate-cta:hover{background:#333333}
.gg-course-gate-form button{background:#1a1a1a;border-radius:4px}
.gg-course-gate-form button:hover{background:#333333}
.gg-course-gate-form input[type=email]{border:1px solid #e5e5e5;border-radius:4px}

/* Progress sidebar: clean white */
.gg-course-progress{background:#ffffff;border:1px solid #e5e5e5;border-radius:4px}

/* Bottom CTA: clean */
.gg-course-bottom-cta{background:#fafafa;border-top:1px solid #e5e5e5}
.gg-course-bottom-cta h2{color:#1a1a1a}
.gg-course-bottom-cta p{color:#4a4a4a}

/* Streak badge: clean */
.gg-streak-badge{color:#1a1a1a}

/* Content body text */
.gg-course-lesson-body p{color:#4a4a4a;line-height:1.8}
.gg-course-lesson-body h1,.gg-course-lesson-body h2,.gg-course-lesson-body h3,.gg-course-lesson-body h4{color:#1a1a1a}

/* Callout info variant */
.gg-guide-callout--info{border-left:3px solid #767676;background:rgba(118,118,118,.04);padding:16px 20px}

/* Scenario label for sport psych context */
.gg-guide-scenario-label{content:'SCENARIO'}

/* Section labels: use accent for quiz/check labels */
.gg-guide-kc-label{color:#4ECDC4}

/* Module outline borders */
.gg-course-module-title{border-bottom:1px solid #e5e5e5;color:#1a1a1a}
.gg-course-learn li::before{color:#4ECDC4}

/* Nav buttons: dark, clean */
.gg-course-nav a{color:#1a1a1a;border:1px solid #e5e5e5;border-radius:4px}
.gg-course-nav a:hover{background:#1a1a1a;color:#ffffff;border-color:#1a1a1a}

/* Mark complete button: dark */
.gg-course-complete-btn{background:#1a1a1a;border-radius:4px}
.gg-course-complete-btn:hover{background:#333333}
.gg-course-complete-btn.gg-completed{background:#767676}

/* Level-up overlay: clean */
.gg-levelup-overlay{background:rgba(255,255,255,.92)}
.gg-levelup-card{background:#ffffff;border:1px solid #e5e5e5;border-radius:4px}
.gg-levelup-title{color:#1a1a1a}
.gg-levelup-badge{color:#4ECDC4}
.gg-levelup-name{color:#4ECDC4}
.gg-levelup-btn{background:#1a1a1a;border-radius:4px}
.gg-levelup-btn:hover{background:#333333}

/* Cards: clean */
.gg-course-card{background:#ffffff;border:1px solid #e5e5e5;border-radius:4px}
.gg-course-card:hover{border-color:#4ECDC4}
.gg-course-card-title{color:#1a1a1a}

/* PWA banner: clean */
.gg-pwa-banner{background:#1a1a1a}
"""
