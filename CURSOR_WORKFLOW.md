# Cursor Workflow for Batch Race Research

How to use Cursor to research and generate race profiles at scale.

## Prerequisites

1. Cursor with Sonnet model and web search enabled
2. Clone this repo: `git clone <gravel-race-automation>`
3. `pip install anthropic requests` (for adversarial review + RideWithGPS verification)

## Pipeline Overview

```
Stage 1: Web Research (Cursor + web search)  → research-dumps/{slug}-raw.md
Stage 2: Synthesis Brief (Cursor + Sonnet)   → briefs/{slug}-brief.md
Stage 3: JSON Generation (Cursor + Sonnet)   → race-data/{slug}.json
Stage 3.5: Adversarial Review (automated)    → CLEAN or fix prompt
Stage 4: Validation (automated)              → PASS or fix queue
```

**Stages 1-3: You run in Cursor.**
**Stages 3.5-4: Automated — run `python3 scripts/pilot_runner.py --race <slug>`**

---

## Stage 1: Web Research

### Option A: One race at a time

1. Open a Cursor chat with web search enabled
2. Paste the prompt from `prompts/{slug}-research.txt` (or use the template below)
3. Cursor will search the web, compile sources, write the research dump
4. Save output to `research-dumps/{slug}-raw.md`

### Stage 1 Prompt Template

```
Research the gravel race "{RACE NAME}" in {LOCATION}.

Find and include ALL of the following, with source URLs inline after each fact:

1. Official website — link to homepage, registration page, course map
2. Course details — distance, elevation gain, surface breakdown (% gravel/dirt/paved), named climbs/sections
3. Route data — search RideWithGPS (ridewithgps.com) for the race route. Note route ID, elevation profile, surface tags. Search DirtyFreehub (dirtyfreehub.com) for the area — they have curated surface breakdowns and local route knowledge
4. Registration — cost, lottery/first-come, sell-out history. Check BikeReg (bikereg.com) or RunSignUp for current/past registration pages
5. Historical results — search Athlinks (athlinks.com) for the race name. Pull finisher counts by year, median finish times, DNF rates, field size trends. This is the best source for hard numbers
6. Historical data — year founded, founder, participation trends, notable editions
7. Rider accounts — search Reddit (r/gravelcycling, r/cycling, r/bikepacking), forum posts (Slowtwitch, PackFodder), personal blogs. Quote real users with u/username attribution
8. Media coverage — search VeloNews, CyclingTips, Escape Collective, RidingGravel.com, In The Know Cycling, GravelCyclist.com for race coverage, previews, and reviews
9. Video/podcast — search YouTube for race recaps, course previews, and ride-alongs. Check podcast episodes: The Gravel Ride Podcast, TrainerRoad Podcast, EVOQ Bike. Race directors and pros often share specific details not found in written media
10. Strava — search Strava for race-related segments, note KOM times and segment names
11. Weather/climate — historical temps, wind, precipitation for race month. Use weather data sites
12. DNF/attrition data — dropout rates, common causes, cutoff times (cross-reference with Athlinks data)
13. Controversy or "black pill" — anything that went wrong, common complaints, honest negatives
14. Community vibe — post-race party, expo, volunteer culture, local town support
15. Lodging/travel — nearest airport, drive time, camping vs hotels, booking pressure

CRITICAL RULES:
- Every fact MUST have its source URL on the same line, e.g.: "The race started in 2015 (https://example.com/about)"
- Tag each source type: [Official], [Reddit], [VeloNews], [CyclingTips], [Strava], [RideWithGPS], [Athlinks], [DirtyFreehub], [Blog], [Forum], [YouTube], [Podcast], etc.
- Minimum 15 unique source URLs from at least 6 different domains
- Include direct quotes from riders with attribution
- No summarizing — include specific numbers, dates, dollar amounts, temperatures, finisher counts
- For historical results: include at least 3 years of data if available (field size, finish times, DNF%)

Save output to research-dumps/{slug}-raw.md
```

### Option B: Batch mode (20 races per session)

1. Generate prompts: `python3 scripts/batch_research.py --tier A --batch-size 20`
2. In Cursor, paste: "Research the following 20 races. For each, save a research dump to `research-dumps/{slug}-raw.md`. Here are the prompts:" then paste all 20 prompt files
3. This works because each prompt is self-contained with seed data

### Quality check after Stage 1

```bash
# Verify research dumps exist and aren't too short
for f in research-dumps/*-raw.md; do
    wc -w "$f" | awk '{if ($1 < 500) print "SHORT:", $2}'
done

# Run quality gates on research dumps
for f in research-dumps/*-raw.md; do
    python3 scripts/quality_gates.py --file "$f" --type research
done
```

---

## Stage 2: Synthesis Brief

Paste this prompt in Cursor with the research dump attached:

```
Read the research dump at research-dumps/{slug}-raw.md.

Synthesize into a brief at briefs/{slug}-brief.md with these sections:

## THE ANGLE
What makes this race unique? One sentence.

## RADAR SCORES (score 1-5, with one-line justification each)
| Variable | Score | Justification |
|----------|-------|---------------|
| Length | | |
| Technicality | | |
| Elevation | | |
| Climate | | |
| Altitude | | |
| Logistics | | |
| Adventure | | |
| Prestige | | |
| Race Quality | | |
| Experience | | |
| Community | | |
| Field Depth | | |
| Value | | |
| Expenses | | |

## TRAINING PLAN IMPLICATIONS
What must an athlete train for? 3-5 bullet points.

## THE BLACK PILL
The honest truth about what will go wrong. Real data, specific scenarios.

## KEY QUOTES
3-5 real rider quotes with u/username or source attribution.

## LOGISTICS SNAPSHOT
Airport, lodging, food, parking, packet pickup.

Rules:
- Every score must have a specific justification (not "it's challenging")
- Every claim must trace back to the research dump
- Carry forward ALL source URLs from the research dump — do not drop citations
- No marketing language. Blunt, direct, specific.
- Matti voice: "You" not "riders", honest not hedging
```

---

## Stage 3: JSON Generation

Paste this prompt in Cursor with the brief attached:

```
Read the brief at briefs/{slug}-brief.md.

Generate a canonical race JSON at race-data/{slug}.json matching this structure:

{
  "race": {
    "name": "FULL RACE NAME",
    "slug": "{slug}",
    "display_name": "Display Name",
    "tagline": "One punchy sentence.",
    "vitals": {
      "distance_mi": <number>,
      "elevation_ft": <number>,
      "location": "City, State/Country",
      "location_badge": "CITY, STATE",
      "date": "Month day-range annually",
      "date_specific": "2026: Month Day",
      "terrain_types": ["type1", "type2"],
      "field_size": "~N riders",
      "start_time": "Day HH:MM AM",
      "registration": "How to register. Cost: $X",
      "aid_stations": "Description of support",
      "cutoff_time": "X hours"
    },
    "climate": {
      "primary": "One-line climate summary",
      "description": "Detailed weather paragraph with specific temps and data",
      "challenges": ["challenge1", "challenge2"]
    },
    "terrain": {
      "primary": "One-line terrain summary",
      "surface": "Detailed surface description",
      "technical_rating": <1-5>,
      "features": ["named feature 1", "named feature 2"]
    },
    "gravel_god_rating": {
      "overall_score": <calculated from 14 vars>,
      "tier": <1|2|3>,
      "tier_label": "TIER X",
      "length": <1-5>, "technicality": <1-5>, "elevation": <1-5>,
      "climate": <1-5>, "altitude": <1-5>, "logistics": <1-5>,
      "adventure": <1-5>, "prestige": <1-5>, "race_quality": <1-5>,
      "experience": <1-5>, "community": <1-5>, "field_depth": <1-5>,
      "value": <1-5>, "expenses": <1-5>
    },
    "course_description": {
      "character": "Paragraph describing the course",
      "suffering_zones": [
        {"mile": <N>, "label": "Real Geographic Name", "desc": "What happens here"},
        ...
      ],
      "signature_challenge": "The one thing that defines this race"
    },
    "biased_opinion": {
      "verdict": "2-3 word verdict",
      "summary": "Paragraph of honest assessment",
      "strengths": ["strength1", "strength2", "strength3"],
      "weaknesses": ["weakness1", "weakness2", "weakness3"],
      "bottom_line": "One sentence"
    },
    "black_pill": {
      "title": "DRAMATIC TITLE",
      "reality": "The hard truth paragraph with specific data",
      "consequences": ["consequence1", "consequence2"],
      "expectation_reset": "What to actually prepare for"
    },
    "logistics": {
      "airport": "Code (Name) - Xhr drive",
      "lodging_strategy": "Paragraph",
      "food": "Paragraph",
      "packet_pickup": "When and where",
      "official_site": "https://..."
    },
    "history": {
      "founded": <year>,
      "founder": "Name",
      "origin_story": "Paragraph",
      "notable_moments": ["year: event", ...],
      "reputation": "One sentence"
    },
    "research_metadata": {
      "data_confidence": "researched",
      "validation_status": "pending",
      "sources": ["cursor_web_search"],
      "research_date": "2026-02-04"
    }
  }
}

Rules:
- overall_score = round((sum of 14 scores / 70) * 100)
- Tier 1: 85-100, Tier 2: 75-84, Tier 3: <75
- Prestige override: if prestige = 5, force Tier 1 regardless of score
- Every suffering zone MUST have a real geographic name
- No sentences over 30 words
- No filler phrases: "world-class", "amazing", "essential", "comprehensive"
- Matti voice: direct, blunt, specific
```

---

## Stages 3.5-4: Automated Validation

After generating the JSON, run:

```bash
# Full pipeline (includes adversarial LLM review — costs ~$0.009)
python3 scripts/pilot_runner.py --race {slug}

# Skip LLM review (free, faster)
python3 scripts/pilot_runner.py --race {slug} --skip-llm

# Run all 5 pilot races
python3 scripts/pilot_runner.py --pilot
```

If issues are found, the adversarial review generates a fix prompt. Paste that prompt back into Cursor to fix the JSON, then re-run validation.

**Fix loop:** Max 2 rounds. If still failing after 2 fixes, flag for manual review.

---

## Batch Execution Plan

| Session | Races | Method |
|---------|-------|--------|
| Pilot | 5 races (ground truth test) | Cursor + web search |
| Batch 1 | 20 Tier A races | `batch_research.py --tier A --batch-size 20` |
| Batch 2-7 | 20 each | Same, next 20 |
| Spot check | 3 random per batch | Manual URL verification |

After each batch:
```bash
# Validate all new profiles
for f in race-data/*-new.json; do
    python3 scripts/pilot_runner.py --race $(basename $f .json) --skip-llm
done

# Run adversarial review on those that passed pre-filter
python3 scripts/adversarial_review.py --dir race-data/
```
