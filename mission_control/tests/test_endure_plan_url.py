"""The kit emails' Endure link ({endure_plan_url}) and its disclosure.

The link opens Endure's onboarding with the lead's race filled in. It is
built server-side (sequence_engine._endure_plan_url), never in a template.
"""

import re
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import pytest

import mission_control.services.race_countdown as rc
from mission_control.services.endure_offer import ENDURE_TRIAL_TERMS
from mission_control.services.sequence_engine import (
    _endure_number,
    _endure_plan_url,
    _inject_utm_params,
    _render_template,
)

TODAY = date(2026, 11, 22)
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def dates():
    with patch.dict(rc._dates_cache, {}, clear=True):
        def _set(brand="gravelgod", **slug_dates):
            rc._dates_cache[brand] = dict(slug_dates)
        yield _set


def _q(url):
    parts = urlsplit(url)
    assert (parts.scheme, parts.netloc, parts.path) == ("https", "endurelabs.app", "/sign-up")
    return {k: v[0] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}


def _keys(url):
    return [p.split("=", 1)[0] for p in urlsplit(url).query.split("&")]


class TestGravelGod:
    def test_full_link_for_a_gravel_race(self, fake_db, dates):
        dates(**{"unbound-200": "2027-06-05"})
        url = _endure_plan_url("gravelgod", "unbound-200", "Unbound 200", today=TODAY)
        assert _q(url) == {
            "race": "unbound-200", "race_name": "Unbound 200", "race_date": "2027-06-05",
            "distance_mi": "200", "elevation_ft": "11000", "discipline": "gravel",
            "utm_source": "gravel-god", "utm_medium": "email",
            "utm_campaign": "kit_endure_plan",
        }
        assert _keys(url) == ["race", "race_name", "race_date", "distance_mi", "elevation_ft",
                              "discipline", "utm_source", "utm_medium", "utm_campaign"]

    def test_mtb_race_keeps_its_discipline(self, fake_db, dates):
        dates()
        assert _q(_endure_plan_url("gravelgod", "leadville-100", "Leadville 100",
                                   today=TODAY))["discipline"] == "mtb"

    @pytest.mark.parametrize("slug", ["tour-divide", "atlas-mountain-race"])
    def test_bikepacking_gets_no_link(self, fake_db, dates, slug):
        dates()
        assert _endure_plan_url("gravelgod", slug, "Some Race", today=TODAY) is None

    def test_race_without_race_data_gets_no_link(self, fake_db, dates):
        dates(**{"no-such-race-xyz": "2027-06-05"})
        assert _endure_plan_url("gravelgod", "no-such-race-xyz", "Nope", today=TODAY) is None

    def test_unknown_discipline_value_gets_no_link(self, fake_db, dates, monkeypatch):
        import mission_control.services.sequence_engine as se
        monkeypatch.setattr(se, "_gravel_race", lambda slug: {
            "vitals": {"discipline": "cyclocross", "distance_mi": 40}})
        assert _endure_plan_url("gravelgod", "some-race", "Some Race", today=TODAY) is None

    def test_missing_discipline_is_gravel_like_the_race_page(self, fake_db, dates, monkeypatch):
        import mission_control.services.sequence_engine as se
        monkeypatch.setattr(se, "_gravel_race", lambda slug: {"vitals": {}})
        url = _endure_plan_url("gravelgod", "some-race", "Some Race", today=TODAY)
        assert _q(url)["discipline"] == "gravel"
        assert "distance_mi" not in _q(url) and "elevation_ft" not in _q(url)

    def test_numbers_are_plain(self, fake_db, dates, monkeypatch):
        import mission_control.services.sequence_engine as se
        monkeypatch.setattr(se, "_gravel_race", lambda slug: {
            "vitals": {"distance_mi": 62.137, "elevation_ft": 12000.0}})
        q = _q(_endure_plan_url("gravelgod", "some-race", "Some Race", today=TODAY))
        assert q["distance_mi"] == "62.14" and q["elevation_ft"] == "12000"
        assert _endure_number(1234567) == "1234567"
        assert _endure_number(10.5) == "10.5"
        for bad in (0, -3, None, "200", True, float("nan"), float("inf")):
            assert _endure_number(bad) is None

    def test_fact_omitted_alone_when_not_numeric(self, fake_db, dates, monkeypatch):
        import mission_control.services.sequence_engine as se
        monkeypatch.setattr(se, "_gravel_race", lambda slug: {
            "vitals": {"distance_mi": 50, "elevation_ft": "5,400 ft"}})
        q = _q(_endure_plan_url("gravelgod", "some-race", "Some Race", today=TODAY))
        assert q["distance_mi"] == "50" and "elevation_ft" not in q


class TestRaceDate:
    def test_omitted_when_unpublished(self, fake_db, dates):
        dates(**{"other-race": "2027-06-05"})
        assert "race_date" not in _q(_endure_plan_url("gravelgod", "unbound-200", "Unbound 200",
                                                       today=TODAY))

    @pytest.mark.parametrize("when", [TODAY, TODAY - timedelta(days=1),
                                      TODAY + timedelta(days=731)])
    def test_omitted_when_not_ahead_or_too_far(self, fake_db, dates, when):
        dates(**{"unbound-200": when.isoformat()})
        assert "race_date" not in _q(_endure_plan_url("gravelgod", "unbound-200", "Unbound 200",
                                                       today=TODAY))

    def test_kept_at_exactly_two_years(self, fake_db, dates):
        when = TODAY + timedelta(days=730)
        dates(**{"unbound-200": when.isoformat()})
        assert _q(_endure_plan_url("gravelgod", "unbound-200", "Unbound 200",
                                   today=TODAY))["race_date"] == when.isoformat()

    def test_omitted_when_unparseable(self, fake_db, dates):
        dates(**{"unbound-200": "2027: June TBD"})
        assert "race_date" not in _q(_endure_plan_url("gravelgod", "unbound-200", "Unbound 200",
                                                       today=TODAY))

    def test_date_is_read_for_the_lead_brand_only(self, fake_db, dates):
        dates("gravelgod", **{"mallorca-312": "2027-04-24"})
        q = _q(_endure_plan_url("roadielabs", "mallorca-312", "Mallorca 312", today=TODAY))
        assert "race_date" not in q


class TestRoadieLabs:
    def test_road_link(self, fake_db, dates):
        dates("roadielabs", **{"mallorca-312": "2027-04-24"})
        q = _q(_endure_plan_url("roadielabs", "mallorca-312", "Mallorca 312", today=TODAY))
        assert q == {"race": "mallorca-312", "race_name": "Mallorca 312",
                     "race_date": "2027-04-24", "discipline": "road",
                     "utm_source": "roadie-labs", "utm_medium": "email",
                     "utm_campaign": "kit_endure_plan"}

    def test_never_reads_gravel_race_data(self, fake_db, dates):
        # unbound-200 is a Gravel God profile: a Roadie lead with that slug
        # must not pick up its distance, climbing or discipline.
        dates("roadielabs")
        q = _q(_endure_plan_url("roadielabs", "unbound-200", "Unbound 200", today=TODAY))
        assert q["discipline"] == "road"
        assert "distance_mi" not in q and "elevation_ft" not in q


class TestNoLink:
    @pytest.mark.parametrize("brand", ["xcskilabs", "", None, "gravel-god", "GRAVELGOD"])
    def test_brands_without_the_offer(self, fake_db, dates, brand):
        dates(brand or "x", **{"unbound-200": "2027-06-05"})
        assert _endure_plan_url(brand, "unbound-200", "Unbound 200", today=TODAY) is None

    @pytest.mark.parametrize("slug", [None, "", "Unbound 200", "../x", "unbound_200",
                                      '"><script>', "https://evil.example.com/x"])
    def test_bad_slug(self, fake_db, dates, slug):
        dates()
        assert _endure_plan_url("gravelgod", slug, "Unbound 200", today=TODAY) is None
        assert _endure_plan_url("roadielabs", slug, "Unbound 200", today=TODAY) is None

    @pytest.mark.parametrize("name", [None, "", "   ", "\n\t"])
    def test_no_race_name(self, fake_db, dates, name):
        dates()
        assert _endure_plan_url("gravelgod", "unbound-200", name, today=TODAY) is None
        assert _endure_plan_url("roadielabs", "mallorca-312", name, today=TODAY) is None

    def test_slug_is_normalised(self, fake_db, dates):
        dates()
        assert _q(_endure_plan_url("gravelgod", "  Unbound-200 ", "Unbound 200",
                                   today=TODAY))["race"] == "unbound-200"


class TestEncoding:
    @pytest.mark.parametrize("name", [
        "Belgian Waffle Ride & Friends",
        'The "Big" Loop',
        "Rider's Choice",
        "Paris–Roubaix Challenge",
        "Étape du Tour",
        "Tour de l'Île 100%",
        "a=b&c=d#frag?x",
    ])
    def test_names_round_trip(self, fake_db, dates, name):
        dates("roadielabs")
        url = _endure_plan_url("roadielabs", "some-race", name, today=TODAY)
        assert _q(url)["race_name"] == name
        raw = re.search(r"(?:^|&)race_name=([^&]*)", urlsplit(url).query).group(1)
        assert not re.search(r"[\s\"'<>&#?=]", raw), raw

    def test_whitespace_collapsed_and_long_names_capped(self, fake_db, dates):
        dates("roadielabs")
        q = _q(_endure_plan_url("roadielabs", "some-race", "  Big \n  Loop  ", today=TODAY))
        assert q["race_name"] == "Big Loop"
        q = _q(_endure_plan_url("roadielabs", "some-race", "x" * 500, today=TODAY))
        assert len(q["race_name"]) == 120

    def test_link_is_attribute_safe_in_the_template(self, fake_db, dates):
        dates()
        html = _render_template("kit_endure_plan", {
            "contact_name": "Jen Rider",
            "source_data": {"race_slug": "unbound-200", "race_name": 'Unbound "200" & <b>'},
        }, brand="gravelgod")
        [href] = re.findall(r'href="(https://endurelabs\.app/[^"]*)"', html)
        assert "<" not in href and ">" not in href and '"' not in href and "'" not in href
        # & between parameters is escaped for the attribute; a browser reads
        # it back as the plain link.
        import html as _html
        assert _q(_html.unescape(href))["race_name"] == 'Unbound "200" & <b>'
        assert "&amp;race_name=" in href


class TestTemplateTokens:
    def _render(self, tpl, sd, brand):
        return _render_template(tpl, {"contact_name": "Jen Rider", "source_data": sd}, brand=brand)

    def test_caller_cannot_supply_the_link_or_terms(self, fake_db, dates):
        dates()
        html = self._render("kit_endure_plan", {
            "race_slug": "tour-divide", "race_name": "Tour Divide",
            "endure_plan_url": "https://evil.example.com/", "endure_trial_terms": "free forever",
        }, "gravelgod")
        assert "evil.example.com" not in html and "free forever" not in html
        assert "endurelabs.app" not in html

    def test_brand_comes_from_the_sequence_when_not_given(self, fake_db, dates):
        dates()
        base = {"contact_name": "Jen", "source_data": {"race_slug": "unbound-200",
                                                       "race_name": "Unbound 200"}}
        gg = _render_template("kit_endure_plan", {**base, "sequence_id": "nurture_v1"})
        assert "utm_source=gravel-god" in gg
        nothing = _render_template("kit_endure_plan", base)  # no sequence, no brand
        assert "endurelabs.app" not in nothing

    def test_utm_injection_leaves_the_endure_link_alone(self, fake_db, dates):
        dates()
        html = self._render("kit_endure_plan", {"race_slug": "unbound-200",
                                                "race_name": "Unbound 200"}, "gravelgod")
        before = re.findall(r'href="(https://endurelabs\.app/[^"]*)"', html)
        out = _inject_utm_params(html, "nurture_v1", "D", 1)
        after = re.findall(r'href="(https://endurelabs\.app/[^"]*)"', out)
        assert before == after and len(after) == 1
        assert after[0].count("utm_source=") == 1 and "utm_content" not in after[0]


def test_endure_offer_terms_match_the_site_wording():
    """One disclosure for every brand: Mission Control's copy must equal the
    approved wording in wordpress/endure_offer.py (read as text, not
    imported: Mission Control never imports wordpress/)."""
    site = (REPO / "wordpress" / "endure_offer.py").read_text()
    m = re.search(r'<p class="endure-trial-terms">([^<]+)</p>', site)
    assert m, "endure-trial-terms paragraph not found in wordpress/endure_offer.py"
    assert m.group(1) == ENDURE_TRIAL_TERMS


def test_mission_control_does_not_import_wordpress():
    src = (REPO / "mission_control" / "services" / "endure_offer.py").read_text()
    src += (REPO / "mission_control" / "services" / "sequence_engine.py").read_text()
    assert not re.search(r"^\s*(from|import)\s+wordpress\b", src, re.M)
    assert "endure_offer import" not in src.replace("mission_control.services.endure_offer import", "")
