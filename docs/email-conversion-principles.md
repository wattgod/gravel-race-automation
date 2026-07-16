> **SUPERSEDED (Jul 16 2026):** the friend-register spec
> (`docs/specs/friend-first-sequences.md`) replaced broadcast pitching
> entirely — replies are the conversion engine now. This doc is kept as
> the WHY-layer archive of the drip era; its 'masters moves' apply to
> REPLY copy, not broadcasts.

# Email Conversion Principles — GG + RL

Companion to `email-voice-model.md` (voice/devices). This is the WHY layer:
what actually converts, distilled from the Physiqonomics study, the Jul 2026
autoreason council, and the direct-response canon. Read both before touching
`mission_control/templates/emails/sequences/`.

## The five gears of the Physiqonomics machine

1. **Trust arbitrage.** In an industry that lies, truth-telling — including
   truths that cost sales — makes you the only credible voice. The pitch
   inherits the accumulated credibility. Our version: harsh public race
   scores are trust deposits; the plan pitch withdraws. Lead sequences with
   the WORST scores (the 36, the 44), not the best.
2. **Objection ventriloquism.** Answer the reader's objection before they
   finish forming it, as a header in their voice. Unanswered objections are
   where sales die silently.
3. **The concession move.** Give real ground on purpose. One honest
   concession makes ten confident claims believable. Salesmen never concede;
   friends do.
4. **Pitch by teaching.** The sales email reads like the free content —
   same voice, same structure, teaching until the last paragraph. The guard
   never goes up because the register never changes.
5. **The ritual container.** Identical greeting/frame/sign-off/P.S.,
   forever. Familiarity compounds into relationship; people buy from
   personalities they feel they know.

## Moves stolen from the masters (and which fit our constraints)

| Source | Move | Our status |
|---|---|---|
| Ramit Sethi | Disqualification pitch ("do NOT buy if…") — flips frame from wanting money to screening buyers. Also: mine reader-reply language into copy. | IN (both anti_pitches disqualify no-race readers; reply-mining TODO) |
| André Chaperon | Open loops across emails — sequence as one serialized story. | IN (P.S. chain) |
| Ben Settle | The doorknob: low-key CTA visible on every content email, forever. | TODO — one-line footer plan link on ongoing signal emails; NOT a pitch, preserves single-pitch posture |
| patio11 | Lifecycle email tied to user state, not signup drip. We uniquely have RACE DATES. | SPEC'd — `docs/specs/race-countdown-trigger.md` |
| Gary Halbert | "Reason why" urgency — pressure built only from true mechanics. | IN (base-weeks-are-non-renewable; "waiting lowers the plan, not the price") |
| Derek Sivers | Confirmation email as forwardable delight — referral engine when testimonials are banned. | Partial (purchase_welcome is solid, not yet screenshot-worthy) |

**Banned regardless of who does it:** countdown timers, fake scarcity,
manufactured deadlines, testimonials/fabricated proof, defensive copy
("no sponsors", "no ambush"), identity-transformation promises, invented
statistics. If pressure isn't made of true mechanics, it doesn't ship.

## Council findings that must not regress (Jul 2026, 3/3 blind judges)

1. **Fight the real competitor.** The buyer's alternative is adaptive
   training software and marketplace plans, not "an Instagram coach."
   Winning frame: *everything models the rider; nothing models the race* —
   beats app users without naming or advertising any app.
2. **Promise-tracking is load-bearing.** If the welcome says two sales
   emails, exactly two arrive. A broken meta-promise ("once, then I'll
   stop" → two pitches) costs more than the pitch earns.
3. **Honest urgency is the biggest conversion lever.** Weeks-to-race are a
   fixed stock; per-week pricing rewards waiting — confront it: "waiting
   does not lower the price, it lowers the plan." Voltage by brand: GG one
   line inside the week-six story; RL the full audit-finding version.
4. **Show the artifact.** With testimonials banned, proof = the product
   itself: a representative mid-plan week inline ("representative", never a
   fabricated customer's plan), offer block with every deliverable.
5. **CTA mechanics:** exit ramp early, verb CTA last ("BUILD MY PLAN →"),
   offer block in the day-7 email only, one idea per email.
6. **Split follow-up spines by brand:** GG = week-six life story (warm);
   RL = pricing-vs-physiology arithmetic (clinical). Structural
   differentiation, not just tonal.

## Where everything lives

- Sequence defs: `mission_control/sequences/*.py` (brand key; road = `road_*`)
- Templates: `mission_control/templates/emails/sequences/*.html`
- Engine: `mission_control/services/sequence_engine.py` (brand senders/UTM)
- Tests: `mission_control/tests/test_brand_routing.py`, `test_sequence_engine.py`
- Voice bible: `docs/email-voice-model.md`
- Push to main = Railway redeploys Mission Control (copy goes live)
