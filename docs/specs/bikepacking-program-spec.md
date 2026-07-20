# Bikepacking Product Program: Guide + TP Plans + Custom Pipeline — v2

v2 drafted 2026-07-20 after codex-sol G0 review returned NO-GO with 8 blockers; all
were verified against live code and are folded below. Status: awaiting G0.2 (sol
re-review of THIS version), then owner gates per workstream. Execution model:
**Fable = spec/dispatch/review/verify/commit; codex = execution; codex-sol =
adversarial review of spec and outputs.** This program IS Phase 6 of
`docs/specs/road-catalog-migration-spec.md`, executed; per D-X1 the Ultra shelf
(that spec's Phase 5) ships in gate G1 as part of WS-G's scope.

## Evidence base

- `docs/whitepapers/ultra-bikepacking-training-white-paper.md` v1.1 (owner review
  pending; the §7/§10 sleep contradiction sol found is fixed — rehearsed low
  points exclude sleep restriction). Owner approval of the white paper happens AT
  G0.5 (authoritative; the method contract and white paper are reviewed together —
  D-M1). G1's content gate then covers guide copy only.
- `docs/research/ultra-bikepacking-coaching-market.md` (verified market research).
- GA4 (90d, pulled 2026-07-18): bikepacking page views — torino-nice-rally 40,
  colorado-trail-race 28, tour-divide 30 (17+13 across two path rows), badlands 23,
  atlas-mountain-race <10.

## Hard rules (R1–R5) and their enforcement scope

| Rule | Scope (all customer-visible artifacts) | Enforcement point |
|---|---|---|
| R1 no first-person ultra claims | guide copy, plan titles/descriptions, ZWO text, calendar notes, custom-plan guides/welcome docs | banned-phrase guard in each repo's test/QC layer |
| R2 no 12-week ultra SKU | TP catalog + marketing copy. NUANCE (custom pipeline): an athlete intake <16 weeks from an ultra race is SERVED, not rejected — the plan is framed honestly as time-limited preparation ("you are playing catch-up; here is what fits") and never titled or sold as an ultra plan format | registry/QC checks (WS-P); framing template + test (WS-C) |
| R3 no fabricated proof | everywhere | existing anti-fabrication guards + review gates |
| R4 no sleep-deprivation training | white paper §10, all plan/guide content; simulations must carry recovery windows | ultra QC profile checks + banned-content guard |
| R5 claims trace to evidence tiers | guide (per-chapter sources block, schema-validated), plan descriptions, custom guide ultra sections | WS-G: JSON schema validator. WS-P: C5-ultra requires a `sources:` sidecar per SKU description (claim → tier/URL), checked by the ultra QC profile's audit step. WS-C: training-guide builder emits the same sidecar for ultra sections; plan-truth validates its presence. |

Voice/register: unchanged from v1 (guide register per road-guide precedent; C5 +
Built-For for descriptions; corner canon for coaching CTAs; Normie gate).

---

## G0.5 — THE METHOD CONTRACT (new; blocks WS-P and WS-C engine work)

Sol's core finding: no normative 16/24-week method exists, and letting two repos
implement it independently invites incompatible products. Therefore a single
deliverable precedes both engines:

**`docs/specs/ultra-method-contract.md`** (authored by Fable from the white paper,
sol-reviewed, Matti-approved) defining, week by week for 16w and 24w:
- prerequisites (base hours floor; what "not playing catch-up" means numerically)
- phase boundaries (base / durability build / specificity+simulation /
  consolidation-taper) for each duration
- recovery cadence (incl. Masters every-3rd-week rule interaction)
- consecutive-long-day rules (when back-to-backs enter, max stacking, recovery after)
- simulation block: timing, length (2–4 days), loaded requirement, systems
  checklist content, mandatory recovery window after (R4)
- testing cadence: 360 Testing Week opener + retest schedule for 16/24w (current
  engine retests once mid-plan and its COPY hardcodes "next 11 weeks"/week-seven
  retest — the contract defines correct cadence and the copy templates must be
  parameterized by plan length)
- strength track periodization incl. taper behavior
- end-state: multi-day race-start behavior replacing the single-Saturday race-week
  model
- normative weekly volume/load progression (hours and long-day dose per week,
  per duration), intensity-session frequency by phase, taper/consolidation load
  numbers, athlete-availability scaling rules (what bends first when weekly hours
  are below prescription)
- race-variation rules (how a race's demand profile perturbs the neutral master)
- boundary behavior: below minimum viable runway (<16w catch-up framing, R2
  nuance) and beyond 36 weeks (hold-then-build rule)
- custom-pipeline adaptation rules: mapping to arbitrary lengths 16–36w

WS-P and WS-C both implement THIS document. Any deviation found in either
implementation is a defect, not a choice.

---

## WS-G — The Bikepacking Guide + Ultra shelf

Sol verified the "existing guide path" claim false: `generate_guide.py` is a
DEPRECATED monolith hardcoded to the gravel content file; the live system is
`generate_guide_cluster.py` with a fixed 8-chapter metadata map, FormSubmit chapter
gate (tests require it), worker-based end-of-chapter capture with fixed source
`training_guide`, and /guide-hardcoded deploy, sitemap, and validation. The worker
allowlist rejects unknown sources. WS-G is therefore a **multi-guide architecture**
job with this explicit inventory:

1. **Cluster generator parameterization** (`generate_guide_cluster.py`): extract a
   GuideConfig (content file, url base, chapter metadata map, GA4 event labels,
   localStorage keys, gate form subject/source labels, CTA set, glossary). Gravel
   guide = config #1 producing byte-identical output (regression-tested); the
   bikepacking guide = config #2 at `/bikepacking-guide/` with collision-free
   storage keys and GA4 labels.
2. **Content**: `guide/bikepacking-guide-content.json` — 8 chapters as v1 described
   (demand profile / race selection on the Ultra shelf / training for repeatability
   / systems / energy economy / mental game / logistics / simulation+race week),
   each chapter carrying a `sources` block (claim → white-paper tier or URL); a
   JSON schema validator enforces the block's presence and shape (R5).
3. **Gate + capture — worker-first (binding repo rule CLAUDE.md "every email form
   MUST POST to its Cloudflare worker"; the gravel cluster's FormSubmit gate is a
   grandfathered violation and is NOT copied)**: chapter 4–8 gate POSTs to the
   fueling-lead-intake worker with honeypot (unlock never network-blocked;
   FormSubmit allowed only as documented no-JS fallback, per the XC gate
   precedent), and the end-of-chapter quiet capture uses the same worker; both use
   NEW source value `bikepacking_guide`:
   - worker.js allowlist + tests + wrangler deploy (the allowlist currently 400s
     unknown sources — verified)
   - Mission Control: map `bikepacking_guide` → guide-context welcome branch (the
     wb_guide-style branch; confirm mapping rather than falling through to
     `new_subscriber` default)
4. **Deploy/validation surface**: push_wordpress sync for the new cluster path;
   generate_sitemap.py addition; validate_deploy.py checks; robots/llms.txt
   mention (llms generator already regenerates at deploy).
5. **CTA truth**: the cluster's always-rendered training/coaching CTA block becomes
   config-driven: bikepacking guide launches with CTAs → Ultra shelf race pages +
   coaching (corner canon). Plan CTAs are added only when WS-P SKUs are live, and
   then point at the 16/24-week SKUs (never 12-week — R2 guard in tests).
6. **Ultra shelf (from migration spec Phase 5, pulled into this gate per D-X1)**:
   rankings/search/homepage surfaces label bikepacking+mtb as "Ultra &
   Bikepacking"; race-page custom-plan CTA suppressed for discipline=bikepacking
   (until WS-C ships, then it may point to the custom pipeline with honest
   horizon framing); coaching CTA unchanged. NOTE: gravel race-page generator work
   must respect whatever branch/pilot state the concurrent race-page redesign
   session has live — coordinate at execution time, verify live markers first.
7. **Tests**: gravel-guide byte-parity regression, new-guide gate/capture/GA4/
   fonts/slop, R1/R2 banned-phrase guards, sources-schema validation, sitemap and
   deploy-validation coverage.

**Owner gate G1**: Matti reads full guide content + approves shelf presentation
before deploy.

---

## WS-P — TrainingPeaks marketplace ultra plans

Reality (sol-verified): registry masters max out at 16 weeks; the engine has
generic phases, ONE weekly long ride, an "ultra" selection overlay but no
simulation block, a single-Saturday race-week model, one mid-plan retest with
hardcoded-length copy. The QC contract (C5) assumes one-day races, 7-tier copy,
`<Race> · <Tier> · <N>wk` titles, fixed prices. The physiology validator
classifies by title keywords and never fails its exit status.

**Deliverables (all implement the G0.5 method contract):**
1. **Engine**: 16w and 24w ultra masters — schedule_builder support for
   consecutive long-day patterns and the simulation block; multi-day end-state
   replacing race-Saturday; retest cadence + testing-week copy parameterized by
   plan length; Masters interaction per contract; strength track wiring.
2. **Product structure** (resolves sol's SKU-mapping gap): one race-neutral
   **Ultra Base** master per duration (2 masters). Pilot SKUs = per-race
   variations for **Tour Divide, Colorado Trail Race, Badlands** (GA4-cited above;
   Torino-Nice excluded as a non-competitive rally; Atlas dropped — traffic
   evidence didn't support it) × both durations = **6 SKUs**, single level
   ("Finisher") for the pilot. Titles: `<Race> · Ultra · 16wk|24wk`. Prices:
   $129/$199 (D-P1, constants in one place).
3. **Guide delivery — decided**: the repo's existing proven mechanism — hosted
   guide link as its own Day-1 calendar note (SWARM_RUNBOOK §G, "NO PDF",
   reference notes 2393661-667). The note links the WS-G hosted guide. No TP
   attachment experiments.
4. **Ultra QC profile** (versioned, replaces "run existing gates"): C5-ultra
   variant (title/price/copy-structure rules for the 2-duration ultra family;
   multi-day end-state expectations; 7-description structure adapted or
   explicitly waived per section); physiology validator gains ultra checks
   (phase sequencing vs contract, simulation presence + recovery window, no
   sleep-dep content, consecutive-day rules) AND a failing exit status; R1/R2
   description guards; sol per-SKU audit stays.
5. **Descriptions**: C5-ultra + Built-For; explicit prerequisites line (base
   hours floor from the contract; "this is not a crash plan").

**Owner gates**: publish flow (private → Matti review → public) per the roll.

---

## WS-C — Custom pipeline: bikepacking discipline (full migration map)

Sol-verified reality: `derive_discipline` returns gravel/road/mtb;
`build_race_snapshot.py` labels discipline from source DIRECTORY (so the 14
bikepacking profiles enter as explicit `gravel`, which outranks name keywords);
three-discipline assumptions live in the selection overlay config, training-guide
branding/methodology dispatch, and fueling speed/duration math; generation clamps
at 4–26 weeks; date-derived classification clamps at 24 and defaults to 12.

**Migration map (every consumer changes together, one commit series):**
1. `build_race_snapshot.py`: discipline from `gravel_god_rating.discipline` (or
   race JSON field), not directory; regenerate the snapshot; assert the 14 races
   carry `bikepacking`.
2. `archetype.py derive_discipline`: fourth value + race-name keyword fallback.
3. Scheduling layer — where the method actually lives (workout_selection.yaml
   only rotates alternatives): `calculate_plan_dates.py` (runway/phase windows),
   the calendar/block builders (back-to-back long-day patterns, simulation-block
   insertion ≥16w, strength activation), race-day overlays (multi-day start
   behavior), `block_compliance.py` and the plan-truth validator (both must
   assert the ultra contract, not just tolerate it). `workout_selection.yaml`
   gets only the selection-rotation overlay (durability-dominant, RPE-forward).
4. `training_guide_builder.py`: bikepacking branding + methodology dispatch (ultra
   sections sourced from white paper / guide content, R1-guarded).
5. `calculate_fueling.py`: ultra speed/duration assumptions (multi-day energy
   economy framing per contract).
6. Checkout/webhook metadata: discipline label; runway rules — sellable horizon
   16–36w for bikepacking targets; generation clamp raised to 36 for the
   discipline; <16w intake → catch-up framing template (R2 nuance), never a
   12-week default for ultra targets (the 12-week fallback branch is guarded by
   discipline).
7. Intake (public questionnaire is a live Elementor widget — repo CLAUDE.md
   pitfall): optional ultra fields ship ONLY in the pipeline's own intake schema +
   parsing first; the Elementor widget edit is a separately-gated Matti-visible
   step, not assumed.
8. **E2E**: refactor ~/gg-e2e into a case matrix (harness currently rewrites one
   gravel fixture — sol-verified); add a bikepacking case with semantic
   assertions: discipline propagation, runway (16/24/36), consecutive long days
   present, simulation + recovery window present, no sleep-dep content, strength
   continuity, R1 text guard on generated artifacts.

**Owner gate**: sol review of the migration commit series; E2E green including the
new case; D-C1 pricing already resolved (existing $15/wk, $249 cap).

---

## Sequencing (revised)

- **G0.2 (now)**: sol re-review of this v2. Fable verifies + folds.
- **G0.5**: Fable authors the method contract → sol review → **Matti approves the
  method** (this is also his white-paper review moment).
- **G1**: WS-G build (codex): parameterization + content + shelf. Gravel-guide
  byte-parity is the safety rail. Matti content gate → deploy.
- **G2**: WS-P engine + 6 pilot SKUs (codex, in gravel-god-training-plans),
  implements the contract; ultra QC profile lands BEFORE SKU generation; sol
  per-SKU audit; Matti publish gate.
- **G3**: WS-C migration series (codex), implements the same contract; sol review;
  E2E green.
- WS-G's architecture/content may draft in parallel to G0.5, EXCEPT chapters 3
  and 8 (training + simulation): their content freezes only against the approved
  contract. WS-P and WS-C are serialized AFTER the contract
  freezes (sol's parallel-implementation warning) — WS-P first, then WS-C reuses
  the proven session/pattern definitions where formats align.

## Anti-goals (unchanged)

No new brand · no 12-week ultra SKU · no first-person ultra narrative · no
fabricated proof · no sleep-deprivation training content · no `[position]` claims
dressed as settled science.

## Owner decisions

RESOLVED: D-G1 title ("The Complete Bikepacking Race Training Guide"), D-P1
pricing ($129/$199), D-C1 cap (existing $15/wk / $249), D-X1 (shelf ships with
guide). REVISED by evidence: D-P2 pilot set = Tour Divide, Colorado Trail Race,
Badlands (GA4-cited; Atlas out, Torino-Nice excluded as non-competitive).
NEW: D-M1 — Matti approves the method contract at G0.5 (his key remaining gate).
