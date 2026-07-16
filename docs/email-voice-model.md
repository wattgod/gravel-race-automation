# Email Voice Model — the Friend Register (Jul 2026, v3)

Supersedes the Physiqonomics-derived device model (git history has it).
Matti's re-direction Jul 16 2026: the drip machine was overengineered; the
voice is not a device kit, it is a register. Canonical copy:
`docs/specs/friend-register-copy.md`. Governing spec:
`docs/specs/friend-first-sequences.md`.

## The register — three tests, every sentence

1. **Is it simple?** A few short sentences. One idea per email.
2. **Is it about THEM?** Their race, their training, their week. ZERO
   sentences about us, the site, the database, or the emails themselves.
   No self-description, no meta ("as promised", "the sales email"), no
   pitch-count announcements. A friend says "how's training going?"
3. **Are we interested?** Every email ends on a real question we genuinely
   want answered. To be interesting, be interested.

## Structural rules

- **No broadcast ever pitches.** Countdown emails open the money
  conversation ("tell me your week and I'll tell you what I'd do with the
  time left"); the plan is offered in Matti's REPLY
  (`scripts/draft_race_reply.py`). Replies are the conversion engine.
- **Premise first.** The first line names why this email exists for THIS
  person: what they grabbed, viewed, bought, or how far out their race is.
  Calendar position is never a premise.
- **The download shape** (Matti's words): "thanks for grabbing X. How did
  you like Y? Any more questions, just hit reply — happy to help."
- **Seasonal sensitivity:** the `offseason` flag (Nov–Jan) swaps the
  anonymous welcome opener; annual `offseason_note` broadcast each November.
- **No links unless the link serves them concretely.** The reply is the click.
- Sign-off: — Matti. Lowercase subjects, tiny, about them.

## Brand skins (same register, different accents)

| | Gravel God | Roadie Labs | XC Ski Labs (proposed) |
|---|---|---|---|
| Accent | warm, first person | deadpan, clinical | deadpan-warm, first person |
| Profanity | avoid (nothing in the 13 needs it) | zero | zero |
| Example | "You bored yet?" | "Where is the training at?" | dry understatement |

## Gate

`scripts/friend_test.py --gate` (Tool / Body-Snatcher / Familiarity,
calibrated on `docs/bonk-bros-voice-patterns.md`) + `slop_rules` + Matti.
