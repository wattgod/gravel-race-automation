# Gravel Weekly issue store

Prepared review drafts live locally in ignored `drafts/YYYY-MM-DD.json`.
Approved issue
snapshots live in `issues/YYYY-MM-DD.json` and use
`gravel-weekly-issue/v1` from the race-intelligence control plane.

The intelligence service may prepare candidates and reaction packets, but it
does not write to `issues/`. An issue enters that directory only after Matti
approves The Take. Published files are historical snapshots: corrections are appended
to `corrections`; old copy is not silently rewritten.

Later issues can revisit an earlier story through `retrospectives`. Each entry
must name the prior issue and story, classify the take as `aged_well`,
`aged_poorly`, or `still_developing`, explain what changed, include fresh
receipts, and carry human-approved assessment provenance before publication.
The loader verifies that every retrospective points backward to a real archived
story. The Past Issues section also preserves each issue's Current Thing, deck,
and Take excerpt so the archive reads as a timeline instead of a link dump.

Build a fail-closed draft from a control-plane review artifact:

```bash
python3 scripts/prepare_gravel_weekly_issue.py REVIEW.json \
  --publication-date 2026-08-28 --issue-number 1
```

Apply Matti's explicit approval packet without making anything deployable:

```bash
python3 scripts/approve_gravel_weekly_issue.py \
  data/gravel-weekly/drafts/2026-08-28.json APPROVAL.json
```

The approval packet must use `gravel-weekly-approval/v1`, decide every reviewed
story exactly once, and supply the final headline, deck, Take, and edit summary
for every approved story. The bridge preserves the reviewed facts, scores,
receipts, and race impacts verbatim. It emits `status=approved` under the
ignored `data/gravel-weekly/approved/` directory, which the deploy workflow
refuses.

After a separate explicit publication instruction, seal the approved file:

```bash
python3 scripts/seal_gravel_weekly_issue.py \
  data/gravel-weekly/approved/2026-08-28.json \
  --published-at 2026-08-28T16:05:00Z
```

Sealing changes only publication state and timestamps, refuses to overwrite an
existing historical snapshot by default, and writes the deployable immutable
file under `data/gravel-weekly/issues/`. Deployment remains a separate manual
workflow dispatch.

Validate files and content hashes:

```bash
python3 scripts/validate_gravel_weekly.py
```

Generate the latest page and dated archive:

```bash
python3 wordpress/generate_gravel_weekly.py
```

Render the controlled race-profile review for a published issue:

```bash
python3 scripts/render_gravel_weekly_race_impact_review.py \
  data/gravel-weekly/issues/2026-08-28.json \
  --output artifacts/gravel-weekly-race-impact-review.md
```

The publication validator requires the issue-level `raceImpacts` collection to
exactly preserve the deduplicated union of story impacts, and every impact claim
must resolve to a receipt on that story. The publish workflow uploads the
immutable artifact and opens one idempotent GitHub review issue when actionable
impacts exist. It never edits a race profile.

Render a local draft for review without making it public:

```bash
python3 wordpress/generate_gravel_weekly.py \
  --preview-draft data/gravel-weekly/drafts/2026-08-28.json
```
