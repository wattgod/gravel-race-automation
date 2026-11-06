"""Pick'em opt-ins (workers/pickem-intake): a lead, never a plan buyer.

The worker sends source "pickem", the game, the racing answer, and a
race_slug + race_name only when the rider said they're racing a distance.
"""

from __future__ import annotations

import pytest

from mission_control.sequences import get_sequences_for_trigger
from mission_control.services.race_countdown import gather_candidates

EMAIL = "racer@example.com"


@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch):
    import mission_control.services.sequence_engine as se
    monkeypatch.setattr(se, "_send_email_sync", lambda *a, **k: "rs-test")


def _post(client, **extra):
    body = {"email": EMAIL, "name": "", "brand": "gravelgod", "source": "pickem",
            "game": "unbound-200-2027", "racing": "200",
            "race_slug": "unbound-200", "race_name": "Unbound 200"}
    body.update(extra)
    body = {k: v for k, v in body.items() if v is not None}
    resp = client.post("/webhooks/subscriber", json=body,
                       headers={"Authorization": "Bearer test-secret-123"})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _rows(fake_db):
    return [e for e in fake_db.store["gg_sequence_enrollments"] if e["contact_email"] == EMAIL]


def test_racer_joins_welcome_only_with_race(client, fake_db):
    result = _post(client)
    welcome = {s["id"] for s in get_sequences_for_trigger("new_subscriber", "gravelgod")}
    assert welcome and set(result["enrolled"]) == welcome
    for trigger in ("plan_debrief", "plan_purchased", "athlete_review", "athlete_exit", "goal_2027"):
        assert not {s["id"] for s in get_sequences_for_trigger(trigger, "gravelgod")} & set(result["enrolled"])
    sd = _rows(fake_db)[0]["source_data"]
    assert sd["pickem_racing"] == "200" and sd["pickem_game"] == "unbound-200-2027"
    assert sd["race_slug"] == "unbound-200" and sd["race_name"] == "Unbound 200"
    # not a page visit: no "saw you on the Unbound 200 page" opener
    assert "wb_race" not in sd and "any_context" not in sd


def test_racer_is_a_countdown_lead(client, fake_db):
    _post(client)
    contacts, _ = gather_candidates(_rows(fake_db))
    assert contacts[EMAIL]["race_slug"] == "unbound-200"
    assert contacts[EMAIL]["race_name"] == "Unbound 200"


def test_no_or_lottery_carries_no_race(client, fake_db):
    _post(client, racing="lottery", race_slug=None, race_name=None)
    sd = _rows(fake_db)[0]["source_data"]
    assert sd["pickem_racing"] == "lottery"
    assert "race_slug" not in sd and "race_name" not in sd
    assert gather_candidates(_rows(fake_db))[0] == {}


def test_changed_answer_updates_the_record(client, fake_db):
    _post(client)
    _post(client, racing="no", race_slug=None, race_name=None)
    rows = _rows(fake_db)
    assert len(rows) == len(get_sequences_for_trigger("new_subscriber", "gravelgod"))
    for row in rows:
        sd = row["source_data"]
        assert sd["pickem_racing"] == "no"
        assert "race_slug" not in sd and "race_name" not in sd and "pickem_race_slug" not in sd
    _post(client, racing="xl", race_slug="unbound-xl", race_name="Unbound Gravel XL")
    assert all(r["source_data"]["race_slug"] == "unbound-xl" for r in _rows(fake_db))


def test_no_keeps_a_race_given_elsewhere(client, fake_db):
    client.post("/webhooks/subscriber", headers={"Authorization": "Bearer test-secret-123"},
                json={"email": EMAIL, "source": "race_profile", "brand": "gravelgod",
                      "race_slug": "sbt-grvl", "race_name": "SBT GRVL"})
    _post(client, racing="no", race_slug=None, race_name=None)
    for row in _rows(fake_db):
        assert row["source_data"]["race_slug"] == "sbt-grvl"
        assert row["source_data"]["pickem_racing"] == "no"
