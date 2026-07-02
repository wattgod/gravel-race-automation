# Email Voice Model — Physiqonomics-derived (Jul 2026)

Style bible for the Gravel God + Roadie Labs email sequences, derived from a
deep study of Aadam Ali / Physiqonomics ("The Vitamin" newsletter). Applied to
`mission_control/templates/emails/sequences/` in the Jul 2026 rewrite.

## The system in one paragraph

**Fixed ritual container + evidence core + personality shell + objection
ventriloquism + free-first selling.** The container (greeting, sections,
sign-off, P.S.) never changes, so the personality can be loud without chaos.
The science is always clean; the attitude lives only in the opinions. Name the
reader's doubts before they do, concede what you must, and pitch by teaching.

## Devices in use (Gravel God — full organism, lower voltage)

- **Objection headers in the reader's voice** — "Yeah, but I only have 8 hours
  a week…" as a literal section header, answered straight. Used in
  anti_pitch/repitch.
- **The concession move** — admit where the argument is weak ("touché") so the
  strong claims land. Integrity at the sentence level.
- **Recurring strawman: Derek** — the Instagram gravel coach. Clearly
  fictional archetype (like Aadam's "Becky"). The misinformation avatar.
  Punch Derek and the industry, never the reader.
- **Math as emotional weapon** — 24 gels, 600 grams, week six. Numbers hit.
- **Sarcastic myth subjects** — "the aid station will save you (it will not)".
- **Story → lesson → evidence → application** arc for content emails.
- **P.S. chain** — every email's P.S. teases the next or invites a reply.
- **Unsubscribe-as-freedom** (never denial framing — see
  feedback_no_defensive_messaging: no "no sponsors/affiliates" copy, ever).
- **Profanity budget:** ~1 per email, on opinions only, never on data.

## Devices in use (Roadie Labs — skeleton only, deadpan skin)

- **Study-breakdown template**: question subject → what the data says → what
  it means for you → key takeaways. This IS the brand.
- **Deadpan parenthetical** as the entire humor budget: "the climb is
  'rolling' (it is not)".
- **Verdict sentences** instead of profanity: "No." / "It isn't."
- **Ventriloquized objections as data questions** — "'Field depth is
  subjective.' Correct. Here is how we bounded it."
- **Methodological transparency instead of self-deprecation** — show the
  ruler, admit the error bars.
- **Zero:** profanity, absurdist imagery, recurring characters, "you're
  welcome" swagger, exclamation points.

## Sequence architecture

Timing is unchanged (research: engagement halves by ~day 12; pitch day 7,
single re-pitch day 10, pure-value close day 17). Gravel welcome keeps its
A/B: variant A = this voice, variant B = sober register (the control).
Road sequences are single-track (list too small to split).

Road sequences carry `"brand": "roadielabs"` and stay **inactive until
roadielabs.com is verified in Resend** (DNS records) — flip `active` in
`mission_control/sequences/road_*.py` after verification.
