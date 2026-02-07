# Rate Limit Solution

## The Problem

Anthropic API has a **30,000 input tokens per minute** rate limit. When running 5 races in parallel, even with 30-second delays, they all hit the API within the same minute window, causing rate limit errors.

## Solutions

### Option 1: Run One at a Time (Recommended)

**Manual approach:**
1. Trigger one race
2. Wait for it to complete (5-7 minutes)
3. Then trigger the next one

**Command:**
```bash
gh workflow run research-race.yml \
  -f race_name="Barry-Roubaix" \
  -f race_folder="barry-roubaix" \
  -f skip_validation="true"
```

### Option 2: Use Batch Process (Built-in Rate Limiting)

The `batch-process.yml` workflow has `max-parallel: 1` which processes races one at a time:

```bash
gh workflow run batch-process.yml \
  -f tier="2" \
  -f limit="5"
```

This will:
- Process races sequentially
- Automatically handle delays
- Track progress in `data/processed/completed.txt`

### Option 3: Increase Rate Limits

Contact Anthropic sales to increase your rate limit:
- Current: 30,000 tokens/minute
- Request higher limit for batch processing

## Current Status

- ✅ Code optimized (max_tokens: 2000, condensed prompts)
- ✅ Retry logic in place
- ⚠️ Need to run sequentially or use batch-process workflow

## Recommendation

**Use `batch-process.yml` for multiple races:**
- Built-in sequential processing
- Automatic progress tracking
- Handles failures gracefully

**Use `research-race.yml` for single races:**
- Quick manual testing
- One-off research tasks

