-- Do-not-email list for Mission Control: current and former coached athletes
-- (and anyone else Matti never wants nurtured). Every sequence send, enroll,
-- resend and race-watch notification checks it; only receipts for a form the
-- person just filed (athlete_review, athlete_exit, plan_debrief) are exempt.
-- Rows hold an address and why, nothing else. Service role only.
create table if not exists public.gg_contact_suppressions (
  email text primary key check (email = lower(btrim(email)) and position('@' in email) > 1),
  reason text not null default 'coached_athlete',
  source text not null default 'manual',
  created_at timestamptz not null default now()
);

alter table public.gg_contact_suppressions enable row level security;

comment on table public.gg_contact_suppressions is
  'Mission Control do-not-email list (coached athletes). Checked before every marketing or follow-up send. Service role only.';
