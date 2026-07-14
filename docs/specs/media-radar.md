# Media Radar — Weekly Gravel Culture Briefing

**Status:** dispatch-ready · **Owner:** Gravel God (endure-plan-engine) · **Author:** Matt via Claude

## Goal
A weekly job that ingests transcripts from Bonk Bros and other gravel/endurance media,
mines them with the Claude API, and emails Matt (matti@endurelabs.app) a briefing that:
1. **Informs** — what the gravel scene is talking about this week.
2. **Pitches** — 3–5 concrete Gravel God article angles drawn from the chatter.
3. **Flags** — possible race-DB updates as *human-gated suggestions only*.

Plus an append-only **glossary** of new/emerging terms that powers a periodic
"bonk bros sanity check" — a soft cultural drift detector, not a CI gate.

## Hard rules (do not violate)
- **NEVER auto-write to the race DB** (`gravel_races_database.json`, `data/master_database.json`,
  or any `gravel_races_*.csv`). Race-DB items appear in the briefing as *flagged suggestions* only.
  A human approves and edits. The cron must have no write path to those files.
- **Do not republish transcript text verbatim** anywhere public. Transcripts are mined, not reprinted.
  Raw transcripts are stored locally and **gitignored** (copyright + repo bloat). Only the
  digest + glossary are committed.
- **No swallowed errors.** If a source fails to fetch, log it loudly (WARN with source id + reason)
  and continue; the digest must show a "sources that failed" section. A run where *all* sources
  fail should exit non-zero.
- Secrets come from `.env` / environment (`ANTHROPIC_API_KEY`, existing SMTP/email vars). Never hardcode.
- Reliability > features. No feature flags. Ship the small thing that works.

## Layout
```
media_radar/
  __init__.py
  sources.yaml          # editable source list (see below)
  known_entities.yaml   # riders + race names for transcript name-normalization
  ingest.py             # youtube-transcript-api + podcast RSS (feedparser); last-7-days only
  store.py              # persist raw transcripts + a seen-ids ledger (dedup)
  mine.py               # single Claude API pass -> structured digest JSON
  digest.py             # render weekly/YYYY-WW.md from the mined JSON
  glossary.py           # append-only new-terms glossary (data/media-radar/glossary.md)
  deliver.py            # email the briefing (reuse existing email path — see step_10_deliver.py)
  run_weekly.py         # orchestrator + CLI entrypoint (the cron target). Supports --dry-run.
tests/
  test_media_radar.py   # unit tests with all network mocked
data/media-radar/        # created at runtime
  transcripts/           # gitignored
  weekly/                # committed digests: YYYY-WW.md
  seen_ids.json          # gitignored dedup ledger
  glossary.md            # committed
```

## Ingest
- **YouTube:** use `youtube-transcript-api` (free, no key) for channels/videos with captions.
  Resolve recent uploads via each channel's uploads RSS feed
  (`https://www.youtube.com/feeds/videos.xml?channel_id=...`) — no YouTube Data API key needed.
- **Podcasts:** `feedparser` on RSS; if an episode has a transcript link/enclosure, use it.
  Do **not** add Whisper transcription in this MVP — skip audio-only-no-caption items and log them.
- Window: only items published in the last 7 days. Dedup via `seen_ids.json` (video id / episode guid).
- Normalize mangled caption text (rider/race names) against `known_entities.yaml` before mining.

## Starter sources (put in sources.yaml, easy to edit)
- Bonk Bros (YouTube channel + podcast RSS) — primary signal
- The Gravel Ride Podcast (Craig Dalton)
- Escape Collective / Groadio
- Adventure Stache (Payson McElveen)
Leave clear comments so Matt can add/remove sources without touching code.

## Mine (Claude API)
One weekly call. Use `claude-sonnet-5` for cost (opus if quality demands). Input: the week's
normalized transcripts (chunk if needed). Force structured JSON output:
```
{
  "tldr": "<= 200 words on the week's gravel conversation",
  "top_topics": [{ "topic": "...", "why_it_matters": "...", "sources": ["..."] }],
  "new_terms": [{ "term": "...", "meaning": "...", "first_seen_source": "..." }],
  "article_angles": [{ "headline": "...", "angle": "...", "hook": "..." }],   // 3–5
  "race_db_flags": [{ "race": "...", "claim": "...", "source": "...", "confidence": "low|med|high" }],
  "failed_sources": [{ "source": "...", "reason": "..." }]
}
```
- `article_angles` should sound like Gravel God editorial fuel, not generic SEO.
- `race_db_flags` are suggestions only. Emphasize verify-before-trust; caption hearsay is unreliable.

## Digest + deliver
- `digest.py` renders `weekly/YYYY-WW.md`: TL;DR → Top Topics → New Terms → Pitched Angles →
  Race-DB items to verify (clearly labeled "SUGGESTIONS — verify manually") → Sources that failed.
- `glossary.py` appends genuinely new terms (dedup against existing glossary) to `glossary.md`.
- `deliver.py` emails the rendered digest to matti@endurelabs.app. **Reuse the existing email
  mechanism** in `pipeline/step_10_deliver.py` (same SMTP creds/pattern) rather than inventing a new one.

## Entry point + cron
- `run_weekly.py` orchestrates: ingest → store → mine → digest → glossary → deliver.
  `--dry-run` does everything except send email and writes the digest to stdout + file.
- Add a `Makefile` target `media-radar` that runs `python -m media_radar.run_weekly`.
- Do **not** install a crontab. Instead print the exact weekly cron line at the end of the run
  and add it to `OPERATOR.md` so Matt installs it deliberately.

## Tests
- `test_media_radar.py`: unit tests with **all network + Claude calls mocked** — ingest windowing,
  dedup ledger, name normalization, digest rendering, glossary dedup, and the "all sources failed
  → non-zero exit" path. No live network in tests.
- Provide `python -m media_radar.run_weekly --dry-run --smoke` that hits *one* real source live for
  a manual sanity check (not run in the test suite).

## Deliverables
- Working module + passing `pytest tests/test_media_radar.py`.
- `requirements.txt` updated (`youtube-transcript-api`, `feedparser`, and whatever else).
- `.gitignore` updated for transcripts + seen_ids ledger.
- A short section appended to `OPERATOR.md` documenting how to run it + the cron line.
- Work on a branch `feat/media-radar`; commit; do NOT push (Matt/Claude reviews and merges).
