# Plan buyer follow-up without custom changes (Nov 2026)

Research and proposal only. Nothing here is live, nothing was sent, and no
code changed with this doc.

## Why this exists

On Nov 10 2026, after reading 8 drafted thank-you notes to past TrainingPeaks
store buyers, Matti wrote:

> "I don't really think opening myself up to make constant scheduling changes
> is what I'm looking for so this needs to be rethought."

Each of those notes offered to adjust the plan ("If anything doesn't fit your
week or you want it adjusted, just reply here"). So did Wendy Butler's note.
None were sent.

On Nov 11, replying to the first version of this doc (which proposed writing a
new plan guide), Matti wrote:

> "They have a guide for the plan tho"

This version builds on that guide instead.

## Bottom line

Thank buyers and point them to the guide their plan already has. Don't offer
to fix their schedule. The guide already says "The plan owns the schedule" and
explains what to do when a week falls apart. The automated TrainingPeaks buyer
sequence drops from five emails to two:

- Day 0: thanks, plus where the guide is.
- After the race: "how did it go".

The plan's own closing note already asks for the debrief and offers the
coupon and coaching, so the emails don't have to.

## What store buyers already get

Source: `wattgod/gravel-god-training-plans` `SWARM_RUNBOOK.md` §G and §G-b,
plus a live guide read from `wattgod/gravel-god-guides`
(`athletes/mid-south-masters-12wk/`).

1. **Day 1 note, "Read This First: Your Training Guide".** It links the plan's
   own guide at `wattgod.github.io/gravel-god-guides/athletes/<slug>-<tier>-<N>wk/`
   and says: "Before your first workout, read the guide. It is the manual for
   this whole plan ... Everything you need to get this plan right is in there."
   It is a link rather than a PDF, so the guide stays current.
2. **The guide has 15 sections.** They run from training plan brief, zones and
   adaptation through weekly structure, workout execution, recovery,
   equipment, nutrition, mental prep, race week, race day and gravel skills.
   Heat, altitude and masters sections appear where they apply.
3. **The guide's "When Life Interferes" section is the support boundary,
   already written:**
   - "The plan owns the schedule."
   - Protect the key sessions first. If a week falls apart, keep one interval
     session and the long ride.
   - Never stack key sessions to catch up. "A missed session stays missed."
   - Illness: drop all intensity.

   The Recovery Protocol section adds: "Missed workout rule: Never try to make
   up a missed workout. Just move forward in the plan."
4. **Closing note on the plan's last day, "After <Race>".** It carries the race
   debrief survey, the `NEXTPLAN` 25% coupon and the coaching link. The
   runbook says TrainingPeaks' email from a store sale is unreliable, so this
   note is the main way a finisher is reached.

What I couldn't confirm:

- I read the guide note setup for the current gravel catalog. I didn't find
  road guides for Gran Fondo Strade Bianche, Tour de Brisbane or GFNY San Luis
  Potosí in `guides/roadie-labs-guides`, so those plans may host their guide
  elsewhere or may not have one.
- Older plans sold under legacy names (for example "8. Mid South - Finisher -
  Masters 50+" and "Gravel God - the MidSouth") may predate the Day 1 note.

Check a plan's Day 1 note before an email tells a buyer it's there.

## What in our emails still offers schedule changes

| Where | Line |
|---|---|
| `tp_purchase_welcome` (day 0) | "reply and tell me what it does look like, and I'll tell you what I'd change" |
| `tp_week1_check` (day 3) | "If something in it looks off, reply and I'll take a look" |
| `tp_checkin` (day 10) | "I can tell you what to move. Which day is giving you trouble?" |
| `tp_progress` (day 21) | "Tell me where you're at and I'll tell you what's coming" |
| `docs/email-voice-model.md` | example help line "reply and I'll fix it" |
| The 8 drafts plus Wendy's draft | "want it adjusted, just reply here" |

These contradict the guide's "The plan owns the schedule."

Out of scope: `purchase_welcome` and `road_purchase_welcome` are for custom,
questionnaire-built plans, which promise rebuilds. Adjustment is part of that
product.

None of the TrainingPeaks buyer emails go out yet: TP buyer ingest is off
(`TP_BUYER_INGEST_ENABLED`).

## What other plan sellers do

These sources back the approach above:

- FasCat tells buyers to drag and drop workouts or re-apply the plan
  themselves, and sends questions to a forum, not to email.
  https://fascatcoaching.com/blogs/training-tips/adjust-fascat-training-plan
- MyProCoach: "We can explain how to make changes, but we don't make those
  changes for you." Customising is listed under "What We Don't Provide".
  https://support.myprocoach.net/hc/en-us/articles/360000529751
- 80/20 Endurance offers unlimited email support while the plan runs. That is
  the model to avoid. https://www.8020endurance.com/getting-started-with-80-20-training/
- TrainingPeaks' coach blog calls it best practice to attach a plan guide to a
  day-one workout, which our plans already do.
  https://www.trainingpeaks.com/coach-blog/how-to-add-value-to-your-training-plans/
  The same blog notes "most athletes will never contact you".
  https://www.trainingpeaks.com/coach-blog/selling-training-plans-fits-within-coaching-business/
- On TrainingPeaks, only Premium accounts can move future workouts, and a
  plan's dates change by removing and re-applying it.
  https://help.trainingpeaks.com/hc/en-us/articles/204072164-How-do-I-move-a-workout
  and https://help.trainingpeaks.com/hc/en-us/articles/204071974-How-do-I-apply-my-plan
- General digital product practice: send the thank-you right away, keep one
  ask per email, and ask for feedback only after the product has been used.
  https://kit.com/resources/blog/customer-onboarding and
  https://campaignmonitor.com/resources/knowledge-base/do-ctas-help-to-improve-email-response-rates

## Recommendations

1. **Point every buyer email to the guide.** Name it the way the plan does: the
   "Read This First" note on day one. Name "When Life Interferes" as the place
   for schedule trouble.
2. **Two emails for TrainingPeaks store buyers, not five.**
   - Day 0: thanks, plus where the guide is, plus one easy question about their race.
   - After the race, or about 3 days after the plan ends with no race: "how did it go".
   - Drop `tp_week1_check`, `tp_checkin` and `tp_progress` for the
     `trainingpeaks_store` source.
3. **Leave the survey, coupon and coaching pitch to the "After <Race>" note.**
   The post-race email shouldn't repeat them. One coaching line in Matti's
   reply, when someone answers, is enough.
4. **Answer change requests from a short template.** Point to "When Life
   Interferes", say once that store plans aren't customized, and give coaching
   one line. Any repeat question goes into the guide generator so the next
   buyer gets the answer there.
5. **Update `docs/email-voice-model.md`** so the help line for plan buyers
   points to the guide or to coaching, never "reply and I'll fix it".

## Proposed copy

Same voice rules as `docs/email-voice-model.md`: 25 to 70 words, opens on
them, one plain help line, one question, sign-off "Matti". This is draft copy
for Matti's edit. Before any of it ships, it still needs the voice grounding
and the full no-ai-slop pass in `docs/AI_WRITING_POLICY.md`.

### Day 0 (race plan)

> Hi {first},
>
> Thanks for grabbing my {race} plan. {One line on what makes the race hard.}
> Start with the Read This First note on day one. The guide it links covers
> everything, including what to do when a week falls apart.
>
> Is this your first {race}?
>
> Matti

### Day 0 (no race)

> Hi {first},
>
> Thanks for picking up {plan}. Start with the Read This First note on day
> one. The guide it links is the manual for the whole plan.
>
> What are you building toward?
>
> Matti

### After the race

> Hi {first},
>
> Thanks for racing {race} on my plan. I hope the day went well.
>
> How did it go?
>
> Matti

### Reply when a buyer asks for changes

> Hi {first},
>
> The When Life Interferes part of your guide covers this: {its rule in one
> sentence}. Store plans aren't customized, so that's the move I'd make. If you
> want someone adjusting it around your week, that's my coaching.
>
> Matti

## The 9 hand-written notes, rewritten

The same people as the Nov 10 drafts. The adjust offer is gone, and the notes
for upcoming races point to the guide instead. None have been sent.

Race dates were checked Nov 10 2026:

- Leuven Legacy Gravel was held Oct 18 2026.
- SBT GRVL was held Jun 28 2026.
- Mid South 2026 was held in mid-March.
- GFNY San Luis Potosí is in December 2026.
- Gran Fondo Strade Bianche and Mid South 2027 are in spring 2027.

Before sending, confirm each plan has the Read This First note. If a plan
doesn't, drop the guide sentence from that note rather than offering help.

Race still ahead:

- **Wendy Butler (Tour de Brisbane):** her draft drops the adjust line and adds
  the guide sentence.
- **William Tietz (Gran Fondo Strade Bianche):** Thanks for grabbing my Strade
  Bianche plan. That steep finish up into Siena hurts once the gravel has taken
  its toll, so the long tempo days are the ones to protect. Start with the Read
  This First note on day one, the guide covers everything. When are you
  planning to start it?
- **Erika Rix (Mid South):** Thanks for grabbing my Mid South plan. That
  Oklahoma red dirt rewards patience and steady fueling more than big watts.
  Start with the Read This First note on day one, the guide covers everything.
  Is this your first Mid South?
- **Alejandra Guerra (GFNY San Luis Potosí):** Thanks for picking up my GFNY
  San Luis Potosí plan. You should be deep in the build now with December
  getting close, and the race week part of the guide is worth a reread. How's
  training feeling?
- **Leonardo Cano (A Year in Gravel):** Thanks for picking up A Year in Gravel.
  A full year is a real commitment and I'm glad you're doing it with my plan.
  What are you building toward?

Race passed (no guide line, since the plan is over):

- **Greg Patychuk (Leuven Legacy Gravel):** Thanks for using my Leuven Legacy
  Gravel plan. I hope the race went well, Belgian gravel is no joke. How did
  the day go?
- **Brendan Train (Crit King):** Thanks for grabbing my Crit King plan back in
  March. I hope it gave you some extra snap in the finishes this season. How
  did the season go?
- **Jamie Keeley (several plans):** Thanks for sticking with my plans this
  year, from the build and Gravel Grit last winter through SBT GRVL. I really
  appreciate it. How did Steamboat go?
- **John Shears (Mid South):** Thanks for using my Mid South plan this spring.
  I hope the red dirt treated you well. How did the race go?

## Code changes to make once Matti agrees

1. Let a step's `source_overrides` entry carry `skip: True` in
   `mission_control/services/sequence_engine.py`. A skipped step advances the
   way a failed race premise already does, with the same audit log entry.
2. In `mission_control/sequences/post_purchase.py`, set
   `trainingpeaks_store: {"skip": True}` on steps 1 to 3.
3. Rewrite `tp_purchase_welcome` and `tp_nps` to the copy above, removing the
   fix-it offers. The post-race email already waits for the race
   (`race_premise`) or the plan's end (`delay_from_completion_days`).
4. Update `mission_control/tests/test_tp_store_sales.py`, which asserts the
   five TrainingPeaks templates and subjects.
5. Amend the help-line example in `docs/email-voice-model.md`.

## Open questions for Matti

- Do road plans (Roadie Labs) carry the same Read This First guide note? Their
  guides weren't where I looked.
- Should the custom-plan welcome emails keep promising rebuilds?
