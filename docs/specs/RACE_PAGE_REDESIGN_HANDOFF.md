# RACE PAGE REDESIGN — HANDOFF ("the new races layout")

**Written:** 2026-07-17 by Fable. **Mandate:** Matti, 2026-07-17: the new races layout
"doesn't exist in production — give me a handoff so another agent can make that happen."
This document is that handoff. The DESIGN originates in a parallel session of Matti's whose
conversation history is not available here — the prototypes below are the only artifacts.

---

## 1. What exists (all preserved in `design-lab/race-page-redesign/`, committed)

Eleven browser-openable prototypes, copied verbatim from the repo root where that session
left them untracked (root copies left in place; the design-lab copies are canonical for
this handoff). Lineage by filename + `<title>`:

| File | Title | Reading |
|---|---|---|
| `preview-amundsen-gg.html` / `-v2` / `-v3` | "Gravel God Cycling — v3 Full Mockup" (v3) | Full-page site mockup. Hero: "Every race. Every mile. Mapped." Preloader/progress/gold-bar sections. **v3 = latest.** |
| `preview-race-cards-v4.html` | "GG Race Cards — Cartographic Route Map Concept" | Bento-grid race cards; each card carries a simplified real road-grid map (comments name "Emporia, KS grid"). |
| `preview-real-map-card.html` … `-v5` | "GG Race Cards — Clean Final" (v5) | Card iterations with REAL road geometry per race — comments name "real Steamboat Springs roads", "real San Marcos roads". **v5 = "Clean Final" = latest.** |
| `preview-hybrid-card.html` | — | Hybrid of the above directions. |
| `preview-integrations.html` | — | Integration exploration (large; likely cards embedded in existing page shells). |

**GATE 0 — before any code: confirm with Matti (a) which variant is canonical (inference:
`real-map-card-v5` for cards + `amundsen-gg-v3` for the page-level direction, being the
"Clean Final"/latest names — but the design conversation happened in his other session,
so CONFIRM, don't infer), and (b) the scope of "races layout":** race DETAIL pages
(`/race/<slug>/`), the race CARDS on search/index/state-hub surfaces, the homepage, or all
three. Matti's complaint was raised while looking at `/race/steamboat-gravel/`, so the
detail page is at least in scope.

---

## 2. Production surfaces you will touch

All in this repo (`wattgod/gravel-race-automation`, branch `main`, deploys to
gravelgodcycling.com — a WordPress shell serving static generated pages):

- `wordpress/generate_neo_brutalist.py` (6,396 lines) — generates all ~735 race detail
  pages. The current live layout. A redesign either rewrites its template layer or
  replaces it; its DATA layer (normalize_race_data, scoring, FAQ/schema/GA4/similar-races)
  should survive.
- `wordpress/generate_state_hubs.py`, `generate_vs_pages.py`, `generate_homepage.py`,
  `web/gravel-race-search.js` + `web/race-index.json` — every surface that renders race
  CARDS today.
- `gravel-god-brand/tokens/tokens.css` — brand tokens. The prototypes may introduce new
  tokens; they must land in tokens.css, never as hardcoded hex (CI-enforced).
- Hashed assets `gg-styles.<hash>.css` / `gg-scripts.<hash>.js` — never edit in place;
  regenerate with new hashes (repo CLAUDE.md pitfall #9).

## 3. The key engineering unknown: the maps

The card design's signature is REAL per-race road geometry. There is no map pipeline in
this repo today. Facts to build on:
- `race-data/<slug>.json` → `course_description.ridewithgps_id` exists for ~208 of 735
  races (count enforced as a floor in `tests/test_race_photos_v2.py`). RWGPS route
  polylines are fetchable per route id (public routes; check ToS/rate limits).
- The other ~527 races have location lat/lng (most profiles) but no route — the design
  needs a documented fallback card state (town road-grid like the Emporia concept, or a
  no-map variant). DO NOT fabricate routes.
- Whatever pipeline you build: cache the geometry into the repo (deterministic rebuilds,
  no live API calls at generate time), and record provenance per race.

## 4. Hard constraints (all currently CI/test-enforced — read repo CLAUDE.md first)

- XSS: no innerHTML with data-derived values; `_safe_json_for_script()` for JSON-in-script.
- Every generated page: `get_ga4_head_snippet()`, `get_font_face_css()`,
  `get_site_header_js()`; email forms POST to their Cloudflare workers + honeypot;
  `addEventListener` only (no inline handlers); A/B selectors use `data-ab`.
- Progressive enhancement: content visible without JS (`gg-animations-ready` pattern).
- The current "neo-brutalist" rules (no border-radius/box-shadow) are the OLD design
  language — if the new direction breaks them, update the design-rule TESTS deliberately
  in the same commit, never silently.
- 7,153-test suite green + `scripts/preflight_quality.py` before any deploy.
- Deploy: race pages via tar+ssh `{slug}/index.html` (`scripts/push_wordpress.py
  --sync-pages`), then SiteGround cache purge (`wp sg purge`); sitemap regen if URLs
  change (they should NOT — keep slugs).
- SEO: this is 1,538 indexed URLs of ranking traffic (the northstar engine). Preserve:
  URLs, h1s, schema.org blocks, FAQ content, internal links (similar-races, tire/prep-kit
  subpage links), OG images, and the TP plan blocks + marketplace links. A redesign is a
  reskin of the same content graph, not a content rewrite.
- Race pages now include: "taking_a_break" hero strip (8 races), plan-ladder block with
  marketplace links, email-gate for private plans — carry all of it forward.

## 5. Suggested execution shape (adapt as you see fit)

1. GATE 0 (variant + scope) with Matti.
2. Extract the chosen prototype into a real template layer + tokens; write a DESIGN.md
   for the new direction (what changed vs neo-brutalist, which rule-tests updated).
3. Map pipeline spike: fetch + cache polylines for the 208 RWGPS races; decide + build the
   fallback for the rest; render into the card/page.
4. Pilot ONE page end-to-end (suggest `/race/steamboat-gravel/` — Matti is actively
   looking at it) + one card surface; deploy the pilot only; Matti review gate.
5. Catalog rollout: regenerate all pages/cards, full test suite + preflight, deploy,
   purge, spot-verify ~10 pages incl. a taking-a-break race, a private-plan race, a
   not-yet-rated race, and a renamed race (truckee-tahoe-gravel).
6. Per the global working agreement: run an adversarial GPT-5.6-sol review of your
   implementation plan BEFORE building, and again before the catalog deploy (this is
   public-facing, SEO-load-bearing work — exactly the weight class the rule exists for).

## 6. Non-goals / don't touch

- TrainingPeaks listing descriptions (v3.1, just shipped catalog-wide — separate system,
  `gravel-god-training-plans` repo).
- Race-data fact bases (recently web-verified; the redesign consumes, never edits).
- The `/questionnaire/` Elementor page (drifted widget — separate backlog item).
- Roadie Labs / Nordie Labs sites (their redesigns are separate workstreams).
