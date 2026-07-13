# SITE-SYNC — db→site propagation + race-page plan ladders (Matti, 2026-07-14)

**What changes for a visitor:** every race page carries a "Train for this race" block
rendering that race's real TP plan ladder (published plans → TP marketplace buy links;
private plans → visible ladder with email-gate "notify me" capture). Race-page facts match
the immune-audited db (fixes reach the storefront automatically at each wave close). The
10 fabricated-race pages are REMOVED with 301 redirects to their state/region best-of pages.

Decisions locked via AskUserQuestion 2026-07-14: remove+redirect fakes; email-gate private
plans; AUTO-DEPLOY per wave behind preflight gates + cache purge (deploy-safely skill is
mandatory reading before every deploy).

## S1 — marketplace_url backfill (browser)
For all PUBLISHED plans (db status=published, ~392): GET each plan via tpapi (or the plans
list) and capture the TP marketplace/store URL field; write to registry marketplace_url +
db records. Verify a sample of URLs 200 and land on the correct store page.

## S2 — race-page plan block (generator, local)
In the gravel-race-automation page generator: new block sourced from
../gravel-god-training-plans/db/plans.json by race_slug —
- ladder table: tier · length · price; published → marketplace_url CTA; private →
  email-gate (reuse training-plans-form.js capture w/ race_slug + tier payload tags);
- brand tokens only (no hardcoded hex); Normie-safe microcopy (no TSS/FTP);
- renders nothing gracefully for races with no plans;
- unit-tested (published-link case, email-gate case, no-plans case, token audit passes).

## S3 — fabricated-page removal + 301s
Slugs (F3-F12): black-forest-gravel, ozark-gravel, pirate-cycling-league-gravel,
grasslands-100, balkan-gravel, greek-gravel, natchez-trace-gran-fondo, walburg-dirty-30,
flint-hills-death-ride, kal-tour-dirty-100 → 301 to their state/region best-of page (or
/race/calendar/ where none exists). Also purge them from sitemaps + internal links
(check_links green). Keep race-data files (annotated) for the audit trail; site pages die.

## S4 — auto-deploy per wave (loop wiring)
At each wave close: regenerate race pages whose race-data changed since last deploy +
plan blocks for landed races → preflight gates (pytest, audit_colors, validate_citations,
preflight_quality) → push_wordpress.py → SiteGround cache purge → check_links + spot-curl
of changed pages. Ledger each deploy in ROLL_HANDOFF. Failures stop the deploy loudly
(no silent partial deploys — CI-veracity lesson).

## Deviations log
- (running)
