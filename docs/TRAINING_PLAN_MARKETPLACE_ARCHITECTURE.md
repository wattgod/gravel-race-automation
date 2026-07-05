# TrainingPeaks Plan Marketplace — Architecture & Decisions

**Canonical decision record. Started 2026-07-04 (Matti + agent session). Update in place; keep the "Last updated" line current.**
**Last updated: 2026-07-04**

> Read this before touching plan generation, the TP catalog, or the marketplace. It exists so we never re-litigate this from scratch. Companion session handoff: `gravel-god-cycling/docs/handoffs/2026-07-04-training-plan-marketplace-architecture.md`. Agent-memory mirror: `tp-plan-catalog-source-of-truth.md`, `tp-plan-build-automation.md`.

---

## 0. The one-sentence thesis

**Build the training plans ONCE as a race-neutral base library, then produce TrainingPeaks offerings for every gravel + road race by swapping only three text layers — the guide (a link), the plan-level description, and race/persona-aware notes — never regenerating the structured workouts or progression.** This makes each new race a cheap, swarm-able wrapper job instead of a full generation.

---

## 1. Core architecture: decouple structure from wrapper

- **Race-AGNOSTIC (build once):** structured workouts + the periodized progression. A "Finisher polarized 12-week" plan is physiologically identical whether the goal is Unbound, SBT, or a road century. Power blocks, phases, recovery weeks — none of it is race-specific.
- **Race-SPECIFIC (swap per race, cheap):** the **guide** (hosted web page, referenced by **link** — see §6), the **marketplace/plan description**, and **notes** (race + persona + plan-position aware). This is text, not structure.
- **Consequence:** a new race = copy the right base plan in TP → attach guide link → add notes → set description → add race event → publish → capture URL. Swarm-able by low-intelligence agents.
- **THE RULE that makes it work:** base workouts MUST be race-neutral. No race/distance fueling numbers, no altitude/heat/terrain baked into workout descriptions. Those live in the guide + notes. Fueling in workouts is **zone-based** (universal physiology), never race-based.
- **Duplicate-content note:** TP workout files are NOT web-indexed, so reusing identical workouts across races costs nothing with Google. Duplicate-content risk lives only in the marketplace description + landing page, which are swapped per race anyway. So workouts can be freely reused.

---

## 2. Catalog / demand cut (do NOT build all 15 per race)

The old model was 15 plans/race (4 tiers × up-to-5 levels × duration). **That's inventory thinking; demand is a funnel.** A prior session already documented a 15→5 simplification (`gpx` repo: `SIMPLIFIED_STRUCTURE_SUMMARY.md`, `UNBOUND_200_CORRECTED_PLANS.md`) plus "build custom plan" + "get coaching" CTAs.

**Decision (2026-07-04):** build a lean self-serve core, route the top end to coaching.

- **Keep (self-serve $ tiers):** Time-Crunched (0-5h, survival) · Finisher (5-8h, the anchor seller) · Compete (8-12h) · Masters (50+).
- **Save My Race** (6-week crash plan) = high-margin urgency add-on. Keep.
- **KILL Podium as a template.** Podium contenders already have coaches; a $99 template is the wrong product → near-zero conversion. Replace the Podium slot on the landing page with a **"Racing to win? Get coached"** CTA. Route highest-value athletes to coaching ($199-$1,200/4wk), not a template.
- **Women = a wrapper MODIFIER across all tiers** (not its own workout set): same base workouts + a women's guide module + women's notes + description that speaks to her. Doubles store *listings* (captures "women's gravel plan" search), not the *workout library*.

**Empirical caveat:** if TP sales data exists for the published Unbound 15, use it — a plan that sold ~nothing is a delete regardless of argument.

---

## 3. Variation model + plan lengths

**Base library dimensions:** `Tier × Length × Variation`.

- **Variation axis = demand emphasis** (this reunites the old tp-skus "demand families" with tier/level):
  - Gravel: all-rounder / climber / ultra-endurance / fast-punchy
  - Road: fast-rolling / alpine-climber / crit-punchy / sprint-finish
  - **3-4 variations per (tier, length)** — Matti confirmed multiple STRUCTURAL variations at the same length, chosen functionally (SBT → climber variant; flat fast race → punchy). Not freshness-for-its-own-sake.
- **Lengths per persona** (TP marketplace read: 12wk is modal; 8 = short runway; 16 = low base/early planner; 4/20+ are outliers):

  | Persona | Lengths |
  |---|---|
  | Time-Crunched | 8, 12 |
  | Finisher (anchor) | 8, 12, 16 |
  | Compete | 12, 16 |
  | Masters | 12, 16 |
  | Save My Race | 6 (fixed) |

  Each length is a properly periodized plan (archetype system expands/compresses), not a truncation.

**Road vs gravel:** shared architecture, road-specific VARIATIONS. Road rewards repeatability of hard efforts (surges, over-unders, sprints, covering attacks, top-end) vs gravel's sustained durability + fueling. Road variations shift the archetype mix toward VO2/anaerobic/neuromuscular + variable-intensity, away from pure LSD. One library, two discipline flavors.

---

## 4. Testing weeks policy  (REVISED 2026-07-04)

**Week 1 = a full 360 Testing Week** (superseded the earlier "test is a day" call). Source of truth = Matti's real TP plan **230732 "Gravel God Testing"** (7 days, 352 TSS / 6:22): Openers → Aerobic/FTP → Recovery → Anaerobic → Rest → Metabolism 2:20 → Strength. RPE-anchored (works when the athlete has no zones yet); profiles every energy system + aerobic durability (HR decoupling) + strength baseline. So the 12wk plan = **1 test week + 11 training weeks**.
- **Education layer (required):** each assessment day carries WHAT IT MEASURES / WHY / WHAT TO RECORD / WHAT GOOD LOOKS LIKE, plus a guide "Your Testing Week" section (measure→record→success table + coach expectations). Matti's hosted "Required Reading" GGC articles are linked from the matching workouts (guide-as-link, already in prod): the-assessment-aerobic / the-anaerobic-assessment / the-aerobic-endurance-test.
- **Mid-plan re-test:** a single compressed day (20-min Aerobic only) on 12wk+ (~Wk 7) to refresh zones. Never a second full test week.
- **8-week / SMR:** open — likely a compressed 2-3 day test block, not the full 7.
Engine: `gravel-god-training-plans/engine/testing_week.py` (+ workout_generator/guide/strength hooks). At TP-build time the swarm can instead APPLY block 230732 for Wk 1 to get exact notes + strength natively. Memory: `testing-week-360-protocol.md`.

---

## 5. Best-of-breed module assembly (you already own the pieces — assemble, don't rebuild)

The high-quality engines already exist, scattered across repos. The work is ASSEMBLY + genericization, not new engines.

| Job | Use this | Repo | Notes |
|---|---|---|---|
| Workout structured content + descriptions | `engine/description_generator.py` | `wattgod/gravel-god-training-plans` (ggtp) | BEST. Verbosity tiers (minimal/standard/full → no boilerplate spam), `FUELING_BY_ZONE` (already race-neutral), heat-tier logic, week-context, "no coddling" voice. Beats gpx `v2_nate`. |
| Workout archetype library (6-level progressions) | `nate-workout-archetypes` (2,576 real Nate Wilson workouts, 31 archetypes × 6 levels) + pipeline archetype system | `wattgod/nate-workout-archetypes` | The quality substrate. Workouts named by WHAT THEY ARE + progression (e.g. `VO2max 6×40/20 (1 of 2)`), NOT `W01 Tue` (drag-and-drop artifact — retire it). |
| Marketplace copy | `v3_sultanic` | `gpx` → `races/generation_modules/v3_sultanic/` | BEST. RULES doc: 300-450 words, "lead with the problem," "hype reads as desperation," one philosophical line max, end on outcome. Hard integrity rule: **claims must be verifiable in the guide + plan.** Supersedes erroring v1 `marketplace_generator`. |
| Guide | 14-section modular guide | v3 rules + `gravel-race-automation/guide/gravel-guide-content.json` + `athlete-custom-training-plan-pipeline` `training_guide_builder.py` (Matti: this guide builder is SUPERIOR to gpx's) | Sections: Brief · Before You Start · Fundamentals · 12-Week Arc · Zones · Workout Execution · Technical Skills · **Fueling & Hydration** · Mental Training · Race Tactics · Race-Specific Prep · Race Week Protocol · **Women-Specific Considerations** · Glossary. Modular conditional sections: women (§13), altitude/heat (in §11), masters. |
| Nutrition / hydration module (UNIVERSAL, every plan) | `guidelines/nutrition_hydration_guidelines.json` | `gpx` | `nutrition_model`, `on_bike_fueling`, `daily_baseline_hydration`, `gut_training`. Drives guide §8 + zone-fueling cues. |
| Heat module (UNIVERSAL, every plan) | heat-tier logic in ggtp engine + guide heat section | ggtp / guide | **Heat protocol goes in EVERY plan — it's a unique universal benefit, not a hot-race-only add-on.** Heat adaptation expands plasma volume and improves cardiovascular efficiency + thermoregulation, which raises performance in COLD races AND hot races (and helps at altitude). Sell it as a differentiator ("most plans skip this; it makes you faster in any conditions"). Optionally intensify further for genuinely hot events, but the protocol is standard everywhere. (Matti, 2026-07-04.) |

**Description-engine improvements to fold in when adopting ggtp** (approved 2026-07-04): (1) fully genericize/race-neutral, (2) kill boilerplate repetition, (3) emit archetype-derived NAMES, (4) light voice pass on purpose lines (write once per archetype, reuse), (5) formalize the "guide intrigue line" as the Day-1 guide-link CTA. All make descriptions SHORTER (further from TP's 4,000-char limit; `gpx/validate_descriptions.py` enforces it).

---

## 6. Guide delivery = LINK, not PDF

The guide is a **hosted web page**, referenced from the TP plan's **Day-1 note as a link** (candidate host: WordPress on gravelgodcycling — TBD). Rationale: fix/improve the guide once and every past + future buyer gets the update; a PDF attachment is frozen at purchase. **Bonus:** the guide link is the **email-capture mechanism** — the page delivers the guide in exchange for an email, which unlocks the entire lifecycle (§8), because TP does NOT give you the buyer's email.

---

## 7. Women modifier — evidence-based only

Keep the training plan ONE thing. Women's module covers what evidence supports — **under-fueling/RED-S, iron & ferritin, bone density, saddle/kit, hydration differences** — and explicitly does **NOT** prescribe cycle-synced periodization (evidence is mixed-to-weak and would contradict the plan structure). Same workouts. A guide module + a few notes. Framed in Matti's voice ("what the research supports, minus the wellness-industry hype") it doubles as a trust play.

---

## 8. Lifecycle (hangs off the guide link)

TP does not expose the buyer's email → capture it via the guide-link page, then:
- **Support:** dedicated inbox (or filtered label on `gravelgodcoaching@gmail.com`) monitored by an AGENT (Gmail MCP available). Auto-answers common Qs from a KB (loading plan into TP, setting zones from the test, swap/move workouts, device sync, refunds); drafts judgment calls for one-click approval; escalates real issues.
- **Nurture sequence** (existing email-sequences engine + Mission Control): welcome → "how to read your Week-1 test" → mid-plan check-in → race-week pep → post-race.
- **Post-plan survey** → harvest testimonials/quotes (plans currently lack social proof) + segment.
- **Upsell ladder:** plan → coaching (serious/podium) · plan → next-race plan (repeat) · plan → course (Dirt Craft). End-of-plan email is the pitch.

Sequence: build after the plan pipeline is nailed (parallel-capable, but only pays off once plans sell).

---

## 9. TP-build automation — PROVEN (the missing last-mile)

Browser automation (Claude in Chrome) turns a plan template into a live TP plan. This was always the manual step the generators left as `PLACEHOLDER_NEEDS_RESEARCH`. Full recipe + APIs in agent-memory `tp-plan-build-automation.md`. Key APIs (Matti's TP Coach account):
- Place workout: `POST tpapi.trainingpeaks.com/plans/v1/plans/{id}/commands/addworkoutfromlibraryitem` `{planId, exerciseLibraryItemId, workoutDateTime:"YYYY-MM-DD"}`. Day 1 = a Monday.
- Note: `POST .../plans/{id}/calendarNote` `{planId,title,noteDate,description,attachments:[],standardFormatDate:"Week N, Monday"}`.
- Event: `POST .../plans/{id}/events` `{planId,eventDate,name,eventType:"CyclingRoad",...}`.
- Delete workout: `DELETE .../plans/{id}/workouts/{workoutId}`.
- Store fields readable via `GET .../plans/{id}`: `price`, `planCategory`, `subcategory`, `customUrl`.
- Library import: inject ZWO into a folder's hidden `<input id="fileUploadInput" accept=".zwo">` via DataTransfer (transport as gzip+base64, verify each piece by SHA-256 — long pastes can SUBSTITUTE a char, which length checks miss).
- Match library items→days: `exerciseLibraryItemId` is auto-increment = creation order = insertion order.

**Swarm version is simpler:** use TP native **Copy Plan** on a base plan, then swap description + guide-link + notes + event. Mechanical.

---

## 10. Pricing

Not in any repo — TP owns checkout. But it IS discoverable from published plans: reference plan **599629** ("Finisher Intermediate," Avail-in-Store) reads `price: 99`, `planCategory: 6`, `subcategory: 14`. So build the price ladder by reading the existing published Unbound 15. (Ladder by tier/level/duration still a Matti decision.)

---

## 11. Where we are (2026-07-04)

- **Base-library engine SHIPPED** (ggtp branch `testing-week-and-base-library`, pushed). The athlete-intake engine now generates race-neutral base plans: **360 testing week (Wk 1)** → deterministic polarized 11-week progression → **compressed mid re-test (Wk 7)** → **universal heat block (Wk 6-10, guide + workout cues)** → taper/race. Clean archetype names (`W## Day:` artifact retired) with `(n of N)` progression suffixes + `placement_manifest.json` for swarm TP placement. 100/100 tests green (also de-staled the fixture dates).
- **4 Finisher-gravel-12wk demand variations GENERATED** (all-rounder/climber/ultra/punchy) via a `DEMAND_EMPHASIS` overlay — same testing week + heat + periodization, biased archetype selection. Verified distinct (climber→Threshold, punchy→Anaerobic/VO2/Explosive, ultra→long-ride Durability). Intakes in `ggtp/base_intakes/`.
- **NEXT:** build the base library into TP (apply block 230732 for Wk 1 to keep exact notes+strength; engine workouts Wk 2-12), then prove the wrapper layer (guide-link / race-aware description / notes) + lifecycle on one race.

- **Finisher Intermediate proof built in TP** (plan **657024**, "AUTO Finisher Intermediate (proof)") from `gravel-race-automation/plans/6. Finisher Intermediate/template.json`: 84 workouts, every day filled, coaching in descriptions, Day-1 welcome orientation, race event, NO notes. Matches published reference **599629** ($99). Prior WEAK plan **657020** (from tp-skus generic families) left for side-by-side.
- **All 15 SBT GRVL plans regenerated** via the catalog generator (`gpx/races/generate_race_plans.py races/sbt_grvl.json`) → `gpx/races/SBT GRVL/` (~1,500 workouts, reference-quality, SBT altitude/fueling overlays). Two non-fatal generator gaps: SBT config is an OLDER schema (non_negotiables/masterclass_topics must be lists; needs guide_variables/marketplace_variables/tier_overrides — transformed copy saved in `gpx/races/sbt_grvl.json`); guide gen needs `markdown` module (use the custom pipeline's `training_guide_builder.py` instead — Matti says it's superior).
- **Published catalog:** the 15 Unbound-200 plans already live PUBLISHED in Matti's TP under folder "Unbound 200" (+ an "Unbound 200 (V2)" folder, 4 plans).
- **Cleanup debt:** TP "0. Test" library folder holds ~300 staging items from the build sessions; plans 657020 (weak) + 657024 (proof) exist. Delete when done comparing.

---

## 12. Open decisions (need Matti)

1. Price ladder by tier/level/duration (read the published Unbound prices as the baseline).
2. ~~Heat conditional?~~ RESOLVED 2026-07-04: heat protocol is UNIVERSAL in every plan (benefits cold + hot + altitude) — a sell-able differentiator. See §5.
3. Include separate strength workouts (two-a-days in TP) OR match published 84-cycling (strength as notes)?
4. Guide-page host (WordPress vs static).
5. Library build order: recommended THIN VERTICAL first — **Finisher, gravel, 12-week, 4 demand-variations** — prove base→wrapper→TP→lifecycle end-to-end, then expand tier-by-tier.

**Governing principle (Matti, 2026-07-04):** ASSEMBLE + CONSOLIDATE the best-of-breed pieces we already own; do NOT rebuild engines. Matti is the bottleneck, so every decision gets a durable, dated, well-articulated memory trace (this doc + the handoff) so the reasoning never has to be reconstructed. When in doubt, write it down here.

---

## 13. Repo map (who has what)

- `wattgod/gravel-race-automation` (LOCAL, primary) — `plans/*/template.json` (15 reference-quality base templates), `races/*.json` configs (unbound/mid_south/sbt_grvl), `pipeline/` (custom-athlete), `guide/gravel-guide-content.json`, this doc.
- `wattgod/gravel-god-training-plans` (ggtp) — the high-quality **`engine/`** (methodology selector, archetype weighting, `description_generator.py`, heat tiers). Best workout-description engine.
- `wattgod/nate-workout-archetypes` (archived) — 2,576 real workouts → 31 archetypes × 6 levels; the quality substrate + white paper.
- `wattgod/gravel-plans-experimental` (gpx) — the 15-plan CATALOG loop (`races/generate_race_plans.py`), `v3_sultanic` marketplace copy, `guidelines/nutrition_hydration_guidelines.json`, 15→5 simplification docs.
- `wattgod/gravel-landing-page-project` (archived) — predecessor catalog generator; Elementor landing pages (15-plan grid → TP links).
- `athlete-custom-training-plan-pipeline` (LOCAL) — block-builder + archetype system + **`training_guide_builder.py` (SUPERIOR guide builder — use this)**; `tp-skus` = the WRONG thin generic-family source (do not use for sellable plans).
- `wattgod/road-race-automation` (LOCAL) — road races (road demand families for road variations).
