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
    load_race,
    parse_race_date,
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
