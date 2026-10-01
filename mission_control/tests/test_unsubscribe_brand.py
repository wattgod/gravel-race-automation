"""Unsubscribe pages keep the brand of the email that sent the link."""

from urllib.parse import parse_qs, urlparse

import pytest

from mission_control.services.sequence_engine import build_unsubscribe_url


@pytest.mark.parametrize("brand,name,domain", [
    ("roadielabs", "Roadie Labs", "roadielabs.com"),
    ("xcskilabs", "XC Ski Labs", "xcskilabs.com"),
    ("gravelgod", "Gravel God", "gravelgodcycling.com"),
])
def test_unsubscribe_page_matches_email_brand(client, fake_db, brand, name, domain):
    email = f"unsubscribe-{brand}@example.com"
    response = client.post(
        "/webhooks/subscriber",
        json={"email": email, "name": "Test", "source": "goal_2027", "brand": brand,
              "goal_answers": {"outcome_goal": "Test goal"}},
        headers={"Authorization": "Bearer test-secret-123"},
    )
    assert response.status_code == 200

    link = build_unsubscribe_url(email, brand)
    page = client.get(urlparse(link).path + "?" + urlparse(link).query)
    assert page.status_code == 200
    assert f"You've Been Unsubscribed — {name}" in page.text
    assert f"{name} &middot; {domain}" in page.text
    rows = [e for e in fake_db.store["gg_sequence_enrollments"]
            if e["contact_email"] == email]
    assert rows and all(e["status"] == "unsubscribed" for e in rows)


@pytest.mark.parametrize("brand,name", [
    ("roadielabs", "Roadie Labs"),
    ("xcskilabs", "XC Ski Labs"),
])
def test_old_unsubscribe_link_infers_brand(client, brand, name):
    email = f"legacy-{brand}@example.com"
    response = client.post(
        "/webhooks/subscriber",
        json={"email": email, "name": "Test", "source": "goal_2027", "brand": brand,
              "goal_answers": {"outcome_goal": "Test goal"}},
        headers={"Authorization": "Bearer test-secret-123"},
    )
    assert response.status_code == 200

    link = build_unsubscribe_url(email)
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query.pop("brand")
    page = client.get(parsed.path, params={key: value[0] for key, value in query.items()})
    assert page.status_code == 200
    assert f"You've Been Unsubscribed — {name}" in page.text
