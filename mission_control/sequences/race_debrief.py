"""Race-debrief sequences — the race happened, ask how it went. Both brands.

Enrollment comes ONLY from services/race_debrief.py (the daily job), never
from the subscriber webhook. One email per contact, ever (enroll()'s
(sequence_id, contact_email) dedup). The premise is certain — we know the
race date passed — so the ask is direct: happy with how you rode? What went
well, what went badly?

No pitch. The plan/coaching conversation happens in Matti's REPLY
(draft_race_reply.py) — replies are the conversion engine. Register per
docs/email-voice-model.md.

A/B (gravel only — road's 4 leads can't power a test): same subject, body
varies structurally. A frames the reply ("what went well/badly" + honest
read offer); B is the bare friend question. The metric that matters is
replies — attribute by looking up the enrollment's variant. Opens per
variant are on the sequence detail page.
"""

GG_DEBRIEF = {
    "id": "race_debrief_v1",
    "name": "Race Debrief (Gravel God)",
    "description": "Their race happened — one honest how'd-it-go. Replies open the coaching conversation.",
    "trigger": "race_debrief",
    "active": True,
    "variants": {
        "A": {"weight": 50, "name": "Honest read", "steps": [
            {"delay_days": 0, "template": "race_debrief",
             "subject": "how'd {race_name} go?"},
        ]},
        "B": {"weight": 50, "name": "Bare question", "steps": [
            {"delay_days": 0, "template": "race_debrief_minimal",
             "subject": "how'd {race_name} go?"},
        ]},
    },
}

RL_DEBRIEF = {
    "id": "road_race_debrief_v1",
    "name": "Race Debrief (Roadie Labs)",
    "brand": "roadielabs",
    "description": "Deadpan mirror of the gravel debrief.",
    "trigger": "race_debrief",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Debrief", "steps": [
            {"delay_days": 0, "template": "road_race_debrief",
             "subject": "how did {race_name} go?"},
        ]},
    },
}
