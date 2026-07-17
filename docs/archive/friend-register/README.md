# Friend-Register program — decision trail (Jul 15-16, 2026)

Why the email sequences are what they are. Live spec:
`docs/specs/friend-first-sequences.md`; copy: `friend-register-copy*.md`.

1. **Thesis (Matti):** sequences felt cringe → "text like a confident
   non-simp dater" → refined to the Claude-register frame → calibrated on
   **Bonk Bros** (friends who don't bullshit each other = trustworthy AND
   entertaining) → `docs/bonk-bros-voice-patterns.md`.
2. **The gate (Matti's 3 detectors):** Tool ("would a friend sound like a
   tool?"), Body-Snatcher ("did someone steal my friend's phone?"),
   Familiarity ("would a friend actually send this, now?") →
   `scripts/friend_test.py`. Findings: 20/25 GG + 12/16 RL emails failed;
   premise (not prose) predicted score.
3. **Sol adversarial review: NO-GO on spec v1** (this dir) — all 5 blockers
   verified: parser missed 6 emails; gate didn't gate; LIVE double-enroll
   bug (WS-E); trigger contradiction; XC infra gaps.
4. **Council:** sol beat terra 2-1 blind; merged 28-email set (this dir) —
   then SUPERSEDED by:
5. **The pivot (Matti):** "grossly overengineered." Final register = three
   tests per sentence: simple? about THEM? are we interested? No broadcast
   ever pitches — replies are the conversion engine (draft_race_reply.py).
   13 tiny emails replaced 28. Shipped e0aa3e36 (GG) + 925d8cbc (RL) +
   a6825c33 (enrollment alerts). E2E verified in prod Jul 17 00:05-00:12 UTC.
