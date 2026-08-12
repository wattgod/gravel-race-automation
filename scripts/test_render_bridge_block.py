from datetime import date, timedelta

from scripts.render_bridge_block import BLOCKS, render_bridge_block, scaled_durations


def test_each_archetype_renders_without_placeholders():
    for archetype in BLOCKS:
        output = render_bridge_block(archetype)
        assert "{easy}" not in output
        assert "whole price" in output
        assert "**Day 1:**" in output


def test_three_hour_input_stays_small():
    durations = scaled_durations(3)
    assert durations["long"] <= 70
    output = render_bridge_block("base_hold", hours=3)
    assert "150 min" not in output
    assert "3-hour week" in output


def test_race_framing_at_six_ten_and_twenty_weeks():
    today = date(2026, 8, 12)
    dates = {"gravelgod": {
        "six": (today + timedelta(weeks=6)).isoformat(),
        "ten": (today + timedelta(weeks=10)).isoformat(),
        "twenty": (today + timedelta(weeks=20)).isoformat(),
    }}
    assert "about 6 weeks out" in render_bridge_block("race_triage", race="six", dates=dates, today=today)
    assert "This is triage" in render_bridge_block("race_triage", race="ten", dates=dates, today=today)
    assert "no reason to force race work" in render_bridge_block("race_triage", race="twenty", dates=dates, today=today)
