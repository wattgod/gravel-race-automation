# SEO Weekly Update-Candidates Loop — Spec (r2, sol findings folded)

**Goal**: every week, deterministically mine first-party GSC data for the 5
highest-leverage content updates on gravelgodcycling.com, surface them in
Morning Intel, and give the operator an in-session skill that drafts the
actual edits for gated deploy.

**Non-goals**: no third-party SEO data (OpenSEO/DataForSEO deferred — GSC-only
per Matti's decision 2026-07-29); **the collector makes no LLM calls** (the
weekly artifact and the intel section are fully deterministic; Morning Intel's
existing `interpret()` narrative may reference the section like any other —
that's pre-existing infra, unchanged); no automated publishing (governance: no
public content changes without Matti's yes). RL/XC extension deferred until
the GG loop proves out.

## Architecture (mirrors the shipped AEO weekly monitor)

```
GHA cron (Mon)                       Morning Intel (daily)      Interactive session
seo-weekly.yml ──runs──▶ scripts/seo_weekly.py                  /seo-updates skill
                          │  GSC Search Analytics API            │ reads latest artifact
                          │  (paginated pulls, two 28d windows)  │ inspects candidate pages
                          ▼                                      │ drafts 5 edits as diffs
                data/seo/seo-weekly-YYYY-MM-DD.json ──▶ collect_seo() section
                (validated BEFORE commit)                        ▼
                                                        Matti gates → deploy
                                                                 ▼
                                                data/seo/updates-log.jsonl
                                                (cooldown + outcome tracking)
```

## 1. Collector — `scripts/seo_weekly.py`

Auth: `GOOGLE_APPLICATION_CREDENTIALS` service-account JSON,
`webmasters.readonly` scope, property **exactly** `sc-domain:gravelgodcycling.com`
(the URL-prefix form 403s — see `reports/2026-07-29.md` §3; keep parity with
`gsc_tracker.py:24`).

**Data boundary probe**: GSC dates are Pacific-time and finalize late. Before
building windows, pull `dimensions: ["date"]` for the last 14 days and take
`boundary = max(date present)`. `current = [boundary-27, boundary]`,
`prior = [boundary-55, boundary-28]`. Artifact stores `data_boundary` and both
windows. If the probe returns no rows → hard fail.

**Pulls** (× both windows, 8 total + probe):
- `dimensions: []` — true overall totals (includes anonymized queries).
- `dimensions: ["query"]` — true per-query totals (content_gaps input; never
  derived by summing query+page rows, which double-counts multi-URL queries).
- `dimensions: ["query","page"]` — page attribution (striking_distance,
  ctr_underperformers).
- `dimensions: ["page"]` — page totals (decliners).

**Pagination**: every dimensioned pull loops `startRow += 25000` until a short
page. Artifact records per-pull `{dimensions, window, rows, requests}` under
`pulls`. Any API error or incomplete pull → exit 1, **no artifact written**
(no partials, no silent caps).

**Units**: CTR is stored as an API-native **fraction** (0.021) everywhere in
the artifact and all math; positions are floats. Rendering as % happens only
in the intel section. Schema documents this.

**URL normalization**: `urllib.parse.urlsplit`. Rows whose host is not
`gravelgodcycling.com`/`www.gravelgodcycling.com` or scheme is not https are
excluded from buckets and counted in `noncanonical` (per-host counts).
Canonical rows keep path only, trailing slash normalized to present (except
`/`). Query strings/fragments stripped.

**Floors** (drop early, keep artifact small): query+page rows need current
impressions ≥ 10; per-bucket floors below.

**Expected-CTR curve**: piecewise-linear interpolation over anchors
`{1: .28, 2: .15, 3: .10, 4: .075, 5: .06, 6: .045, 7: .035, 8: .03,
9: .025, 10: .02, 12: .02, 20: .01}`; clamp outside [1, 20] to the endpoint
values. `expected_ctr(position: float) -> float`, unit-tested at anchor,
midpoint, and out-of-range positions.

**Candidate buckets** (each entry carries: `page`, `query` (or null),
`clicks`, `impressions`, `ctr`, `position`, prior-window values when present,
`score`, `reason` — plain-English one-liner):

1. `striking_distance` — query+page rows, position 4–20, impressions ≥ 30.
   `target_pos = 3 if position <= 10 else 8`.
   `score = impressions * max(0, expected_ctr(target_pos) - ctr)`.
2. `ctr_underperformers` — query+page rows, position ≤ 12, impressions ≥ 50,
   `ctr < 0.4 * expected_ctr(position)`.
   `score = impressions * (expected_ctr(position) - ctr)`.
3. `decliners` — page-dim rows present in both windows, AND (clicks dropped
   ≥ 40% with prior clicks ≥ 10) OR (position worsened ≥ 3.0 with impressions
   ≥ 50 in **both** windows). `score = max(0, prior_clicks - clicks)`.
4. `content_gaps` — query-dim rows, impressions ≥ 50, whose best-ranking
   canonical page (from query+page rows) is `/` or `/gravel-race-search/` or
   absent. `score = max(0, impressions * expected_ctr(5) - clicks)`. Carries
   `recommended_target_path` (slug suggestion only; the skill decides).

All scores share one unit — estimated 28-day click upside — so cross-bucket
ranking is meaningful. `score_version: 1` stamped on the artifact; bump on
any formula change.

**Ranking → `top_candidates`**:
1. Merge buckets; dedupe by canonical page (content_gaps dedupe by query),
   keeping the max-score entry; attach `supporting_queries` (up to 5 other
   qualifying queries for that page, by impressions, with their metrics) and
   `combined_upside` (sum of that page's qualifying scores).
2. **Cooldown**: parse `data/seo/updates-log.jsonl` (missing file = empty);
   exclude pages with an `applied` entry newer than 21 days from
   top_candidates (they remain in buckets). Malformed log lines are skipped
   with a warning, never fatal.
3. Sort: score desc, impressions desc, page asc (deterministic tie-break).
   Take up to 5 (fewer is fine; `top_candidates` may be short or empty).
4. Each candidate: `rank`, `bucket`, `action` (one of `improve_ranking`,
   `rewrite_title_meta`, `refresh_content`, `create_or_link_content`),
   `target_path`, `source_hint` (routing per §4 table), `reason`, raw
   metrics, `supporting_queries`, `combined_upside`, `score`.

**Artifact** `data/seo/seo-weekly-YYYY-MM-DD.json` (date = data_boundary):
```json
{
  "schema_version": 1,
  "score_version": 1,
  "generated_at_utc": "...",
  "site": "sc-domain:gravelgodcycling.com",
  "data_boundary": "YYYY-MM-DD",
  "current_window": {"start": "...", "end": "..."},
  "prior_window": {"start": "...", "end": "..."},
  "overall": {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0,
               "prior": {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}},
  "pulls": [{"dimensions": ["query","page"], "window": "current",
              "rows": 0, "requests": 1}],
  "noncanonical": {"http://gravelgodcycling.com": 0},
  "cooldown_excluded": ["/race/..."],
  "buckets": {"striking_distance": [], "ctr_underperformers": [],
               "decliners": [], "content_gaps": []},
  "top_candidates": []
}
```

**CLI**: default = collect + write. `--validate-latest` validates newest
artifact (schema_version, required keys, window/boundary sanity,
generated_at not future, ctr values in [0,1]); `--require-all-ok` exits 1 on
any error. `--date` override for tests. `validate_artifact(artifact, path)`
importable (daily_intel reuses it).

## 2. Workflow — `.github/workflows/seo-weekly.yml`

- `schedule: cron "20 11 * * 1"` + `workflow_dispatch`;
  `permissions: contents: write`; timeout 15 min;
  `concurrency: {group: seo-weekly, cancel-in-progress: false}`.
- Steps: checkout → setup-python 3.11 → `pip install google-api-python-client
  google-auth` → write `$GSC_SERVICE_ACCOUNT_JSON` (existing secret, proven in
  daily-monitoring.yml) to `$RUNNER_TEMP/gsc-creds.json` → run collector →
  **`--validate-latest --require-all-ok` BEFORE commit** → commit `data/seo/`
  with the aeo rebase-retry ×3; on rebase conflict `git rebase --abort` and
  fail the step explicitly.

## 3. Morning Intel — `scripts/daily_intel.py`

- `collect_seo(today)` mirroring `collect_aeo`: newest
  `data/seo/seo-weekly-*.json`; states `missing` (silent, ok=True) / `ok` /
  `stale` (>8 days) / `invalid`; stale/invalid → one BROKEN line via
  `_collector_failures`. Validation via imported `validate_artifact`.
- Deterministic render: overall WoW line + up to 5 top_candidates
  (`#1 [striking_distance] /race/x — "query" pos 6.2, 480 impr, CTR 2.1% —
  <reason>`; CTR rendered as % here only) + `Run /seo-updates to draft
  these.` Empty top_candidates renders `no qualifying candidates this week`.
- Add `("wattgod/gravel-race-automation", "seo-weekly.yml")` to
  `collect_workflows` dead-man list. (Known limitation inherited from that
  list: it reads only the latest conclusion, not `updatedAt` age — deferred,
  same exposure as aeo.)

## 4. Drafting skill — `.claude/skills/seo-updates/SKILL.md`

Source-routing table (the load-bearing part — never hand-edit emitted HTML):

| target_path prefix | source of truth | apply via |
|---|---|---|
| `/race/<slug>/` | `race-data/<slug>.json` → `seo.title`/`seo.description` (+ profile fields for content) | regenerate page (generate_neo_brutalist path), preflight, deploy per deploy-safely |
| `/articles/<slug>/` | article source generator in repo | regenerate → SCP to `/articles/<slug>/` (NOT --sync-blog) |
| WP-native/Elementor pages (`/questionnaire/`, hubs) | `scripts/generate_meta_descriptions.py` for meta; Elementor widget for body | flag Elementor bodies for manual/JS-API edit — do not guess |
| anything else / content_gaps with no source | no source | propose new content or internal links; never invent a page silently |

Procedure (in-session, subscription Claude, zero API keys):
1. Read newest artifact; refuse if stale >8 days (tell operator to dispatch
   the workflow).
2. Per candidate: curl the live page, open its source per routing table,
   diagnose per bucket. **Freshness/factual edits require source
   verification** (official race site, registry) — GSC identifies the
   opportunity, it does not supply facts.
3. Draft the 5 edits as diffs (respect brand tokens, slop_rules, voice
   memories, race-page spine contract). Present with expected impact.
4. **Matti gates.** On yes: regenerate, `preflight_quality.py`, deploy,
   purge cache.
5. Append one JSONL line per applied update to `data/seo/updates-log.jsonl`:
   `{"date", "page", "query", "bucket", "action", "artifact",
   "baseline": {clicks, impressions, ctr, position}, "change_summary",
   "status": "applied"|"skipped"}`. The collector consumes this for cooldowns
   and for future before/after measurement.

## 5. Tests — `tests/test_seo_weekly.py` (+ intel tests)

No network. Cover: pagination loop (multi-page synthetic responses, per-pull
counts), CTR-as-fraction end-to-end (a 100× unit error must fail), expected
CTR at anchors/midpoints/out-of-range, each bucket's include/exclude edges,
decliner floors, dedupe keeps max score + attaches supporting_queries,
deterministic tie-break, cooldown exclusion + malformed log lines,
content_gaps duplicate targets, host/trailing-slash normalization,
empty/fewer-than-five top_candidates, artifact validation
(good/missing-key/future-date/bad-window/ctr-out-of-range), collect_seo
missing/ok/stale/invalid states, API error → no artifact file written.

## Rollout

1. PR from `seo-weekly` branch (worktree off origin/main; repo checkout is on
   `bikepacking-wsg`, untouched). Tests + sol-review fold documented.
2. Merge → `workflow_dispatch` first run → verify committed artifact
   validates; Morning Intel renders the section next morning.
3. First `/seo-updates` session = pilot; RL/XC cloning decision after 2–3
   weeks of GG signal.
