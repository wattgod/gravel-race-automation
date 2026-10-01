"""Coach-facing review alert uses saved answers without sending a lead reply."""
import asyncio

from mission_control.routers.webhooks import _send_enrollment_alert
from mission_control.services import sequence_engine


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
