# GitHub Setup & Actions Testing

## Current Status

✅ All code is committed locally
✅ Ready to push to GitHub
❌ No GitHub remote configured yet

## Setup Steps

### 1. Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `gravel-race-automation` (or your preferred name)
3. Description: "Automated gravel race research and WordPress publishing system"
4. Visibility: Private (recommended) or Public
5. **Do NOT** initialize with README, .gitignore, or license (we already have these)
6. Click "Create repository"

### 2. Add Remote and Push

```bash
cd "/Users/mattirowe/Zwift Batcher"

# Add your GitHub remote (replace YOUR_USERNAME and REPO_NAME)
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# Or if using SSH:
# git remote add origin git@github.com:YOUR_USERNAME/REPO_NAME.git

# Push to GitHub
git branch -M main  # Ensure we're on main branch
git push -u origin main
```

### 3. Add GitHub Secrets

Go to your repository → Settings → Secrets and variables → Actions → New repository secret

**Required:**
- `ANTHROPIC_API_KEY`: `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`

**Optional (for WordPress publishing):**
- `WP_URL`: Your WordPress site URL
- `WP_USER`: WordPress username
- `WP_APP_PASSWORD`: WordPress application password
- `SLACK_WEBHOOK`: Slack webhook URL (for notifications)

### 4. Test via GitHub Actions

#### Option A: Manual Trigger (Recommended for first test)

1. Go to your repository on GitHub
2. Click "Actions" tab
3. Select "Research Gravel Race" workflow
4. Click "Run workflow"
5. Fill in:
   - **race_name**: `Mid South`
   - **race_folder**: `mid-south`
   - **skip_validation**: `false`
6. Click "Run workflow"

#### Option B: Via API

```bash
curl -X POST \
  -H "Authorization: token YOUR_GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/YOUR_USERNAME/REPO_NAME/actions/workflows/research-race.yml/dispatches \
  -d '{"ref":"main","inputs":{"race_name":"Mid South","race_folder":"mid-south","skip_validation":"false"}}'
```

## What to Watch For

### Successful Run

The workflow should:
1. ✅ Checkout code
2. ✅ Setup Python
3. ✅ Install dependencies
4. ✅ Run Research (takes 3-5 minutes)
5. ✅ Validate Research (optional, if not skipped)
6. ✅ Synthesize Brief
7. ✅ Generate JSON
8. ✅ Quality Gate - Research (should pass)
9. ✅ Quality Gate - Brief (should pass)
10. ✅ Validate Output Quality
11. ✅ Commit Results
12. ✅ Push to WordPress (if credentials set)
13. ✅ Notify Slack (if webhook set)

### Quality Gate Results

Check the "Quality Gate - Research" step output:

**Should see:**
```
✓ PASS | SLOP
✓ PASS | SPECIFICITY
✓ PASS | LENGTH
✓ PASS | SECTIONS
✓ PASS | CITATIONS
✓ PASS | SOURCE_DIVERSITY
✓ ALL QUALITY GATES PASSED
```

**If it fails:**
- Check which gate failed
- Review the research output in `research-dumps/mid-south-raw.md`
- Adjust prompts if needed

### Output Files

After successful run, check these files in the repo:
- `research-dumps/mid-south-raw.md` - Raw research dump
- `briefs/mid-south-brief.md` - Synthesized brief
- `landing-pages/mid-south.json` - Final JSON

## Troubleshooting

### Rate Limit Errors

If you see rate limit errors:
- Wait 2-3 minutes between test runs
- The script is optimized for rate limits (4000 max_tokens, condensed prompts)
- GitHub Actions may have different rate limits

### Quality Gate Failures

If quality gates fail:
1. Check the specific failure (slop, citations, source_diversity, etc.)
2. Review the research output
3. Adjust prompts in `scripts/research.py` if needed
4. Re-run workflow

### Missing Secrets

If workflow fails with "ANTHROPIC_API_KEY not set":
- Go to Settings → Secrets → Actions
- Add the secret
- Re-run workflow

## Next Steps After First Success

1. **Test batch processing:**
   - Actions → "Batch Process Races"
   - Tier: 1
   - Limit: 2 (start small)

2. **Review output quality:**
   - Check research dumps for source diversity
   - Verify briefs are in Matti voice
   - Confirm JSON structure

3. **Scale up:**
   - Process Tier 1 races (23 total)
   - Then Tier 2, etc.

## Repository Structure

Your repo should have:
```
.github/workflows/     ← 4 workflow files
scripts/               ← 7 Python scripts
skills/                ← Research & voice guides
tests/                 ← Test suite
data/                  ← Database & tracking
research-dumps/        ← Raw research (gitignored or committed)
briefs/                ← Synthesized briefs
landing-pages/         ← Final JSON files
```

