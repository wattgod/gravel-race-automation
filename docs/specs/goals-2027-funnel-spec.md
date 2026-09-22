# 2027 Goals Funnel — spec v0.2 (2026-09-22, after Fable review)

Matti's ask, in his words: the "So. 2026" season review becomes (1) a lead magnet
above the fold on gravelgodcycling.com (then Roadie Labs, XC Ski Labs) with a
provocative, on-brand headline, Manual-for-Speed UI/UX vibes, results emailed plus a
Gravel God–styled 2027 goal poster, and a conditional "step two" offer (copy
variants to test) that segues into a shorter custom-plan questionnaire, with the plan
price ceiling raised because season-long plans can't be worth $249 max; (2) a separate
version for current athletes whose answers land in their file for context and review;
(3) mockups on the site, then end-to-end tests; (4) an Endure-instead-of-TrainingPeaks
option. Everything double-checked by Fable.

Mockups: https://claude.ai/artifact/JugTXP7Sx5RpnHeZjXZycz (4 hero directions, phone
questionnaire, offer with 3 copy variants, 2 poster styles, prefilled plan form).
Questionnaire source: `wordpress/generate_season_review.py` + `season_review_variants.py`
(branch `feat/season-review`), variant `matti` ("So. 2026.").

---

## Decisions most likely to change (each has a default; Matti reverses)

| # | Decision | Default | Why |
|---|---|---|---|
| D1 | This funnel vs the Sep 17 offseason spec (`docs/specs/offseason-goal-setting-product-spec.md`: no new SKU, $150 "Offseason Read" consult, pitch-free broadcast, `/offseason/` page) | This funnel replaces that spec's page and product. The November broadcast stays pitch-free and links to the questionnaire, not an offer. The consult stays a separate, existing product. | Matti asked for a homepage lead magnet with an offer inside the flow; that spec was a draft awaiting his gates. |
| D2 | Price for a whole-season plan | New **Season Plan** product, **$499**, separate from the race plan (which stays $15/week, 4-week minimum, $249 cap). Up to 52 weeks, every A/B/C race periodised, four scheduled rescales. | Raising the cap breaks the Stripe fixed-price table (17+ weeks is a pre-made $249 price on the shared account) and every "$249" in ~20 files across 3 repos. A separate product avoids both. $499 sits between a $249 race plan and ~$2,600/yr coaching ($199 / 4 weeks). **Money: Matti sets the number before anything ships.** |
| D3 | Does the offer gate the results? | **No, and it isn't even in the way.** The results screen (poster + summary) comes first; the offer sits directly beneath it on the same screen. | Fable: an interstitial in front of the deliverable contradicts the promise, whatever the escape link says. Cheaper to build, too. |
| D4 | Where the questionnaire lives | `/goals/` (GG), `/goals/` (RL), `/goals/` (XC) — a standalone page, `index, follow` once live. Homepage hero links to it. | The homepage stays fast; the questionnaire keeps save/resume and its own analytics. |
| D5 | Homepage change | **Keep the h1** ("Every gravel race, rated."). Add the goal block as an h2 strip directly above the search box, shown Oct 1 – Jan 31, with the date passed in as a parameter (not read from the clock) so tests don't flip by calendar. Also place the strip on race pages in that window. | Fable: CI regenerates and redeploys the homepage weekly (`.github/workflows/weekly-broadcast.yml:104,162`), so a clock-driven hero flips up to a week late; swapping the flagship page's h1 for four months risks its "gravel race" ranking; and race pages carry far more traffic than the homepage. |
| D6 | What's asked | The "So. 2026." core **minus section 7 (hours, life constraints)** and minus "what do you want from me". Those move to the plan form. | Matti: "I don't think we need to put in things like 7 just yet." Leads aren't clients yet. |
| D7 | Lead plumbing | POST to `fueling-lead-intake` with a new source `goal_2027`, **plus new plumbing for the answers**: the worker forwards a size-capped `goal_answers` object and `offer_variant` (`worker.js:379-391` currently forwards only email/name/brand/source/race), Mission Control accepts them (`webhooks.py:207-275` rebuilds its own short whitelist) and stores them against the lead. Without this the answers are dropped twice — no poster, no variant logging. | Repo rule: every email form posts to its worker. Verified: both whitelists drop everything else. |
| D8 | The poster | Drawn in the browser on the results screen (instant download), and served for email from a **signed, render-on-demand route** `/poster/{token}.png` in Mission Control (Pillow, reusing `scripts/media_templates`), rendered from the stored answers. **No attachment**: `sequence_engine.py:610-616` sends Resend html only, and Railway disk persistence is unverified, so a file written at lead time could vanish on redeploy. | Verified. Depends on D7. |
| D9 | The shorter plan form | A new page, not an edit to the Elementor `/questionnaire/` (its live widget has drifted from the repo). It reads the goal answers from a signed token in the link, shows them "already on file · edit", and asks only what's missing (other races, days, equipment, health, strength, delivery). Posts to the same Railway `create-checkout`. | Lowest risk to the money path that works today. |
| D10 | Copy tests | Offer copy rotates across 3 variants (A/B/C on the canvas), logged per lead. Treat as directional: homepage traffic is too low for a significant A/B result (repo CLAUDE.md). | Matti wants many variants; the numbers won't settle it quickly, so read replies and purchases too. |
| D11 | Current athletes | A private link per athlete (signed token), modelled on `/api/delivery/consult`: verbatim answers → `extended_profile.interrogation[]` and `limiter_evidence[]` (the shapes endure-loop-2026 §3 already defines), plus draft `goals` / `goal_actions`. **Not** `plan_season_reviews`: it requires a plan (`plan_id NOT NULL`, `UNIQUE(plan_id)`) and most of the roster has no Endure plan. A **reader must be added** — David currently reads only `limiters` and `consult`. | Verified against the migration and David's context code. Fable corrected my invented `season_review_2026` key. |
| D12 | Endure option | Offered in the plan form as "Endure (beta)" **only after** the purchased-plan delivery path has its production proof; today Endure can show only the first two weeks of a Motoren plan. Until then, TrainingPeaks. | Promising a full season in Endure today would be false. |
| D13 | Brands | GG first. RL and XC after GG runs a full cycle (lead → poster → offer → purchase) in production. Each gets its own headline in its brand voice. | One funnel proven before three. |
| D14 | Which questionnaire | **Fork a `goal_2027` variant** of the question set, don't subtract from `matti`. The `matti` variant talks to someone he already coaches ("A break from me", "What should I keep doing? I can take it", "Just me and you"). | Fable: to a stranger those read as a conversation they're not part of. |
| D15 | What the Season Plan is | Differentiated by what the race plan **cannot** do: several races periodised across the year (A/B/C) and four scheduled rebuilds. Its checkout branch bypasses the week-based price and the fixed Stripe price table (which would silently charge $249), and its price ID goes in the reconciliation registry (`app.py:10386`) or the revenue is unclassified. Same 7-day full refund as the race plan. | Verified: `compute_plan_price` caps but never limits weeks, so a 45-week race plan already costs $249 (`webhook/app.py:1070-1072`). Without a real difference, the Season Plan is undercut by your own product. |
| D16 | The labour budget | Before the price, set the coach-hours budget per Season Plan (four Motoren rebuilds plus reviews). Automate the rescales or cap them. | Fable, citing the retro that a $105 order once cost a day of coach time. At $499 with four manual rebuilds this can lose money. |

## Headline slate (Matti's register: flat, deadpan, no commands, ≤60 chars)

- Everyone is fast in January.
- You said 2026 would be different. *(test variant only: it presumes)*
- Same goal as last year. Bold.
- It's dreaming season. Most of it stays a dream. *(Matti, 2021)*

Cut: "Most goals die in February." It is shaped like a statistic and has no source, which
the repo's citation rule treats as a fabricated claim.

Sub: "Fifteen minutes. Five whys. You leave with a 2027 goal poster and the one thing most
likely to wreck it." (Both numbers are true of the page as built.)

## Offer copy variants (after the last question, before results)

- A: "You've written it down. Historically, this is where it dies."
- B: "Goals are free. The doing is the product." *(the only salesy one; drop if it tests soft)*
- C: "That's step one. Step two is the part everyone skips."

Each: Race Plan / Season Plan with prices, primary "Build my 2027 plan", secondary
"Just send my poster".

## Build order (corrected — Fable: the old order shipped pages that 400)

1. **Plumbing first**: `goal_2027` in the worker's `KNOWN_SOURCES` + its test, the
   `goal_answers` / `offer_variant` payload through worker and Mission Control with size
   caps and storage (D7), `trigger_map` entry and the `goal_2027` sequence, and the signed
   poster route (D8). Nothing user-facing yet.
2. **Lead questionnaire page** (`/goals/`, GG): the forked `goal_2027` variant (D14),
   styling from the chosen hero direction, results screen with the browser poster, offer
   beneath it (D3) — **Race Plan only** until step 4 exists, with the copy variants logged.
   Consent line per D17. Analytics per below.
3. **Homepage + race-page goal strip** (D5), tests updated.
4. **Season Plan product** (D2, D15, D16): labour budget, then Matti's price, then Stripe
   product, checkout branch, reconciliation entry, copy.
5. **Season Plan added to the offer**; **prefilled plan form** (D9).
6. **Current-athlete version** (D11) in Endure, including the reader that surfaces it.
7. **Endure option** (D12), then RL and XC (D13).

## Consent and analytics

- **D17 consent line** at submit, replacing the FormSubmit sentence now on the page: the
  poster comes by email, one follow-up follows, unsubscribe is in every email, where the
  answers are stored, and how to have them deleted. Health information stays covered by the
  privacy policy link.
- **Events** (none existed in v0.1): `goal_hero_click`, `goal_start`, `goal_section`
  (with number), `goal_submit`, `goal_results_view`, `goal_poster_download`,
  `goal_offer_view` (with variant), `goal_offer_click` (with variant and plan type),
  then the existing checkout events. GA4 needs its custom fields registered by hand in the
  admin, which is Matti's step.

## Testing

- Each page: the existing Playwright pattern (fill every required answer, submit
  intercepted, email body asserted, 390px width, zero page errors).
- Worker: a labelled test lead through `fueling-lead-intake` → Mission Control → email with
  poster in Matti's inbox.
- Money path: Stripe test-mode checkout for Race Plan and Season Plan; webhook creates the
  order; no live charge.
- Endure: a test athlete's token writes `extended_profile.season_review_2026` and a draft
  goal; David's context shows it.
- Reviews: Fable adversarial review of this spec before build; sol/Fable review of each
  money-path or public-surface PR before merge.

## Not in scope

Changing coaching tiers; changing the race plan's price; any Motoren engine change.

## Corrections to v0.1 (Fable, verified)

"$249" appears in 41 files, not ~20. The offseason spec D1 refers to is untracked in the
main checkout (`git status` shows `??`) and absent from origin/main — commit or delete it.
D12 verified: Endure delivery is exactly two weeks and the pilot is email-allowlisted.
