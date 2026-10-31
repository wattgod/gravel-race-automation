"""Guards for the 2026-10-31 SEO crawl pass.

Each test pins one finding from that audit so it can't quietly come back:
orphaned hub/vs/tire/guide pages, redirect chains on the plan button, raw
template text in place of the cookie banner, duplicate race descriptions,
and a sitemap that the regular publish never uploaded.
"""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_neo_brutalist import build_explore_links, build_seo_description  # noqa: E402
from generate_prep_kit import build_pk_footer_cta  # noqa: E402
from generate_state_hubs import _slugify, group_races_by_state  # noqa: E402
from generate_tire_pages import build_internal_links_section  # noqa: E402
from generate_vs_pages import select_pairs  # noqa: E402


@pytest.fixture(scope="module")
def race_index():
    return json.loads((ROOT / "web" / "race-index.json").read_text(encoding="utf-8"))


def test_every_state_hub_and_vs_page_is_linked_from_a_race_page(race_index):
    linked = set()
    for r in race_index:
        html = build_explore_links({"slug": r["slug"], "name": r["name"]}, race_index)
        linked.update(re.findall(r'href="/race/([^/"]+)/"', html))
    hubs = {f"best-gravel-races-{_slugify(s)}" for s in group_races_by_state(race_index)}
    vs = {f"{a}-vs-{b}" for a, b in select_pairs(race_index)}
    assert hubs - linked == set()
    assert vs - linked == set()


def test_explore_links_only_point_at_generated_pages(race_index):
    hubs = {f"best-gravel-races-{_slugify(s)}" for s in group_races_by_state(race_index)}
    vs = {f"{a}-vs-{b}" for a, b in select_pairs(race_index)}
    for r in race_index[:60]:
        html = build_explore_links({"slug": r["slug"], "name": r["name"]}, race_index)
        for target in re.findall(r'href="/race/([^/"]+)/"', html):
            assert target in hubs or target in vs, target


def test_prep_kit_links_to_training_guide_only_when_it_exists():
    packs = ROOT / "web" / "race-packs"
    with_guide = next(p.stem for p in sorted(packs.glob("*.json"))
                      if json.loads(p.read_text(encoding="utf-8")).get("demands"))
    html = build_pk_footer_cta({"slug": with_guide, "name": "Example"})
    assert f'href="/race/{with_guide}/training-plan/"' in html
    html = build_pk_footer_cta({"slug": "no-such-race-pack", "name": "Example"})
    assert "/training-plan/" not in html


def test_tire_page_links_its_comparisons():
    html = build_internal_links_section(
        {"name": "Tire A"}, [], [("tire-a-vs-tire-b", "Tire B")])
    assert 'href="/tire/tire-a-vs-tire-b/"' in html


def test_race_description_without_tagline_is_unique():
    def rd(name):
        return {"name": name, "overall_score": 79, "tier": 2, "vitals": {"location": ""}}
    a, b = build_seo_description(rd("Race One")), build_seo_description(rd("Race Two"))
    assert a != b
    assert a.startswith("Race One")


@pytest.mark.parametrize("module", [
    "generate_insights.py", "generate_methodology.py",
    "generate_state_hubs.py", "generate_tier_hubs.py",
])
def test_no_unformatted_consent_banner_placeholder(module):
    # The tail of these templates is a plain string (not an f-string), so a
    # literal {get_consent_banner_html()} there shipped as visible text.
    src = (ROOT / "wordpress" / module).read_text(encoding="utf-8")
    tail = src[src.rfind("'<script>'") if "'<script>'" in src else src.rfind("'</script>'"):]
    assert "\n{get_consent_banner_html()}\n" not in tail


def test_plan_redirects_are_single_hop():
    src = (ROOT / "scripts" / "push_wordpress.py").read_text(encoding="utf-8")
    rules = dict(re.findall(r"^RewriteRule \^([\w-]+)/\?\$ (\S+) \[R=30\d", src, re.M))
    for source, target in rules.items():
        hop = target.strip("/").split("?")[0]
        assert hop not in rules, f"/{source}/ -> {target} redirects again"


def test_regular_publishes_ship_the_sitemap():
    src = (ROOT / "scripts" / "push_wordpress.py").read_text(encoding="utf-8")
    block = src.split("if args.deploy_content:", 1)[1].split("if args.deploy_all:", 1)[0]
    assert "args.sync_sitemap = True" in block
    wf = (ROOT / ".github" / "workflows" / "publish-site.yml").read_text(encoding="utf-8")
    assert "generate_sitemap.py" in wf
    assert "--sync-sitemap" in wf
