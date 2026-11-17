"""Matti, 2026-11-17: the plan offer is the 4-weekly rate on every brand,
never a total, payment count or per-race sum. Scans every sequence email."""

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "mission_control" / "templates" / "emails" / "sequences"
ENGINE = Path(__file__).resolve().parent.parent / "mission_control" / "services" / "sequence_engine.py"


def test_no_sequence_email_uses_a_total_price_token():
    hits = {f.name: re.findall(r"\{(price_\w+|plan_12wk\w*)\}", f.read_text())
            for f in TEMPLATES.glob("*.html")}
    assert {k: v for k, v in hits.items() if v} == {}


def test_engine_offers_only_the_rate_token():
    src = ENGINE.read_text()
    assert '_PRICING_TOKEN_KEYS = ("plan_price",)' in src
    assert "total_display" not in src


def test_roadie_offer_states_the_rate():
    for name in ("road_anti_pitch.html", "road_repitch.html"):
        assert "{plan_price}" in (TEMPLATES / name).read_text(), name
