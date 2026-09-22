# 2027 Goals Funnel — spec v0.1 (2026-09-22)

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
| D3 | Does the offer gate the results? | **No.** The offer appears after the last question and before the results screen, but "Just send my poster" always works, and the poster is emailed either way. | Holding results hostage is a bait-and-switch and poisons the list. |
| D4 | Where the questionnaire lives | `/goals/` (GG), `/goals/` (RL), `/goals/` (XC) — a standalone page, `index, follow` once live. Homepage hero links to it. | The homepage stays fast; the questionnaire keeps save/resume and its own analytics. |
| D5 | Homepage change | A **seasonal hero slot**: Oct 1 – Jan 31 the goal hero leads, the race search sits directly beneath it (still above the fold on desktop); the rest of the year the race-database hero returns. Chosen at build time by date. | "More dynamic content above the fold" without losing the race search, which is most of the traffic. |
| D6 | What's asked | The "So. 2026." core **minus section 7 (hours, life constraints)** and minus "what do you want from me". Those move to the plan form. | Matti: "I don't think we need to put in things like 7 just yet." Leads aren't clients yet. |
| D7 | Lead plumbing | POST to the existing `fueling-lead-intake` worker with a new source `goal_2027` (added to `KNOWN_SOURCES` + test) → Mission Control `trigger_map` → new `goal_2027` sequence. Replaces FormSubmit for the public form. | Repo rule: every email form posts to its Cloudflare worker. FormSubmit keeps a copy for 30 days and bypasses the lead system. |
| D8 | The poster | Rendered **server-side** by Mission Control (Pillow, reusing `scripts/media_templates`) when the lead lands; emailed as an image link + attachment; also drawn in the browser on the results page for instant download. Two styles (dark, paper) — Matti picks one from the canvas. | Email needs a hosted image; the browser copy makes the results screen feel immediate. |
| D9 | The shorter plan form | A new page, not an edit to the Elementor `/questionnaire/` (its live widget has drifted from the repo). It reads the goal answers from a signed token in the link, shows them "already on file · edit", and asks only what's missing (other races, days, equipment, health, strength, delivery). Posts to the same Railway `create-checkout`. | Lowest risk to the money path that works today. |
| D10 | Copy tests | Offer copy rotates across 3 variants (A/B/C on the canvas), logged per lead. Treat as directional: homepage traffic is too low for a significant A/B result (repo CLAUDE.md). | Matti wants many variants; the numbers won't settle it quickly, so read replies and purchases too. |
| D11 | Current athletes | A separate private link per athlete (signed token), modelled on Endure's `/api/delivery/consult` endpoint: answers → `athletes.extended_profile.season_review_2026` (raw) + draft `goals` / `goal_actions` + `plan_season_reviews` (needs the one-per-plan limit relaxed). Questions aligned to Endure's "limiter interrogation" (endure-loop-2026 §3). | Endure already has the shapes; David and the coach UI read them. |
| D12 | Endure option | Offered in the plan form as "Endure (beta)" **only after** the purchased-plan delivery path has its production proof; today Endure can show only the first two weeks of a Motoren plan. Until then, TrainingPeaks. | Promising a full season in Endure today would be false. |
| D13 | Brands | GG first. RL and XC after GG runs a full cycle (lead → poster → offer → purchase) in production. Each gets its own headline in its brand voice. | One funnel proven before three. |

## Headline slate (Matti's register: flat, deadpan, no commands, ≤60 chars)

- Most goals die in February.
- You said 2026 would be different.
- Same goal as last year. Bold.
- It's dreaming season. Most of it stays a dream. *(Matti, 2021)*

Sub: "Fifteen minutes. Five whys. You leave with a 2027 goal poster and the one thing most
likely to wreck it."

## Offer copy variants (after the last question, before results)

- A: "You've written it down. Historically, this is where it dies."
- B: "Goals are free. The doing is the product."
- C: "That's step one. Step two is the part everyone skips."

Each: Race Plan / Season Plan with prices, primary "Build my 2027 plan", secondary
"Just send my poster".

## Build order

1. **Lead questionnaire page** (`/goals/`, GG): variant `matti` minus D6, Manual-for-Speed
   styling from the chosen hero direction, worker submission (D7), results screen with
   browser poster, offer interstitial (D3, D10).
2. **Mission Control**: `goal_2027` source → sequence: results email with poster (D8),
   one follow-up. Doctrine note: the pitch lives in the page, not the emails.
3. **Homepage seasonal hero** (D5) + tests updated (`tests/test_homepage_generator.py`
   pins the current h1).
4. **Season Plan product** (D2): Stripe product/price, `webhook/app.py` checkout branch,
   copy on /training-plans/. Matti sets price first.
5. **Prefilled plan form** (D9).
6. **Current-athlete version** (D11) in Endure.
7. **Endure option** (D12), then RL and XC (D13).

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
