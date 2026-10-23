# Email Voice Model — the Friend Register (Jul 2026, v3)

Supersedes the Physiqonomics-derived device model (git history has it).
Matti's re-direction Jul 16 2026: the drip machine was overengineered; the
voice is not a device kit, it is a register. Canonical copy:
`docs/specs/friend-register-copy.md`. Governing spec:
`docs/specs/friend-first-sequences.md`.

## Matti's rules (Oct 23 2026, his words; these win over anything below)

> "The key thing is that I 1. keep track of everyone 2. don't accidentally
> send an old email or out of date email that obviously doesn't make sense
> 3. an email that doesn't sound like me and is too long winded 4. an email
> that dances around things too much forever 5. I want to speak to ther
> person succinctly and offer interest in them and value in my services and
> I need a process to do it"

> "Yeah, but it can go early be even shorter than 100 words in a lot of
> cases. It's almost like I'm texting a friend."

What that means for every lead and buyer email, broadcast or drafted:

- **Texting a friend.** Aim for 25 to 70 words, not counting greeting and
  sign-off. Never over 100. Shorter wins when it still says the thing.
- **Open on them.** The first line is about the person: what they grabbed,
  bought, said, or where they are with their race.
- **One plain line on how Matti can help.** Say it straight ("reply and I'll
  fix it", "that's what my coaching is"). No hinting, no build-up.
- **One question,** easy to answer, at the end.
- **No dancing around.** If the email exists to offer something, say the
  offer in one sentence. No warm-up paragraph, no recap, no apology.
- **Nothing that can be out of date when it lands.** Don't state a week
  count, a race date, a plan stage or "you haven't replied" unless it was
  checked against the latest thread and the race's current date right
  before the draft or send. A draft that sat in Gmail for days gets checked
  again or deleted.

## The register — three tests, every sentence

1. **Is it simple?** A few short sentences, 25 to 70 words. One idea per email.
2. **Is it about THEM?** Their race, their training, their week. ZERO
   sentences about us, the site, the database, or the emails themselves.
   No self-description, no meta ("as promised", "the sales email"), no
   pitch-count announcements. A friend says "how's training going?"
3. **Are we interested?** Every email ends on a real question we genuinely
   want answered. To be interesting, be interested.

## Structural rules

- **No broadcast hard-sells.** One plain line on how Matti can help is
  expected (rules above); prices and links wait for the reply. Countdown
  emails open the money conversation ("tell me your week and I'll tell you what I'd do with the
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

## Reply register — Reflect → Give → Ask

Broadcasts open the conversation; replies prove the relationship. A Matti reply
uses the lightest structure that is still useful:

1. Reflect one specific detail so the person knows they were read.
2. Give one answer, connection, or practical implication when it is grounded.
3. Ask one easy question. One question mark is the default.

Do not stack three questions, turn a short answer into a coaching monologue, or
add a pitch when the person did not ask about help. Clever metaphors are rare:
if the line draws more attention than the person, cut it. Early questions should
be easy to answer (“still deciding or registered?”, “what keeps getting in the
way?”, “what workout do you look forward to?”). Invite a longer story only after
the person is engaged. Measurement and examples:
`docs/specs/gmail-lead-reply-loop-2026.md`.

Professional and human beats polished. Dry understatement is part of Matti's
voice when the moment gives him an opening; a joke in every reply is a bot doing
an impression of Matti. Continue the thread instead of resetting to “what are
your challenges?” after the person has already answered it. By the third lead
turn, give something useful before asking for more context.

## Brand skins (same register, different accents)

| | Gravel God | Roadie Labs | XC Ski Labs (proposed) |
|---|---|---|---|
| Accent | warm, first person | deadpan, clinical | deadpan-warm, first person |
| Profanity | avoid (nothing in the 13 needs it) | zero | zero |
| Example | "You bored yet?" | "Where is the training at?" | dry understatement |

## Gate

`scripts/friend_test.py --gate` (Tool / Body-Snatcher / Familiarity,
calibrated on `docs/bonk-bros-voice-patterns.md`) + `slop_rules` + Matti.
