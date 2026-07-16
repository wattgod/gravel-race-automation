"""Race-countdown sequences — weeks-to-race lifecycle emails, both brands.

Enrollment comes ONLY from services/race_countdown.py (the daily job), never
from the subscriber webhook — the triggers are deliberately not
"new_subscriber". Each sequence is a single email at delay 0; the two tiers
are separate sequences so enroll()'s dedup gives each contact each tier at
most once (which is also the year-over-year guard).

{race_name}, {race_date}, {weeks_out} are safe here: the job guarantees all
three in source_data before enrolling. Copy register per
docs/email-conversion-principles.md — honest urgency only (base weeks are
non-renewable; the $249 cap subsidizes early starts).
"""

GG_16 = {
    "id": "race_countdown_16_v1",
    "name": "Race Countdown — 16 weeks (Gravel God)",
    "description": "The honest window: full-runway plan email when a lead's race is ~12-17 weeks out.",
    "trigger": "race_countdown_16",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Window", "steps": [
            {"delay_days": 0, "template": "countdown_16w",
             "subject": "16 weeks to {race_name}"},
        ]},
    },
}

GG_8 = {
    "id": "race_countdown_8_v1",
    "name": "Race Countdown — 8 weeks (Gravel God)",
    "description": "Triage math: what a short runway still buys, when a lead's race is ~5-9 weeks out.",
    "trigger": "race_countdown_8",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Triage", "steps": [
            {"delay_days": 0, "template": "countdown_8w",
             "subject": "8 weeks to {race_name}"},
        ]},
    },
}

RL_16 = {
    "id": "road_race_countdown_16_v1",
    "name": "Race Countdown — 16 weeks (Roadie Labs)",
    "brand": "roadielabs",
    "description": "The honest window, deadpan register.",
    "trigger": "race_countdown_16",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Window", "steps": [
            {"delay_days": 0, "template": "road_countdown_16w",
             "subject": "16 weeks to {race_name}"},
        ]},
    },
}

RL_8 = {
    "id": "road_race_countdown_8_v1",
    "name": "Race Countdown — 8 weeks (Roadie Labs)",
    "brand": "roadielabs",
    "description": "Triage math, deadpan register.",
    "trigger": "race_countdown_8",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Triage", "steps": [
            {"delay_days": 0, "template": "road_countdown_8w",
             "subject": "8 weeks to {race_name}"},
        ]},
    },
}
