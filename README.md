# Gravel Race Automation

328 gravel race profiles, page generators, search widget, prep kits, blog previews, and deploy pipeline for [gravelgodcycling.com](https://gravelgodcycling.com).

> Part of the [Gravel God Cycling](https://github.com/wattgod/gravel-god-cycling) ecosystem. See the meta repo for architecture docs, deploy runbook, lessons learned, and sprint log.

## What This Repo Does

### Generators

- **Race pages** (`wordpress/generate_neo_brutalist.py`) — 328 static HTML race profiles with JSON-LD, citations, photo gallery
- **Prep kits** (`wordpress/generate_prep_kit.py`) — 328 race-specific 12-week training timelines + race-day checklists
- **Blog previews** (`wordpress/generate_blog_preview.py`) — template-based race preview articles for registration windows
- **Search widget** (`web/gravel-race-search.html` + `.js`) — embeddable race search with compare, favorites, pagination
- **Homepage** (`wordpress/generate_homepage.py`) — site homepage generator
- **Methodology** (`wordpress/generate_methodology.py`) — scoring methodology explainer
- **OG images** (`scripts/generate_og_images.py`) — 1200x630 social sharing images
- **Guide media** (`scripts/generate_guide_media.py`) — training guide infographics and hero photos

### Data & Scripts

- **Race profiles** (`race-data/*.json`) — 328 scored and tiered gravel race profiles
- **Race index** (`web/race-index.json`) — generated JSON index for the search widget
- **Race lookup** (`scripts/race_lookup.py`) — Athlete OS integration module with fuzzy matching
- **Data freshness** (`scripts/audit_date_freshness.py`) — stale dates, missing fields, content gaps audit
- **Color audit** (`scripts/audit_colors.py`) — WCAG AA contrast, banned colors, token sync
- **Citations** (`scripts/extract_citations.py`) — URL extraction, relevance filtering, dedup
- **Deploy** (`scripts/push_wordpress.py`) — tar+ssh deploy to SiteGround

## Quick Start

```bash
# Generate all race pages
python wordpress/generate_neo_brutalist.py --all

# Regenerate the search index
python scripts/generate_index.py --with-jsonld

# Deploy everything
python3 scripts/push_wordpress.py --deploy-all --purge-cache

# Or deploy individual components
python3 scripts/push_wordpress.py --sync-pages --sync-widget --sync-index --purge-cache
```

## Search Widget Features

- **View modes**: Tier-based sections (T1-T4) and match mode (flat sorted list)
- **Filters**: Tier, distance, region, terrain, month, discipline, has_profile
- **Compare**: Side-by-side comparison of 2-4 races with radar SVG, 14 score dimensions
- **Favorites**: localStorage heart icons, favorites filter toggle (`?favs=1`)
- **Pagination**: Match mode at 20/page with load-more and smooth scroll (`?page=N`)
- **URL state**: All selections persist in URL params for shareable links

## Deploy Targets

| Flag | What |
|------|------|
| `--sync-pages` | Race pages (328 HTML + shared assets) |
| `--sync-prep-kits` | Prep kit pages (328 HTML) |
| `--sync-widget` | Search widget HTML + JS |
| `--sync-index` | Race index JSON |
| `--sync-og` | OG images (328 JPEGs) |
| `--sync-homepage` | Homepage HTML |
| `--sync-guide` | Guide media (48 WebP) |
| `--sync-photos` | Race photos (curated) |
| `--sync-redirects` | .htaccess redirect rules (33) |
| `--sync-noindex` | Noindex mu-plugin |
| `--sync-sitemap` | Sitemap index + race sitemap |
| `--purge-cache` | SiteGround cache purge |
| `--deploy-content` | Pages + index + widget + cache |
| `--deploy-all` | Everything above |

## Quality Gates

| Check | Command | Count |
|-------|---------|-------|
| Unit tests | `python3 -m pytest tests/` | 731 passing, 1 skipped |
| Deploy validation | `python scripts/validate_deploy.py` | 58 checks |
| Color audit | `python scripts/audit_colors.py` | WCAG AA verified |
| Citation validation | `python scripts/validate_citations.py` | 328 races |
| Redirect validation | `python scripts/validate_redirects.py` | 33 rules |
| Data freshness | `python scripts/audit_date_freshness.py` | 328 races |

## Scoring

14 criteria scored 1-5. Overall score = `round((sum / 70) * 100)`.

| Tier | Threshold | Count |
|------|-----------|-------|
| T1 — Iconic | >= 80 | 25 (8%) |
| T2 — Premier | >= 60 | 73 (22%) |
| T3 — Notable | >= 45 | 154 (47%) |
| T4 — Emerging | < 45 | 76 (23%) |

Prestige overrides: p5 + score >= 75 → T1, p5 + score < 75 → T2 cap, p4 = 1-tier promotion (not into T1).

## Related Repos

| Repo | What |
|------|------|
| [gravel-god-cycling](https://github.com/wattgod/gravel-god-cycling) | Project hub — architecture, deploy runbook, lessons learned, sprint log |
| [gravel-god-brand](https://github.com/wattgod/gravel-god-brand) | Design system tokens and brand guide |
| [athlete-custom-training-plan-pipeline](https://github.com/wattgod/athlete-custom-training-plan-pipeline) | Coaching pipeline (uses `race_lookup.py` for race enrichment) |
