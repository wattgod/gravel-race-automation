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

## Bottom line

Thank TrainingPeaks store buyers, but stop offering to fix their schedule.
Instead, give them a self-serve guide for running a plan on their own. Cut the
automated buyer sequence from five emails to two: a thank-you on day 0 and a
"how did it go" after the race. The only paid way to get the plan bent around
their life is coaching.

## What in the system offers schedule changes today

| Where | Line | Problem |
|---|---|---|
| `tp_purchase_welcome` (day 0) | "reply and tell me what it does look like, and I'll tell you what I'd change" | Invites a custom rework on day one |
| `tp_week1_check` (day 3) | "If something in it looks off, reply and I'll take a look" | Open-ended support offer |
| `tp_checkin` (day 10) | "I can tell you what to move. Which day is giving you trouble?" | Asks for a scheduling problem |
| `tp_progress` (day 21) | "Tell me where you're at and I'll tell you what's coming" | Turns plan reading into email work |
| `docs/email-voice-model.md` | example help line "reply and I'll fix it" | The voice rule itself suggests fixing |
| The 8 drafts plus Wendy's draft | "want it adjusted, just reply here" | Same offer, sent by hand |

`tp_nps` (the post-plan email) is already close to right: "If you want the next
block built around you week by week, that's what my coaching is."

Out of scope: `purchase_welcome` and `road_purchase_welcome` are for custom,
questionnaire-built plans, which promise rebuilds ("The plan gets rebuilt
around it"). Adjustment is part of that product. Matti should still decide
whether he wants that promise.

None of the TrainingPeaks buyer emails go out yet: TP buyer ingest is off
(`TP_BUYER_INGEST_ENABLED`). The sequence can be fixed before it is switched on.

## What other plan sellers do

1. **Put the fix in the buyer's hands, not the coach's.**
   - FasCat tells buyers to drag and drop workouts. For a wrong start date, illness or travel, it says to un-apply the plan and re-apply it with a new date.
   - FasCat sends questions to a forum, not to email.
   - Sources: https://fascatcoaching.com/blogs/training-tips/adjust-fascat-training-plan and https://forum.fascatcoaching.com/t/get-started-with-your-plan/55
2. **State the limit plainly, once.**
   - MyProCoach: "We can explain how to make changes, but we don't make those changes for you." It lists customising plans under "What We Don't Provide".
   - Its support ends 3 months after the plan ends. Extra support is paid: $30 for 3 months, $90 for 12.
   - Sources: https://support.myprocoach.net/hc/en-us/articles/360000529751 and https://www.myprocoach.net/extended-coach-support/
3. **Publish rules for missed workouts so buyers don't need to ask.** TrainRight's rules:
   - Miss 1 to 2 days: move on.
   - Miss 3 to 7 days: add back part of the missed volume over several weeks, never by doubling up.
   - Miss 10 or more days: ease back in.
   - Source: https://trainright.com/missed-workouts-guide-to-adjusting-training/
4. **80/20 Endurance is the other extreme:** unlimited email support while the plan runs. That is the model to avoid, given Matti's steer. https://www.8020endurance.com/getting-started-with-80-20-training/
5. **TrainingPeaks itself:**
   - Buyers can drag and drop and shift workouts. Moving future workouts needs a Premium account. https://help.trainingpeaks.com/hc/en-us/articles/204072164-How-do-I-move-a-workout
   - A plan is applied by start date or end date. To change the date, the buyer removes the plan and re-applies it. Event-specific plans can only be applied once. https://help.trainingpeaks.com/hc/en-us/articles/204071974-How-do-I-apply-my-plan
   - TrainingPeaks emails the buyer for a star rating within about 3 days of the last planned workout. https://help.trainingpeaks.com/hc/en-us/articles/204072494
   - TrainingPeaks' coach blog calls it best practice to attach a short plan guide to a day-one workout and to add weekly notes. https://www.trainingpeaks.com/coach-blog/how-to-add-value-to-your-training-plans/
   - The same blog notes that "most athletes will never contact you". https://www.trainingpeaks.com/coach-blog/selling-training-plans-fits-within-coaching-business/
   - It also suggests a paid call of about $50 to fit a plan to someone's schedule. https://www.trainingpeaks.com/coach-blog/how-to-sell-100000-worth-of-training-plans-a-year/
6. **Digital product emails in general:**
   - Send the thank-you right away.
   - Send a feedback or review ask only after the product has been used.
   - One ask per email.
   - Don't pay for positive reviews.
   - Sources: https://kit.com/resources/blog/customer-onboarding, https://help.klaviyo.com/hc/en-us/articles/360028872611 and https://campaignmonitor.com/resources/knowledge-base/do-ctas-help-to-improve-email-response-rates

Inference, not from a source: the Premium-only workout moves and the
"event plans apply once" rule probably cause many of the "can you move my
plan" requests. A guide that covers both should cut most of them.

## Recommendations

1. **Write one "How to run this plan" guide per brand.**
   - Contents:
     - setting the start or end date, and re-applying the plan
     - moving workouts on Premium, and what to do on a free account
     - event plans apply once
     - what to do after 1 to 2, 3 to 7, or 10 or more missed days
     - never stack hard days
     - the line "Store plans aren't customized. If you want it built around your week, that's coaching."
   - Attach the guide to the day-one workout of every TrainingPeaks plan, and link it from the day-0 email.
   - Matti writes the coaching rules. Claude can draft for his edit.
2. **Two emails for TrainingPeaks store buyers, not five.**
   - Day 0: thanks, plus the guide. Its one ask is an easy question about their race.
   - After the race, or about 3 days after the plan ends with no race: "how did it go", plus one line that coaching is how you get training built around your life.
   - Drop `tp_week1_check`, `tp_checkin` and `tp_progress` for the `trainingpeaks_store` source.
3. **No open-ended support, and no reply that promises to fix the plan.** When a buyer writes in anyway, reply from a short template:
   - Point them to the guide section that covers it.
   - Say once that store plans aren't customized.
   - Offer coaching in one line.
   - Each new repeat question becomes a line in the guide.
4. **Coaching is the only way to get a plan bent around their life.** Matti could also offer a paid one-off plan review call, as TrainingPeaks suggests (about $50). That is his call, and it is not in the templates below.
5. **Leave ratings to TrainingPeaks.** It already asks within days of the last workout, so our post-race email doesn't need a second ask.
6. **Update `docs/email-voice-model.md`** so the help line for plan buyers says "here's how" or "that's what my coaching is", not "reply and I'll fix it".

## Proposed copy

Same voice rules as `docs/email-voice-model.md`: 25 to 70 words, opens on
them, one plain help line, one question, sign-off "Matti". This is draft copy
for Matti's edit. Before any of it ships, it still needs the voice grounding
and the full no-ai-slop pass in `docs/AI_WRITING_POLICY.md`.

### Day 0 (race plan, race upcoming)

> Hi {first},
>
> Thanks for grabbing my {race} plan. {One line on what makes the race hard.}
> Everything you need to run it, including what to do with a missed week, is
> in the guide on day one of the plan.
>
> Is this your first {race}?
>
> Matti

Until the guide exists, drop the guide sentence. Don't swap in a "reply and I'll
adjust it" line.

### Day 0 (no race, e.g. base plans or A Year in Gravel)

> Hi {first},
>
> Thanks for picking up {plan}. The guide on day one covers your start date and
> what to do when a week falls apart.
>
> What are you building toward?
>
> Matti

### After the race (or plan end)

> Hi {first},
>
> Thanks for using my {race} plan. I hope the day went well. If you ever want
> training built around your life week to week, that's what my coaching is.
>
> How did it go?
>
> Matti

### Reply when a buyer asks for changes

> Hi {first},
>
> Good question. {The guide's answer in one or two sentences.} Store plans
> aren't customized, so that's the move I'd make. If you want someone
> adjusting it around your week, that's my coaching.
>
> Matti

## The 9 hand-written notes, rewritten

The same people as the Nov 10 drafts, with the adjust offer removed. None have
been sent. Race dates were checked Nov 10 2026:

- Leuven Legacy Gravel was held Oct 18 2026.
- SBT GRVL was held Jun 28 2026.
- Mid South 2026 was held in mid-March.
- GFNY San Luis Potosí is in December 2026.
- Gran Fondo Strade Bianche and Mid South 2027 are both in spring 2027.

Race still ahead:

- **Wendy Butler (Tour de Brisbane):** her existing draft drops the adjust line and keeps the thanks and her question.
- **William Tietz (Gran Fondo Strade Bianche):** Thanks for grabbing my Strade Bianche plan. That steep finish up into Siena hurts once the gravel has taken its toll, so the long tempo days are the ones to protect. When are you planning to start it?
- **Erika Rix (Mid South):** Thanks for grabbing my Mid South plan. That Oklahoma red dirt rewards patience and steady fueling more than big watts. Is this your first Mid South?
- **Alejandra Guerra (GFNY San Luis Potosí):** Thanks for picking up my GFNY San Luis Potosí plan. You should be deep in the build now with December getting close. How's training feeling?
- **Leonardo Cano (A Year in Gravel):** Thanks for picking up A Year in Gravel. A full year is a real commitment and I'm glad you're doing it with my plan. What are you building toward?

Race passed:

- **Greg Patychuk (Leuven Legacy Gravel):** Thanks for using my Leuven Legacy Gravel plan. I hope the race went well, Belgian gravel is no joke. How did the day go?
- **Brendan Train (Crit King):** Thanks for grabbing my Crit King plan back in March. I hope it gave you some extra snap in the finishes this season. How did the season go?
- **Jamie Keeley (several plans):** Thanks for sticking with my plans this year, from the build and Gravel Grit last winter through SBT GRVL. I really appreciate it. How did Steamboat go?
- **John Shears (Mid South):** Thanks for using my Mid South plan this spring. I hope the red dirt treated you well. How did the race go?

For the passed-race notes, Matti can add the coaching line ("If you want 2027
built around your life week to week, that's what my coaching is"). He can also
leave it for the reply, since the voice model offers the paid thing in the
reply, not the broadcast.

## Code changes to make once Matti agrees

1. Add a per-source `skip: True` to `_OVERRIDABLE_STEP_KEYS` handling in
   `mission_control/services/sequence_engine.py`. A skipped step advances the
   way a failed race premise already does, with the same audit log entry.
2. In `mission_control/sequences/post_purchase.py`, set
   `trainingpeaks_store: {"skip": True}` on steps 1 to 3.
3. Rewrite `tp_purchase_welcome` and `tp_nps` to the copy above, and remove the
   fix-it offers. The post-race email already waits for the race
   (`race_premise`) or the plan's end (`delay_from_completion_days`).
4. Update `mission_control/tests/test_tp_store_sales.py`, which asserts the
   five TrainingPeaks templates and subjects.
5. Amend the help-line example in `docs/email-voice-model.md`.

## Open questions for Matti

- Does the guide live as a page per brand, a PDF attached in TrainingPeaks, or both?
- A paid plan review call, or coaching only?
- Should the custom-plan welcome emails keep promising rebuilds?
- I could not confirm when TrainingPeaks includes the buyer's email in the sale
  notice. Only 10 of 27 sale mails carried one, so many buyers can only be
  reached through the guide inside the plan itself.
