-- Mission Control v2: Automation Engine + Revenue Dashboard
-- Run after 20260216000001_mission_control.sql

-- ---------------------------------------------------------------------------
-- Automation: sequence execution state
-- ---------------------------------------------------------------------------

CREATE TABLE gg_sequence_enrollments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_id TEXT NOT NULL,
    variant TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    contact_name TEXT DEFAULT '',
    source TEXT,
    source_data JSONB DEFAULT '{}',
    current_step INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    enrolled_at TIMESTAMPTZ DEFAULT now(),
    next_send_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE(sequence_id, contact_email)
);

CREATE TABLE gg_sequence_sends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enrollment_id UUID REFERENCES gg_sequence_enrollments(id),
    step_index INTEGER NOT NULL,
    template TEXT NOT NULL,
    subject TEXT NOT NULL,
    resend_id TEXT,
    status TEXT DEFAULT 'sent',
    sent_at TIMESTAMPTZ DEFAULT now(),
    opened_at TIMESTAMPTZ,
    clicked_at TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- Sales pipeline
-- ---------------------------------------------------------------------------

CREATE TABLE gg_deals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_email TEXT NOT NULL,
    contact_name TEXT DEFAULT '',
    race_name TEXT,
    race_slug TEXT,
    stage TEXT DEFAULT 'lead',
    value DECIMAL DEFAULT 249.00,
    source TEXT,
    notes TEXT DEFAULT '',
    athlete_id UUID REFERENCES gg_athletes(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    closed_at TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- Revenue tracking
-- ---------------------------------------------------------------------------

CREATE TABLE gg_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID REFERENCES gg_deals(id),
    athlete_id UUID REFERENCES gg_athletes(id),
    amount DECIMAL NOT NULL,
    source TEXT DEFAULT 'manual',
    stripe_payment_id TEXT,
    description TEXT DEFAULT '',
    paid_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- GA4 cache
-- ---------------------------------------------------------------------------

CREATE TABLE gg_ga4_cache (
    cache_key TEXT PRIMARY KEY,
    data JSONB NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX idx_enrollments_status ON gg_sequence_enrollments(status, next_send_at);
CREATE INDEX idx_enrollments_email ON gg_sequence_enrollments(contact_email);
CREATE INDEX idx_sends_enrollment ON gg_sequence_sends(enrollment_id);
CREATE INDEX idx_deals_stage ON gg_deals(stage);
CREATE INDEX idx_deals_email ON gg_deals(contact_email);
CREATE INDEX idx_payments_month ON gg_payments(paid_at);

-- ---------------------------------------------------------------------------
-- RLS: service-role only (same pattern as v1)
-- ---------------------------------------------------------------------------

ALTER TABLE gg_sequence_enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_sequence_sends ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_deals ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_ga4_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all" ON gg_sequence_enrollments FOR ALL USING (true);
CREATE POLICY "service_role_all" ON gg_sequence_sends FOR ALL USING (true);
CREATE POLICY "service_role_all" ON gg_deals FOR ALL USING (true);
CREATE POLICY "service_role_all" ON gg_payments FOR ALL USING (true);
CREATE POLICY "service_role_all" ON gg_ga4_cache FOR ALL USING (true);
