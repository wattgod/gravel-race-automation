#!/usr/bin/env python3
"""Validate blog content quality before deploy.

Automated quality gate that catches common shortcuts in blog content
generation. Runs as part of preflight validation (Phase 1).

Checks:
1. Blog-index.json schema validation
2. Generated HTML quality (SEO tags, required sections, clean URLs)
3. CSS duplication detection across generators
4. Real-data integration test coverage for extractors
5. Roundup completeness (minimum race counts, slug format)

Usage:
    python scripts/validate_blog_content.py
    python scripts/validate_blog_content.py --verbose
    python scripts/validate_blog_content.py --fix-css  # Report CSS duplication details
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BLOG_DIR = PROJECT_ROOT / "wordpress" / "output" / "blog"
INDEX_PATH = PROJECT_ROOT / "web" / "blog-index.json"
GENERATORS = [
    PROJECT_ROOT / "wordpress" / "generate_blog_preview.py",
    PROJECT_ROOT / "wordpress" / "generate_race_recap.py",
    PROJECT_ROOT / "wordpress" / "generate_season_roundup.py",
]
TEST_FILES = [
    PROJECT_ROOT / "tests" / "test_blog_preview.py",
    PROJECT_ROOT / "tests" / "test_race_recap.py",
    PROJECT_ROOT / "tests" / "test_season_roundup.py",
]

VERBOSE = False


class Validator:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def check(self, condition, label, *, warn_only=False):
        if condition:
            self.passed += 1
            if VERBOSE:
                print(f"  PASS  {label}")
        elif warn_only:
            self.warnings += 1
            print(f"  WARN  {label}")
        else:
            self.failed += 1
            print(f"  FAIL  {label}")

    def section(self, label):
        print(f"\n{'─' * 50}")
        print(f"  {label}")
        print(f"{'─' * 50}")


def check_blog_index_schema(v):
    """Validate blog-index.json has correct schema."""
    v.section("Blog Index Schema")

    if not INDEX_PATH.exists():
        v.check(False, "blog-index.json exists (run generate_blog_index.py first)",
                warn_only=True)
        return

    try:
        data = json.loads(INDEX_PATH.read_text())
    except json.JSONDecodeError as e:
        v.check(False, f"blog-index.json valid JSON: {e}")
        return

    v.check(isinstance(data, list), "blog-index.json is an array")
    if not isinstance(data, list):
        return

    required_fields = {"slug", "title", "category", "tier", "date", "excerpt", "url"}
    valid_categories = {"preview", "roundup", "recap"}

    for i, entry in enumerate(data):
        label = entry.get("slug", f"entry[{i}]")

        # Required fields present
        missing = required_fields - set(entry.keys())
        v.check(
            not missing,
            f"{label}: has all required fields (missing: {missing})" if missing
            else f"{label}: has all required fields",
        )

        # Category is valid
        cat = entry.get("category", "")
        v.check(
            cat in valid_categories,
            f"{label}: category '{cat}' is valid",
        )

        # Tier is 1-4
        tier = entry.get("tier", 0)
        v.check(
            isinstance(tier, int) and 1 <= tier <= 4,
            f"{label}: tier {tier} in range 1-4",
        )

        # Date format YYYY-MM-DD
        date_str = entry.get("date", "")
        v.check(
            bool(re.match(r"^\d{4}-\d{2}-\d{2}$", date_str)),
            f"{label}: date '{date_str}' matches YYYY-MM-DD",
        )

        # URL format /blog/{slug}/
        url = entry.get("url", "")
        v.check(
            url == f"/blog/{entry.get('slug', '')}/",
            f"{label}: URL '{url}' matches /blog/{{slug}}/ format",
        )

        # Title not empty
        v.check(
            bool(entry.get("title", "").strip()),
            f"{label}: title is not empty",
        )

        # Excerpt not empty
        v.check(
            bool(entry.get("excerpt", "").strip()),
            f"{label}: excerpt is not empty",
        )

        # Only check first 5 in non-verbose mode
        if not VERBOSE and i >= 4:
            remaining = len(data) - 5
            if remaining > 0:
                v.check(True, f"... and {remaining} more entries (use --verbose to check all)")
            break

    # Sorted by date descending
    dates = [e.get("date", "") for e in data]
    v.check(
        dates == sorted(dates, reverse=True),
        "blog-index.json sorted by date descending",
    )


def check_html_quality(v):
    """Validate generated blog HTML files."""
    v.section("Blog HTML Quality")

    if not BLOG_DIR.exists():
        v.check(False, f"Blog output directory exists: {BLOG_DIR}")
        return

    html_files = sorted(BLOG_DIR.glob("*.html"))
    v.check(len(html_files) > 0, f"Blog directory has HTML files ({len(html_files)} found)")
    if not html_files:
        return

    # Sample files: 1 preview, 1 roundup (if exists), 1 recap (if exists)
    samples = {}
    for f in html_files:
        stem = f.stem
        if stem.startswith("roundup-") and "roundup" not in samples:
            samples["roundup"] = f
        elif stem.endswith("-recap") and "recap" not in samples:
            samples["recap"] = f
        elif "preview" not in samples and not stem.startswith("roundup-") and not stem.endswith("-recap"):
            samples["preview"] = f

    for cat, filepath in samples.items():
        content = filepath.read_text()
        slug = filepath.stem
        label = f"{cat}:{slug}"

        # DOCTYPE
        v.check("<!DOCTYPE html>" in content, f"{label}: has DOCTYPE")

        # SEO: og:title
        v.check("og:title" in content, f"{label}: has og:title")

        # SEO: canonical
        v.check('rel="canonical"' in content, f"{label}: has canonical URL")

        # SEO: JSON-LD
        v.check("application/ld+json" in content, f"{label}: has JSON-LD")

        # SEO: meta description
        v.check('name="description"' in content, f"{label}: has meta description")

        # Clean URLs: no -preview suffix
        v.check("-preview/" not in content, f"{label}: no -preview/ in URLs")

        # Has hero section
        v.check(
            "gg-blog-hero" in content or "gg-roundup-hero" in content,
            f"{label}: has hero section",
        )

        # Has CTA section
        v.check(
            "gg-blog-cta" in content or "gg-roundup-cta" in content,
            f"{label}: has CTA section",
        )

        # No unescaped script tags in body
        if "</head>" in content and "</body>" in content:
            body = content.split("</head>")[1].split("</body>")[0]
            script_count = body.count("<script")
            v.check(
                script_count <= 1,  # Only JSON-LD allowed
                f"{label}: no unexpected <script> in body ({script_count} found)",
            )


def check_css_duplication(v, fix_css=False):
    """Detect CSS duplication across blog generators."""
    v.section("CSS Duplication")

    css_blocks_by_file = {}
    for gen_path in GENERATORS:
        if not gen_path.exists():
            v.check(False, f"{gen_path.name} exists")
            continue

        content = gen_path.read_text()
        # Extract all CSS rule selectors from inline <style> blocks
        blocks = re.findall(r"(\.gg-[\w-]+)\s*\{", content)
        css_blocks_by_file[gen_path.name] = set(blocks)

    if len(css_blocks_by_file) < 2:
        return

    # Find shared selectors across files
    files = list(css_blocks_by_file.keys())
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            shared = css_blocks_by_file[files[i]] & css_blocks_by_file[files[j]]
            # Some sharing is expected (brand classes). Flag if > 15 shared selectors.
            v.check(
                len(shared) <= 15,
                f"{files[i]} + {files[j]}: {len(shared)} shared CSS selectors"
                + (f" (max 15)" if len(shared) > 15 else ""),
                warn_only=True,
            )
            if fix_css and shared:
                print(f"\n    Shared between {files[i]} and {files[j]}:")
                for sel in sorted(shared):
                    print(f"      {sel}")


def check_extractor_test_coverage(v):
    """Verify extractors have real-data integration tests."""
    v.section("Extractor Test Coverage")

    test_recap = PROJECT_ROOT / "tests" / "test_race_recap.py"
    if not test_recap.exists():
        v.check(False, "test_race_recap.py exists")
        return

    content = test_recap.read_text()

    # Must have real-data integration tests (not just synthetic)
    real_data_tests = re.findall(r"def (test_extract_real_\w+)", content)
    v.check(
        len(real_data_tests) >= 3,
        f"Real-data integration tests: {len(real_data_tests)} found (min 3)",
    )

    # Must test at least 2 different dump formats
    dump_slugs = set()
    for test_name in real_data_tests:
        for slug in ["unbound", "bwr", "grinduro", "mid-south"]:
            if slug in test_name:
                dump_slugs.add(slug)
    v.check(
        len(dump_slugs) >= 2,
        f"Real-data tests cover {len(dump_slugs)} dump formats (min 2): {dump_slugs}",
    )

    # Must test both genders
    v.check(
        'gender="male"' in content or '"male"' in content,
        "Tests cover male extraction",
    )
    v.check(
        'gender="female"' in content or '"female"' in content,
        "Tests cover female extraction",
    )

    # Must test edge cases (empty dump, wrong year)
    v.check(
        "empty" in content.lower(),
        "Tests include empty-input edge case",
    )


def check_roundup_completeness(v):
    """Verify roundup slug conventions and minimum counts."""
    v.section("Roundup Completeness")

    if not BLOG_DIR.exists():
        v.check(False, "Blog directory exists")
        return

    roundups = sorted(BLOG_DIR.glob("roundup-*.html"))
    v.check(
        len(roundups) > 0,
        f"Roundup files exist ({len(roundups)} found)",
        warn_only=True,  # Roundups may not be generated yet
    )

    for f in roundups:
        slug = f.stem
        # Verify slug format
        valid = (
            re.match(r"roundup-[a-z]+-\d{4}$", slug)  # monthly
            or re.match(r"roundup-[a-z]+-[a-z]+-\d{4}$", slug)  # regional
            or re.match(r"roundup-tier-\d-\d{4}$", slug)  # tier
        )
        v.check(
            valid is not None,
            f"{slug}: valid roundup slug format",
        )


def check_test_file_coverage(v):
    """Verify each generator has a corresponding test file with minimum test count."""
    v.section("Test File Coverage")

    gen_to_test = {
        "generate_blog_preview.py": "test_blog_preview.py",
        "generate_race_recap.py": "test_race_recap.py",
        "generate_season_roundup.py": "test_season_roundup.py",
    }

    for gen_name, test_name in gen_to_test.items():
        test_path = PROJECT_ROOT / "tests" / test_name
        v.check(test_path.exists(), f"{test_name} exists for {gen_name}")
        if not test_path.exists():
            continue

        content = test_path.read_text()
        test_count = len(re.findall(r"^def test_", content, re.MULTILINE))
        # Each generator should have at least 10 tests
        v.check(
            test_count >= 10,
            f"{test_name}: {test_count} tests (min 10)",
        )


def check_blog_url_consistency(v):
    """Verify all blog URLs use /blog/{slug}/ format consistently."""
    v.section("Blog URL Consistency")

    for gen_path in GENERATORS:
        if not gen_path.exists():
            continue
        content = gen_path.read_text()
        name = gen_path.name

        # Check for -preview/ URLs (legacy pattern)
        v.check(
            "-preview/" not in content or "# legacy" in content.lower(),
            f"{name}: no -preview/ URLs in generated content",
        )

        # Check canonical URLs use /blog/ prefix.
        # Source code uses f-strings like href="{SITE_URL}/blog/{slug}/" or
        # href="{og_url}" where og_url is set to a /blog/ path.
        canonical_matches = re.findall(r'canonical.*?href="([^"]+)"', content)
        for url in canonical_matches:
            # The template string should contain /blog/ either directly
            # or via a variable that resolves to a /blog/ path.
            has_blog = "/blog/" in url
            if not has_blog and "{" in url:
                # Variable reference — check that its definition uses /blog/
                var_match = re.search(r"\{(\w+)\}", url)
                if var_match:
                    var_name = var_match.group(1)
                    has_blog = bool(re.search(
                        rf"{var_name}\s*=.*?/blog/", content
                    ))
            v.check(
                has_blog,
                f"{name}: canonical URL resolves to /blog/ prefix",
            )


def main():
    global VERBOSE
    parser = argparse.ArgumentParser(description="Validate blog content quality")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--fix-css", action="store_true",
                        help="Show detailed CSS duplication report")
    args = parser.parse_args()
    VERBOSE = args.verbose

    v = Validator()

    print(f"\n{'═' * 50}")
    print("  BLOG CONTENT QUALITY GATE")
    print(f"{'═' * 50}")

    check_blog_index_schema(v)
    check_html_quality(v)
    check_css_duplication(v, fix_css=args.fix_css)
    check_extractor_test_coverage(v)
    check_roundup_completeness(v)
    check_test_file_coverage(v)
    check_blog_url_consistency(v)

    print(f"\n{'═' * 50}")
    print(f"  RESULTS: {v.passed} passed, {v.failed} failed, {v.warnings} warnings")
    print(f"{'═' * 50}")

    if v.failed:
        print("\n  BLOG CONTENT QUALITY GATE: FAILED")
        print("  Fix failures before deploying.\n")
        return 1
    else:
        print("\n  BLOG CONTENT QUALITY GATE: PASSED")
        if v.warnings:
            print(f"  ({v.warnings} warnings — review before deploy)\n")
        else:
            print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
