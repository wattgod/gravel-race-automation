# Spec: Weeks-to-Race Lifecycle Trigger ("Race Countdown")

**Status:** SPEC — not yet built (Jul 2026)
**Owner:** Mission Control (`mission_control/`), both brands
**Why:** The patio11 move — lifecycle email tied to *user state*, not signup-day
drip. We know each lead's race (from capture `source_data.race_slug`) and each
race's date (`race-data/*.json` → `vitals.date_specific`, ~100% coverage both
brands). "Your race is 16 weeks out — this is the week a plan matters most" is
a service with a buy button, timed to when buying intent naturally peaks. The
single highest-leverage email not yet built.

---

## 1. Data flow

```
race-data/*.json (vitals.date_specific, e.g. "2026: May 30")
      │  build step per brand
      ▼
web/race-dates.json   {"unbound-200": "2026-05-30", ...}   ← deployed with site
      │  fetched daily over HTTPS by Mission Control
      ▼
countdown job (daily, 14:00 UTC, APScheduler next to process_sequences)
      │  joins: contacts-with-race  ×  race dates  ×  thresholds
      ▼
enroll(email, name, "race_countdown_{16|8}_{brand}_v1", source="race_countdown",
       source_data={race_slug, race_name, race_date, weeks_out})
      │  existing engine: 15-min send loop, brand sender, UTM, unsubscribe
      ▼
one email per threshold crossing
```

### 1a. Publish race dates (per brand repo)

New script `scripts/generate_race_dates.py` in BOTH repos:
- Parse `vitals.date_specific` ("2026: May 30" → `2026-05-30`). Rules:
  strip the `YYYY:` prefix, parse the remainder with the year; skip entries
  without a parseable day ("2026: October TBD" → omit). ~19 gravel + 1 road
  races are unparseable — omitted, never guessed.
- Emit `web/race-dates.json`: `{slug: "YYYY-MM-DD"}` — flat, small (~15KB).
- Deploy with the sitemap batch (gravel: existing deploy flow; road: SCP).
- Regenerate whenever race dates are edited; wire into the existing
  post-batch checklists.

### 1b. Contact → race resolution (Mission Control)

A contact "has a race" when any `gg_sequence_enrollments` row for that email
has `source_data.race_slug` (set by the worker for `race_profile`,
`prep_kit_gate`, `race_quiz`, `date_reminder` captures). Most recent
enrollment wins if a contact has several races. Brand comes from
`source_data.brand` (present since the Jul 2026 brand-routing work; absent →
gravelgod).

## 2. Thresholds and sequences

Two thresholds, each its own single-step sequence per brand (4 sequences
total). Separate sequences (rather than steps in one) because `enroll()`
already dedups per `(sequence_id, contact_email)` — a contact crossing 16w
then 8w gets each email exactly once, and late-captured contacts (race
already <16w away) cleanly get only the 8w email.

| Sequence id | Trigger window (weeks_out) | Email |
|---|---|---|
| `race_countdown_16_gg_v1` / `_rl_v1` | 17 ≥ w ≥ 12 | "the honest window" — 16-ish weeks is the full-runway plan; what base weeks are; calendar math from §B of the council critique |
| `race_countdown_8_gg_v1` / `_rl_v1` | 9 ≥ w ≥ 5 | "triage math" — 8 weeks is still worth structuring, here is what is and isn't achievable; explicitly honest about what's gone |

Windows are ranges (not exact-week equality) so the daily job catches
contacts captured mid-window and tolerates missed job runs. Below 5 weeks:
no email — an 3-week "plan" pitch would spend trust for low-quality sales.
`trigger` field: `"race_countdown_16"` / `"race_countdown_8"` (not
`new_subscriber` — keeps them out of the welcome-enrollment path).

## 3. The countdown job

`mission_control/services/race_countdown.py`, scheduled daily in
`scheduler.py` (`@scheduler.scheduled_job("cron", hour=14, id="race_countdown")`):

1. Fetch both `race-dates.json` files (10s timeout; on failure log + skip —
   the job self-heals tomorrow). Cache last-good copy in memory.
2. Query enrollments with non-empty `source_data->>race_slug`, dedupe to
   latest per email.
3. For each: `weeks_out = (race_date - today).days / 7`. Skip if date past.
4. Suppressions (in order):
   - customer suppression — reuse the engine's existing check
     (`gg_athletes.plan_status` in delivered/approved/audit_passed);
   - unsubscribed contacts (engine already refuses; check early to avoid
     log noise);
   - contact already enrolled in the OTHER countdown tier for the SAME race
     within this race cycle (16w email then 8w email is allowed and intended;
     the guard is only against re-enrollment across years — compare
     `source_data.race_date`);
   - a pitch email sent to this contact in the last 7 days (avoid stacking
     on top of welcome/nurture day-7/day-10 pitches): check
     `gg_sequence_sends` for anti_pitch/repitch templates.
5. Enroll in the matching brand+threshold sequence.
6. `db.log_action("race_countdown_enrolled", ...)` per enrollment; one
   summary log line per run.

## 4. Email copy (to be written with the email-sequences skill)

Both emails follow the honest-urgency register proven by the council pass:
- 16w: the window email. Base-weeks arithmetic ("the weeks you lose come off
  the front, and the front is where the base lives"), $249-cap-favors-early
  framing, sample-week proof block, one verb CTA. GG warm / RL audit-finding.
- 8w: the triage email. Concession-led ("a chunk of the window is gone — here
  is what 8 structured weeks still buys"), explicitly disqualifies <5w buyers
  ("if your race is three weeks out, keep the money"). Trust deposit + sale.
- {race_name} is SAFE here (unlike the welcome pitch): enrollment guarantees
  `source_data.race_name` exists.

## 5. Edge cases

- **TBD/unparseable dates:** omitted from race-dates.json → contact simply
  never enrolls. Never guess.
- **Stale dates (48 known on gravel):** a past date is skipped; when the
  date is refreshed the contact enrolls on the next run if in-window.
- **Race date moves:** job reads current dates daily; enrollment's
  `next_send_at` is immediate (single step, delay 0) so drift risk is ~1 day.
- **Multi-race contacts:** latest capture wins v1; per-race fanout is v2.
- **Volume guard:** cap enrollments per run (e.g. 200) with a log warning —
  protects against a bad dates file mass-enrolling.

## 6. Build checklist

1. `scripts/generate_race_dates.py` ×2 repos + deploy + tests (parse rules,
   TBD omission).
2. `race_countdown.py` job + scheduler wiring + tests (window math,
   suppressions, brand routing, year-cycle guard).
3. 4 sequence defs + 4 templates (2 per brand), council-checked.
4. Verify end-to-end with a synthetic contact (test email, fake race 16w out).
5. Activate: sequences `active: True`, deploy race-dates.json both sites,
   push (Railway redeploys MC).
```
