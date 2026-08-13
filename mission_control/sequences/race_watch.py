"""One-step confirmation for Gravel God race watchers."""

SEQUENCE = {
    "id": "race_watch_v1",
    "name": "Race Watch (Gravel God)",
    "description": "Confirms a race watch; later updates come from the daily notifier.",
    "trigger": "race_watch",
    "active": True,
    "variants": {"A": {"weight": 100, "name": "Confirm", "steps": [
        {"delay_days": 0, "template": "race_watch_confirm", "subject": "watching {race_name}"},
    ]}},
}
