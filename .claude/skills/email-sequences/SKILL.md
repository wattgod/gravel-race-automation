---
name: email-sequences
description: Write, revise, or extend Gravel God / Roadie Labs email sequences (Mission Control drip emails, lifecycle triggers, broadcasts). Use whenever the task touches mission_control/templates/emails/, sequence definitions, subjects, or new email-marketing ideas for either brand. Encodes the friend register, the hard constraints, and the ship process.
---

# Email Sequences — Gravel God + Roadie Labs (Friend Register, Jul 2026)

Revenue email for honest-critic cycling brands. The protected asset is trust.
**The drip-pitch era is over (Matti, Jul 16 2026): broadcasts never pitch;
replies are the conversion engine** (`scripts/draft_race_reply.py`; the plan
is offered inside Matti's reply when it fits).

## Read first (canonical)

1. `docs/specs/friend-first-sequences.md` — governing spec
2. `docs/specs/friend-register-copy.md` — canonical copy (13 emails + banked
   offseason note). Templates mirror it; a divergence is a defect.
3. `docs/email-voice-model.md` — the register, one page
4. `docs/bonk-bros-voice-patterns.md` — voice north star

## The register (three tests, every sentence)

1. **Simple?** A few short sentences, one idea.
2. **About THEM?** Their race/training/week. Zero sentences about us, the
   site, the database, or the emails themselves. No meta, ever.
3. **Interested?** End on a real question we genuinely want answered.

## Hard constraints (non-negotiable)

- **Product facts only** (when facts appear at all — mostly in replies):
  course profile + FTP + real hours; 48h; ZWO + PDF; $15/wk one payment cap
  $249; human rebuilds on reply; small coaching roster. Verify race numbers
  against `race-data/<slug>.json`.
- **Never:** fabricated anything, countdown timers, fake scarcity, defensive
  copy, identity-transformation promises, hype adjectives, banner/all-caps
  CTAs, "as promised" sequence meta, resource catalogs, P.S. next-email
  teasers, pitch paragraphs in broadcasts.
- **Premise honesty:** an email may only claim the context its enrollment
  guarantees. Welcome branches on ONE wb_* key (guide > trail > race —
  exclusivity enforced in `webhooks.py`, tested in `test_webhooks.py::
  TestFriendRegisterEnrollment`). {race_name} outside countdown/quiz tracks
  needs a {{^race_name}} fallback branch (engine substitutes "your race" —
  grammar breaks without one).
- **WS-E:** never reintroduce also-enroll-in-welcome (double-enrollment bug,
  removed Jul 2026, regression-tested).
- **Seasonal:** `offseason` flag Nov–Jan swaps the anonymous welcome opener;
  `offseason_note` broadcast sends each November (script: build before Nov).
- **Sober variant B** (welcome) is the A/B control — do not edit it with
  register changes; it measures the register against the old style.

## File map

- Defs: `mission_control/sequences/*.py` (road = `road_*` or `brand` key;
  `race_countdown.py` is MIXED-brand — check the `brand` key per sequence)
- Templates: `mission_control/templates/emails/sequences/*.html` — keep each
  file's `<style>` shell; subjects live in the DEFS, not templates
- Engine: `mission_control/services/sequence_engine.py`
  (`_apply_conditionals` resolves NESTED mustache to a fixed point)
- Enrollment/context: `mission_control/routers/webhooks.py` (wb_* keys,
  offseason flag, trigger_map)
- Worker: `workers/fueling-lead-intake/worker.js` (KNOWN_SOURCES incl.
  training_guide; carries guide_chapter + viewed_races)

## Ship process

1. Edit copy doc + templates + defs together (they must not diverge).
2. Gate: `python3 scripts/friend_test.py --gate` (Tool / Body-Snatcher /
   Familiarity; 2-of-2 variance policy on FAILs) + `wordpress/slop_rules.py`.
3. `python3 -m pytest mission_control/tests/ -q` (ignore pre-existing
   test_triage* 401 failures; everything else green).
4. Matti reviews rendered copy before anything ships. Stage ONLY your files;
   push to main → Railway redeploys; live next 15-min cycle.

## Measurement

Replies (primary KPI) + GA4 purchase events + unsub/spam rates.
`sequence_report.py` purchase numbers are broken (gg_athletes is never
written by the purchase path) — do not cite them.
