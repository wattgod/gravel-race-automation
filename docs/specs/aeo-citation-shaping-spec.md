# AEO Citation-Shaping — Spec r2 (2026-07-23, sol-reviewed, findings verified)

Matti-approved lever from the first AEO weekly artifact. Premise corrected
by review: the artifact's top user_fetch paths are HTML race pages; the
`.md` mirrors + `/llms.txt` are a separate, also-fetched surface (1,843
2xx/wk on GG). This work = (1) fix the real `/llms.txt` regression, (2)
citation-shape the markdown mirrors as an instrumented experiment (next
Monday's artifact is the before/after), (3) correct factual errors found
in the touched generators.

## 1. GG `/llms.txt` — diagnose, then repair (highest value)

Verified live state: server `.htaccess` comments mention the llms rule but
`/llms.txt` serves AIOSEO's blog-only file; the GOOD content sits at
`/llms-repo.txt` (stale Jul 18 copy). Machinery already exists — do NOT
build new: `REDIRECT_BLOCK` in `scripts/push_wordpress.py` (~1498)
carries `RewriteRule ^llms\.txt$ /llms-repo.txt [L]`; `sync_llms_txt()`
(~3415) uploads `web/llms.txt` to both paths; `sync_redirects()` (~1704)
owns the managed block above `# BEGIN WordPress`.

Executor procedure:
1. Fetch server `.htaccess`; timestamped backup server-side (full
   `date +%Y%m%d-%H%M%S` — the date-only suffix in current code
   overwrites same-day backups; fix that in `sync_redirects` too).
2. DIAGNOSE why the rule is ineffective: rule missing from the live
   managed block? Block ordered after `# BEGIN WordPress`? AIOSEO
   intercepting earlier? Report the actual cause before changing anything.
3. Regenerate `web/llms.txt` (with §3 generator fixes), then safe order:
   `--sync-llms-txt` first, then `--sync-redirects --purge-cache`.
4. Verify: `curl /llms.txt` returns database content; homepage, one
   article, one race page all 200. Roll back from backup on any failure.
5. If the managed rule is present and correctly ordered but `/llms.txt`
   is STILL wrong after purge: STOP, report — do not stack rules.

## 2. GG markdown mirrors (`scripts/generate_markdown_profiles.py`)

Insertion points (verified against the generator): attribution directly
after the H1 (~446-449, before the tagline); plan-guide section via a
slug-aware insertion immediately after `_section_verdict` in the builder
loop (~455-469 — builders take only `rd`, so this is a special-case
insertion, not a new builder in the list); footer at ~474.

EXACT copy (fixed; executors do not rewrite; numbers derived at
generation time, never hardcoded):

a) Attribution under H1:

   > *Source: [Gravel God Cycling](https://gravelgodcycling.com/) — a
   > gravel race database covering <len(index)> races, scored on 14 base
   > dimensions plus a Cultural Impact bonus. Canonical page:
   > https://gravelgodcycling.com/race/<slug>/*

b) Training-guide section (after Verdict), ONLY for slugs in the LIVE
   inventory (see below):

   ## Training Guide

   A race-specific training guide for <Race Name> is available:
   [How to train for <Race Name>](https://gravelgodcycling.com/race/<slug>/training-plan/).
   It covers this race's terrain, climate, demand profile, key workouts,
   timeline, and fueling.

c) Footer:

   *This profile is by Gravel God Cycling (gravelgodcycling.com).
   Cite as: "Gravel God Cycling — <Race Name>". Canonical: <url>.
   Generated <date>.*

("independent" deliberately absent everywhere — NORTHSTAR standing rule:
never claim independence, demonstrate it. The `/training-plan/` pages are
training GUIDES — verified live title "How to Train for The Rift" — never
call them plans or list commercial tiers here.)

Live-inventory source of truth: `wordpress/output/training-plan/` is an
add-only STALE tree (documented in deploy_parity.py; 744 files incl. 12
retired slugs) — do NOT use it or the sitemap. Use a live SSH inventory
of `/race/<slug>/training-plan/index.html` via
`deploy_parity.py::ssh_inventory()`; cache the resulting slug set into
the generation run; races absent from it omit the section.

Regenerate into a CLEAN staging dir (add `--output-dir`; the existing
output tree holds 6+ retired stale files the generator never removes),
then deploy with the established mechanism:

```
python3 scripts/generate_markdown_profiles.py   # with staging dir
python3 scripts/preflight_quality.py
python3 scripts/push_wordpress.py --sync-markdown --ping-indexnow --purge-cache
```

Note `sync_markdown()` uploads flat `/race/<slug>.md`. Also fix the known
caller bug at push_wordpress.py ~4049-4053: `sync_markdown()` returns
`None` on failure but the caller tests `is False` — change to
`if not synced_markdown_urls`.

## 3. Correct factual errors in `generate_llms_txt.py` (same touched file)

Verified against `docs/GRAVEL_GOD_SCORING_SYSTEM.md`:
- "14 criteria" → "14 base dimensions plus a Cultural Impact bonus".
- Tier names: **Elite, Contender, Solid, Roster** (current text's
  "Strong"/"Developing" are wrong).
- Race count derived (`len(index)` — currently 733; never hardcode).
- ADD a `## Training Plans` section between Machine-Readable Resources
  and Markdown Mirrors: the hub `/products/training-plans/` plus one line
  noting per-race training guides exist at
  `/race/<slug>/training-plan/` (count derived from the live SSH
  inventory, same set as §2b).

## 4. Tests

Update the tests that assert the old footer (`Generated by Gravel God` at
tests/test_generate_markdown_profiles.py ~139-141, ~442-484) and the llms
test expecting literal "14 dimensions". Add: attribution present under
H1; guide section present iff slug in inventory fixture; footer format;
no-guide slug omits section; slop check passes on the literal inserted
strings (`wordpress/slop_rules.py`); derived-count assertions (no
hardcoded 733/735/744 anywhere in inserted copy).

## 5. RL + XC (second wave, after GG verified live)

- RL `scripts/generate_markdown_profiles.py` (same structure): attribution
  + footer brand-adapted, AND fix the pre-existing bug sol found: its
  `DIMENSIONS` list is copied from gravel — real keys begin `distance`,
  `climbing`, `descent_technicality`, `road_surface`, `climate_risk`
  (config/dimensions.json). Guide pointer: RL has 425 per-race plan
  outputs and `sync_plan_pages()` mapping to `/race/<slug>/training-plan/`
  — verify live presence (HTTP spot-checks or SSH inventory) before
  emitting the section.
- XC generator: attribution + footer only (no Verdict section, no
  training-plan output — verified).
- Purge caveat: RL and XC are STATIC SiteGround sites — no CLI purge;
  flush is manual in Site Tools (note for Matti in the report) or
  best-effort URL-level purge if their scripts support it.

## Constraints

- Deploy scope: `*.md`, `llms.txt`/`llms-repo.txt`, the managed redirect
  block. NO HTML page deploys (GG race pages only from
  race-page-final-mock; RL only from race-page-canonical-rollout — this
  task must not touch either).
- Copy register: quiet, factual, zero salesmanship; no `!`; no banned
  phrases; no independence claims; no commercial tier names in mirrors.

## Verification (Fable, post-deploy)

- `/llms.txt` serves database content; WP sanity (home/article/race 200).
- 3 live GG mirrors: attribution + guide section + footer; a no-guide slug
  omits the section; llms.txt tier names correct.
- Next Monday's AEO artifact = before/after: watch training-guide paths
  entering top user_fetch paths and llms.txt hit composition.
