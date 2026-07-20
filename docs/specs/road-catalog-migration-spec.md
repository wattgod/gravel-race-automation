# Road Catalog Migration: gravelgodcycling.com → roadielabs.com

Drafted 2026-07-18 (Fable). Status: AWAITING OWNER GO. Nothing in this spec executes
without Matti's explicit approval, phase by phase.

## Why (evidence)

gravelgodcycling.com currently serves live race pages for four disciplines
(web/race-index.json, verified live 2026-07-18):

| discipline | pages | GA4 views (90d) | share of /race/* views |
|---|---|---|---|
| gravel | 353 | 3,183 | 62.5% |
| **road** | **364** | **404** | **7.9%** |
| bikepacking | 14 | 165 | 3.2% |
| mtb | 4 | 51 | 1.0% |

- The 364 road pages (Mallorca 312, Paris-Brest-Paris, La Marmotte, GFNY…) duplicate
  the Roadie Labs catalog on GG's stronger domain — GG competes with its own vertical
  for every road query, which contradicts the northstar (each vertical owns its sport)
  and makes GG's "every gravel race, rated" claim false.
- Traffic risk of removal is negligible: all 364 road pages combined earn ~4.5
  views/day on GG (top page: race-across-america, 34 views/90d). The SEO equity is
  worth 301ing, not worth keeping.
- Origin: road races were built inside GG before the Sprint 41 fork and never removed.

## Decision summary (owner ratified the framing 2026-07-18; execution NOT yet approved)

1. **Road (364): migrate to roadielabs.com with per-slug 301s.**
2. **Bikepacking (14) + MTB (4): KEEP on GG** as a labeled "Ultra & Bikepacking" shelf;
   suppress the per-race custom-plan CTA on bikepacking pages (fails the Built-For fit
   test — a 12-week plan cannot honestly claim to prepare a 2,700-mile self-supported
   ultra); the coaching CTA stays (coaching honestly serves ultra prep). MTB keeps
   plan CTAs (Leadville-class events are classic trainable targets). No fourth brand
   for 18 races.

## Preconditions (strongly recommended before Phase 1)

- **P0: merge `race-page-canonical-rollout` into road main.** RL race pages currently
  deploy ONLY from that branch (see the landmine note in road CLAUDE.md — regenerating
  from main overwrites the approved spine; it fired 2026-07-18). This migration adds
  new RL race pages, which means regenerating the RL catalog. Doing that from an
  unmerged branch multiplies the standing foot-gun. If Matti prefers not to merge yet,
  every RL regen/deploy in this spec runs from a worktree of that branch instead.
- P1: confirm no other session is mid-flight in either repo at execution time.

## Phase 0 — Reconciliation (read-only, no deploys)

Build `docs/specs/road-migration-map.json` by comparing GG's 364 road entries against
RL's 427 race-data profiles:
- Match by slug, then by normalized name (case/punct/edition-year insensitive), then
  by (location, month, distance±10%) heuristic; every heuristic match is flagged for
  human review, never auto-trusted.
- Output classes: `exact` (GG slug == RL slug), `renamed` (match, different slug),
  `gg_only` (no RL profile — must be ported), `ambiguous` (parked for Matti).
- Also map the 364 GG markdown-mirror URLs (/race/{slug}.md) to RL equivalents.
- Deliverable: counts per class + the parked list. OWNER GATE: Matti reviews the map
  (especially `renamed` and `gg_only`) before anything moves.

## Phase 1 — Roadie Labs side first (targets must exist before any redirect)

- Port every `gg_only` road profile into road-race-automation/race-data/ through RL's
  OWN quality gates (schema/validate_profile, audit_fabricated_claims, citations;
  fondo_rating conversion via the migrate_from_gravel.py precedent — check its
  gravel_god_rating→fondo_rating mapping still matches current schema).
- Regenerate RL: race pages (FROM THE SPINE SOURCE per P0), race-index, sitemap,
  llms.txt/llms-full.txt, markdown mirrors, search copies.
- Deploy RL, verify every migration-map target returns 200 with the spine marker.
- IndexNow-ping all new RL URLs.

## Phase 2 — GG removal

- Move the 364 road race-data JSONs out of gravel-race-automation (recommendation:
  `git mv` into `race-data-archived/road/` in the same commit that removes them from
  generation — history preserved, accidental regen impossible; do NOT hard-delete).
- Regenerate GG: race-index, sitemap, homepage (counts are dynamic — hero/ladder will
  say ~371), rankings/tier hubs/state hubs/vs pages/calendar (audit each generator for
  road leakage), llms files, markdown mirrors (road .md files removed from
  web/markdown/ and the server), search copies.
- Delete the 364 road page directories AND the 364 road .md files on the GG server
  (tar+ssh rm list generated from the map — no wildcards).
- GG tests gain a catalog-contract guard: `discipline == "road"` count in
  web/race-index.json must be 0.

## Phase 3 — 301s

- Extend the managed REDIRECT_BLOCK mechanism (scripts/push_wordpress.py
  sync_redirects — same mechanism as the llms.txt rule) with a generated section:
  - `/race/{gg-slug}/` → `https://roadielabs.com/race/{rl-slug}/` [R=301,L]
  - `/race/{gg-slug}.md` → `https://roadielabs.com/race/{rl-slug}.md` [R=301,L]
  - 364×2 explicit rules, generated from the map file (never hand-written). Verify
    .htaccess size/eval cost is acceptable on SiteGround (~80KB; test on deploy with
    immediate homepage/race-page/article health checks, same as the llms rollout).
- Rules go ABOVE the WordPress block; gravel slugs must be verified non-overlapping
  with the redirect list before deploy (a gravel page must never 301 away).
- Rollback: sync_redirects with the section removed restores everything instantly;
  Phase 2's archived JSONs allow full page restoration if needed.

## Phase 4 — Signals

- Resubmit both sitemaps in GSC + Bing (both sites are verified in Bing as of
  2026-07-18; BingSiteAuth.xml files on RL/XC roots must survive).
- IndexNow-ping: the 364 removed GG URLs (so crawlers re-fetch and see the 301s) and
  all RL targets again.
- Watch GSC/Bing coverage for 404s/redirect errors for 2 weeks; keep the map file as
  the audit source of truth.

## Phase 5 — Bikepacking shelf (GG-side, independent of road phases)

> RESEARCH UPDATE 2026-07-20 (docs/research/ultra-bikepacking-coaching-market.md,
> verified/cited): the 12-week plan suppression below is CONFIRMED honest — no live
> ultra vendor sells a 12-week product; practitioner formats are 4-6 month plans,
> 6-9+ month coaching, and $45-80 consults. The coaching CTA staying is also
> confirmed honest: verified ultra coaches deliver through exactly GG's machinery
> (TrainingPeaks subscription, weekly-adaptive review, durability focus), the top
> vendor's roster is FULL (supply-constrained market), and GG's Mid price sits below
> the verified $400/mo benchmark. See optional Phase 6 for the ultra product ladder;
> the credibility gap (every verified vendor is a finisher/winner of these races) is
> the owner-level consideration there.

- Rankings/search/homepage filters: bikepacking+mtb presented as "Ultra & Bikepacking"
  shelf, not blended into gravel tier lists (search UI already filters by discipline;
  audit the tiered rankings sections and tier hubs for blending).
- Race-page generator: suppress the custom-plan CTA block for `discipline ==
  "bikepacking"` (the spine's plan offer + prep-strip plan CTAs); coaching footnote
  unchanged. MTB unchanged. Tests assert: no plan CTA on the 14 bikepacking pages,
  coaching CTA present, gravel pages unaffected (spot count).
- llms.txt/llms-full.txt: bikepacking entries labeled with their discipline.

## Phase 6 (OPTIONAL, owner decision) — Ultra product ladder

If Matti wants to SERVE ultra prep rather than just gate it (research says he can,
honestly, in the right formats — docs/research/ultra-bikepacking-coaching-market.md):

- 6a. **Ultra consult SKU** ($45-80/call benchmark; two vendors prove the format):
  race-strategy + logistics consults built on GG's race-demand database — the
  cheapest honest entry, and the piece where the database is a real differentiator.
- 6b. **4-6 month ultra plan + bundled prep guide** ($65-75 benchmark, UltraMTB
  template): a NEW SKU format, not the 12-week engine output; prep guide covers
  gear/sleep/resupply/mental chapters (research-sourced, no fabricated experience).
- 6c. **1:1 ultra coaching**: existing coaching machinery + explicit non-training
  scope (route/resupply planning, sleep strategy, pre-written quitting rules —
  McSharry's verified package is the model). Longer minimum (6-9 months) than the
  4-week gravel cycle.
- CREDIBILITY GATE (Matti's call, blocks 6b/6c positioning): every verified vendor's
  authority rests on personally finishing/winning these races. Options: transparent
  framing (coach-the-training + research-backed logistics, no first-person claims),
  partnering/guest expertise, or Matti racing one. NO copy may imply first-person
  ultra racing experience that doesn't exist — this is a hard voice/trust rule.
- If Phase 6 ships, Phase 5's plan-CTA suppression on bikepacking pages is replaced
  by CTAs to the ultra SKUs instead.

## Process gates

- Sol adversarial review of this spec against BOTH repos before Phase 0 executes,
  and again on the Phase 3 redirect generator before its deploy.
- Owner gates: after Phase 0 (map review), before Phase 2 (the removal commit), and
  before Phase 3 (the redirect deploy).
- Each phase lands as its own commit(s) with tests; no `git add -A`; concurrent-
  session check before touching either repo.

## Open decisions for Matti

- D1: Merge `race-page-canonical-rollout` into road main first? (Recommended: yes.)
- D2: Archive location for the 364 GG road JSONs (`race-data-archived/road/` in gravel
  repo vs moving them wholesale into the road repo). Recommended: archive in gravel;
  RL imports only what it lacks, through its own QC.
- D3: Timing — no seasonal urgency found; the 90-day traffic is negligible either way.
- D4: The 4 MTB races stay on GG under the Ultra shelf — confirm, or park them too.
