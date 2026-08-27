# Provider revenue ingestion

Mission Control can ingest the reconciled, PII-minimized TrainingPeaks evidence
without pretending that every source contains transaction- or customer-level
identifiers. Validation is the default. Database writes require both `--apply`
and the exact confirmation string.

## Source contract

The importer requires these five sanitized files in one directory:

| File | Canonical destination | Boundary |
| --- | --- | --- |
| `gravel-god-trainingpeaks-coaching-provider-ledger.csv` | `gg_payments` | TrainingPeaks did not export payment transaction IDs. Each row receives a labeled, duplicate-aware synthetic fingerprint. `amount` and `net_amount` are provider Amount Received. |
| `gravel-god-trainingpeaks-coaching-payout-ledger.csv` | `gg_provider_payouts` | Provider payout IDs remain SHA-256 values. Bank destinations are omitted. |
| `gravel-god-trainingpeaks-coaching-customer-lifecycle.csv` | `gg_provider_customer_snapshots` | Customer keys are snapshot-local, not durable identities across exports. Names and email addresses are not imported. |
| `gravel-god-trainingpeaks-coaching-lifecycle-monthly.csv` | `gg_provider_monthly_controls` | Dated activity counts are retained; the export does not support a churn-rate denominator. |
| `gravel-god-trainingpeaks-marketplace-royalty-reconciliation.csv` | `gg_provider_monthly_controls` | Marketplace evidence is aggregate royalty control data. It is not promoted to purchaser-level transactions. |

`gg_provider_import_batches` records the sanitized file hash, available upstream
hashes, observation time, row count, evidence grade, boundary, and control
totals. Reapplying identical inputs upserts the same transaction, payout,
snapshot, and monthly-control keys.

## Pinned baseline gate

The default 2026-08-27 gate fails closed unless the source bundle reconciles to:

- Coaching: 553 all-time payment rows; 213 operating-period rows; 209 succeeded;
  4 refunded; $47,765.60 gross; $45,694.95 provider Amount Received.
- Payouts: 351 all-time rows; 132 paid operating-period rows; $45,404.92 paid.
- Customers: 36 snapshot rows; 17 paid; 8 paused; 11 canceled.
- Lifecycle: 6 new starts; 5 inferred resumptions or migrations; 5 confirmed
  terminal churns. No churn percentage is asserted.
- Marketplace: 17 sale notices; $1,342.00 gross; $939.40 expected author share;
  $793.80 paid; $145.60 pending.

`--skip-2026-08-27-controls` exists only for fixtures and intentionally changed
source profiles. It must not be used to force a failing production snapshot.

## Runbook

Validate without credentials or writes:

```bash
python3 scripts/import_provider_revenue.py \
  --input-dir /absolute/path/to/sanitized/outputs \
  --observed-at 2026-08-27T18:00:00+00:00 \
  --receipt /absolute/path/to/provider-ingestion-dry-run.json
```

Apply migration `supabase/migrations/20260827000001_provider_revenue_truth.sql`
to the Mission Control Supabase project before enabling apply mode. Then run:

```bash
python3 scripts/import_provider_revenue.py \
  --input-dir /absolute/path/to/sanitized/outputs \
  --observed-at 2026-08-27T18:00:00+00:00 \
  --apply --confirm APPLY_PROVIDER_TRUTH \
  --receipt /absolute/path/to/provider-ingestion-apply.json
```

Apply mode lazy-loads Supabase credentials; dry-run does not. `SUPABASE_URL` and
`SUPABASE_SERVICE_KEY` must identify the same live project that owns Mission
Control. Ordinary PostgREST roles are denied access to the new financial and
lifecycle tables. The migration also replaces the old permissive
`gg_payments` policy with the service-role-only pattern.

## Live verification

Run these queries in that Supabase project after apply:

```sql
select count(*) as rows,
       sum(gross_amount) as gross,
       sum(net_amount) as net
from gg_payments
where provider = 'trainingpeaks'
  and provider_account = 'coaching'
  and provider_metadata->>'in_operating_system_period' = 'true';

select status, count(*) as rows
from gg_payments
where provider = 'trainingpeaks'
  and provider_account = 'coaching'
  and provider_metadata->>'in_operating_system_period' = 'true'
group by status order by status;

select count(*) as rows, sum(amount) as paid
from gg_provider_payouts
where provider = 'trainingpeaks'
  and provider_account = 'coaching'
  and status = 'paid'
  and provider_metadata->>'in_operating_system_period' = 'true';

select current_status, count(*) as customers
from gg_provider_customer_snapshots
where provider = 'trainingpeaks'
  and provider_account = 'coaching'
  and snapshot_sha256 = (
    select source_payload_sha256
    from gg_provider_import_batches
    where provider = 'trainingpeaks'
      and provider_account = 'coaching'
      and source_kind = 'customer_lifecycle_snapshot'
    order by observed_at desc limit 1
  )
group by current_status order by current_status;
```

Expected results are 213 / $47,765.60 / $45,694.95; 4 refunded and 209
succeeded; 132 / $45,404.92; and 11 canceled, 17 paid, 8 paused.

## Corrections and rollback

The import is additive and idempotent; it does not delete provider rows that
disappear from a later corrected export. Treat removal or re-keying as a
reviewed correction migration so the audit trail remains explicit. If an apply
is interrupted, rerun the exact command: batch and row conflict keys resume the
upserts safely.

Do not roll back by dropping `gg_payments`. For a pre-data schema rollback,
drop the four new tables in dependency order, remove the provider columns and
indexes added to `gg_payments`, and restore its prior policy. Once evidence has
been imported, preserve it and use a forward corrective migration instead.
