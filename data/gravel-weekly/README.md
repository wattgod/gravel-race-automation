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

Validate files and content hashes:

```bash
python3 scripts/validate_gravel_weekly.py
```

Generate the latest page and dated archive:

```bash
python3 wordpress/generate_gravel_weekly.py
```

Render a local draft for review without making it public:

```bash
python3 wordpress/generate_gravel_weekly.py \
  --preview-draft data/gravel-weekly/drafts/2026-08-28.json
```
