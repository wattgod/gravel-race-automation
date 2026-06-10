"""Training-plan SEO pages — northstar Phase 2 commercial-intent play.

Guards: query-targeted head, FAQ schema validity, data-derived numbers,
the anti-shill structure (free guide first, personalization CTA), and
graceful skips when race-pack data is missing.
"""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from generate_training_plan_pages import (
    generate_page, load_pack, est_hours, fueling_numbers, build_faq,
)

RACE_DATA = Path(__file__).resolve().parent.parent / "race-data"


@pytest.fixture(scope="module")
def rd():
    d = json.loads((RACE_DATA / "unbound-200.json").read_text())
    race = d.get("race", d)
    race.setdefault("slug", "unbound-200")
    return race


@pytest.fixture(scope="module")
def pack():
    return load_pack("unbound-200")


@pytest.fixture(scope="module")
def html(rd, pack):
    return generate_page(rd, pack)


class TestSeoHead:
    def test_title_targets_query(self, html):
        m = re.search(r"<title>(.*?)</title>", html)
        assert "Training Plan" in m.group(1)
        assert "Unbound" in m.group(1)

    def test_canonical(self, html):
        assert 'rel="canonical" href="https://gravelgodcycling.com/race/unbound-200/training-plan/"' in html

    def test_faq_schema_valid_json(self, html):
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        data = json.loads(m.group(1))
        types = {d["@type"] for d in data}
        assert "FAQPage" in types
        faq = next(d for d in data if d["@type"] == "FAQPage")
        assert len(faq["mainEntity"]) >= 4

    def test_indexable(self, html):
        assert "noindex" not in html


class TestDerivedNumbers:
    def test_est_hours_reasonable(self, rd):
        h = est_hours(rd)
        assert 10 < h < 20  # 200mi gravel race, mid-pack

    def test_fueling_scales_with_hours(self):
        f = fueling_numbers(10)
        assert f["carbs_low"] == 600
        assert f["carbs_high"] == 900

    def test_zero_distance_no_fueling_claims(self):
        assert fueling_numbers(0) == {}
        assert est_hours({"vitals": {}}) == 0

    def test_faq_answers_are_race_specific(self, rd, pack):
        _, qa = build_faq(rd, pack)
        joined = " ".join(q + a for q, a in qa)
        assert "Unbound" in joined


class TestAntiShillStructure:
    def test_free_content_before_cta(self, html):
        assert html.find('id="demands"') < html.find('id="get-plan"')
        assert html.find('id="fueling"') < html.find('id="get-plan"')

    def test_prefilled_questionnaire_cta(self, html):
        assert "questionnaire/?race=unbound-200" in html

    def test_links_to_free_prep_kit(self, html):
        assert "/race/unbound-200/prep-kit/" in html

    def test_links_back_to_review(self, html):
        assert 'href="/race/unbound-200/"' in html


class TestSafety:
    def test_no_inline_handlers(self, html):
        assert "onclick=" not in html
        assert "onsubmit=" not in html

    def test_date_degradation(self, rd, pack):
        import copy
        r = copy.deepcopy(rd)
        r["vitals"]["date_specific"] = ""
        h = generate_page(r, pack)
        assert 'data-race-date="' not in h  # attribute absent (JS source still mentions the name)
        assert "$15/WK" in h  # generic price copy survives

    def test_no_pack_returns_skip(self):
        assert load_pack("no-such-slug-xyz") == {}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
