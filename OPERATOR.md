# ENDURE Plan Engine — Operator Guide

## New Athlete (One Command)

```bash
python3 new_plan.py --id <request-id>
```

The request ID comes from the email subject (e.g. `tp-sbt-grvl-sarah-printz-mlju8jn9`).

This runs all 10 steps:
1. Pulls questionnaire from Supabase
2. Validates → profiles → classifies → schedules → templates → generates workouts
3. Builds HTML guide
4. Generates PDF
5. Deploys to GitHub Pages (live URL)
6. Emails athlete
7. Copies PDF + workouts to `~/Downloads/{Name} - {Race}/`

When it finishes, open `~/Downloads` and you're done.

## Review Before Sending

```bash
python3 new_plan.py --id <request-id> --draft
```

This skips PDF/deploy/email. Opens the guide in your browser so you can review it.

When you're happy, run the full pipeline:

```bash
python3 run_pipeline.py athletes/<slug>/intake.json
```

## Makefile Shortcuts

```bash
make draft      # Generate guide only (no PDF/deploy/email)
make deliver    # Full pipeline (PDF + deploy + email)
make ship       # Draft + validate + check-tp, then tells you to review
make test       # Run all tests
```

## What Gets Delivered

| File | Location |
|------|----------|
| PDF | `~/Downloads/{Name} - {Race}/{Name}_{Race}_Training_Guide.pdf` |
| ZWO workouts | `~/Downloads/{Name} - {Race}/workouts/*.zwo` |
| Live guide | `https://wattgod.github.io/gravel-race-automation/guides/{slug}/` |

## Troubleshooting

**"Playwright not installed"** — Run `pip install playwright && playwright install chromium`

**"Missing SUPABASE_URL"** — Create `.env` with `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`

**Wrong plan duration** — Never regenerate a guide just to change styling. PDF print CSS lives in `pipeline/print.css` and is injected by step 8 at render time.

## Media Radar Weekly Briefing

Set `ANTHROPIC_API_KEY` and `RESEND_API_KEY` in `.env`, then run:

```bash
make media-radar
python3 -m media_radar.run_weekly --dry-run
python3 -m media_radar.run_weekly --dry-run --smoke  # one live source
```

The job stores raw transcripts and its seen-ID ledger locally under `data/media-radar/` (both are gitignored), writes committed weekly digests and the append-only glossary there, and emails `matti@endurelabs.app` unless `--dry-run` is used. Race-database flags are suggestions for manual verification only; this job has no race-database write step.

Install the schedule deliberately with `crontab -e`; the program does not install it:

```cron
0 7 * * 1 cd /Users/mattirowe/endure-plan-engine && .venv/bin/python -m media_radar.run_weekly >> data/media-radar/media-radar.log 2>&1
```
