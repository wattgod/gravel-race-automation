# Quality Gates System

## Overview

Comprehensive quality control system that catches AI slop before it hits production.

## What It Catches

### 1. Slop Phrases (50+ patterns)
- Generic filler ("in conclusion", "it's worth noting")
- AI enthusiasm ("amazing opportunity", "truly remarkable")
- Hedge words ("perhaps", "it seems like")
- Generic encouragement ("you've got this", "embrace the challenge")
- Filler transitions ("let's dive in", "without further ado")
- AI tell-tales ("delve into", "leverage", "utilize")

### 2. Voice Quality
- **Matti Voice Score**: Must have 40%+ of indicators
- Checks for: direct address, concrete language, honest/blunt markers
- Fails on: generic corporate speak, hedging, over-qualification

### 3. Specificity
- **Specificity Score**: Counts mile markers, quotes, URLs, usernames, years
- Minimum 30 points required
- Rewards: specific mile markers (5x), Reddit usernames (5x), quotes (4x)

### 4. Required Sections
- **Research**: OFFICIAL DATA, TERRAIN, WEATHER, REDDIT, SUFFERING ZONE, DNF, EQUIPMENT, LOGISTICS
- **Brief**: RADAR SCORES, all 7 variables, PRESTIGE, TRAINING, BLACK PILL

### 5. Source Citations
- Minimum 5 URLs required
- At least 1 Reddit source required
- Checks for: Reddit, TrainerRoad, YouTube, official sources

### 6. Length Sanity
- Research: 1500-5000 words
- Brief: 800-2500 words
- JSON: 500-3000 words

## Usage

### Manual Check

```bash
# Check research dump
python scripts/quality_gates.py \
  --file research-dumps/mid-south-raw.md \
  --type research \
  --strict

# Check brief
python scripts/quality_gates.py \
  --file briefs/mid-south-brief.md \
  --type brief \
  --strict
```

### In Scripts

Quality gates are automatically run in:
- `research.py` - After research generation
- `synthesize.py` - After brief generation

### In GitHub Actions

Quality gates run automatically:
- **research-race.yml**: Strict mode, fails workflow on slop
- **batch-process.yml**: Warns but continues (logs issues)

## Test Suite

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_quality_gates.py -v

# Run with coverage
pytest tests/ --cov=scripts/quality_gates
```

## Quality Thresholds

| Check | Research | Brief | JSON |
|-------|----------|-------|------|
| Slop Phrases | 0 allowed | 0 allowed | N/A |
| Voice Score | N/A | 40%+ | N/A |
| Specificity | 30+ points | 30+ points | N/A |
| Sections | All 8 | All 11 | N/A |
| Citations | 5+ URLs, 1+ Reddit | N/A | N/A |
| Length | 1500-5000 words | 800-2500 words | 500-3000 words |

## Failure Modes

### Critical Failures (Fail Workflow)
- Slop phrases detected
- Missing required sections
- Insufficient citations (research only)

### Warnings (Log but Continue)
- Low voice score
- Low specificity score
- Length outside range

## Golden Files

Reference outputs in `tests/golden/`:
- Known-good examples
- Used for regression testing
- Quality benchmarks

Add golden files when you have outputs that:
1. Pass all quality gates
2. Have been manually reviewed
3. Represent target quality

## Continuous Improvement

When quality gates catch issues:

1. **Document the pattern** - Add to slop phrases list
2. **Update thresholds** - Adjust if too strict/loose
3. **Add tests** - Ensure pattern is caught
4. **Update golden files** - New quality standard

## Examples

### Good Content (Passes)
```
Mile 80-95 is where Unbound breaks people. In 2023, temps hit 103°F.
u/graveldude said "Mile 130 is where dreams die."
DNF rate was 35%. https://reddit.com/r/gravelcycling/xyz
```

### Bad Content (Fails)
```
It's worth noting that this race offers an amazing opportunity for participants.
In conclusion, this is truly a remarkable experience that you should embrace.
Perhaps you might want to consider training more for this world-class event.
```

## Integration

Quality gates are integrated at multiple levels:

1. **Runtime** - Scripts check output as generated
2. **GitHub Actions** - Workflows validate before commit
3. **Tests** - Automated tests ensure gates work
4. **Manual** - Can run standalone for review

## Cost

Quality gates add ~5-10 seconds per race:
- Slop detection: ~1s
- Voice scoring: ~1s
- Specificity: ~1s
- Sections: ~1s
- Citations: ~1s

**Worth it:** Prevents publishing bad content that requires manual cleanup.

