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
{first_name} — thanks for grabbing the guide. How did you like the chapter on {wb_guide}?

Any more questions there, just hit reply — happy to help.
{{/wb_guide}}
{{#wb_trail}}
{first_name} — saw you checking out {wb_trail}. Racing one of them, or still deciding?

How's training going so far?
{{/wb_trail}}
{{#wb_race}}
{first_name} — saw you on the {wb_race} page. Is that the one you're getting ready for?

How's training going?
{{/wb_race}}
{{^any_context}}
{{^offseason}}
{first_name} — what race are you getting ready for?

How's training going?
{{/offseason}}
{{#offseason}}
{first_name} — happy offseason. You bored yet?

Happy with last year? What went well, what went badly? I'm always curious how people approach the offseason.
{{/offseason}}
{{/any_context}}

— Matti

### welcome · day 10 · welcome_followup   [OPTIONAL — cut if it feels like one text too many]
SUBJECT: land on a race yet?
BODY:
{first_name} — did you land on a race, or still shopping?

If you're stuck between two, send me both. Picking is half the fun.

— Matti

### nurture · day 2 · race_prep_tips   (they downloaded a prep kit)
SUBJECT: how'd the prep kit land?
BODY:
{first_name} — thanks for grabbing {{#race_name}}the {race_name} prep kit{{/race_name}}{{^race_name}}the prep kit{{/race_name}}. Did it cover what you needed?

Any questions about the race, just hit reply — happy to help.

— Matti

### race_specific · day 1 · quiz_results_recap   (they ran the race finder)
SUBJECT: which one are you actually considering?
BODY:
{first_name} — the finder gave you matches. Which ones are you actually considering?

Send me the shortlist and I'll tell you where I think the quiz got it right — and where it might have missed for you.

— Matti

### race_specific · day 4 · race_deep_dive
SUBJECT: where do races usually get you?
BODY:
{first_name} — while {race_name} is on your mind: where do long races usually get you — the start too fast, the middle too boring, or the last hour?

Genuinely curious. The answer changes what I'd tell you to work on.

— Matti

### race_countdown · day 0 · countdown_16w
SUBJECT: 16 weeks to {race_name}
BODY:
{first_name} — {race_name} is sixteen weeks out. That's the full window.

Are you where you wanted to be, training-wise? If not, tell me what your week actually looks like — I'll tell you what I'd do with the time you've got.

— Matti

### race_countdown · day 0 · countdown_8w
SUBJECT: 8 weeks to {race_name}
BODY:
{first_name} — eight weeks to {race_name}. Still enough time to do real work, not enough to waste any.

How's the training been going? Tell me your weekly hours and I'll give you my honest read on what's possible from here.

— Matti

### post_purchase · day 0 · purchase_welcome
SUBJECT: got your questionnaire
BODY:
{first_name} — got your questionnaire. I'm building around your course, your FTP, and the hours you actually have. You'll have it inside 48 hours.

One thing: if anything about your life changes — schedule, knee, race date — just reply. The plan bends.

— Matti

### post_purchase · day 3 · week1_tips
SUBJECT: how did the first rides feel?
BODY:
{first_name} — how did the first rides feel?

If the answer is "too easy" — good. That's calibration, not a mistake. Don't add extra. I've made that mistake enough times for both of us.

— Matti

### post_purchase · day 10 · checkin_week2
SUBJECT: two weeks in — quick check
BODY:
{first_name} — two weeks in. Three things I want to know:

Do the numbers feel right? Is the schedule surviving your actual week? Does anything hurt?

One line back is plenty. If Tuesday keeps not happening, Tuesday is wrong — not you.

— Matti

### post_purchase · day 21 · progress_update
SUBJECT: the boring middle
BODY:
{first_name} — you're in the boring middle now. How's it feeling?

Recovery week is coming. When it arrives, let it be easy — that's where the fitness actually shows up.

— Matti

### post_purchase · day 42 · nps_request   (timed to plan end via plan_weeks)
SUBJECT: did {race_name} happen?
BODY:
{first_name} — did the race happen? How did it go?

I want the real version — where the plan helped and where it was useless. The part that stings a little is the part I can fix.

— Matti

### win_back · day 0 · win_back_value
SUBJECT: did you end up racing it?
BODY:
{{#race_name}}{first_name} — a while back you were looking at {race_name}. Did you end up racing it?{{/race_name}}{{^race_name}}{first_name} — a while back you were poking around the race database. Did you end up racing this year?{{/race_name}}

Either way I'm curious how the season's going. What's next on your calendar?

— Matti

### seasonal · november · offseason_note   (annual broadcast — sent once via scripts/send_offseason_note.py, built before Nov)
SUBJECT: happy offseason
BODY:
{first_name} — happy offseason. You bored yet?

Happy with last year? What went well, what went badly?

I'm always curious how people approach the offseason.

— Matti
