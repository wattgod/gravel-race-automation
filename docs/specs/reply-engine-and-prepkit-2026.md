# Reply Engine & Prep-Kit Delivery — 2026-08-12

Spec author: Claude (Fable). Implementer: Codex. Review/merge: Claude → Matt.
Register law: `docs/email-voice-model.md`. Every new email template and every
drafted-reply skeleton MUST pass `scripts/friend_test.py --gate` before the
workstream is done. Global rules: `~/.codex/AGENTS.md` (Acceptance Recap
mandatory; never invent schema — verify against live tables or
`mission_control/supabase_client.py` usage).

## Context (verified 2026-08-12, do not re-litigate)

- Debrief/countdown sequences are live and getting ~17% reply rates day-one.
  Replies land in gravelgodcoaching@gmail.com. Replies are the conversion
  engine; broadcasts never pitch.
- `scripts/draft_race_reply.py` exists: deterministic drafter for "here's my
  race" welcome replies, frame picked by runway bucket. It has NO mode for
  debrief-thread replies (race already happened / went wrong).
- prep_kit_gate is a browser-side content unlock. NOTHING is emailed at
  enrollment: `nurture_v1` variant steps start at `delay_days: 2`
  ("how'd the prep kit land?"). Live consequence: matthall2099@yahoo.com
  (Unbound XL lead, enrolled 2026-08-09) replied "Never received it."
  gg_sequence_sends has no kit delivery row for him; gg_communications empty.
- Kit pages live at `https://gravelgodcycling.com/race/{slug}/prep-kit/`.
  Spot-check: unbound-xl 200, unbound-100 200, rebeccas-private-idaho 200,
  little-sugar-mtb 200, colorado-trail-race 200, **the-mid-south 404** (an
  active lead's race — hbuford2016, enrolled 2026-08-09).
- XC: `https://xcskilabs.com/race-dates.json` is live (200) but xcskilabs is
  NOT in `RACE_DATES_URLS` (`mission_control/config.py`), and there are no
  XC countdown/debrief sequences. Roadie mirrors exist and are the pattern.
- Hosts 403 bot UAs and intermittently serve non-JSON; any new fetch must
  reuse `_fetch_dates_sync` (UA + gg_settings fallback), never raw urllib.

## WS-A — `draft_race_reply.py --debrief` mode

Goal: paste an athlete's debrief/countdown reply, get a Matti-register draft
in ~2 seconds that continues the conversation and (where warranted) closes
with the free bridge-block offer (WS-B).

- CLI: `python3 scripts/draft_race_reply.py --debrief --reply-file r.txt
  [--race "Salida 76"] [--brand gravel|road] [--name Michael]`; `--reply -`
  reads stdin. Race optional — if omitted, draft skips race facts gracefully.
- Deterministic keyword classifier over the reply text → failure mode:
  `illness`, `injury`, `fueling`, `pacing`, `mechanical`, `dns_deferred`,
  `logistics`, `happy`, `unknown`. Multi-label allowed; primary = first hit
  by a documented priority order. NO LLM calls — this tool must work offline
  in 2 seconds like the existing modes.
- Frame library (one per failure mode) in the register: (1) acknowledge the
  SPECIFIC thing they said (quote a fragment), (2) one sharp follow-up
  question a coach would actually ask, (3) close with the bridge-block offer
  ONLY for modes where a block is honest value: illness, injury(returning),
  pacing, fueling, race<12wks. `happy`/`unknown` end on the question alone.
  Canonical skeleton (calibrate against these real cases, in
  git history of this spec):
  - illness + race 8wks out (Mendik): "Getting sick at 55 and restarting at
    40 with 8 weeks to go is a solvable problem, but the order matters —
    rebuild aerobically before you touch intensity. What did your biggest
    week look like before you got sick? If you want, I'll sketch the next
    10 days for you — no charge, just tell me how week one feels."
  - dns_deferred + injury (John Martin): acknowledge, ask what PT/fit angle
    is still unresolved, NO block offer until they name a next race.
- Offer copy must not overpromise: the block is "the next 10 days", not "a
  plan". Run every frame through `scripts/friend_test.py --draft-file`.
- Tests: classifier cases from the five real replies quoted above (fixture
  file with anonymized text is fine), frame selection, offer-gating rules,
  no-crash on empty/HTML-quoted reply text.

## WS-B — Bridge blocks (`scripts/render_bridge_block.py`)

Three archetypes, 10–14 days, TEXT output (markdown), pasted into a reply.
Explicitly lighter than the paid pipeline — no PDF, no TP push, no guide.

- Archetypes: `comeback` (post-illness/injury return: 10 days, aerobic
  rebuild, RPE-capped, 2 rest days, one openers day), `base_hold` (no near
  race: 14 days, 3 quality-free weeksish pattern, durability focus),
  `race_triage` (race 5–10 wks: 10 days, one threshold touch, one long ride
  with race-fuel practice, taper note if <6wks).
- Inputs: `--archetype`, `--race` (optional, adds weeks-out framing via
  race-dates through `mission_control.services.race_countdown` fetch/cache),
  `--hours <weekly hours>` (optional; scales durations; default 6–8h band
  with an honest "adjust to your life" line).
- Content source: derive session templates from existing plan content in
  `plans/` where a pattern fits; otherwise write them fresh in the coaching
  voice conventions (efforts not intervals, rest as strategy). No fabricated
  physiology, no watts prescriptions without FTP — use RPE and time.
- Footer line (fixed): "If you do it, tell me how it felt — that's the whole
  price." Nothing else is pitched inside the block.
- Tests: each archetype renders, hours scaling sane (3h input never yields a
  14h week), race framing correct at 6/10/20 weeks out, output contains no
  template placeholders.

## WS-C — Prep-kit day-0 delivery email + coverage

1. New step 0 (`delay_days: 0`) in BOTH `nurture_v1` variants and
   `road_nurture_v1` for prep_kit_gate enrollments — template
   `prep_kit_delivery`, subject `your {race_name} prep kit`. Body is the
   download shape: thanks for grabbing the {race_name} kit — here's your
   link so you don't lose it: https://gravelgodcycling.com/race/{race_slug}/prep-kit/
   … any questions, hit reply. Use mustache conditionals: if `race_slug`
   missing from source_data, drop the link line (copy still works). Road
   version links roadielabs.com and keeps the deadpan accent.
   CAUTION: nurture sequences also trigger from non-kit sources — the step-0
   email must only apply to prep_kit_gate enrollments. If per-source steps
   aren't expressible in the sequence schema, split a `kit_delivery_v1`
   sequence triggered alongside nurture for prep_kit_gate (enroll() dedup
   keys on sequence_id+email, so this is safe); pick whichever is smaller
   and DOCUMENT the choice in the commit message.
2. Friend-gate the copy. It's a transactional-shaped email; unsubscribe
   footer stays (engine adds it).
3. Coverage checker `scripts/check_prep_kit_coverage.py`: for every slug in
   web/race-index.json (and roadie equivalent if reachable), verify
   `/race/{slug}/prep-kit/` returns 200 (send the `GG-MissionControl/1.0`
   UA — default UAs get 403'd). Output a table; exit 1 if any race that has
   the gate form 404s. Fix the-mid-south by generating its kit page
   (`wordpress/generate_prep_kit.py`) — flag in the recap if deploy access
   is unavailable so Matt/Claude can push it live.
4. Tests: sequence-schema tests for the new step-0 path (mirror
   `test_sequence_engine.py` idioms), template rendering with and without
   race_slug, no double-send to existing enrollments (the new step must not
   fire for contacts already past step 0 — verify engine behavior and add a
   regression test).

## WS-D — XC lifecycle mirrors

1. `mission_control/config.py`: add `"xcskilabs": os.environ.get("XC_RACE_DATES_URL",
   "https://xcskilabs.com/race-dates.json")` to RACE_DATES_URLS.
2. Sequences: `xc_race_countdown_16_v1`, `xc_race_countdown_8_v1`,
   `xc_race_debrief_v1` — brand `xcskilabs`, deadpan-warm accent (see brand
   table in docs/email-voice-model.md), templates mirroring the road set
   with ski language (no "saddle"/"rode" — "how'd the race go? happy with
   how you skied?"). Register-gate all copy.
3. Add `("xcskilabs", 16/8)` to `_SEQUENCE_IDS` in
   `services/race_countdown.py` and `"xcskilabs"` to `_SEQUENCE_IDS` in
   `services/race_debrief.py`.
4. Tests mirror `test_race_countdown.py` / `test_race_debrief.py` brand
   cases. Note: countdown windows are season-agnostic (weeks-out math), no
   inverted-season special-casing needed here.

## Verification (run before claiming done)

- `python -m pytest mission_control/tests/ scripts/ -q` — zero failures in
  touched files (suite has ~76 pre-existing unauthenticated-client failures;
  do not fix those here, do not add new ones — compare against a baseline
  run on your starting commit).
- `python3 scripts/friend_test.py --draft-file <new-copy>.md --gate` exit 0.
- `python3 scripts/draft_race_reply.py --debrief --reply-file <mendik.txt>`
  produces a sane draft (include the fixture).
- `python3 scripts/render_bridge_block.py --archetype comeback --hours 6`
  renders clean.
- Do NOT push. Commit to your branch; Claude reviews and merges. Railway
  auto-deploys main — an unreviewed push IS a deploy.
