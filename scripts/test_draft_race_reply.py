import json
from pathlib import Path

from scripts.draft_race_reply import classify_debrief, draft_debrief


FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "debrief_replies.json").read_text())


def test_real_reply_fixtures_classify():
    for case in FIXTURES:
        assert classify_debrief(case["text"])["primary"] == case["mode"]


def test_classifier_retains_multiple_labels_in_priority_order():
    result = classify_debrief("I deferred because my knee injury flared, then got sick.")
    assert result["labels"] == ["illness", "injury", "dns_deferred"]
    assert result["primary"] == "illness"


def test_offer_is_gated_by_mode_return_and_sub_twelve_week_race():
    race = {"weeks_out": 8}
    assert "next 10 days" in draft_debrief("I got sick and am riding again.", facts=race)
    assert "next 10 days" not in draft_debrief("I deferred with a knee injury.", facts=race)
    assert "next 10 days" not in draft_debrief("I paced it badly.", facts={"weeks_out": 14})
    assert "next 10 days" not in draft_debrief("It was a great day.", facts=race)


def test_empty_and_html_quoted_replies_do_not_crash_or_echo_quote():
    assert "understand" in draft_debrief("")
    html = "<p>I bonked late.</p><blockquote>Old email about pacing</blockquote>"
    result = draft_debrief(html)
    assert "I bonked late" in result
    assert "Old email" not in result
    assert classify_debrief(html)["primary"] == "fueling"
