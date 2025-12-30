# Source Diversity Guide

## Overview

The research system now requires **comprehensive source diversity** to ensure high-quality, well-researched race briefs.

## Source Categories

### 1. Official Sources
- Race website
- Rider guide PDFs
- Course maps
- Official results pages

**Search queries:**
- `{race} official site`
- `{race} rider guide pdf`
- `{race} course map`

### 2. Forums (Minimum 2 different platforms)
- Reddit (r/gravelcycling, r/cycling, r/Velo)
- TrainerRoad forum
- Slowtwitch forum
- RidingGravel.com

**Quality signals:**
- Reddit: Prioritize threads with 20+ comments
- TrainerRoad: Look for threads with specific mile markers
- Slowtwitch: Ultra/endurance perspective

**Search queries:**
- `{race} site:reddit.com/r/gravelcycling`
- `{race} site:trainerroad.com/forum`
- `{race} site:forum.slowtwitch.com`
- `{race} site:ridinggravel.com`

### 3. Race Reports (Minimum 1)
- Team blogs: Rodeo Labs, NoFcks, Sage, ENVE
- Personal blogs
- First-person accounts preferred

**Search queries:**
- `{race} race report site:rodeo-labs.com`
- `{race} race report site:nofcksgivengravel.com`
- `{race} race report site:sage.bike`
- `{race} race recap 2024`

### 4. Media Coverage
- VeloNews
- CyclingTips
- Escape Collective
- Cycling Weekly
- BikeRadar

**Search queries:**
- `{race} site:velonews.com`
- `{race} site:cyclingtips.com`
- `{race} site:escapecollective.com`

### 5. Video (Minimum 1 with comments analyzed)
- YouTube race reports
- GoPro POV videos
- **Critical: Read the comments** - often more honest than video

**Quality signals:**
- Prioritize videos with 50+ comments

**Search queries:**
- `{race} race report youtube`
- `{race} POV gopro`
- `{race} 2024 youtube`

### 6. Data & Results
- Race results (Athlinks, RunSignup, BikeReg)
- Strava segments
- Timing data
- DNF rates
- Finish time distributions

**What to extract:**
- Total starters
- Total finishers
- DNF count and rate
- Winning time
- Median finish time
- Cutoff pressure

**Search queries:**
- `{race} results 2024`
- `{race} results athlinks`
- `{race} strava segment`
- `{race} DNF rate`

### 7. Weather History (Minimum 3 years)
- Historical conditions by year
- Actual data, not just anecdotes
- Temperature, precipitation, wind

**Search queries:**
- `{race} weather history`
- `{race} heat 2023`
- `{race} conditions 2022`

### 8. Gear & Equipment
- Tire pressure recommendations
- Tire recommendations
- Bike setup guides
- Gear lists

**Search queries:**
- `{race} tire pressure`
- `{race} tire recommendation`
- `{race} bike setup`

## Quality Requirements

### Source Count
- **Minimum:** 15 URLs
- **Target:** 15-25 URLs
- **Maximum:** No limit (more is better)

### Source Diversity
- **Minimum:** 4 different source categories
- **Required:** At least 2 forum sources (different platforms)
- **Required:** At least 1 race report blog
- **Required:** At least 1 video with comments analyzed
- **Required:** Weather data for last 3 years minimum

### Quality Gates

The system will **fail** if:
- Less than 15 URLs total
- Less than 4 different source categories
- Missing required source types (forums, race reports, video)

## Sources We Can't Easily Get

### Acknowledged Gaps

| Source | Why It's Hard | Workaround |
|--------|--------------|------------|
| Facebook groups | Private, auth required | Mention in research that FB groups exist but weren't accessed |
| Instagram | Rate limited, scraping blocked | Search for embedded IG posts in blogs |
| Strava segments | API requires auth | Search for "strava segment {race}" in forums where people share links |
| Podcasts | No transcripts | Search for podcast show notes, episode descriptions |
| Private race reports | Paywalled (some teams) | Stick to public blogs |

## Example: Good Research

```
# UNBOUND 200 - RAW RESEARCH DUMP

## OFFICIAL DATA
Source: https://unboundgravel.com
- 200 miles, 11,000 ft elevation
- Rider guide: https://unboundgravel.com/rider-guide.pdf

## FORUM SOURCES

### Reddit
- https://reddit.com/r/gravelcycling/comments/abc (127 comments)
- https://reddit.com/r/cycling/comments/def (89 comments)

### TrainerRoad
- https://trainerroad.com/forum/xyz (45 comments, specific mile markers)

### Slowtwitch
- https://forum.slowtwitch.com/abc (ultra perspective)

## RACE REPORTS
- https://rodeo-labs.com/unbound-200-race-report (first-person)
- https://nofcksgivengravel.com/unbound-recap (detailed)

## MEDIA
- https://velonews.com/unbound-2024
- https://cyclingtips.com/unbound-coverage

## VIDEO
- https://youtube.com/watch?v=xyz (2,340 comments analyzed)
- https://youtube.com/watch?v=abc (GoPro POV)

## DATA & RESULTS
- https://athlinks.com/unbound-200-2024 (DNF rate: 32%)
- https://strava.com/segments/12345 (popular route)

## WEATHER HISTORY
- 2024: 98°F, 5mph wind
- 2023: 103°F, 8mph wind
- 2022: 95°F, 12mph wind

## GEAR
- Tire pressure: 28-32 psi (forum consensus)
- Tire: 40mm minimum (multiple sources)

**Total URLs: 18**
**Source Categories: 7**
**Status: ✓ PASSES quality gates**
```

## Continuous Improvement

When you find new valuable sources:

1. **Add to search queries** in `research.py`
2. **Update source patterns** in `quality_gates.py`
3. **Document in this guide**
4. **Update tests** if needed

## Verification

Run quality gates to verify source diversity:

```bash
python scripts/quality_gates.py \
  --file research-dumps/{race}-raw.md \
  --type research \
  --strict
```

Check for:
- ✓ `source_diversity`: PASS (4+ categories)
- ✓ `citations`: PASS (15+ URLs)
- ✓ `specificity`: PASS (50+ points)

