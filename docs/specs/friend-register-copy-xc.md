# Friend-register copy — XC Ski Labs (deadpan-warm skin)

Same register as GG/RL (`friend-register-copy.md`): simple, about THEM, end
on a real question, broadcasts never pitch. XC accent: Labs-family deadpan +
Matti first person, zero profanity, dry understatement, weather/wax fatalism
allowed. Sign-off: — Matti.

**Season inversion (critical):** Nov–Mar is XC RACE SEASON; offseason ≈
Apr–Oct. The webhook computes `offseason` per-brand — never reuse the
gravel calendar here.

Launch set = welcome pair + win_back + banked offseason note. Race-finder /
countdown / post-purchase tracks follow when XC's quiz, race-date triggers,
and purchase webhook exist.

### xc_welcome · day 0 · xc_welcome_value
SUBJECT: which race?
BODY:
(exactly one wb_* key set at enrollment — guide > trail > race; offseason
flag is XC-seasonal: Apr–Oct)

{{#wb_guide}}
{first_name} — thanks for reading the guide. How was the section on {wb_guide}?

Questions, hit reply. Happy to help.
{{/wb_guide}}
{{#wb_trail}}
{first_name} — saw you looking at {wb_trail}. Skiing one of them, or comparing?

How is training going?
{{/wb_trail}}
{{#wb_race}}
{first_name} — you were on the {wb_race} page. Is that the one you're pointing at?

How is training going?
{{/wb_race}}
{{^any_context}}
{{^offseason}}
{first_name} — what race are you getting ready for?

How is the season going so far?
{{/offseason}}
{{#offseason}}
{first_name} — offseason. How did last winter go?

What worked, what did not? I'm always curious how skiers spend the summer.
{{/offseason}}
{{/any_context}}

— Matti

### xc_welcome · day 10 · xc_welcome_followup   [OPTIONAL]
SUBJECT: pick a race yet?
BODY:
{first_name} — did you land on a race, or still weighing options?

If it is down to two, send both. Snow reliability usually settles the argument.

— Matti

### xc_win_back · day 0 · xc_win_back
SUBJECT: did you end up skiing it?
BODY:
{{#race_name}}{first_name} — a while back you were looking at {race_name}. Did you end up skiing it?{{/race_name}}{{^race_name}}{first_name} — a while back you were comparing races in the database. Did you end up racing last winter?{{/race_name}}

What is next on the calendar?

— Matti

### seasonal · may · xc_offseason_note   (annual broadcast, banked — XC offseason opens ~April)
SUBJECT: offseason
BODY:
{first_name} — offseason. How did the winter go?

What worked, what did not? I'm always curious how skiers approach the summer.

— Matti
