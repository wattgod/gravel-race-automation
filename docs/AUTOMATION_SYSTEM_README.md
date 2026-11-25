# Gravel Race Automation System

## Overview

Fully self-contained automation system that lives in your GitHub repo. No external platforms. Python scripts do the work, GitHub Actions triggers and orchestrates them.

## How It Works

```
Your GitHub Repo
├── .github/
│   └── workflows/
│       ├── research-race.yml      ← Trigger: manual or API dispatch
│       ├── batch-process.yml      ← Trigger: process list of races
│       └── update-existing.yml    ← Trigger: weekly refresh
├── scripts/
│   ├── research.py                ← Calls Claude for research
│   ├── validate.py                ← Fact-checks against source URLs
│   ├── synthesize.py              ← Creates brief in Matti voice
│   ├── generate_json.py           ← Outputs Elementor-ready JSON
│   ├── push_wordpress.py          ← Publishes to your site
│   └── notify.py                  ← Slack/Discord notification
├── skills/
│   ├── research_prompt.md         ← Research methodology
│   ├── voice_guide.md             ← Matti voice rules
│   └── json_schema.json           ← Elementor JSON structure
├── data/
│   ├── master_database.json       ← All 388 races (gravel_races_full_database.json)
│   └── processed/                 ← Tracking what's done
├── research-dumps/                ← Raw research outputs
├── briefs/                        ← Synthesized briefs
└── landing-pages/                 ← Final JSON for each race
```

## Setup

### 1. GitHub Secrets

Add these secrets to your GitHub repository:

**Required:**
- `ANTHROPIC_API_KEY` - Your Claude API key

**Optional:**
- `WP_URL` - WordPress site URL
- `WP_USER` - WordPress username
- `WP_APP_PASSWORD` - WordPress application password
- `SLACK_WEBHOOK` - Slack webhook URL for notifications

### 2. Install Dependencies

The workflows install dependencies automatically, but for local testing:

```bash
pip install anthropic requests python-frontmatter pyyaml
```

## Usage

### Process Single Race

**Via GitHub UI:**
1. Go to Actions → "Research Gravel Race"
2. Click "Run workflow"
3. Enter:
   - Race name: `Unbound 200`
   - Folder: `unbound-200`
   - Skip validation: `false` (default)

**Via API:**
```bash
curl -X POST \
  -H "Authorization: token YOUR_GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/dispatches \
  -d '{"event_type":"research-race","client_payload":{"race_name":"Mid South","folder":"mid-south"}}'
```

The run summary links to a review branch with the scanned research files.
The WordPress step creates a draft from the scanned landing-page output.

### Batch Process Races

**Via GitHub UI:**
1. Go to Actions → "Batch Process Races"
2. Click "Run workflow"
3. Select:
   - Tier: `1`, `2`, `3`, `4`, or `all`
   - Limit: `10` (or `0` for all)

**What it does:**
- Filters races by tier
- Skips already processed races
- Processes up to limit (or all)
- Runs 3 races in parallel
- Commits results automatically

### Weekly Refresh

Automatically runs every Monday at 2 AM UTC to refresh races with briefs older than 30 days.

## Workflow Steps

### 1. Research (`research.py`)
- Uses Claude with web search
- Searches Reddit, TrainerRoad, YouTube, news
- Extracts specific mile markers, weather data, DNF rates
- Outputs raw research dump

### 2. Validate (`validate.py`)
- Extracts top 10 factual claims
- Fetches source URLs
- Verifies claims against source content
- Calculates validation score (target: 60%+)

### 3. Synthesize (`synthesize.py`)
- Converts research dump to race brief
- Scores 7 radar variables (Logistics, Length, Technicality, Elevation, Climate, Altitude, Adventure)
- Identifies training plan implications
- Writes Black Pill section in Matti voice
- Outputs brief in markdown

### 4. Generate JSON (`generate_json.py`)
- Converts brief to Elementor-ready JSON
- Matches schema for WordPress publishing
- Ready for `push_pages.py` integration

### 5. Push WordPress (`push_wordpress.py`)
- Creates draft page in WordPress
- Sets SEO metadata
- Ready for Elementor editing

### 6. Notify (`notify.py`)
- Sends Slack notification when complete
- Optional step

## Output Files

### Research Dump
`research-dumps/{race-folder}-raw.md`
- Raw research with all sources
- Metadata header
- Ready for synthesis

### Race Brief
`briefs/{race-folder}-brief.md`
- Synthesized brief in Matti voice
- Radar scores
- Training implications
- Black Pill section

### Landing Page JSON
`landing-pages/{race-folder}.json`
- Elementor-ready JSON
- Matches WordPress schema
- Ready for publishing

## Cost Estimate

**For 388 races:**
- GitHub Actions: Free (2,000 min/month, ~5 min/race = within limit)
- Claude API: ~$0.50-1.00/race × 388 = $194-388
- **Total: $194-388 (one-time)**

**Ongoing:**
- Weekly refresh: ~$5-10/month
- New races: ~$0.50-1.00 each

## Local Testing

Test scripts locally before pushing:

```bash
# Set API key
export ANTHROPIC_API_KEY="your-key-here"

# Test research
python scripts/research.py --race "Mid South" --folder "mid-south"

# Test validation
python scripts/validate.py --input "research-dumps/mid-south-raw.md"

# Test synthesis
python scripts/synthesize.py \
  --input "research-dumps/mid-south-raw.md" \
  --output "briefs/mid-south-brief.md"

# Test JSON generation
python scripts/generate_json.py \
  --input "briefs/mid-south-brief.md" \
  --output "landing-pages/mid-south.json"
```

## Tracking Progress

The selectors read the historical list at `data/processed/completed.txt` and the
per-race markers in `data/processed/races/`. Scheduled results and their markers
enter main when the review PR merges.

## Troubleshooting

### Research fails
- Check ANTHROPIC_API_KEY is set
- Verify race name exists in database
- Check API rate limits

### Validation score low
- Research may need more sources
- Some claims may be unverifiable
- Consider manual review

### JSON generation fails
- Check brief format
- Verify schema matches
- Review error output

### WordPress push fails
- Verify credentials
- Check WordPress REST API enabled
- Verify application password format

## Next Steps

1. **Add GitHub Secrets:**
   - ANTHROPIC_API_KEY (required)
   - WP_URL, WP_USER, WP_APP_PASSWORD (optional)
   - SLACK_WEBHOOK (optional)

2. **Test with one race:**
   - Run "Research Gravel Race" workflow
   - Review output files
   - Verify quality

3. **Batch process:**
   - Start with Tier 1 races
   - Monitor progress
   - Review results

4. **Integrate with WordPress:**
   - Test push_wordpress.py
   - Verify page creation
   - Set up Elementor templates

## Files Created

✅ `.github/workflows/research-race.yml`
✅ `.github/workflows/batch-process.yml`
✅ `.github/workflows/update-existing.yml`
✅ `scripts/research.py`
✅ `scripts/validate.py`
✅ `scripts/synthesize.py`
✅ `scripts/generate_json.py`
✅ `scripts/push_wordpress.py`
✅ `scripts/notify.py`
✅ `skills/research_prompt.md`
✅ `skills/voice_guide.md`
✅ `skills/json_schema.json`

**System is ready to use!** 🚀

