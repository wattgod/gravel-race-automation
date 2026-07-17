# Race Page Redesign — Implementation Plan (§5 steps 2-4: extraction, map spike, pilot)

**Written:** 2026-07-17. Scope: this document covers ONLY the work authorized in this
dispatch — design extraction, the map-pipeline spike, and the one-page pilot on
`/race/steamboat-gravel/`. Catalog rollout (handoff §5 step 5) is explicitly out of
scope and requires Matti's review gate.

Governing docs: `docs/specs/RACE_PAGE_REDESIGN_HANDOFF.md` (GATE 0 resolved:
`preview-real-map-card-v5.html` + `preview-amundsen-gg-v3.html`, race detail pages
first), repo `CLAUDE.md`.

---

## 1. What the prototypes actually specify (extraction findings)

Read both canonical prototypes in full (`design-lab/race-page-redesign/preview-real-map-card-v5.html`,
`preview-amundsen-gg-v3.html`, both untracked-at-root copies identical). Key finding:
**the new direction is a warmth/refinement pass on the existing neo-brutalist system,
not a rule-breaking overhaul.**

- **Palette**: `--primary:#1a1613` / `--paper:#f5efe6` / `--tan:#d4c5b9` /
  `--sand:#ede4d8` are **identical** to current `--gg-color-near-black`,
  `--gg-color-warm-paper`, `--gg-color-tan`, `--gg-color-sand`. **CORRECTED during
  planning** (found by running `python3 scripts/audit_colors.py`, not merely
  proposed): the prototype's brighter teal/gold/brown-light accents are NOT new
  tokens to add — this codebase already tried and explicitly reverted exactly those
  three hex values. `scripts/audit_colors.py::BANNED_COLORS` (wired into
  `scripts/preflight.py --deploy`) hard-bans each with a directive to use the
  existing canonical token instead: brighter teal → use `--gg-color-teal` (`#178079`),
  brighter gold → use `--gg-color-gold` (`#9a7e0a`), lighter brown → use
  `--gg-color-secondary-brown` (`#7d695d`). Running the scan against this very plan
  doc (which originally quoted those hex values in prose) confirmed it fires on any
  literal occurrence, doc or code, not just live CSS. **Decision: this pilot
  introduces zero new color tokens.** The route-map SVG, hero, and card treatment all
  use the existing `--gg-color-teal` / `--gg-color-gold` / `--gg-color-secondary-brown`
  / `--gg-color-light-teal` (`#4ECDC4`, already an exact match to the prototype's
  teal-light) tokens as-is. `gravel-god-brand/tokens.json` and `tokens.css` are **not
  touched** by this pilot.
- **Typography**: Sometype Mono (data/labels) + Source Serif 4 (editorial) — **same
  two families already self-hosted**, no font changes needed.
- **Borders/radius/shadow**: the prototype's card component (`.rc`, the flagship "real
  map card") uses zero `border-radius` and zero `box-shadow` on any element that
  matters for the detail-page reskin — the score gauge is an SVG `<circle>` with
  `stroke-dasharray` (not a CSS circle), the tier/discipline pills are square
  (`.pill`), the prestige dots are square backgrounds (`.pip`). The only
  `border-radius`/`box-shadow` uses in the 11 prototypes are decorative
  homepage-mockup flourishes (custom cursor dot/ring, preloader, hscroll pagination
  dots, sticky-header blur shadow, article-card hover shadow) that belong to the
  **homepage/marketing mockup**, not the race detail page, and are **not part of this
  pilot's scope**. Conclusion: **no design-rule test changes are required for the
  pilot.** `.gg-neo-brutalist-page *,*::before,*::after { border-radius:0 !important;
  box-shadow:none !important; }` (generate_neo_brutalist.py:5265-5269) already
  globally enforces this and needs no exception carved out. This is a deliberate,
  verified finding, not an assumption — flagged for sol review.
- **The flagship new element**: `.rc__route` — an SVG line (`.route-glow` blurred
  teal-light stroke underneath, `.route-main` solid teal stroke on top, both drawn
  from the *same* path `d`) rendered over a faint generic road-grid backdrop
  (`.rc__roads`, decorative, NOT the real route). This is the "real map card"
  signature. The path coordinates are pre-baked into a normalized viewBox (e.g.
  `0 0 800 1000`) — exactly the shape produced by projecting lat/lng track points into
  a bounding-box-fit coordinate space.

## 2. What already exists vs. what's net-new

- **Existing today**: race detail pages already embed a *live* RideWithGPS iframe
  (`build_course_overview()`, generate_neo_brutalist.py:2248-2251) for the ~208 races
  with a `ridewithgps_id`. So "there is no map pipeline" (handoff §3) is accurate in
  the sense of *no owned, cached, on-brand-rendered* geometry — not that maps are
  totally absent today. The redesign's job is to replace the generic third-party
  iframe with an owned SVG rendering in the new visual language, using real,
  API-fetched track geometry (never fabricated), cached in-repo.
- **Verified live**: `GET https://ridewithgps.com/routes/{id}.json` is a public,
  unauthenticated, working endpoint that returns `track_points: [{x:lng, y:lat,
  e:elev_m, d:dist_m}, ...]`. Confirmed against steamboat-gravel's real id
  (`53876176`, 3,092 points) during this planning pass.
- **`scripts/fetch_rwgps_routes.py`** already exists and populates `ridewithgps_id` by
  fuzzy-matching race name/distance/location against RWGPS search results (the 208
  floor in `tests/test_race_photos_v2.py`). It does **not** fetch geometry — it only
  resolves the route id. This plan adds a new, separate script for geometry.

## 3. Map pipeline design

**New script: `scripts/fetch_route_geometry.py`**

- Input: every `race-data/*.json` with `race.course_description.ridewithgps_id` set
  (currently 208; re-derived at run time, not hardcoded).
- For each: `GET https://ridewithgps.com/routes/{id}.json`, `User-Agent` identifying
  us + contact (courtesy header, matches existing script's practice), rate-limited to
  1 request per 1.1s (same constant as `fetch_rwgps_routes.py` — no documented RWGPS
  ToS forbidding this for public routes at this cadence, but the courtesy limit stays).
  No API key exists or is needed for public routes.
- Downsample `track_points` (some routes have 3,000-9,000+ points) via a simple
  every-Nth-point stride targeting ~250-400 output points — plenty of visual fidelity
  at card/hero scale, keeps the inline SVG `path d` small.
- Project lon/lat to a normalized `0 0 800 600` (or `800 1000` for tall/narrow routes —
  pick orientation by aspect ratio of the bounding box, matching the two viewBox shapes
  seen in the prototype) viewBox: equirectangular with `x' = (lon - lon_min) *
  cos(lat_mean)`, `y' = -(lat - lat_min)` (inverted, north-up), then scale-to-fit with
  ~4% padding, preserving aspect ratio (no distortion).
  Note: this is presentational (a stylized wayfinding SVG, not a navigational map), the
  same tolerance a printed race poster would take.
- Cache to **`data/route-geometry/{slug}.json`**: `{slug, ridewithgps_id, route_name,
  source_url, fetched_at (ISO 8601 UTC), point_count, sampled_count, distance_mi_from_geometry,
  viewbox, path_d}`. Committed to the repo — deterministic rebuilds, zero live API
  calls at page-generate time (generator only reads this cache file).
- **Fallback (no rwgps_id, ~527 races)**: the template layer renders an explicit
  "no verified route on file" state — a labeled placeholder (location pin + race
  name/location text on the paper background, mono-font caption
  `NO VERIFIED ROUTE ON FILE`), never a fabricated line or a generic city-grid
  standing in for a real route. This satisfies the handoff's explicit "DO NOT
  fabricate routes." The existing RWGPS iframe embed (when `map_url` alone, without a
  captured `ridewithgps_id`, resolves one) remains the interactive fallback shown below
  the static hero visual, exactly as it renders today — nothing about the current
  iframe embed is removed for races that have it, it is supplemented.
- Coverage run: this pipeline runs for **all 208** RWGPS races in this dispatch (not
  just steamboat-gravel) — at ~1.1s/request that's under 4 minutes, well within
  budget, and gives real coverage numbers for the final report instead of a
  single-race spike. Failures (404, malformed JSON, route since made private) are
  logged and skipped, not retried indefinitely; the slug simply falls back to the
  no-route state until re-run.

## 4. Template layer design

**New module: `wordpress/generate_race_page_v2.py`** (sibling to
`generate_neo_brutalist.py`, not a rewrite of it).

Rationale for a new module instead of editing the 6,396-line file in place: the
dispatch requires that **zero other race pages change** as a side effect of this work
(catalog rollout is a separate, gated step). Editing `build_hero`/`build_course_overview`
in place would change the default `--all` generation path immediately. A sibling
module that **imports** the DATA-layer and unrelated section builders from
`generate_neo_brutalist.py` and only replaces the presentation-critical pieces gets
genuine reskin behavior for the pilot page while leaving the 6,396-line file, and every
other page's output, byte-identical.

Imported unchanged (DATA layer + sections outside this pilot's visual scope, per
handoff §4 "carry all of it forward"): `normalize_race_data`, `_parse_score`, all
JSON-LD builders (`build_sports_event_jsonld`, `build_faq_jsonld`,
`build_breadcrumb_jsonld`, `build_webpage_jsonld`), `build_nav_header`, `build_history`,
`build_pullquote`, `build_from_the_field`, `build_ratings`, `build_verdict`,
`build_racer_reviews`, `build_email_capture`, `build_visible_faq`, `build_news_section`,
`build_training`, `build_plan_ladder`, `build_train_for_race`, `build_prep_strip`,
`build_logistics_section`, `build_tire_picks`, `build_tire_guide_callout`,
`build_coaching_teaser`, `build_date_reminder`, `build_similar_races`,
`build_citations_section`, `build_footer`, `build_sticky_cta`, `build_toc`,
`build_inline_js`, `get_ga4_head_snippet`, `get_font_face_css`, `get_preload_hints`,
`esc`, `_safe_json_for_script`. This is the concrete list of "what survives" —
identical HTML/behavior to production for these sections; only their surrounding CSS
tokens shift (warmer accent colors cascade in via the new stylesheet, same class
names).

Net-new / replaced (the visual redesign surface):
- `get_page_css_v2()` — same structural CSS as `get_page_css()` (layout, spacing,
  component rules) built entirely on **existing** tokens (per §1's correction — no new
  color tokens) plus the new `.gg-route-map` component rules (`.gg-route-map__roads`,
  `.gg-route-map__glow`, `.gg-route-map__line`, `.gg-route-map__empty`).
- `build_hero_v2(rd)` — same content contract as `build_hero` (tier label, series
  badge, h1, vitals line, taking-a-break strip, GG score, rider score/ask-to-rate) with
  updated visual treatment (serif h1 sized per the mockup's editorial scale, gold
  top-accent rule). No new data fields, no removed data fields — verified line-by-line
  against `build_hero` before implementation.
- `build_course_map_v2(rd)` — new function, reads `data/route-geometry/{slug}.json` if
  present and renders the glow+line SVG inline (server-generated numeric path data,
  not user input — no innerHTML/XSS concern, follows the same string-templating
  pattern as the rest of the file); falls back to the no-verified-route placeholder:
  MUST always render one of the two states, and — when `ridewithgps_id` or a
  `map_url`-derived id exists — keeps the existing RWGPS iframe embed underneath as the
  interactive/authoritative map, unchanged from `build_course_overview`'s current
  behavior. Stat cards, difficulty gauge, calendar export, nearby-races block are
  reused via the same logic as `build_course_overview` (ported, not reinvented, since
  they're presentational not data-shape changes — this is the one section where "new
  template layer" and "reuse existing" overlap; the port keeps the same stat tuples,
  gauge thresholds, and calendar/ICS logic byte-for-byte, changing only wrapper markup
  and class names).
- `generate_page_v2(rd, race_index, external_assets)` — same assembly contract as
  `generate_page`, section order preserved, TOC/active-section logic reused as-is.

**Deliberately unchanged in this pilot** (explicitly flagged, not silently dropped):
the marketing-mockup flourishes from `preview-amundsen-gg-v3.html` (preloader, custom
cursor, grain animation overlay, marquee ticker, horizontal-scroll showcase) belong to
homepage/index-page surfaces, which are out of scope per GATE 0 ("race DETAIL pages
FIRST... homepage come after"). None of them are needed to satisfy "reskin of the race
detail page," and several (custom cursor, preloader) would need their own
accessibility/reduced-motion review before touching a production page — deferred to
the homepage-scope follow-up explicitly named in the handoff, not silently cut.

## 5. Design-rule / test changes

Per §1's finding: **no changes to `border-radius`/`box-shadow` neo-brutalist tests are
required, and (per the corrected §1 finding) no brand-token additions are required
either** — `gravel-god-brand/tokens.json`/`tokens.css` and
`wordpress/brand_tokens.py::COLORS` are untouched by this pilot; `python3
scripts/audit_colors.py` passes with zero new findings once the plan doc's own
now-corrected prose is clean of the banned hex strings.

- New test file `tests/test_race_page_v2.py`: asserts `generate_page_v2()` output for
  steamboat-gravel contains — h1 with race name, GG4 snippet, font-face CSS, schema.org
  `SportsEvent` + `FAQPage` JSON-LD blocks, plan-ladder block, similar-races links,
  no `innerHTML` with data-derived values, no inline `onclick`/`onsubmit`, `data-ab`
  attributes preserved where the reused sections use them, and — new to this
  redesign — that the route-map section renders exactly one of {real route SVG,
  no-verified-route placeholder} and never both/neither.
- `scripts/preflight_quality.py::check_all_generators_token_refs()` (or equivalent) is
  checked against the new module before commit — if it enumerates generator files by
  path pattern, `generate_race_page_v2.py` must satisfy the same "no hardcoded hex"
  scan the existing generators do.

## 6. Pilot cutline

Exactly one artifact ships: `/race/steamboat-gravel/`, generated by
`generate_race_page_v2.py` via a small pilot driver (e.g.
`python3 wordpress/generate_race_page_v2.py steamboat-gravel --output-dir
wordpress/output_v2_pilot`), writing to an **isolated output directory** — never
`wordpress/output/`, which is what `generate_neo_brutalist.py --all` populates and
must stay untouched so the other 734 pages' local build artifacts aren't disturbed by
this pilot's asset-hash cleanup logic (`write_shared_assets()` deletes stale
`gg-styles.*.css` in whatever directory it's pointed at).

Deploy: `scripts/push_wordpress.py --sync-pages --pages-dir wordpress/output_v2_pilot`
— **correction to the dispatch's literal staging-dir description**: verified against
`sync_pages()` (push_wordpress.py:1360) that it expects a **flat** `{slug}.html` file
(plus an optional `assets/` subdir) in the given `--pages-dir`, and builds the
`{slug}/index.html` remote structure itself — not a pre-built `steamboat-gravel/index.html`
in the staging dir as the dispatch prose suggested. The staging dir for this pilot will
contain exactly `steamboat-gravel.html` + `assets/` (new-hash CSS/JS + fonts). The
tar+ssh extraction target (`~/www/gravelgodcycling.com/public_html/race`) is shared
with all other live pages but extraction only adds/overwrites the `steamboat-gravel/`
subdir and any files whose hashed names differ from what's already live — it cannot
remove or corrupt the other 734 live pages.

Post-deploy verification: `curl -I` for 200, then fetch and grep for: `<h1>` containing
"SBT GRVL" or the race name, `application/ld+json` schema blocks present, plan-ladder
block markup present, existing internal link targets (similar-races hrefs, tire/prep-kit
subpage links) unchanged from the current live page (diff canonical URLs before/after).

## 7. Open questions (see §8 for review disposition)

1. Is the "no test-rule changes needed" finding (§1) actually correct, or is there a
   test elsewhere in the 7,153-count suite that would break on the new `.gg-route-map`
   markup/classes even without a radius/shadow violation?
2. Is the sibling-module approach (§4) the right call vs. an in-place feature-flagged
   branch inside `generate_neo_brutalist.py`? Tradeoff: sibling module = zero blast
   radius on the other 734 pages but duplicates the assembly/TOC logic that catalog
   rollout will need to reconcile later; in-place flag = less duplication now but risk
   of an `--all` run accidentally picking up the new path.
3. Is projecting RWGPS track points into a stylized (non-georeferenced, bounding-box-fit)
   SVG defensible as "real per-race road geometry, never fabricated," given it's not a
   navigationally accurate projection? The prototype's own city-grid backdrop is
   explicitly decorative/generic — only the `.rc__route` line needs to be real; that's
   what this plan delivers.
4. Any RWGPS ToS/rate-limit concern with fetching full `track_points` (not just search
   metadata) for 208 routes in one run, beyond the 1.1s courtesy delay already used by
   the existing script?

## 8. Adversarial review disposition

Per the global working agreement, `codex exec -m gpt-5.6-sol -s read-only -C .` was run
three times against this plan (brief + governing docs), foreground, waiting for
completion each time. **All three runs failed with "Selected model is at capacity"**
before producing a final verdict — a service-side capacity error, not a rejection of
the plan. Each run did real, visible investigative work before dying (transcripts in
`docs/specs/race-page-redesign/` review logs are not committed — they're multi-MB
tool-call transcripts; the corrections below are what's load-bearing):

- Run 1 independently curl-verified `GET https://ridewithgps.com/routes/{id}.json`
  (200 OK, confirming §2's live-endpoint claim) and read
  `tests/test_neo_brutalist.py` / the DATA-layer functions before running out.
- Run 2 read `docs/GRAVEL_GOD_SCORING_SYSTEM.md`, `.claude/skills/deploy-safely/SKILL.md`,
  and — the one finding that changed this plan — **found `scripts/audit_colors.py`
  and its `BANNED_COLORS` dict** while investigating token questions, before running
  out on the web-search step verifying RWGPS's official API status.
- Run 3 re-confirmed the `sync_pages()` flat-file reading (matching §6's correction)
  before running out.

I independently pulled the `BANNED_COLORS` thread run 2 surfaced, read
`scripts/audit_colors.py` directly, and ran it — it flagged this plan doc itself for
the three hex values quoted in the original §1/§5 draft, confirming both that the scan
is real/enforced (`scripts/preflight.py --deploy` runs it) and that the plan's original
token-addition proposal was wrong. §1 and §5 above are corrected accordingly. This is
the single material correction from this review pass; questions 1, 3, and 4 above got
no adversarial answer (capacity failures prevented it) and are carried forward as open
risk, mitigated as follows before proceeding: (1) addressed directly by building
`tests/test_race_page_v2.py` and running the full suite — if a rule-name collision
existed it will surface as a test failure, not a silent gap; (3) accepted as
reasonable per the plan's own reasoning (§3) — the route line is real per-race
geometry, only the projection is stylized, which is what "not fabricated" requires;
(4) accepted the existing script's 1.1s precedent as the working norm for this exact
API, with fetch failures logged/skipped rather than retried aggressively.
