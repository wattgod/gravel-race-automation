-- Canonical settlement ledger for privacy-safe standalone Stripe imports.
--
-- This migration is additive. It creates one empty table and indexes that
-- table before any importer is enabled; no existing provider row is rewritten.

CREATE TABLE gg_provider_balance_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    provider_account TEXT NOT NULL DEFAULT '',
    provider_record_key TEXT NOT NULL,
    provider_record_key_kind TEXT NOT NULL,
    import_batch_id UUID NOT NULL REFERENCES gg_provider_import_batches(id),
    source_record_key TEXT,
    transaction_type TEXT NOT NULL,
    reporting_category TEXT NOT NULL,
    status TEXT NOT NULL,
    amount DECIMAL NOT NULL,
    fee_amount DECIMAL NOT NULL,
    net_amount DECIMAL NOT NULL,
    currency TEXT NOT NULL,
    provider_created_at TIMESTAMPTZ NOT NULL,
    available_at TIMESTAMPTZ,
    source_payload_sha256 TEXT NOT NULL
        CHECK (length(source_payload_sha256) = 64),
    source_record_sha256 TEXT NOT NULL
        CHECK (length(source_record_sha256) = 64),
    evidence_grade TEXT NOT NULL,
    source_boundary TEXT NOT NULL DEFAULT '',
    provider_metadata JSONB NOT NULL DEFAULT '{}',
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(provider, provider_account, provider_record_key)
);

COMMENT ON TABLE gg_provider_balance_transactions IS
    'Provider settlement activity. Amount, fee_amount, and net_amount use the settlement currency, not necessarily the purchaser presentment currency.';
COMMENT ON COLUMN gg_provider_balance_transactions.source_record_key IS
    'PII-safe HMAC reference to the source charge, refund, payout, or other provider object when supplied.';

CREATE INDEX idx_provider_balance_transactions_created
    ON gg_provider_balance_transactions(
        provider, provider_account, provider_created_at, reporting_category
    );
CREATE INDEX idx_provider_balance_transactions_import_batch
    ON gg_provider_balance_transactions(import_batch_id);

ALTER TABLE gg_provider_balance_transactions ENABLE ROW LEVEL SECURITY;

-- The service role bypasses RLS. Explicitly deny ordinary PostgREST roles.
CREATE POLICY "Service role only" ON gg_provider_balance_transactions
    FOR ALL USING (false) WITH CHECK (false);
