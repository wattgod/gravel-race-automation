# Receipts: real social proof for Gravel God — 2026-09-28

Spec author: Claude (Opus 5.5), adversarially reviewed by Claude (Fable 5.1), verdict
SHIP-WITH-AMENDMENTS, all 12 amendments folded in. Implementer: Claude subagents in
origin/main worktrees. Review and merge: Claude → Matti. Status: **APPROVED 2026-09-28** (decisions in §12).

This repo is PUBLIC. This spec names no athletes, customers or prospects. The athlete
evidence inventory, consent records and review notes live in private repos (§6.2).
Research with citations: [`receipts-social-proof-2026-research.md`](receipts-social-proof-2026-research.md).
Nothing here is legal advice.

## 1. Context (verified 2026-09-28, do not re-litigate)

**Trigger.** On 2026-09-24 a prospective buyer of a 35-week custom plan asked where
to find reviews. He had checked the TrainingPeaks coach profile and searched the web
and found nothing. He has not bought.

**Off-site, a prospect finds nothing.**
- No Trustpilot, Google, Reddit or forum reviews.
- TrainingPeaks has 15 ratings (average 4.8) on 9 legacy plans and none on the 1,838
  current plans. TP draws stars only when `ratingCount > 2`, so 13 of the 15 are
  invisible. The coach profile has no reviews section and still reads "Road Cycling
  Coach", Longmont. (One earlier count found 18 ratings on 10 plans; re-fetch before
  quoting.)
- AI search summaries already quote the on-site placeholders below as real reviews.

**On-site, the proof is placeholder text, and it sits at the decision points.**

| Where | What | Live | Owner of the fix |
|---|---|---|---|
| `wordpress/generate_about.py:195-280`, JS `:770-829` | 50 placeholder testimonials in an auto-rotating carousel (no pause for keyboard/touch) | /about/ | Claude PR |
| `wordpress/generate_training_plans.py:321-349` | 3 placeholder testimonials ("Don't Take My Word For It.") | /products/training-plans/ | Claude PR |
| `web/training-plans-questionnaire.html:1056-1076` (WP page 5017) | 2 of the same 3, directly above "Submit & Pay" | /questionnaire/ | Claude PR + Matti pastes to WP |
| `web/training-plans.html:1181-1200` | Same 3, legacy paste-in | not live | Claude PR (delete) |
| `wordpress/ab_experiments.py:94-118` | Scarcity variants: "Limited spots.", "20 athletes/month.", "Next window: April." | /about/ via A/B JS | Claude PR |
| `wordpress/generate_about.py:144,157-158`, `generate_consulting.py:242` | "100+ athletes coached", "1,000+ plans sold", "12 years at TrainingPeaks" | /about/, /consulting/ | Matti confirms wording, Claude PR |
| `scripts/generate_index.py:525-531`, `web/jsonld/*.jsonld` | Hard-coded `aggregateRating` `ratingCount "14"` (latent) | not live | Claude PR (delete) |
| Elementor page, not in any repo | "4.7 Stars from 100+ Reviews" and an unsourced named quote | /popular-training-plans/ | **Matti, WP admin** |
| Elementor page, not in any repo | Legacy custom-plan page, self-canonical, off-brand | /custom-training-plans/ | **Matti, WP admin** (301 to /products/training-plans/) |
| `road-race-automation` `wordpress/generate_about.py:195-254,275`, `generate_training_plans.py:336-369` | The same 53, captioned "Gravel God athletes" | roadielabs.com /about/, /training-plans/ | Claude PR (Roadie) |

Provenance: Claude sessions wrote the 55 in February 2026 (`cfd9cf09`, `6939db7c`,
co-authored-by Claude). Several of the 50 credit the race database and prep kits,
which launched 3 days to 7 weeks before the quotes were written. The only real
testimonials this site ever carried were 5 full-name quotes on the old WordPress
homepage from 2021 to 2024 (Wayback), dropped in the rebuild. Three repo records call
the placeholders real and need correcting:
- `.claude/skills/scoring-and-veracity/SKILL.md:74-82`
- the comment at `wordpress/generate_homepage.py:204`
- the `_note` in `gravel-god-training-plans/db/testimonials.json`

**Funnel (GA4 property 353120093, 2026-06-30 to 2026-09-27).**
- Coaching: /coaching/ 90 sessions → /coaching/apply/ 38 → 4 `coaching_apply_started`
  (real path only; preview pages excluded) → 2 `apply_form_submitted` (1 before and 1
  after the 07-26 consent gate).
- Custom plan: /questionnaire/ 113 → `tp_form_start` 26 users → 6 submits → 4 live
  purchases.
- Consulting: 17 → 1 purchase.
- /coaching/ contains no coach name, no image, no credential, no outcome and no sample
  of work.

**Real proof exists but has never been collected.**
- Dozens of paying coaching clients since 2023-10 (18 active in the last 90 days).
- Custom-plan and consult buyers.
- Publicly checkable results, including an overall win in a 111-finisher 125-mile
  gravel race, 5th in age group at Unbound 200, and an Elite national TT placing.
- Consent on file: zero.
- There is no collection loop. `gg_nps_scores` has 0 rows, and the post-race
  touchpoint became a reminder to Matti on 09-23 (#284).

**Legal (see research §1).**
- 16 CFR 465.2(a) prohibits a business from **writing or creating** a testimonial
  that misrepresents that the reviewer exists or had the experience. 465.2(a) is the
  operative clause here, because the business's own tooling wrote these.
- The FTC Q&A: a business that puts testimonials on its own site "is disseminating
  them and is not merely 'hosting' them".
- The civil penalty ceiling is $53,088 per violation (2025 adjustment). The FTC sent
  its first warning letters in Dec 2025.
- Also relevant: Endorsement Guides 255.1(b) (edits), 255.2(b) (generally expected
  results) and 255.5 (material connections).
- Canada Competition Act s.74.02 requires written approval of the testimonial.
- Realistic first contact for a solo coach who removes promptly is a warning letter,
  but removal is not optional.

**Standing rulings this spec respects.**
- 2026-07-18: no testimonials on /coaching/ or the homepage. /coaching/ ("the
  Dossier") is a still document with no entrance animations. Enforced by
  `tests/test_coaching.py` `test_no_testimonials` (counts `<blockquote>`),
  `test_no_animation_on_tiers` and `test_no_bounce_easing`.
- 2026-09-23: never commit customer or lead names, emails or phones to this public repo.
- 2026-09-23: no automated follow-up emails to plan athletes; `[GG] Reminder` to Matti
  instead.
- 2026-09-24: a public first-read sample on /coaching/ is allowed, but only from a
  real, consented read.
- `docs/email-conversion-principles.md` is SUPERSEDED (2026-07-16) and email-scoped.
  Its testimonial ban does not govern web pages. Proof does not enter reply copy
  either way: the artifact is the proof in email.

## 2. Scope: what proof can and can't fix

Proof here is **hygiene, off-site presence and a credible coach identity**. It is not
the main conversion lever. It addresses:
- the off-site search a careful buyer does before paying;
- /about/, the "check the coach" page (112 sessions in 90 days), which is currently
  the most fabricated page;
- a $1,200/month page that does not name its coach.

Out of scope, to be ticketed separately:
- apply-page friction (38 sessions → 4 starts);
- questionnaire start → submit (26 → 6, with 13 explicit abandons).

At 2 applications a quarter, no funnel ratio will be readable within this project.
**The primary success metric is the proof inventory (§9).**

Receipts supplement the artifact proof the site already shows (sample build week,
first read, calendar preview). They don't replace it.

## 3. Principles (non-negotiable)

1. **Empty beats fake.** Nothing renders unless it traces to a real person, a source,
   and written approval of the exact text. The fallback is the brand's existing honest
   empty state, or nothing.
2. **Receipts, not reviews.** Results link to a third-party page (official timing, a
   TP rating, a Trustpilot review). The link is the proof; the quote is colour.
3. **Representative by process.** Ask everyone who meets an objective criterion at
   fixed triggers, never by expected sentiment. Publish a count that includes athletes
   who opted out: "N athletes coached since 2023-10; those who chose not to be named
   appear only in this count". No "typical results" claim until the data supports one
   (§6.3, G4).
4. **Disclose connections inline.** Standard copy: "coached at no charge", "friend and
   training partner of the coach", "colleague of the coach at TrainingPeaks",
   "athlete's business partner". In video it is on screen and spoken.
5. **Performance and results only; never health data in public.** FTP from
   athlete-confirmed tests, placings and times. No HR, HRV, weight, W/kg (it needs
   weight), medication or medical context.
6. **Motion reveals, then rests.** Graphics are drawn from the same record as the text,
   reveal in stages, and end on a static labelled frame. `prefers-reduced-motion`
   shows the final frame only. No Lottie for data. /coaching/ stays still.
7. **Matti writes every ask.** Claude prepares facts and prompts. No generated text
   goes to an athlete. Two long-tenure athletes flagged AI-drafted reviews on
   2026-08-22.
8. **Private evidence, public HTML.** Evidence pointers, consent records and approved
   text live in a private repo. The public repos hold schema, loader, tests and
   synthetic fixtures only. The deployed HTML is the only public copy.

## 4. Phase 0: takedown (day 0)

1. **Claude PR-1 (this repo):** remove every row marked Claude PR in §1, including:
   - the /about/ carousel section and its JS;
   - the A/B `coaching_scarcity` experiment, then regenerate `ab/experiments.json`;
   - the aggregateRating templates.

   Replace the stats line with wording Matti confirms (§12.6), or drop it. Leave the
   sections out rather than substituting composites or paraphrases.
2. **Claude PR-2 (road-race-automation):** the same for roadielabs.com.
3. **Matti, WP admin:**
   - edit /popular-training-plans/ to remove the rating claim and the unsourced quote;
   - 301 /custom-training-plans/ → /products/training-plans/;
   - paste the updated questionnaire HTML into page 5017;
   - run `push_wordpress.py` for both brands.
4. **Guard: `tests/test_no_unsourced_proof.py`,** run over generated output in both
   repos. It fails on:
   - any element with a legacy testimonial class (`gg-about-testimonial`,
     `gg-tp-testimonial`, `gg-coach-testimonial`, `gg-consult-testimonial`,
     `rl-about-testimonial`);
   - `aggregateRating`;
   - the strings "Stars from", "athletes/month" or "Next window";
   - a person-attributed `<cite>` outside the receipts component.

   The receipts component emits `data-receipt-id`, which must resolve in the ledger at
   build time. Scope is deliberately narrow: legitimate `<blockquote>` uses (gravel
   weekly, race pages) stay allowed.
5. **Correct the record:** the veracity skill, the homepage comment, and the
   gravel-god-training-plans `_note` (it says the 53 were purged; they were not).
6. **Removal log:** a private, dated log in gravel-god-training-plans (`docs/proof/`)
   covering what came down, where, and when. Counsel only if paid ads ever used the
   quotes. No public statement without counsel.
7. **Reply to the prospect, same day.** Matti writes it; it is not gated on athlete
   consent. Facts to include:
   - reviews have never been collected systematically;
   - the legacy TP ratings, with a link;
   - an offer of a 10-minute call with a current athlete (disclose any comped status);
   - who the custom plan is not for;
   - the 7-day refund on the product page.

   Public result links follow once one or two athletes agree to be named as coached.

## 5. Phase 1: minimum lovable version (weeks 1–2, then stop and read)

1. **Coach identity block** on /coaching/ and /about/:
   - a real photograph of Matti (rights confirmed);
   - his name;
   - a two-line credential with verified wording;
   - "I read every application and write every review myself".

   This is not a testimonial and it is still, so it fits the 07-18 ruling without
   amendment. **Coach receipts evidence list** (Matti supplies, Claude verifies):
   TrainingPeaks tenure wording, Matti's own race results with official links, and
   the photograph and its rights holder.
2. **TrainingPeaks profile:** headline (gravel, not road), location, and a bio in the
   low-hype register. Matti edits it in TP.
3. **Consent form** (Google Form owned by gravelgodcoaching; separate from the
   coaching agreement, per `athlete-custom-training-plan-pipeline`
   `docs/legal/COACHING_LEGAL_REVIEW_PACKET.md:175`). Fields:
   - identity tier: full name / first name + last initial / first name + age group /
     count only;
   - one tick per asset: quote, photo (plus copyright owner), result links,
     athlete-confirmed test numbers, a chart of their data, voice/video clip;
   - channels: gravelgodcycling.com / roadielabs.com / social / email / TP;
   - duration: 3 years;
   - approval of the exact final text and of the exact render;
   - material-connection declaration;
   - parent signature if under 18;
   - withdrawal, including a plain statement of what cannot be recalled (§8).
4. **Batch-1 asks** go to everyone who meets an objective criterion: all coaching
   clients active in the last 90 days, plus every 2026 custom-plan and consult buyer.
   - Claude prepares a private one-page fact sheet per athlete: the pre-filled facts
     to confirm (race, placing, official link, test numbers) and seven prompts, e.g.
     "what almost stopped you", "what changed, in numbers, at which race", "what was
     hard or didn't work", "who shouldn't hire me".
   - Matti writes and sends each ask in his own words. A 10-minute call is offered as
     an alternative; the transcript excerpt goes back to the athlete for approval.
   - Matti sends one reminder at day 7, by hand, then stops. Nobody is dropped for
     expected sentiment.
5. **/athletes/ v0** with whatever has been approved, even three:
   - receipt cards;
   - the opt-out-inclusive count line;
   - the verification line: "Every story here is from a coached athlete who approved
     the wording in writing. Results link to official timing."
6. **TP final-week rating ask** on the top-20 selling plans only. It is one line in the
   final-week note, shown to every buyer. Uses the gravel-god-training-plans TP
   tooling and needs Matti's logged-in TP tab.

**Gate G:** move to Phase 2 at **≥5 approved stories**, not on a calendar date.

## 6. Phase 2: receipts at decision points, plus motion (gated on G)

### 6.1 Placements

| Page | Proof | Register |
|---|---|---|
| /questionnaire/ (Submit & Pay) | Up to 2 receipt cards from plan or custom-plan buyers, else only the legacy TP ratings line | still |
| /products/training-plans/ | Receipt cards from plan buyers, else nothing | still or light reveal |
| /coaching/ | Identity block (Phase 1), one consented first-read excerpt as an "Exhibit" (allowed 09-24), and a still outcomes table linking to /athletes/ (**needs the §12.2 amendment**) | still; add a test for no `data-animate` or `@keyframes` |
| /about/ | Identity block, 2–3 receipts, link to /athletes/ | reveal allowed |
| /consulting/ | One consented, redacted sample plan of action | still |
| /athletes/ | All approved receipts, the count line, and case studies with G1–G3/G5 | motion allowed |
| roadielabs.com | Identity block, TP ratings line, and "the coach's gravel athletes →" linking to GG /athletes/ (per-channel consent). No borrowed quote wall | still |

- Show the Trustpilot link only once there are ≥5 reviews.
- Link a TP rating only where the plan has ≥3 ratings, labelled "on legacy Gravel God
  plans" until a current plan is rated.
- "Talk to an athlete": a roster of consenting references. The prospect asks and
  Matti makes an email intro. No contact details are ever published.

### 6.2 Data architecture

- **Ledger (private):** `gravel-god-training-plans/db/testimonials.json`, upgraded to
  schema `gg-receipts-v2`. Per entry:
  - `id`, `identity_tier`, `display_name`, `age_group`, `hours_per_week`;
  - `product` (tp_plan | custom_plan | coaching | consult), `coached_since`;
  - `results[]`: `event`, `date`, `placing`, `field`, `time`, `official_url`;
  - `quote` (exact approved text), `quote_approved_at`, `render_approved_at`;
  - `material_connection` (enum + display copy), `channels[]`;
  - `consent_id` (Form response id), `consent_expires`, `withdrawn_at`;
  - `source_ref`, private only and never exported.

  `headline` is dropped: any headline must be the athlete's approved words or
  unquoted editorial text.
- **Build-time read:** generators read `GG_RECEIPTS_PATH` (Matti's local private
  checkout; deploys are manual). If it is unset (CI), they fall back to
  `tests/fixtures/receipts_synthetic.json`, which holds invented, obviously fake names
  such as "Test Rider A" and never renders on production builds.
- **This repo holds:** `wordpress/receipts_data.py` (loader and validator),
  `wordpress/receipts_components.py`, schema docs, and synthetic fixtures. **No
  `data/*.json` holds real people.**
- **Retire** the `data/testimonials.json` mirror (its allow-list includes
  `source_ref`). Point `generate_training_plan_pages.py:load_testimonials` at the
  loader. Change `tests/test_training_plan_reviews.py:83-90` deliberately in the same
  PR.
- **The validator rejects:**
  - a missing `consent_id`, `quote_approved_at` or `render_approved_at`;
  - an expired or withdrawn entry;
  - any health field (`hr`, `hrv`, `weight`, `wkg`, `med*`);
  - a result without an `official_url`;
  - a channel not in the entry's `channels`.
- The same rules apply to road-race-automation, reading the same private ledger with
  `channel = roadie`.

### 6.3 Motion and graphics workstream

| ID | Graphic | Rule | Where | Status |
|---|---|---|---|---|
| G1 | Result receipt card: event, date, placing / field, time, official link, approved quote or nothing, disclosure line | Plain typographic reveal. **No "stamp" or seal**: it implies third-party verification the site didn't do | /athletes/, /questionnaire/, /products/training-plans/, /about/ (still version on /coaching/) | Phase 2 |
| G2 | Season timeline: every consented, **publicly checkable** result as a dot (position ÷ finishers), each dot linking to official timing, bad results included | Caption "public results only"; needs field size | /athletes/ case studies | Phase 2 |
| G3 | Before/after test | Only when both tests are athlete-confirmed, same protocol, meter named. Axis from 0 W or the absolute delta printed alongside | case studies | Phase 2 |
| G5 | Modelled fitness (CTL, 42-day) build | **Never on its own** (it's an input the coach controls). Only inside a case study, next to the race result it led to, labelled as a model | case studies | Phase 2 |
| G7 | Social cards (1080×1350, `social_engine`) and OG images (PIL) | Same record, same numbers | social, share | Phase 2 |
| G4 | Cohort outcome chart | **Deferred.** At n≈12 the values are mostly coach-set mFTP, windows and meters differ, top racers are flat, and W/kg breaks principle 5. Revisit at ≥20 athletes with same-protocol, athlete-confirmed tests, or use a public race-result distribution instead | — | Deferred |
| G6 | Vertical case-study videos (9:16, 30–45 s) | **Deferred** and merged with the Substack→Shorts pipeline (character kit + `assemble_video.py`) once ≥5 stories exist and the Reel pilot works. Quotes on screen as text; never a synthetic voice reading an athlete's words; disclosure on screen and spoken by Matti's real voice. The Gravel God character may open or close a video, never stand in for an athlete | — | Deferred |

Reuse before building:
- `wordpress/guide_infographics.py`: `render_power_duration:2018`,
  `render_before_after:2185` and `render_pmc_chart:1403`, parameterized with real data
  (they are illustrative today);
- `wordpress/scroll_animations.py` (tested, reduced-motion-safe);
- `scripts/social_engine.py` card renderer;
- the PIL OG generators.

**Process for every graphic:** paper storyboard → Matti signs off on the storyboard
before any code → data contract → build → acceptance tests → Matti approves → the
athlete approves the exact render.

**Acceptance criteria (all graphics):**
1. A test asserts every number in the rendered SVG/PNG equals the ledger record.
2. The `prefers-reduced-motion: reduce` render is byte-identical to the final frame
   (snapshot test).
3. Axes start at zero, or the absolute delta is printed next to the chart. No overshoot
   or bounce easing; brand motion tokens only; `transform`/`opacity` only.
4. Dimensions are reserved (CLS 0). A per-page byte budget test, like the homepage's,
   covers /athletes/ and /about/. `scripts/cwv_monitor.py` adds /about/ and /athletes/.
5. Anything moving longer than 5 s has a pause control (WCAG 2.2.2). Scroll-driven
   animation only inside `@supports (animation-timeline: scroll())`, with an
   IntersectionObserver fallback.
6. /coaching/ keeps a still-document test: no `data-animate`, no `@keyframes`.
7. "A chart of my data" is its own consent asset, and the athlete has approved the
   exact render.
8. Every chart carries its source and date range, its units, and a link to the
   official result or the data's origin.

The homepage gets nothing: it is already over its 170 KB test limit
(`tests/test_homepage_generator.py:782-791`, red on main).

## 7. Ongoing collection triggers

These are `[GG] Reminder` emails to Matti from the pipeline (`webhook/app.py` reminder
path, #284). They never go to athletes. Each includes the fact sheet and the consent
form link:
- A race + 3 days, any outcome;
- coaching renewal;
- custom-plan race date + 3 days;
- cancellation (exit note).

## 8. Withdrawal runbook (7-day target)

1. Set `withdrawn_at` in the ledger, rebuild, then run `push_wordpress.py` for every
   channel the entry used.
2. Regenerate and redeploy OG images; purge the CDN cache.
3. Social posts: delete them. Say plainly in the consent form that reposts and screenshots
   cannot be recalled.
4. Videos: unlist or delete.
5. Wayback: submit an exclusion request if the athlete asks.
6. AI-search caches cannot be purged. The consent form says so up front.
7. Log it in the private removal log.

## 9. Measurement

- **Primary, the proof inventory, read weekly.** Approved stories by product; TP
  ratings on the top-20 plans; Trustpilot count and average; results with official
  links.
- **Secondary, directional only.**
  - Make `apply_form_submitted` and `tp_form_submit` GA4 key events.
  - Add `proof_link_click` (param: `timing` | `tp` | `trustpilot`),
    `reference_request` and `receipts_view`.
  - Definitions: sessions, not users. Exclude preview `.html` traffic. Epochs are the
    2026-07-26 consent gate and the 2026-09-11 `cta_name` change; never compare across
    them without saying so.
- **Qualitative.** Add an optional "What made you decide?" field to the coaching apply
  form and the questionnaire.

## 10. Who does what

| Task | Claude | Matti | Athlete |
|---|---|---|---|
| Code, tests, PRs, fact sheets, removal log draft | does | reviews/merges | — |
| WP-admin edits, deploys, TP profile, Trustpilot account | prepares steps | does | — |
| Writing and sending every ask and reminder | fact sheet only | does | — |
| Quote wording | — | proposes trims | approves exact text |
| Graphics | builds | approves storyboard + render | approves exact render |
| Reply to the prospect | facts list | writes + sends | — |

## 11. Implementation: PR sequence

| PR | Repo | Content | Done when |
|---|---|---|---|
| PR-1 | gravel-race-automation | Phase 0 takedown, `test_no_unsourced_proof.py`, record corrections | Live /about/, /products/training-plans/ and /questionnaire/ show 0 unsourced quotes; the guard fails on a planted regression |
| PR-2 | road-race-automation | Same for Roadie | Live roadielabs.com shows none of the 53 |
| PR-3 | this spec | This document + research appendix | Matti's §12 decisions recorded |
| PR-4 | gravel-race-automation + gravel-god-training-plans | `gg-receipts-v2` schema, `receipts_data.py` loader/validator, synthetic fixtures, `GG_RECEIPTS_PATH`, retire the public mirror | The validator rejects each §6.2 failure case in tests; a CI build with fixtures renders; the production build reads the private path |
| PR-5 | gravel-race-automation | Identity block, /athletes/ v0, receipt card (G1 still), count line | Renders the honest empty state at 0 approvals and cards at ≥1; the still-document test passes on /coaching/ |
| PR-6 | pipeline | Proof `[GG] Reminder` triggers (§7) | Each trigger fires once per athlete per event, to Matti only |
| PR-7 (gated on G) | gravel-race-automation | Placements §6.1, G1 reveal, G2, G3, G5 in case studies, G7 cards | The 8 acceptance criteria in §6.3 pass |

## 12. Decisions (recorded 2026-09-28, Matti approved all eight)

1. **Takedown today: approved.** Gravel God in PR-1; Roadie and XC Ski Labs in PR-2.
2. **07-18 ruling amended for one item:** a still outcomes table on /coaching/ linking to
   /athletes/. The identity block needs no amendment, and the first-read exhibit was
   already allowed on 09-24.
3. **Text messages are allowed as a quote source,** per athlete, with that athlete's
   consent. The "texts are off-limits" rule in the review sheets is lifted for this purpose only.
4. **Photograph:** a real photo Matti or a friend took, so the rights are clear. Race
   photographers' images only with a licence. Matti supplies the file (open item).
5. **Credentials:** publish only what can be checked. Matti's own results need an
   official results link, e.g. the unverified "Unbound 2026 podium". TrainingPeaks
   tenure wording stays as Matti's own bio line; Matti confirms the exact wording
   (open item).
6. **Stats line: "100+ athletes coached" and "1,000+ plans sold" are dropped,** because
   neither can be checked. PR-1 and PR-2 remove them on all three brands.
7. **Roadie:** identity block, TP ratings line, and a link to the Gravel God /athletes/
   page. No borrowed quotes.
8. **Google Business Profile:** only with a real, recurring in-person offer. Skipped for now.

**Also resolved:** Matti shared the coaching-praise sheet ("Utholdening", tabs "Trener
Ros", "Ros", "Ros 24"). It adds verbatim athlete material, including an unprompted
offer to write a review and a 2020 message giving permission to use a quote. It is
logged in the private evidence inventory. Friends' and teammates' remarks about
Matti's own riding are not coaching proof and are excluded.

## 13. Risks

- **Asking right after athletes noticed AI-drafted reviews.** Mitigated by principle 7:
  Matti writes; nobody is skipped.
- **Selection bias.** Mitigated by the opt-out-inclusive count, objective batch
  criteria, and bad results staying on the timeline.
- **Minors.** Parent signature. Never cite team-name results that link a minor to the
  brand.
- **A sparse /athletes/ page** reads weak. Keep the honest empty state and the count
  line; don't pad.
- **Matti's time.** The MLV is about 10 hours over two weeks, and Phase 2 waits for
  Gate G.
