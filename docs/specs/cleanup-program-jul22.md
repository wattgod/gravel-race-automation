# Cleanup Program — 2026-07-22 (converged: Claude × GPT-5.6-sol, 2 rounds)

Status: CONVERGED. Execution gated on Matti's go (WS5 additionally needs a
content decision — see the two-option memo at bottom).

Context: same-day incidents — 239 dead sitemap URLs (stale tires/VS), 5
fabricated-race blog previews live, stale /blog/ tree (351 vs 242), and
per-tire review pages live-200 citing fabricated races. Root causes: (A)
tar+ssh deploys add-but-never-delete → live trees drift from generated output;
(B) 10 fabricated profiles persist in race-data + derivatives, suppressed only
by seven copy-pasted exclusion sets; (C) trust leaks: synthetic Product-schema
ratings published for 13 tires.

## WS1 — Fabricated root purge + /tire/ trust fixes (FIRST, ~3h)
1. Canonical tombstone registry `config/tombstones.json` (slug, reason,
   redirect target); all seven exclusion sets import it (generate_index,
   generate_og_images, generate_race_pack_previews, generate_tire_guide, …).
2. Delete the 10 profiles. Purge ACTIVE derivatives: race-dates, tire maps via
   `rebuild_tire_indexes.py` (add tombstone exclusion; cleans both maps +
   race_appearances in data/tires/*.json), tp-sku-map,
   website-data/difficulty-rankings.json, alternative_slugs refs, route
   geometry, quotes, photos, ~37 video briefs. KEEP historical evidence
   (research dumps, GSC snapshots, immune ledger, redirect rules, specs).
3. Remove the synthetic AggregateRating proxy branch
   (generate_tire_pages.py:~1236): no aggregateRating below 3 real approved
   reviews, ever (fabricated structured data in Google rich results; violates
   scoring-and-veracity SKILL real-submissions-only rule). Reverse the tests
   that assert the proxy (tests/test_tire_reviews.py:~462).
4. Build `--sync-tire-pages`: generate BOTH /tire/ classes (reviews +
   comparisons) into one fresh staging tree, validate the exact directory set,
   deploy to /tire/, include in --deploy-all. (Today /tire/ is live with NO
   deploy path — orphaned manual deploy.)
5. URGENT deploy leg: regenerate /tire/ from purged data → deploy → purge
   cache → scan expected AND remotely-discovered /tire/*/index.html for
   fabricated names and proxy ratings (target: zero).
6. Fix immune index-drift check to compare (profiles − tombstones); post-
   delete assert 734 files == 734 index entries; zero tombstoned slugs in any
   active catalog/output; full pytest + preflight_quality; Railway API 404s
   for the 10 slugs.
7. TP-catalog check: tp-sku-map maps all 10 fabricated slugs to SKU families —
   verify via tp-maintenance tooling whether TrainingPeaks lists any plan named
   for a fabricated race; if yes flag to Matti (TP-side deletion is his call).

## WS2 — Tire-crosslink fix (cherry-pick, ~1-2h)
Cherry-pick SOURCE changes only from origin/intel/tire-crosslink-404s (its
race-index.json regen is stale): prep-kit conditional crosslink, state-hub
has_tire_guide filter, index flag. Regenerate race-index at HEAD post-WS1.
Focused tests: prep-kit ± primary, hubs mixed flags, index flag; fix the
untracked tests/test_sprint_ralph_wiggum.py fixture (currently expects
unconditional tire links). Harden generate_tire_guide.py --all to require
tire_recommendations.primary (else regeneration resurrects the 217 pages
removed Jul 22). Deploys from FRESH staging dirs only: prep-kits via
--sync-prep-kits --prep-kit-dir <empty tmp>; state hubs via --sync-pages
--pages-dir <tmp asserting exactly 60 best-gravel-races-* dirs>. Validate all
emitted /tires/ links against the canonical 316 set pre-upload. Then delete
both intel branches (crosslink after cherry-pick; link-check-sg-captcha is
superseded by main).

## WS3 — Deploy-parity detector (gravel first, ~3h)
Three-way model: (1) expected manifest from shared zero-render page rules —
each page class exposes pure `iter_expected_pages(context)` returning
PageSpec(url, owner, source, indexability); generators AND manifest builder
import the same predicates; inputs = canonical data + tombstones + static-page
registry + frozen as_of date. (2) SSH inventory of live webroot index.html
paths. (3) HTTP health of expected URLs. Nightly manifest↔SSH↔HTTP; weekly CI
empty-staging build asserting rules-derived == build-derived; generator/rule
changes trigger that proof immediately. Coverage: race/vs/hubs/calendar/series,
prep-kits, plan pages, race tire guides, /tire/ reviews+comparisons, blog all
categories, articles; explicit exclusions for assets + WordPress/money-path.
Findings: ORPHAN + UNDEPLOYED, YELLOW, URL-identity in detail. Seeded
acceptance tests (orphan, undeployed, nested, malformed SSH, allowlists).
First full live inventory is review-only. Port to roadie/xc only after one
clean gravel live cycle. Also migrate generate_sitemap.py off output-tree
enumeration onto the shared rules.

## WS4 — Road catalog existence audit (async)
RESUME the in-flight R4 eligibility program (426 profiles; 137 done: 118
active / 9 defunct / 6 cancelled / 4 unknown; 3 waves landed 2026-07-22).
Audit only the 289 without evidence; import existing race.eligibility;
R4-schema-compatible; evidence-only (no overwrites/deletions/deploys).
Fabricated-claims backlog (169 findings / 89 races) = separate workstream.

## WS5 — Blog content (Matti decision — memo below; exec ~1h on approval)
On approval: pull 158 previews + 46 recaps (fresh allowlisted blog staging
dir — add-only trees make "stop generating" insufficient). Fix
generate_blog_index.py counting articles/index.html as an article. Roundup
survivors (if Option A) recorded in config/indexable-roundups.json consumed by
generation, sitemap, and deploy; every survivor passes gates first: temporal
correctness (filter_by_month currently IGNORES its year arg —
generate_season_roundup.py:87), unique-intent/cannibalization review,
Friend-Test + slop lint, link/claim validation, infra parity (GA4, shared
header, fonts/tokens, safe JSON, dynamic totals — generator currently
hardcodes noindex, raw colors, and a stale "328 races" claim).

### WS5 decision memo (two options)
A. RECOMMENDED — Curate & index: keep monthly (12) + strongest regional/season
   roundups as candidates through the gates above, remove the hardcoded
   noindex for survivors, pull everything else (previews, recaps, failed
   roundups). Rationale: roundups aggregate real ratings; they're the only
   scalable indexable blog class; traffic is the binding constraint.
B. Pull all: blog = 2 hand-written articles only. Cleanest trust posture,
   forfeits the scalable indexable class.
Not offered: keep-but-delist (preserves liability, removes discoverability).

## Order
WS1 → WS2 → WS3(gravel) → WS4 async → WS5 on decision → WS3 port after one
clean live cycle.
