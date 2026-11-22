# Kit follow-ups and Endure offer: draft provenance (2026-11-22)

Status: DRAFT 2026-11-22, pending Matti's read. Working note, never copy.

Templates covered: `kit_followup` (reworded), `kit_endure_plan`,
`kit_worry`, `road_prep_kit_delivery_notes`, `road_kit_endure_plan`,
`road_kit_worry`, `xc_prep_kit_delivery`, `xc_prep_checkin`. Canonical copy
is in `friend-register-copy.md`, `-road.md` and `-xc.md`.

## Owner decisions behind the drafts

- The plan pitch to new kit leads is replaced by an offer to build their
  race season in Endure, through a sign-up link with the race filled in,
  14 days free.
- No email promises a rebuild or schedule change on reply.
- XC Ski Labs kit leads get the kit link and one check-in. No Endure offer
  (Endure builds gravel, road and mtb seasons only).

## Voice sources consulted

- `wattgod/writing-graph/self/voice-and-beliefs-profile.md`
- `docs/email-voice-model.md` (Matti's Oct 23 2026 rules: texting a
  friend, open on them, one plain line on how he can help, one question)
- The approved kit emails as the register reference: `kit_checkin_pilot`,
  `kit_pitch`, `kit_followup` (pre-change), `prep_kit_delivery`,
  `road_prep_kit_delivery`, `road_prep_variables`.

## Retrieval

Retrieval for the drafting brief returned three essays, from which no
lines were reused:

- `inbox/gravel-god/i-screwed-up-unbound-gravel-200-so-you-dont-have-to.md`
- `inbox/gravel-god/sweet-spot-training-cycling.md`
- `inbox/gravel-god/how-to-beat-people-20-years-younger-than-you.md`

A re-run during implementation (`scripts/retrieve_voice.py "prep kit lead
follow-up email, training app offer, race worry question"`) returned other
pieces (relationship and training, winning when terrible, doing workouts
right, CO2UT, Red Granite Grinder). None of their lines were used either.

## Fixed wording reused verbatim

- The trial disclosure under the Endure button is the approved site
  wording in `wordpress/endure_offer.py`, held for Mission Control in
  `mission_control/services/endure_offer.py`.
- The `kit_followup` block sentence follows `wordpress/plan_offer.py`
  `BLOCKS_LINE`, without the word TrainingPeaks.
