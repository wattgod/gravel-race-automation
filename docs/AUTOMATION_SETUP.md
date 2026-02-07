# Fully Automated Setup (No Monitoring Required)

## Overview

Set up the system to run automatically without any manual intervention. No need to be at your computer or monitor progress.

## Option 1: Scheduled Daily Processing (Recommended)

### Setup

The `auto-process-races.yml` workflow runs automatically every day at 2 AM UTC.

**Default behavior:**
- Processes 5 Tier 2 races per day
- Runs sequentially (one at a time) to avoid rate limits
- Tracks progress automatically
- Commits results to repo

### Customize Schedule

Edit `.github/workflows/auto-process-races.yml`:

```yaml
schedule:
  - cron: '0 2 * * *'  # 2 AM UTC daily
```

**Cron examples:**
- `'0 2 * * *'` - Daily at 2 AM UTC
- `'0 */6 * * *'` - Every 6 hours
- `'0 2 * * 1'` - Every Monday at 2 AM UTC
- `'0 0,12 * * *'` - Twice daily (midnight and noon UTC)

### Manual Trigger

You can also trigger it manually:

```bash
gh workflow run auto-process-races.yml \
  -f tier=2 \
  -f limit=5
```

## Option 2: Process All Races Over Time

### Strategy

Process all 388 races automatically over several weeks:

1. **Week 1:** Tier 1 races (23 races, ~5/day = 5 days)
2. **Week 2-3:** Tier 2 races (65 races, ~5/day = 13 days)
3. **Week 4-5:** Tier 3 races (continue pattern)
4. **Week 6+:** Tier 4 races

### Setup Multiple Schedules

Create separate workflows for each tier:

```yaml
# .github/workflows/auto-process-tier1.yml
schedule:
  - cron: '0 2 * * 1-5'  # Weekdays only
```

## Option 3: Continuous Processing

### High-Volume Setup

If you want faster processing:

1. **Increase rate limit** - Contact Anthropic sales
2. **Run every 6 hours** - Process 4 batches per day
3. **Process 10 races per batch** - If rate limits allow

**Warning:** This requires higher rate limits from Anthropic.

## Monitoring (Optional)

### GitHub Actions Dashboard

View progress anytime:
- https://github.com/wattgod/gravel-race-automation/actions

### Email Notifications

GitHub will email you:
- When workflows fail
- When workflows complete (if configured)

### Slack/Discord Notifications

Add to workflow:

```yaml
- name: Notify Slack
  if: always()
  env:
    SLACK_WEBHOOK: ${{ secrets.SLACK_WEBHOOK }}
  run: |
    python scripts/notify.py \
      --race "${{ matrix.race_name }}" \
      --status "${{ job.status }}"
```

## Progress Tracking

### Check What's Done

```bash
# See completed races
cat data/processed/completed.txt

# Count completed
wc -l data/processed/completed.txt
```

### Check What's Remaining

The workflow automatically:
- Skips already processed races
- Processes unprocessed races only
- Tracks progress in `data/processed/completed.txt`

## Cost Estimate

**With scheduled processing (5 races/day):**
- 388 races ÷ 5/day = ~78 days
- Cost: ~$0.50-1.00 per race × 388 = $194-388 total
- Spread over 78 days = ~$2.50-5.00/day

**Faster processing (10 races/day):**
- 388 races ÷ 10/day = ~39 days
- Same total cost, just faster

## Troubleshooting

### Workflow Not Running

1. Check GitHub Actions is enabled
2. Verify schedule syntax (use https://crontab.guru)
3. Check if workflow file is in `.github/workflows/`

### Rate Limit Errors

- Workflow processes sequentially (max-parallel: 1)
- If still hitting limits, reduce `limit` to 3-4 races/day
- Or increase Anthropic rate limits

### No Races Processed

- Check if all races are already in `data/processed/completed.txt`
- Verify database file exists
- Check workflow logs for errors

## Next Steps

1. **Enable scheduled workflow:**
   - Already created: `auto-process-races.yml`
   - Runs daily at 2 AM UTC
   - Processes 5 Tier 2 races per day

2. **Customize if needed:**
   - Change schedule time
   - Change tier or limit
   - Add notifications

3. **Let it run:**
   - No monitoring required
   - Check back in a few days
   - All results committed to repo

## No Computer Required

Once set up:
- ✅ Runs automatically on schedule
- ✅ Processes races sequentially
- ✅ Commits results to GitHub
- ✅ Tracks progress automatically
- ✅ Handles failures gracefully

You can check progress anytime via GitHub web interface, but no active monitoring needed.

