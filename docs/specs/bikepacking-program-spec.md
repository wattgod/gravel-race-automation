# Bikepacking Product Program: Guide + TP Plans + Custom Pipeline

Drafted 2026-07-20 (Fable). Status: awaiting codex-sol adversarial review, then owner
gates per workstream. Execution model per owner: **Fable = spec/dispatch/review/
verify/commit; codex = execution; codex-sol = adversarial review of this spec and of
each workstream's output.** This program IS Phase 6 of
`docs/specs/road-catalog-migration-spec.md`, executed.

## Evidence base (binding)

- `docs/whitepapers/ultra-bikepacking-training-white-paper.md` (v1, evidence-tiered)
- `docs/research/ultra-bikepacking-coaching-market.md` (verified/cited market research)

Hard rules inherited from both: **(R1)** no copy anywhere may claim or imply
first-person ultra-racing experience; authority = method + evidence + the rated race
database. **(R2)** no 12-week ultra plan product exists in this program — formats are
4-month and 6-month (market-verified). **(R3)** no fabricated proof of any kind
(testimonials, results, anecdotes). **(R4)** sleep-deprivation training is excluded
from all products. **(R5)** every load-bearing claim in customer-facing content
traces to a white-paper tier or a cited source; `[position]`-tier claims are stated
as coaching positions, not facts.

## Voice/register (binding)

Guide prose: the established guide register — Claude-authored, plain and useful,
Matti's voice leaking through naturally, "not trying too hard" (owner precedent from
the road guide build). Normie gate applies (no unexplained TSS/FTP/CTL jargon). Plan
descriptions: the C5 seven-tier system-sans template + Built-For register (fit
claims, no selling verbs, no outcome promises). CTAs use corner canon where coaching
appears. Editorial-loud/offer-quiet split holds everywhere.

---

## WS-G — The Bikepacking Guide (lead magnet, gravelgodcycling.com)

**Template**: `guide/gravel-guide-content.json` schema (title/subtitle/
meta_description/personalization/glossary/chapters[8] with sections[]), rendered by
`wordpress/generate_guide.py`, email gate on chapters 4–8
(`build_chapter_email_capture`, capture POSTs to the fueling-lead-intake worker —
live infra, do not rebuild), GA4 guide events, end-of-chapter quiet capture.

**Deliverables**
1. `guide/bikepacking-guide-content.json` — 8 chapters mirroring the gravel guide's
   arc, adapted to the ultra demand profile:
   1. What Ultra Bikepacking Actually Asks (demand profile: repeatability not
      peak-day; the 100mi/5,500ft-per-day framing; who these races are for)
   2. Choosing Your Race (the rated ultra shelf — Tour Divide, CTR, TCR, Atlas,
      Badlands et al., tiers/scores from race-data; free-route vs fixed-route)
   3. Training for Repeatability (white paper §2–4: 6–9 month horizon, base
      without catch-up, durability blocks, back-to-back days, simulation)
   4. Systems: Bike, Pack, Sleep (verified practitioner doctrine, cited; gear
      decision deadlines; test-before-race rule)
   5. The Energy Economy (in-ride fueling → daily replenishment → appetite
      management; resupply-constrained eating)
   6. The Mental Game (pre-commitment: quitting rules written in advance;
      segment thinking; rehearsed low points; "every athlete is their own worst
      blindspot" mechanism)
   7. Race Logistics (resupply mapping, navigation/route research, dot-watching
      etiquette and rules-of-the-event self-supported ethics)
   8. Simulation, Race Week & Beyond (the 2–4 day shakedown, final consolidation,
      post-race recovery and what compounding multi-day fatigue means after)
   Each chapter: 5–9 sections, glossary entries for new terms, personalization
   hooks matching the existing schema. A `sources` block per chapter mapping
   load-bearing claims → white-paper tier or URL (renderer may ignore it; it is
   the audit trail satisfying R5).
2. Generator support: parameterize `generate_guide.py` (content file + URL slug +
   GA4 label as inputs) OR a thin `generate_bikepacking_guide.py` wrapper —
   whichever the existing code structure makes least invasive; output at
   `/bikepacking-guide/`, same gate mechanics (ch 4–8), capture source value
   `bikepacking_guide` so Mission Control can branch the welcome context
   (`wb_guide`-style) without new worker code.
3. CTAs inside the guide: race pages (ultra shelf), coaching (corner canon line).
   NO plan CTAs until WS-P ships; then chapter 3/8 CTAs may point at the ultra
   plan SKUs. Never a 12-week plan CTA (R2).
4. Tests mirroring the existing guide test surface (gate present on 4–8, GA4,
   fonts, capture wiring, no-slop pass) + R1/R2 guards (banned first-person ultra
   phrases list; no "12-week" in guide copy).

**Owner gates**: D-G1 title/positioning (working title "The Bikepacking Race
Guide" under Gravel God, presented on the Ultra shelf); Matti reads full content
before deploy (fork-governance rule: no public content without his yes).

---

## WS-P — TrainingPeaks marketplace bikepacking plans

**Method source**: `../gravel-god-training-plans` — base-library engine (race-neutral
masters + variations), Durability workout library, 360 Testing Week opener
(TP 230732 precedent), strength system, description generator
(`tools/description_generator/GENERATE.md` + C5 in `qc/SOL_QC_SPEC.md`),
SWARM_RUNBOOK QC gates, TP upload last-mile (browser automation recipes in
tp-maintenance memory/docs).

**Product (from verified market evidence)**
- Formats: **16-week ("4-month") and 24-week ("6-month")** ultra plan masters —
  never 12 (R2). Market price benchmark $65–75 (UltraMTB); our band decision is
  D-P1.
- Each plan bundles the **prep guide** (WS-G content exported as the plan's
  document payload / linked hosted guide — the verified UltraMTB template: plans
  ship WITH prep education).
- Phase structure per white paper §4: base → durability build (back-to-back long
  days, fatigue-resistance sessions from the Durability library) → specificity +
  loaded simulation block (multi-day entries with explicit systems-shakedown
  instructions) → consolidation/taper. 360 Testing Week opens. Strength/mobility
  as a parallel track (positional sustainability bias). RPE-forward targets with
  power/HR as secondary (ultras are paced by judgment).
- Per-race SKUs per OD-1 (fragmentation intentional): pilot subset D-P2 —
  recommend Tour Divide, Colorado Trail Race, Atlas Mountain Race first (highest
  GG page traffic among the 14), each in both formats; race-neutral "Ultra Base"
  master underneath, race variations layered the standard way.
- Descriptions: C5 template + Built-For register; explicit horizon honesty ("this
  plan assumes N hours/week and a base of X — it is not a crash plan"); R1 guard.

**QC**: existing swarm gates (physiology validation, normie lint as C5 subset,
sol per-SKU audit) + a new ultra-specific check: no plan may schedule
sleep-deprivation training (R4) and simulation blocks must carry recovery windows.

**Owner gates**: D-P1 pricing; D-P2 pilot race subset; publish gate (plans go
private → Matti reviews → public, per the roll's standard flow).

---

## WS-C — Custom training plan pipeline: bikepacking discipline

**Source**: `../athlete-custom-training-plan-pipeline`. The pipeline already has a
discipline axis (`derive_discipline: gravel/road/mtb from target race`;
`workout_selector.py: phase × archetype × discipline`). Bikepacking becomes the
fourth discipline value, NOT a fork.

**Deliverables**
1. `derive_discipline` recognizes the ultra races (the 14 rated + any bikepacking
   race in race intake free-text) → `bikepacking`.
2. Selection rules for the discipline: durability-dominant session mix, long-ride
   progression with loaded/back-to-back variants, simulation-block insertion for
   plans ≥16 weeks, strength track default ON, RPE-forward workout targets.
3. Horizon support: verify and, if needed, extend max plan length to ≥36 weeks;
   intake accepts race dates ≥6 months out without warning. Pricing: existing
   $15/wk with cap (cap value for long horizons = D-C1; XC precedent caps at
   $249) — implement against whatever cap Matti sets, no hardcoded new number.
4. Intake: OPTIONAL ultra fields (target daily riding hours, prior multi-day
   experience, sleep-system ownership) — all recoverable-optional per the
   order-killer rule; absence never blocks plan generation.
5. Plan-truth/compliance gates extended to the new discipline; one new case in the
   daily E2E harness (~/gg-e2e/) exercising a bikepacking intake end-to-end.
6. Delivery copy (plan notes, welcome doc) inherits R1–R5.

**Owner gate**: D-C1 pricing cap; pipeline changes reviewed by sol before merge
(standing pipeline practice), never `git add -A`, worktree if the concurrent
committer is active.

---

## Sequencing & process

- **G0 (now)**: codex-sol adversarial review of THIS spec against all three repos;
  Fable verifies sol's findings against live code, folds confirmed ones.
- **G1**: WS-G build (codex executes content + generator; Fable verifies, tests,
  Matti reads content, deploy via existing guide deploy path).
- **G2**: WS-P engine + pilot SKUs (codex in gravel-god-training-plans; sol QC per
  SKU; Matti pricing + publish gates).
- **G3**: WS-C pipeline discipline (codex; sol review; E2E green).
- WS-G and WS-P engine work may run in parallel AFTER G0 (different repos); WS-P's
  bundled-guide payload depends on WS-G content freeze.
- Each workstream: own commits, targeted staging, concurrent-session check, tests
  green before any commit, no deploy without the workstream's owner gate.

## Anti-goals

No new brand. No 12-week ultra SKU ever. No first-person ultra narrative. No
fabricated proof. No sleep-deprivation training content. No claiming the white
paper's `[position]` tier as settled science in customer copy.

## Owner decisions — RESOLVED 2026-07-20

- **D-G1 (title)**: "The Complete Bikepacking Race Training Guide" — mirrors the
  gravel guide's exact title pattern ("The Complete Gravel Racing Training Guide");
  subtitle: "Everything you need to know about ultra-distance bikepacking races —
  from systems to training to the mental game." Fable's call per owner delegation;
  positioned under Gravel God on the Ultra shelf, URL /bikepacking-guide/.
- **D-P1 (plan pricing)**: owner ruled $65–75 too low. Set **$129 (16-week) /
  $199 (24-week)** — per-week parity with the $99/12-week gravel ceiling
  (~$8.25/wk), sits above the whole existing catalog as the premium anchor the
  cross-discipline teardown recommended, justified by length + bundled guide.
  Constants live in one place; trivially adjustable at publish gate.
- **D-P2 (pilot SKUs)**: Tour Divide, Colorado Trail Race, Atlas Mountain Race
  (highest-traffic ultra pages), each in both formats, over a race-neutral Ultra
  Base master.
- **D-C1 (custom cap)**: SAME cap as all other races — $15/wk, existing $249 cap;
  no new pricing logic, long horizons simply hit the cap.
- **D-X1**: Ultra shelf (migration-spec Phase 5) ships WITH WS-G in gate G1 —
  owner confirmed.
