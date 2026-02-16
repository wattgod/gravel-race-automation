"""Sequence registry — loads all sequence definitions and exports SEQUENCES dict."""

from mission_control.sequences.welcome import SEQUENCE as welcome
from mission_control.sequences.nurture import SEQUENCE as nurture
from mission_control.sequences.race_specific import SEQUENCE as race_specific
from mission_control.sequences.post_purchase import SEQUENCE as post_purchase
from mission_control.sequences.win_back import SEQUENCE as win_back

SEQUENCES: dict[str, dict] = {
    welcome["id"]: welcome,
    nurture["id"]: nurture,
    race_specific["id"]: race_specific,
    post_purchase["id"]: post_purchase,
    win_back["id"]: win_back,
}


def get_sequence(sequence_id: str) -> dict | None:
    """Get a sequence definition by ID."""
    return SEQUENCES.get(sequence_id)


def get_active_sequences() -> list[dict]:
    """Get all active sequence definitions."""
    return [s for s in SEQUENCES.values() if s.get("active")]


def get_sequences_for_trigger(trigger: str) -> list[dict]:
    """Get all active sequences that match a trigger."""
    return [s for s in SEQUENCES.values() if s.get("active") and s.get("trigger") == trigger]
