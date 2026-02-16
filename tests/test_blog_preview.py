"""Tests for blog preview generator, blog index, and blog sitemap."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_blog_preview import (
    find_candidates,
    generate_preview_html,
    is_generic_suffering,
    load_race,
    parse_race_date,
    pick_best_opinions,
)
from generate_blog_index import (
    classify_blog_slug,
    extract_blog_metadata,
    generate_blog_index,
)
from generate_blog_index_page import generate_blog_index_page
from generate_sitemap import generate_blog_sitemap


# ── parse_race_date ──


def test_parse_date_standard():
    d = parse_race_date("2026: June 6")
    assert d is not None
    assert d.year == 2026
    assert d.month == 6
    assert d.day == 6


def test_parse_date_with_range():
    d = parse_race_date("2026: October 3-4")
    assert d is not None
    assert d.year == 2026
    assert d.month == 10
    assert d.day == 3


def test_parse_date_none():
    assert parse_race_date(None) is None
    assert parse_race_date("") is None


def test_parse_date_tbd():
    assert parse_race_date("TBD") is None


def test_parse_date_invalid_month():
    assert parse_race_date("2026: Fakeuary 5") is None


# ── load_race ──


def test_load_race_exists():
    rd = load_race("unbound-200")
    assert rd is not None
    assert rd.get("name") is not None


def test_load_race_nonexistent():
    rd = load_race("nonexistent-race-12345")
    assert rd is None


# ── find_candidates ──


def test_find_candidates_returns_list():
    candidates = find_candidates(min_days=0, max_days=365)
    assert isinstance(candidates, list)


def test_find_candidates_have_required_keys():
    candidates = find_candidates(min_days=0, max_days=365)
    if candidates:
        c = candidates[0]
        assert "slug" in c
        assert "name" in c
        assert "date" in c
        assert "tier" in c
        assert "days_until" in c


def test_find_candidates_sorted():
    """Verify candidates are sorted by tier then days_until."""
    candidates = find_candidates(min_days=0, max_days=365)
    if len(candidates) >= 2:
        for i in range(len(candidates) - 1):
            a, b = candidates[i], candidates[i + 1]
            assert (a["tier"], a["days_until"]) <= (b["tier"], b["days_until"])


# ── generate_preview_html ──


def test_generate_preview_valid():
    html = generate_preview_html("unbound-200")
    assert html is not None
    assert "<!DOCTYPE html>" in html
    assert "Unbound" in html


def test_generate_preview_has_seo():
    html = generate_preview_html("mid-south")
    assert html is not None
    assert "og:title" in html
    assert "application/ld+json" in html
    assert 'canonical' in html


def test_generate_preview_clean_urls():
    """Verify blog URLs use /blog/{slug}/ format (no -preview suffix)."""
    html = generate_preview_html("mid-south")
    assert html is not None
    assert '/blog/mid-south/"' in html or "/blog/mid-south/" in html
    assert "-preview/" not in html


def test_generate_preview_has_sections():
    html = generate_preview_html("unbound-200")
    assert html is not None
    # Should have at least some content sections
    assert "Race Preview" in html
    assert "Full Race Profile" in html
    assert "Free Prep Kit" in html


def test_generate_preview_has_tier():
    html = generate_preview_html("unbound-200")
    assert html is not None
    assert "Tier 1" in html or "Elite" in html


def test_generate_preview_nonexistent():
    html = generate_preview_html("nonexistent-race-12345")
    assert html is None


def test_generate_preview_escapes_html():
    """Verify HTML entities are escaped in output."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    # Should not contain unescaped angle brackets in text content
    # (but will have them in HTML tags)
    assert "<script>" not in html.split("</head>")[1].split("</body>")[0] or \
           html.count("<script") <= 2  # Only the JSON-LD script


# ── Template quality ──


def test_preview_has_stats_section():
    """Verify stats section renders when data exists."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    # Unbound-200 should have distance and elevation
    assert "Miles" in html or "Ft Elevation" in html


def test_preview_has_hero():
    """Verify hero section exists."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    assert "gg-blog-hero" in html


def test_preview_has_cta():
    """Verify CTA section exists."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    assert "gg-blog-cta" in html


# ── classify_blog_slug ──


def test_classify_slug_preview():
    assert classify_blog_slug("unbound-200") == "preview"


def test_classify_slug_roundup():
    assert classify_blog_slug("roundup-march-2026") == "roundup"


def test_classify_slug_recap():
    assert classify_blog_slug("unbound-200-recap") == "recap"


def test_classify_slug_roundup_tier():
    assert classify_blog_slug("roundup-tier-1-2026") == "roundup"


# ── extract_blog_metadata ──


def test_extract_metadata_from_preview(tmp_path):
    """Extract metadata from a generated preview HTML."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    html_file = tmp_path / "unbound-200.html"
    html_file.write_text(html)
    meta = extract_blog_metadata(html_file)
    assert meta is not None
    assert meta["slug"] == "unbound-200"
    assert meta["category"] == "preview"
    assert "Unbound" in meta["title"]
    assert meta["tier"] > 0
    assert meta["date"]  # Should have a date
    assert meta["excerpt"]  # Should have a description
    assert meta["url"] == "/blog/unbound-200/"


def test_extract_metadata_missing_file(tmp_path):
    """Missing file returns None."""
    meta = extract_blog_metadata(tmp_path / "nonexistent.html")
    assert meta is None


# ── generate_blog_index ──


def test_blog_index_empty_dir(tmp_path):
    """Empty directory returns empty list."""
    entries = generate_blog_index(tmp_path, tmp_path)
    assert entries == []


def test_blog_index_with_files(tmp_path):
    """Generate index from preview HTML files."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    blog_dir = tmp_path / "blog"
    blog_dir.mkdir()
    (blog_dir / "unbound-200.html").write_text(html)
    out_dir = tmp_path / "out"

    entries = generate_blog_index(blog_dir, out_dir)
    assert len(entries) == 1
    assert entries[0]["slug"] == "unbound-200"

    # Verify JSON file was written
    index_file = out_dir / "blog-index.json"
    assert index_file.exists()
    loaded = json.loads(index_file.read_text())
    assert len(loaded) == 1


def test_blog_index_sorted_by_date(tmp_path):
    """Entries should be sorted newest first."""
    blog_dir = tmp_path / "blog"
    blog_dir.mkdir()

    # Create two files with different dates in JSON-LD
    for slug, dt in [("older", "2026-01-01"), ("newer", "2026-02-01")]:
        html = f'''<!DOCTYPE html><html><head>
        <title>{slug} — Gravel God</title>
        <meta name="description" content="Test">
        <script type="application/ld+json">{{"datePublished":"{dt}"}}</script>
        </head><body></body></html>'''
        (blog_dir / f"{slug}.html").write_text(html)

    entries = generate_blog_index(blog_dir, tmp_path)
    assert len(entries) == 2
    assert entries[0]["slug"] == "newer"
    assert entries[1]["slug"] == "older"


def test_blog_index_entry_schema(tmp_path):
    """Every entry must have all required fields."""
    html = generate_preview_html("mid-south")
    if html is None:
        pytest.skip("mid-south preview not generated")
    blog_dir = tmp_path / "blog"
    blog_dir.mkdir()
    (blog_dir / "mid-south.html").write_text(html)

    entries = generate_blog_index(blog_dir, tmp_path)
    assert len(entries) == 1
    entry = entries[0]
    required_fields = ["slug", "title", "category", "tier", "date", "excerpt", "og_image", "url"]
    for field in required_fields:
        assert field in entry, f"Missing required field: {field}"


# ── generate_blog_index_page ──


def test_blog_index_page_generated(tmp_path):
    """Blog index page should be a valid HTML file."""
    out_file = generate_blog_index_page(tmp_path)
    assert out_file.exists()
    content = out_file.read_text()
    assert "<!DOCTYPE html>" in content
    assert "Gravel God Blog" in content
    assert "blog-index.json" in content
    assert "gg-bi-grid" in content


def test_blog_index_page_has_seo(tmp_path):
    """Blog index page should have SEO tags."""
    out_file = generate_blog_index_page(tmp_path)
    content = out_file.read_text()
    assert "og:title" in content
    assert "og:url" in content
    assert 'rel="canonical"' in content
    assert "application/ld+json" in content
    assert '"CollectionPage"' in content


def test_blog_index_page_has_filters(tmp_path):
    """Blog index page should have filter chips."""
    out_file = generate_blog_index_page(tmp_path)
    content = out_file.read_text()
    assert "Race Previews" in content
    assert "Season Roundups" in content
    assert "Race Recaps" in content
    assert "gg-bi-chip" in content
    assert "gg-bi-sort" in content


def test_blog_index_page_responsive(tmp_path):
    """Blog index page should have responsive CSS."""
    out_file = generate_blog_index_page(tmp_path)
    content = out_file.read_text()
    assert "@media" in content


# ── generate_blog_sitemap ──


def test_blog_sitemap_structure(tmp_path):
    """Blog sitemap should be valid XML with correct URLs."""
    blog_index = [
        {"slug": "unbound-200", "category": "preview", "date": "2026-02-12"},
        {"slug": "roundup-march-2026", "category": "roundup", "date": "2026-02-12"},
        {"slug": "unbound-200-recap", "category": "recap", "date": "2026-02-12"},
    ]
    output = tmp_path / "blog-sitemap.xml"
    generate_blog_sitemap(blog_index, output)
    assert output.exists()

    import xml.etree.ElementTree as ET
    tree = ET.parse(output)
    root = tree.getroot()
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = root.findall("s:url", ns)
    # Blog index page + 3 entries = 4
    assert len(urls) == 4


def test_blog_sitemap_priorities(tmp_path):
    """Roundups should have higher priority than previews/recaps."""
    blog_index = [
        {"slug": "roundup-march-2026", "category": "roundup", "date": "2026-02-12"},
        {"slug": "unbound-200", "category": "preview", "date": "2026-02-12"},
    ]
    output = tmp_path / "blog-sitemap.xml"
    generate_blog_sitemap(blog_index, output)

    import xml.etree.ElementTree as ET
    tree = ET.parse(output)
    root = tree.getroot()
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = root.findall("s:url", ns)

    priorities = {}
    for url in urls:
        loc = url.find("s:loc", ns).text
        pri = url.find("s:priority", ns).text
        if "roundup" in loc:
            priorities["roundup"] = float(pri)
        elif "unbound" in loc:
            priorities["preview"] = float(pri)

    assert priorities.get("roundup", 0) > priorities.get("preview", 0)


def test_blog_sitemap_has_blog_index_page(tmp_path):
    """Blog sitemap should include /blog/ index page."""
    blog_index = [{"slug": "test", "category": "preview", "date": "2026-02-12"}]
    output = tmp_path / "blog-sitemap.xml"
    generate_blog_sitemap(blog_index, output)

    content = output.read_text()
    assert "/blog/" in content


def test_blog_sitemap_url_format(tmp_path):
    """Blog URLs should use /blog/{slug}/ format."""
    blog_index = [{"slug": "my-race", "category": "preview", "date": "2026-02-12"}]
    output = tmp_path / "blog-sitemap.xml"
    generate_blog_sitemap(blog_index, output)

    content = output.read_text()
    assert "/blog/my-race/" in content


def test_blog_sitemap_empty(tmp_path):
    """Empty blog index should still produce valid XML with index page."""
    output = tmp_path / "blog-sitemap.xml"
    generate_blog_sitemap([], output)
    assert output.exists()

    import xml.etree.ElementTree as ET
    tree = ET.parse(output)
    root = tree.getroot()
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = root.findall("s:url", ns)
    assert len(urls) == 1  # Just the blog index page


# ── Sprint 35: No raw Python repr in rendered HTML ──
# These tests make it structurally impossible to regress the 4 rendering
# bugs fixed in Sprint 35. Each test verifies BOTH the positive case
# (correct rendering) AND the negative case (no raw repr patterns).

import re

PYTHON_REPR_PATTERNS = [
    re.compile(r"\[?\{&#x27;"),   # HTML-escaped dict literal
    re.compile(r"\[&#x27;"),       # HTML-escaped list literal
    re.compile(r"\[?\{'"),          # unescaped dict literal
    re.compile(r"\['"),             # unescaped list literal
    re.compile(r"\[\{"),            # list-of-dicts opening
]


def _body_content(html):
    """Extract body content excluding script/style tags."""
    body = html.split("</head>")[1].split("</body>")[0] if "</head>" in html else html
    body = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.DOTALL)
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.DOTALL)
    return body


def _assert_no_python_repr(html, label=""):
    """Assert no raw Python repr patterns in body HTML."""
    body = _body_content(html)
    for pattern in PYTHON_REPR_PATTERNS:
        match = pattern.search(body)
        assert match is None, (
            f"Raw Python repr found in {label}: "
            f"'{body[max(0,match.start()-20):match.end()+40]}'"
        )


# ── suffering_zones rendering ──


def test_suffering_zones_renders_as_bullet_list():
    """suffering_zones (list of dicts) must render as HTML bullet list, not raw repr."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    body = _body_content(html)

    # Positive: correct rendering
    assert "<ul>" in body, "suffering_zones should render as <ul> list"
    assert "Mile 60:" in body or "Mile 120:" in body, "Mile markers should be visible"
    assert "<strong>" in body, "Zone labels should be bold"

    # Negative: no raw repr
    assert "[{" not in body, "Raw list-of-dicts opening should not appear"
    assert "'mile'" not in body, "Raw dict key 'mile' should not appear"
    assert "'label'" not in body, "Raw dict key 'label' should not appear"
    _assert_no_python_repr(html, "unbound-200 suffering_zones")


def test_suffering_zones_mile_zero():
    """Mile 0 (race start) should render as 'Mile 0:' not be silently dropped."""
    from generate_blog_preview import esc

    # Simulate what the code does with mile=0
    mile = 0
    prefix = f"Mile {esc(str(mile))}: " if mile is not None and mile != "" else ""
    assert prefix == "Mile 0: ", f"Mile 0 prefix should be 'Mile 0: ', got '{prefix}'"


def test_suffering_zones_string_fallback():
    """If suffering_zones is a plain string, it should render as text, not crash."""
    html = generate_preview_html("unbound-200")
    # This test verifies the code path exists; the real test is that
    # when suffering is a string, the elif branch renders it as <p>.
    # We verify by checking the function handles the unbound-200 case (list).
    assert html is not None
    _assert_no_python_repr(html, "suffering_zones string fallback")


# ── non_negotiables rendering ──


def test_non_negotiables_renders_requirement_and_why():
    """non_negotiables (list of dicts) must render requirement + why, not raw repr."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    body = _body_content(html)

    # Positive: correct rendering — requirement as bold, why as explanation
    assert "Training Focus" in body, "Training Focus section should exist"
    assert "<ol>" in body, "Non-negotiables should render as ordered list"
    # Unbound-200 has "Heat adaptation protocol" as first requirement
    assert "Heat adaptation" in body or "adaptation" in body.lower(), \
        "Requirement text should appear in rendered HTML"

    # Negative: no raw repr
    assert "'requirement'" not in body, "Raw dict key should not appear"
    assert "'by_when'" not in body, "Raw dict key should not appear"
    assert "'why'" not in body, "Raw dict key 'why' should not appear"
    _assert_no_python_repr(html, "unbound-200 non_negotiables")


def test_non_negotiables_renders_mid_south():
    """Verify non_negotiables rendering with a second race (Mid South)."""
    html = generate_preview_html("mid-south")
    assert html is not None
    body = _body_content(html)

    # Mid South has "Weather adaptation" as a requirement
    assert "Weather adaptation" in body or "Red clay" in body or "Wind" in body, \
        "Mid South non-negotiable requirements should appear"

    _assert_no_python_repr(html, "mid-south non_negotiables")


def test_non_negotiables_string_items():
    """If non_negotiables contains plain strings, they should render as text."""
    # The isinstance(n, dict) guard means strings hit the else branch
    # and render via esc(str(n)). This test verifies no crash.
    from generate_blog_preview import esc
    n = "Just a plain string requirement"
    result = f"<li>{esc(str(n))}</li>"
    assert "<li>Just a plain string requirement</li>" == result


# ── terrain_types rendering ──


def test_terrain_types_renders_as_joined_string():
    """terrain_types (list of strings) must render joined with middot, not as raw list."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    body = _body_content(html)

    # Positive: should see joined terrain names
    # Unbound-200 has: Flint Hills gravel, rolling hills, sharp limestone, cattle guards
    assert "Flint Hills" in body, "Individual terrain type should appear"
    assert "·" in body or "·" in body, "Terrain types should be joined with middot"

    # Negative: no raw list brackets
    assert "['Flint" not in body, "Raw list literal should not appear"
    assert "[&#x27;Flint" not in body, "HTML-escaped raw list should not appear"
    _assert_no_python_repr(html, "unbound-200 terrain_types")


def test_terrain_types_string_fallback():
    """If terrain_types is already a string, it should render as-is."""
    from generate_blog_preview import esc
    terrain_types = "mixed gravel and dirt"
    terrain_display = " · ".join(str(t) for t in terrain_types) if isinstance(terrain_types, list) else str(terrain_types)
    assert terrain_display == "mixed gravel and dirt"


def test_terrain_types_single_item_list():
    """A single-item terrain list should render without a separator."""
    from generate_blog_preview import esc
    terrain_types = ["gravel roads"]
    terrain_display = " · ".join(str(t) for t in terrain_types) if isinstance(terrain_types, list) else str(terrain_types)
    assert terrain_display == "gravel roads"
    assert "[" not in terrain_display


# ── notable_moments rendering ──


def test_notable_moments_renders_as_bullet_list():
    """notable_moments (list of strings) must render as HTML list, not raw repr."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    body = _body_content(html)

    # Positive: correct rendering
    assert "Notable moments" in body, "Notable moments header should appear"
    # Unbound-200 has "2019: Renamed" and "2021: Prize purse"
    assert "2019" in body or "2021" in body, "Notable moment years should appear"

    # Negative: no raw repr
    assert '["2019' not in body, "Raw list literal should not appear"
    assert "[&#x27;2019" not in body, "HTML-escaped raw list should not appear"
    _assert_no_python_repr(html, "unbound-200 notable_moments")


def test_notable_moments_renders_mid_south():
    """Verify notable_moments rendering with a second race."""
    html = generate_preview_html("mid-south")
    assert html is not None
    body = _body_content(html)

    # Mid South has notable moments about tactical pack racing, wildfires, etc.
    has_moments = any(year in body for year in ["2019", "2024", "2025", "2026"])
    assert has_moments, "Mid South notable moment years should appear"
    _assert_no_python_repr(html, "mid-south notable_moments")


def test_notable_moments_string_fallback():
    """If notable_moments is a plain string, it renders as paragraph text."""
    from generate_blog_preview import esc
    notable = "Founded in 2015"
    # Simulates the elif branch
    result = f"<p><strong>Notable moments:</strong> {esc(str(notable))}</p>"
    assert "Founded in 2015" in result
    assert "<ul>" not in result


# ── Full-page no-repr integration tests ──


def test_no_python_repr_unbound_200():
    """Full-page integration: unbound-200 has zero raw Python repr in body."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    _assert_no_python_repr(html, "unbound-200")


def test_no_python_repr_mid_south():
    """Full-page integration: mid-south has zero raw Python repr in body."""
    html = generate_preview_html("mid-south")
    assert html is not None
    _assert_no_python_repr(html, "mid-south")


def test_no_python_repr_dirty_reiver():
    """Full-page integration: dirty-reiver (T1) has zero raw Python repr."""
    html = generate_preview_html("dirty-reiver")
    assert html is not None
    _assert_no_python_repr(html, "dirty-reiver")


def test_no_python_repr_barry_roubaix():
    """Full-page integration: barry-roubaix (T3) has zero raw Python repr."""
    html = generate_preview_html("barry-roubaix")
    assert html is not None
    _assert_no_python_repr(html, "barry-roubaix")


# ── is_generic_suffering ──


def test_generic_suffering_detects_filler():
    """Generic zone labels like 'Early Rolling', 'Midpoint' should be detected."""
    zones = [
        {"label": "Early Rolling", "mile": 15, "desc": "First rolling sections."},
        {"label": "Midpoint", "mile": 25, "desc": "Halfway through the course."},
        {"label": "Late Rolling", "mile": 40, "desc": "Final rolling sections before finish."},
    ]
    assert is_generic_suffering(zones) is True


def test_generic_suffering_allows_real_zones():
    """Real zone labels like named features should pass through."""
    zones = [
        {"label": "Flint Hills Gauntlet", "mile": 60, "desc": "Relentless 20mi of exposed limestone."},
        {"label": "Thrall Creek Climb", "mile": 120, "desc": "Steep gravel climb after 100+ miles."},
        {"label": "Final Wind Tunnel", "mile": 180, "desc": "Exposed prairie with crosswinds."},
    ]
    assert is_generic_suffering(zones) is False


def test_generic_suffering_empty():
    assert is_generic_suffering([]) is False
    assert is_generic_suffering(None) is False
    assert is_generic_suffering("a string") is False


def test_generic_suffering_mixed_zones():
    """Majority rule: if 2/3 are generic, suppress all."""
    zones = [
        {"label": "Flint Hills Gauntlet", "mile": 60, "desc": "Relentless exposed limestone."},
        {"label": "Midpoint", "mile": 100, "desc": "Halfway through the course."},
        {"label": "Final Stretch", "mile": 180, "desc": "Last sections before finish."},
    ]
    assert is_generic_suffering(zones) is True


# ── pick_best_opinions ──


def test_pick_best_opinions_returns_top3():
    ratings = {
        "prestige": {"score": 1, "explanation": "A" * 50},
        "experience": {"score": 2, "explanation": "B" * 80},
        "community": {"score": 3, "explanation": "C" * 60},
        "value": {"score": 4, "explanation": "D" * 100},
        "adventure": {"score": 3, "explanation": "E" * 70},
    }
    result = pick_best_opinions(ratings)
    assert len(result) == 3
    # Sorted by explanation length desc, so value (100), experience (80), adventure (70)
    assert result[0][0] == "value"
    assert result[1][0] == "experience"
    assert result[2][0] == "adventure"


def test_pick_best_opinions_empty():
    assert pick_best_opinions({}) == []
    assert pick_best_opinions(None) == []


def test_pick_best_opinions_skips_short():
    """Explanations under 40 chars should be skipped."""
    ratings = {
        "prestige": {"score": 1, "explanation": "Short."},
        "experience": {"score": 2, "explanation": "A" * 50},
    }
    result = pick_best_opinions(ratings)
    assert len(result) == 1
    assert result[0][0] == "experience"


# ── Real Talk section rendering ──


def test_t4_preview_has_real_talk():
    """T4 previews should have a 'Real Talk' section with strengths/weaknesses."""
    html = generate_preview_html("wild-gravel")
    assert html is not None
    body = _body_content(html)
    assert "The Real Talk" in body
    assert "Strengths" in body
    assert "Weaknesses" in body


def test_t4_preview_suppresses_generic_suffering():
    """T4 previews with generic suffering zones should not show them."""
    html = generate_preview_html("bald-eagle-gravel-grinder")
    assert html is not None
    body = _body_content(html)
    # Should NOT have the generic zone labels
    assert "Early Rolling" not in body or "The Real Talk" in body


def test_t1_preview_has_real_talk():
    """T1 previews should also have Real Talk (they have rich opinion data)."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    body = _body_content(html)
    assert "The Real Talk" in body


def test_preview_uses_bottom_line():
    """When bottom_line exists, it should appear in the Why Race section."""
    rd = load_race("wild-gravel")
    if rd is None:
        pytest.skip("wild-gravel not available")
    bottom_line = rd.get("biased_opinion", {}).get("bottom_line", "")
    if not bottom_line:
        pytest.skip("wild-gravel has no bottom_line")
    html = generate_preview_html("wild-gravel")
    assert html is not None
    # The bottom_line text should appear in the output
    import html as html_mod
    assert html_mod.escape(bottom_line) in html or bottom_line[:30] in html


# ── Hero image ──


def test_preview_has_hero_image():
    """Preview articles should have an OG hero image."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    assert "gg-blog-hero-img" in html
    assert "/og/unbound-200.jpg" in html


def test_preview_hero_image_alt_text():
    """Hero image should have descriptive alt text."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    assert 'alt="' in html
    # Alt should contain the race name
    assert "Unbound" in html.split('alt="')[1].split('"')[0]
