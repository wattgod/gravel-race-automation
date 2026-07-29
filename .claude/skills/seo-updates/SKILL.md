---
name: seo-updates
description: Draft the week's 5 SEO content updates from the latest data/seo/seo-weekly-*.json artifact. Load when the operator runs /seo-updates or asks to act on the Morning Intel SEO section. Drafts diffs only — Matti gates every deploy.
---

# SEO Updates (weekly drafting session)

Turns the deterministic weekly artifact into 5 concrete, gated content
updates. The artifact found the leverage; this session supplies the judgment
and the words. Spec: `docs/specs/seo-weekly-spec.md`.

## Hard rules

- **Never publish without Matti's explicit yes.** Output of this session is
  diffs + expected impact, then a gate. No exceptions.
- **Never hand-edit emitted HTML.** Route every edit through the source of
  truth (table below), regenerate, preflight, deploy.
- **GSC finds opportunities; it does not supply facts.** Any factual or
  freshness claim you add (dates, distances, entry status) must be verified
  against the official race source first. Unverifiable → reframe the edit so
  it makes no new factual claim.
- Voice: brand tokens, `wordpress/slop_rules.py` anti-slop, race-page spine
  contract. Title/meta rewrites sell the page honestly — specificity, not
  salesmanship.

## Procedure

1. **Load the artifact**: newest `data/seo/seo-weekly-*.json`. If
   `generated_at_utc` is >8 days old, stop and tell the operator to run the
   seo-weekly workflow (`gh workflow run seo-weekly.yml`) instead of drafting
   from stale data.
2. **Per candidate** (`top_candidates`, usually 5):
   - curl the live page (cache-busted) and read what's actually there.
   - Open the source per the routing table; read `supporting_queries` — the
     edit should serve the whole query cluster, not just the headline query.
   - Diagnose by `bucket`:
     - `striking_distance` → strengthen relevance: heading/intro coverage of
       the query, internal links from related pages, content depth.
     - `ctr_underperformers` → rewrite `seo.title`/`seo.description` (or WP
       meta) to match the query intent; the ranking is fine, the pitch isn't.
     - `decliners` → refresh: stale dates/facts (verify first), thin sections,
       lost freshness signals.
     - `content_gaps` → propose a new page or internal-linking fix;
       `recommended_target_path` is a suggestion, not a decision.
3. **Draft all 5 as diffs** in the sources of truth. Present together:
   change, reason (from artifact), expected impact (the candidate's `score` =
   estimated 28-day click upside), and any facts you verified.
4. **Gate.** On Matti's yes, per approved item: regenerate the page,
   `python3 scripts/preflight_quality.py`, deploy per the `deploy-safely`
   skill, purge SiteGround cache.
5. **Log every decision** (applied AND skipped) — append one line per
   candidate to `data/seo/updates-log.jsonl`:

   ```json
   {"date": "YYYY-MM-DD", "page": "/race/x/", "query": "...", "bucket": "...",
    "action": "rewrite_title_meta", "artifact": "seo-weekly-YYYY-MM-DD.json",
    "baseline": {"clicks": 0, "impressions": 0, "ctr": 0.021, "position": 6.2},
    "change_summary": "...", "status": "applied"}
   ```

   The collector reads this for the 21-day cooldown and for before/after
   measurement — an unlogged edit breaks both.

## Source routing table

| target_path | source of truth | apply via |
|---|---|---|
| `/race/<slug>/` | `race-data/<slug>.json` — `seo.title`, `seo.description`, profile fields | regenerate race page, preflight, deploy per deploy-safely |
| `/articles/<slug>/` | article source (repo generator) | regenerate → SCP to `/articles/<slug>/` — NOT `--sync-blog` |
| WP-native / Elementor (e.g. `/questionnaire/`, hubs) | `scripts/generate_meta_descriptions.py` for meta; Elementor widget for body | meta via script; Elementor body edits are manual/JS-API — flag, don't guess |
| no source (most `content_gaps`) | none | propose new content or internal links; never silently invent a page |

## Measurement

When drafting, check `updates-log.jsonl` for entries ~4+ weeks old and
compare their `baseline` against the current artifact's buckets for the same
page/query — report movement (or its absence) to Matti before proposing new
work. Changes that didn't move anything are the most important finding.
