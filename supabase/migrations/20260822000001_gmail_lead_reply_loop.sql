-- Gmail lead reply loop: durable conversations, draft approvals, and reply attribution.
-- Bodies are private operator data. Tables are service-role only.

ALTER TABLE gg_sequence_sends
    ADD COLUMN IF NOT EXISTS reply_token TEXT,
    ADD COLUMN IF NOT EXISTS question_type TEXT DEFAULT 'other',
    ADD COLUMN IF NOT EXISTS reply_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS first_reply_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS complained_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS idx_sequence_sends_reply_token
    ON gg_sequence_sends(reply_token)
    WHERE reply_token IS NOT NULL;

CREATE TABLE IF NOT EXISTS gg_lead_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gmail_thread_id TEXT NOT NULL UNIQUE,
    contact_email TEXT NOT NULL,
    contact_name TEXT DEFAULT '',
    brand TEXT DEFAULT 'gravelgod',
    deal_id UUID REFERENCES gg_deals(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'needs_reply'
        CHECK (status IN (
            'needs_reply', 'suggested', 'approved_for_gmail', 'gmail_drafted',
            'waiting_on_lead', 'won', 'lost', 'closed', 'draft_conflict'
        )),
    intent TEXT DEFAULT 'unknown',
    latest_question_type TEXT DEFAULT 'other',
    last_sequence_send_id UUID REFERENCES gg_sequence_sends(id) ON DELETE SET NULL,
    last_inbound_at TIMESTAMPTZ,
    last_outbound_at TIMESTAMPTZ,
    first_reply_latency_seconds INTEGER,
    inbound_count INTEGER NOT NULL DEFAULT 0,
    outbound_count INTEGER NOT NULL DEFAULT 0,
    substantive_reply_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gg_lead_messages (
    gmail_message_id TEXT PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES gg_lead_conversations(id) ON DELETE CASCADE,
    gmail_thread_id TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound', 'draft')),
    from_address TEXT NOT NULL DEFAULT '',
    to_addresses JSONB NOT NULL DEFAULT '[]',
    cc_addresses JSONB NOT NULL DEFAULT '[]',
    subject TEXT NOT NULL DEFAULT '',
    body_text TEXT NOT NULL DEFAULT '',
    body_sha256 TEXT NOT NULL DEFAULT '',
    message_at TIMESTAMPTZ NOT NULL,
    sequence_send_id UUID REFERENCES gg_sequence_sends(id) ON DELETE SET NULL,
    attribution_confidence TEXT DEFAULT 'none'
        CHECK (attribution_confidence IN ('exact', 'email_time', 'none')),
    question_type TEXT DEFAULT 'other',
    reply_quality TEXT DEFAULT 'brief'
        CHECK (reply_quality IN ('brief', 'substantive')),
    word_count INTEGER NOT NULL DEFAULT 0,
    is_trash BOOLEAN NOT NULL DEFAULT false,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gg_lead_reply_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES gg_lead_conversations(id) ON DELETE CASCADE,
    inbound_message_id TEXT NOT NULL UNIQUE REFERENCES gg_lead_messages(gmail_message_id) ON DELETE CASCADE,
    initial_draft_text TEXT NOT NULL DEFAULT '',
    draft_text TEXT NOT NULL DEFAULT '',
    suggested_question TEXT NOT NULL DEFAULT '',
    question_type TEXT NOT NULL DEFAULT 'other',
    needs_coach_answer BOOLEAN NOT NULL DEFAULT false,
    rationale TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'suggested'
        CHECK (status IN (
            'suggested', 'needs_coach_answer', 'approved_for_gmail',
            'gmail_drafted', 'sent', 'superseded', 'dismissed', 'draft_conflict'
        )),
    gmail_draft_id TEXT,
    gmail_draft_message_id TEXT,
    approved_at TIMESTAMPTZ,
    drafted_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lead_conversations_contact
    ON gg_lead_conversations(contact_email, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_lead_conversations_status
    ON gg_lead_conversations(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_lead_messages_conversation
    ON gg_lead_messages(conversation_id, message_at);
CREATE INDEX IF NOT EXISTS idx_lead_messages_sequence_send
    ON gg_lead_messages(sequence_send_id)
    WHERE sequence_send_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_lead_suggestions_status
    ON gg_lead_reply_suggestions(status, updated_at DESC);

ALTER TABLE gg_lead_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_lead_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE gg_lead_reply_suggestions ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON gg_lead_conversations FROM anon, authenticated;
REVOKE ALL ON gg_lead_messages FROM anon, authenticated;
REVOKE ALL ON gg_lead_reply_suggestions FROM anon, authenticated;
GRANT ALL ON gg_lead_conversations TO service_role;
GRANT ALL ON gg_lead_messages TO service_role;
GRANT ALL ON gg_lead_reply_suggestions TO service_role;
