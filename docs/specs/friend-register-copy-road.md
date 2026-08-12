# Friend-register copy — Roadie Labs (deadpan skin)

Same register as GG (`friend-register-copy.md`): simple, about THEM, end on a
real question. Accent differences: deadpan, clinical, zero profanity, no
exclamation points, verdict sentences allowed, humor budget = flat
parenthetical only. Sign-off: — Matti. Broadcasts never pitch.

### road_welcome · day 0 · road_welcome_value
SUBJECT: which race?
BODY:
{{#wb_guide}}
{greeting} thanks for reading the guide. How was the chapter on {wb_guide}?

Questions, hit reply. That is what it is for.
{{/wb_guide}}
{{#wb_trail}}
{greeting} you were looking at {wb_trail}. Riding one of them, or comparing?

How is training going?
{{/wb_trail}}
{{#wb_race}}
{greeting} you were on the {wb_race} page. Is that the target?

How is training going?
{{/wb_race}}
{{^any_context}}
{{^offseason}}
{greeting} what race are you getting ready for?

How is training going?
{{/offseason}}
{{#offseason}}
{greeting} offseason. How did last year go?

What worked, what did not? We are always curious how people run the offseason.
{{/offseason}}
{{/any_context}}

— Matti

### road_welcome · day 10 · road_welcome_followup   [OPTIONAL]
SUBJECT: pick a race yet?
BODY:
{greeting} did you pick a race, or still comparing?

If it is down to two, send both. That is a solvable problem.

— Matti

### road_nurture · day 2 · road_prep_variables
SUBJECT: did the prep notes cover it?
BODY:
{greeting} thanks for grabbing {{#race_name}}the {race_name} prep notes{{/race_name}}{{^race_name}}the prep notes{{/race_name}}. Did they cover what you needed?

Questions about the race, hit reply.

— Matti

### road kit delivery · day 0 · road_prep_kit_delivery   (prep_kit_gate only)
SUBJECT: your {race_name} prep kit
BODY:
{greeting} thanks for grabbing {{#race_name}}the {race_name} prep kit{{/race_name}}{{^race_name}}the prep kit{{/race_name}}.

{{#race_slug}}Here is the link before it disappears into a browser tab: https://roadielabs.com/race/{race_slug}/prep-kit/.{{/race_slug}}

Questions about the race, hit reply. What are you trying to sort out?

— Matti

### road_race_specific · day 1 · road_quiz_recap
SUBJECT: which ones made the shortlist?
BODY:
{greeting} the finder gave you matches. Which ones are actually in contention?

Send the shortlist. We will tell you where the quiz is right and where it probably is not.

[if prep_kit_url] The {race_name} prep kit: open it here.

— Matti

### road_race_specific · day 4 · road_race_deep_dive
SUBJECT: where do long races get you?
BODY:
{greeting} while {race_name} is on your list: where do long races usually get you — the start, the middle, or the last hour?

The answer changes what to work on. Genuinely asking.

— Matti

### race_countdown (RL) · road_countdown_16w
SUBJECT: 16 weeks to {race_name}
BODY:
{greeting} {race_name} is sixteen weeks out. That is the full training window.

Are you where you planned to be? If not, send your actual weekly hours. We will tell you what the time is good for.

— Matti

### race_countdown (RL) · road_countdown_8w
SUBJECT: 8 weeks to {race_name}
BODY:
{greeting} eight weeks to {race_name}. Enough time to do real work. Not enough to waste.

How has training gone? Send your weekly hours for an honest read on what is possible from here.

— Matti

### road_post_purchase · day 0 · road_purchase_welcome
SUBJECT: questionnaire received
BODY:
{greeting} questionnaire received. The plan is being built from your course, your FTP, and your actual hours. Delivery inside 48 hours.

If anything changes — schedule, body, race date — reply. The plan gets rebuilt around it.

— Matti

### road_post_purchase · day 3 · road_week1
SUBJECT: how did the first rides feel?
BODY:
{greeting} how did the first rides feel?

If the answer is "easy": correct. That is calibration. Do not add volume to it.

— Matti

### road_post_purchase · day 10 · road_checkin_week2
SUBJECT: two weeks in
BODY:
{greeting} two weeks in. Three data points, one line each:

Numbers right or wrong? Schedule holding? Anything hurting?

If Tuesday keeps failing, Tuesday is mis-specified. Not you.

— Matti

### road_post_purchase · day 21 · road_progress_update
SUBJECT: the middle weeks
BODY:
{greeting} you are in the middle of the build. How is it holding?

A recovery week is coming. Let it be easy. That is where the adaptation happens.

— Matti

### road_post_purchase · day 42 · road_nps_request   (plan-end timing)
SUBJECT: did {race_name} happen?
BODY:
{greeting} did the race happen? How did it go?

We want the unpolished version — what the plan got right, what it got wrong. The part that stings is the part that gets fixed.

— Matti

### road_win_back · day 0 · road_win_back   (create def if absent)
SUBJECT: did you end up riding it?
BODY:
{{#race_name}}{greeting} a while back you were looking at {race_name}. Did you end up riding it?{{/race_name}}{{^race_name}}{greeting} a while back you were comparing races in the database. Did you end up riding one this year?{{/race_name}}

What is next on the calendar?

— Matti

### seasonal · november · road_offseason_note   (annual broadcast, banked)
SUBJECT: offseason
BODY:
{greeting} offseason. How did the year go?

What worked, what did not? We are always curious how people run the offseason.

— Matti

### race_debrief · day 0 · road_race_debrief   (daily job services/race_debrief.py — race passed 3–180 days ago; {when_phrase} supplied by the job; friend-test 4/5)
SUBJECT: how did {race_name} go?
BODY:
{greeting} did you race {race_name} {when_phrase}? Happy with how it went?

What held up, what did not? If the day came apart — pacing, fueling, the back half — tell me what happened.

— Matti
