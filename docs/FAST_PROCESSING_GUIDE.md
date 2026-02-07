# Fast Processing Guide (2-4 Days)

## Overview

Process all 388 races in 2-4 days instead of 78 days.

## Processing Speed Options

### Option 1: Every 6 Minutes (Recommended - ~1.6 Days)

**Workflow:** `fast-process-races.yml`
- Runs every 6 minutes
- Processes 1 race per run
- = 10 races/hour = 240 races/day
- **388 races ÷ 240/day = ~1.6 days**

**Schedule:**
```yaml
schedule:
  - cron: '*/6 * * * *'  # Every 6 minutes
```

### Option 2: Every 3 Minutes (Aggressive - ~0.8 Days)

**Workflow:** `aggressive-process.yml`
- Runs every 3 minutes
- Processes 1 race per run
- = 20 races/hour = 480 races/day
- **388 races ÷ 480/day = ~0.8 days**

**Warning:** May hit rate limits more often, but retry logic handles it.

**Schedule:**
```yaml
schedule:
  - cron: '*/3 * * * *'  # Every 3 minutes
```

### Option 3: Every 10 Minutes (Conservative - ~2.7 Days)

**Workflow:** `auto-process-races.yml` (modify schedule)
- Runs every 10 minutes
- Processes 1 race per run
- = 6 races/hour = 144 races/day
- **388 races ÷ 144/day = ~2.7 days**

**Schedule:**
```yaml
schedule:
  - cron: '*/10 * * * *'  # Every 10 minutes
```

## Recommended Setup

### For 2-3 Day Completion

Use `fast-process-races.yml`:
- Runs every 6 minutes
- Processes continuously
- Handles rate limits with retries
- Completes in ~1.6 days

### For 4 Day Completion

Use `auto-process-races.yml` with modified schedule:
- Change to `*/10 * * * *` (every 10 minutes)
- More conservative, fewer rate limit issues
- Completes in ~2.7 days

## How It Works

1. **Scheduled Trigger:** GitHub Actions triggers workflow every X minutes
2. **Get Next Race:** Finds first unprocessed race from database
3. **Process:** Research → Synthesize → Generate JSON
4. **Commit:** Saves results to repo
5. **Mark Complete:** Adds to `data/processed/completed.txt`
6. **Repeat:** Next scheduled run picks next race

## Rate Limit Handling

- **Sequential Processing:** Only 1 race at a time (max-parallel: 1)
- **Retry Logic:** Built into research.py (waits 60s, 120s, 180s)
- **Spacing:** 6-minute intervals = 10 races/hour (well under limits)

## Cost

**Total cost is the same regardless of speed:**
- 388 races × $0.50-1.00 = $194-388 total
- Faster = same cost, just completes sooner

## Monitoring

### Check Progress Anytime

```bash
# See completed races
cat data/processed/completed.txt | wc -l

# See remaining
python3 << 'EOF'
import json
with open('gravel_races_full_database.json') as f:
    db = json.load(f)
total = len(db.get('races', []))
with open('data/processed/completed.txt') as f:
    completed = len([l for l in f if l.strip()])
print(f"Progress: {completed}/{total} ({completed/total*100:.1f}%)")
EOF
```

### GitHub Actions Dashboard

View all runs:
https://github.com/wattgod/gravel-race-automation/actions

## Setup Steps

1. **Choose workflow:**
   - `fast-process-races.yml` for ~1.6 days
   - `aggressive-process.yml` for ~0.8 days (may hit more rate limits)

2. **Enable schedule:**
   - Already configured in workflow file
   - GitHub Actions will run automatically

3. **Let it run:**
   - No monitoring needed
   - Processes continuously
   - All results auto-committed

## Troubleshooting

### Rate Limit Errors

If you see frequent rate limit errors:
- Switch to `fast-process-races.yml` (6 min intervals)
- Or modify `aggressive-process.yml` to `*/6 * * * *`

### Workflow Not Running

- Check GitHub Actions is enabled
- Verify schedule syntax (cron format)
- Check if workflow file exists in `.github/workflows/`

### Stuck on Same Race

- Check workflow logs for errors
- Race may have failed - will retry on next scheduled run
- Or manually mark as complete if needed

## Timeline Examples

### Fast Process (6 min intervals)
- **Start:** Day 1, 00:00
- **End:** Day 2, ~14:00 (1.6 days)
- **Races/hour:** 10
- **Total time:** ~38 hours

### Aggressive (3 min intervals)
- **Start:** Day 1, 00:00
- **End:** Day 1, ~19:00 (0.8 days)
- **Races/hour:** 20
- **Total time:** ~19 hours

## Recommendation

**Use `fast-process-races.yml`:**
- ✅ Completes in ~1.6 days
- ✅ Less likely to hit rate limits
- ✅ More reliable
- ✅ Still very fast

The aggressive option is faster but may have more rate limit retries.

