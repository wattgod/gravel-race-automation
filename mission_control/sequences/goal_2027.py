"""2027 goal questionnaire: results, then one check-in.

Doctrine holds (docs/email-voice-model.md): these emails do not pitch. The
step-two offer lives on the results screen, where the athlete just answered
the questions. Here we deliver what was promised and ask one question.
"""

GG = {
    "id": "goal_2027_v1",
    "name": "2027 Goals (Gravel God)",
    "description": "Poster delivery for goal_2027 leads, then one check-in.",
    "trigger": "goal_2027",
    "active": True,
    "variants": {"A": {"weight": 100, "name": "Delivery", "steps": [
        {"delay_days": 0, "template": "goal_2027_results", "subject": "your 2027 goal, on paper"},
        {"delay_days": 7, "template": "goal_2027_checkin", "subject": "still the goal?"},
    ]}},
}

ROAD = {
    **GG,
    "id": "road_goal_2027_v1",
    "name": "2027 Goals (Roadie Labs)",
    "brand": "roadielabs",
    "variants": {"A": {"weight": 100, "name": "Delivery", "steps": [
        {"delay_days": 0, "template": "road_goal_2027_results", "subject": "your 2027 goal, on paper"},
        {"delay_days": 7, "template": "road_goal_2027_checkin", "subject": "still the goal?"},
    ]}},
}

# XC ski races span a winter (2026-27), not a calendar year, so the subject
# reads "your season" rather than "your 2027 goal" — everything else about
# the delivery/check-in shape is identical to GG and Road.
XC = {
    **GG,
    "id": "xc_goal_2027_v1",
    "name": "2027 Goals (XC Ski Labs)",
    "brand": "xcskilabs",
    "variants": {"A": {"weight": 100, "name": "Delivery", "steps": [
        {"delay_days": 0, "template": "xc_goal_2027_results", "subject": "your season, on paper"},
        {"delay_days": 7, "template": "xc_goal_2027_checkin", "subject": "still the goal?"},
    ]}},
}


# A coached athlete's season review. One transactional receipt, no marketing:
# their answers ride on the enrollment so scripts/file_athlete_review.py can
# file them into the athlete's Endure record.
ATHLETE_REVIEW = {
    "id": "athlete_review_v1",
    "name": "Athlete Season Review (Gravel God)",
    "description": "Receipt for a coached athlete's season review. Never nurture.",
    "trigger": "athlete_review",
    "active": True,
    "variants": {"A": {"weight": 100, "name": "Receipt", "steps": [
        {"delay_days": 0, "template": "athlete_review_receipt", "subject": "got it"},
    ]}},
}
