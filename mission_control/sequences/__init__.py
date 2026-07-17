"""Sequence registry — loads all sequence definitions and exports SEQUENCES dict.

Sequences are brand-scoped: each definition may carry a "brand" key
("gravelgod" | "roadielabs" | "xcskilabs"); absent means "gravelgod" (back-compat with
pre-multi-brand definitions). Enrollment filters on (trigger, brand) so a
Roadie Labs lead never receives Gravel God copy and vice versa.
"""
from __future__ import annotations

from mission_control.sequences.welcome import SEQUENCE as welcome
from mission_control.sequences.nurture import SEQUENCE as nurture
from mission_control.sequences.race_specific import SEQUENCE as race_specific
from mission_control.sequences.post_purchase import SEQUENCE as post_purchase
from mission_control.sequences.win_back import SEQUENCE as win_back
from mission_control.sequences.road_welcome import SEQUENCE as road_welcome
from mission_control.sequences.road_nurture import SEQUENCE as road_nurture
from mission_control.sequences.road_race_specific import SEQUENCE as road_race_specific
from mission_control.sequences.road_post_purchase import SEQUENCE as road_post_purchase
from mission_control.sequences.race_countdown import GG_8, GG_16, RL_8, RL_16
from mission_control.sequences.xc_welcome import SEQUENCE as xc_welcome
from mission_control.sequences.xc_win_back import SEQUENCE as xc_win_back

DEFAULT_BRAND = "gravelgod"

SEQUENCES: dict[str, dict] = {
    welcome["id"]: welcome,
    nurture["id"]: nurture,
    race_specific["id"]: race_specific,
    post_purchase["id"]: post_purchase,
    win_back["id"]: win_back,
    road_welcome["id"]: road_welcome,
    road_nurture["id"]: road_nurture,
    road_race_specific["id"]: road_race_specific,
    road_post_purchase["id"]: road_post_purchase,
    GG_16["id"]: GG_16,
    GG_8["id"]: GG_8,
    RL_16["id"]: RL_16,
    RL_8["id"]: RL_8,
    xc_welcome["id"]: xc_welcome,
    xc_win_back["id"]: xc_win_back,
}


def sequence_brand(seq: dict) -> str:
    """Brand a sequence belongs to (absent key = gravelgod)."""
    return seq.get("brand", DEFAULT_BRAND)


def get_sequence(sequence_id: str) -> dict | None:
    """Get a sequence definition by ID."""
    return SEQUENCES.get(sequence_id)


def get_active_sequences() -> list[dict]:
    """Get all active sequence definitions."""
    return [s for s in SEQUENCES.values() if s.get("active")]


def get_sequences_for_trigger(trigger: str, brand: str = DEFAULT_BRAND) -> list[dict]:
    """Get all active sequences matching a trigger for one brand."""
    return [
        s for s in SEQUENCES.values()
        if s.get("active") and s.get("trigger") == trigger and sequence_brand(s) == brand
    ]
