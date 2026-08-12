# Runway-Aware Kits + Race Intel Feed — 2026-08-12

Spec author: Claude (Fable). Implementer: Codex. Review/merge: Claude → Matt.
Global rules: `~/.codex/AGENTS.md` (Acceptance Recap mandatory; never invent
schema). Anti-slop is the product: personalize ONLY from data the athlete
gave or facts that are objectively true; nothing simulated, nothing hyped.
Gravel God only in this spec — road/XC mirrors are explicit follow-ups, do
not build them here.

## WS-A — Runway-aware prep kits (client-side, no backend)

Kit pages (`wordpress/generate_prep_kit.py`, deployed to
`/race/{slug}/prep-kit/`) are static. The race date is already public at
`https://gravelgodcycling.com/wp-content/uploads/race-dates.json` (same
origin — fetchable from the page without CORS drama). Make the kit read
differently depending on how far out the race is.

1. Generator embeds a small inline script (no external deps, follow the
   repo's `_safe_json_for_script`-style escaping discipline) that fetches
   race-dates.json, computes weeks_out for this page's slug, and stamps
   `data-runway` on the kit root:
   - `build`     — > 16 weeks
   - `sharpen`   — 8–16 weeks
   - `triage`    — 10 days–8 weeks
   - `race-week` — ≤ 10 days
   - no date / fetch fails / date in past → NO attribute, page renders
     exactly as today (graceful degradation is the contract).
2. Visible, honest runway line near the top when known: "Unbound 200 is
   14 weeks out." Computed client-side; never rendered stale into HTML.
3. Per-mode emphasis via CSS keyed on `data-runway` (existing kit CSS
   conventions; no new colors): build → training guidance leads;
   sharpen → pacing/fueling lead; triage → logistics + fueling lead,
   training section collapsed with a one-line honest note ("8 weeks out,
   the plan you have is the plan — sharpen, don't rebuild"); race-week →
   checklist first, everything else collapsed (`<details>` is fine).
   Reordering may be visual (CSS order/collapse), not DOM rewriting.
4. Finisher/racer toggle — ONLY where the kit already renders pacing or
   fueling tables whose underlying data supports two honest readings
   (e.g., pace bands already computed from distance + typical finish
   spreads). If the data can't support a racer variant for a section,
   the toggle must not appear on that section. No invented splits.
   localStorage persistence (`gg_kit_mode`), default finisher.
5. Tests (pytest, alongside the existing generator tests): script embedded
   with correct slug; `data-runway` logic unit-tested by extracting the
   classification function into testable Python that mirrors the JS
   thresholds (single source of truth comment linking the two); toggle
   markup only present when variant data exists; `</script>` injection
   safety; page renders byte-identical to current output when JS disabled
   (progressive enhancement).

## WS-B — "Latest" race intel feed (deterministic, cited, no LLM)

Per-race changelog mined from git history of `race-data/{slug}.json`.
The database's own verified edits ARE the news — no generated prose.

1. `scripts/generate_race_intel.py` → `web/race-intel.json`
   (`{slug: [events]}`, each event `{date: "2026-08-10", type, text}`,
   newest first, max 5 per race, look back 18 months).
   Event classes (diff old→new JSON per commit; classify field changes):
   - `date_specific` changed → `date_confirmed`: "2027 edition: June 5 — date confirmed"
   - `tier` changed → `rerated`: "Re-rated: Tier 2 → Tier 1"
   - `overall_score` changed by ≥ 2 → `rescored`: "Score updated: 78 → 82"
   - `website` changed → `site_updated`: "Official site link updated"
   - file created → `added`: "Added to the database"
   Anything else: ignored in v1. Text is fully templated from the diff —
   zero free text.
2. **Bulk-commit guard (critical):** ignore any commit touching more than
   20 files under `race-data/` — migrations and normalization sweeps would
   otherwise stamp 400+ identical "rescored" events on one day and turn
   the feed into noise. Make the threshold a module constant with a
   comment. Also ignore merge commits' combined diffs (use first-parent).
3. Render: a compact "LATEST" sidebar section on race pages
   (`wordpress/generate_neo_brutalist.py`), existing brand tokens, max 3
   events shown, each with its month+year. If a race has no events in 18
   months, render nothing (an empty "Latest" box is worse than none).
   Date-confirmed events link to the race's `website` field when present
   (that's the verifiable source); rating changes need no link — the
   database is the source of its own ratings.
4. Regeneration: intel build step documented in the runbook alongside the
   other generators; deploy rides the existing `--sync-pages` path.
5. Tests: classifier as pure functions over (old_dict, new_dict) — no git
   needed in unit tests; bulk-guard test; render test (3-cap, no-events →
   no section, month formatting); one integration test running the miner
   against the real repo history for `unbound-200` asserting it returns
   ≤5 well-formed events without crashing.

## Out of scope (do not build)

Road/XC mirrors; any LLM chat surface; UGC race reports; weather layer;
fueling-calculator embed. These are sequenced follow-ups.

## Verification (before claiming done)

- `$VENV -m pytest` on touched test files; full-suite failure count must
  not exceed the baseline on your starting commit.
- `python3 scripts/generate_race_intel.py && python3 -c "import json;
  d=json.load(open('web/race-intel.json')); print(len(d))"` runs clean.
- Regenerate the unbound-200 kit + race page; include output paths in the
  recap for visual review.
- Do NOT push; do NOT deploy. Commit to your branch; Claude reviews,
  merges, and deploys via push_wordpress.py after visual review.
