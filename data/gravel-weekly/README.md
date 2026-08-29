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

The approval packet must use `gravel-weekly-approval/v2`, name the exact
`reviewedDraftContentHash`, decide every reviewed story exactly once, and supply
the final headline, deck, Take, and edit summary for every approved story. A
stale approval cannot be replayed against a regenerated draft with the same
issue ID. The reviewed hash remains in the approved snapshot and must match its
decision receipt again at sealing and deploy time. The bridge preserves the
reviewed facts, scores, receipts, and race impacts verbatim. It emits both a
`status=approved` issue and a decision receipt under the ignored
`data/gravel-weekly/approved/` directory, which the deploy workflow refuses.

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

The public generator and sender both use the same fail-closed loader: only a
sealed `status=published` snapshot can cross the publication boundary.
`status=approved` remains private staging even if a file is placed in the
canonical issue directory by mistake.

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

Or generate the complete newest-to-oldest desk index and every yearly review in
one pass:

```bash
python3 scripts/render_gravel_weekly_history_review.py --all
```

The private index starts with 2026, then works backward. Within a year it places
READY decisions before HOLD research debt and orders each group by editorial
score. It changes no approval or publication state.

The desk puts the point, prior and changed judgments, model Take, uncertainty,
contemporary receipts, later evidence, gates, and review-only race implications
in one place. It also displays the pinned no-AI-slop verdict and named findings.
A story is marked ready only when all five editorial gates and the prose gate
pass and at least two contemporary publishers corroborate it. Historical drafts
that fail the prose gate cannot enter the repository validator at all.

Historical entries may also carry up to six `cultureArtifacts`. These are
date-bound, rights-bounded links to X, Instagram, YouTube, forums, blogs,
newsletters, or podcasts that help reconstruct the jokes, arguments,
personalities, and artifacts circulating during the active period. They are
part of the entry content hash and therefore part of Matti's exact approval.
The private desk shows why each artifact was selected; the public timeline
shows the artifact and original link but not the internal ranking rationale.
No third-party embed, copied social image, engagement total, or tracking script
is stored or rendered. Every artifact is permanently marked
`purpose=culture_sensor`, `canProveClaim=false`, and
`canEstablishConsensus=false`.

Turn a control-plane `historical-culture-sweep/v1` artifact into a topical,
date-correct private proposal:

```bash
python3 scripts/prepare_gravel_weekly_history_culture.py \
  data/gravel-weekly/history/2026-example.json \
  artifacts/historical-culture-2026.json
```

The bridge defaults to at most four artifacts, at most two from one source
type, and X attention scores of 70 or higher. Generic gravel virality does not
match a story; a distinctive configured topic must occur in the entry, and the
artifact date must fall inside its active period. Cross-source recurrence can
raise research priority but cannot establish consensus. By default the command
writes to the ignored `history-culture-proposals/` directory and leaves the
canonical draft unchanged. `--in-place` updates only a status=draft canonical
entry, changing its content hash and invalidating any stale approval; it still
cannot approve, seal, publish, deploy, or edit race data.

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

After the sealed snapshots and decisions merge to `main`, dispatch
`Gravel Weekly History Publish` with the reviewed year. This route is separate
from weekly issue publication: it requires no Issue #001, validates every
public snapshot against its immutable decision, generates entry-level hash
markers, opens an idempotent controlled race-impact review when needed, deploys
the timeline and homepage, purges SiteGround cache, and verifies every selected
hash plus the legacy Gravel TV redirect on the live site. Approved-but-unsealed
entries remain private and are excluded from the public loader.
