-- Mission Control tables — all prefixed gg_ to coexist with plan_requests.
-- Manages athlete lifecycle: intake → pipeline → QC → delivery → touchpoints → post-race.

-- gg_athletes: Core athlete record
CREATE TABLE gg_athletes (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,
    plan_request_id TEXT REFERENCES plan_requests(request_id),
    name            TEXT NOT NULL,
    email           TEXT NOT NULL,
    tier            TEXT,
    level           TEXT,
    race_name       TEXT,
    race_date       DATE,
    plan_weeks      INTEGER,
    weekly_hours    TEXT,
    ftp             INTEGER,
    plan_status     TEXT DEFAULT 'intake_received',
    intake_json     JSONB,
    derived_json    JSONB,
    methodology_json JSONB,
    notes           TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- gg_pipeline_runs: Every pipeline execution with per-step tracking
CREATE TABLE gg_pipeline_runs (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    athlete_id      UUID NOT NULL REFERENCES gg_athletes(id),
    run_type        TEXT NOT NULL DEFAULT 'draft',
    status          TEXT NOT NULL DEFAULT 'pending',
    current_step    TEXT DEFAULT '',
    steps_completed JSONB DEFAULT '[]',
    error_message   TEXT DEFAULT '',
    stdout          TEXT DEFAULT '',
    duration_secs   REAL,
    skip_pdf        BOOLEAN DEFAULT true,
    skip_deploy     BOOLEAN DEFAULT true,
    skip_deliver    BOOLEAN DEFAULT true,
    started_at      TIMESTAMPTZ DEFAULT now(),
    finished_at     TIMESTAMPTZ
);

-- gg_touchpoints: Scheduled lifecycle emails
CREATE TABLE gg_touchpoints (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    athlete_id      UUID NOT NULL REFERENCES gg_athletes(id),
    touchpoint_id   TEXT NOT NULL,
    category        TEXT NOT NULL,
    send_date       DATE NOT NULL,
    subject         TEXT NOT NULL,
    template        TEXT NOT NULL,
    sent            BOOLEAN DEFAULT false,
    sent_at         TIMESTAMPTZ,
    resend_id       TEXT,
    template_data   JSONB,
    UNIQUE(athlete_id, touchpoint_id)
);

-- gg_communications: Every email sent (delivery, touchpoints, manual)
CREATE TABLE gg_communications (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    athlete_id      UUID NOT NULL REFERENCES gg_athletes(id),
    comm_type       TEXT NOT NULL,
    subject         TEXT,
    recipient       TEXT,
    resend_id       TEXT,
    status          TEXT DEFAULT 'sent',
    sent_at         TIMESTAMPTZ DEFAULT now()
);

-- gg_nps_scores: Post-race NPS
CREATE TABLE gg_nps_scores (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    athlete_id      UUID NOT NULL REFERENCES gg_athletes(id),
    score           INTEGER NOT NULL CHECK(score BETWEEN 0 AND 10),
    comment         TEXT DEFAULT '',
    race_name       TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- gg_referrals: Referral tracking
CREATE TABLE gg_referrals (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    referrer_id     UUID NOT NULL REFERENCES gg_athletes(id),
    referred_name   TEXT NOT NULL,
    referred_email  TEXT NOT NULL,
    status          TEXT DEFAULT 'pending',
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- gg_files: Metadata for files in Supabase Storage
CREATE TABLE gg_files (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    athlete_id      UUID NOT NULL REFERENCES gg_athletes(id),
    file_type       TEXT NOT NULL,
    storage_path    TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    size_bytes      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- gg_audit_log: Every operator action
CREATE TABLE gg_audit_log (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    action          TEXT NOT NULL,
    entity_type     TEXT,
    entity_id       TEXT,
    details         TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- gg_settings: App configuration
CREATE TABLE gg_settings (
    key             TEXT PRIMARY KEY,
    value           TEXT
);

-- Indexes
CREATE INDEX idx_gg_athletes_status ON gg_athletes(plan_status);
CREATE INDEX idx_gg_athletes_race_date ON gg_athletes(race_date);
CREATE INDEX idx_gg_touchpoints_due ON gg_touchpoints(send_date, sent);
CREATE INDEX idx_gg_pipeline_runs_athlete ON gg_pipeline_runs(athlete_id);
CREATE INDEX idx_gg_files_athlete ON gg_files(athlete_id);

-- RLS: All tables locked to service role only
ALTER TABLE gg_athletes ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_touchpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_communications ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_nps_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_referrals ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role only" ON gg_athletes FOR ALL USING (false) WITH CHECK (false);
CREATE POLICY "Service role only" ON gg_pipeline_runs FOR ALL USING (false) WITH CHECK (false);
CREATE POLICY "Service role only" ON gg_touchpoints FOR ALL USING (false) WITH CHECK (false);
CREATE POLICY "Service role only" ON gg_communications FOR ALL USING (false) WITH CHECK (false);
CREATE POLICY "Service role only" ON gg_nps_scores FOR ALL USING (false) WITH CHECK (false);
CREATE POLICY "Service role only" ON gg_referrals FOR ALL USING (false) WITH CHECK (false);
CREATE POLICY "Service role only" ON gg_files FOR ALL USING (false) WITH CHECK (false);
CREATE POLICY "Service role only" ON gg_audit_log FOR ALL USING (false) WITH CHECK (false);
CREATE POLICY "Service role only" ON gg_settings FOR ALL USING (false) WITH CHECK (false);
