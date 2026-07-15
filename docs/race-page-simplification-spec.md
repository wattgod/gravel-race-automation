# Race-Page "Full Breakdown" Simplification Spec (v2)

**Status:** Investigation + spec only. No code changed. Intended for a Codex executor to implement.
**Target file:** `wordpress/generate_neo_brutalist.py` (6,302 lines)
**Live evidence:** `https://gravelgodcycling.com/crusher-in-the-tushar/` (fetched 2026-07-14)
**Data sample:** `race-data/crusher-in-the-tushar.json`

**Execution companion:** See `docs/race-page-overhaul-handoff.md` for the approved
spine-first order, custom-plan-first offer, interactive-rating behavior, deploy gate,
and the product decisions that supersede this document's earlier target DOM.

**v2 changelog:** This revision folds in a GPT-5.6-sol code review that caught several
factual errors in v1 that would have shipped broken behavior if a Codex executor had
implemented v1 literally. Specifically: v1's T1 image gate would have crashed on
`ai_relevance: null` and hidden legitimate non-YouTube imagery; T8 mischaracterized what
`photo_qc.py` actually collects and how `ai_relevance` reaches the JSON; T4 conflated two
distinct revenue surfaces as "duplicate CTAs"; D1 overcounted the Riders Report reuse;
D3 conflated two related-but-different rating models; and the proposed target DOM
undercounted the real section count. See inline notes marked **[v2 correction]**. The
core finding — unvetted YouTube stills/GIFs and genuine content duplication — still
holds and is still the right thing to fix.

---

## TL;DR — the two things Matti most wants fixed

1. **"Random YouTube images."** The Course section renders up to **7 YouTube-derived
   images** — 2 auto-extracted video stills + **5 looping preview GIFs**. The GIFs are
   frames grabbed at fixed *time-percentages* (10%, 20%, 30%…) of whatever YouTube videos
   matched a keyword search (`scripts/youtube_screenshots.py:69`). **[v2 correction]**
   These frames ARE quality-gated — but only on mechanical visual-quality/motion signals
   (brightness, blur, contrast, composition, a bright-text-overlay detector) — **never on
   whether the frame actually depicts this race's course.** **Proof:** in
   `crusher-in-the-tushar.json` the 3 stills carry `ai_relevance` scores of 5/5/4, but all
   5 GIFs carry `ai_relevance` **missing/null when read** — they were never AI-relevance
   reviewed. The generator **ignores the relevance score entirely** when rendering. Only
   274 of 746 race JSONs carry the `ai_relevance` field on any photo at all.
   → **Fix: cut GIFs to at most 1 (ideally 0), gate stills on relevance (null-safe, only
   for video-derived images), delete the dead duplicate photo renderer.**

2. **Redundancy / overwhelm.** 21 stacked content blocks, with **3 separate email-capture
   forms**, several plan/coaching CTAs across distinct revenue surfaces, the rider-intel
   "RIDERS REPORT" widget rendered **3×** (plus one true duplicate quote elsewhere), and
   distance/elevation/demand data repeated across multiple surfaces.
   → **Fix: collapse the CTA sprawl, cut the one true duplicate rider-voice render, trim
   inside the training block, render each demand datum with a distinct purpose only.**

---

## 1. Section Inventory

Actual on-page render order is set at `generate_neo_brutalist.py:6083-6088` (NOT the
numeric `[01]…[11]` kickers, which are out of order with the real DOM). Structure above
content: `nav → hero → prep_strip → toc → content → footer → sticky_cta`.

**[v2 correction]** The tickets below (T2–T10) were checked against this inventory and
**leave ~14 top-level sections, not the "~10–11" originally promised** in v1 §4. See the
new **T9 (target-DOM ticket)** for an honest, acceptance-tested target section list.

| # | Section (builder) | Def line | Renders | Data source (`race-data/<slug>.json` → `race.*`) | Rough length | Verdict |
|---|---|---|---|---|---|---|
| — | `build_hero` | 1966 | Name, tier, vitals line (loc·date·**dist·elev**), GG Score, Rider Score | `vitals`, `gravel_god_rating`, `racer_rating` | small | **KEEP** |
| — | `build_prep_strip` | 3968 | "Preparation Profile": top-3 **demand chips**, countdown, Build-Plan CTA, **free prep-kit link** | `web/race-packs/<slug>.json` `demands` | small | **KEEP** (spine) |
| — | `build_toc` | 2062 | Sticky "On This Page" nav | static + `active` set | small | **KEEP** |
| 1 | `build_course_overview` | 2135 | Tagline, RWGPS map, **stat cards (dist/elev/loc/date/field/cost)**, **difficulty gauge**, calendar export, nearby-races | `vitals`, `course`, `explanations` | medium | **KEEP** (trim: see dup map) |
| 2 | `build_history` | 2259 | Origin story, reputation, notable-moments timeline | `history` | medium | **MERGE → Course** (must stay server-rendered/crawlable — see DON'T-CUT list) |
| — | `build_pullquote` | 4565 | Pull-quote from `biased_opinion.summary` | `biased_opinion` | small | **KEEP** (1 line) |
| 3 | `build_course_route` | 2352 | **2 stills + 5 GIFs**, character, signature challenge, surface bar (currently dead — see **T0**), suffering-zones, **Riders Report (challenges+terrain)** | `photos`, `course`, `rider_intel` | **large** | **KEEP + heavily trim images** |
| — | `build_tire_guide_callout` | 4462 | Inline link to `/race/<slug>/tires/` | `tire_recommendations` | small | **MERGE → tire_picks** |
| 4 | `build_from_the_field` | 2502 | Rider quotes + video embeds (lite-youtube) | `youtube_data.videos/quotes` | medium | **KEEP** (videos already capped at 3 in `normalize_race_data` — no change needed) |
| 5 | `build_ratings` | 2584 | Course-profile + editorial radar + 14 accordion rows | `gravel_god_rating`, `explanations` | **large** | **KEEP** (core product) |
| 6 | `build_verdict` | 2618 | Race-this-if / skip-this-if / bottom line / alternatives | `biased_opinion`, `final_verdict` | medium | **KEEP** |
| — | `build_racer_reviews` | 2754 | Star summary, **real user reviews**, inline review form (email) | `racer_rating` | medium | **KEEP** (form #1 — trust surface, see DON'T-CUT list) |
| — | `build_email_capture` | 4631 | **"FREE DOWNLOAD — Prep Kit" email form** | static + slug | small | **MERGE/DEDUPE** (form #2) |
| — | `build_date_reminder` | 4659 | **"Remind me 12 wks before" email form** | `vitals.date_specific` | small | **CUT standalone form; fold opt-in into prep-kit success step** (form #3) |
| — | `build_news_section` | 4547 | Google-News ticker (T1/T2 only, JS-hydrated) | runtime RSS | small | **DEMOTE-TO-TILE / KEEP** |
| 7 | `build_training` | 2841 | Countdown, free prep-kit CTA, custom-plan pitch, 1:1 coaching pitch, Riders Report (gear) | `rider_intel.gear_mentions`, constants | medium | **MERGE (CTA hub, layout only — see T4a/T4b)** |
| — | `build_plan_ladder` | 4726 | Static TP-SKU plan tiers (per-tier "notify me" form where no marketplace URL yet) from sibling plans DB | `../gravel-god-training-plans/db/plans.json` | medium | **MERGE (layout) — DISTINCT product surface, see T4b** |
| — | `build_coaching_teaser` | 4500 | **"RIDERS SAY" quote (= `key_challenges[0]`) + coaching CTA** | `rider_intel.key_challenges[0]` | small | **CUT** (true dup — see D1) |
| 8 | `build_train_for_race` | 4037 | **8 demand bars** + configurator + up to 5 full workout protocols (from `WORKOUT_SHOWCASE`, lines 2906-3967) + plan CTA | `web/race-packs/<slug>.json` | **large** | **MERGE (layout) + INTERNAL TRIM — see T10** |
| 9 | `build_logistics_section` | 4314 | Airport/lodging/food/packet/parking, official-site link, **Riders Report (race-day tips)** | `logistics`, `rider_intel.race_day_tips` | medium | **KEEP** |
| 10 | `build_tire_picks` | 4369 | Top-3 tire picks + width + link to full guide | `tire_recommendations` | medium | **KEEP** (absorb callout) |
| — | `build_similar_races` | 4871 | 6 related races by computed relevance | `race_index` | small | **KEEP** (trust + SEO — DON'T-CUT) |
| — | `build_visible_faq` | 4823 | 6 Q&A accordions | `faq`/derived | medium | **KEEP** (DON'T-CUT) |
| 11 | `build_citations_section` | 4951 | 14 numbered sources | `citations` | medium | **KEEP** (DON'T-CUT) |
| — | `build_photos_section` | 2036 | Photo grid — **NEVER CALLED** (absent from assembly list 6083-6088) | `photos` | — | **CUT (dead code)** |

---

## 2. Duplicate Map (the core finding)

### D1 — **[v2 correction: renamed]** Repeated rider-intel presentation, not "6 places"

`_build_riders_report()` (helper at `2310`) is invoked **3×**, not 4× — grep confirms
calls only at `2471` (Course), `2858` (Training), `4350` (Logistics). A 4th surface,
`build_coaching_teaser` (`4523`), renders `key_challenges[0]` **directly**, not through
the helper, but it happens to be the **same underlying quote already shown in Course**
(`2471`). That is the one true hard duplicate. From-the-Field quotes
(`youtube_data.quotes`, line `2518`) and Racer Reviews (`racer_rating.reviews`, line
`2810`) are **separate data sources with separate trust functions** (curated
video-transcript quotes vs. real submitted star reviews) — **[v2 correction] these are
NOT duplicates and must be kept, both.**

| Surface | Line | Data | Verdict |
|---|---|---|---|
| Course "RIDERS REPORT" | `2471` | `rider_intel.key_challenges` + `terrain_notes` | KEEP |
| Training "RIDERS REPORT" | `2858` | `rider_intel.gear_mentions` | KEEP |
| Logistics "RIDERS REPORT" | `4350` | `rider_intel.race_day_tips` | KEEP |
| Coaching-teaser "RIDERS SAY" | `4523` | `rider_intel.key_challenges[0]` ← **exact dup of Course** | **CUT** |
| From-the-Field quotes | `2518` | `youtube_data.quotes` | **KEEP — distinct source** |
| Racer Reviews | `2810` | `racer_rating.reviews` | **KEEP — distinct source, real user trust surface** |

**Hard duplicate:** `build_coaching_teaser` (`4506-4524`) reuses `key_challenges[0]` —
the *same* item already rendered in the Course Riders Report (`2471`). Live page
confirms: the crusher "valley section between towns" quote appears in the training area
*and* in the course area.
**Keep:** the Course Riders Report instance. **Cut:** the coaching-teaser "RIDERS SAY"
re-render (see D2/T3 for the CTA half of this cut, and its A/B-experiment dependency).

### D2 — CTA / capture sprawl: 3 email forms + several plan/coaching CTAs

Between Verdict and Logistics the page stacks (assembly `6085-6086`):
`racer_reviews → email_capture → date_reminder → news → training → plan_ladder → coaching_teaser → train_for_race`.

- **Email forms ×3:** racer-review form (`2685`), prep-kit form (`4631`), date-reminder
  form (`4659`).
- **"Free prep kit" pitched ×3:** prep_strip link (`4032`), email_capture form (`4635`),
  training free-block (`build_training` body, "12-week timeline + race-day checklist +
  packing list. Free.").
- **Plan/coaching CTAs across distinct surfaces:** prep_strip "Build my plan" (`4031`),
  training custom-plan + 1:1 coaching pitch (`build_training`), plan_ladder static-SKU
  tiers (`4726`), coaching_teaser (`4529`, to be cut per D1), train_for_race plan CTA
  (`4037`), plus persistent `sticky_cta` (`6046`). **[v2 correction]** `build_training`
  (custom-plan pitch + 1:1 coaching) and `build_plan_ladder` (static TP-SKU tiers / per-
  tier "notify me" form) sell **two different products** — a bespoke race-specific plan
  vs. an off-the-shelf plan tier — and are **not duplicate CTAs**. Do not remove either
  product surface. What's actually sprawling is the *layout* (too many visually separate
  boxes for what could read as one coherent "Train for This Race" hub) and the
  *repetition* of the free-prep-kit pitch. See T4a/T4b.

**Keep:** one prep-kit gate (with the date-reminder opt-in folded into its success step),
one Racer Review form, and both distinct plan/coaching product surfaces (custom plan +
coaching pitch, and the static plan ladder), consolidated into a single visual hub.
**Cut:** date_reminder as a standalone form; coaching_teaser entirely (dup CTA + dup
quote, pending its A/B-experiment sunset — see T3).

### D3 — **[v2 correction]** Difficulty gauge and radar are two related models, not "same data 4×"

The `course_overview` **difficulty gauge** (4 editorial criteria, `2181-2237`) and the
`ratings` **radar** (14-criterion editorial rating, `2598`) are **related but distinct
models** — the gauge is a compressed, above-the-fold difficulty summary; the radar is the
full editorial rating surface. They are not the same data rendered four times. The
`prep_strip` top-3 chips (`4006-4013`) and `train_for_race` 8 demand bars (`4072-4087`)
are a third, separate model (per-race training-demand weights, sourced from
`web/race-packs/<slug>.json`, not `gravel_god_rating`). So there are really **two demand-
adjacent models rendered across four surfaces** (editorial difficulty: gauge + radar;
training demand: chips + bars), not one model rendered 4×.
**Any gauge removal is a visual-simplification call, not a dedup fix** — it trims an
above-the-fold summary that duplicates information available two sections down in the
radar, at the cost of losing a quick-scan difficulty signal near the top of the page.
**[v2 correction] Note: removing the gauge breaks `tests/test_neo_brutalist.py:712`
(`test_course_overview_has_difficulty`, asserts `"gg-difficulty-gauge" in html`) — update
or remove that test as part of the same PR, don't leave it red.**
**Keep:** prep_strip chips (above fold, training-demand model) + train_for_race bars
(full training-demand profile). **Optional, visual-simplification only:** cut the
course_overview difficulty gauge (editorial-difficulty model) since the radar two
sections down covers the same editorial ground in more detail.

### D4 — Distance / elevation stated 2×+

Hero vitals line (`1987-1996`, `"{dist} mi · {elev} ft"`) **and** course_overview stat
cards (`2160-2166`). Live page also surfaces the numbers again inside Facts & History
prose and training copy.
**Keep:** the course_overview stat cards (canonical). **Trim:** drop dist/elev from the
hero vitals line (keep location·date), since the stat grid sits one screen down.

### D5 — Course narrative split across 3 sections

`course_overview` (tagline + stats), `history` (origin/reputation/timeline),
`course_route` (character + surface + suffering-zones). History is a thin section that
reads as a digression between the overview and the actual course.
**Merge:** fold `build_history` output into the Course area (as a collapsible "Facts &
History" sub-block under Course Overview) so a reader gets one continuous course story
instead of Overview → History → back to Course. **History content must remain
server-rendered and crawlable** — a collapsible `<details>`-style disclosure is fine; a
JS-only reveal that hides content from crawlers/no-JS is not (see DON'T-CUT list).

### D6 — Photo gallery rendered by two code paths

`build_photos_section` (`2036`) and the gallery block inside `build_course_route`
(`2362-2383`) contain **identical** filter logic
(`[p for p in photos if not primary and not gif][:4]`). `build_photos_section` is
**dead** (never in the assembly list). **Cut it.**

---

## 3. Image Cleanup (the "random YouTube images")

### Mechanism

1. `scripts/youtube_research.py` keyword-searches YouTube for each race and stores
   matched videos in `race.youtube_data.videos`.
2. `scripts/youtube_screenshots.py` downloads short segments at **fixed
   time-percentages** of each video (`sample_percents = [0.10, 0.20, …, 0.90]`, line
   `69`), extracts frames (`ffmpeg -ss`), and keeps ones that pass **mechanical**
   gates — brightness (`_reject_dark`, `227`), blur, composition/contrast checks, and a
   bright-text-overlay detector (`_has_bright_text_clusters`, `258`). **[v2 correction]**
   These are real quality gates, but they check *visual quality and motion*, not *race
   relevance* — there is **no check that the frame depicts this race's course.** A frame
   at "40% through a random gravel-cyclist vlog" can pass every mechanical gate and still
   become a course still or a looping GIF.
3. `scripts/photo_qc.py` *can* AI-rate relevance (Layer 2 `--ai-review`, Claude vision →
   `ai_relevance` 1-5). **[v2 correction — this step was materially wrong in v1]**:
   - The `--ai-review` step's file-collection loop only iterates `.jpg` files
     (`scripts/photo_qc.py:528`, `photo_files = sorted(f for f in slug_dir.iterdir() if
     f.suffix == ".jpg")`) — **GIFs are structurally excluded from AI review, not merely
     "unreviewed."** They will never get an `ai_relevance` score under the current
     pipeline, full stop.
   - `ai_relevance` is computed in memory during `--ai-review` but only **written back
     into the race JSON during the separate `--apply-seo` phase**
     (`scripts/photo_qc.py:783`, inside `apply_seo_alt_text()`). A race can have been
     AI-reviewed and still show no `ai_relevance` field on disk if `--apply-seo` hasn't
     run for it yet.
   - **472 of 746 races have zero photos at all** (`race.photos == []`), not
     "unreviewed stills" — there's nothing there to gate. Of the 274 races that *do* have
     photographed stills, all carry stills with `ai_relevance` scores; it's the GIFs that
     are structurally unscored.
   - **The generator never reads `ai_relevance` at all** — `build_course_route` filters
     only on `primary`/`gif` and caps `[:4]` (`2362-2364`, `2446`).

### What ends up on the page (crusher, confirmed)

- Course section: **2 stills** (`video-2`, `video-3`) + **5 looping GIFs**
  (`preview-gif` ×5), all credited "YouTube / Gravel Cyclist," alt text AI-guessed
  (e.g. "descending … on Col de Crush mountain" — a guess, not verified).
- The `primary` still (`video-1`) is marked but **never rendered** — `build_hero` has no
  `<img>`. OG image is a separate `/og/<slug>.jpg`. So the "best" vetted image is
  orphaned.

### Fixes (conceptual — see T1)

- **Cut the GIF stack.** 5 auto-extracted looping GIFs are the single biggest source of
  visual noise and are, by pipeline design, **permanently unscored for relevance** (see
  above — GIFs can never get an `ai_relevance` value under the current `--ai-review`
  collection logic). Render **at most 1** GIF, or **0** and rely on the video embeds in
  From-the-Field for motion. Preferred: **0 GIFs**, since From-the-Field already offers
  playable video.
- **Gate stills on relevance — scoped and null-safe.** Render a still only if its parsed
  `ai_relevance` is present and `>= 4`. This gate applies **only to video-derived
  images** (`type` starting with `"video-"`) — see T1 for why scoping the filter matters.
- **Delete dead `build_photos_section`** (`2036`).
- **Optional promotion:** surface the highest-`ai_relevance` still as a small hero/course
  lead image instead of leaving `video-1` orphaned.

---

## 4. Proposed Simplified Structure

**[v2 correction]** See **T9** for the acceptance-tested target section list and ordering
— the sketch below is the *intent*, but the literal section count and exact
merge/no-merge boundaries are normative only as written in T9, not here.

A **spine** (always present, fast) + a **compact breakdown**, replacing the 21-block
stack.

```
nav
hero                         (name · tier · location · date · GG Score · Rider Score)   ← drop dist/elev here
prep_strip                   (top-3 demand chips · countdown · ONE Build-Plan CTA · ONE prep-kit link)
toc

[01] Course                  overview stats + map + surface (fixed — see T0) + suffering-zones
                             + collapsible "Facts & History"          ← history merged in, still crawlable
                             + ≤2 relevance-gated stills, 0–1 GIF     ← images gated (T1)
                             + Riders Report (challenges + terrain)   ← ONE of the three rider-intel callouts
[02] From the Field          rider quotes + video embeds (already capped at 3, no change)
[03] The Ratings             radar + accordions                       ← editorial-difficulty model of record
[04] Verdict                 race-this-if / skip-this-if / alternatives
[05] Racer Reviews           stars + real reviews + review form        ← the ONE review email form
[06] Train for This Race     8 demand bars + trimmed workout showcase (T10) + plan ladder + custom-plan/coaching pitch
                             + prep-kit gate                          ← training + plan_ladder + train_for_race +
                                                                         email_capture merged BY LAYOUT ONLY (T4a);
                                                                         both product surfaces preserved (T4b)
[07] Logistics               logistics grid + race-day tips + tires (picks + guide link merged)
[08] Similar Races
[09] FAQ
[10] Sources
footer + sticky_cta (single persistent CTA)
```

**Cut outright:** `build_photos_section` (dead), `build_coaching_teaser` (dup quote + dup
CTA, pending A/B sunset — T3), `build_date_reminder` as a standalone form (fold its
opt-in into the prep-kit success step).
**Visual-simplification candidate (not a dedup requirement):** course_overview
difficulty gauge — see D3.
**Demote-to-tile:** `news` ticker (already collapsible; keep as a thin strip, not a
section).
**Rationale:** every true duplicate (the coaching-teaser quote/CTA, the dead photo
renderer) is cut; every rider-voice datum keeps its distinct source; the training area
reads as one hub instead of a CTA carpet — without deleting either revenue product
surface and without deleting any trust/SEO surface.

### DON'T-CUT list (explicit)

The following must remain, unchanged in substance, through every ticket in this spec:

- **Ratings** (radar + accordions) — core product.
- **Verdict** (race-this-if / skip-this-if / alternatives).
- **Sourced field quotes** (From-the-Field, `youtube_data.quotes`).
- **Real Racer Reviews** (`racer_rating.reviews`) and its submission form.
- **Sources / Citations** section.
- **FAQ**.
- **Similar/nearby races** — trust + internal-linking SEO surface.
- **History** — may merge visually into Course, but must stay **server-rendered and
  crawlable** (a collapsible disclosure is fine; deletion or a JS-only/client-fetched
  reveal is not).

---

## 5. Codex Tickets

Each is bounded and independently shippable. All edits in
`wordpress/generate_neo_brutalist.py` unless noted. After any change:
`python3 -m pytest tests/` and `python3 scripts/preflight_quality.py`.

### T0 (PREREQUISITE — do before T1/T5/T9) — Fix `surface_breakdown` normalization

- **Goal:** `build_course_route`'s surface-composition bar chart currently renders
  nothing on every race, because `normalize_race_data()` never copies
  `surface_breakdown` into the normalized `course` dict that `build_course_route` reads
  (`c = rd['course']`; `c.get('surface_breakdown', {})` is always `{}`). Fix the
  normalization gap before restructuring the Course section, or the restructure ships
  with a still-dead chart baked into the new layout.
- **Source-shape reality (verified against `race-data/*.json`):** the raw field is
  **inconsistently located** — found at `race['terrain']['surface_breakdown']` in most
  files that have it, but at `race['course_description']['surface_breakdown']` in
  others (127 races carry the field across both shapes; `crusher-in-the-tushar.json` has
  neither). `normalize_race_data()` must check both locations (terrain-nested first,
  course_description-nested as fallback) when building `course['surface_breakdown']`.
- **Files:** `normalize_race_data` (`335-490`, specifically the `'course': {...}` block
  at `448-455`).
- **Acceptance:** for a race with `terrain.surface_breakdown` set, the normalized
  `course['surface_breakdown']` matches it; for a race with only
  `course_description.surface_breakdown` set, normalization still picks it up; for a race
  with neither, normalization returns `{}` (no crash); `build_course_route` renders the
  surface bar for any race that has the data in either shape; add unit tests covering all
  three cases; tests green.

### T1 — Kill the GIF stack, gate stills on relevance (null-safe, scoped)

- **Goal:** Course section renders ≤2 stills with a valid `ai_relevance >= 4` and
  **0 GIFs** (or ≤1 behind a flag) — without crashing on `ai_relevance: null` and without
  hiding legitimate non-YouTube imagery that has no `ai_relevance` field at all (e.g. a
  future Street View/map image type, which is a real vetted source, not an unreviewed
  YouTube frame).
- **Files:** `build_course_route` (`2352-2488`).
- **[v2 correction — this is a full rewrite of the v1 gate, not a one-line filter add]**
  The gate must:
  1. Apply **only** to images whose `type` starts with `"video-"` (the YouTube-derived
     stills). Do **not** apply an `ai_relevance` requirement to any other image `type` —
     other sources are vetted differently (or simply don't run through this pipeline) and
     must not be hidden for lacking a field they were never meant to carry.
  2. Parse `ai_relevance` null-safely — reuse `_parse_score()` (already used elsewhere
     per repo convention for exactly this "don't crash on `None`/string/empty" problem)
     rather than a bare `p.get('ai_relevance', 0) >= 4`, which throws `TypeError` the
     moment a photo carries an **explicit** `"ai_relevance": null` (the default in
     `.get()` only applies when the *key is missing*, not when its value is `None`).
  3. Cap qualifying video-derived stills at **2**.
  4. Drop/short-circuit the `preview_gifs` block (`2445-2467`) — default to no GIFs (see
     §3 — GIFs are structurally excluded from AI review, so they can never pass a
     relevance gate; don't bother gating them, just don't render them by default).
  5. When no video-derived image qualifies, render no image element (not a broken
     `<img>`, not a fallback placeholder).
- **Required test cases** (add to `tests/test_neo_brutalist.py` or a new test module):
  - a `video-*` photo with `ai_relevance` below threshold (e.g. `2`) → excluded.
  - a `video-*` photo with `ai_relevance` **missing entirely** → excluded, no crash.
  - a `video-*` photo with `ai_relevance` **explicitly `None`/`null`** → excluded, no
    crash (this is the case that would `TypeError` under a naive `>= 4` gate).
  - a `video-*` photo with `ai_relevance` as a **string** (e.g. `"4"`) → parsed and
    included if it clears the threshold, no crash.
  - a **non-`video-*`** (trusted) image type with no `ai_relevance` field at all → still
    renders (proves the gate is scoped, not blanket).
  - a race with **no photos at all** → Course section renders with no image element, no
    crash.
- **Acceptance:** crusher page shows ≤2 stills, 0 GIFs; a race with only
  `ai_relevance=None`/missing photos shows no images; a race with a trusted non-video
  image type still shows it; no broken `<img>`; note (informational, not a blocker): with
  the `>= 4` threshold, ~30 of the 274 races that currently have photographed stills will
  show **zero** images post-gate — expected and acceptable (unvetted imagery is worse
  than no imagery), but call it out in the PR description so it isn't mistaken for a
  regression; tests green.

### T2 — Delete dead `build_photos_section`

- **Goal:** Remove unreachable duplicate renderer.
- **Files:** `build_photos_section` (`2036-2059`) + any import/test references.
- **Acceptance:** function gone; `grep build_photos_section wordpress/` returns nothing;
  tests green.

### T3 — De-dup rider voice: cut coaching-teaser, keep one Riders Report per datum

- **Goal:** `key_challenges[0]` renders once (in Course). Remove `build_coaching_teaser`
  from assembly.
- **Files:** `build_coaching_teaser` (`4500-4544`); assembly list (`6086`); TOC/`active`
  logic if referenced.
- **[v2 correction — blocking dependency, not a plain cut]** `build_coaching_teaser`'s
  CTA is the target of an **active** A/B experiment: `race_coaching_teaser` in
  `wordpress/ab_experiments.py:178`, selector `[data-ab='race_coaching_cta']`, `start:
  2026-03-25`, `end: None` (still running as of this spec). Removing the section without
  first closing the experiment orphans a live selector and breaks whatever tests assert
  the experiments-JSON matches source (`test_experiments_json_matches_source` per
  `CLAUDE.md`). **Sequence required:** (1) pull/decide the experiment result and set an
  `end` date in `ab_experiments.py`, (2) regenerate the experiments JSON
  (`python3 wordpress/ab_experiments.py`), (3) confirm no other selector/test references
  `race_coaching_teaser` or `[data-ab='race_coaching_cta']`, (4) only then remove
  `build_coaching_teaser` from assembly. Do not implement this ticket until step (1) has
  a decision from Matti (GA4-close on the experiment).
- **Acceptance:** the first key-challenge string appears exactly once in rendered HTML
  for crusher; `ab_experiments.py` has no dangling reference to the removed selector;
  page still builds; tests green.

### T4a — Collapse the training-area CTA sprawl into one visual hub (layout only)

- **Goal:** Merge `build_training` + `build_plan_ladder` + `build_train_for_race` into a
  single "Train for This Race" **visual** section — one header, one continuous
  `gg-section-body` — with the standalone `build_email_capture` mid-stack form folded into
  the end of that hub instead of appearing as its own block between Reviews and the
  training area.
- **[v2 correction] This is a layout/DOM-position consolidation only.** It must NOT
  remove or alter: the custom-plan pitch, the 1:1 coaching pitch, the plan-ladder tiers
  (buy CTA or "notify me" email-gate rows), the 8 demand bars, or the workout showcase
  (workout-count/content trimming is T10's job, not this ticket's). Every worker
  contract, form field name, form `id`/CSS-class anchor
  (`gg-email-capture-form`, `gg-plan-ladder-form`, `gg-review-form`, etc.), GA4 event
  name, and existing plan-ladder test must continue to pass unmodified — this ticket
  changes where things sit on the page, not what they say or where they POST.
- **Files:** assembly list (`6083-6088`), `build_training` (`2841`),
  `build_train_for_race` (`4037`), `build_plan_ladder` (`4726`), `build_email_capture`
  (`4631`).
- **Acceptance:** exactly one prep-kit form remains in the training area (the standalone
  mid-stack `email_capture` block is gone as a *separate section*, its form now lives
  inside the hub); `sticky_cta` unchanged; all forms still POST to their existing workers
  with unchanged field names; `tests/test_plan_ladder.py` and any other existing
  plan-ladder/training tests pass unmodified; tests green.

### T4b — Funnel-policy review (decision ticket, not an implementation ticket)

- **Goal:** Separately from T4a's layout work, decide — with GA4 conversion data, not
  intuition — whether any of the *distinct* revenue rungs currently offered in the
  training area (custom plan, 1:1 coaching, static plan-ladder tiers) should be trimmed,
  reordered by priority, or A/B tested against each other.
- **[v2 correction]** `build_training` and `build_plan_ladder` sell **different
  products** (bespoke custom plan / coaching vs. off-the-shelf TP-SKU tiers) and are not
  interchangeable CTAs — do not remove either without conversion evidence.
- **Files:** none — this is a data/decision ticket. Output is a written recommendation,
  not a diff.
- **Acceptance:** N/A for Codex — flag as **requires Matti sign-off before any product
  surface is removed**, informed by GA4 `email_capture`/`cta_click` event data broken out
  by `source`/`cta_type`.

### T5 — Fold Facts & History into the Course area (server-rendered, crawlable)

- **Goal:** History renders as a collapsible sub-block under Course, not a standalone
  section between Overview and Route.
- **Files:** `build_history` (`2259`), `build_course_overview` (`2135`) or
  `build_course_route` (`2352`), assembly (`6083`), `build_toc` (`2062`) links.
- **Constraint (see DON'T-CUT list):** the collapse must be a server-rendered disclosure
  (e.g. `<details>`/`<summary>`, or a CSS-only collapsed state with content already in the
  DOM) — content must be present in the initial HTML for crawlers and no-JS clients, not
  fetched or revealed only via JS.
- **Acceptance:** no top-level "Facts & History" section; history content reachable
  within Course and present in server-rendered HTML (verify via `curl`/no-JS fetch, not
  just a browser check); TOC updated; tests green.

### T6 — Remove duplicate dist/elev render; treat difficulty-gauge removal as a separate visual call

- **Goal:** Remove dist/elev from the hero vitals line (`1987-1996`), keeping
  location·date (this part is a straightforward dedup — D4).
- **[v2 correction] The course_overview difficulty gauge (`2181-2237`, `2253`) is a
  visual-simplification decision, not a mechanical dedup (see D3) — split it out of this
  ticket's acceptance criteria.** If Matti confirms the gauge should go: (a) remove it
  from `build_course_overview`, and (b) in the **same PR**, update or delete
  `tests/test_neo_brutalist.py:712` (`test_course_overview_has_difficulty`) — do not ship
  a PR that leaves that test red.
- **Files:** `build_course_overview` (`2135`), `build_hero` (`1966`),
  `tests/test_neo_brutalist.py` (only if the gauge is cut).
- **Acceptance:** dist/elev appears only in the stat cards (mandatory); gauge
  removal is optional pending Matti's call, and if done, ships with the test update in
  the same PR; tests green either way.

### T7 — Fold tire-guide callout into tire picks; demote news to a tile

- **Goal:** Remove standalone `tire_callout` from assembly (`6084`) and render its link
  inside `build_tire_picks`; keep `news` as a thin collapsible strip, not a numbered
  section.
- **Files:** `build_tire_guide_callout` (`4462`), `build_tire_picks` (`4369`),
  `build_news_section` (`4547`), assembly (`6083-6088`).
- **Acceptance:** one tire block containing the guide link; news still hydrates for
  T1/T2 (news's own ticket numbers, unrelated to this doc's T1/T2); tests green.

### T8 — **[v2 correction: replaces the v1 "run photo QC on all races" ticket]** Coverage assertion + future-ingestion rule

v1 framed this as "backfill `ai_relevance` for ~472 unreviewed races." That's wrong on
two counts (see §3): (a) 472 races have **zero photos**, not unreviewed ones — there's
nothing to backfill for them; (b) `scripts/photo_qc.py`'s `--ai-review` step only
collects `.jpg` files (`photo_qc.py:528`) — **GIFs structurally cannot receive an
`ai_relevance` score** under the current pipeline, so "run QC on all races" would not
actually close the GIF gap T1 depends on. Replace with two smaller, honest tickets:

- **T8a — Coverage assertion for current stills.** Add a script/test that reports, for
  every race with photographed stills (`type` starting `video-`), whether all stills
  carry a parsed `ai_relevance` value. This is visibility, not a backfill mandate — a
  race can legitimately have stills below threshold; the assertion just makes "how many
  races will lose all images under T1's gate" (the ~30/274 number) a tracked, re-runnable
  number instead of a one-time spec observation.
- **T8b — Future-ingestion rule.** Any new video-derived still added to `photos` after
  this spec ships must go through `--ai-review` (and its score must be committed via
  `--apply-seo`) **before** it is eligible to render under T1's gate. Document this as a
  hard rule in `scripts/youtube_screenshots.py` and/or `scripts/photo_qc.py`'s module
  docstring, and in this repo's `CLAUDE.md` under "Known Pitfalls" so it isn't
  rediscovered the next time someone adds a race. GIFs remain out of scope for AI review
  under the current pipeline (per §3) and are not rendered by default per T1 regardless.
- **Acceptance:** T8a script/test runs and reports the current ~30/274 (or updated)
  count; T8b rule is documented in both named locations; no claim that GIF coverage
  reaches any particular percentage, since the current pipeline cannot score GIFs at all.

### T9 — Explicit target-DOM ticket (section order, IDs, and count — acceptance-tested)

- **Goal:** **[v2 correction]** v1 promised "~10-11 visible sections" but the tickets as
  written (T2, T3, T5, T7 merges; T0/T1 image work; T4a layout consolidation) leave
  roughly **14** top-level sections, not 10-11. Make the real target explicit and
  acceptance-test it, instead of shipping a section count nobody agreed to.
- **Target top-level section list and order** (post T0–T8, matching §4's sketch):
  `hero, prep_strip, toc, course (incl. history + surface + images), from-the-field,
  ratings, verdict, racer-reviews, train-for-this-race (incl. plan-ladder + email
  capture), logistics (incl. tires), similar-races, faq, citations` — **13 sections**
  (12 numbered/visible content sections + the always-present `toc`), down from 21 blocks
  today. If a further merge is desired to hit a smaller number, it must be proposed and
  approved as its own ticket with its own DON'T-CUT check — do not silently cut further
  to hit a round number.
- **Files:** assembly list (`6083-6088`) primarily; no builder-function changes beyond
  what T0–T8 already specify.
- **Acceptance:** a test asserts the exact ordered list of top-level section `id`s
  present in a fully-enriched race page's rendered HTML matches the list above (or
  whatever list is actually agreed before implementation — the point is the test locks
  in a real, counted number, not an aspirational one); every ID in the DON'T-CUT list
  (§4) is present; tests green.

### T10 — **[v2 new]** Trim inside the training block (higher leverage than section-wrapper merging alone)

- **Goal:** Merging `build_training` + `build_plan_ladder` + `build_train_for_race` into
  one visual hub (T4a) reduces *section-count* overwhelm but does nothing about the
  overwhelm **inside** that hub: 8 demand bars, the plan mini-configurator, **up to 5 full
  workout protocols** (`WORKOUT_SHOWCASE`, `2906-3967`), and multiple CTAs all stacked in
  one block. This is likely a bigger contributor to "this page is a lot" than the
  section-wrapper duplication T4a fixes. Trim inside the block:
  - Cap the number of **full** workout protocols previewed inline (e.g. 2-3 instead of up
    to 5); move the remainder behind a link to an indexed, crawlable training-guide page
    (reuse or extend whatever page already serves `/race/<slug>/training/` or equivalent,
    if one exists — check before building a new route).
  - Keep the 8 demand bars (they're the compact, scannable form of the training-demand
    model — see D3) and the configurator (it's interactive utility, not passive content),
    but audit whether all 8 bars need to render at full detail inline vs. a condensed
    view with a "see full breakdown" expand.
- **Files:** `build_train_for_race` (`4037`), `WORKOUT_SHOWCASE` usage (`2906-3967`), and
  (if it doesn't already exist) a new or existing indexed training-guide route.
- **Acceptance:** inline workout-protocol count is capped and documented; any protocols
  moved off-page remain reachable via a real, crawlable, indexed URL (not a JS-only
  modal); demand bars still render (full or condensed, per the audit decision); tests
  green. This ticket may ship after T4a/T9 land, since it changes hub *contents* rather
  than hub *position*.

---

## Evidence index (file:line)

- Assembly / render order: `6083-6088`; page skeleton `6136-6150`.
- GIF sampling by time-percent: `scripts/youtube_screenshots.py:69,80,133-160`;
  brightness/blur/composition/text gates `227,258`.
- `photo_qc.py` AI-review file collection is JPG-only: `scripts/photo_qc.py:528`
  (`f.suffix == ".jpg"`) — GIFs (`.gif`, collected separately at line `322` for the
  earlier mechanical-QC layer) never enter `--ai-review`.
- `ai_relevance` computed during `--ai-review`, written to JSON only during
  `--apply-seo`: `scripts/photo_qc.py:783` (`p["ai_relevance"] = ai.get("relevance")`,
  inside `apply_seo_alt_text()`); generator never reads it (`grep relevance` in
  generator → only similar-races logic `4906`).
- Crusher data: 3 stills `ai_relevance` 5/5/4, 5 GIFs `ai_relevance` missing/null;
  274/746 race JSONs carry the field on any photo; verified via `race-data/*.json` scan:
  272 races have `video-*` stills, 30 of those would show zero images under a naive
  `ai_relevance >= 4` gate; 472/746 races have `photos == []`.
- `normalize_race_data` never copies `surface_breakdown` into the normalized `course`
  dict (`335-490`, `course` block at `448-455`); raw field found at
  `race['terrain']['surface_breakdown']` (most common) or
  `race['course_description']['surface_breakdown']` (also occurs), 127 races carry it in
  one shape or the other; `build_course_route` reads `c.get('surface_breakdown', {})`
  from the (always-empty) normalized dict at line ~2391.
- Riders Report reuse (3 calls, not 4): helper `2310`, calls at `2471, 2858, 4350`; the
  4th "RIDERS SAY" surface at `4523` is a direct, non-helper render of
  `key_challenges[0]` that duplicates the `2471` render — the actual hard dup.
  From-the-Field quotes `2518`, Racer Reviews `2810` — distinct sources, not duplicates.
- From-the-Field videos already capped at 3 in `normalize_race_data`:
  `[v for v in race.get('youtube_data', {}).get('videos', []) if
  v.get('curated')][:3]` (line ~472-474).
- Active A/B experiment tied to the coaching-teaser CTA:
  `wordpress/ab_experiments.py:178` (`id: "race_coaching_teaser"`,
  selector `[data-ab='race_coaching_cta']`, `start: 2026-03-25`, `end: None`).
- Test that breaks if the difficulty gauge is cut:
  `tests/test_neo_brutalist.py:712` (`test_course_overview_has_difficulty`, asserts
  `"gg-difficulty-gauge" in html`).
- Email forms: `2685, 4631, 4659`. Plan/coaching CTAs across distinct product surfaces:
  `4031, build_training, 4726, 4529 (cut per T3), 4037, 6046`.
- Demand-adjacent renders (two related-but-distinct models — see D3):
  editorial difficulty: gauge `2181-2237`, radar `2598`; training demand: chips
  `4006-4013`, bars `4072-4087`. Dist/elev: `1987-1996, 2160-2166`.
- Dead renderer: `build_photos_section` `2036` (absent from `6083-6088`).
