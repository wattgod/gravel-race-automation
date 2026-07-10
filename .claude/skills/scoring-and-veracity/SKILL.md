---
name: scoring-and-veracity
description: Load when touching race scores, ratings, rankings, testimonials, or any trust-bearing editorial claim.
---

# Scoring and Veracity

## 1. Scoring changes are trust-bearing, not cosmetic

The entire value of this database is honest-critic credibility — see
`gravel-god-cycling/NORTHSTAR.md`, "The anti-shill operating principle
(RottenTomatoes mechanic)": never claim independence, demonstrate it via
public methodology and brutal scores. Lab Score (critic) and Rider Score
(audience) are deliberately separate — that split is the product.

The scoring bible is `docs/GRAVEL_GOD_SCORING_SYSTEM.md`. Read it before
touching any score. Do not restate its rubric here — reference sections:
- Tier thresholds and Prestige Override: "Tier System" section
- The 14 base dimensions (7 Course Profile + 7 Editorial) + Cultural Impact
  bonus dimension, denominator-70 math: "Overview" / "Overall Score (0-100+)"
  sections
- JSON field structure: "Complete JSON Structure" section
- "Agent Instructions" section: explicit DO NOT list (don't invent a scoring
  system, don't skip explanations, don't skip tier assignment)

Any change to a race's score or tier needs a defensible written reason
recorded in that race's `explanation` field in `race-data/{slug}.json` — not
vibes, not a re-vibe from a different session. If you can't write the
one-to-two-sentence rubric-grounded reason, you don't have grounds to change
the number.

## 2. The rankings veracity checker

`scripts/verify_race_rankings.py`, run by `.github/workflows/rankings-veracity.yml`
(Thursdays 14:00 UTC, sibling of the Tuesday `weekly-fact-refresh` which owns
dates/status via official-site scraping — this one owns ratings vitals).

Mechanism: one Haiku 4.5 call per race with server-side web search
(`web_search_20250305` — Haiku cannot use the newer `_20260209` variant)
verifies the objective vitals behind the rating: distance, elevation gain,
field size, purse, cost, alive/dead. Cost ~$0.04/race, 25 races/run,
rotating oldest-first via `data/verification/verify_state.json`. A full
757-race sweep takes ~30 weeks at that cadence.

On a high-confidence mismatch: the whitelisted FACT field is auto-fixed,
then Length/Elevation criterion scores are recomputed from the published
rubric (`docs/GRAVEL_GOD_SCORING_SYSTEM.md`), then overall_score/tier
recomputed via `recalculate_tiers` logic — tier changes ARE applied (marked
`tier_change: true` in the report), verified against the code and against
commit 473c935d, which dropped balatonfondo T2→T3. Subjective criteria
(prestige, community, experience...) are never touched. Only status changes
(cancelled/defunct) are FLAG-ONLY. An anomaly brake stops auto-commit if
more than 10 profiles change in one run. Known gap: a recompute-driven tier
drop can invalidate `cultural_impact` eligibility (ci>0 requires prestige>=3
or tier<=2, enforced by `test_tier_integrity.py`) — the checker does not
zero the bonus itself; do it manually when the tier test fires.

**War story**: rankings claims silently drifted from reality for months
before this shipped (2026-07-04, hardened 2026-07-09) — nobody was
re-verifying published distance/elevation/field-size against the live
event. Run `python scripts/verify_race_rankings.py --slug {slug}` (or
`--limit N`) manually after any bulk data change (scraping pass, batch
enrichment, migration) that touches vitals. Don't wait for Thursday's cron —
by then the wrong number has been public for days.

## 3. NEVER fabricate social proof

**War story**: a Jun 2026 voice audit (Phase 1 sprint) found 53 fabricated
testimonials live on roadielabs.com — an earlier generation pass had
name-swapped road race names into real gravel-race quotes (3 on
`/products/training-plans/`, 50 on `/about/`) and presented them as road
testimonials. Fixed by restoring the real originals with a provenance line
("Gravel God athletes — same coach, same plan engine, different surface...")
labeled `(gravel)`.

Rule going forward: testimonials, quotes, review counts, "riders say"
claims — every one must trace to a real source (an actual rider, an actual
review, an actual data point) or it does not exist on the page. Never
name-swap or vertical-swap a real quote to make a new vertical (road, ski,
future disciplines) look more populated than it is. This applies until that
vertical has its own real finishers/reviewers — then replace with real ones,
don't keep borrowing.

This is the single fastest way to destroy the honest-critic position the
whole northstar depends on. If you're ever tempted to write a plausible
quote to fill a gap, stop — an honest "— RATE IT →" empty state (see the
Rider Score pattern: real submissions only, zero shown as zero) is the
correct output, not an invented one.

## 4. Anti-shill rules

Full rules: `../gravel-god-cycling/NORTHSTAR.md`, "The anti-shill operating
principle (RottenTomatoes mechanic)". Standing brand rule (Matt's): never
use "no sponsors/no affiliates" copy — defensive framing plants a doubt
nobody had. Independence is demonstrated (public methodology, separated
critic/audience scores), never claimed defensively.

## 5. Stale-date debt undermines scoring credibility too

`CLAUDE.md` Known Pitfall #3: 48 race profiles carry stale 2025 dates; 7 are
genuinely undateable (TBD). A high score sitting next to a stale or wrong
date reads as neglect, not authority, and quietly erodes the same trust this
skill exists to protect. When you touch a profile for scoring or veracity
reasons, check `vitals.date` / `vitals.date_specific` for staleness while
you're in there — it's a one-line check that's already cheap because you're
already in the file.

## When NOT to use this

- Pure layout/CSS/generator-template changes that don't touch score values,
  tier labels, or editorial claims — no need to load this.
- Date/status freshness work with no scoring angle — that's the Tuesday
  `weekly-fact-refresh` loop, not this one.
- Brand tokens, fonts, CI/Python-version issues — see
  `.claude/skills/brand-tokens-and-ci/SKILL.md` if present, not this file.
- Deploy mechanics (SSH, tar, cache purge) with no data change — see
  `.claude/skills/deploy-safely/SKILL.md` if present, not this file.
