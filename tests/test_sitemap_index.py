"""Regression tests for indexability-safe sitemap composition."""

import sys
from pathlib import Path
from xml.etree import ElementTree


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from generate_sitemap import INDEXABLE_WORDPRESS_PAGES, generate_sitemap  # noqa: E402
from push_wordpress import build_sitemap_index  # noqa: E402


def _locations(xml: str) -> list[str]:
    root = ElementTree.fromstring(xml)
    return [node.text for node in root.iter() if node.tag.endswith("loc")]


def test_root_index_omits_noindex_page_and_category_sitemaps() -> None:
    locations = _locations(build_sitemap_index("2026-08-28", True))
    assert locations == [
        "https://gravelgodcycling.com/race-sitemap.xml",
        "https://gravelgodcycling.com/blog-sitemap.xml",
        "https://gravelgodcycling.com/post-sitemap.xml",
    ]


def test_generated_sitemap_owns_indexable_wordpress_pages(tmp_path: Path) -> None:
    output = tmp_path / "web" / "sitemap.xml"
    generate_sitemap([], output)
    locations = _locations(output.read_text(encoding="utf-8"))
    for path in INDEXABLE_WORDPRESS_PAGES:
        assert f"https://gravelgodcycling.com{path}" in locations

    for excluded_path in (
        "/questionnaire/",
        "/cart/",
        "/instructor-registration/",
        "/student-registration/",
        "/dashboard/",
    ):
        assert f"https://gravelgodcycling.com{excluded_path}" not in locations
