# Gravel Weekly issue store

Prepared review drafts live locally in ignored `drafts/YYYY-MM-DD.json`.
Approved issue
snapshots live in `issues/YYYY-MM-DD.json` and use
`gravel-weekly-issue/v1` from the race-intelligence control plane.

The intelligence service may prepare candidates and reaction packets, but it
does not write to `issues/`. An issue enters that directory only after Matti
approves The Take. Published files are historical snapshots: corrections are appended
to `corrections`; old copy is not silently rewritten.

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
