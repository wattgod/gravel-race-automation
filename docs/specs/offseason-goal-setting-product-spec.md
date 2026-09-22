> **SUPERSEDED (2026-09-22) by `goals-2027-funnel-spec.md` v0.3.** Matti ruled the
> funnel takes the page and the offer (`/goals/`, offer in the results screen). What
> survives from this draft: the $150 Offseason Read consult as a separate,
> higher-touch product offered in replies, and the pitch-free November broadcast,
> which now links to the free questionnaire. Kept for its evidence and its reasoning.

# Offseason Goal-Setting Product — spec v0.1 (2026-09-17, draft for Matti's gates)

## Why (facts, not hopes)
- The list has never been given an offseason reason to reply. 255 nurture enrollments / 118 deals in 90 days, 51.5% open, 6.1% click; premise-true emails (debrief, countdown) get ~17% day-one replies. Replies are the only measured conversion mechanism; clicks do not convert (0.73% race→questionnaire, 1 purchase/28 d). Source: memory/lead-nurture-sep12, data/intel-snapshots/2026-09-14.md, docs/specs/reply-engine-and-prepkit-2026.md.
- The offseason broadcast already exists as copy and template (`offseason_note.html`, friend-register-copy.md §seasonal·november) but has no sender: `scripts/send_offseason_note.py` is an owed item since Jul 2026. Brand offseason flag (Nov–Jan gravel/road) already exists in Mission Control.
- The Consult Engine ($150 / 60 min, +$100 custom-plan add-on) is live on GG/RL/XC with checkout, intake tokens, runner, WKO claim store, Endure delivery and call-relative follow-ups. Its analyzer already computes a `season` power-duration window. Its C3 report template is still open.
- Matti's Season Review (Self-Authoring Inspired) Google Form exists (2025-10-16). His 2021 article "How to achieve your goals and stop ruining your dreams" is the thesis in his voice ("It's dreaming season… PROCESS is the difference").
- Coaching Min already lists "Quarterly strategy calls"; a Base + Strength 12-wk $69 SKU ("Squats and Zone 2. That's the Plan.") is built but the goal suite is unpublished.

## Decision (Fable decides, Matti reverses)
Do NOT build a new SKU. Build **one consult variant + one broadcast + one page**, all on machinery that exists:

1. **Product: the Offseason Read** — the $150 consult with three swaps: (a) intake = the Season Review questions (12 prompts: what went well / badly / why, what you avoided, the one race that matters, hours you can actually give, the thing you keep saying you'll fix); (b) analysis window = `season` (the retrospective) instead of last90; (c) deliverable = the call + a one-page **Season Review & Next-Season Map** (written within 48 h: three findings from the files, one limiter, the A-race, a month-by-month shape, the first block's start date). Add-on: **+$100 first block** — the opening 12 weeks (Base + Strength via Motoren, testing week first) on TrainingPeaks within 7 days. The add-on is the on-ramp to a custom plan; the Map's "what I'd do if I were coaching you" line is the on-ramp to coaching.
2. **Distribution: the November offseason note**, sent once to the whole list (both brands), premise-true, no pitch (doctrine). The reply is where the Read is offered — Matti's reply, drafted by the reply engine with a new `--offseason` mode. Also: the Read replaces the generic Calendly link in the debrief-sequence reply drafts from Nov 1 to Jan 31.
3. **Page: /offseason/** on GG and RL (mirror), sultanic structure in the plain register: two futures (the rider who starts January with a map vs the one who starts with a resolution), what I look at, what you get, for/not-for, price. No testimonials. `noindex` until Matti approves copy.

## What ships (executors) — behind Matti's gates below
- `mission_control/sequences/offseason_v1.py` + `scripts/send_offseason_note.py` (idempotent, dry-run default, brand-aware, skips leads who bought/coached in the last 90 d).
- Consult intake variant: `wordpress/generate_consult_intake.py --variant offseason` (12 prompts; key stays `tp_email`), `POST /api/consult-intake` accepts `variant`.
- Consult runner: `--window season` default when `variant == offseason`.
- Report template C3 (owed anyway): `docs/templates/season-review-map.md` → rendered by the existing report route.
- `wordpress/generate_offseason.py` (GG) + RL mirror; Stripe: reuse `CONSULTING_PRICE_ID` + `CONSULT_PLAN_ADDON_PRICE_ID`; new `consult_variant=offseason` metadata on checkout so the funnel report can split it.
- Reply engine: `scripts/draft_race_reply.py --offseason` (uses the lead's race history + the Read's link; friend-register).
- Measurement: consults booked with `variant=offseason`, add-ons, coaching applications Nov–Feb with source `offseason`, reply count on the note (Gmail `! Reply` label count the week after send).

## Copy (Matti reads everything before publish; droll, ≤60 chars, searchable noun)
Page/product name candidates (his pick): **"Happy Offseason. Now What?"** · **"Dreaming Season — 60 Minutes"** · **"The Plan Before the Plan"**.
Broadcast subject stays the ratified `happy offseason`. No commands, no hype verbs, no fourth wall.

## Gates (Matti)
G1 Shape: consult variant (this spec) vs. a standalone $99 product. Default: consult variant.
G2 Price: $150 + $100 add-on as-is, or an introductory $99 for November only. Default: as-is (cap math: consult+add-on $250 already sits above the $249 custom-plan cap; a lower add-on avoids the "price wrong below cap" trap).
G3 Doctrine: broadcast stays pitch-free; the Read is offered in replies only. Default: yes. The Oct 10 kit-pitch pilot readout may revise this.
G4 Copy and name: Matti reads page + reply draft before anything is public.

## Not in scope
New nurture sequences; a course; changes to coaching tiers; any Motoren engine change (the add-on block uses Motoren as-is).

## Timeline
Oct 1 send_offseason_note.py + sequence def merged (dry-run proven) · Oct 15 intake variant + runner window + report template · Oct 22 page + reply mode · Oct 31 sol review + Matti copy gate · Nov 3 send.
