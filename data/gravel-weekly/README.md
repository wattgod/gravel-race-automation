# Gravel Weekly issue store

Prepared review drafts live locally in ignored `drafts/YYYY-MM-DD.json`.
Approved issue snapshots live in `issues/YYYY-MM-DD.json` and use
`gravel-weekly-issue/v1` from the race-intelligence control plane.
Each snapshot has a paired `decisions/YYYY-MM-DD.json` receipt containing every
explicit approve/reject verdict, the exact model Take that Matti reviewed, the
approved Take, and the human edit summary.

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

The bridge independently recomputes the pinned `petergyang/no-ai-slop` audit
over the exact headline, deck, `whatHappened`, and Take. A missing, failed, or
stale content-hashed prose verdict excludes the packet even when every story
gate passes. Draft, approved, and published issue files are all re-audited by
the publication validator; human approval remains a separate requirement.

Apply Matti's explicit approval packet without making anything deployable:

```bash
python3 scripts/approve_gravel_weekly_issue.py \
  data/gravel-weekly/drafts/2026-08-28.json APPROVAL.json
```

The approval packet must use `gravel-weekly-approval/v1`, decide every reviewed
story exactly once, and supply the final headline, deck, Take, and edit summary
for every approved story. The bridge preserves the reviewed facts, scores,
receipts, and race impacts verbatim. It emits both a `status=approved` issue and
a decision receipt under the ignored `data/gravel-weekly/approved/` directory,
which the deploy workflow refuses.

After a separate explicit publication instruction, seal the approved file:

```bash
python3 scripts/seal_gravel_weekly_issue.py \
  data/gravel-weekly/approved/2026-08-28.json \
  --published-at 2026-08-28T16:05:00Z
```

Sealing changes only publication state and timestamps, refuses to overwrite an
existing historical snapshot by default, and writes the deployable immutable
issue under `data/gravel-weekly/issues/` plus its canonical receipt under
`data/gravel-weekly/decisions/`. The publish workflow validates the pair and
mirrors each idempotent decision into the control plane before deployment, so
gate outcomes and approved-copy edits cannot silently fall out of the learning
history. Deployment remains a separate manual workflow dispatch.

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

## Historical narrative review

Historical Current Thing entries are narrative reconstructions, not fabricated
old weekly issues. Drafts live in `history/`, but the public loader excludes
them. Build a private, read-only desk for one year:

```bash
python3 scripts/render_gravel_weekly_history_review.py --year 2026
```

The desk puts the point, prior and changed judgments, model Take, uncertainty,
contemporary receipts, later evidence, gates, and review-only race implications
in one place. It also displays the pinned no-AI-slop verdict and named findings.
A story is marked ready only when all five editorial gates and the prose gate
pass and at least two contemporary publishers corroborate it. Historical drafts
that fail the prose gate cannot enter the repository validator at all.

Apply one explicit decision using `gravel-weekly-history-approval/v1`:

```bash
python3 scripts/approve_gravel_weekly_history.py \
  data/gravel-weekly/history/2026-example.json APPROVAL.json
```

The packet must identify the exact reviewed `contentHash`. Approval may change
only the headline and Take, records the edit summary, and stages the result and
decision under ignored `history-staged/`. Rejection records a reason but creates
no approved entry. A stale hash, held gate, single-publisher premise, factual
edit, or copy that still claims to be a model draft fails closed.

When the private desk offers a one-line bulk approval, apply that exact phrase
to every READY entry—and no HOLD entry—with:

```bash
python3 scripts/approve_ready_gravel_weekly_history.py \
  --year 2026 \
  --approval-phrase "approve all READY 2026 entries as written" \
  --approver "Matti Rowe" \
  --decided-at 2026-08-28T16:00:00Z
```

The command preflights and stages hash-bound decisions, removes only the internal
model-draft warning that the desk does not show as part of the Take, and refuses
to overwrite prior staged decisions. It cannot seal, publish, deploy, or alter
race data.

Only after a separate explicit publication instruction may the staged entry be
sealed:

```bash
python3 scripts/seal_gravel_weekly_history.py \
  data/gravel-weekly/history-staged/history-example.approved.json \
  --published-at 2026-08-28T16:05:00Z
```

Sealing verifies the decision against the unchanged canonical draft, replaces
that draft with the published immutable snapshot, and writes its durable
decision under `history-decisions/`. It does not deploy the site, and race
impacts remain editorial-review proposals with `autoFixAllowed: false`.
