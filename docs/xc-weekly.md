# XC Ski Labs Weekly

A once-a-week round-up of cross-country ski news and podcasts with a short
take, sent as Matti from `weekly@xcskilabs.com`. Spec (Matti, 2026-11-15): a
Johnny Klister toned round-up surveying blogs, news sources (langrenn.com,
FasterSkier, Norwegian outlets) and podcasts, a quick summary of the week and
an editorial paragraph or two.

## Pipeline

| Step | Where | When |
|---|---|---|
| Collect | `xc-weekly-collect.yml` → `scripts/collect_xc_weekly.py` | daily 05:15 UTC, artifact kept 21 days |
| Headline brief | `xc-weekly-brief.yml` → `draft_xc_weekly.py --brief` | Sundays 18:00 UTC, or dispatch |
| Matti reacts | reply to the brief email or comment on the issue | whenever he's read it |
| Draft, gate, stage | `xc-weekly-draft-staging.yml` → `draft_xc_weekly.py --from-brief` | on each of Matti's comments on the brief issue |
| Preview | `send_xc_weekly.py --preview` | in the staging run, to the review inbox only |
| Send | `xc-weekly-send.yml` → `send_xc_weekly.py --broadcast` | manual, with the approved hash |

Sources live in `config/xc-weekly-sources.json`; every feed was fetched and
parsed on its `verified_on` date. A feed that fails shows up in the review
issue's coverage table. It is never swapped for another source.

The draft brief is `prompts/xc-weekly-voice.md` (voice evidence:
`writing-graph` `inbox/gravel-god/you-know-people-remember-how-you-race-right.md`,
`your-eating-habits-are-killing-your-performance.md`,
`you-dont-need-to-bike-to-bike-fast.md`). `scripts/xc_weekly_issue.py`
holds the publication gate. It refuses: links not taken from the collected
items, an eight-word run copied from a source, quotation marks, AI or
automation wording, Matti in the third person, slop words, and a take
without `[n]` markers that resolve to stories. A draft that fails gets one
repair pass; then the run fails and nothing is staged.

## Reacting and sending

1. Sunday's run shortlists the week (5 to 9 stories, up to 4 podcasts, each
   with headline, blurb and link) and opens a GitHub issue labelled
   `xc-weekly-brief`, assigned to `wattgod`, so it reaches Matti's inbox.
   Source coverage is in the issue.
2. Matti replies to that email or comments on the issue: what he thinks,
   which story leads, what to drop or add, by shortlist number. Only
   comments by `wattgod` count.
3. Each comment starts the draft. The take is written from his reactions
   only, with no opinion he did not give; the publication gate runs; a
   preview goes to the review inbox; the staged review and its hash are
   posted back on the same issue and it gains the `xc-weekly-draft` label.
   Another comment redrafts with everything he has said so far. A comment
   that only approves (go, send it, looks good) redrafts nothing.
4. No reaction means no take and nothing staged. There is no Monday
   auto-draft.
5. After Matti says go, dispatch **XC Weekly Send** on `main` with that run
   ID and hash. A different hash is refused. A rerun reuses the broadcast
   and never sends twice.

## Subscribers

xcskilabs.com `/weekly/` and the homepage band post
`source=newsletter_subscribe, brand=xcskilabs` to the lead-intake Worker.
Mission Control enrolls the address in `xc_welcome_v1` and stores
`source_data.newsletter_opt_in_at`; someone already in `xc_welcome_v1`
gets the opt-in merged onto their record. The send reads every XC
enrollment with that field, removes Mission Control opt-outs, and syncs the
Resend segment "XC Ski Labs Weekly". The footer prints
"XC Ski Labs · 2183 Lombardy St, Longmont, CO 80503" and Resend's
unsubscribe link.
