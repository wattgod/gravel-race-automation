---
name: email-sequences
description: Write, revise, or extend Gravel God / Roadie Labs email sequences (Mission Control drip emails, lifecycle triggers, broadcasts). Use whenever the task touches mission_control/templates/emails/, sequence definitions, subjects, or new email-marketing ideas for either brand. Encodes the Physiqonomics-derived voice models, the conversion principles, the hard constraints, and the ship process.
---

# Email Sequences — Gravel God + Roadie Labs

You are writing revenue email for two honest-critic cycling brands. The goal
is one custom-plan sale per day ($15/wk, one payment, cap $249), which also
feeds the coaching pipeline. The protected asset is trust: harsh public race
scores earn it; every email either deposits or withdraws.

## Read first (canonical, in gravel-race-automation)

1. `docs/email-voice-model.md` — voice + devices per brand (Physiqonomics-derived)
2. `docs/email-conversion-principles.md` — the five gears, masters' moves, council findings
3. `docs/specs/race-countdown-trigger.md` — the lifecycle-trigger spec (if touching triggers)

## Hard constraints (non-negotiable)

- **Product facts are the only claims allowed:** built from the race's course
  profile + rider FTP + real weekly hours; 48h delivery; ZWO + PDF overview;
  course pacing/fueling targets; human rebuilds remaining weeks on reply;
  $15/wk, one payment, cap $249; coaching exists (small roster). Verify any
  race-specific number against `race-data/<slug>.json` before writing it.
- **Never:** fabricated stats/testimonials/examples, countdown timers, fake
  scarcity, defensive copy ("no sponsors", "no ambush"), identity-
  transformation promises ("become a competitor"), hype adjectives.
- **Promise-tracking:** whatever the welcome says about future email volume
  must be literally true of the sequence. Count the sales emails.
- **Single-pitch posture:** one sales email + one follow-up per sequence,
  then done. Anti_pitch/repitch templates are SHARED across welcome/nurture/
  quiz/win-back — keep them self-contained (no references that only welcome
  readers would get).
- **{race_name} merge field:** only safe where enrollment guarantees
  source_data.race_name (quiz + countdown sequences). Never in welcome-track
  pitch emails — most subscribers never supplied a race.

## Voice cheat-sheet

| | Gravel God | Roadie Labs |
|---|---|---|
| Register | Warm, irreverent, first-person Matti | Deadpan, clinical, institutional "we" allowed |
| Profanity | ≤1 per email, opinions only, never on data | Zero |
| Humor | Jokes allowed, never at the reader | Flat parenthetical only ("the climb is 'rolling' (it is not)") |
| Instead of a swear | — | A verdict sentence: "No." / "It isn't." |
| Honesty mechanism | Self-deprecation, concessions | Methodological transparency, error bars |
| Urgency voltage | One line inside a story | Full audit-finding arithmetic |
| Sign-off | — Matti | — Matti (terse body above it) |

**THE FRIEND-OPENER RULE (Matti, Jul 2026 — his words: "normal, ask simple
q about them without wasting their time, and provide value"):** openers talk
about THEM, never about the email. When the capture context is known
(race_name/race_slug in source_data), open with the callback + a value link +
ONE small answerable question ("A-race or stepping stone? one word"). When
anonymous, the question IS the opener ("which race? one line is plenty").
Engine supports {{#race_name}}...{{/race_name}} / {{^race_name}}...{{/race_name}}
conditional blocks — one template, both branches, never leak mustache or an
empty placeholder (tests: TestConditionalPersonalization).

Devices that must survive edits: objection headers in the reader's voice,
the concession move, pitch-by-teaching, P.S. open loops, exit ramp EARLY +
verb CTA LAST ("BUILD MY PLAN →"), scannable offer block (day-7 email only),
representative sample week as proof, "everything models the rider, nothing
models the race" as the competitive frame (never name competitor apps).

## File map (gravel-race-automation repo — road emails also live HERE)

- Sequence defs: `mission_control/sequences/*.py` — road = `road_*.py` with
  `"brand": "roadielabs"`; absent brand key = gravelgod
- Templates: `mission_control/templates/emails/sequences/*.html` — keep each
  file's existing `<style>` shell; GG marketing = teal-link letter, GG
  post-purchase = boxed brand header, RL = monochrome (#1a1a1a on #f5f5f0)
- Engine (brand senders, UTM, unsubscribe): `mission_control/services/sequence_engine.py`
- Brand sender config: `mission_control/config.py` `BRAND_SEQUENCE_SENDERS`
- Worker (lead intake, sends `brand` field): `workers/fueling-lead-intake/worker.js`

## Ship process

1. Write/edit templates + sequence defs. Subjects live in the defs, not
   the templates — update both.
2. Self-check against the constraints above, then against
   `wordpress/slop_rules.py` phrases.
3. For major rewrites (new sequence, new pitch angle): run the autoreason
   council (`/council`) — critique → counter-proposal → synthesis → 3 blind
   judges with randomized labels. Judge on: conversion power, cringe risk,
   trust preservation, brand differentiation, cohesion. Truncation check:
   verify every proposal file contains ALL emails before judging.
4. `python3 -m pytest mission_control/tests/test_brand_routing.py
   mission_control/tests/test_sequence_engine.py -q` (70+ must pass; also
   run any new tests). The registry test asserts every referenced template
   file exists.
5. Commit (stage ONLY your files — the repo often carries parallel WIP),
   push to main → Railway auto-redeploys Mission Control; copy is live for
   the next 15-min send cycle.

## Ops notes

- Resend domains: gravelgodcycling.com + roadielabs.com both verified
  (road: DKIM/SPF/MX in Cloudflare via one-time authorization, Jul 2026).
  Senders: matti@gravelgodcycling.com / matti@roadielabs.com.
- Road sequences activate only if `active: True` AND the brand routes —
  the subscriber webhook reads the worker's `brand` field; the
  `plan_purchased` enrollment path may NOT carry brand yet (unverified).
- Pre-existing: ~76 mission_control dashboard test failures (401 auth,
  env-dependent) — not caused by email work; don't chase them.

## Parked build-items (highest-leverage first)

1. Race-countdown lifecycle trigger — SPEC'd, see docs/specs/.
2. Footer doorknob: one-line plan link on ongoing content emails.
3. Reply-mining: harvest "reply with your race" answers into copy + personal
   weeks-remaining replies.
4. Sample week hosted on each brand's How-it-works page (emails reference
   the inline version only, deliberately, until this exists).
5. purchase_welcome as forwardable delight (the CD Baby move).
