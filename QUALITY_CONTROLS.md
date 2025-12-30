# Quality Controls & Validation

## Overview

This system includes multiple layers of validation to prevent sloppy output from reaching production.

## Validation Layers

### 1. Runtime Checks (In Scripts)

**`research.py`:**
- Minimum research length check (1000 chars)
- URL count warning (< 2 URLs)

**`synthesize.py`:**
- Minimum brief length check (500 chars)
- Required sections check (RADAR SCORES, TRAINING PLAN IMPLICATIONS, THE BLACK PILL)

**`generate_json.py`:**
- JSON syntax validation
- Required keys check (race, race.name)
- Empty field checks

### 2. Output Validation (`validate_output.py`)

Runs after all generation steps to catch quality issues:

**Research Quality:**
- Minimum length (2000 chars)
- URL count (3+ expected)
- Specific data points (mile markers, weather data)
- Forum data indicators

**Brief Format:**
- Required sections present
- Radar scores table complete
- Anti-pattern detection (marketing language)
- Mile markers present
- Quotes section populated
- Black Pill depth check

**JSON Structure:**
- Schema validation
- Required fields present
- Type checking
- Score range validation (1-5)
- Empty field detection

### 3. Regression Tests (`regression_test.py`)

Run before deploying changes:

- JSON schema loads correctly
- Voice guide loads
- Research prompt loads
- Database loads
- Scripts are executable
- Workflows exist
- Directory structure complete
- Python packages available

## Usage

### Validate Single Race Output

```bash
python scripts/validate_output.py --folder mid-south
```

**Strict mode (fails on warnings):**
```bash
python scripts/validate_output.py --folder mid-south --strict
```

### Run Regression Tests

```bash
python scripts/regression_test.py
```

Or via GitHub Actions:
- Pull requests automatically run regression tests
- Manual trigger: Actions → "Regression Tests"

## Quality Thresholds

### Research Dump
- **Minimum length:** 2000 characters
- **Minimum URLs:** 3 sources
- **Required:** Mile markers, weather data, forum insights

### Brief
- **Minimum length:** 500 characters
- **Required sections:** All 5 sections present
- **Radar scores:** All 7 variables scored 1-5
- **Black Pill:** Minimum 200 characters
- **Quotes:** Minimum 100 characters

### JSON
- **Valid JSON:** Must parse correctly
- **Required keys:** race, race.name, race.display_name, race.vitals
- **Score ranges:** All radar scores 1-5
- **No empty fields:** Critical fields must have content

## Failure Modes

### Research Fails
- **Symptom:** Research dump too short or no URLs
- **Action:** Re-run research, check API key, verify race name

### Brief Fails
- **Symptom:** Missing sections or too short
- **Action:** Check voice guide loaded, verify research quality, re-run synthesis

### JSON Fails
- **Symptom:** Invalid JSON or missing fields
- **Action:** Check brief format, verify schema, re-run generation

### Validation Fails
- **Symptom:** Output validation reports errors
- **Action:** Review errors, fix source data, re-run pipeline

## GitHub Actions Integration

### Automatic Validation

**`research-race.yml`:**
- Runs `validate_output.py` after JSON generation
- Uses `--strict` mode (fails on warnings)
- Prevents committing bad output

**`batch-process.yml`:**
- Runs `validate_output.py` after each race
- Continues on warnings (logs them)
- Fails only on errors

**`regression-tests.yml`:**
- Runs on pull requests
- Validates system integrity
- Prevents breaking changes

## Manual Quality Review

Even with automated validation, review:

1. **First race of each batch:** Spot-check quality
2. **Tier 1 races:** Highest visibility, manual review recommended
3. **Random sampling:** Review 10% of batch output
4. **User feedback:** Monitor for quality issues

## Anti-Patterns Detected

The system automatically flags:

- Marketing language ("amazing opportunity", "don't miss out")
- Generic content (no specific mile markers)
- Empty sections (quotes, Black Pill)
- Missing data (no weather info, no forum insights)

## Continuous Improvement

If validation catches issues:

1. **Document the pattern** in this file
2. **Add detection** to `validate_output.py`
3. **Update prompts** in `skills/` if needed
4. **Run regression tests** before deploying

## Cost of Quality

Validation adds ~30 seconds per race:
- Research quality check: ~5s
- Brief validation: ~10s
- JSON validation: ~5s
- Output validation: ~10s

**Worth it:** Prevents publishing bad content that requires manual cleanup.

