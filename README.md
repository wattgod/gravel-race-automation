# Gravel Race Automation

328 gravel race profiles, page generators, search widget, tier scoring, and deploy pipeline for [gravelgodcycling.com](https://gravelgodcycling.com).

> Part of the [Gravel God Cycling](https://github.com/wattgod/gravel-god-cycling) ecosystem. See the meta repo for architecture docs, deploy runbook, lessons learned, and sprint log.

## What This Repo Does

- **Race profiles** (`race-data/*.json`) — 328 scored and tiered gravel race profiles
- **Page generator** (`wordpress/generate_neo_brutalist.py`) — generates static HTML race pages
- **Search widget** (`web/gravel-race-search.html` + `.js`) — embeddable race search for WordPress
- **Race index** (`web/race-index.json`) — generated JSON index for the search widget
- **OG images** (`scripts/generate_og_images.py`) — 1200x630 social sharing images
- **Methodology page** (`wordpress/generate_methodology.py`) — scoring methodology explainer
- **Homepage** (`wordpress/generate_homepage.py`) — site homepage generator
- **Guide media** (`scripts/generate_guide_media.py`) — training guide infographics and hero photos
- **Deploy** (`scripts/push_wordpress.py`) — tar+ssh deploy to SiteGround

## Quick Start

```bash
# Generate all race pages
python wordpress/generate_neo_brutalist.py --all

# Regenerate the search index
python scripts/generate_index.py --with-jsonld

# Deploy everything
python3 scripts/push_wordpress.py --sync-index --sync-widget --sync-og --sync-homepage --sync-guide
```

## Scoring

14 criteria scored 1-5. Overall score = `round((sum / 70) * 100)`.

| Tier | Threshold | Count |
|------|-----------|-------|
| T1 — Iconic | >= 80 | 25 (8%) |
| T2 — Premier | >= 60 | 73 (22%) |
| T3 — Notable | >= 45 | 154 (47%) |
| T4 — Emerging | < 45 | 76 (23%) |

## Related Repos

| Repo | What |
|------|------|
| [gravel-god-cycling](https://github.com/wattgod/gravel-god-cycling) | Project hub — architecture, deploy runbook, lessons learned |
| [gravel-god-brand](https://github.com/wattgod/gravel-god-brand) | Design system tokens and brand guide |
| [athlete-custom-training-plan-pipeline](https://github.com/wattgod/athlete-custom-training-plan-pipeline) | Coaching pipeline |
