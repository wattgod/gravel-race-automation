# Codex deduplication report

Date: 2026-07-13
Branch supplied by user: `immune-fixes-data`

## Scope and constraints

- No Git commands were run.
- No network requests were made.
- Nothing was committed, pushed, or deployed.

## Duplicate removal

Deleted all 11 requested non-canonical profiles:

- `big-horn-gravel`
- `tour-de-tucson`
- `dreilaendergiro`
- `gran-fondo-felice-gimondi`
- `gran-fondo-guadeloupe`
- `gran-fondo-novi-sad`
- `gran-fondo-via-del-sale`
- `gran-fondo-vosges`
- `granfondo-strade-bianche`
- `istria-gran-fondo`
- `oetztaler-radmarathon`

None of the corresponding `wordpress/output/{slug}/` or `output/{slug}/`
directories existed before deletion. They were also confirmed absent after
regeneration.

All 11 requested canonical keep profiles were confirmed present.

## Generator results

1. `python3 scripts/generate_race_index.py`
   - **Skipped: requested script does not exist.**
   - The available similarly named file is `scripts/generate_index.py`, but it
     was not substituted because the task limited execution to the listed
     generators that exist.
2. `python3 wordpress/generate_neo_brutalist.py --all`
   - **Success (exit 0).**
   - Generated `746/746` race pages.
   - The generator reported that it loaded the stale race index at `757`
     entries.
   - It emitted non-fatal existing warnings for unparseable/TBD date strings
     and missing `course_description` values on a few profiles; no generator
     error occurred.
3. `python3 scripts/generate_sitemap.py`
   - **Success (exit 0).**
   - Generated `web/sitemap.xml` with `1,653` URLs.
4. `python3 wordpress/generate_homepage.py`
   - **Skipped to preserve offline execution.** Inspection confirmed the
     generator calls `urllib.request.urlopen()` against the Substack RSS feed.

Generator errors: **0 among commands executed**. Two commands were skipped for
the reasons above.

## Verification counts

| Check | Expected | Actual | Result |
|---|---:|---:|---|
| `ls race-data/*.json \| grep -v _schema \| wc -l` | 746 | 746 | PASS |
| `web/race-index.json` race count | 746 | 757 | FAIL |
| Removed-slug entries in `web/race-index.json` | 0 | 11 | FAIL |
| Fresh top-level race-page occurrences of `/race/3rides-gran-fondo/tires/` | 0 | 0 | PASS |

Each removed slug still has exactly one entry in the stale
`web/race-index.json` (11 total). This is directly attributable to the missing
requested index-generator script.

The dead-tire-link spot-check above was run against the freshly regenerated
top-level race-page files (`wordpress/output/*.html`). A recursive search of
all ancillary artifacts below `wordpress/output/` finds 7 older references:
one prep-kit page, five references in the existing tire-guide page, and one in
the generated sitemap. Those are outside the freshly generated top-level race
pages, but are recorded here for completeness.

## Final state

- Source race profiles: **746**.
- Fresh race pages generated: **746/746**.
- Race index: **stale at 757** because the requested generator path is absent.
- Requested loser profiles/output directories: **absent**.
- Canonical keep profiles: **all present**.
- Files left uncommitted for review.
