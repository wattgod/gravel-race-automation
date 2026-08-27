-- Decision-grade provider revenue imports for Mission Control.
--
-- This migration extends the existing gg_payments table compatibly. Existing
-- manual rows remain valid. Provider imports gain idempotency, source evidence,
-- status, gross/net separation, and an explicit boundary when the upstream
-- export does not contain a transaction identifier.

CREATE TABLE gg_provider_import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    provider_account TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL,
    source_payload_sha256 TEXT NOT NULL CHECK (length(source_payload_sha256) = 64),
    upstream_source_sha256 JSONB NOT NULL DEFAULT '[]',
    observed_at TIMESTAMPTZ NOT NULL,
    row_count INTEGER NOT NULL CHECK (row_count >= 0),
    control_totals JSONB NOT NULL DEFAULT '{}',
    evidence_grade TEXT NOT NULL,
    source_boundary TEXT NOT NULL DEFAULT '',
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(provider, provider_account, source_kind, source_payload_sha256)
);

ALTER TABLE gg_payments
    ADD COLUMN provider TEXT NOT NULL DEFAULT 'manual',
    ADD COLUMN provider_account TEXT NOT NULL DEFAULT '',
    ADD COLUMN provider_record_key TEXT,
    ADD COLUMN provider_record_key_kind TEXT,
    ADD COLUMN import_batch_id UUID REFERENCES gg_provider_import_batches(id),
    ADD COLUMN customer_key TEXT,
    ADD COLUMN product_name TEXT,
    ADD COLUMN status TEXT NOT NULL DEFAULT 'succeeded',
    ADD COLUMN currency TEXT NOT NULL DEFAULT 'usd',
    ADD COLUMN gross_amount DECIMAL,
    ADD COLUMN provider_adjustment_amount DECIMAL,
    ADD COLUMN net_amount DECIMAL,
    ADD COLUMN source_payload_sha256 TEXT CHECK (source_payload_sha256 IS NULL OR length(source_payload_sha256) = 64),
    ADD COLUMN source_record_sha256 TEXT CHECK (source_record_sha256 IS NULL OR length(source_record_sha256) = 64),
    ADD COLUMN evidence_grade TEXT,
    ADD COLUMN source_boundary TEXT NOT NULL DEFAULT '',
    ADD COLUMN provider_metadata JSONB NOT NULL DEFAULT '{}',
    ADD COLUMN observed_at TIMESTAMPTZ,
    ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ADD CONSTRAINT gg_payments_provider_record_unique
        UNIQUE(provider, provider_account, provider_record_key);

COMMENT ON COLUMN gg_payments.provider_record_key IS
    'Provider ID when exported; otherwise a labeled synthetic fingerprint over normalized source facts plus duplicate ordinal.';
COMMENT ON COLUMN gg_payments.provider_adjustment_amount IS
    'Gross minus provider net. May combine fees and refund effects when the source export does not separate them.';
COMMENT ON COLUMN gg_payments.customer_key IS
    'PII-minimized source key. It is not a canonical customer identity unless the provider supplies a stable ID.';

CREATE INDEX idx_payments_provider_status_month
    ON gg_payments(provider, provider_account, status, paid_at);
CREATE INDEX idx_payments_import_batch ON gg_payments(import_batch_id);

CREATE TABLE gg_provider_payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    provider_account TEXT NOT NULL DEFAULT '',
    provider_record_key TEXT NOT NULL,
    provider_record_key_kind TEXT NOT NULL,
    import_batch_id UUID NOT NULL REFERENCES gg_provider_import_batches(id),
    status TEXT NOT NULL,
    amount DECIMAL NOT NULL,
    currency TEXT NOT NULL,
    provider_created_at TIMESTAMPTZ,
    arrival_date DATE,
    payout_type TEXT,
    payout_method TEXT,
    livemode BOOLEAN,
    source_payload_sha256 TEXT NOT NULL CHECK (length(source_payload_sha256) = 64),
    source_record_sha256 TEXT NOT NULL CHECK (length(source_record_sha256) = 64),
    evidence_grade TEXT NOT NULL,
    source_boundary TEXT NOT NULL DEFAULT '',
    provider_metadata JSONB NOT NULL DEFAULT '{}',
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(provider, provider_account, provider_record_key)
);

CREATE INDEX idx_provider_payouts_arrival
    ON gg_provider_payouts(provider, provider_account, arrival_date);

CREATE TABLE gg_provider_customer_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    provider_account TEXT NOT NULL DEFAULT '',
    snapshot_sha256 TEXT NOT NULL CHECK (length(snapshot_sha256) = 64),
    import_batch_id UUID NOT NULL REFERENCES gg_provider_import_batches(id),
    customer_key TEXT NOT NULL,
    customer_key_kind TEXT NOT NULL,
    first_success_date DATE,
    last_success_date DATE,
    current_status TEXT NOT NULL,
    current_product TEXT,
    current_last_payment_date DATE,
    current_next_payment_date DATE,
    payment_rows INTEGER NOT NULL DEFAULT 0,
    succeeded_rows INTEGER NOT NULL DEFAULT 0,
    refunded_rows INTEGER NOT NULL DEFAULT 0,
    lifetime_gross_amount DECIMAL,
    lifetime_net_amount DECIMAL,
    period_gross_amount DECIMAL,
    period_net_amount DECIMAL,
    confirmed_cancel_events INTEGER NOT NULL DEFAULT 0,
    latest_confirmed_cancel_date DATE,
    pause_events INTEGER NOT NULL DEFAULT 0,
    latest_pause_date DATE,
    successes_after_latest_cancel INTEGER NOT NULL DEFAULT 0,
    lifecycle_class TEXT NOT NULL,
    source_record_sha256 TEXT NOT NULL CHECK (length(source_record_sha256) = 64),
    evidence_grade TEXT NOT NULL,
    source_boundary TEXT NOT NULL DEFAULT '',
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(provider, provider_account, snapshot_sha256, customer_key)
);

COMMENT ON COLUMN gg_provider_customer_snapshots.customer_key_kind IS
    'snapshot_local means the key must not be joined to another snapshot as a stable identity.';

CREATE INDEX idx_provider_customer_snapshot_status
    ON gg_provider_customer_snapshots(provider, provider_account, observed_at, current_status);

CREATE TABLE gg_provider_monthly_controls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    provider_account TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL,
    control_month DATE NOT NULL,
    import_batch_id UUID NOT NULL REFERENCES gg_provider_import_batches(id),
    metrics JSONB NOT NULL,
    source_payload_sha256 TEXT NOT NULL CHECK (length(source_payload_sha256) = 64),
    source_record_sha256 TEXT NOT NULL CHECK (length(source_record_sha256) = 64),
    evidence_grade TEXT NOT NULL,
    source_boundary TEXT NOT NULL DEFAULT '',
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(provider, provider_account, source_kind, control_month)
);

CREATE INDEX idx_provider_monthly_controls_month
    ON gg_provider_monthly_controls(provider, provider_account, source_kind, control_month);

ALTER TABLE gg_provider_import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_provider_payouts ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_provider_customer_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_provider_monthly_controls ENABLE ROW LEVEL SECURITY;

-- The service-role key bypasses RLS.  Explicitly deny ordinary PostgREST roles
-- so financial controls and lifecycle snapshots cannot be read anonymously.
DROP POLICY IF EXISTS "service_role_all" ON gg_payments;
DROP POLICY IF EXISTS "Service role only" ON gg_payments;
CREATE POLICY "Service role only" ON gg_payments
    FOR ALL USING (false) WITH CHECK (false);
CREATE POLICY "Service role only" ON gg_provider_import_batches
    FOR ALL USING (false) WITH CHECK (false);
CREATE POLICY "Service role only" ON gg_provider_payouts
    FOR ALL USING (false) WITH CHECK (false);
CREATE POLICY "Service role only" ON gg_provider_customer_snapshots
    FOR ALL USING (false) WITH CHECK (false);
CREATE POLICY "Service role only" ON gg_provider_monthly_controls
    FOR ALL USING (false) WITH CHECK (false);
