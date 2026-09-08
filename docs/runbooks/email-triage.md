# Email triage and briefing handoff

Status: proposed migration, not a claim that live Claude routines were updated.
Source audit: 2026-09-08. Scope verified: gravelgodcoaching@gmail.com only.
Other accounts require separate access verification and queue audits.

## Ownership and observed failures

| Component | Verified source/control | Intended responsibility |
| --- | --- | --- |
| Morning Intel | `.github/workflows/daily-intel.yml`, daily 12:00 UTC | Collect and persist operational facts |
| Intel triage | Claude routine `trig_01NsfF54ZZYauZTW7CtXeDpU`, listed in `wattgod/hq/STATE.md` | Turn facts into tracked work; report through Console |
| Morning Console | Claude routine `trig_01KWri9idC3oRy7gbohFTDZj`, documented in `wattgod/hq` | Sole routine daily briefing to Matti |
| Gmail reply drafter | Not located in indexed GitHub searches; live scheduler/prompt unverified | One owner for pending replies and draft creation |
| Lead bridge | `integrations/gmail-lead-bridge/Code.gs`, deployed Apps Script state unverified | Sync known leads; create explicitly approved drafts; already refuses draft conflicts |

Do not confuse Endure's in-app `review-drafts` cron with Gmail reply drafting.
Do not replace the lead bridge with a second writer.

Observed mailbox failures: unlabeled athlete replies were missed; `! Review`
accumulated repeated build alerts; multiple drafts existed for one conversation;
one draft answered questions the correspondent had explicitly withdrawn; another
remained after Matti sent a reply. Do not copy private message bodies into this repo.

## Replace the existing Gmail routine prompt with this procedure

Verify the connected account. Scan all received inbox conversations and existing
`! Reply`, `! Waiting`, and `@Action` queues, regardless of read status or labels.
Include recently archived human conversations in the initial audit so old filters
cannot silently exclude replies. Page through results; report incomplete coverage
instead of saying there are zero replies. Reuse existing Gmail labels.

For each human conversation:

1. Read the entire relevant thread, with sent mail and drafts. Page older messages
   when the recent window lacks the question being answered. Draft timestamps do
   not count as replies. Read corrections and withdrawals before classifying.
2. Check recent sent/received conversations with the same verified correspondent
   when an old request may have been answered in a separate thread. A newer message
   on an unrelated topic is not proof of resolution.
3. Record the outstanding request and its source message ID. If Matti owes a
   substantive response, apply `! Reply`; if the correspondent owes an explicit
   answer, apply `! Waiting`. Remove the opposite state only after verifying the
   transition. A thank-you, race result, or withdrawn request does not automatically
   create a reply obligation. Preserve ambiguous items in `! Review` with a reason.
4. Prioritize service/delivery failures, time-sensitive athlete decisions, warm
   leads, then routine check-ins. Sort within those groups by deadline and age.
   Give each item one next action. Do not infer completion of calendar changes,
   refunds, payment recovery, or plan delivery from an email promising to do them.
5. Before creating a draft, enumerate existing drafts for the thread. Never add a
   second alternative. Preserve human edits. If a draft is stale, duplicated, or
   contradicted by a later message, label it `Drafts/Needs correction` and explain
   why in the review queue. Do not delete or overwrite it automatically.
6. Create only drafts authorized by the existing workflow/user. Follow
   `docs/AI_WRITING_POLICY.md` before writing as Matti. Ground every factual claim
   in the current thread or verified coaching data. No invented calendar changes,
   forced jokes, or sales pitch inserted into athlete support.
7. Immediately before any authorized draft write, re-fetch the latest non-draft
   message and existing drafts. If either changed since analysis, reclassify and
   skip the write. Use one writer; parallel runs must not draft the same thread.
   Use account + thread ID + latest inbound message ID as the idempotency key.
8. Read back the draft and labels. Record source ID, disposition, draft ID if any,
   reason, and verification result in restricted routine state. An uncertain write
   result requires reconciliation, never a blind retry. Never send email.

Retain unresolved items across runs; a search lookback expiring must not close a
request. A daily pass returns changes and overdue work to Console, not another
email. Report collector failures distinctly from an empty queue.

## Technical mail handling

- `GG/Ops`: build logs, PR CI failures, and routine reports. Do not make every
  repeated notification a fresh `! Review` item.
- Consolidate repeated preview failures by project and main-branch workflow
  failures by repository + workflow + branch. Preserve a current actionable
  representative and the historical evidence. A new project/branch/failure class
  must not disappear through a sender-wide rule.
- Keep security, payment failures, production incidents, and delivery failures
  visible until resolved by evidence. A dev-project security alert is not cleared
  by a clean production-project scan. A promised card update is not a paid invoice.
- `GG/Money`: routine receipts. `Read & Offers`: newsletters and promotions.
- Archive only classified noise or verified resolved conversations. Preserve
  unread state. Do not delete mail, unsubscribe, or create broad sender filters.
- Closure needs a receipt: a sent reply, confirmed transaction, verified fix, or
  explicit withdrawal. A PR merge alone does not prove the production fix works.

## Briefing migration: preserve the feeder before removing the email

The current default remains email. `--snapshot-only` still collects and interprets
the report, writes dated JSON and Markdown, and never calls Resend. Unlike email
mode, a snapshot write failure exits nonzero because the snapshot is the delivery.
The existing commit step publishes those files to GitHub.

1. In Claude, inspect the two known routine IDs above and locate the Gmail drafter
   by its Gmail-draft actions/run history. Save current prompts and schedules.
   Also inventory any Daily Brief routine; do not assume it is retired merely
   because it is absent from HQ's table.
2. Update intel triage and Console to read this repo's dated
   `data/intel-snapshots/YYYY-MM-DD.json` and `.md`, not depend on an inbox email.
   Require today's committed snapshot; missing/stale snapshots are an explicit
   feeder failure, never "all clear." Preserve tracked unresolved work on failure.
   Have triage publish issues/results for Console rather than send its own email.
3. Run the existing consumers against a committed snapshot and verify that known
   failures are represented once with their issue/action links. Test a missing or
   stale snapshot and require a visible failure. Verify the Gmail procedure below.
4. Only after consumer verification, set repository Actions variable
   `INTEL_DELIVERY_MODE=snapshot-only`. Manual dispatch has a delivery choice for
   testing. Do not silently activate this mode before the Claude handoff works.
5. Verify a scheduled run: successful JSON + Markdown commit, successful consumer
   reads, one Console briefing, no separate Intel/triage/Daily Brief email.
   Roll back the variable to `email` if consumers cannot retrieve the snapshots.

This file is not automatically loaded by Claude's existing scheduler. Someone
with that scheduler's controls must install the procedure in the existing jobs;
merging this PR alone does not complete the migration.

## Acceptance cases for the Gmail routine

Use synthetic messages and a non-sending validation pass before live drafting:

| Case | Required outcome |
| --- | --- |
| Unread or already-read human reply with no custom label | Both found and classified |
| Question followed by "ignore those questions" | No draft answering the withdrawn questions |
| Old inbound followed by Matti's sent answer | No new reply obligation for the answered request |
| Unrelated newer sent email | Original unresolved request retained |
| Existing draft; repeated run with no new inbound | No second draft, no human edit overwritten |
| New inbound arrives between analysis and write | Skip write and reclassify |
| Draft write times out after server accepts it | Reconcile by readback before any retry |
| Thread exceeds the tool's message window | Fetch missing context or mark incomplete; never guess |
| Repeated preview failures plus a new security alert | Consolidate previews; preserve security action |
| Payment update promised but no receipt | Payment action remains unresolved |

Completion means the source routines have these behaviors and have passed the
cases, not that the inbox was archived once or another summary was created.
