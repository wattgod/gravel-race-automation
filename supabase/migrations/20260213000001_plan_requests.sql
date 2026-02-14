-- Plan submission requests from gravelgodcycling.com questionnaire
-- The Cloudflare Worker inserts here after sending the SendGrid email.
-- new_plan.py queries by request_id to pull data for pipeline execution.

CREATE TABLE IF NOT EXISTS public.plan_requests (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    request_id TEXT UNIQUE NOT NULL,       -- e.g. "tp-sbt-grvl-sarah-printz-mlju8jn9"
    payload JSONB NOT NULL,                 -- Full training request JSON from worker
    status TEXT DEFAULT 'pending' NOT NULL,  -- pending, processing, completed, failed
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    processed_at TIMESTAMPTZ
);

-- Index for lookup by request_id (the ID shown in the email)
CREATE INDEX idx_plan_requests_request_id ON public.plan_requests(request_id);
CREATE INDEX idx_plan_requests_status ON public.plan_requests(status);

-- RLS: Only service role can read/write (the worker and pipeline use service key)
ALTER TABLE public.plan_requests ENABLE ROW LEVEL SECURITY;

-- No public access
CREATE POLICY "Service role only" ON public.plan_requests
    FOR ALL
    USING (false)
    WITH CHECK (false);
