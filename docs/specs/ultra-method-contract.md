# Ultra Method Contract — v1 (G0.5)

Normative implementation contract for all Gravel God ultra-bikepacking training
products. Authored by Fable from
`docs/whitepapers/ultra-bikepacking-training-white-paper.md` (v1.1); sol review
then OWNER APPROVAL (D-M1) required before any engine work implements it.
WS-P (TP masters) and WS-C (custom pipeline) both implement THIS document; any
deviation in either implementation is a defect. All prescriptions are coaching
positions (`[position]` tier) unless marked otherwise; the demand profile they
serve is `[verified]` (see white paper §2).

Pilot scope: level = Finisher. Durations = 16w and 24w masters; custom 16–36w.
Units: hours = moving time; "long day" = the week's longest ride; RPE = 1–10.

## 1. Prerequisites (numeric definition of "not playing catch-up")

An athlete is PREPARED to start an ultra plan when ALL hold:
- P-1: ≥12 consecutive weeks of riding ≥4 days/week (any intensity) before week 1
- P-2: rolling 4-week average ≥6.0 h/week at plan start
- P-3: at least one ride ≥4 h within the last 6 weeks
- P-4: no current injury limiting consecutive riding days

CATCH-UP state = runway <16 weeks to race OR any prerequisite unmet. Catch-up
athletes are SERVED (custom pipeline only, never a marketed SKU — spec rule R2)
under §12 rules and the honest framing template (§12.3).

## 2. Weekly hours prescription (Finisher)

| Phase | 16w weeks | 24w weeks | Hours band | Long day | Notes |
|---|---|---|---|---|---|
| Testing week | 1 | 1 | 5–7 | 2.5h RPE-calibration ride | 360 Testing Week opener (existing protocol, TP 230732 lineage) |
| Base | 2–5 | 2–9 | 7–10 | 3→4.5h progression | 1 intensity session/wk max |
| Durability build | 6–10 | 10–16 | 9–13 | 4.5→6h; back-to-backs enter §4 | 2 quality sessions/wk cap |
| Specificity + simulation | 11–13 | 17–20 | 10–14 peak; SIM block §5 | 6h and/or SIM | 1 intensity/wk; systems work scheduled |
| Consolidation/taper | 14–16 | 21–24 | 12→8→6 taper per §7 | 4h wk-14/21, then ≤3h | nothing new enters |

Load progression rule: week-over-week hours increase ≤10% except entering a
recovery week (down) or the simulation block (governed by §5). Recovery weeks
(§6) run at 60–70% of the preceding week's hours with zero intensity sessions.

## 3. Intensity (frequency and role)

- Base: 1 session/week — tempo/sweet-spot durability placement (final third of a
  ride), RPE 6–7. No VO2 work in base.
- Durability build: 2 sessions/week (Masters cap also 2 — see §6): one
  fatigue-resistance session (quality work placed ≥2h into a long ride), one
  standalone tempo/threshold session RPE 7–8.
- Specificity: 1 session/week, fatigue-resistance placement only.
- Consolidation/taper: week 14/21 one short tempo touch; nothing harder after.
- Role (white paper §2): intensity maintains the ceiling the all-day pace draws
  against. It is never the plan's center. All targets are RPE-primary with
  power/HR as secondary reference (`[position]`; ultras are paced by judgment).

## 4. Long days and back-to-backs

- Long-day dose progresses per §2 table; every long ride from build onward
  carries the in-ride fueling protocol (≥60 g/h carbohydrate target, trained not
  assumed) and, from week 8/12 (16w/24w), rides loaded (race pack weight ±20%).
- Back-to-back entry: build phase week 7 (16w) / week 11 (24w): pattern = long
  day + 60–70% long day the following day.
- Max stacking outside the simulation block: 2 consecutive long days.
- After any back-to-back: ≥1 full rest or ≤1h recovery-spin day before the next
  quality session.
- The week containing a back-to-back counts it as BOTH the long day and one of
  the week's quality sessions (it displaces a standalone intensity session).

## 5. The simulation block (defining feature)

- Placement: 16w → weeks 11–12 boundary (end of specificity's first week).
  24w → weeks 17–18 boundary. Custom lengths: at 75% of runway, never inside the
  final 3 weeks.
- Shape: 2–4 consecutive days, fully loaded, race systems mandatory (pack, sleep
  system if the athlete will bivvy in the race, navigation, planned resupply
  cadence). Daily duration: day 1 = 100–120% of current long-day dose;
  subsequent days = 70–90% of day 1.
- Overnight: sleeping out is ENCOURAGED where the athlete's race requires bivvy
  competence; sleep DURATION is never restricted — R4: no sleep-deprivation
  training, anywhere, ever. The rehearsed low point (white paper §7) is
  calories/fatigue-based only.
- Systems checklist (must appear in the block's calendar notes): contact points,
  pack balance, sleep-system deploy/stow time, fueling execution vs plan,
  resupply timing, navigation trust, morning-start friction.
- Mandatory recovery window: ≥4 days at recovery volume (≤60% baseline, no
  intensity) immediately after the block. This is a hard QC assertion.
- 24w plans additionally get a MINI-simulation (overnight, 2 days) at weeks
  13–14 as a systems shakedown; 16w plans do not (insufficient runway).

## 6. Recovery cadence and Masters interaction

- Standard: every 4th week is a recovery week (60–70% hours, no intensity).
- Masters (50+): every 3rd week, per the existing Masters rule; Masters also
  cap at 2 quality sessions/week in ALL phases (they already are, by §3) and
  insert one extra rest day in simulation recovery (≥5 days).
- Phase tables in §2 flex accordingly: engines compute recovery placement from
  cadence rules, not hardcoded week numbers; the §2 table assumes standard
  cadence.

## 7. Testing cadence

- Week 1: 360 Testing Week (existing 7-day RPE protocol) — unchanged opener.
- Retests (abbreviated, 2-day): 16w → week 9. 24w → weeks 9 and 17 (week-17
  retest precedes the simulation block; if the calendar collides, retest first).
- ALL testing-week copy must be parameterized by plan length (the current
  "next 11 weeks"/"week seven" hardcodes are defects when reused here).

## 8. Strength and mobility (positional sustainability track)

- Base: 2 sessions/week (trunk endurance, grip/forearm, posterior chain, neck
  endurance — white paper §5 bias).
- Build + specificity: 1–2/week, reduced to 1 in simulation weeks; NEVER the day
  before a long day or back-to-back.
- Consolidation/taper: 1 maintenance session/week through week 14/21, then none
  in the final 2 weeks. None during the simulation block itself.
- Sessions come from the existing strength system's library; ultra products
  default the strength track ON.

## 9. End-state: race start, not race day

The final week models a multi-day race START (replacing the single-Saturday
model): travel/logistics buffer days, 2 short opener spins (≤1h, RPE ≤5 with
3×1min leg-openers), equipment-final checklist note, carb-normal eating (no
race-morning loading theatrics), and a day-0 note covering start-line execution:
conservative first-day pacing (the plan's stated rule: day 1 ends with the
athlete feeling they underdid it — `[position]`). No workout is scheduled on or
after race start; the plan's last scheduled item is the day-before opener.

## 10. Race-variation rules (per-race SKUs and custom targets)

A race's demand profile perturbs the neutral master ONLY in these bounded ways:
- Climbing-heavy (Tour Divide, CTR): long-day routes prescribed with climbing
  targets scaling to race's per-day gain; low-cadence seated strength-endurance
  placements in build; gearing note in systems checklist.
- Technical surface (CTR, Atlas): handling blocks appended to 2 base long days;
  simulation terrain instruction upgraded; no change to load numbers.
- Altitude flag (per existing rule: race ASL >5,000 ft): existing altitude-note
  protocol applies unchanged.
- Heat flag: heat-adaptation notes in the final 3 weeks (existing protocol).
- Free-route races (TCR-class): navigation/route-research tasks appear as
  scheduled off-bike items in specificity weeks; systems checklist gains
  route-plan validation.
- Race length tier: races with expected finish >10 days bias the 24w SKU in all
  recommendations (guide + descriptions may state this; both SKUs remain valid).
No other perturbation is permitted without a contract revision.

## 11. Availability scaling (what bends when hours don't fit)

When an athlete's available hours < prescription band (custom pipeline; also the
descriptions' honesty line), bend in THIS order:
1. Mid-week aerobic volume shrinks first (down to 45min floors).
2. Standalone intensity drops from 2→1 (fatigue-resistance session survives).
3. Long-day dose reduces LAST, never below 70% of prescription.
4. Back-to-backs become long day + 50% day before disappearing entirely.
5. The simulation block is NEVER cut below 2 days for a plan ≥16w; below that
   the athlete is in catch-up state by definition.
Floor: an athlete averaging <6 h/week available cannot be honestly prepared for
a Tour Divide-class race on any timeline this contract covers; products must say
so (fit filter, not upsell).

## 12. Boundary behavior

- 12.1 Runway >36 weeks (custom): hold-then-build — maintain base (§2 base
  phase pattern) until exactly 24 weeks remain, then run the 24w structure.
  Never stretch phases to fill arbitrary runway.
- 12.2 Custom lengths 16–36w: run the 24w phase RATIOS (testing 1w, base 33%,
  build 29%, specificity 21%, consolidation 17%, rounded to whole weeks, ±1wk
  honoring recovery cadence); ≥20w gets the mini-sim, <20w does not.
- 12.3 Catch-up (<16w or prerequisites unmet): serve with a compressed
  durability-first structure (no marketed format name): testing week, then
  build-biased weeks at the athlete's real availability, ONE 2-day simulation if
  ≥10w runway, consolidation ≥2w. The plan's welcome/Day-1 note uses the honest
  framing template: what full preparation looks like, what this timeline can and
  cannot deliver, and the specific compromises made. No catch-up plan may carry
  the "Ultra" SKU naming (R2).

## 13. QC assertions derived from this contract (ultra QC profile inputs)

Machine-checkable minimums for any generated ultra plan: exactly one testing
week at week 1; retest weeks per §7; recovery cadence per §6 (3 or 4-week per
Masters flag); simulation block present with §5 placement/shape and the ≥4-day
(≥5 Masters) recovery window after; back-to-back stacking ≤2 days outside SIM;
week-over-week hours ramp ≤10% outside recovery/SIM; strength absent from final
2 weeks and SIM; no scheduled workout on/after race start; zero sleep-
deprivation content (banned-phrase list); testing copy contains no hardcoded
week counts foreign to the plan's length; race-variation perturbations within
§10's enumerated set.

## 14. Versioning

This contract is versioned; engines record the contract version they implement.
Changes require sol review + owner approval, then propagate to BOTH engines in
the same release cycle.
