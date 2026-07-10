---
name: conversion-and-email
description: Load when touching email capture, sequences, Mission Control, athlete replies, or any conversion surface.
---

# Conversion and Email

You are editing the money path: forms that capture an email, the sequences that follow, and the reply loop that turns a warm lead into a $15/wk plan sale. Read `CLAUDE.md`'s "Email Capture Forms" section first (worker POST, honeypot, addEventListener) — not repeated here. For sequence copywriting (voice, devices, ship process), load `.claude/skills/email-sequences/SKILL.md` before editing `mission_control/templates/emails/` or `mission_control/sequences/`. This file is the surface map, brand routing, and two hard rules.

## 1. The conversion surface map

- **Prep strip** — `wordpress/generate_neo_brutalist.py::build_prep_strip()` (~line 3915). Renders on race pages between hero and TOC: demand chips, weeks-out countdown, live price, three CTAs (`data-cta=prep_strip_build` / `prep_profile_full` / `prep_strip_kit`). Kit link anchors to the on-page email gate (`#prep-kit-capture`).
- **Prep kit generator** — `wordpress/generate_prep_kit.py`. Renders gated full prep-kit content; posts to `FUELING_WORKER_URL`.
- **Rider Score** — hero block in `generate_neo_brutalist.py` (~line 1950-1962). Number comes ONLY from real `racer_rating` submissions (star_average × 20) gated by `RACER_RATING_THRESHOLD`; below threshold it shows an honest "RIDER SCORE · RATE IT →" ask (`data-cta=hero_rate_race`) to `#racer-reviews`, never a fabricated number. Ratings themselves post to `workers/review-intake/worker.js` — check that worker if ratings aren't showing up, not the general capture path.
- **General email capture (9 sources: exit intent, race profile, prep kit gate, quiz, quiz-shared, tire guide, race review, state hub, date reminder, plus fueling calculator)** — all post to `workers/fueling-lead-intake/worker.js`. Multi-brand: page sends `brand: 'gravelgod' | 'roadielabs'` (absent = gravelgod).
- **Sequences (Mission Control)** — defs in `mission_control/sequences/*.py` (registry `mission_control/sequences/__init__.py`), engine `mission_control/services/sequence_engine.py`, templates `mission_control/templates/emails/sequences/*.html`.

*`CLAUDE.md`'s Email Capture Forms rule names a generic `WORKER_URL` (`email-intake.gravelgodcoaching.workers.dev`) — no worker with that exact name exists in `workers/`. Live generators point at `fueling-lead-intake` (or `review-intake`). Grep the specific generator for `WORKER_URL` — don't trust the generic CLAUDE.md string.*

## 2. Mission Control is brand-aware

Sequences carry a `"brand"` key; absent means `gravelgod`. `sequence_brand()` and `get_sequences_for_trigger(trigger, brand)` in `mission_control/sequences/__init__.py` filter enrollment so a Roadie Labs lead cannot receive Gravel God copy or vice versa. Sender/reply-to/UTM are looked up per brand in `mission_control/config.py::BRAND_SEQUENCE_SENDERS`. Tests: `mission_control/tests/test_brand_routing.py`.

**Current verified state** (check `"active"` in each `road_*.py` before trusting old notes): all four road sequences are `"active": True`, roadielabs.com is verified in Resend — the "road inactive pending DNS" state from early Jul 2026 is stale. Open caveat [UNVERIFIED — session memory, Jul 2026]: `plan_purchased` enrollment may not pass `brand` yet, so a road buyer could still enroll in gravel post-purchase — trace `mission_control/routers/webhooks.py` before relying on it.

**Rule:** before editing a sequence file, check its `brand` key and `"active"` flag — never let a Gravel God edit land in a `road_*.py` file or template, or vice versa.

## 3. Voice

Binding: `docs/email-voice-model.md` (devices per brand) and `docs/email-conversion-principles.md` (five gears, masters' moves, banned list). Read both — don't improvise voice here.

One rule easy to forget mid-edit, not always spelled out in those two docs: **never write defensive messaging.** "No sponsors," "no affiliates," "no ambush," "scored not sponsored" — any phrase answering a question the reader wasn't asking plants the doubt it claims to dispel. Standing rule (Matt's) across all GG/RL surfaces, not just email. If a draft justifies its own honesty, cut the justification.

## 4. The order-killer rule

A field the system can estimate or defer must never hard-fail an intake or capture flow. If it can be defaulted, default it and flag it.

War story (sibling repo athlete-custom-training-plan-pipeline, lesson is general): an intake validator hard-required FTP even though the plan builder already estimates it from weight — one blank field killed a paying order at step 1. Separately, a Jun 2026 GA4 audit on this repo's own forms found roughly zero real leads/month reaching completion (PDF + timeout bugs), since fixed. Failures must be **invisible to the customer, loud to the coach** — never auto-email an athlete "we hit a snag"; it advertises the breakage and often fires on a retry that succeeds anyway. Applied here: check `fueling-lead-intake/worker.js` and `review-intake/worker.js`'s 400 paths before adding a required field — confirm it's truly unrecoverable (email format, honeypot), not defaultable.

## 5. Reply-drafter

`scripts/draft_race_reply.py` drafts Matti's reply to a "here's my race" email in seconds. Both welcome sequences promise a personal reply once the reader shares their race; this fuzzy-matches the name against either brand's `race-data/*.json`, computes real weeks-out via `generate_race_dates.parse_date_specific`, and picks an honest runway-bucket frame (full ≥10w / short 5-10w / keep-your-money <5w / passed / TBD) — editable draft, never an autoresponder. `python3 scripts/draft_race_reply.py "SBT GRVL" [--brand road] [--name Jen] [--copy]`. Use whenever an athlete replies with their race name — don't hand-draft.

## 6. The email worker contract

Every form must POST to its Cloudflare worker, never show success without a real submission (`CLAUDE.md` Email Capture Forms: honeypot, `addEventListener` not `onsubmit`). Sources: `workers/<name>/worker.js` + matching `wrangler.toml` (`fueling-lead-intake/`, `review-intake/`, `training-plan-intake/`, `course-access/`, `course-nudge/`, `tire-review-intake/`). Renaming a form field means opening the matching `worker.js` to confirm it reads that name — each worker validates a fixed `source` list and required keys; an unrecognized `source` or missing key returns a 400 the page may silently swallow. A field renamed on only one side is a silent order-killer per §4.

## When NOT to use this

- Race scoring or ratings math beyond Rider Score display/threshold — scoring/data-pipeline work.
- Deploy mechanics (tar+ssh, cache purge, article SCP) — deploy skill.
- Writing sequence/template copy — load `email-sequences` instead; this file is the surface map and hard rules, not the style guide.
- Brand tokens, fonts, CSS — brand-tokens skill.
