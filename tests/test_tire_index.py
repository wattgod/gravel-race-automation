"""/tire/ index: every race tire guide (by tier) and every tire page."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_tire_index as gti  # noqa: E402

RACES = [
    {"slug": "big-one", "name": "Big One", "tier": 1, "status": "active", "has_tire_guide": True},
    {"slug": "small-one", "name": "Small One", "tier": 4, "status": "inactive", "has_tire_guide": True},
    {"slug": "no-guide", "name": "No Guide", "tier": 2, "status": "active", "has_tire_guide": False},
]
TIRES = [{"id": "fast-tire-40", "name": "Fast Tire 40", "brand": "Acme", "tread_type": "file"}]


def test_links_every_guide_grouped_by_tier_and_every_review():
    html = gti.build_tire_index_page(RACES, TIRES)
    assert '<link rel="canonical" href="https://gravelgodcycling.com/tire/">' in html
    tier1 = html.split('id="tier-1"')[1].split("</section>")[0]
    assert 'href="/race/big-one/tires/"' in tier1
    assert 'href="/race/small-one/tires/"' in html.split('id="tier-4"')[1]
    assert "/race/no-guide/tires/" not in html
    assert 'href="/tire/fast-tire-40/">Fast Tire 40</a>' in html
    assert gti.get_ga4_head_snippet() in html and "@font-face" in html
    assert "onclick=" not in html and "innerHTML" not in html


def test_every_real_guide_and_tire_is_linked(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["generate_tire_index.py", "--output-dir", str(tmp_path)])
    gti.main()
    html = (tmp_path / "index.html").read_text()
    index = json.loads((ROOT / "web" / "race-index.json").read_text())
    for race in index:
        if race.get("has_tire_guide"):
            assert f'href="/race/{race["slug"]}/tires/"' in html
    for path in (ROOT / "data" / "tires").glob("*.json"):
        assert f'href="/tire/{json.loads(path.read_text())["id"]}/"' in html


def test_tire_pages_build_writes_the_index(tmp_path, monkeypatch):
    import generate_tire_pages as gtp

    monkeypatch.setattr(sys, "argv", ["generate_tire_pages.py", "--output-dir", str(tmp_path)])
    gtp.main()
    assert (tmp_path / "index.html").exists()


def test_review_pages_breadcrumb_to_the_index():
    source = (ROOT / "wordpress" / "generate_tire_pages.py").read_text()
    assert '<a href="/tire/">Tires</a> / {esc(tire["name"])}' in source


def test_guessed_urls_redirect_and_deploy_ships_the_index():
    import push_wordpress as pw

    assert "RewriteRule ^tires/?$ /tire/ [R=301,L]" in pw.REDIRECT_BLOCK
    assert "RewriteRule ^race/tires/?$ /tire/ [R=301,L]" in pw.REDIRECT_BLOCK
    source = (ROOT / "scripts" / "push_wordpress.py").read_text()
    assert 'root_files = ["index.html"] if (src / "index.html").exists()' in source


def test_sitemap_lists_the_index(tmp_path):
    import generate_sitemap as gs

    tire_dir = tmp_path / "wordpress" / "output" / "tire" / "fast-tire-40"
    tire_dir.mkdir(parents=True)
    (tire_dir / "index.html").write_text("<html></html>")
    out = tmp_path / "web" / "sitemap.xml"
    out.parent.mkdir()
    gs.generate_sitemap([], out)
    assert "<loc>https://gravelgodcycling.com/tire/</loc>" in out.read_text()


def test_method_section_publishes_the_constants_the_scorer_uses():
    import generate_tire_guide as g
    html = gti.build_method_section()
    assert 'id="method"' in html
    for value in (g.PUNCTURE_REF, g.PUNCTURE_W_SHARP, g.WET_REF, g.KNOB_EDGE_REF,
                  g.MUD_KNOB_REF, g.WIDTH_SHORT_W, g.UNTESTED_WIDTH_W, g.BIKE_AND_KIT_LB):
        assert f"{value:g}" in html, value
    for width in g.WIDTH_TARGETS.values():
        assert f"{width}mm" in html
    assert "bicyclerollingresistance.com" in html
    assert "We don't test tires ourselves" in html


def test_tire_guides_link_the_method():
    import generate_tire_guide as g
    assert 'href="/tire/#method"' in g.build_tire_cards([], {"tech_rating": 2}, "X", {"applicable": False})


def test_tire_pages_never_claim_a_review(tmp_path, monkeypatch):
    """We cite lab data and pick races; we don't test tires, so no title,
    heading or breadcrumb says Review. Community reviews are real and stay."""
    import re
    import generate_tire_pages as gtp

    monkeypatch.setattr(sys, "argv", ["generate_tire_pages.py", "--output-dir", str(tmp_path)])
    gtp.main()
    tires = [json.loads(f.read_text()) for f in (ROOT / "data" / "tires").glob("*.json")]
    db = {gtp.tire_slug(t): t for t in tires}
    pages = [p for p in tmp_path.glob("*/index.html") if p.parent.name in db]
    assert len(pages) == len(db)
    for page in pages:
        html = page.read_text()
        title = re.search(r"<title>(.*?)</title>", html).group(1)
        h1 = re.search(r"<h1>(.*?)</h1>", html).group(1)
        crumb = re.search(r'class="tp-breadcrumb">(.*?)</div>', html, re.S).group(1)
        for text in (title, h1, crumb):
            assert "Review" not in text, (page.parent.name, text)
        assert "Tire Reviews" not in html
        lab = db[page.parent.name].get("lab_tested")
        assert ("Rolling Resistance" in title) == bool(lab), title
        assert ("No lab test yet." in html) != bool(lab), page.parent.name


def test_vs_buttons_name_the_tire_only():
    source = (ROOT / "wordpress" / "generate_tire_vs_pages.py").read_text()
    assert "} Review</a>" not in source
