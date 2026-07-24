# AEO Weekly Monitor — Spec (2026-07-23, sol-reviewed r2)

Approved direction (Matti, Jul 20): a weekly **monitoring** loop measuring
AEO outcomes across the three brands, surfaced as an advisory section in
Morning Intel. Deterministic collectors gather facts; the LLM narrates only.
Never auto-applies site changes.

## What changes

1. **New script `scripts/aeo_weekly.py`** — three deterministic collectors,
   one JSON artifact per run at `data/aeo/aeo-weekly-YYYY-MM-DD.json`.
2. **New module `scripts/aeo_agents.py`** — versioned UA taxonomy, single
   source of truth (research basis:
   `docs/research/aeo-monitor-ua-taxonomy.md`).
3. **New workflow `.github/workflows/aeo-weekly.yml`** — Mondays 10:30 UTC
   (before daily-intel at 12:00), `workflow_dispatch` enabled.
4. **`scripts/daily_intel.py` gains an AEO section.**
5. **New repo secrets** (via `gh secret set`, same practice as the existing
   `SSH_PRIVATE_KEY`/`GA4_CREDENTIALS_JSON`): `RL_SSH_HOST`, `RL_SSH_USER`,
   `RL_SSH_PORT`, `RL_SSH_PRIVATE_KEY`, `XC_SSH_HOST`, `XC_SSH_USER`,
   `XC_SSH_PORT`, `XC_SSH_PRIVATE_KEY`. Fork PRs and Dependabot never
   receive repo secrets; values are masked in logs. Blast radius note:
   anyone who can land workflow changes on the default branch can use
   them — same posture as the existing GG deploy key. Recommend (Matti,
   later, SiteTools UI): dedicated read-only keys + rotation; reusing the
   existing keys is acceptable to ship.

## Collector 1 — AI-referral sessions (GA4)

Reuses the `collect_ga4` client pattern (google-analytics-data,
`GA4_CREDENTIALS` env, `GG_GA4_PROPERTY_ID` / `RL_GA4_PROPERTY_ID`).
Per brand (gravelgod, roadie; **XC has no GA4 property — emit an explicit
`"not_configured"` state**):

- `runReport` dimension `sessionSource`, metric `sessions`, two windows:
  current 7 completed days and the prior 7. Fetch source rows (limit 250)
  and filter in Python with the versioned regex
  `(?i)(chatgpt|openai|perplexity|claude|anthropic|copilot|gemini|bard|poe\.com|you\.com|phind|kagi)`
  (do NOT rely on inline `(?i)` in an API StringFilter).
- Output per brand: `{source: sessions}` for both windows + the regex
  version used. New source values matching the regex appear automatically;
  genuinely new vendors still require a taxonomy update.

Framing (for the renderer and docs): sessions GA4 attributed to an
AI-associated source — a lower-bound click-through proxy, not proof the
domain appeared as a cited answer.

Quota: 4 small runReport calls/week is negligible against GA4 Data API
property quotas.

## Collector 2 — AI-crawler log analysis (all 3 brands)

Empirically verified 2026-07-23 on all three SiteGround accounts: daily
rotated logs at `~/www/<domain>/logs/<domain>-YYYY-MM-DD.gz`, standard
combined format. One day of GG traffic: 132 ChatGPT-User, 29 Claude-User
(mixed case), 5 OAI-SearchBot, 432 `/llms.txt` + `.md` fetches.

Implementation constraints (shared hosting is CPU/IO-metered):

- One SSH connection per brand; a single server-side shell script does ONE
  decompression pass per file (`gzip -cd` piped into a single `awk`) and
  emits ONLY aggregate TSV — no raw log lines, IPs, referrers, or query
  strings ever leave the server.
- Exactly the 7 completed days `D-1..D-7` by filename date; NEVER the
  current day (SiteGround archives completed days; current day is
  separate). Report `missing_log_dates` when a file is absent; 7-file max.
- Per-brand subprocess timeout 240–300s. Pre-check total compressed bytes
  (`du`); over a ceiling (default 500MB) → collector failure with the size
  reported, not a hung run.
- Loop files individually so counts retain per-day attribution.

Counted, per day per brand, keyed by taxonomy class
(`scripts/aeo_agents.py`, three buckets per vendor docs):

- **user_fetch** (retrieval for a live user request — the citation-adjacent
  signal): `ChatGPT-User`, `Claude-User`, `Perplexity-User`.
- **search_index**: `OAI-SearchBot`, `Claude-SearchBot`, `PerplexityBot`.
- **training_crawl**: `GPTBot`, `ClaudeBot`, `meta-externalagent`,
  `Amazonbot`, `Bytespider`, `cohere-ai`. (`Google-Extended` is a
  robots.txt token, not a UA — excluded from log matching; Gemini-related
  fetchers get added via collector 3 discovery once observed.)
- **Ingestibility hits**: requests to `/llms.txt` and paths ending `.md`,
  bucketed by HTTP status class (2xx vs 3xx/4xx/5xx) — a 404 is NOT a
  successful hit (XC had historical llms.txt 404s; don't mask a
  regression).
- **Top 10 user_fetch paths** (2xx only, query strings stripped
  server-side before anything is emitted — this artifact lives in a
  public repo).

## Collector 3 — spec-drift watch (deterministic, no web research)

Same server-side pass: UA strings matching
`(?i)(bot|crawler|spider|gpt|claude|llm)` NOT in the taxonomy's combined
allowlist AND not in the known non-AI suppression list (Googlebot,
Bingbot, DuckDuckBot, YandexBot, Applebot, common SEO crawlers — list in
aeo_agents.py) → reported as `unknown_agent_candidates` (UAs are
spoofable; these are candidates, not authenticated vendors), capped at 15
with per-UA counts, sample truncated to 120 chars. This is how new AI
agents get discovered and added to the taxonomy.

## Artifact contract

```json
{
  "schema_version": 1,
  "generated_at_utc": "...",
  "taxonomy_version": 1,
  "current_window": {"start": "...", "end": "..."},
  "prior_window": {"start": "...", "end": "..."},
  "brands": {
    "gravelgod": {
      "ga4": {"status": "ok|error", "...": "..."},
      "logs": {"status": "ok|error", "days": {"YYYY-MM-DD": {"...": "..."}},
               "missing_log_dates": [], "status_buckets": {}},
      "top_user_fetch_paths": []
    },
    "roadie": {}, "xcski": {"ga4": {"status": "not_configured"}}
  },
  "unknown_agent_candidates": []
}
```

- Filename date must equal `generated_at_utc` date; loader validates
  `schema_version`.
- Per-collector `status` — a partial artifact with errors is still
  written and committed BEFORE the workflow's final validation step turns
  the run red (never lose the most informative failure artifact).
- Deltas vs the prior artifact are computed at RENDER time by the intel
  side; first run → deltas are `null`, rendered "baseline — no prior
  artifact", never zero.

## Rendering contract (daily_intel.py)

- New `collect_aeo()` in `scripts/daily_intel.py`, registered as
  `"aeo": _safe(collect_aeo)` in the `collected` dict (the `_safe`
  registry around daily_intel.py:915). It reads the two newest
  `data/aeo/aeo-weekly-*.json` (current + prior for deltas).
- Three states: `missing` (no artifact ever — section absent, no BROKEN
  line, first-deploy friendly), `ok` (artifact ≤8 days old — section
  renders; note: that means it renders EVERY day of the week, which is
  intended — it's the week's AEO status), `stale`/`invalid` (>8 days or
  bad schema — no section, exactly one BROKEN line via the existing
  broken-collection path, e.g. "AEO weekly artifact stale (N days)").
  This wiring is explicit — `safe_render` alone does not do it.
- Section renders per brand: AI-referral sessions w/ week-over-week
  delta, user_fetch totals w/ delta, search_index + training_crawl
  totals, llms.txt/.md 2xx hits (and non-2xx count if >0), top 3 fetched
  paths, any unknown_agent_candidates. ALL arithmetic precomputed —
  the interpreter never does math.
- Reaches the LLM through both channels `interpret()` already receives:
  `json.dumps(collected)` (DATA) and the deterministic `render_report()`
  output; persisted in the daily snapshot afterward for audit/history.
- `collect_workflows()`'s hard-coded allowlist (daily_intel.py:363) gains
  `("wattgod/gravel-race-automation", "aeo-weekly.yml")` — dead-man
  coverage for the weekly job.

## Workflow (`aeo-weekly.yml`)

- `permissions: contents: write`; checkout; `pip install --quiet
  google-analytics-data`; write `GA4_CREDENTIALS_JSON` secret to
  `ga4-credentials.json` (same step as daily-intel.yml:27); write the 3
  SSH keys from secrets (`chmod 600`, no shell tracing).
- Run `scripts/aeo_weekly.py`; commit `data/aeo/` with the
  Thursday-veracity rebase/retry pattern (main moves fast; plain push is
  not acceptable); no-change-safe.
- Final step validates the artifact (schema + all collectors ok) and
  fails the run on error — AFTER the commit step, so partial artifacts
  survive.
- Rollout: after merge, dispatch once manually and verify artifact +
  next-morning intel section.

## Tests (pytest, `tests/test_aeo_weekly.py`)

- UA classification: every taxonomy UA → right bucket;
  case-insensitivity ("claude-user"); FooBot/1.0 → candidate; Googlebot →
  suppressed.
- Server-side awk output parsing from a fixture; llms.txt 404 is NOT a
  2xx hit; query strings never appear in the artifact; current-day file
  excluded by date math; missing-date reporting.
- Artifact schema round-trip + filename/date agreement; first-run deltas
  null → "baseline" rendering; stale artifact → exactly one BROKEN line;
  corrupt JSON → collect_aeo returns error state, never raises;
  render fixture snapshot test.

## Explicitly out of scope (phase 2, separate decision)

- Live-engine query spot-checks via the Mac browser farm — deferred:
  Mini unaudited, bot-detection fragility, and user_fetch UA counts
  already measure retrieval directly.
- XC GA4 (no property exists), Substack/YouTube surfaces, any
  auto-application of recommendations.

## Non-negotiables carried from the handoff

- Deterministic collectors, LLM narrates only.
- Advisory in Morning Intel, not a standalone report.
- No auto-applied site changes; recommendations gated on Matti.
