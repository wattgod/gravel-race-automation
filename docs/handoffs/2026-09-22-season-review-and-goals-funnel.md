# Season review + the 2027 goals funnel — handoff

**Date:** 2026-09-22 (into the 23rd) · **Repo:** gravel-race-automation
**Worktree:** `~/Documents/GravelGod/gra-season-review` (branch `feat/goals-page`)
**Spec:** `docs/specs/goals-2027-funnel-spec.md` v0.3 — read it before changing shape.
**Mockups:** https://claude.ai/artifact/JugTXP7Sx5RpnHeZjXZycz (Matti picked hero **D1**,
the poster wall)

---

## What is live right now

| Thing | Where | Version |
|---|---|---|
| Public lead page | https://gravelgodcycling.com/goals/ (`index, follow`) | page deployed 2026-09-22 |
| Athlete season review | https://gravelgodcycling.com/coaching/season-review/athlete/ (noindex) | same |
| Lead worker | `fueling-lead-intake.gravelgodcoaching.workers.dev` | `2921528f` |
| Mission Control | `athlete-profiles-production.up.railway.app` (Railway service **athlete-profiles**) | main @ 7515ce09 |

Merged: **#373** (build), **#375** (Fable round 1). **#376 is OPEN** — the `/goals/` page
plus the fixes from Fable round 2. Its code is already deployed; the PR is the source of
truth catching up. All checks were green. Matti was asked whether to merge and had not
answered.

## The shape of it

1. A rider fills in `/goals/` (24 questions, ~15 min, optional deeper sections).
2. The page posts to the worker (`source=goal_2027`), which forwards to Mission Control,
   which stores the answers on a `gg_sequence_enrollments` row and issues a poster token.
3. The page then shows a **results screen**: the poster drawn in the browser from their
   answers, a PNG download, and **beneath it** one of three offer copy variants
   (A/B/C, chosen on load, sent with the lead so the test is readable later).
4. Mission Control's `goal_2027_v1` sequence emails the poster
   (`/poster/{token}.png`, rendered on demand by Pillow) and one check-in a week later.
5. Coached athletes get the same machinery at `/coaching/season-review/athlete/`
   (`source=athlete_review`): worker + email backstop, a receipt to the athlete, an alert
   to Matti, and answers he can file with `scripts/file_athlete_review.py`.

Question sets are **data** (`wordpress/season_review_variants.py`); one renderer
(`wordpress/generate_season_review.py`) draws every variant. Six exist: `standard`,
`claude`, `matti`, `goal_2027`, `five`, `athlete`. The "So. 2026." sections are shared
functions (`s_highlight`, `s_blooper`, `s_2027`, `s_obstacle`, `s_habit`, …) so the lead
page and the athlete page cannot drift into different voices — tests pin the wording.

## Rulings — do not re-litigate

- **Hero D1** (poster wall) for the homepage, race band beneath, and the goal strip on
  **race pages** in Oct–Jan. Homepage is ~5% of landings; race pages carry the traffic
  (verified against the Sep 21 intel snapshot and the weekly SEO report).
- **No auto-rotating carousel.** Rotate artwork only, never the headline or button.
- **The offer never precedes the deliverable.** Poster first, offer underneath.
- **Season Plan is a separate product, not a raised cap** ($449 proposed, Matti sets the
  number). A 45-week race plan already costs $249, so it must differ in kind:
  multi-race periodisation + four scheduled rebuilds. Labour budget ≈1h45 per athlete
  per year, and only if Motoren does the rebuilds.
- **Posters shown on the site** use real, permissioned athlete goals or are marked SAMPLE.
- **Headline register:** flat deadpan, no commands, ≤60 chars. "Most goals die in
  February" was cut as an unsourced statistic. Live slate: "Everyone is fast in January",
  "Same goal as last year. Bold.", "It's dreaming season. Most of it stays a dream."
- **No FTP or training numbers** in any questionnaire; they come from data.

## Traps that cost time here

- **SendGrid is dead on this account.** Sends 401, marketing-contact upserts 403, for
  *every* lead source — leads may not be reaching the SendGrid list at all. Unfixed,
  pre-existing, worth its own look. Notifications were moved to **Resend**.
- **Resend senders are not interchangeable.** `matti@gravelgodcycling.com` is accepted
  (200, with an id) and never arrives. `noreply@gravelgodcycling.com` lands in seconds.
- **Gmail hides FormSubmit mail.** A filter matches
  `{from:…trainingpeaks… from:submissions@formsubmit.co} -subject:"Sold a Training Plan"`
  → Skip Inbox + `Domain/Coaching`. Editing a filter through Gmail's UI with Playwriter
  silently switches to *create-filter* mode and would leave a duplicate — do not try.
  Workaround in place: the coach alert uses subject `[GG] Season review filed · X`.
- **Railway** builds `main` automatically; MC is the `athlete-profiles` service and sets
  `RAILWAY_PUBLIC_DOMAIN` itself, so `MC_PUBLIC_URL` needs nothing. `railway variables
  --json` from the main checkout is how the Resend key reached Cloudflare.
- **Squash merges orphan the branch.** After #373 merged, the branch conflicted; rebuild
  on `origin/main` and cherry-pick rather than merging.
- **`push_wordpress.py`** needs a flag in *three* places: the argument, the dispatch, and
  the "did you pass a sync flag" tuple (~line 4436) — miss the third and it exits with a
  usage error.
- **Pre-existing red on main:** `mission_control/tests/test_pre_deploy_audit.py` (analytics
  CSS classes). Not ours.
- Test data goes in `gg_sequence_enrollments`; delete `gg_sequence_sends` children first
  or the delete 409s.

## Open, and what I would do next

1. **Merge #376** (asked, unanswered).
2. **Matti's calls:** the Season Plan price and labour budget; whether to add
   `-subject:"Season Review"` to that Gmail filter; the poster style (dark vs paper).
3. **Known and unfixed, both wording decisions:** a repeat submission updates the answers
   but sends no second email while the screen says a copy is coming; "within 24 hours"
   depends on the rider finishing checkout.
4. **Next build steps** (spec §Build order): the homepage poster wall + race-page strip,
   then pricing into one file (`pricing.json`, Stripe prices built at checkout — the
   "$249" string is in 41 files), then the Season Plan, then the prefilled plan form,
   then the Endure filing endpoint, then Roadie Labs and XC.
5. **Not started:** the `/walkthrough` voice-feedback loop Matti asked for (record while
   using the page, transcribe, turn into per-section items).

## Review discipline that earned its keep

sol reviewed the questionnaire three times; Fable reviewed the spec once and the shipped
code twice. Between them they caught: answers being dropped by two whitelists, a false
privacy promise, links breaking on deletion, a $249 product undercutting a $499 one, no
attachment path for the poster, a build order that shipped pages returning 400, the
marketing guards silently discarding coached athletes' reviews, a filing script that
would have deleted an athlete's history in Endure, and a lead that could vanish while the
page said "it's in your file". **Verify every finding against the code before acting —
several did not survive that check.**
