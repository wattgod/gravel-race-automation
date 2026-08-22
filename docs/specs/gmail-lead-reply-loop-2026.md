# Gmail Lead Reply Loop — implementation and voice audit

**Status:** built on `codex/gmail-lead-reply-loop`; not deployed.
**Date:** 2026-08-21
**System of record:** Mission Control/Supabase for operational state; Gmail for
the original communication; Endure receives the relationship only after a lead
becomes an athlete.

## Goal

Know which Gravel God or Roadie message created a conversation, stop automated
follow-ups when a person answers, give Matti one clean draft to edit, and learn
which questions create useful conversations and customers without spending
trust.

## Evidence audit

A read-only sample of recent Gmail threads tied to the canonical sequence
subjects showed:

- The simplest questions produced the richest context. “How's training going?”
  elicited weekly volume, climbing work, vacation disruption, confidence, and
  race concerns in one reply.
- One plain follow-up — asking what got in the way — surfaced injury treatment,
  insufficient preparation, a deferred goal, and a positive result at another
  event.
- Asking about the practical reason behind an overnight concern surfaced the
  real constraint: cost. That is more useful than guessing an objection.
- “How'd it go?” produced detailed race stories without needing a clever frame.
- Operational failures (“never received it”, missing guide/attachment) also
  appeared as replies. These are service incidents first and sales leads second.
- Several threads accumulated multiple alternative Gmail drafts. Some were
  later trashed, but the active thread could still contain a stale version.
- The weakest suggested replies were not wrong; they were over-authored. Long
  metaphors, verdict-like language, and two or three coaching assertions made
  the response sound more eager to perform a voice than to hear the person.

Conclusion: the current friend-register strategy is correct. The improvement is
less stylistic voltage, better operational memory, and disciplined follow-up.

## Matti reply register: Reflect → Give → Ask

1. **Reflect one specific thing.** Prove the reply was read. Do not restate the
   whole message or produce therapy language.
2. **Give one useful thing when grounded.** Answer the question, make one
   connection, or name one practical implication. If evidence is missing, do
   not manufacture expertise to fill the space.
3. **Ask one easy question.** One question mark is the default. The answer
   should fit in one line, although the person may choose to say more.

The tone is professionally useful, recognizably human, and occasionally
deadpan. Dry understatement is seasoning, not a compulsory brand device. The
system carries forward the recent thread and advances the question ladder
instead of restarting an intake interview on every reply. By the third lead
turn, the editor must add a useful observation or practical suggestion before
asking for anything else.

Do not pitch unless the person asks about a plan, coaching, price, or what to do
next and the offer genuinely answers that question.

### Question ladder

Use the lowest-effort question that can reveal the next useful fact.

| Stage | Purpose | Good shapes |
|---|---|---|
| First reply | Establish context | “Still deciding, or registered?” “How's training going?” |
| Context known | Find the constraint | “What's been hardest to get right?” “What keeps getting in the way?” |
| Training conversation | Learn motivation/preferences | “What workout do you actually look forward to?” |
| Race conversation | Find failure mode | “Where does the race usually start going wrong?” |
| Engaged relationship | Invite a story | “What went well, and what would you change?” |

Avoid a three-question stack. Avoid “why?” as the first response when “what” or
a simple choice will feel less interrogative. Favorite-workout questions are
useful after a person has shown interest in training; dropped cold, they can
sound like engagement bait.

## Runtime

1. Sequence emails receive a unique Gmail plus-address reply token.
2. The account-local Apps Script runs every five minutes, scans a rolling
   30-day overlap, and asks Mission Control which correspondents are known
   leads. A one-time 180-day backfill reconciles older active drafts and
   replies; Gmail message IDs keep repeated scans idempotent.
3. It syncs only those Gmail threads. Mission Control verifies identity again
   before storing any body.
4. An inbound reply is attributed to the exact sequence send when the token is
   present, otherwise to the nearest eligible send by email and time with lower
   confidence.
5. Active marketing enrollments pause immediately. Post-purchase service
   sequences remain active.
6. Mission Control records a conservative suggestion and an easy question.
   Explicit questions, buying signals, or service problems are marked
   `needs_coach_answer`.
7. Matti edits and approves in `/lead-replies`.
8. Apps Script creates one unsent Gmail draft. If any draft already exists in
   the thread, it records `draft_conflict` and creates nothing.
9. The next sync observes a sent reply and supersedes remaining suggestions.

## What success means

### Safety first

- Marketing sends after a reply: **0**.
- Duplicate drafts created by the bridge: **0**.
- Unmatched lead replies: trend toward **0**.
- Spam complaints and unsubscribe rate: non-increasing.
- Service incidents answered before any sales treatment.

### Conversation quality

- Reply rate by source, brand, sequence, variant, step, and question type.
- Median reply latency.
- Median coach response time from an inbound reply to Matti's next sent reply.
- Substantive reply rate (20+ newly authored words; descriptive, not a value
  judgment).
- Second-reply rate: did a question start a conversation rather than collect a
  single answer?
- Editor correction rate: how often Matti substantially changes a suggestion.
  This is the main signal for improving the drafter.
- Suggestion acceptance rate and median edit percentage. These measure whether
  the queue is actually saving Matti work, not whether text was generated.

### Business outcomes

- Movement to qualified/proposal.
- Consultation booked.
- Closed won and revenue, joined through `gg_deals`/`gg_payments` rather than
  the known-broken `gg_athletes` purchase proxy.
- Time from first capture and first reply to conversion.

## Improvement loop

- Compare actual sent questions, not merely suggested questions.
- Use the tagged Reply-To to recognize Gmail's copy of an automated sequence
  send. Count the sequence ledger once; do not count that mirrored message as
  a second send or as a manual Matti question.
- Attribute a lead's next reply to Matti's manual question when he has replied
  since the sequence email; do not double-credit the older automation.
- Require at least 30 attributed sends per question type before review. Larger
  conversion claims need more volume.
- Change one premise or question at a time. Do not “optimize” the whole sequence
  from a handful of colorful replies.
- Treat replies and substantive replies as primary conversation signals;
  opens are diagnostic only.
- Keep the sober control intact.
- Mission Control recommends; Matti approves. No automatic copy rewrites or
  weight changes.
- Review false positives and edited drafts weekly. Add the language Matti kept,
  not the language an LLM merely generated.

## Deployment order

1. Apply `20260822000001_gmail_lead_reply_loop.sql`.
2. Deploy Mission Control code with the new tables already present.
3. Subscribe the signed Resend webhook to `email.complained` in addition to the
   existing open/click/bounce events.
4. Install and authorize `integrations/gmail-lead-bridge` in the coaching Gmail
   account.
5. Run `backfillLeadThreads()` once to surface older replies and active Gmail
   drafts. Resolve conflicts manually; nothing is deleted automatically.
6. Run a dry sync and confirm known leads only, exact token attribution, and
   pause-on-reply.
7. Approve one test suggestion and verify one unsent Gmail draft appears.
8. Run `scripts/lead_nurture_report.py`; verify no active-after-reply leaks.
9. Only then enable the five-minute trigger for normal operation.

## Privacy and retention

Lead message bodies are private operational data, excluded from Git, and
stored in service-role-only tables. The bridge never syncs an address unless
Mission Control already knows it as a sequence enrollment or open deal. Add a
documented retention/deletion policy before using message bodies for model
training or exporting them to any additional provider.
