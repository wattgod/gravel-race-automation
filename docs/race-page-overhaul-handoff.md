# Race-Page Overhaul — Execution Handoff

**For:** the agent(s) driving the gravelgodcycling.com race-page redesign. **Author:** Fable, 2026-07-14. **Status:** design approved by Matti, ready to build. **You need no prior context — this is self-contained**, but the linked artifacts hold the detail.

## 0. The one-sentence goal

The race page is our **funnel** (the honest-critic ratings earn the trust that sells the plan), and it currently **leaks badly** — reorganize it **spine-first**, make the rating **interactive**, and lead the offer with the **custom plan**, without cutting the trust/SEO content.

## 1. The evidence (GA4, last 90 days — quantified, not vibes)

- **5,180 race-page views → 76 plan-CTA clicks = 1.5%.** 98.5% never click toward a plan.
- **Only ~18% reach 90% scroll** — and the plan ladder sits near the *bottom* of ~20 sections, so the offer is below where most people stop.
- **Coaching pages: 42 views. Training-plan pages: 161. ~5 plan purchases (0.1%).**
- Diagnosis: the ratings pull traffic; the path to the plan is a cliff; the offer barely gets seen. (Source: `scripts/funnel_report.py`, GA4 property 353120093.)

## 2. The approved design — spine-first

**Prototype (Matti-approved shape):** https://claude.ai/code/artifact/69072363-72d0-4b7f-94e3-f4e4527d16a8 — a working mock in the real brand (warm-paper, teal #178079, gold #9a7e0a, Source Serif 4 + Sometype Mono). Build to this.

The page turns from an encyclopedia into a **decision tool**. Section order:

1. **Hero** — race name, vitals, the **dual Lab Score / Rider Score** (the RottenTomatoes mechanic, already in `build_hero`), and a one-line **verdict**.
2. **Interactive rating** (the centerpiece — see §4) — labeled two-radar model (Course /35 · Opinion /35) where **clicking a criterion lights its spoke and unfolds its explanation**. Tabbed Course / Opinion.
3. **Full-breakdown tiles** — a compact grid of small tiles (Course & Route · Elevation · Altitude/Weather · Tires · History · Logistics · Racer Reviews · Photos/News) that jump into the depth *without* pushing the offer off-screen.
4. **Transition** — a gold-outlined callout ("Get ready for [Race] / You've seen what it asks. Here's how you answer it.") — the hinge from "what is this race" to "here's your move." **Not** a dark band.
5. **The offer — custom plan first** (see §3).
6. **Deep dive** — everything demoted from the current 20-section stack, as expandable content (not deleted — see §5 don't-cut list).

## 3. The offer (custom-plan-first — the highest-margin move)

- **Lead with the custom plan.** It's `$15/week` ("less than one gel per ride" — real copy), ~100% margin (no 30% TP cut), built for the rider + the race, and CTAs to the questionnaire (`QUESTIONNAIRE_URL?race=<slug>` → `BUILD MY PLAN`). Copy uses the **Built-For register** — see `../gravel-god-training-plans/docs/BUILT-FOR-pitch-formula.md` (Anthropic precision + splashes of color earned by specificity; no selling verbs / hype / self-reference).
- **Coaching as the up-tier** — "Really want to find out what you can do? Get a coach." (from `$199/4wk`).
- **Pull the ready-made TP ladder OFF the race page** (Matti-approved). At $15/wk the custom plan is barely pricier, higher margin, and better; the ready-made SKUs still sell via TP-marketplace search + `/training-plans/`. This removes `build_plan_ladder` from the race page — **but first fix its broken lead capture** (already done: commit `a25fd1b8` added `race_plan_ladder` to the worker + fixed the fire-and-forget success bug; ship that before/with the overhaul).
- **Guardrail (load-bearing):** *don't turn the critic into a salesman.* Surface the offer with confidence, not hard-sell — the ratings' honesty is what makes the plan believable.

## 4. The interactive rating component (net-new)

The real model is **two categories, two radars** (verified in `wordpress/generate_neo_brutalist.py`): **Course Profile /35** (logistics, length, technicality, elevation, climate, altitude, adventure) + **The Opinion /35** (prestige, race_quality, experience, community, field_depth, value, expenses). Plus `overall_score` (Lab) + tier + the audience Rider Score.

Build: a labeled radar (each axis shows name + `n/5`, total in center) beside/above a clickable criteria list; **click a criterion → its spoke highlights + its explanation (the existing `explanations` dict / accordion prose) unfolds.** Tabs switch Course ↔ Opinion. This replaces the static `build_radar_charts` + the separate accordion with one interactive unit (the prototype has a working canvas implementation to port). Keep it compact (Matti's note: don't sprawl).

## 5. Simplification — reuse the sol-reviewed spec

**`docs/race-page-simplification-spec.md` (v2, commit `a0e79677`) is already written AND GPT-5.6-sol-reviewed** — use it as the ticket source for the restructure. Highlights:
- **The random-YouTube-image fix (P1):** the Course section renders every YT-derived GIF with **no relevance check** (`ai_relevance` ignored); the generator ignores the QC score that exists. Gate images to `type.startswith("video-")` with a **null-safe** `ai_relevance` check; drop the GIF stack; leave non-YouTube imagery alone. (Prereq: the `photo_qc` coverage reality — 472/746 races have no photos — see spec T8.)
- **Duplicate reduction:** hero + stat-card vitals repeat; `build_photos_section` is dead code; rider-intel is presented 3×. Consolidate per the spec's duplicate map (with the corrections sol made — from-the-field quotes and racer-reviews are DIFFERENT trust functions, do NOT merge them).
- **Higher-leverage than wrapper-merging:** trim *inside* the training block (8 demand bars + configurator + 5 full workout protocols) — cap preview workouts / move full protocols to the indexed training-guide page.
- **⛔ DON'T CUT** (SEO + trust): Ratings, Verdict, sourced field quotes, real Racer Reviews, Sources, FAQ, Similar/nearby races. History may merge but must stay server-rendered/crawlable.
- **Prereq ticket:** `surface_breakdown` normalization gap (chart is effectively dead — `normalize_race_data` doesn't copy the field).

## 6. Hard constraints (from `gravel-race-automation/CLAUDE.md` — tests enforce)

- **XSS:** `esc()` on every data-derived value; never `innerHTML` with data; no inline `onclick`/`onsubmit` (use `addEventListener`).
- **Every generator includes `get_ga4_head_snippet()`**; GA4 events only on real user interaction.
- **Brand tokens only** (`tokens.css` / `brand_tokens.py`) — never hardcode hex; neo-brutalist (2–3px borders, no radius/shadow); Sometype Mono + Source Serif 4.
- **Every email form MUST POST to its worker and only show success on `response.ok`** (the fire-and-forget bug was just fixed — don't reintroduce it).
- Deploy = tar+ssh + SiteGround cache purge; run `python3 scripts/preflight_quality.py` + `pytest tests/` first.

## 7. Suggested workstreams (Codex-dispatchable)

- **WS-A · Structure** — implement the spine-first section order + the tile breakdown; execute the simplification-spec restructure tickets (kill dup, dead code, consolidate). Acceptance: top-level section count + order match §2; don't-cut list intact; `test_neo_brutalist.py` green (note: gauge removal breaks `test_neo_brutalist.py:712` — update the test with the product decision).
- **WS-B · Interactive rating** — the labeled two-radar + click-to-explain component (§4), ported from the prototype canvas. Acceptance: renders real `gravel_god_rating` data; click highlights spoke + unfolds explanation; keyboard-accessible; no inline handlers.
- **WS-C · Offer** — custom-plan-first block (Built-For copy, $15/wk → questionnaire), the transition callout, coaching up-tier, remove `build_plan_ladder` from the race page. Acceptance: single primary CTA to the questionnaire with `race=<slug>`; GA4 events preserved; guardrail honored (no hard-sell).
- **WS-D · Images** — the `ai_relevance` gate + GIF-stack removal (simplification-spec T1). Acceptance: video images gated null-safe; non-YouTube imagery untouched; tests for low/missing/string score + no-image page.
- **WS-E · Measure** — wire the changed surfaces to `ab_experiments.py` (hero, rating, offer) and watch the funnel (`scripts/funnel_report.py`): does race-page → plan-CTA move off **1.5%**? That's the success metric.

## 8. Process (non-negotiable)

- **GA4 before big cuts** — the leak is measured; measure the fix. A/B, don't guess.
- **Adversarial GPT-5.6-sol review** of each workstream's plan before dispatching to executors and before committing (per the global rule). Verify sol's findings against live code — it misfires too.
- **Stage, don't publish.** Nothing customer-facing ships without Matti's read + his deploy gate.
- **Two registers:** the ratings/editorial stay irreverent (Physiqonomics); the offer is calm Built-For. Editorial earns trust loudly; the offer spends it quietly.

## 9. Open decisions for Matti (don't guess these)
- Exact custom-plan price/framing on the page ($15/wk confirmed as the number).
- Whether the difficulty-gauge is cut (visual simplification; it breaks a test + a live A/B experiment — close/relocate the experiment first).
- Final verdict/hero copy voice per race.

**Start here:** read the prototype (§2) and `docs/race-page-simplification-spec.md`, then WS-A + WS-B in parallel (structure + rating), WS-C close behind (offer), WS-D independently (images), WS-E throughout (measure).
