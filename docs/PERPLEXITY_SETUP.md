# Perplexity API Setup

## Why Perplexity?

**Problem with Claude + web_search:**
- Research too short (800-1200 words)
- Missing URLs (0-7 found, needs 15+)
- Missing Reddit/YouTube sources
- Token limits restricting output

**Perplexity advantages:**
- Built for research (does 20-30 autonomous searches)
- Better at finding Reddit/YouTube sources
- Longer, more comprehensive output (2000-4000 words)
- Includes URLs naturally in responses
- `sonar-deep-research` model optimized for this

## Setup Steps

### 1. Get API Key

1. Go to: https://www.perplexity.ai/settings/api
2. Fill out API Group form:
   - **API Group name:** `Gravel God`
   - **Description:** `Gravel race research automation`
   - **Address Line 1:** [Your address]
   - **City:** [Your city]
   - **State:** [Your state]
   - **Zip:** [Your zip]
   - **Country:** United States
3. Click **Save**
4. Copy API key (starts with `pplx-`)

### 2. Add to GitHub Secrets

1. Go to: Repository → Settings → Secrets → Actions
2. Click **New secret**
3. Name: `PERPLEXITY_API_KEY`
4. Value: `pplx-xxxxx` (your API key)
5. Click **Add secret**

### 3. Test

```bash
# Via GitHub Actions:
GitHub → Actions → Research Gravel Race → Run workflow
  race_name: Mid South
  race_folder: mid-south
  research_engine: perplexity
```

## Cost Comparison

| Engine | Model | Cost per Race | Quality |
|--------|-------|---------------|---------|
| Claude | sonnet + web_search | ~$0.50-1.00 | Thin (800-1200 words) |
| Perplexity | sonar-deep-research | ~$0.40-1.30 | Comprehensive (2000-4000 words) |
| Perplexity | sonar-pro | ~$0.15-0.30 | Medium (1500-2500 words) |

**Recommendation:**
- **Tier 1-2 (88 races):** Use `sonar-deep-research` (~$0.40-1.30/race)
- **Tier 3-4 (300 races):** Use `sonar-pro` (~$0.15-0.30/race) or Claude

## Pipeline

```
Perplexity (research) → Claude (synthesis) → Claude (JSON) → WordPress
```

- **Perplexity:** Better at web research, finding sources, comprehensive dumps
- **Claude:** Better at synthesis, voice, formatting

## Expected Output

With Perplexity, research should have:
- ✅ 2000-4000 words (vs 800-1200 with Claude)
- ✅ 15-25 URLs (vs 0-7 with Claude)
- ✅ Reddit + YouTube sources (Perplexity finds them better)
- ✅ All required sections
- ✅ Specific quotes, mile markers, data

## Workflow Options

The workflow now supports both engines:

```yaml
research_engine:
  - perplexity  # Recommended for Tier 1-2
  - claude      # Fallback or Tier 3-4
```

Default is `perplexity` for better quality.

