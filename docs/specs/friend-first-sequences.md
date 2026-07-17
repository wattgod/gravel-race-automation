# Friend-Register Sequences — final spec (v3)

**Status:** FINAL, awaiting Matti go/no-go. Supersedes v1/v2 (the 28-email
rewrite program). Matti's re-direction, Jul 16: the drip machine was
overengineered — the fix is register + premise, not better drip copy.
**Canonical copy set:** embedded below (§3). 13 emails replace 28.

## 1. The register (the whole constitution now)

Three tests, every sentence:
1. **Is it simple?** A few short sentences. One idea.
2. **Is it about THEM?** Their race, their training, their week. Zero
   sentences about us, the site, the database, or the emails themselves.
3. **Are we interested?** Every email ends on a real question we genuinely
   want answered. To be interesting, be interested.

The pitch never appears in a broadcast. Countdown emails open the money
conversation ("tell me your week and I'll tell you what I'd do with the
time left"); the plan is offered inside Matti's REPLY, via
`scripts/draft_race_reply.py`. Replies are the conversion engine.

Gate: `scripts/friend_test.py --draft-file <set> --gate` (three detectors,
2-of-2 variance policy) + `slop_rules` + Matti's read. The old device tables
(v2 §2) are moot — nothing in this set has furniture to regulate.

## 2. What dies / what lives

- **Dies (A-variant broadcasts):** welcome days 3/5/7/10/17 content+pitch
  emails, nurture days 5/8/11, race_specific day 10 anti_pitch, win_back
  day 6 anti_pitch. The pitch-count-promise machinery dies with them
  (nothing left to promise about); `test_pitch_count_promise_in_both_branches`
  is updated/removed in the same commit.
- **Lives:** the 13 emails below. Sober variant B keeps its CURRENT copy
  untouched as the A/B control (welcome 50/50). Countdown + post_purchase
  keep their triggers/timing (day-42 → plan-end via existing plan_weeks).

## 3. The copy set (canonical)

Full text: 13 emails as reviewed and approved in draft by Matti Jul 16 —
source of truth for implementation is `docs/specs/friend-register-copy.md`
until templated; then the templates ARE the copy. Set:

| # | slot | subject | premise |
|---|------|---------|---------|
| 1 | welcome d0 (4-branch) | getting ready for one of these? | guide chapter → viewed races → race page → anonymous |
| 2 | welcome d10 (OPTIONAL) | land on a race yet? | no reply to #1 |
| 3 | nurture d2 | how'd the prep kit land? | they downloaded the {race_name} kit ("thanks for grabbing… just hit reply, happy to help") |
| 4 | race_specific d1 | which one are you actually considering? | ran the finder |
| 5 | race_specific d4 | where do races usually get you? | race on their mind |
| 6 | countdown 16w | 16 weeks to {race_name} | full window opens |
| 7 | countdown 8w | 8 weeks to {race_name} | short-runway triage |
| 8–12 | post_purchase d0/3/10/21/plan-end | got your questionnaire / first rides / two weeks in / boring middle / did {race_name} happen? | their plan, their weeks |
| 13 | win_back d0 | did you end up racing it? | what they looked at last time |

Guide-branch copy (Matti's words): "thanks for grabbing the guide. How did
you like the chapter on {guide_chapter}? Any more questions there, just hit
reply — happy to help."

## 4. Build items (small, ordered)

1. **WS-E — enrollment hygiene (live bug, ship first):** stop double-
   enrolling quiz/prep-kit leads into welcome (`webhooks.py`, the "Also
   enroll in welcome" block). New test: no path yields overlapping opener
   tracks.
2. **Trail capture:** shared site JS keeps last ~5 viewed race pages +
   guide chapters in localStorage (first-party); email POSTs include
   `viewed_races` / `guide_chapter`. Worker passes them through in
   source_data. Until shipped, welcome renders the lower branches.
   *Built Jul 16: race-page forms (prep kit, plan ladder, date reminder) +
   the guide form carry the trail. Quiz/tire/state-hub forms do NOT yet —
   backlog, add when touched next.*
3. **Guide entry point (new — guide currently has NO capture):** quiet
   end-of-chapter one-field form ("Training for something? Leave your email
   and tell me the race — I'll help."), no gate — the guide stays free.
   Worker: add `training_guide` to KNOWN_SOURCES + `guide_chapter` field;
   trigger → new_subscriber.
4. **Branch exclusivity:** enrollment writes only the single highest-
   priority context field (guide_chapter > viewed_races > race_name) so the
   welcome branches are mutually exclusive; `any_context` computed at render.
   Safety: give nurture d2 a no-race fallback branch.
5. **Templates + defs:** 13 templates in existing style shells, subjects in
   defs; retire dead slots from A-variant defs. Update
   `test_pitch_count_promise_in_both_branches`, conditional-personalization
   test lists. `pytest mission_control/tests/` green.
6. **Measurement:** replies (the primary KPI now) + GA4 purchase events +
   unsub/spam rates. `sequence_report.py` purchase numbers are known-broken
   (gg_athletes) — do not read them.
7. **Seasonal sensitivity (Matti, Jul 16):** enrollment sets an `offseason`
   flag Nov–Jan (northern-hemisphere gravel calendar); welcome's anonymous
   branch swaps to the offseason opener ("happy offseason. You bored yet?
   Happy with last year? What went well, what went badly?"). The annual
   offseason broadcast (`offseason_note` template, copy banked) sends once
   each November via a small script — build `scripts/send_offseason_note.py`
   before Nov 2026, not now. Southern-hemisphere riders get the wrong
   season read — acceptable v1 imprecision, noted.

## 5. Rollout

GG first (A vs sober-B control stands). RL follows in the same register,
deadpan skin ("Roadie Labs would say: 'Eight weeks to the Maratona. Where
is the training at?'") after GG shows non-negative replies/unsubs for ~2
weeks. XC: same register at launch; full infra prerequisites in v2 archive
(webhook allowlist, UTM domains, worker CORS/brand maps, Resend domain,
registry, senders).

## 6. Kept from the v1/v2 program (not wasted)

- `scripts/friend_test.py` — the gate (AST discovery, --gate, --draft-file).
- `docs/bonk-bros-voice-patterns.md` — voice reference for judging + future
  copy.
- Findings docs — the diagnosis that led here (premise > polish).
- The council-merged 28-email set (`docs/archive/friend-register/council-merged-28-set.md`)
  — parts bank if any dead slot ever needs reviving.
- Sol-review forensics: WS-E bug, attribution breakage, XC prerequisite
  list — all still true and tracked above.
