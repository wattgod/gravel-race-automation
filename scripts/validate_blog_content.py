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

# Patterns that indicate raw Python repr leaked into HTML.
# Module-level so tests can import and verify them directly.
# Each pattern requires structural signals (key:value, item,item) to avoid
# false positives on normal English text.
PYTHON_REPR_PATTERNS = [
    # HTML-escaped single quotes (esc() converts ' to &#x27;)
    (re.compile(r"\{&#x27;\w+&#x27;:"), "HTML-escaped dict ({&#x27;key&#x27;:)"),
    (re.compile(r"\[&#x27;[^]]+&#x27;[,\]]"), "HTML-escaped list ([&#x27;item&#x27;,])"),
    # Unescaped single quotes
    (re.compile(r"\{'\w+':\s"), "single-quoted dict ({'key': )"),
    (re.compile(r"\['[^]]+?'[,\]]"), "single-quoted list (['item',])"),
    # Double-quoted (json.dumps output or f-string repr)
    (re.compile(r'\{"\w+":\s'), 'double-quoted dict ({"key": )'),
    (re.compile(r'\["[^]]+?"[,\]]'), 'double-quoted list (["item",])'),
    # List-of-dicts (most common bug pattern)
    (re.compile(r"\[\{['\"]"), "list-of-dicts ([{'...} or [{\"...}])"),
]


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

        # Tier is 1-4 for previews/recaps, 0 allowed for roundups
        tier = entry.get("tier", 0)
        if cat == "roundup":
            v.check(
                isinstance(tier, int) and 0 <= tier <= 4,
                f"{label}: tier {tier} valid for roundup (0-4)",
            )
        else:
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


def check_no_python_repr(v):
    """Detect raw Python repr (dict/list literals) leaked into blog HTML.

    Catches bugs where list-of-dicts or list-of-strings are rendered via
    str() instead of being formatted as readable HTML.
    """
    v.section("No Python Repr in HTML")

    if not BLOG_DIR.exists():
        v.check(False, "Blog directory exists")
        return

    html_files = sorted(BLOG_DIR.glob("*.html"))
    if not html_files:
        v.check(True, "No HTML files to check")
        return

    # Patterns that indicate raw Python repr leaked into HTML.
    # Covers: single-quoted, double-quoted, HTML-escaped, and list-of-dicts.
    # Each pattern is tested in test_validate_blog_content.py to prove it
    # catches the corresponding repr variant.
    repr_patterns = PYTHON_REPR_PATTERNS

    failures = []
    for f in html_files:
        content = f.read_text()

        # Extract body content, excluding <script> and <style> blocks
        body_match = re.search(r"<body[^>]*>(.*)</body>", content, re.DOTALL)
        if not body_match:
            continue
        body = body_match.group(1)

        # Remove <script> and <style> blocks from body
        body_clean = re.sub(r"<script[^>]*>.*?</script>", "", body, flags=re.DOTALL)
        body_clean = re.sub(r"<style[^>]*>.*?</style>", "", body_clean, flags=re.DOTALL)

        for pattern, desc in repr_patterns:
            match = pattern.search(body_clean)
            if match:
                # Get context around match
                start = max(0, match.start() - 20)
                end = min(len(body_clean), match.end() + 40)
                snippet = body_clean[start:end].replace("\n", " ").strip()
                failures.append((f.name, desc, snippet))
                break  # One failure per file is enough

    for fname, desc, snippet in failures:
        v.check(False, f"{fname}: raw {desc} found: ...{snippet}...")

    if not failures:
        v.check(True, f"All {len(html_files)} HTML files clean of Python repr")


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
        "validate_blog_content.py": "test_validate_blog_content.py",
    }

    for gen_name, test_name in gen_to_test.items():
        test_path = PROJECT_ROOT / "tests" / test_name
        v.check(test_path.exists(), f"{test_name} exists for {gen_name}")
        if not test_path.exists():
            continue

        content = test_path.read_text()
        test_count = len(re.findall(r"^\s*def test_", content, re.MULTILINE))
        # Each generator should have at least 10 tests
        v.check(
            test_count >= 10,
            f"{test_name}: {test_count} tests (min 10)",
        )


def check_date_diversity(v):
    """Detect when all articles have identical datePublished (shortcut signal).

    If every article shares the same date, it means the generator used
    date.today() instead of contextual dates. This check catches that.
    """
    v.section("Date Diversity")

    if not INDEX_PATH.exists():
        v.check(True, "blog-index.json not yet generated (skipping)")
        return

    try:
        data = json.loads(INDEX_PATH.read_text())
    except (json.JSONDecodeError, KeyError):
        return

    if len(data) < 3:
        v.check(True, f"Only {len(data)} entries — too few to check diversity")
        return

    dates = [e.get("date", "") for e in data]
    unique_dates = set(dates)

    # Previews must have diverse dates (race-specific dates)
    preview_dates = [e.get("date", "") for e in data if e.get("category") == "preview"]
    if len(preview_dates) >= 3:
        unique_preview = set(preview_dates)
        v.check(
            len(unique_preview) >= 2,
            f"Preview dates have diversity: {len(unique_preview)} unique dates "
            f"across {len(preview_dates)} previews"
            + (f" (ALL identical: {preview_dates[0]})" if len(unique_preview) == 1 else ""),
        )

    # Roundups must have diverse dates (month/season-specific dates)
    roundup_dates = [e.get("date", "") for e in data if e.get("category") == "roundup"]
    if len(roundup_dates) >= 3:
        unique_roundup = set(roundup_dates)
        v.check(
            len(unique_roundup) >= 2,
            f"Roundup dates have diversity: {len(unique_roundup)} unique dates "
            f"across {len(roundup_dates)} roundups"
            + (f" (ALL identical: {roundup_dates[0]})" if len(unique_roundup) == 1 else ""),
        )

    # Overall: should never have 100% identical dates when > 10 entries
    if len(data) >= 10:
        v.check(
            len(unique_dates) >= 3,
            f"Overall date diversity: {len(unique_dates)} unique dates "
            f"across {len(data)} entries (min 3)",
        )


def check_blog_index_ssr(v):
    """Verify blog index page has server-side rendered content.

    Crawlers cannot execute JavaScript. The blog index page must include
    pre-rendered card HTML so that search engines see actual content,
    not just an empty container with "Loading..." text.
    """
    v.section("Blog Index SSR")

    index_page = Path(__file__).resolve().parent.parent / "wordpress" / "output" / "blog-index.html"
    if not index_page.exists():
        v.check(False, "blog-index.html exists", warn_only=True)
        return

    content = index_page.read_text()

    # Grid must contain actual card HTML, not be empty
    # Look for gg-bi-card inside gg-bi-grid
    grid_match = re.search(r'id="gg-bi-grid"[^>]*>(.*?)</div>\s*<div class="gg-bi-empty"',
                           content, re.DOTALL)
    if grid_match:
        grid_content = grid_match.group(1).strip()
        card_count = grid_content.count("gg-bi-card")
        v.check(
            card_count >= 1,
            f"Blog index has {card_count} SSR cards in grid (min 1)",
        )
        v.check(
            card_count >= 10,
            f"Blog index has {card_count} SSR cards (expect 10+)",
            warn_only=True,
        )
    else:
        v.check(False, "Blog index grid element found")

    # Count text should show a number, not "Loading..."
    v.check(
        "Loading..." not in content,
        "Blog index count does not show 'Loading...'",
    )


def check_recap_pipeline(v):
    """Verify recap pipeline produces output when results data exists.

    If races have results data but no recap HTML files exist, the pipeline
    was never run — the recap feature is vaporware.
    """
    v.section("Recap Pipeline")

    race_data_dir = PROJECT_ROOT / "race-data"
    if not race_data_dir.exists():
        return

    # Count races with results data
    races_with_results = 0
    for f in race_data_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            race = data.get("race", data)
            results = race.get("results", {})
            years = results.get("years", {})
            for yr_data in years.values():
                if yr_data.get("winner_male") or yr_data.get("winner_female"):
                    races_with_results += 1
                    break
        except (json.JSONDecodeError, KeyError):
            continue

    # Count recap HTML files
    recap_count = 0
    if BLOG_DIR.exists():
        recap_count = len(list(BLOG_DIR.glob("*-recap.html")))

    v.check(
        races_with_results > 0 or True,  # Don't fail if no results yet
        f"Races with results data: {races_with_results}",
    )

    if races_with_results > 0:
        v.check(
            recap_count > 0,
            f"Recap HTML files exist ({recap_count} found) — "
            f"{races_with_results} races have results data",
        )
        if recap_count > 0:
            # At least 50% of races with results should have recaps
            ratio = recap_count / races_with_results
            v.check(
                ratio >= 0.5,
                f"Recap coverage: {recap_count}/{races_with_results} "
                f"({ratio:.0%}, expect >= 50%)",
                warn_only=True,
            )
    else:
        v.check(True, "No results data yet — recap pipeline not applicable",
                warn_only=False)


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


RACE_DATA_DIR = PROJECT_ROOT / "race-data"

# Takeaway quality patterns — raw URLs, markdown, citations, HTML tags
TAKEAWAY_BAD_PATTERNS = [
    (re.compile(r'https?://'), "bare URL"),
    (re.compile(r'#:~:text='), "URL text fragment"),
    (re.compile(r'\*\*'), "markdown bold **"),
    (re.compile(r'\[\d+\]'), "citation bracket [N]"),
    (re.compile(r'</?[a-zA-Z]'), "HTML tag"),
]


def check_hero_images(v):
    """Verify non-roundup blog articles have hero images."""
    v.section("Hero Images")

    if not BLOG_DIR.exists():
        v.check(False, "Blog directory exists")
        return

    html_files = sorted(BLOG_DIR.glob("*.html"))
    non_roundup = [f for f in html_files if not f.stem.startswith("roundup-")]

    if not non_roundup:
        v.check(True, "No non-roundup articles to check")
        return

    missing = []
    for f in non_roundup:
        content = f.read_text()
        if "gg-blog-hero-img" not in content:
            missing.append(f.stem)

    if missing:
        shown = missing[:5]
        extra = f" (+{len(missing)-5} more)" if len(missing) > 5 else ""
        v.check(False, f"Hero images missing from {len(missing)} articles: {', '.join(shown)}{extra}")
    else:
        v.check(True, f"All {len(non_roundup)} non-roundup articles have hero images")


def check_t4_content_quality(v):
    """Verify T4 previews don't have generic filler without Real Talk section."""
    v.section("T4 Content Quality")

    if not BLOG_DIR.exists():
        v.check(False, "Blog directory exists")
        return

    # Generic zone labels that indicate template filler
    generic_labels = {
        "early rolling", "midpoint", "late rolling", "final stretch",
        "early climb", "mid climb", "final descent", "early hills",
        "mid hills", "late hills", "early flat", "mid flat",
        "final push", "opening miles", "middle miles", "closing miles",
    }

    preview_files = [f for f in BLOG_DIR.glob("*.html")
                     if not f.stem.startswith("roundup-") and not f.stem.endswith("-recap")]

    failures = []
    for f in preview_files:
        content = f.read_text()
        content_lower = content.lower()

        # Check if this is a T4 race (Tier 4 or Roster in hero)
        if "tier 4" not in content_lower and "roster" not in content_lower:
            continue

        # Check for generic zone labels in the body
        has_generic = any(label in content_lower for label in generic_labels)
        has_real_talk = "the real talk" in content_lower

        if has_generic and not has_real_talk:
            failures.append(f.stem)

    if failures:
        shown = failures[:5]
        extra = f" (+{len(failures)-5} more)" if len(failures) > 5 else ""
        v.check(False, f"T4 previews with generic zones but no Real Talk: {', '.join(shown)}{extra}")
    else:
        v.check(True, "T4 previews have Real Talk section or no generic zones")


def check_takeaway_quality(v):
    """Verify race JSON takeaways are clean of URLs, markdown, citations, HTML."""
    v.section("Takeaway Quality")

    if not RACE_DATA_DIR.exists():
        v.check(False, "Race data directory exists")
        return

    dirty_races = []
    total_takeaways = 0

    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            race = data.get("race", data)
            results = race.get("results", {})
            for yr_data in results.get("years", {}).values():
                takeaways = yr_data.get("key_takeaways", [])
                for t in takeaways:
                    total_takeaways += 1
                    for pattern, desc in TAKEAWAY_BAD_PATTERNS:
                        if pattern.search(str(t)):
                            dirty_races.append((f.stem, desc, str(t)[:60]))
                            break
        except (json.JSONDecodeError, KeyError):
            continue

    if dirty_races:
        shown = dirty_races[:5]
        extra = f" (+{len(dirty_races)-5} more)" if len(dirty_races) > 5 else ""
        for slug, desc, snippet in shown:
            v.check(False, f"{slug}: takeaway has {desc}: {snippet}...")
        if extra:
            v.check(False, f"Additional dirty takeaways{extra}")
    else:
        v.check(True, f"All {total_takeaways} takeaways are clean")


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
    check_no_python_repr(v)
    check_hero_images(v)
    check_t4_content_quality(v)
    check_takeaway_quality(v)
    check_date_diversity(v)
    check_blog_index_ssr(v)
    check_recap_pipeline(v)
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
