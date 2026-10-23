# The friend-register set — GG, complete
# Rules: every sentence about them. 2–4 short sentences. End on a real question
# we actually want answered. Pitch lives in replies, never broadcasts.
# Sober variant B keeps existing copy as the A/B control — none of these touch it.

### welcome · day 0 · welcome_value
SUBJECT: getting ready for one of these?
BODY:
(exactly one wb_* key is set at enrollment — priority guide > trail > race;
offseason flag set Nov-Jan swaps the anonymous opener)

{{#wb_guide}}
{greeting} thanks for reading the guide. How did you like the chapter on {wb_guide}?

[if wb_guide_url] You can pick it back up here: {wb_guide}.

Any more questions there, just hit reply — happy to help.
{{/wb_guide}}
{{#wb_trail}}
{greeting} saw you checking out {wb_trail}. Racing one of them, or still deciding?

How's training going so far?
{{/wb_trail}}
{{#wb_race}}
{greeting} saw you on the {wb_race} page. Is that the one you're getting ready for?

How's training going?
{{/wb_race}}
{{^any_context}}
{{^offseason}}
{greeting} what race are you getting ready for?

How's training going?
{{/offseason}}
{{#offseason}}
{greeting} happy offseason. You bored yet?

Happy with last year? What went well, what went badly? I'm always curious how people approach the offseason.
{{/offseason}}
{{/any_context}}

— Matti

### welcome · day 10 · welcome_followup   [OPTIONAL — cut if it feels like one text too many]
SUBJECT: land on a race yet?
BODY:
{greeting} did you land on a race, or still shopping?

If you're stuck between two, send me both. Picking is half the fun.

— Matti

### nurture · day 2 · race_prep_tips   (they downloaded a prep kit)
SUBJECT: how'd the prep kit land?
BODY:
{greeting} thanks for grabbing {{#race_name}}the {race_name} prep kit{{/race_name}}{{^race_name}}the prep kit{{/race_name}}. Did it cover what you needed?

Any questions about the race, just hit reply — happy to help.

— Matti

### kit delivery · day 0 · prep_kit_delivery   (prep_kit_gate only)
SUBJECT: your {race_name} prep kit
BODY:
{greeting} thanks for grabbing {{#race_name}}the {race_name} prep kit{{/race_name}}{{^race_name}}the prep kit{{/race_name}}.

{{#race_slug}}Here is the link so you do not lose it: https://gravelgodcycling.com/race/{race_slug}/prep-kit/.{{/race_slug}}

Any questions about the race, hit reply. What are you trying to sort out?

— Matti

### race_specific · day 1 · quiz_results_recap   (they ran the race finder)
SUBJECT: which one are you actually considering?
BODY:
{greeting} the finder gave you matches. Which ones are you actually considering?

Send me the shortlist and I'll tell you where I think the quiz got it right — and where it might have missed for you.

[if prep_kit_url] Your {race_name} prep kit: open it here.

— Matti

### race_specific · day 4 · race_deep_dive
SUBJECT: where do races usually get you?
BODY:
{greeting} while {race_name} is on your mind: where do long races usually get you — the start too fast, the middle too boring, or the last hour?

Genuinely curious. The answer changes what I'd tell you to work on.

— Matti

### race_countdown · day 0 · countdown_16w
SUBJECT: 16 weeks to {race_name}
BODY:
{greeting} {race_name} is sixteen weeks out. That's the full window.

Are you where you wanted to be, training-wise? If not, tell me what your week actually looks like — I'll tell you what I'd do with the time you've got.

— Matti

### race_countdown · day 0 · countdown_8w
SUBJECT: 8 weeks to {race_name}
BODY:
{greeting} eight weeks to {race_name}. Still enough time to do real work, not enough to waste any.

How's the training been going? Tell me your weekly hours and I'll give you my honest read on what's possible from here.

— Matti

### post_purchase · day 0 · purchase_welcome
SUBJECT: got your questionnaire
BODY:
{greeting} got your questionnaire. I'm building around your course, your FTP, and the hours you actually have. You'll have it inside 24 hours.

One thing: if anything about your life changes — schedule, knee, race date — just reply. The plan bends.

— Matti

### post_purchase · day 0 · tp_purchase_welcome   (source trainingpeaks_store only; replaces purchase_welcome for TP store buyers)
SUBJECT: did the plan land on your calendar?
BODY:
{greeting} saw you picked up {{#plan_name}}{plan_name}{{/plan_name}}{{^plan_name}}the plan{{/plan_name}} on TrainingPeaks. If your week doesn't look like what the plan assumes, reply and tell me what it does look like. Easier to fix in week one than week six.

{{#race_name}}Did you set the start date so it ends on race day?{{/race_name}}{{^race_name}}When are you starting it?{{/race_name}}

— Matti

### post_purchase · day 3 · tp_week1_check   (trainingpeaks_store only; TP buyers pick their own start date, so nothing assumes the plan has begun)
SUBJECT: started yet?
BODY:
{greeting} once the plan starts, week 1 should feel too easy. That's calibration, not a mistake, so don't add extra. I've made that mistake enough times for both of us.

Has it started yet, or is it still sitting on the calendar?

— Matti

### post_purchase · day 10 · tp_checkin   (trainingpeaks_store only)
SUBJECT: is the schedule surviving your week?
BODY:
{greeting} a couple of weeks in, the thing I care about is whether the schedule survives your actual week. If Tuesday keeps not happening, Tuesday is wrong, not you.

Which day is giving you trouble so far?

— Matti

### post_purchase · day 21 · tp_progress   (trainingpeaks_store only)
SUBJECT: the easy weeks
BODY:
{greeting} the recovery weeks in {{#plan_name}}{plan_name}{{/plan_name}}{{^plan_name}}the plan{{/plan_name}} will feel too easy. Let them be easy, because that's where the fitness shows up.

How far in are you now?

— Matti

### post_purchase · end · tp_nps   (trainingpeaks_store only; base plans have no race, and without plan_weeks this falls back to day 42, so the copy works mid-plan or after)
SUBJECT: how's the plan treating you?
BODY:
{greeting} I want the honest version of how {{#plan_name}}{plan_name}{{/plan_name}}{{^plan_name}}the plan{{/plan_name}} is going for you, where it helps and where it's useless. The part that stings a little is the part I can fix.

What would you change about it?

— Matti

### post_purchase · day 3 · week1_tips
SUBJECT: how did the first rides feel?
BODY:
{greeting} how did the first rides feel?

If the answer is "too easy" — good. That's calibration, not a mistake. Don't add extra. I've made that mistake enough times for both of us.

— Matti

### post_purchase · day 10 · checkin_week2
SUBJECT: two weeks in — quick check
BODY:
{greeting} two weeks in. Three things I want to know:

Do the numbers feel right? Is the schedule surviving your actual week? Does anything hurt?

One line back is plenty. If Tuesday keeps not happening, Tuesday is wrong — not you.

— Matti

### post_purchase · day 21 · progress_update
SUBJECT: the boring middle
BODY:
{greeting} you're in the boring middle now. How's it feeling?

Recovery week is coming. When it arrives, let it be easy — that's where the fitness actually shows up.

— Matti

### post_purchase · day 42 · nps_request   (timed to plan end via plan_weeks)
SUBJECT: did {race_name} happen?
BODY:
{greeting} did the race happen? How did it go?

I want the real version — where the plan helped and where it was useless. The part that stings a little is the part I can fix.

— Matti

### win_back · day 0 · win_back_value
SUBJECT: did you end up racing it?
BODY:
{{#race_name}}{greeting} a while back you were looking at {race_name}. Did you end up racing it?{{/race_name}}{{^race_name}}{greeting} a while back you were poking around the race database. Did you end up racing this year?{{/race_name}}

Either way I'm curious how the season's going. What's next on your calendar?

— Matti

### seasonal · november · offseason_note   (annual broadcast — sent once via scripts/send_offseason_note.py, built before Nov)
SUBJECT: happy offseason
BODY:
{greeting} happy offseason. You bored yet?

Happy with last year? What went well, what went badly?

I'm always curious how people approach the offseason.

— Matti

### race_debrief · day 0 · race_debrief   (VARIANT A "Honest read", weight 50 — daily job services/race_debrief.py, race passed 3–180 days ago; {when_phrase} supplied by the job: "the other weekend" / "a few weeks back" / "back in {Month}"; friend-test 5/5)
SUBJECT: how'd {race_name} go?
BODY:
{greeting} did you end up racing {race_name} {when_phrase}? Happy with how it went?

What went well, what went badly? If something fell apart — pacing, fueling, the back half — tell me what happened and I'll give you my honest read.

— Matti

### race_debrief · day 0 · race_debrief_minimal   (VARIANT B "Bare question", weight 50 — same subject so the split isolates the body; tests whether the diagnostic frame earns replies or the bare friend question beats it; friend-test 5/5)
SUBJECT: how'd {race_name} go?
BODY:
{greeting} did you end up racing {race_name} {when_phrase}? How'd it go?

— Matti

### race_watch · day 0 · race_watch_confirm   (transactional confirm for the watch-this-race affordance; the question makes it reply-able; friend-test 4/5)
SUBJECT: watching {race_name}
BODY:
{greeting} you're watching {race_name} — when its entry changes (date confirmed, re-rated, course news), I'll send it over. Nothing else comes with this.

Are you racing it, or still deciding?

— Matti
