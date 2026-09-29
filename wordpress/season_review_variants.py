"""
Question sets for the season review (/coaching/season-review/).

Each variant is pure data; generate_season_review.py renders any of them
with the same card, save/resume, timers and email formatting. Variants
differ in voice and length, not in behaviour.

Field names that mean the same thing across variants share a name
(outcome_goal, inner_obstacle, habit, hours_next, ...) so the coach's
flags and the Endure draft JSON work for every variant.

Field kinds:
  text, area (textarea), date, select, radio, checks, timed (textarea
  with a countdown), pair (two fields side by side), scale (0-10 in one
  row, with `low`/`high` end labels), note (a paragraph, no input).
Optional keys: req, ph, rows, options, minutes, swap (start/stop prompt
swap, keyed off habit_direction), lift (a radio value that makes other
fields optional), layout ("vertical" stacks a radio's options).

Every input name must be unique within a variant; each `checks` option is
its own input, named by its key.
"""

from pricing import SEASON_PLAN_PRICE_DISPLAY

SEASON = 2026
NEXT = SEASON + 1

AREAS = [
    ("endurance", "Endurance / late-race durability"),
    ("climbing", "Climbing"),
    ("top_end", "Top end / surges"),
    ("fueling", "Fueling & hydration"),
    ("skills", "Bike handling & skills"),
    ("strength", "Strength & mobility"),
    ("body_comp", "Body composition"),
    ("recovery", "Sleep & recovery"),
    ("consistency", "Consistency"),
    ("mental", "Head game / pacing"),
    ("other", "Something else"),
]

HOURS = [
    ("3-5", "3&ndash;5 hrs"), ("5-7", "5&ndash;7 hrs"), ("7-10", "7&ndash;10 hrs"),
    ("10-12", "10&ndash;12 hrs"), ("12-15", "12&ndash;15 hrs"), ("15+", "15+ hrs"),
]

# Verbatim from the Self Authoring Present Authoring lists.
STRENGTHS = [
    "Do what I say I am going to do",
    "Make plans and stick to them",
    "Am very goal-oriented",
    "Have seen my tendency for hard work pay off",
    "Am always learning new things",
    "Am not bothered when things don't go according to plan",
    "Calm down quickly when I do get upset",
    "Am rarely or never stopped from doing what I want by my fears",
    "Watch what I eat carefully",
    "Am comfortable alone",
    "Enjoy time in natural surroundings",
    "Make other people laugh and have fun",
]
FAULTS = [
    "Am too perfectionistic",
    "Feel that I am being unproductive if I relax",
    "Seriously dislike having my routine or schedule upset",
    "Often procrastinate",
    "Frequently make excuses",
    "Have no stable daily routine for sleeping or eating",
    "Pursue too many activities at the same time",
    "May spend too much time pursuing fun and excitement",
    "Am often too optimistic",
    "Often take counterproductive or unnecessary risks",
    "Compare myself unfavorably to other people",
    "Let my fears stop me from doing things I want to do",
    "Get stressed out easily",
    "Cannot negotiate for myself very well",
]

DEAD_HABIT_REASONS = [
    ("dead_obvious", "No set time or place"),
    ("dead_attractive", "Nothing in it I looked forward to"),
    ("dead_easy", "Too much hassle to start"),
    ("dead_satisfying", "Couldn't see it working"),
]

YOU = {"title": "You", "fields": [{"kind": "pair", "fields": [
    {"name": "name", "label": "Name", "kind": "text", "req": True, "ph": "First Last", "auto": "name"},
    {"name": "email", "label": "Email", "kind": "email", "req": True, "ph": "you@email.com", "auto": "email"},
]}]}

HABIT_SWAP_FIELDS = [
    {"name": "habit_direction", "label": "Will you start or stop a habit?", "kind": "radio", "req": True,
     "options": [("do", "Start"), ("reduce", "Stop")]},
    {"name": "habit", "label": "What will you do every day?", "kind": "text", "req": True,
     "swap": {"do": {"label": "What will you do every day?", "ph": "e.g., 10 minutes of hip mobility"},
              "reduce": {"label": "What will you stop doing?", "ph": "e.g., Phone in the bedroom"}}},
    {"name": "habit_when", "label": "When and where will it happen?", "kind": "text", "req": True,
     "swap": {"do": {"label": "When and where will it happen?", "ph": "e.g., After I close the laptop, on the mat by the trainer"},
              "reduce": {"label": "What will you change so it doesn't happen?", "ph": "e.g., Charger lives in the kitchen"}}},
    {"name": "habit_min", "label": "What is the smallest version that counts?", "kind": "text", "req": True,
     "swap": {"do": {"label": "What is the smallest version that counts?", "ph": "e.g., One stretch"},
              "reduce": {"label": "What will you do instead?", "ph": "e.g., Read the book on the nightstand"}}},
]


def _race_pair(label="Main race, if the goal has one"):
    return {"kind": "pair", "fields": [
        {"name": "a_race", "label": label, "kind": "text", "ph": "e.g., Unbound 200"},
        {"name": "a_race_date", "label": "Date", "kind": "date"},
    ]}


def _module(key, title, minutes, fields):
    return {"key": key, "title": title, "minutes": minutes, "fields": fields}


# ── Standard: the version Matti tried first ───────────────────

STANDARD = {
    "slug": "standard",
    "badge": "Season Review",
    "h1": f"Close the Books on {SEASON}",
    "intro": "About 15 minutes, with optional sections at the end if you want to go deep. It saves as you type.",
    "sections": [
        YOU,
        {"title": f"{SEASON}", "fields": [
            {"name": "proudest", "label": f"What are you proudest of from {SEASON}, and what did you do that made it happen?", "kind": "area", "req": True, "rows": 4},
            {"name": "last_goal", "label": f"What was your main goal for {SEASON}?", "kind": "text", "req": True, "ph": "The one you set before the season"},
            {"name": "last_goal_result", "label": "What happened?", "kind": "radio", "req": True,
             "options": [("hit", "Hit"), ("close", "Close"), ("missed", "Missed"), ("dropped", "Dropped"), ("none", "No clear goal")],
             "lift": {"when": "none", "fields": ["last_goal", "last_goal_why"]}},
            {"name": "last_goal_why", "label": "What most decided the result?", "kind": "text", "req": True, "ph": "e.g., Flatted at mile 40; the fitness was there"},
        ]},
        {"title": f"{NEXT}", "fields": [
            {"name": "outcome_goal", "label": f"By the end of {NEXT}, I will&hellip;", "kind": "text", "req": True, "ph": "e.g., Finish Unbound 200 under 14 hours"},
            {"name": "outcome_measure", "label": "How will we know?", "kind": "text", "req": True, "ph": "e.g., Official finish time"},
            {"name": "not_yet", "label": "Why haven&#39;t you done it already?", "kind": "text", "req": True,
             "ph": "Not the excuse. The reason."},
            {"name": "outcome_why", "label": "Why do you want it?", "kind": "whychain", "req": True},
            _race_pair(),
        ]},
        {"title": "What Gets in the Way", "fields": [
            {"name": "inner_obstacle", "label": "What in you is most likely to get in the way?", "kind": "text", "req": True, "ph": "Not the weather. You. e.g., I skip rides after a late night out"},
            {"name": "obstacle_plan", "label": "If that shows up, then I will&hellip;", "kind": "text", "req": True, "ph": "e.g., Ride the short version before 9 a.m."},
        ]},
        {"title": "One Area, One Habit", "fields": [
            {"name": "area", "label": "What one area most needs to improve for this goal?", "kind": "select", "req": True, "options": AREAS},
            *HABIT_SWAP_FIELDS,
        ]},
        {"title": "Your Year", "fields": [
            {"name": "hours_next", "label": "How many hours can you honestly give most weeks?", "kind": "select", "req": True, "options": HOURS},
            {"name": "constraints", "label": "Anything that could change what you can do: work, family, health or travel?", "kind": "text", "req": True, "ph": "Write &ldquo;nothing&rdquo; if none"},
        ]},
        {"title": "Me", "fields": [
            {"name": "next_season_plan", "label": f"For {NEXT}, what do you want from me?", "kind": "radio", "req": True,
             "options": [("coaching", "Coaching"), ("custom_plan", "A custom plan"), ("undecided", "Not sure"), ("break", "Taking a break")]},
            {"name": "coach_notes", "label": "What should I keep or change? Anything else?", "kind": "area", "rows": 3},
        ]},
    ],
    "done": "You&#39;re done. Submit now, or add any of the optional sections below first.",
    "deep_title": "Go deeper &mdash; optional, as much as you want",
    "modules": [
        _module("ideal", "The season you want", "15 min", [
            {"name": "ideal_season", "kind": "timed", "minutes": 15, "rows": 12,
             "label": f"It&#39;s December {NEXT} and the season went as well as it could. Who were you, what did you do, and what made it matter? Write without stopping."}]),
        _module("avoid", "The season to avoid", "5 min", [
            {"name": "avoid_season", "kind": "timed", "minutes": 5, "rows": 7,
             "label": f"It&#39;s December {NEXT} and it went badly. What happened, and what was your part in it?"}]),
        _module("moments", f"The moments that shaped {SEASON}", "10 min", [
            {"name": "moment_1", "label": "The moment that mattered most: what happened?", "kind": "area", "rows": 3},
            {"name": "moment_1_role", "label": "What part was yours, and what wasn&#39;t?", "kind": "area", "rows": 2},
            {"name": "moment_1_impact", "label": "What did it change about how you see yourself?", "kind": "area", "rows": 2},
            {"name": "moment_2", "label": "Another one, good or bad", "kind": "area", "rows": 3}]),
        _module("traits", "What carried you, what cost you", "5 min", [
            {"name": "strength", "label": f"Which of these carried you in {SEASON}?", "kind": "select", "options": [(t, t) for t in STRENGTHS]},
            {"name": "strength_when", "label": "When did it show up, and how do you use it more?", "kind": "area", "rows": 2},
            {"name": "fault", "label": "Which of these cost you most?", "kind": "select", "options": [(t, t) for t in FAULTS]},
            {"name": "fault_when", "label": "When did it cost you, and what will you do so it doesn&#39;t repeat?", "kind": "area", "rows": 2}]),
        _module("wants", "Wants that fight your goal", "3 min", [
            {"name": "competing_wants", "label": "What do you enjoy that costs you training?", "kind": "area", "rows": 2, "ph": "The post-ride party. Two days wrecked, twenty times a year."},
            {"name": "want_to_want", "label": "What would you have to start wanting instead?", "kind": "text", "ph": "e.g., Being proud of a 9 p.m. bedtime"}]),
        _module("dead_habit", "A habit that died", "2 min", [
            {"name": "dead_habit", "label": f"A habit you meant to keep in {SEASON} that didn&#39;t last", "kind": "text", "ph": "e.g., Mobility after every ride"},
            {"name": "dead_reasons", "label": "What was missing?", "kind": "checks", "options": DEAD_HABIT_REASONS}]),
    ],
    "submit": "Submit Season Review",
    "success": f"Got it. I'll read it properly and come back with the plan for {NEXT}.",
}


# ── Claude style: warm, plain, one idea per question ──────────

CLAUDE = {
    "slug": "claude",
    "badge": "Season Review",
    "h1": f"Your {SEASON}, and What Comes Next",
    "intro": "Around 15 minutes. There are no wrong answers here, just honest ones. Your progress saves as you go.",
    "sections": [
        {"title": "About You", "fields": YOU["fields"]},
        {"title": "Looking Back", "fields": [
            {"name": "proudest", "label": "What are you proudest of from this season?", "kind": "area", "req": True, "rows": 3,
             "ph": "It doesn't have to be a result. Consistency, courage, a hard day you didn't quit on: all of it counts."},
            {"name": "hardest", "label": "What was the hardest part of the season, and what did it teach you?", "kind": "area", "req": True, "rows": 3},
            {"name": "last_goal_result", "label": f"How did your main goal for {SEASON} turn out?", "kind": "radio", "req": True,
             "options": [("hit", "I got there"), ("close", "Came close"), ("missed", "Fell short"), ("dropped", "Changed course"), ("none", "I didn't set one")]},
            {"name": "surprise", "label": "What surprised you about yourself this year?", "kind": "text"},
        ]},
        {"title": "Right Now", "fields": [
            {"name": "energy", "label": "How do you feel about riding right now?", "kind": "radio", "req": True,
             "options": [("hungry", "Hungry for more"), ("content", "Content"), ("tired", "Tired"), ("break", "Ready for a break")]},
            {"name": "strength_text", "label": "What's one strength you'll carry into next season?", "kind": "text", "req": True},
            {"name": "fault_text", "label": "What's one pattern you'd like to leave behind?", "kind": "text", "req": True},
        ]},
        {"title": "Looking Ahead", "fields": [
            {"name": "outcome_goal", "label": f"What would make {NEXT} feel like a great season?", "kind": "text", "req": True,
             "ph": "As specific as you can: a race, a time, a feeling you could describe"},
            {"name": "outcome_measure", "label": "How will you know you got there?", "kind": "text", "req": True},
            {"name": "not_yet", "label": "What has kept you from getting there so far?", "kind": "text", "req": True},
            {"name": "outcome_why", "label": "Why does this matter to you?", "kind": "whychain", "req": True},
            _race_pair("Is there a race at the center of it?"),
        ]},
        {"title": "Making It Real", "fields": [
            {"name": "inner_obstacle", "label": "What's most likely to get in your way?", "kind": "text", "req": True,
             "ph": "Think about your own habits and patterns more than circumstances"},
            {"name": "obstacle_plan", "label": "When that happens, what will you do?", "kind": "text", "req": True, "ph": "If ___, then I will ___"},
            {"name": "habit", "label": "What's one small habit that would help most?", "kind": "text", "req": True},
            {"name": "habit_when", "label": "When and where will you do it?", "kind": "text", "req": True},
        ]},
        {"title": "Life Around Riding", "fields": [
            {"name": "hours_next", "label": "About how many hours a week can you give to training?", "kind": "select", "req": True, "options": HOURS},
            {"name": "constraints", "label": "Is anything coming up that I should plan around?", "kind": "text"},
        ]},
        {"title": "Working Together", "fields": [
            {"name": "next_season_plan", "label": f"What would you like for {NEXT}?", "kind": "radio", "req": True,
             "options": [("coaching", "Continue coaching"), ("custom_plan", "A custom plan"), ("undecided", "Not sure yet"), ("break", "Taking a break")]},
            {"name": "coach_notes", "label": "Is there anything you'd like me to do more of, less of, or differently?", "kind": "area", "rows": 3},
        ]},
    ],
    "done": "That&#39;s everything I need. Submit now, or keep going below if you&#39;d like to reflect further.",
    "deep_title": "If you&#39;d like to go further",
    "modules": [
        _module("ideal", "The season you want", "15 min", [
            {"name": "ideal_season", "kind": "timed", "minutes": 15, "rows": 12,
             "label": f"Imagine it's December {NEXT} and the season went better than you hoped. Describe it: where you rode, how you felt, who you became."}]),
        _module("moments", "A moment that mattered", "5 min", [
            {"name": "moment_1", "label": "Choose a moment from this season that stayed with you. What happened?", "kind": "area", "rows": 3},
            {"name": "moment_1_impact", "label": "What did it show you about yourself?", "kind": "area", "rows": 2}]),
        _module("letter", "A note to your future self", "5 min", [
            {"name": "letter", "label": "Write a few lines to yourself, to read the night before your first race next year.", "kind": "area", "rows": 6}]),
    ],
    "submit": "Send My Review",
    "success": f"Thank you. I'll read this carefully and come back to you with a plan for {NEXT}.",
}


# ── Shared voice: the "So. 2026." blocks ──────────────────────
# Matti's register, used by every questionnaire that speaks in it — the
# public lead form, the coached-athlete form, and the original. Built as
# functions so the three can't drift into three different tones.


def s_you(hidden_athlete: bool = False):
    fields = list(YOU["fields"])
    if hidden_athlete:
        fields = [{"name": "athlete", "kind": "hidden"}] + fields
    return {"title": "Who Are You Again", "fields": fields}


def s_highlight():
    return {"title": "The Highlight Reel", "sub": "Not the Strava version. The one you&#39;d tell at 1 a.m.", "fields": [
        {"name": "proudest", "label": f"What are you proudest of from {SEASON}?", "kind": "area", "req": True, "rows": 3},
        {"name": "last_goal", "label": "What did you say you&#39;d do this year?", "kind": "text", "req": True,
         "ph": "The goal you wrote down in January, not the one you&#39;ve since decided you meant"},
        {"name": "last_goal_result", "label": "And?", "kind": "radio", "req": True,
         "options": [("hit", "Nailed it"), ("close", "Close"), ("missed", "Missed"), ("dropped", "Quietly abandoned"), ("none", "Never set one")],
         "lift": {"when": "none", "fields": ["last_goal", "last_goal_why"]}},
        {"name": "last_goal_why", "label": "What decided it?", "kind": "text", "req": True, "ph": "Flat tires only explain so much"},
    ]}


def s_blooper(vices_field: str = "competing_wants"):
    """The same question, asked of a stranger (a want) or an athlete (a vice)."""
    vices = (
        {"name": "vices", "label": "What do you eat, drink or do that you already know is costing you? What, how often, and when.",
         "kind": "area", "req": True, "rows": 3,
         "ph": "Mine&#39;s the post-ride party. Two days wrecked, twenty times a year."}
        if vices_field == "vices" else
        {"name": "competing_wants", "label": "What do you love that&#39;s quietly making you slower?", "kind": "text", "req": True,
         "ph": "Mine&#39;s the post-ride party. Two days wrecked, twenty times a year. Do the math."}
    )
    return {"title": "The Blooper Reel", "sub": "Do you double up, spiral, or quietly disappear?", "fields": [
        {"name": "hardest", "label": "Worst moment of the season. How much of it was on you?", "kind": "area", "req": True, "rows": 3,
         "ph": "Some of it, probably. That&#39;s the good news. It means you can fix it."},
        {"name": "missed_workout", "label": "When you miss a planned workout, you&hellip;", "kind": "radio", "req": True,
         "options": [("make_up", "Make it up", "Even if it wrecks the next two days"),
                     ("move_on", "Move on", "One workout won&#39;t matter"),
                     ("guilt", "Feel guilty", "Beat myself up, eventually let it go"),
                     ("spiral", "Spiral", "Start questioning the whole plan"),
                     ("disappear", "Quietly disappear", "Go dark for a week and hope nobody notices")]},
        vices,
    ]}


def s_2027(audience: bool = True, scary: bool = True):
    fields = [
        {"name": "outcome_goal", "label": f"By the end of {NEXT}, I will&hellip;", "kind": "text", "req": True,
         "ph": "Measurable. If it can&#39;t fail, it&#39;s not a goal, it&#39;s a vibe."},
        {"name": "outcome_measure", "label": "How will we know you did it?", "kind": "text", "req": True},
    ]
    if scary:
        fields.append({"name": "outcome_scary", "label": "Say it out loud. Does it scare you?", "kind": "radio",
                       "options": [("yes", "Yes"), ("a_bit", "A little"), ("no", "No (so make it bigger)")]})
    fields += [
        {"name": "not_yet", "label": "So why haven&#39;t you done it yet?", "kind": "text", "req": True, "ph": "Not the excuse. The reason."},
        {"name": "outcome_why", "label": "Why do you want it? The real answer, not the Instagram caption.", "kind": "whychain", "req": True},
    ]
    if audience:
        fields.append({"name": "goal_audience", "label": "Who knows about this goal?", "kind": "radio", "req": True,
                       "options": [("public", "Everyone", "I posted it"), ("friends", "Friends and family"),
                                   ("coach", "Just me and you"), ("nobody", "Nobody yet", "Including, until now, me")]})
    fields.append(_race_pair("The race it all points at"))
    return {"title": f"{NEXT}", "sub": "&ldquo;Get faster&rdquo; isn&#39;t a goal. It&#39;s a direction.", "fields": fields}


def s_obstacle():
    return {"title": "Your Biggest Obstacle Is You", "sub": "Not the weather. Not work. You.", "fields": [
        {"name": "inner_obstacle", "label": "What in you is most likely to screw this up?", "kind": "text", "req": True,
         "ph": "e.g., I skip rides after a late night out"},
        {"name": "obstacle_plan", "label": "When that shows up, you&#39;ll&hellip;", "kind": "text", "req": True,
         "ph": "Specific. &ldquo;Try harder&rdquo; isn&#39;t a plan."},
    ]}


def s_habit():
    return {"title": "What Would a Fast Cyclist Do?", "sub": "One thing. Built so it survives a bad week.", "fields": [
        {"name": "area", "label": "What&#39;s the one thing that most needs to get better?", "kind": "select", "req": True, "options": AREAS},
        *[dict(f) for f in HABIT_SWAP_FIELDS[:3]],
        {"name": "habit_min", "label": "The smallest version that still counts", "kind": "text", "req": True,
         "swap": {"do": {"label": "The smallest version that still counts", "ph": "The one you&#39;ll still do on your worst Tuesday"},
                  "reduce": {"label": "What you&#39;ll do instead", "ph": "e.g., Read the book on the nightstand like an adult"}}},
        {"name": "habit_2", "label": "A second daily habit, and when (optional)", "kind": "text",
         "ph": "e.g., Lights out by 10, phone charging in the kitchen"},
    ]}


def s_logistics():
    return {"title": "The Boring Logistics", "sub": "Include the kids, the commute, and the partner who thinks you ride too much.", "fields": [
        {"name": "hours_next", "label": "Hours a week you can actually train. Not aspirationally.", "kind": "select", "req": True, "options": HOURS},
        {"name": "constraints", "label": "Anything coming that&#39;ll blow up the plan?", "kind": "text", "req": True,
         "ph": "Baby, new job, surgery, a move. &ldquo;Nothing&rdquo; is a fine answer."},
    ]}


def s_me(coached: bool = True):
    return {"title": "Me", "fields": [
        {"name": "next_season_plan", "label": f"For {NEXT}, you want:", "kind": "radio", "req": True,
         "options": [("coaching", "More coaching" if coached else "Coaching"), ("custom_plan", "A custom plan"),
                     ("undecided", "Not sure"), ("break", "A break from me" if coached else "Neither")]},
        {"name": "coach_notes", "label": "What should I keep doing, and what should I stop? I can take it.", "kind": "area", "rows": 3},
    ]}


MATTI_MODULES = [
    _module("ideal", "The season you want", "15 min", [
        {"name": "ideal_season", "kind": "timed", "minutes": 15, "rows": 12,
         "label": f"It&#39;s December {NEXT} and it went perfectly. Write it like a race report: where, who, how it felt. Don&#39;t stop to edit."}]),
    _module("avoid", "The season you&#39;re scared of", "5 min", [
        {"name": "avoid_season", "kind": "timed", "minutes": 5, "rows": 7,
         "label": f"Now the other one. December {NEXT}, it went sideways. What happened, and what was your part?"}]),
    _module("best", "Your best stretch ever", "3 min", [
        {"name": "best_block", "label": "Describe the best stretch of training you&#39;ve ever had. What made it work?", "kind": "area", "rows": 3,
         "ph": "Those are your success conditions. We&#39;re going to rebuild them on purpose."}]),
    _module("quit", "What would make you quit", "2 min", [
        {"name": "quit_triggers", "label": "What would make you quit, or quietly stop caring?", "kind": "area", "rows": 2}]),
    _module("traits", "Your faults, itemized", "5 min", [
        {"name": "fault", "label": "Pick the one that cost you most", "kind": "select", "options": [(t, t) for t in FAULTS]},
        {"name": "fault_when", "label": "When did it bite you?", "kind": "area", "rows": 2},
        {"name": "strength", "label": "Fine, and the one that carried you", "kind": "select", "options": [(t, t) for t in STRENGTHS]}]),
    _module("dead_habit", "The habit that died", "2 min", [
        {"name": "dead_habit", "label": "One you swore you&#39;d keep this year", "kind": "text", "ph": "e.g., Mobility after every ride (lol)"},
        {"name": "dead_reasons", "label": "Cause of death", "kind": "checks", "options": DEAD_HABIT_REASONS}]),
]


# ── Matti style: the coaching register, with the wink ─────────

MATTI = {
    "slug": "matti",
    "badge": "Season Autopsy",
    "h1": f"So. {SEASON}.",
    "intro": "Fifteen minutes. Don&#39;t write what you&#39;d post. Write what you&#39;d admit after the second beer. It saves as you go, so &ldquo;I lost my answers&rdquo; is off the table as an excuse.",
    "sections": [s_you(), s_highlight(), s_blooper(), s_2027(), s_obstacle(), s_habit(), s_logistics(), s_me()],
    "done": "That&#39;s the minimum. Hit submit, or keep digging if you&#39;re into that kind of thing.",
    "deep_title": "Extra credit &mdash; for the obsessive",
    "modules": MATTI_MODULES,
    "submit": "Submit the Autopsy",
    "success": f"Got it. I&#39;ll read every word (probably twice) and come back with a plan for {NEXT}.",
}


# ── The public lead form (/goals/) — same voice, no coaching talk ──
# D6/D14: a stranger gets the autopsy and the 2027 goal, not the logistics
# and not "what do you want from me". Those belong in the plan form, after
# they have a reason to care.

GOAL_2027 = {
    "slug": "goal_2027",
    "badge": "The 2027 Goal Autopsy",
    "h1": f"So. {SEASON}.",
    "intro": "Fifteen minutes. Don&#39;t write what you&#39;d post. Write what you&#39;d admit after the second beer. You leave with a 2027 goal poster and the one thing most likely to wreck it. It saves as you go.",
    "sections": [s_you(), s_highlight(), s_blooper(), s_2027(), s_obstacle(), s_habit()],
    "done": "That&#39;s it. Hit submit and your poster is on its way &mdash; or keep digging first.",
    "deep_title": "Extra credit &mdash; for the obsessive",
    "modules": MATTI_MODULES,
    "submit": "Make My Poster",
    "success": f"Got it. Your {NEXT} poster is on its way to your inbox.",
    # Its own page, and the only variant that is meant to be found.
    "path": "/goals/",
    "title": f"Your {NEXT} Goal, On Paper | Gravel God",
    "description": (f"Fifteen minutes on the season you had and the one you want. You leave "
                    f"with a {NEXT} goal poster and the one thing most likely to wreck it."),
    "output": "goals.html",
    "robots": "index, follow",
    # The lead system is the record here: Mission Control stores the answers,
    # renders the poster and sends it. No email backstop, because every
    # backstop copy is another thing in Matti's inbox for a stranger.
    "transport": "worker",
    # The results screen, and the offer beneath it (never in front of it).
    "results": {
        "title": f"Your {NEXT}, on paper.",
        "lead": "Print it. Tape it where you'll see it in February. A copy is on its way to your inbox.",
        "download": "Download the poster",
    },
    "offer": {
        "kicker": "Step two",
        "variants": [
            {"key": "A", "h": "You&#39;ve written it down. Historically, this is where it dies.",
             "p": "Step two is a plan built around the hours you actually have, not the ones you promised."},
            {"key": "B", "h": "Goals are free. The doing is the product.",
             "p": "You&#39;ve done the thinking. The rest is a calendar and your real hours."},
            {"key": "C", "h": "That&#39;s step one. Step two is the part everyone skips.",
             "p": f"A custom plan for your {NEXT}, built from what you just told me."},
        ],
        # Two plans beneath the same variant copy (D2/D15, step 5 of the
        # build order). Kept to a price line + one button each — Matti
        # found the earlier step-two body too complicated.
        "plans": [
            {
                "key": "race",
                "price": "Race Plan: priced by the week from your race date",
                "cta": f"Build my {NEXT} plan",
                "cta_href": "/questionnaire/?src=goals",
            },
            {
                "key": "season",
                "price": f"Season Plan: {SEASON_PLAN_PRICE_DISPLAY}, the whole year",
                "cta": "Build my whole season",
                "cta_href": "/season-plan/",
            },
        ],
        "decline": "Just the poster, thanks",
        "terms": "I build every plan myself. You see the number before you pay.",
    },
}



# ── Five Questions: the shortest thing that still plans a season ──

FIVE = {
    "slug": "five",
    "badge": "Season Review",
    "h1": "Five Questions",
    "intro": "Five minutes. More room at the end if you want it.",
    "sections": [
        {"title": "You", "numbered": False, "fields": YOU["fields"]},
        {"title": f"1. What went well in {SEASON}?", "numbered": False, "fields": [
            {"name": "proudest", "label": "", "kind": "area", "req": True, "rows": 3}]},
        {"title": "2. What didn&#39;t, and why?", "numbered": False, "fields": [
            {"name": "hardest", "label": "", "kind": "area", "req": True, "rows": 3}]},
        {"title": f"3. What do you want from {NEXT}, and how will we know you got it?", "numbered": False, "fields": [
            {"name": "outcome_goal", "label": "", "kind": "area", "req": True, "rows": 2, "ph": "e.g., Finish Unbound 200 under 14 hours. Official time."}]},
        {"title": "4. What&#39;s most likely to get in the way, and what will you do when it does?", "numbered": False, "fields": [
            {"name": "obstacle_combo", "label": "", "kind": "area", "req": True, "rows": 2, "ph": "If ___, then I will ___"}]},
        {"title": "5. What should I know before I plan it?", "numbered": False, "fields": [
            {"name": "constraints", "label": "", "kind": "area", "rows": 2, "ph": "Travel, work, family, injuries, the race that matters most"}]},
        {"title": "Two Quick Picks", "numbered": False, "fields": [
            {"name": "hours_next", "label": "Hours a week you can train", "kind": "select", "req": True, "options": HOURS},
            {"name": "next_season_plan", "label": f"For {NEXT}, you want", "kind": "radio", "req": True,
             "options": [("coaching", "Coaching"), ("custom_plan", "A custom plan"), ("undecided", "Not sure"), ("break", "A break")]},
        ]},
    ],
    "done": "Done. Submit, or open any section below if you want to spend longer.",
    "deep_title": "More room &mdash; optional",
    "modules": [
        _module("ideal", "The season you want", "15 min", STANDARD["modules"][0]["fields"]),
        _module("habit", "One habit", "3 min", [
            {"name": "area", "label": "What one area most needs to improve?", "kind": "select", "options": AREAS},
            *[dict(f, req=False) for f in HABIT_SWAP_FIELDS]]),
        STANDARD["modules"][2],
        STANDARD["modules"][3],
        STANDARD["modules"][4],
        _module("whys", "Five whys", "5 min", [
            {"name": "not_yet", "label": "Why haven&#39;t you done it already?", "kind": "text", "ph": "Not the excuse. The reason."},
            {"name": "outcome_why", "label": "Why do you want it?", "kind": "whychain"}]),
        _module("coach", "Notes for me", "2 min", [
            {"name": "coach_notes", "label": "What should I keep or change?", "kind": "area", "rows": 3}]),
    ],
    "submit": "Submit",
    "success": f"Got it. I'll come back with the plan for {NEXT}.",
}


# ── Athlete: for the people Matti already coaches ─────────────
# Built on Endure's limiter interrogation (endurelabs
# docs/specs/endure-loop-2026.md §3, the seven probes), so the answers file
# straight into the athlete's record: probes stored verbatim, the rate
# limiter with its evidence, vices as habits to cut, skill gaps, the week
# breakers, the drop order, the 48 hours, and the admission.

ATHLETE = {
    "slug": "athlete",
    "badge": "Athlete Season Review",
    "h1": f"So. {SEASON}.",
    "intro": "About twenty-five minutes. Same deal as always: don&#39;t write what you&#39;d post, write what you&#39;d admit after the second beer. This one goes in your file and shapes what I build you. It saves as you go.",
    "sections": [
        s_you(hidden_athlete=True),
        s_highlight(),
        s_blooper(vices_field="vices"),
        # The seven probes (endure-loop-2026 §3), in the same voice as the rest.
        {"title": "The One Thing", "sub": "If I could fix exactly one thing about you, what wins the most time?", "fields": [
            {"name": "limiter", "label": "The one thing", "kind": "text", "req": True, "ph": "e.g., I fade after hour five"},
            {"name": "limiter_kind", "label": "What kind of thing is it?", "kind": "radio", "req": True,
             "options": [("fitness", "Fitness"), ("skill", "Skill"), ("positioning", "Positioning"),
                         ("durability", "Durability"), ("body", "Body"), ("life", "Life")]},
            {"name": "limiter_evidence", "label": "And the evidence? Don&#39;t say &ldquo;I just feel like it.&rdquo;", "kind": "area", "req": True, "rows": 2,
             "ph": "The race, the ride, the moment you knew"},
        ]},
        {"title": "Where You Lose Races", "sub": "The ones fitness doesn&#39;t explain.", "fields": [
            {"name": "skill_gaps", "label": "Where do they get away from you?", "kind": "area", "req": True, "rows": 2,
             "ph": "Descending, feed zones, the first 30 miles, the surge out of a corner"},
        ]},
        {"title": "The Week That Breaks", "sub": "Everyone has one. The question is how often.", "fields": [
            {"name": "week_breakers", "label": "What breaks a training week for you, and how many weeks a year?", "kind": "area", "req": True, "rows": 2,
             "ph": "Sick kids, work trips, the in-laws"},
            {"name": "drop_order", "label": "When the week collapses, what goes first, second, third?", "kind": "text", "req": True,
             "ph": "e.g., Strength, then the long ride, then sleep"},
        ]},
        {"title": "The 48 Hours", "sub": "Before your last race. All of it, including the part you&#39;d skip.", "fields": [
            {"name": "pre_race_48h", "label": "Walk me through it.", "kind": "area", "req": True, "rows": 4,
             "ph": "Sleep, food, caffeine, travel, who you were with, what you were thinking"},
        ]},
        s_2027(),
        {"title": "The Admission", "sub": "The one you&#39;d rather not write down.", "fields": [
            {"name": "admission", "label": "What would you have to admit to yourself to hit this goal?", "kind": "area", "req": True, "rows": 3},
        ]},
        s_obstacle(),
        s_habit(),
        s_logistics(),
        s_me(),
    ],
    "done": "That&#39;s what I need. Hit submit, or keep digging below.",
    "deep_title": "Extra credit &mdash; for the obsessive",
    "modules": MATTI_MODULES,
    "submit": "Send It to Matti",
    "success": f"Got it. It&#39;s in your file. I&#39;ll read it before I build {NEXT}.",
}



# ── Exit: for an athlete who is leaving ──────────────────────
# Not a season review and not a lead. One required question, then the
# report card, the consent ask for the receipts ledger
# (docs/specs/receipts-social-proof-2026.md §3, §5.3) and loose ends.
# Answers go to Mission Control as source=athlete_exit, transactional only:
# a receipt to the athlete, an alert to Matti, never a marketing sequence.

# DRAFT COPY: Matti's read pending before deploy (receipts spec §3.7: Matti writes every ask).
EXIT = {
    "slug": "exit",
    "badge": "Exit Interview",
    "crumb": "Exit Interview",
    "h1": "Before You Go",
    "intro": "Five minutes, less if you&#39;re quick. Apart from your name and email, only the first question is required. I read every one of these myself. It isn&#39;t anonymous, so say it straight. It saves as you go.",
    "sections": [
        {"title": "You", "fields": s_you(hidden_athlete=True)["fields"]},
        {"title": "Why Now", "sub": "The real reason. There isn&#39;t a wrong one.", "fields": [
            {"name": "exit_reason", "label": "What&#39;s the main reason you&#39;re stopping?", "kind": "radio", "req": True,
             "options": [("done", "I got what I came for", "The race is done or the goal is hit"),
                         ("time", "Life got full", "Work, family, a move, the calendar"),
                         ("cost", "Cost", "The money needs to go elsewhere for now"),
                         ("health", "Injury or health"),
                         ("break", "A break from structured training"),
                         ("diy", "Coaching myself from here", "Or riding off a plan"),
                         ("elsewhere", "Moving to another coach, team or app"),
                         ("fit", "The coaching wasn&#39;t the right fit"),
                         ("progress", "I wasn&#39;t seeing the progress I wanted"),
                         ("other", "Something else")]},
            {"name": "exit_story", "label": "What tipped it, and when did you know?", "kind": "area", "rows": 3,
             "ph": "The week, the conversation, the race. Whatever it was."},
            {"name": "stay_lever", "label": "What, if anything, would have kept you?", "kind": "text",
             "ph": "&ldquo;Nothing, it was time&rdquo; is a fine answer."},
        ]},
        {"title": "The Report Card", "sub": "I&#39;ve graded you long enough. Your turn.", "fields": [
            {"name": "recommend", "label": "How likely are you to recommend me to a rider like you?", "kind": "scale",
             "low": "Not likely", "high": "Already have"},
            {"name": "keep_doing", "label": "What should I keep doing?", "kind": "area", "rows": 2},
            {"name": "change_one", "label": "What&#39;s one thing I should change?", "kind": "area", "rows": 2,
             "ph": "Be blunt. I&#39;d rather hear it from you than guess."},
            {"name": "what_changed", "label": "What changed for you while we worked together?", "kind": "area", "rows": 3,
             "ph": "Results, habits, how you think about training. &ldquo;Not much&rdquo; is worth knowing too."},
        ]},
        {"title": "On the Record", "sub": "Optional. Skip it and nothing changes.", "fields": [
            {"name": "quote", "label": "If a rider asked whether they should hire me, what would you tell them?", "kind": "area", "rows": 3,
             "ph": "In your words, the way you&#39;d say it. Good, bad or both."},
            {"name": "not_for", "label": "And who shouldn&#39;t hire me?", "kind": "text",
             "ph": "The rider this wouldn&#39;t work for"},
            {"name": "share_as", "label": "Can I share what you wrote above?", "kind": "radio", "layout": "vertical",
             "options": [("full", "Yes, with my full name"),
                         ("initial", "Yes, first name and last initial"),
                         ("age_group", "Yes, first name and age group"),
                         ("private", "No, keep it between us")]},
            {"name": "age_group", "label": "Your age group. It only shows if you picked first name and age group. If you&#39;re under 18, I&#39;ll need a parent&#39;s OK.",
             "kind": "select",
             "options": [("under_18", "Under 18"), ("18_29", "18&ndash;29"), ("30_39", "30&ndash;39"),
                         ("40_49", "40&ndash;49"), ("50_59", "50&ndash;59"), ("60_plus", "60+")]},
            {"name": "share_where", "label": "Where it can appear", "kind": "checks",
             "options": [("where_site", "gravelgodcycling.com"),
                         ("where_social", "Gravel God social posts"),
                         ("where_email", "Emails to riders thinking about coaching"),
                         ("where_tp", "My TrainingPeaks coach profile")]},
            {"name": "connection", "label": "Anything connecting us besides coaching? If so, I say so next to your words.",
             "kind": "radio", "layout": "vertical",
             "options": [("none", "No, just coaching"),
                         ("comped", "You coached me free or at a discount"),
                         ("friend", "We&#39;re friends or ride together"),
                         ("work", "We&#39;ve worked together"),
                         ("family", "We&#39;re family")]},
            {"name": "reference", "label": "If someone thinking about coaching wants to talk to a real athlete, can I introduce you by email?",
             "kind": "radio", "options": [("yes", "Yes"), ("ask", "Ask me first each time"), ("no", "No")]},
            {"name": "consent_note", "kind": "note",
             "text": "Before anything goes up, I&#39;ll send you the exact words and how they&#39;ll look, and nothing runs until you say yes. I won&#39;t edit your words without asking. It stays up for three years at most. Reply any time and it comes down within 7 days, though I can&#39;t pull back screenshots, reposts or search-engine copies. If you&#39;re under 18, I&#39;ll need a parent&#39;s OK too."},
        ]},
        {"title": "Loose Ends", "fields": [
            {"name": "come_back", "label": "Would you come back one day?", "kind": "radio",
             "options": [("yes", "Probably"), ("maybe", "Maybe"), ("no", "Probably not")]},
            {"name": "checkin", "label": "Want me to check in later? Once, then I leave you alone.", "kind": "radio",
             "options": [("none", "No thanks"), ("3m", "In about three months"),
                         ("6m", "In about six months"), ("preseason", "Before next season")]},
            {"name": "needs", "label": "Anything you need from me before you go?", "kind": "checks",
             "options": [("need_zones", "A summary of my zones and latest tests"),
                         ("need_notes", "Notes for training on my own"),
                         ("need_billing", "Confirmation that billing has stopped"),
                         ("need_tp", "Help with my TrainingPeaks account")]},
            {"name": "last_word", "label": "Anything else?", "kind": "area", "rows": 3, "ph": "Last word&#39;s yours."},
        ]},
    ],
    "done": "That&#39;s everything. Send it when you&#39;re ready.",
    "modules": [],
    "submit": "Send It to Matti",
    "success": "Got it. I&#39;ll read every word, and I&#39;ll come back to you on anything you asked for above.",
    # Its own page, never indexed, and not in any sitemap (the sitemap is an
    # allowlist: scripts/generate_sitemap.py INDEXABLE_WORDPRESS_PAGES).
    "path": "/coaching/exit/",
    "output": "coaching-exit.html",
    "title": "Before You Go | Gravel God",
    "robots": "noindex, nofollow",
    # Worker (the record) plus the FormSubmit email backstop, like athlete.
    "transport": "both",
    # The FormSubmit backstop's subject and heading. No coach flags and no
    # Endure goal draft: nothing on this form is a goal.
    "email_title": "Exit survey",
    "goal_export": False,
    "footer": "Your answers come straight to me and are stored in my system. They aren&#39;t anonymous. If you said I can share your words, nothing goes up until you&#39;ve approved the exact wording. The email copy goes through FormSubmit, a form service that keeps a copy for 30 days. Drafts are saved only in this browser until you submit. Questions? Email gravelgodcoaching@gmail.com",
}


VARIANTS = {v["slug"]: v for v in (STANDARD, CLAUDE, MATTI, GOAL_2027, FIVE, ATHLETE, EXIT)}
