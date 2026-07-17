# Gravel God Race Pages — Canonical Spine v2

**Decision date:** 2026-07-17  
**Status:** Implemented and catalog-audited on `race-page-final-mock`; staged, not deployed  
**Owner approval:** Matti approved the final mock before catalog rollout  
**Supersedes:** conflicting structure/copy instructions in the 2026-07-14 overhaul handoff and simplification spec

This is the durable source of truth for Gravel God race-page structure. Earlier
artifacts remain useful for analytics evidence, data-cleanup tickets, and interaction
details, but they do not override the final owner-approved contract below.

## Why the page changed

The decision was evidence-led:

- GA4 baseline: 5,180 race-page views produced 76 plan-CTA clicks, or 1.5%.
- Only about 18% of visitors reached 90% scroll.
- Ratings were the trust/acquisition surface, while the offer was buried near the
  bottom of a roughly 20-section page.

The response was not to make the critic louder as a salesperson. It was to preserve
the useful editorial depth, surface the decision-making rating first, put one calm
offer where it can be seen, and remove repeated commerce from the reference material.

## Final owner-approved contract

Top-level order:

1. Hero, including the concise race verdict already carried by the hero data.
2. Interactive two-radar Ratings component.
3. Custom Plan offer.
4. Coaching footnote.
5. Full Breakdown navigation.
6. Original collapsible Deep Dive.

The top custom-plan CTA is exactly:

- `START MY CUSTOM PLAN →`
- `$15 / WEEK`

The coaching footnote is exactly:

- `Really want to see what you can do?`
- `Hire a coach. You’ll never become what you could be alone. (And no, AI isn’t a person.)`
- `GET ME IN YOUR CORNER →`

The Deep Dive retains the original accordion/mobile presentation and its useful
race-specific material:

- Course Overview
- Facts & History
- The Course
- From the Field
- Racer Reviews
- Training
- Train for This Race
- Race Logistics
- Tire Picks
- Latest Coverage when data permits
- Similar Races
- FAQ
- Sources
- Race-demand profile
- Training considerations and rider intelligence
- Expandable sample workouts

## Explicit removals

Do not reintroduce any of the following without a new owner decision:

- A standalone Final Verdict section. The concise hero verdict is sufficient.
- The transition strip: “You’ve seen what it asks. Here’s how you answer it.”
- `BUILT FOR THIS` framing.
- Race-date repetition inside the custom-plan offer.
- “Less than one gel per ride.”
- “What the plan has to solve.”
- Sticky training-plan CTAs.
- Ready-made TrainingPeaks plan ladders on race pages.
- Plan configurators or preview controls inside the Deep Dive.
- Plan/coaching sales copy or purchase links inside the Deep Dive.
- Duplicated plan/coaching pitches.

These removals reduce buying friction and prevent editorial material from repeatedly
switching into sales mode. TrainingPeaks race SKUs still serve marketplace discovery;
that is a separate surface and does not justify putting the ladder back on race pages.

## Brand and implementation invariants

- Gravel God uses `gravel_god_rating`, `gg-*` classes, `--gg-*` tokens, Gravel God
  URLs, logo, typography, copy vocabulary, and GA4 property `G-EJJZ9T6M52`.
- Never copy Roadie Labs `rl-*` classes or tokens into Gravel output.
- Page marker: `data-page-format="spine-v2-approved"`.
- Exactly one approved plan CTA and one approved coaching CTA appear above Deep Dive.
- `#ratings` precedes the offer; the offer precedes coaching; coaching precedes
  `#breakdown`; breakdown precedes `#deep-dive`.
- `#training` and `#train-for-race` live inside Deep Dive.
- Deep Dive contains no questionnaire, coaching, plan-guide, configurator, preview,
  or sticky-CTA commerce.
- No duplicate IDs, inline data-derived executable HTML, hardcoded colors, fake form
  success, or fabricated race content.
- GA4, consent, canonical, header/footer, XSS escaping, and email-worker rules remain
  binding.

## Implementation record

Generator:

- `wordpress/generate_neo_brutalist.py`

Key Gravel commits:

- `88159da7` — lock approved spine and restore editorial Deep Dive
- `6cda07d9` — mark approved page format
- `4bdd686f` — add repeatable catalog audit

Catalog result:

- 746 stored race profiles
- 10 explicitly retired/fabricated slugs remain excluded by contract
- 736 eligible pages generated
- 736/736 pages have race-demand packs
- 736/736 passed `scripts/audit_spine_v2_catalog.py`
- Focused generator suite: 174 passed
- Python 3.11 compilation passed

Staged output:

- `wordpress/output-spine-v2-stage/`

Known non-blocking data gap:

- `best-buddies-challenge-hyannis-port`, `bp-ms-150-texas`, and
  `gran-fondo-argentina` currently lack a course description. Their pages render the
  approved structure without fabricating replacement prose.

## Regenerate and verify

```bash
python3 wordpress/generate_neo_brutalist.py --all \
  --output-dir wordpress/output-spine-v2-stage
python3 -m pytest tests/test_neo_brutalist.py -q
uv run --python 3.11 --no-project python -m py_compile \
  wordpress/generate_neo_brutalist.py
python3 scripts/audit_spine_v2_catalog.py
```

## Deploy gate

The staged catalog is not permission to publish. Do not push to `main`, trigger the
catalog-sync workflow, upload WordPress output, or purge caches without Matti’s
separate deploy approval. Before an approved deploy, rerun the focused tests, catalog
audit, and repository preflight; then follow `.claude/skills/deploy-safely/SKILL.md`.
