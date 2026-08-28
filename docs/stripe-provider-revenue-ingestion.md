# Standalone Stripe provider ingestion

Mission Control ingests the authenticated, privacy-safe standalone Stripe
receipt as a separate revenue authority. This path is operationally isolated
from Checkout and fulfillment: an export, validation, or database failure never
blocks or changes a customer order.

## Canonical mapping

| Receipt evidence | Destination | Financial meaning |
| --- | --- | --- |
| Successful charges | `gg_payments` | Settlement-currency gross, processing adjustment, and net. Purchaser presentment money remains labeled in metadata. |
| Succeeded refunds | `gg_payments` | Separate negative payment rows. The original charge may be outside the bounded receipt period. |
| Paid payouts | `gg_provider_payouts` | Positive provider payout amount. Bank destination and deposit matching remain out of scope. |
| All balance transactions | `gg_provider_balance_transactions` | Settlement ledger for charges, refunds, provider fees, and payouts. |
| Created-at monthly controls | `gg_provider_monthly_controls` | Monthly charge, refund, payout, Checkout, offer-allocation, and balance controls. |

Raw Stripe IDs, names, email addresses, payment methods, and bank destinations
are rejected. Stable `srk_…` keys are server-HMAC references, not reversible
provider identifiers. The importer validates every reported total from source
rows, checks paid Checkout-to-charge joins, verifies charge/refund/payout links
through the balance ledger, requires complete paid-invoice line items, and then
applies pinned 2026-08-27 controls.

## Migration plan

Apply
[`20260828000001_stripe_provider_balance_truth.sql`](../supabase/migrations/20260828000001_stripe_provider_balance_truth.sql)
before enabling apply mode.

- Lock profile: one new-table catalog lock and indexes built on that empty
  table. Existing `gg_payments` and provider rows are not rewritten.
- Runtime risk: no Checkout, fulfillment, email, or customer-facing path reads
  this table. Import failures are reporting failures only.
- Idempotency: the table is unique on provider, account, and HMAC record key;
  every canonical destination is upserted with its real unique key.
- Production-like proof: validate the full authenticated 1,685-row receipt,
  apply it, repeat the exact apply, and require identical row keys and totals on
  direct service-role readback.

## Runbook

Dry-run without database credentials or writes:

```bash
python3 scripts/import_stripe_provider_revenue.py \
  --receipt-file /absolute/path/to/stripe-reconciliation.json \
  --output-receipt /absolute/path/to/stripe-provider-dry-run.json
```

Apply after the migration:

```bash
python3 scripts/import_stripe_provider_revenue.py \
  --receipt-file /absolute/path/to/stripe-reconciliation.json \
  --apply --confirm APPLY_STRIPE_PROVIDER_TRUTH \
  --output-receipt /absolute/path/to/stripe-provider-apply.json
```

Apply mode uses `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`. The apply receipt is
not successful until direct readback proves the exact batch key sets, row
counts, and financial sums. A rerun is safe after an interrupted upsert.

## Pinned baseline

The production 2025-08-27 through 2026-08-27 receipt must validate to:

- 1,685 raw sanitized rows and 92 canonical payment rows: 91 successful
  charges plus one separate refund;
- $2,273.70 settlement charge activity, $194.16 processing fees, and $2,079.54
  charge net;
- $6.92 of separate fee net and a $1.30 refund, yielding 70 paid payouts and
  $2,071.32;
- a zero-cent settlement cash loop and zero current available/pending balance;
- six custom-plan charges for $1,023 and two consulting charges for $300;
- 83 merchant-label-ambiguous recurring charges: 82 USD charges for $945 and
  one EUR charge for €5;
- 876 synthetic expired/unpaid monitor Sessions excluded from abandonment,
  217 non-synthetic expired/unpaid Sessions, and eight paid Sessions.

`--skip-2026-08-27-controls` is for tests or a reviewed period rollover. It is
not an override for a failing production receipt.

## Deploy order

1. Ship the exporter source-link correction and create a fresh receipt.
2. Merge the Mission Control migration, importer, tests, and ingestion workflow.
3. Apply the migration and verify the new table is service-role-only.
4. Manually ingest the fresh receipt twice and prove idempotent live readback.
5. Only then enable the exporter repository dispatch for recurring ingestion.

## Rollback

Disable `.github/workflows/stripe-provider-ingestion.yml` first. The importer
does not delete rows that disappear from a later rolling receipt; reviewed
corrections remain forward migrations.

For a code-only rollback, revert the importer/workflow commit. For an exact data
rollback before downstream adoption, delete only rows whose provider is
`stripe` and whose provider account equals the imported HMAC account key, then
delete their matching import batches. For a schema rollback after those rows
are gone:

```sql
drop table if exists gg_provider_balance_transactions;
```

Never drop `gg_payments`, `gg_provider_payouts`, or
`gg_provider_monthly_controls`; they also contain TrainingPeaks evidence.
