# Generate Race Photos

Generate AI race photos using the Gemini 2.5 Flash Image pipeline. See `docs/photo-strategy.md` for the full research behind prompt design.

## Photo Types

- **hero** — Lone rider dwarfed by epic landscape (16:9, 1200x675)
- **grit** — Low-angle close-in action, dust/gravel spraying (4:3, 1200x900)
- **pack** — Group of riders silhouetted at golden hour (16:9, 1200x675)

## Commands

```bash
# Single race (test)
python3 scripts/generate_race_photos.py --slug unbound-200

# Single photo type
python3 scripts/generate_race_photos.py --slug mid-south --type grit

# Dry run (print prompts, no API calls)
python3 scripts/generate_race_photos.py --slug badlands --dry-run

# All 328 races (984 photos, ~30-40 min, ~$38)
python3 scripts/generate_race_photos.py --all --concurrency 5

# Check progress
python3 scripts/generate_race_photos.py --status
```

## What It Does

1. Reads race JSON from `race-data/{slug}.json`
2. Builds 3 narrative prompts per race using location, terrain, climate, date
3. Calls Gemini 2.5 Flash Image API (`gemini-2.5-flash-image`)
4. Post-processes: converts to RGB, resizes to target dimensions, saves as JPEG (quality 85)
5. Writes `race_photos` array back into the race JSON
6. Skips races where all photos already exist (resume support)

## After Generation

```bash
# Regenerate race pages to include new photos
python3 wordpress/generate_neo_brutalist.py --all

# Deploy photos to server
python3 scripts/push_wordpress.py --sync-photos

# Deploy updated race pages
# (use your existing race page deploy process)
```

## Environment

Requires `GOOGLE_API_KEY`, `GEMINI_API_KEY`, or `GOOGLE_AI_API_KEY` in `.env`.

## Photo Strategy

Every photo must have a cyclist. Empty landscapes don't engage. The 3 types cover:
- **Aspiration** (hero) — "I want to ride there"
- **Authenticity** (grit) — "This is real suffering"
- **Community** (pack) — "We ride together"

See `docs/photo-strategy.md` for full research and prompt engineering guidelines.
