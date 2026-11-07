"""Secondary "train in Endure" link on race pages (spec G-A)."""
import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wordpress"))

import endure_offer as offer  # noqa: E402
from generate_neo_brutalist import generate_page, normalize_race_data  # noqa: E402

TODAY = date(2026, 11, 1)


def _race(slug):
    return json.loads((ROOT / "race-data" / f"{slug}.json").read_text())["race"]


def test_link_carries_exactly_the_params_endure_reads():
    url = urlparse(offer.endure_plan_url(_race("unbound-200"), TODAY))
    assert (url.scheme, url.netloc, url.path) == ("https", "endurelabs.app", "/sign-up")
    q = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert q == {
        "race": "unbound-200",
        "race_name": _race("unbound-200")["name"],
        "race_date": "2027-06-05",
        "distance_mi": "200",
        "elevation_ft": "11000",
        "discipline": "gravel",
        "utm_source": "gravel-god",
        "utm_medium": "race-page",
        "utm_campaign": "endure_plan",
    }


def test_every_listed_race_builds_a_valid_link_and_is_in_the_2_year_window():
    assert 10 <= len(offer.ENDURE_PLAN_RACES) <= 20
    for slug in offer.ENDURE_PLAN_RACES:
        url = offer.endure_plan_url(_race(slug), TODAY)
        assert url, slug
        when = date.fromisoformat(parse_qs(urlparse(url).query)["race_date"][0])
        assert TODAY < when <= date(2028, 10, 31), slug


def test_no_link_for_unlisted_races_unsure_dates_or_past_dates():
    assert offer.endure_plan_url(_race("mid-south"), TODAY) is None  # not on the list
    r = _race("unbound-200")
    for text in ["2027: TBD", "2027: June 5 (PATTERN ESTIMATE)", "2027: June 5-7", "June 5", "2027: Feb 30", "2026: June 5"]:
        r2 = {**r, "vitals": {**r["vitals"], "date_specific": text}}
        assert offer.endure_plan_url(r2, TODAY) is None, text
    assert offer.endure_plan_url(r, date(2027, 6, 5)) is None  # race day itself
    for key in ("distance_mi", "elevation_ft"):
        r3 = {**r, "vitals": {**r["vitals"], key: None}}
        assert offer.endure_plan_url(r3, TODAY) is None, key


def test_page_shows_secondary_link_after_the_main_button():
    html = generate_page(normalize_race_data({"race": _race("unbound-200")}), [])
    assert "Or train in Endure: $24/month, 14 days free" in html
    main = html.index('data-cta="approved_custom_plan"')
    link = html.index('data-cta="endure_plan"')
    assert main < link
    tag = html[html.rindex("<a", 0, link): html.index("</a>", link)]
    assert 'class="gg-endure-link"' in tag and "gg-plan-cta" not in tag
    assert "&amp;utm_campaign=endure_plan" in tag
    assert "onclick" not in tag
    assert "endure_plan_click" in html


def test_page_without_listing_has_no_endure_link():
    html = generate_page(normalize_race_data({"race": _race("mid-south")}), [])
    assert 'data-cta="endure_plan"' not in html and "Or train in Endure" not in html


def test_listed_races_still_get_a_link_from_normalized_page_data():
    for slug in offer.ENDURE_PLAN_RACES:
        rd = normalize_race_data({"race": _race(slug)})
        assert offer.endure_plan_url(rd, TODAY), slug
