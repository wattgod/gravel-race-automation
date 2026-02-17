# WordPress Performance Guide

## Current Asset Architecture

### Race Pages (`/race/{slug}/`)
- **1 external CSS** (`gg-styles.{hash}.css`) — shared across all race pages
- **2 external JS** (GA4 gtag + `gg-scripts.{hash}.js`) — minimal
- **~66-73KB HTML** — includes inline GA4 snippet
- No WP plugin bloat (served as static HTML via SiteGround)

### Prep Kits (`/race/{slug}/prep-kit/`)
- **0 external CSS** — all styles inlined (~24KB)
- **1 external JS** (GA4 only)
- **~70KB HTML**
- Self-contained, no WP dependency

### Homepage (`/`)
- **0 external CSS** — all styles inlined (~37KB)
- **2 external JS** (GA4 + Speed Optimizer combined)
- **~85KB HTML**
- Served via Code Snippets plugin (Code Snippet #11)

### Search Widget (`/gravel-races/`)
- **1 external CSS** (Speed Optimizer combined)
- **8 external JS** (GA4, jQuery, SG Cache, WP hooks/i18n, search widget, Speed Optimizer)
- **~188KB HTML** — includes heavy inline CSS (~129KB) and inline JS (~10KB)
- This is the heaviest WP-served page due to plugin overhead

### About (`/about/`)
- **1 external CSS** (`gg-styles.{hash}.css`)
- **3 external JS** (GA4, AB testing, gg-scripts)
- **~48KB HTML**

## Optimization Targets

### Priority 1: Search Widget Page
The `/gravel-races/` page is the heaviest at 188KB. The inline CSS (129KB) is large because it includes the full search widget styles. Consider:
1. Externalizing the search CSS to a hashed `.css` file (cacheable)
2. Lazy-loading non-critical CSS (e.g., map styles, calendar styles)

### Priority 2: Asset CleanUp Configuration
SiteGround Speed Optimizer already combines JS/CSS. However, AIOSEO may still load unnecessary CSS on pages where it's not needed.

**Steps to configure Asset CleanUp (WP Admin > Asset CleanUp):**
1. Go to each page type and disable AIOSEO CSS/JS where not needed
2. Focus on: race pages (static HTML, don't need AIOSEO), prep kits (same), homepage (same)
3. Only the blog index and WP-native pages need AIOSEO assets

### Priority 3: Image Optimization
Current race pages have 1 image (OG/hero). When race photos v2 pipeline runs:
- Use WebP format with JPEG fallback
- Lazy-load below-fold images (`loading="lazy"`)
- Set explicit width/height to prevent CLS

## How to Monitor

```bash
# Run page weight audit
python scripts/audit_page_weight.py

# Verbose mode — shows individual asset URLs
python scripts/audit_page_weight.py --verbose

# JSON output for CI integration
python scripts/audit_page_weight.py --json
```

## Thresholds

| Metric | Threshold | Current Status |
|--------|-----------|---------------|
| External CSS files | >15 per page | All pages well under (max 1) |
| External JS files | >10 per page | All pages well under (max 8) |
| HTML size | >500KB | All pages well under (max 188KB) |

## SiteGround Cache

Always purge SiteGround cache after any deploy:
```bash
python3 scripts/push_wordpress.py --purge-cache
```

The Speed Optimizer plugin handles:
- JS/CSS combining and minification
- Lazy image loading
- Browser caching headers
