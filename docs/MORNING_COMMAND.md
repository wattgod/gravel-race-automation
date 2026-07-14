# Morning Command

`scripts/daily_intel.py` is the single daily composer and email sender. The
scheduled `.github/workflows/daily-intel.yml` runs the detectors, then sends one
ranked report. `daily-monitoring.yml` is manual/detector-only, `immune.yml` keeps
its push gate but has no daily schedule, and `scripts/send_digest.py` only
renders detector output. No other daily path sends mail.

## Pipeline

1. GSC and CWV write their existing snapshots under `data/gsc-snapshots/` and
   `data/cwv-snapshots/`. Morning Command reads them; it does not call those APIs
   again. A snapshot older than 48 hours is shown as unavailable and cannot
   create an action item.
2. `scripts/immune_check.py --json` writes `immune/report.json` using the
   established `Finding` schema.
3. `scripts/immune_ci.py` reads the last runs for the four ecosystem repos with
   `gh run list`, reads failed logs only for a newly-red or chronic workflow,
   and reads Endure Labs cron rows from one of:
   `CRON_HEALTH_SNAPSHOT`, `ENDURELABS_CRON_HEALTH_URL`, or Supabase REST using
   `ENDURELABS_SUPABASE_URL` and `ENDURELABS_SUPABASE_SERVICE_KEY`. It writes
   `reports/health/ci-cron.json` in the same finding schema.
4. The composer adds commerce/order-killer findings, ranks RED before YELLOW
   and critical before lower severities, folds overnight `type:"fix"` ledger
   entries into AUTO-HEALED, and suppresses green/known backlog to a count.

Preview is offline-safe and never writes or sends:

```bash
python3 scripts/daily_intel.py --preview
python3 scripts/daily_intel.py --json
```

Both commands reuse the latest fresh commerce snapshot. Missing credentials,
network, detector reports, or health snapshots render as `unavailable`.

## CI and cron lane policy

| Problem | Lane | Action |
|---|---|---|
| Invalid workflow syntax (`strategy` on a step, `::set-output`, bad `fromJson`) | GREEN | Apply the known pattern in the home repo, then pass the verify gate. |
| Known Node runtime drift | GREEN | Bump to the known-good runtime, then pass the verify gate. |
| Scheduled workflow fails 3 consecutive times because a script or secret is missing/empty | GREEN → surfaced YELLOW | Disable only `schedule`, retain `workflow_dispatch`, verify, log, and ask the owner to repair/re-enable it. |
| Known-noise run | GREEN/suppressed | Count only. |
| Failing tests, real monitor findings, ambiguous CI, repeated/zero-work cron | YELLOW | Human-reviewed proposal/PR. |
| Money path, secret/security issue, production outage | RED | Flag only; never auto-heal. |

GREEN repair is home-repo-only. A known GREEN pattern in a sibling repo is
demoted to YELLOW and proposed as a PR. The optional repair entry point is:

```bash
python3 scripts/immune_ci.py --apply-safe
```

It keeps a workflow edit only if its static failure disappears and neither the
ecosystem scan nor `immune_check.py` gains a new RED fingerprint. Otherwise it
restores the original file. Every kept repair appends a `type:"fix"` record to
`immune/ledger.jsonl` with a regression check. It never deploys.

The hard boundary is encoded ahead of GREEN rules in `immune_check.RULES`:
Stripe/webhook, checkout, order delivery/fulfillment, `/questionnaire/`,
`/coaching/`, security, and production outages can never receive `auto_fix`.
