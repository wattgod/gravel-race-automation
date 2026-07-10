---
name: data-pipeline-ops
description: Load when adding/editing race profiles, running enrichment, scraping, or regenerating the site from data.
---

# Data Pipeline Ops

## 1. Data flow, one line
`race-data/*.json` (757 profiles, source of truth) → `scripts/generate_index.py`
builds `web/race-index.json` (757-entry search/filter index — verified count
matches) → `wordpress/generate_neo_brutalist.py` renders race pages into
`output/` → `scripts/push_wordpress.py` tar+ssh deploys to SiteGround.

Regenerate the index after ANY profile edit, before regenerating pages — the
search/filter UI and JSON-LD read the index, not the profiles directly, and a
stale index silently ships old vitals/scores.
```
python scripts/generate_index.py --with-jsonld    # index + per-race JSON-LD
python scripts/generate_index.py --stats           # coverage check only
```
Race pages render from `race-data/*.json` (new format) via
`wordpress/generate_neo_brutalist.py <slug>` or `--all`. It also supports a
legacy `data/*-data.json` format — don't create new profiles in that format.
## 2. Profile JSON traps
CLAUDE.md's HTML Generation section covers the load-bearing ones:
`d['race']['gravel_god_rating']` path, `_parse_score()`, `_safe_json_for_script()`.
Read that first. Additional traps verified against a live profile
(`race-data/114-gravel-race.json`):
- **Two scoring blocks must stay in sync.** `gravel_god_rating` holds 14 bare
  integer scores + `overall_score`/`tier`. `biased_opinion_ratings` holds the
  SAME 14 criteria as `{score, explanation}` objects in Matti voice.
  `batch_enrich.py` writes `biased_opinion_ratings` only — it does not touch
  `gravel_god_rating`. A generator reading one and not the other renders a
  stale score next to a mismatched explanation.
- **Deeply optional nested blocks.** `youtube_data`, `tire_recommendations`,
  `citations`, `photos`, `history.notable_moments` are absent or `[]` on
  thinner profiles. Guard with `.get()` chains.
- **`rider_intel` can exist with every field empty.** `search_text` can be
  full of prose explaining that NO usable intel was extracted (transcript was
  music/foreign speech/fragmented). A non-empty `search_text` is not proof of
  real intel — check `key_challenges`/`terrain_notes` arrays are non-empty too.
- **`curated: false` videos stay in `videos[]`.** Only `curated: true` entries
  should render; the array holds accepted and rejected results side by side.
- **`history.founded` / `guide_variables.altitude_feet` are `null`-typed, not
  absent.** Same falsiness risk as CLAUDE.md #4 (`esc(0)`) — check `is None`,
  not truthiness, on any numeric vitals field here.
## 3. Adding a new race, end to end
1. **Research brief** (deep qualitative races) — root `skills/` dir (NOT
   `.claude/skills/`): `skills/RACE_RESEARCH_BRIEF_SKILL_UPDATED.md` defines
   source-diversity requirements and handoff format; `skills/research_prompt.md`,
   `skills/voice_guide.md` back it. Prompt/doc system for a human-or-Claude
   research pass, not an executable script.
2. **Cheap web-search pass** (bulk/thin profiles) —
   `python scripts/batch_research.py --auto N` → `research-dumps/{slug}-raw.md`
   via Kimi K2 web search.
3. **Enrich into profile JSON** — `python scripts/batch_enrich.py --slugs <slug>`
   reads the dump + existing profile, calls Claude for `biased_opinion_ratings`
   explanations, merges into `race-data/{slug}.json`. Use `--dry-run` first.
4. **Validate** — `python scripts/validate_race_data.py` cross-checks vitals
   against `known_races.py` / `athletes/config/races.json` in the sibling
   training-plan-pipeline repo, catches gain-vs-ASL copy-paste errors and
   implausible internal values. Also `python -m pytest tests/`.
5. **Regenerate index** — `python scripts/generate_index.py --with-jsonld`.
6. **Generate the page** — `python wordpress/generate_neo_brutalist.py <slug>`.
7. **Preflight + deploy** — section 6 below; don't deploy straight from step 6.
## 4. YouTube enrichment
Adds rider intel (challenges/terrain notes/tips/quotes from race recap
transcripts) and curated thumbnails to a profile's `youtube_data` block,
rendered as "RIDERS REPORT" callouts.
- `scripts/youtube_research.py --slug <slug>` — populates `videos[]`.
  `build_search_query()` is discipline-aware, reads `discipline` from the race
  JSON. [UNVERIFIED — session memory, Jul 2026: exact term mapping]
- `scripts/youtube_enrich.py --slug <slug>` (or `--auto N`) — curates real
  race content (rejects indoor-trainer platforms, slideshows, promo reels,
  sub-3min/over-2hr videos), sets `curated`/`display_order`.
- `scripts/youtube_extract_intel.py --slug <slug>` (or `--auto N`) — extracts
  structured `rider_intel` from curated-video transcripts.
- `scripts/youtube_thumbnail.py` — fetches/scores thumbnails
  (`maxresdefault.jpg` → `hqdefault.jpg` fallback), caches in
  `data/thumbnail-cache/` (30-day TTL, gitignored). [UNVERIFIED — session
  memory, Jul 2026: exact scoring formula]
- `scripts/youtube_validate.py` — schema/format check before shipping.
- Coverage: [UNVERIFIED — session memory figures are from Mar 2026, stale by
  ~4 months; grep `youtube_data` across `race-data/*.json` for current counts
  before quoting a percentage].
## 5. Scrapling scraping stack
`scripts/scrape_utils.py` (shared fetch/cache/extract) +
`scripts/scrape_official_sites.py` (CLI driver) + `scripts/fact_check_profiles.py`
(compares scraped facts vs profile, proposes fixes). Built for road-race
expansion batches; applies equally here.
- Tiered fetch: fast `Fetcher` first, `StealthyFetcher` (Cloudflare bypass) on
  failure. Use `str(response.html_content)`, not `response.text`.
- Cache: `data/scrape-cache/` (7-day TTL, gitignored, SHA-256 of URL). Extracts
  land in `data/scrape-extracts/{slug}.json` (committed).
- Rate limit: `scrape_official_sites.py --delay` defaults 3.0s between sites —
  don't lower against live race-org sites.
- **Do not run scrapers against live sites from this task.** Treat scraping as
  a scheduled/manual operation with its own review.
- Mar 2026 batch history / dead-URL fixes: [UNVERIFIED — session memory, Jul
  2026: stale ~4 months, check `road-race-automation` git log for current
  state before citing batch counts].
## 6. Bulk-change discipline
After any bulk data edit (batch enrich, batch scrape-fix, mass score
recompute), before deploy:
1. Veracity checker — `.claude/skills/scoring-and-veracity/SKILL.md`
   (`scripts/verify_race_rankings.py`, cross-checked against
   `docs/GRAVEL_GOD_SCORING_SYSTEM.md`).
2. Preflight — `.claude/skills/deploy-safely/SKILL.md`
   (`scripts/preflight_quality.py`, `scripts/preflight.py --deploy`).

Skipping either on a bulk edit is how a wrong distance/elevation figure or a
score/explanation mismatch (section 2) reaches production.
## When NOT to use this
- Training-plan generation (`run_pipeline.py`, `pipeline/`, `gates/`) — that's
  the ENDURE athlete intake→plan engine living in this same repo, unrelated to
  race-data profiles.
- WordPress deploy mechanics, cache purging, deploy checklist — use
  `.claude/skills/deploy-safely/SKILL.md`.
- Scoring rubric definitions, tier thresholds, criterion weighting — use
  `docs/GRAVEL_GOD_SCORING_SYSTEM.md` and
  `.claude/skills/scoring-and-veracity/SKILL.md`.
- Email/Mission Control sequence work — use the `email-sequences` skill.
- One-off single-field typo fixes — just edit the JSON, run `pytest tests/`
  and `validate_race_data.py`, no need for the full pipeline.
