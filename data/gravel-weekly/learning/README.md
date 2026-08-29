# Gravel Weekly learning sources

This directory stores human-authored, review-only outcomes that cannot be
inferred from publication or engagement:

- `race_impact_decision` binds one exact impact from a published issue to the
  owning-repository result. An accepted decision requires a merged
  implementation URL and the exact regression-test selector. Rejected and
  superseded decisions preserve the reason and cannot pretend work shipped.
- `missed_story` records a story a human confirms was materially important and
  discovered late. Publication and discovery timestamps remain distinct; a
  model cannot declare its own omission important.

Every JSON file uses `gravel-weekly-learning-source/v1`, is validated against
its linked immutable issue when one exists, and is mirrored only by the manual
`Gravel Weekly Learning Receipt` workflow. The workflow binds the source file
to its Git commit and SHA-256 hash, then submits it to the protected control
plane. It cannot publish copy, change a race, alter a threshold, or spend model
budget.

Validate locally:

```bash
python3 scripts/validate_gravel_weekly_learning.py \
  data/gravel-weekly/learning/example.json
```

Preview the exact control-plane payload without sending it:

```bash
python3 scripts/record_gravel_weekly_learning.py \
  --learning-source data/gravel-weekly/learning/example.json \
  --dry-run
```
