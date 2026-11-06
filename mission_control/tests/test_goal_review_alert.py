"""Coach-facing review alert uses saved answers without sending a lead reply."""
import asyncio
import sys
from pathlib import Path

from mission_control.routers.webhooks import HELP_MOST_LABELS, _send_enrollment_alert
from mission_control.services import sequence_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "wordpress"))

from season_review_variants import GOAL_2027  # noqa: E402


def test_goal_review_alert_is_brand_scoped_and_escaped(monkeypatch):
    sent = []
    monkeypatch.setattr(sequence_engine, "_send_email_sync",
                        lambda to, subject, html, brand: sent.append((to, subject, html, brand)))
    for brand, tag in (("roadielabs", "RL"), ("xcskilabs", "XC")):
        asyncio.run(_send_enrollment_alert(
            "rider@example.com", "Rider", brand, "goal_2027",
            {"goal_answers": {
                "a_race": "Test Race", "outcome_goal": "Finish <script>alert(1)</script>",
                "inner_obstacle": "Work travel", "habit": "Ski twice weekly",
            }, "entry_src": "race", "offer_variant": "B"},
            ["goal_2027_v1"],
        ))
        _, subject, html, routed_brand = sent[-1]
        assert f"[{tag}] Goal review filed" in subject
        assert routed_brand == brand
        assert "Finish &lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "<script>" not in html
        assert "Work travel" in html and "Entry: race" in html
        assert "Reply personally" in html


def _goal_alert_html(monkeypatch, answers):
    sent = []
    monkeypatch.setattr(sequence_engine, "_send_email_sync",
                        lambda to, subject, html, brand: sent.append(html))
    asyncio.run(_send_enrollment_alert(
        "rider@example.com", "Rider", "gravelgod", "goal_2027",
        {"goal_answers": {"outcome_goal": "Finish Unbound", **answers}},
        ["goal_2027_v1"],
    ))
    return sent[-1]


def test_goal_review_alert_shows_what_would_help_most(monkeypatch):
    for key, label in (("plan", "A plan"), ("coaching", "Coaching"), ("tips", "Just tips")):
        html = _goal_alert_html(monkeypatch, {"help_most": key})
        assert f"Help</th><td style='padding:3px 0'>{label}</td>" in html
        assert "Pitch what they said would help most." in html


def test_goal_review_alert_without_help_answer_has_no_help_line(monkeypatch):
    html = _goal_alert_html(monkeypatch, {})
    assert ">Help<" not in html
    assert "Pitch what they said" not in html


def test_goal_review_alert_escapes_an_unknown_help_value(monkeypatch):
    html = _goal_alert_html(monkeypatch, {"help_most": "<b>both</b>"})
    assert "&lt;b&gt;both&lt;/b&gt;" in html and "<b>both</b>" not in html


def test_help_labels_match_the_goals_form():
    field = next(f for sec in GOAL_2027["sections"] for f in sec["fields"]
                 if f.get("name") == "help_most")
    assert dict((value, label) for value, label in field["options"]) == HELP_MOST_LABELS
