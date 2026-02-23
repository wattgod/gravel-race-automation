"""Tests for the Gravel God Training Guide topic cluster generator.

Phase A: Hub-and-spoke architecture — 1 pillar + 8 chapter pages.
Phase B: Database connection — race_reference, race_callout, decision_tree blocks.
Covers structure, SEO, brand compliance, accessibility, gating, and race integration.
"""
import json
import re
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

import generate_guide
import generate_guide_cluster as ggc
from generate_guide_cluster import (
    load_content,
    build_chapter_grid,
    build_prev_next_nav,
    build_chapter_gate,
    build_chapter_breadcrumb,
    build_chapter_progress,
    build_pillar_jsonld,
    build_chapter_jsonld,
    build_cluster_css,
    build_cluster_js,
    build_head,
    build_configurator_race_data,
    build_configurator_body,
    build_configurator_css,
    build_configurator_js,
    build_configurator_jsonld,
    CHAPTER_META,
    FREE_CHAPTERS,
    GATED_CHAPTERS,
)
from generate_guide import (
    render_race_reference,
    render_race_callout,
    render_decision_tree,
    load_race_index,
    BLOCK_RENDERERS,
)

# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture(scope="module")
def content():
    return load_content()


@pytest.fixture(scope="module")
def chapters(content):
    return content["chapters"]


@pytest.fixture(scope="module")
def output_dir():
    """Return the guide cluster output directory (must exist from generation)."""
    return Path(__file__).parent.parent / "wordpress" / "output" / "guide"


@pytest.fixture(scope="module")
def pillar_html(output_dir):
    path = output_dir / "index.html"
    if not path.exists():
        pytest.skip("Guide cluster not generated — run generate_guide_cluster.py first")
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def chapter_htmls(output_dir, chapters):
    """Return dict of chapter_id → HTML content."""
    result = {}
    for ch in chapters:
        path = output_dir / ch["id"] / "index.html"
        if path.exists():
            result[ch["id"]] = path.read_text(encoding="utf-8")
    if not result:
        pytest.skip("No chapter pages generated — run generate_guide_cluster.py first")
    return result


@pytest.fixture(scope="module")
def configurator_html(output_dir):
    """Return the configurator page HTML."""
    path = output_dir / "race-prep-configurator" / "index.html"
    if not path.exists():
        pytest.skip("Configurator page not generated — run generate_guide_cluster.py first")
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def all_htmls(pillar_html, chapter_htmls, configurator_html):
    """All 10 pages: pillar + 8 chapters + configurator."""
    return {"pillar": pillar_html, **chapter_htmls, "configurator": configurator_html}


# ── Structure Tests ───────────────────────────────────────


class TestOutputStructure:
    def test_pillar_page_exists(self, output_dir):
        assert (output_dir / "index.html").exists(), "Pillar page not generated"

    @pytest.mark.parametrize("slug", [
        "what-is-gravel-racing",
        "race-selection",
        "training-fundamentals",
        "workout-execution",
        "nutrition-fueling",
        "mental-training-race-tactics",
        "race-week",
        "post-race",
    ])
    def test_chapter_page_exists(self, output_dir, slug):
        path = output_dir / slug / "index.html"
        assert path.exists(), f"Chapter page missing: {slug}/index.html"

    def test_all_8_chapter_pages_exist(self, output_dir, chapters):
        for ch in chapters:
            path = output_dir / ch["id"] / "index.html"
            assert path.exists(), f"Chapter {ch['number']} ({ch['id']}) not generated"

    def test_pillar_not_empty(self, pillar_html):
        assert len(pillar_html) > 1000, "Pillar page suspiciously small"

    def test_chapter_pages_not_empty(self, chapter_htmls, chapters):
        for ch in chapters:
            html = chapter_htmls.get(ch["id"])
            assert html and len(html) > 1000, f"Chapter {ch['id']} suspiciously small"


# ── Pillar Page Tests ─────────────────────────────────────


class TestPillarPage:
    def test_pillar_has_chapter_grid(self, pillar_html):
        assert "gg-cluster-grid" in pillar_html, "Pillar missing chapter grid"

    def test_pillar_has_8_chapter_cards(self, pillar_html):
        card_count = pillar_html.count('class="gg-cluster-card')
        assert card_count >= 8, f"Expected 8+ chapter cards, found {card_count}"

    def test_pillar_chapter_links(self, pillar_html, chapters):
        for ch in chapters:
            href = f'/guide/{ch["id"]}/'
            assert href in pillar_html, f"Pillar missing link to {ch['id']}"

    def test_pillar_has_hero(self, pillar_html):
        assert "gg-hero" in pillar_html, "Pillar missing hero section"

    def test_pillar_has_cta_section(self, pillar_html):
        assert "gg-guide-cta" in pillar_html, "Pillar missing CTA section"

    def test_pillar_has_lock_icons_on_gated(self, pillar_html, chapters):
        for ch in chapters:
            if ch["gated"]:
                # The card for this chapter should have a lock indicator
                card_section = pillar_html[pillar_html.find(ch["id"]):]
                card_end = card_section.find("gg-cluster-card")
                if card_end > 0:
                    card_section = card_section[:card_end + 500]
                    assert "lock" in card_section.lower() or "🔒" in card_section, \
                        f"No lock indicator on gated chapter {ch['number']}"


# ── Chapter Page Tests ────────────────────────────────────


class TestChapterPages:
    def test_chapter_has_content(self, chapter_htmls, chapters):
        for ch in chapters:
            html = chapter_htmls.get(ch["id"], "")
            # Should have at least some section content
            assert "gg-guide-section" in html or ch["title"].lower() in html.lower(), \
                f"Chapter {ch['id']} appears to have no content"

    def test_chapter_has_breadcrumb(self, chapter_htmls, chapters):
        for ch in chapters:
            html = chapter_htmls.get(ch["id"], "")
            assert "gg-breadcrumb" in html, \
                f"Chapter {ch['id']} missing breadcrumb"

    def test_chapter_breadcrumb_has_3_items(self, chapter_htmls, chapters):
        for ch in chapters:
            html = chapter_htmls.get(ch["id"], "")
            # Breadcrumb should have: Home → Training Guide → Chapter
            bc_section = html[html.find("gg-breadcrumb"):html.find("</nav", html.find("gg-breadcrumb")) + 10] if "gg-breadcrumb" in html else ""
            home_link = "/guide/" in bc_section or "gravelgodcycling.com" in bc_section
            assert home_link, f"Chapter {ch['id']} breadcrumb missing guide link"

    def test_chapter_has_prev_next_nav(self, chapter_htmls, chapters):
        for ch in chapters:
            html = chapter_htmls.get(ch["id"], "")
            assert "gg-cluster-nav" in html, \
                f"Chapter {ch['id']} missing prev/next navigation"

    def test_first_chapter_no_prev(self, chapter_htmls, chapters):
        first = chapters[0]
        html = chapter_htmls.get(first["id"], "")
        nav_pos = html.find("gg-cluster-nav")
        if nav_pos >= 0:
            nav_section = html[nav_pos:nav_pos + 2000]
            assert "gg-cluster-nav-prev" not in nav_section or \
                "gg-cluster-nav-spacer" in nav_section, \
                "First chapter should not have a Previous link"

    def test_last_chapter_no_next(self, chapter_htmls, chapters):
        last = chapters[-1]
        html = chapter_htmls.get(last["id"], "")
        nav_pos = html.find("gg-cluster-nav")
        if nav_pos >= 0:
            nav_section = html[nav_pos:nav_pos + 2000]
            assert "gg-cluster-nav-next" not in nav_section or \
                "gg-cluster-nav-spacer" in nav_section, \
                "Last chapter should not have a Next link"

    def test_chapter_has_progress(self, chapter_htmls, chapters):
        for ch in chapters:
            html = chapter_htmls.get(ch["id"], "")
            assert "gg-cluster-progress" in html, \
                f"Chapter {ch['id']} missing progress bar"


# ── Gate Tests ────────────────────────────────────────────


class TestGating:
    def test_gated_chapters_have_gate(self, chapter_htmls, chapters):
        for ch in chapters:
            html = chapter_htmls.get(ch["id"], "")
            if ch["gated"]:
                assert 'id="gg-guide-gate"' in html, \
                    f"Gated chapter {ch['id']} missing gate overlay"

    def test_free_chapters_no_gate(self, chapter_htmls, chapters):
        for ch in chapters:
            html = chapter_htmls.get(ch["id"], "")
            if not ch["gated"]:
                assert 'id="gg-guide-gate"' not in html, \
                    f"Free chapter {ch['id']} should not have gate overlay"

    def test_gate_has_email_form(self, chapter_htmls, chapters):
        gated = [ch for ch in chapters if ch["gated"]]
        for ch in gated:
            html = chapter_htmls.get(ch["id"], "")
            assert "formsubmit.co" in html or 'type="email"' in html, \
                f"Gated chapter {ch['id']} missing email form"

    def test_gate_no_substack_iframe(self, chapter_htmls, chapters):
        for ch in chapters:
            html = chapter_htmls.get(ch["id"], "")
            assert "substackapi.com" not in html, \
                f"Chapter {ch['id']} still has Substack iframe (should use formsubmit.co)"

    def test_gate_has_localstorage_unlock(self, chapter_htmls, chapters):
        gated = [ch for ch in chapters if ch["gated"]]
        for ch in gated[:1]:  # Just check one — JS is shared
            html = chapter_htmls.get(ch["id"], "")
            assert "gg_guide_unlocked" in html, \
                f"Gate on {ch['id']} missing localStorage unlock key"


# ── SEO Tests ─────────────────────────────────────────────


class TestSEO:
    def test_each_page_has_canonical(self, all_htmls):
        for name, html in all_htmls.items():
            assert 'rel="canonical"' in html, f"Page '{name}' missing canonical link"

    def test_each_page_has_unique_title(self, all_htmls):
        titles = []
        for name, html in all_htmls.items():
            m = re.search(r"<title>(.+?)</title>", html)
            assert m, f"Page '{name}' missing <title> tag"
            titles.append(m.group(1))
        assert len(titles) == len(set(titles)), \
            f"Duplicate titles found: {[t for t in titles if titles.count(t) > 1]}"

    def test_each_page_has_meta_description(self, all_htmls):
        for name, html in all_htmls.items():
            assert 'name="description"' in html, \
                f"Page '{name}' missing meta description"

    def test_unique_meta_descriptions(self, all_htmls):
        descs = []
        for name, html in all_htmls.items():
            m = re.search(r'name="description"\s+content="([^"]+)"', html)
            if m:
                descs.append(m.group(1))
        assert len(descs) == len(set(descs)), "Duplicate meta descriptions found"

    def test_pillar_has_jsonld(self, pillar_html):
        assert "application/ld+json" in pillar_html, "Pillar missing JSON-LD"

    def test_pillar_jsonld_has_course(self, pillar_html):
        # Extract JSON-LD blocks
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            pillar_html, re.DOTALL
        )
        found_course = any('"Course"' in b for b in blocks)
        assert found_course, "Pillar JSON-LD missing Course schema"

    def test_pillar_jsonld_has_breadcrumb(self, pillar_html):
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            pillar_html, re.DOTALL
        )
        found_bc = any('"BreadcrumbList"' in b for b in blocks)
        assert found_bc, "Pillar JSON-LD missing BreadcrumbList"

    def test_chapter_jsonld_has_article(self, chapter_htmls, chapters):
        for ch in chapters:
            html = chapter_htmls.get(ch["id"], "")
            blocks = re.findall(
                r'<script type="application/ld\+json">(.*?)</script>',
                html, re.DOTALL
            )
            found_article = any('"Article"' in b for b in blocks)
            assert found_article, \
                f"Chapter {ch['id']} JSON-LD missing Article schema"

    def test_chapter_jsonld_has_breadcrumb(self, chapter_htmls, chapters):
        for ch in chapters:
            html = chapter_htmls.get(ch["id"], "")
            blocks = re.findall(
                r'<script type="application/ld\+json">(.*?)</script>',
                html, re.DOTALL
            )
            found_bc = any('"BreadcrumbList"' in b for b in blocks)
            assert found_bc, \
                f"Chapter {ch['id']} JSON-LD missing BreadcrumbList"

    def test_prev_next_link_tags(self, chapter_htmls, chapters):
        for i, ch in enumerate(chapters):
            html = chapter_htmls.get(ch["id"], "")
            if i > 0:
                assert 'rel="prev"' in html, \
                    f"Chapter {ch['id']} missing <link rel='prev'>"
            if i < len(chapters) - 1:
                assert 'rel="next"' in html, \
                    f"Chapter {ch['id']} missing <link rel='next'>"

    def test_pillar_has_no_prev_next(self, pillar_html):
        assert 'rel="prev"' not in pillar_html, "Pillar should not have prev link"
        assert 'rel="next"' not in pillar_html, "Pillar should not have next link"

    def test_canonical_urls_correct(self, all_htmls, chapters):
        # Pillar canonical should be /guide/
        m = re.search(r'rel="canonical"\s+href="([^"]+)"', all_htmls["pillar"])
        assert m and m.group(1).endswith("/guide/"), \
            f"Pillar canonical wrong: {m.group(1) if m else 'not found'}"

        # Chapter canonicals
        for ch in chapters:
            html = all_htmls.get(ch["id"], "")
            m = re.search(r'rel="canonical"\s+href="([^"]+)"', html)
            expected = f'/guide/{ch["id"]}/'
            assert m and expected in m.group(1), \
                f"Chapter {ch['id']} canonical wrong: {m.group(1) if m else 'not found'}"

    def test_og_image_on_all_pages(self, all_htmls):
        for name, html in all_htmls.items():
            assert 'og:image' in html, f"Page '{name}' missing og:image"


# ── Brand Compliance Tests ────────────────────────────────


class TestBrandCompliance:
    def test_no_raw_hex_in_cluster_css(self):
        css = build_cluster_css()
        hex_matches = re.findall(r'#[0-9a-fA-F]{3,8}', css)
        assert not hex_matches, \
            f"Raw hex values in cluster CSS: {hex_matches[:5]}"

    def test_no_border_radius_in_cluster_css(self):
        css = build_cluster_css()
        assert "border-radius" not in css, \
            "border-radius found in cluster CSS (neo-brutalist rule)"

    def test_no_box_shadow_in_cluster_css(self):
        css = build_cluster_css()
        assert "box-shadow" not in css, \
            "box-shadow found in cluster CSS (neo-brutalist rule)"

    def test_uses_shared_header(self, all_htmls):
        for name, html in all_htmls.items():
            assert "gg-site-header" in html, \
                f"Page '{name}' missing shared site header"

    def test_uses_shared_footer(self, all_htmls):
        for name, html in all_htmls.items():
            assert "gg-mega-footer" in html, \
                f"Page '{name}' missing shared mega footer"

    def test_uses_consent_banner(self, all_htmls):
        for name, html in all_htmls.items():
            assert "gg-consent-banner" in html, \
                f"Page '{name}' missing cookie consent banner"

    def test_uses_ga4_snippet(self, all_htmls):
        for name, html in all_htmls.items():
            assert "gtag" in html or "G-EJJZ9T6M52" in html, \
                f"Page '{name}' missing GA4 snippet"

    def test_uses_design_tokens(self, all_htmls):
        for name, html in all_htmls.items():
            assert "--gg-color-" in html, \
                f"Page '{name}' not using design tokens"


# ── Accessibility Tests ───────────────────────────────────


class TestAccessibility:
    def test_all_images_have_alt(self, all_htmls):
        for name, html in all_htmls.items():
            # Find <img> tags without alt
            imgs = re.findall(r'<img\b[^>]*>', html)
            for img in imgs:
                assert 'alt=' in img, \
                    f"Image without alt in '{name}': {img[:80]}"

    def test_no_circles_in_svg(self, all_htmls):
        for name, html in all_htmls.items():
            svgs = re.findall(r'<svg\b.*?</svg>', html, re.DOTALL)
            for svg in svgs:
                assert "<circle" not in svg, \
                    f"SVG with <circle> in '{name}' (brand rule: use rect only)"

    def test_gate_has_form_label(self, chapter_htmls, chapters):
        gated = [ch for ch in chapters if ch["gated"]]
        for ch in gated[:1]:
            html = chapter_htmls.get(ch["id"], "")
            gate_section = html[html.find("gg-cluster-gate"):] if "gg-cluster-gate" in html else ""
            has_label = ('for="' in gate_section or
                         'aria-label' in gate_section or
                         '<label' in gate_section or
                         'placeholder=' in gate_section)
            assert has_label, \
                f"Gate form on {ch['id']} missing label/aria-label for email input"


# ── Infographic Tests ─────────────────────────────────────


class TestInfographics:
    def test_all_infographics_render(self, chapter_htmls, content):
        """All infographic asset_ids in content produce output in chapter pages."""
        hero_ids = {f"ch{i}-hero" for i in range(1, 9)}
        missing = []
        for ch in content["chapters"]:
            html = chapter_htmls.get(ch["id"], "")
            for sec in ch["sections"]:
                for block in sec["blocks"]:
                    if block.get("type") == "image":
                        aid = block["asset_id"]
                        if aid in hero_ids:
                            continue
                        # Check the infographic rendered (has the wrapper class)
                        if "gg-infographic-wrap" not in html and aid not in html:
                            missing.append(f"{ch['id']}/{aid}")
        assert not missing, f"Missing infographic output: {missing}"


# ── Chapter Content Builder Tests ─────────────────────────


class TestBuildFunctions:
    def test_chapter_grid_has_8_cards(self, chapters):
        grid = build_chapter_grid(chapters)
        # Count actual card <a> elements (data-chapter attribute is unique to cards)
        card_count = len(re.findall(r'data-chapter="\d+"', grid))
        assert card_count == 8, f"Expected 8 chapter cards, got {card_count}"

    def test_chapter_grid_links(self, chapters):
        grid = build_chapter_grid(chapters)
        for ch in chapters:
            assert f'/guide/{ch["id"]}/' in grid

    def test_prev_next_first_chapter(self, chapters):
        nav = build_prev_next_nav(chapters[0], chapters)
        assert "Previous" not in nav or "placeholder" in nav

    def test_prev_next_last_chapter(self, chapters):
        nav = build_prev_next_nav(chapters[-1], chapters)
        assert "Next" not in nav or "placeholder" in nav

    def test_prev_next_middle_chapter(self, chapters):
        nav = build_prev_next_nav(chapters[3], chapters)
        assert 'rel="prev"' in nav or chapters[2]["id"] in nav
        assert 'rel="next"' in nav or chapters[4]["id"] in nav

    def test_gate_html_for_gated_chapter(self, chapters):
        gated_ch = [ch for ch in chapters if ch["gated"]][0]
        gate = build_chapter_gate(gated_ch)
        assert "gg-cluster-gate" in gate
        assert "email" in gate.lower()

    def test_free_chapter_page_no_gated_content_div(self, chapter_htmls, chapters):
        """Free chapter pages should not have the gated content wrapper in body HTML."""
        free = [ch for ch in chapters if not ch["gated"]]
        for ch in free:
            html = chapter_htmls.get(ch["id"], "")
            # Extract body content (after </style> tags) to avoid matching CSS definitions
            body_start = html.rfind("</style>")
            body_html = html[body_start:] if body_start > 0 else html
            assert 'class="gg-cluster-gated-content"' not in body_html, \
                f"Free chapter {ch['id']} has gated-content wrapper in body"

    def test_breadcrumb_has_guide_link(self, chapters):
        bc = build_chapter_breadcrumb(chapters[0])
        assert "/guide/" in bc

    def test_breadcrumb_has_chapter_title(self, chapters):
        bc = build_chapter_breadcrumb(chapters[0])
        assert chapters[0]["title"] in bc

    def test_progress_bar(self, chapters):
        prog = build_chapter_progress(chapters[0], chapters)
        assert "gg-cluster-progress" in prog
        assert "1" in prog  # Chapter 1

    def test_cluster_css_not_empty(self):
        css = build_cluster_css()
        assert len(css) > 100

    def test_cluster_js_not_empty(self):
        js = build_cluster_js()
        assert len(js) > 100

    def test_cluster_js_has_gate_unlock(self):
        js = build_cluster_js()
        assert "gg_guide_unlocked" in js


# ── JSON-LD Tests ─────────────────────────────────────────


class TestJsonLD:
    def test_pillar_jsonld_valid(self, content):
        jsonld = build_pillar_jsonld(content)
        # Should be valid JSON inside script tags
        raw = re.search(r'<script type="application/ld\+json">(.*?)</script>',
                        jsonld, re.DOTALL)
        assert raw, "No JSON-LD block found"
        data = json.loads(raw.group(1))
        # Could be a list of schemas
        if isinstance(data, list):
            types = [d.get("@type") for d in data]
        else:
            types = [data.get("@type")]
        assert "Course" in types or any("Course" in str(t) for t in types), \
            f"Expected Course type, got {types}"

    def test_chapter_jsonld_valid(self, content):
        ch = content["chapters"][0]
        jsonld = build_chapter_jsonld(ch, content)
        raw = re.search(r'<script type="application/ld\+json">(.*?)</script>',
                        jsonld, re.DOTALL)
        assert raw, "No JSON-LD block found"
        data = json.loads(raw.group(1))
        if isinstance(data, list):
            types = [d.get("@type") for d in data]
        else:
            types = [data.get("@type")]
        assert "Article" in types or any("Article" in str(t) for t in types), \
            f"Expected Article type, got {types}"


# ── CHAPTER_META Tests ────────────────────────────────────


class TestChapterMeta:
    def test_all_chapters_have_meta(self, chapters):
        for ch in chapters:
            assert ch["id"] in CHAPTER_META, \
                f"Chapter {ch['id']} missing from CHAPTER_META"

    def test_meta_has_title_suffix(self):
        for slug, meta in CHAPTER_META.items():
            assert "title_suffix" in meta, f"CHAPTER_META[{slug}] missing title_suffix"

    def test_meta_has_description(self):
        for slug, meta in CHAPTER_META.items():
            assert "description" in meta, f"CHAPTER_META[{slug}] missing description"

    def test_meta_descriptions_unique(self):
        descs = [m["description"] for m in CHAPTER_META.values()]
        assert len(descs) == len(set(descs)), "Duplicate CHAPTER_META descriptions"

    def test_meta_descriptions_reasonable_length(self):
        for slug, meta in CHAPTER_META.items():
            desc = meta["description"]
            assert 50 <= len(desc) <= 160, \
                f"CHAPTER_META[{slug}] description length {len(desc)} (should be 50-160)"


# ── Constants Tests ───────────────────────────────────────


class TestConstants:
    def test_free_chapters(self):
        assert FREE_CHAPTERS == {1, 2, 3}

    def test_gated_chapters(self):
        assert GATED_CHAPTERS == {4, 5, 6, 7, 8}

    def test_free_and_gated_cover_all(self):
        assert FREE_CHAPTERS | GATED_CHAPTERS == {1, 2, 3, 4, 5, 6, 7, 8}

    def test_no_overlap(self):
        assert FREE_CHAPTERS & GATED_CHAPTERS == set()


# ── HTML Validity Tests ───────────────────────────────────


class TestHTMLValidity:
    def test_all_pages_have_doctype(self, all_htmls):
        for name, html in all_htmls.items():
            assert html.strip().startswith("<!DOCTYPE html>") or \
                html.strip().startswith("<!doctype html>"), \
                f"Page '{name}' missing DOCTYPE"

    def test_all_pages_have_lang(self, all_htmls):
        for name, html in all_htmls.items():
            assert 'lang="en"' in html, f"Page '{name}' missing lang='en'"

    def test_all_pages_have_charset(self, all_htmls):
        for name, html in all_htmls.items():
            assert 'charset="utf-8"' in html.lower() or \
                'charset="UTF-8"' in html, \
                f"Page '{name}' missing charset"

    def test_all_pages_have_viewport(self, all_htmls):
        for name, html in all_htmls.items():
            assert "viewport" in html, f"Page '{name}' missing viewport meta"

    def test_no_broken_template_vars(self, all_htmls):
        for name, html in all_htmls.items():
            # Check for un-interpolated Python f-string vars
            assert "{SITE_BASE_URL}" not in html, \
                f"Page '{name}' has un-interpolated SITE_BASE_URL"
            assert "{SUBSTACK_URL}" not in html, \
                f"Page '{name}' has un-interpolated SUBSTACK_URL"

    def test_consent_uses_regex_not_indexOf(self, all_htmls):
        for name, html in all_htmls.items():
            # Consent check must use regex, not indexOf
            if "gg_consent" in html and "indexOf" in html:
                # Check if indexOf is used specifically for consent
                idx_pos = html.find("indexOf")
                context = html[max(0, idx_pos - 50):idx_pos + 50]
                assert "gg_consent" not in context, \
                    f"Page '{name}' uses indexOf for consent check (must use regex)"


# ══════════════════════════════════════════════════════════════
# Phase B: Database Connection — Race-Connected Block Renderers
# ══════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def race_index():
    """Load race index for renderer tests."""
    return load_race_index()


@pytest.fixture(scope="module", autouse=True)
def activate_race_index(race_index):
    """Set module-level _RACE_INDEX for renderer functions."""
    old = generate_guide._RACE_INDEX
    generate_guide._RACE_INDEX = race_index
    yield
    generate_guide._RACE_INDEX = old


# ── Race Reference Renderer ─────────────────────────────────


class TestRaceReference:
    def test_renders_linked_race_name(self, race_index):
        html = render_race_reference({"slug": "unbound-200", "context": "elevation"})
        assert "gg-race-ref" in html
        assert 'href="/race/unbound-200/"' in html
        assert "Unbound" in html

    def test_renders_elevation_stat(self, race_index):
        html = render_race_reference({"slug": "unbound-200", "context": "elevation"})
        assert "ft gain" in html

    def test_renders_distance_stat(self, race_index):
        html = render_race_reference({"slug": "unbound-200", "context": "distance"})
        assert "miles" in html

    def test_renders_climate_stat(self, race_index):
        html = render_race_reference({"slug": "gravel-locos", "context": "climate"})
        assert "Climate:" in html

    def test_renders_technicality_stat(self, race_index):
        html = render_race_reference({"slug": "bwr-california", "context": "technicality"})
        # Technicality uses labels, not "Technicality: N/5"
        assert any(label in html for label in ["Paved", "Smooth gravel", "Mixed", "Technical", "Extreme"])

    def test_renders_generic_score_dimension(self, race_index):
        html = render_race_reference({"slug": "unbound-200", "context": "adventure"})
        assert "Adventure:" in html
        assert "/5" in html

    def test_renders_tier(self, race_index):
        html = render_race_reference({"slug": "unbound-200", "context": "elevation"})
        assert "Tier 1" in html

    def test_missing_slug_returns_comment(self):
        html = render_race_reference({"slug": "nonexistent-race-xyz", "context": "distance"})
        assert "<!--" in html
        assert "race not found" in html

    def test_has_data_slug_attribute(self, race_index):
        html = render_race_reference({"slug": "unbound-200", "context": "distance"})
        assert 'data-slug="unbound-200"' in html

    def test_empty_context_still_renders(self, race_index):
        html = render_race_reference({"slug": "unbound-200", "context": ""})
        assert "gg-race-ref" in html
        assert "Unbound" in html
        assert "Tier" in html

    def test_no_race_index_returns_comment(self):
        old = generate_guide._RACE_INDEX
        generate_guide._RACE_INDEX = None
        try:
            html = render_race_reference({"slug": "unbound-200", "context": "elevation"})
            assert "<!--" in html
        finally:
            generate_guide._RACE_INDEX = old


# ── Race Callout Renderer ────────────────────────────────────


class TestRaceCallout:
    def test_renders_comparison_card(self, race_index):
        html = render_race_callout({
            "slugs": ["unbound-200", "mid-south"],
            "dimension": "elevation_ft",
            "caption": "Test caption"
        })
        assert "gg-race-callout" in html
        assert "RACE COMPARISON" in html

    def test_renders_both_race_names(self, race_index):
        html = render_race_callout({
            "slugs": ["unbound-200", "mid-south"],
            "dimension": "elevation_ft"
        })
        assert "Unbound" in html
        assert "Mid South" in html

    def test_renders_stat_values(self, race_index):
        html = render_race_callout({
            "slugs": ["unbound-200", "mid-south"],
            "dimension": "elevation_ft"
        })
        assert "gg-race-callout__stat-value" in html
        assert "11,000" in html  # Unbound elevation

    def test_renders_overall_score_dimension(self, race_index):
        html = render_race_callout({
            "slugs": ["unbound-200", "mid-south"],
            "dimension": "overall_score"
        })
        assert "Overall" in html

    def test_renders_score_dimension(self, race_index):
        html = render_race_callout({
            "slugs": ["unbound-200", "mid-south"],
            "dimension": "technicality"
        })
        assert "Technicality" in html

    def test_renders_caption(self, race_index):
        html = render_race_callout({
            "slugs": ["unbound-200", "mid-south"],
            "dimension": "elevation_ft",
            "caption": "Very different profiles."
        })
        assert "Very different profiles." in html
        assert "gg-race-callout__caption" in html

    def test_no_caption_omits_element(self, race_index):
        html = render_race_callout({
            "slugs": ["unbound-200", "mid-south"],
            "dimension": "elevation_ft"
        })
        assert "gg-race-callout__caption" not in html

    def test_missing_slug_returns_comment(self, race_index):
        html = render_race_callout({
            "slugs": ["unbound-200", "nonexistent-xyz"],
            "dimension": "elevation_ft"
        })
        assert "<!--" in html
        assert "missing slugs" in html

    def test_has_data_dimension_attribute(self, race_index):
        html = render_race_callout({
            "slugs": ["unbound-200", "mid-south"],
            "dimension": "elevation_ft"
        })
        assert 'data-dimension="elevation_ft"' in html

    def test_tier_badges_rendered(self, race_index):
        html = render_race_callout({
            "slugs": ["unbound-200", "mid-south"],
            "dimension": "elevation_ft"
        })
        assert "gg-race-callout__tier" in html
        assert 'data-tier=' in html

    def test_race_links_to_profile(self, race_index):
        html = render_race_callout({
            "slugs": ["unbound-200", "mid-south"],
            "dimension": "elevation_ft"
        })
        assert 'href="/race/unbound-200/"' in html
        assert 'href="/race/mid-south/"' in html

    def test_vs_element_present(self, race_index):
        html = render_race_callout({
            "slugs": ["unbound-200", "mid-south"],
            "dimension": "elevation_ft"
        })
        assert "VS" in html
        assert "gg-race-callout__vs" in html

    def test_no_race_index_returns_comment(self):
        old = generate_guide._RACE_INDEX
        generate_guide._RACE_INDEX = None
        try:
            html = render_race_callout({
                "slugs": ["unbound-200", "mid-south"],
                "dimension": "elevation_ft"
            })
            assert "<!--" in html
        finally:
            generate_guide._RACE_INDEX = old


# ── Decision Tree Renderer ───────────────────────────────────


class TestDecisionTree:
    SAMPLE_TREE = {
        "root": {
            "question": "What's your goal?",
            "options": [
                {"text": "Fun", "next": "fun"},
                {"text": "Competition", "result": "unbound-200"}
            ]
        },
        "fun": {
            "question": "How far?",
            "options": [
                {"text": "Short", "result": "rasputitsa"},
                {"text": "Long", "result": "mid-south"}
            ]
        }
    }

    def test_renders_tree_container(self):
        html = render_decision_tree({"title": "Find Your Race", "tree": self.SAMPLE_TREE})
        assert "gg-decision-tree" in html

    def test_renders_title(self):
        html = render_decision_tree({"title": "Find Your Race", "tree": self.SAMPLE_TREE})
        assert "Find Your Race" in html
        assert "gg-decision-tree__header" in html

    def test_renders_root_question(self):
        html = render_decision_tree({"title": "Test", "tree": self.SAMPLE_TREE})
        assert "What&#x27;s your goal?" in html or "What's your goal?" in html
        assert "gg-decision-tree__question" in html

    def test_renders_root_options(self):
        html = render_decision_tree({"title": "Test", "tree": self.SAMPLE_TREE})
        assert "gg-decision-tree__option" in html
        assert "Fun" in html
        assert "Competition" in html

    def test_option_data_attributes(self):
        html = render_decision_tree({"title": "Test", "tree": self.SAMPLE_TREE})
        assert 'data-target="fun"' in html
        assert 'data-is-result="false"' in html
        assert 'data-target="unbound-200"' in html
        assert 'data-is-result="true"' in html

    def test_tree_data_attribute_contains_json(self):
        html = render_decision_tree({"title": "Test", "tree": self.SAMPLE_TREE})
        assert "data-tree=" in html

    def test_result_div_hidden(self):
        html = render_decision_tree({"title": "Test", "tree": self.SAMPLE_TREE})
        assert 'class="gg-decision-tree__result"' in html
        assert 'display:none' in html

    def test_restart_button_hidden(self):
        html = render_decision_tree({"title": "Test", "tree": self.SAMPLE_TREE})
        assert "gg-decision-tree__restart" in html
        assert "Start Over" in html

    def test_default_title(self):
        html = render_decision_tree({"tree": self.SAMPLE_TREE})
        assert "Find Your Race" in html  # default title


# ── Race Data Loading ────────────────────────────────────────


class TestRaceDataLoading:
    def test_race_index_loads(self, race_index):
        assert isinstance(race_index, dict)
        assert len(race_index) > 300

    def test_race_index_has_expected_slugs(self, race_index):
        for slug in ["unbound-200", "mid-south", "tour-divide", "badlands"]:
            assert slug in race_index, f"Expected slug '{slug}' not in race index"

    def test_race_has_required_fields(self, race_index):
        race = race_index["unbound-200"]
        for field in ["name", "slug", "tier", "distance_mi", "elevation_ft", "profile_url"]:
            assert field in race, f"Race missing field: {field}"

    def test_race_has_scores(self, race_index):
        race = race_index["unbound-200"]
        assert "scores" in race
        assert "technicality" in race["scores"]
        assert "elevation" in race["scores"]
        assert "climate" in race["scores"]

    def test_block_renderers_registered(self):
        for bt in ["race_reference", "race_callout", "decision_tree"]:
            assert bt in BLOCK_RENDERERS, f"'{bt}' not in BLOCK_RENDERERS"


# ── Content JSON: Race Block Distribution ────────────────────


class TestRaceBlockContent:
    def test_content_has_race_blocks(self, content):
        """At least 20 race-connected blocks exist across all chapters."""
        count = 0
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] in ("race_reference", "race_callout", "decision_tree"):
                        count += 1
        assert count >= 20, f"Only {count} race blocks found, expected >= 20"

    def test_race_reference_blocks_have_slug(self, content):
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] == "race_reference":
                        assert "slug" in b, f"race_reference in {sec['id']} missing slug"
                        assert b["slug"], f"race_reference in {sec['id']} has empty slug"

    def test_race_callout_blocks_have_slugs(self, content):
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] == "race_callout":
                        assert "slugs" in b, f"race_callout in {sec['id']} missing slugs"
                        assert len(b["slugs"]) >= 2, \
                            f"race_callout in {sec['id']} needs >= 2 slugs"

    def test_decision_tree_has_root(self, content):
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] == "decision_tree":
                        assert "tree" in b, f"decision_tree in {sec['id']} missing tree"
                        assert "root" in b["tree"], \
                            f"decision_tree in {sec['id']} missing root node"

    def test_all_race_slugs_exist_in_index(self, content, race_index):
        """Every slug referenced in race blocks exists in the race index."""
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] == "race_reference":
                        assert b["slug"] in race_index, \
                            f"race_reference slug '{b['slug']}' in {sec['id']} not in race index"
                    elif b["type"] == "race_callout":
                        for slug in b["slugs"]:
                            assert slug in race_index, \
                                f"race_callout slug '{slug}' in {sec['id']} not in race index"

    def test_decision_tree_result_slugs_exist(self, content, race_index):
        """All result slugs in decision trees point to real races."""
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] != "decision_tree":
                        continue
                    tree = b.get("tree", {})
                    for node_id, node in tree.items():
                        for opt in node.get("options", []):
                            if "result" in opt:
                                assert opt["result"] in race_index, \
                                    f"decision_tree result '{opt['result']}' in {sec['id']} not in race index"

    def test_chapter_2_has_decision_tree(self, content):
        """Chapter 2 (Race Selection) must have the main decision tree."""
        ch2 = content["chapters"][1]
        has_tree = any(
            b["type"] == "decision_tree"
            for sec in ch2["sections"]
            for b in sec["blocks"]
        )
        assert has_tree, "Chapter 2 (Race Selection) must have a decision_tree block"

    def test_each_chapter_has_race_blocks(self, content):
        """Every chapter has at least 1 race-connected block."""
        for ch in content["chapters"]:
            count = sum(
                1 for sec in ch["sections"]
                for b in sec["blocks"]
                if b["type"] in ("race_reference", "race_callout", "decision_tree")
            )
            assert count >= 1, \
                f"Chapter {ch['number']} ({ch['id']}) has no race-connected blocks"


# ── Generated Output: Race Blocks in HTML ────────────────────


class TestRaceBlocksInOutput:
    def test_chapter_pages_have_race_refs(self, chapter_htmls):
        """At least some chapter pages contain rendered race references."""
        pages_with_refs = sum(
            1 for html in chapter_htmls.values()
            if 'class="gg-race-ref"' in html
        )
        assert pages_with_refs >= 4, \
            f"Only {pages_with_refs} chapter pages have race references, expected >= 4"

    def test_race_ref_links_to_profile(self, chapter_htmls):
        """Race reference links point to /race/{slug}/ profile pages."""
        for name, html in chapter_htmls.items():
            # Only check links inside gg-race-ref anchors
            for m in re.finditer(r'class="gg-race-ref"[^>]*href="(/race/[^"]+)"', html):
                url = m.group(1)
                assert url.endswith("/"), \
                    f"Race ref in {name} has URL without trailing slash: {url}"
            # Also check href before class
            for m in re.finditer(r'href="(/race/[^"]+)"[^>]*class="gg-race-ref"', html):
                url = m.group(1)
                assert url.endswith("/"), \
                    f"Race ref in {name} has URL without trailing slash: {url}"

    def test_chapter_pages_have_race_callouts(self, chapter_htmls):
        """At least some chapter pages contain rendered race callouts."""
        pages_with_callouts = sum(
            1 for html in chapter_htmls.values()
            if 'class="gg-race-callout"' in html
        )
        assert pages_with_callouts >= 3, \
            f"Only {pages_with_callouts} chapter pages have race callouts, expected >= 3"

    def test_race_callout_has_comparison_structure(self, chapter_htmls):
        """Race callouts have the grid + VS + header structure."""
        for name, html in chapter_htmls.items():
            if 'class="gg-race-callout"' not in html:
                continue
            assert "RACE COMPARISON" in html, \
                f"Race callout in {name} missing RACE COMPARISON header"
            assert "gg-race-callout__grid" in html, \
                f"Race callout in {name} missing grid"

    def test_decision_tree_in_chapter_2(self, chapter_htmls):
        """Chapter 2 output contains a rendered decision tree."""
        ch2 = chapter_htmls.get("race-selection", "")
        assert 'class="gg-decision-tree"' in ch2, \
            "Chapter 2 (race-selection) missing decision tree"
        assert "gg-decision-tree__option" in ch2, \
            "Chapter 2 decision tree missing options"

    def test_race_callout_css_exists(self, all_htmls):
        """Race callout CSS classes are defined in at least one page."""
        any_page = next(iter(all_htmls.values()))
        assert "gg-race-callout__header" in any_page
        assert "gg-race-callout__grid" in any_page

    def test_decision_tree_css_exists(self, all_htmls):
        """Decision tree CSS classes are defined in at least one page."""
        any_page = next(iter(all_htmls.values()))
        assert "gg-decision-tree__header" in any_page
        assert "gg-decision-tree__option" in any_page

    def test_decision_tree_js_exists(self, all_htmls):
        """Decision tree JS handlers are present in at least one page."""
        any_page = next(iter(all_htmls.values()))
        assert "gg-decision-tree__option" in any_page
        assert "decision_tree_result" in any_page or "decision_tree_step" in any_page


# ══════════════════════════════════════════════════════════════
# Phase C: Gate Verification + Personalized Content
# ══════════════════════════════════════════════════════════════


# ── Gate Verification ────────────────────────────────────────


class TestGateFormsubmit:
    def test_gate_has_email_form(self, chapter_htmls):
        """Gated chapters use formsubmit.co email form, not Substack iframe."""
        gated_slugs = ["workout-execution", "nutrition-fueling",
                       "mental-training-race-tactics", "race-week", "post-race"]
        for slug in gated_slugs:
            html = chapter_htmls.get(slug, "")
            if not html:
                continue
            assert "formsubmit.co" in html, \
                f"Gated chapter '{slug}' missing formsubmit.co form"
            assert 'type="email"' in html, \
                f"Gated chapter '{slug}' missing email input"

    def test_gate_no_substack_iframe(self, chapter_htmls):
        """No gated chapter uses a Substack iframe for gating."""
        gated_slugs = ["workout-execution", "nutrition-fueling",
                       "mental-training-race-tactics", "race-week", "post-race"]
        for slug in gated_slugs:
            html = chapter_htmls.get(slug, "")
            if not html:
                continue
            # Gate section should not contain an iframe
            gate_start = html.find('id="gg-guide-gate"')
            if gate_start == -1:
                continue
            gate_section = html[gate_start:gate_start + 2000]
            assert "<iframe" not in gate_section, \
                f"Gated chapter '{slug}' uses iframe in gate (should use formsubmit.co form)"

    def test_gate_has_bypass_button(self, chapter_htmls):
        """Gated chapters have a bypass button for existing subscribers."""
        gated_slugs = ["workout-execution", "nutrition-fueling",
                       "mental-training-race-tactics", "race-week", "post-race"]
        for slug in gated_slugs:
            html = chapter_htmls.get(slug, "")
            if not html:
                continue
            assert "gg-guide-gate-bypass" in html, \
                f"Gated chapter '{slug}' missing bypass button"

    def test_gate_localstorage_key(self, all_htmls):
        """Gate JS uses gg_guide_unlocked localStorage key."""
        any_page = next(iter(all_htmls.values()))
        assert "gg_guide_unlocked" in any_page

    def test_gate_ga4_events(self, all_htmls):
        """Gate JS fires GA4 events on unlock."""
        any_page = next(iter(all_htmls.values()))
        assert "guide_gate_unlock" in any_page


# ── Personalized Content Renderer ────────────────────────────


class TestPersonalizedContentRenderer:
    SAMPLE_BLOCK = {
        "type": "personalized_content",
        "variants": {
            "ayahuasca": {"content": "Easy rides only."},
            "finisher": {"content": "Build your base."},
            "competitor": {"content": "Structured intervals."},
            "podium": {"content": "Periodized blocks."}
        }
    }

    def test_renders_container(self):
        from generate_guide import render_personalized_content
        html = render_personalized_content(self.SAMPLE_BLOCK)
        assert 'class="gg-personalized"' in html

    def test_renders_all_4_variants(self):
        from generate_guide import render_personalized_content
        html = render_personalized_content(self.SAMPLE_BLOCK)
        assert html.count("gg-personalized__variant") == 4

    def test_finisher_visible_by_default(self):
        from generate_guide import render_personalized_content
        html = render_personalized_content(self.SAMPLE_BLOCK)
        # Finisher variant should NOT have display:none
        import re
        finisher_match = re.search(
            r'data-rider-type="finisher"([^>]*)', html
        )
        assert finisher_match
        assert 'display:none' not in finisher_match.group(1)

    def test_finisher_has_active_class(self):
        from generate_guide import render_personalized_content
        html = render_personalized_content(self.SAMPLE_BLOCK)
        assert 'gg-personalized--active' in html
        # Only finisher should have the active class
        import re
        finisher_div = re.search(
            r'class="gg-personalized__variant gg-personalized--active"[^>]*'
            r'data-rider-type="finisher"', html
        )
        assert finisher_div, "finisher variant must have gg-personalized--active class"
        # No other rider types should have the active class
        non_finisher_active = re.findall(
            r'class="gg-personalized__variant gg-personalized--active"[^>]*'
            r'data-rider-type="(?!finisher)\w+"', html
        )
        assert non_finisher_active == [], f"Only finisher should be active, but found: {non_finisher_active}"

    def test_other_variants_hidden(self):
        from generate_guide import render_personalized_content
        import re
        html = render_personalized_content(self.SAMPLE_BLOCK)
        # 3 variants should NOT have the active class (all except finisher)
        # CSS hides variants without --active via opacity:0;visibility:hidden
        variants = re.findall(r'class="gg-personalized__variant([^"]*)"', html)
        active_count = sum(1 for v in variants if 'gg-personalized--active' in v)
        non_active_count = sum(1 for v in variants if 'gg-personalized--active' not in v)
        assert active_count == 1, f"Expected 1 active variant, got {active_count}"
        assert non_active_count == 3, f"Expected 3 hidden variants, got {non_active_count}"

    def test_data_rider_type_attributes(self):
        from generate_guide import render_personalized_content
        html = render_personalized_content(self.SAMPLE_BLOCK)
        for rider in ["ayahuasca", "finisher", "competitor", "podium"]:
            assert f'data-rider-type="{rider}"' in html, \
                f"Missing data-rider-type for {rider}"

    def test_content_rendered(self):
        from generate_guide import render_personalized_content
        html = render_personalized_content(self.SAMPLE_BLOCK)
        assert "Easy rides only." in html
        assert "Build your base." in html
        assert "Structured intervals." in html
        assert "Periodized blocks." in html

    def test_content_in_paragraphs(self):
        from generate_guide import render_personalized_content
        html = render_personalized_content(self.SAMPLE_BLOCK)
        assert "<p>" in html

    def test_missing_variant_skipped(self):
        from generate_guide import render_personalized_content
        block = {
            "variants": {
                "finisher": {"content": "Only finisher."},
                "competitor": {"content": "Only competitor."}
            }
        }
        html = render_personalized_content(block)
        assert html.count("gg-personalized__variant") == 2
        assert 'data-rider-type="ayahuasca"' not in html

    def test_empty_variants_renders_empty(self):
        from generate_guide import render_personalized_content
        html = render_personalized_content({"variants": {}})
        assert 'class="gg-personalized"' in html


# ── Personalized Content CSS/JS ──────────────────────────────


class TestPersonalizedContentCSS:
    def test_personalized_css_exists(self, all_htmls):
        """Personalized content CSS classes are defined."""
        any_page = next(iter(all_htmls.values()))
        assert "gg-personalized__variant" in any_page
        assert "gg-personalized--active" in any_page

    def test_prefers_reduced_motion_guard(self, all_htmls):
        """CSS includes prefers-reduced-motion media query."""
        any_page = next(iter(all_htmls.values()))
        assert "prefers-reduced-motion" in any_page

    def test_personalized_transition_css(self, all_htmls):
        """Personalized content CSS uses opacity transition and class-based visibility."""
        any_page = next(iter(all_htmls.values()))
        # CSS must have transition:opacity on variant class
        assert "transition:opacity" in any_page.replace(" ", ""), \
            "gg-personalized__variant must have opacity transition"
        # Active variant uses opacity:1;visibility:visible
        assert "gg-personalized--active" in any_page
        assert "opacity:1" in any_page.replace(" ", "")
        assert "visibility:visible" in any_page.replace(" ", "")


class TestPersonalizedContentJS:
    def test_js_handles_personalized_swap(self, all_htmls):
        """JS toggles gg-personalized--active class on rider type change."""
        any_page = next(iter(all_htmls.values()))
        # JS must querySelector .gg-personalized and toggle --active class
        assert "gg-personalized" in any_page
        assert "gg-personalized__variant" in any_page
        # JS must toggle the active class (not use display:none)
        assert 'classList.toggle("gg-personalized--active"' in any_page, \
            "JS must use classList.toggle for personalized--active, not display:none"

    def test_js_uses_data_rider_type(self, all_htmls):
        """JS uses data-rider-type attribute for matching."""
        any_page = next(iter(all_htmls.values()))
        assert "data-rider-type" in any_page


# ── Personalized Content in Output ───────────────────────────


class TestPersonalizedContentInOutput:
    def test_chapters_3_8_have_personalized_content(self, chapter_htmls):
        """Chapters 3-8 have personalized content blocks in HTML output."""
        personalized_chapters = [
            "training-fundamentals", "workout-execution", "nutrition-fueling",
            "mental-training-race-tactics", "race-week", "post-race"
        ]
        for slug in personalized_chapters:
            html = chapter_htmls.get(slug, "")
            assert 'class="gg-personalized"' in html, \
                f"Chapter '{slug}' missing personalized content blocks"

    def test_chapters_1_2_no_personalized_content(self, chapter_htmls):
        """Chapters 1-2 should not have personalized content (general intro)."""
        body_sections = {}
        for slug in ["what-is-gravel-racing", "race-selection"]:
            html = chapter_htmls.get(slug, "")
            # Extract body after </style> to avoid CSS class matches
            parts = html.split("</style>")
            body = parts[-1] if len(parts) > 1 else html
            body_sections[slug] = body

        for slug, body in body_sections.items():
            assert 'class="gg-personalized"' not in body, \
                f"Chapter '{slug}' should not have personalized content"

    def test_personalized_blocks_have_4_variants(self, chapter_htmls):
        """Each personalized block in output has all 4 rider type variants."""
        import re
        for slug, html in chapter_htmls.items():
            blocks = re.findall(
                r'<div class="gg-personalized">(.*?)</div>\s*</div>\s*</div>',
                html, re.DOTALL
            )
            # Simpler check: count personalized containers vs variant divs
            containers = html.count('class="gg-personalized"')
            if containers == 0:
                continue
            for rider in ["ayahuasca", "finisher", "competitor", "podium"]:
                rider_variants = html.count(f'data-rider-type="{rider}"')
                assert rider_variants >= containers, \
                    f"Chapter '{slug}' has {containers} personalized blocks " \
                    f"but only {rider_variants} {rider} variants"

    def test_content_json_has_personalized_blocks(self, content):
        """Content JSON has personalized_content blocks in chapters 3-8."""
        for ch in content["chapters"]:
            if ch["number"] < 3:
                continue
            has_personalized = any(
                b["type"] == "personalized_content"
                for sec in ch["sections"]
                for b in sec["blocks"]
            )
            assert has_personalized, \
                f"Chapter {ch['number']} ({ch['id']}) missing personalized_content blocks"

    def test_all_personalized_variants_have_content(self, content):
        """Every personalized_content block has non-empty content in all variants."""
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] != "personalized_content":
                        continue
                    variants = b.get("variants", {})
                    for rider in ["ayahuasca", "finisher", "competitor", "podium"]:
                        assert rider in variants, \
                            f"personalized_content in {sec['id']} missing '{rider}' variant"
                        assert variants[rider].get("content", "").strip(), \
                            f"personalized_content in {sec['id']} has empty '{rider}' content"

    def test_total_personalized_blocks_count(self, content):
        """At least 15 personalized_content blocks exist."""
        count = sum(
            1 for ch in content["chapters"]
            for sec in ch["sections"]
            for b in sec["blocks"]
            if b["type"] == "personalized_content"
        )
        assert count >= 15, f"Only {count} personalized blocks, expected >= 15"


# ══════════════════════════════════════════════════════════════
# Phase D: Race Preparation Configurator
# ══════════════════════════════════════════════════════════════


class TestConfiguratorPageExists:
    def test_configurator_output_exists(self, output_dir):
        """Configurator page is generated in the output directory."""
        path = output_dir / "race-prep-configurator" / "index.html"
        assert path.exists(), "Configurator page not generated"

    def test_configurator_page_not_empty(self, configurator_html):
        """Configurator page has substantial content."""
        assert len(configurator_html) > 50000, \
            f"Configurator page too small ({len(configurator_html)} bytes)"


class TestConfiguratorRaceData:
    def test_race_data_embedded(self, configurator_html):
        """Race data is embedded as inline JS variable."""
        assert "var GG_RACES=" in configurator_html, \
            "Configurator missing embedded race data (var GG_RACES=)"

    def test_race_data_has_entries(self, configurator_html):
        """Embedded race data contains multiple entries."""
        # GG_RACES should be a JS array with many objects
        assert configurator_html.count('"s":') > 100, \
            "GG_RACES has fewer than 100 race entries"

    def test_race_data_has_required_keys(self, configurator_html):
        """Race data entries have required keys for configurator logic."""
        for key in ['"n":', '"s":', '"d":', '"e":', '"t":', '"m":', '"cl":', '"te":', '"u"']:
            assert key in configurator_html, \
                f"Race data missing key {key}"


class TestConfiguratorFormFields:
    def test_race_search_input(self, configurator_html):
        """Configurator has a race search input."""
        assert 'id="gg-cfg-race-search"' in configurator_html
        assert 'placeholder="Search 328 races..."' in configurator_html

    def test_race_select_dropdown(self, configurator_html):
        """Configurator has a race select dropdown."""
        assert 'id="gg-cfg-race"' in configurator_html
        assert "<select" in configurator_html

    def test_rider_type_buttons(self, configurator_html):
        """Configurator has 4 rider type buttons."""
        for rider in ["ayahuasca", "finisher", "competitor", "podium"]:
            assert f'data-rider="{rider}"' in configurator_html, \
                f"Missing rider type button for {rider}"

    def test_rider_buttons_radiogroup(self, configurator_html):
        """Rider buttons have ARIA radiogroup role."""
        assert 'role="radiogroup"' in configurator_html
        assert 'role="radio"' in configurator_html

    def test_date_picker(self, configurator_html):
        """Configurator has a date input."""
        assert 'id="gg-cfg-date"' in configurator_html
        assert 'type="date"' in configurator_html

    def test_generate_button(self, configurator_html):
        """Configurator has a generate button."""
        assert 'id="gg-cfg-generate"' in configurator_html
        assert "GENERATE PREP PLAN" in configurator_html


class TestConfiguratorOutput:
    def test_output_section_exists(self, configurator_html):
        """Configurator has an output section (hidden by default)."""
        assert 'id="gg-cfg-output"' in configurator_html
        assert 'style="display:none"' in configurator_html

    def test_five_output_cards(self, configurator_html):
        """Output has 5 recommendation cards."""
        expected_cards = ["TRAINING", "NUTRITION", "HYDRATION", "GEAR", "MENTAL PREP"]
        for card in expected_cards:
            assert f">{card}</div>" in configurator_html, \
                f"Missing output card: {card}"

    def test_output_card_ids(self, configurator_html):
        """Each output card has a unique ID for JS population."""
        for card_id in ["training", "nutrition", "hydration", "gear", "mental"]:
            assert f'id="gg-cfg-out-{card_id}"' in configurator_html, \
                f"Missing output body ID: gg-cfg-out-{card_id}"

    def test_prep_kit_link_placeholder(self, configurator_html):
        """Output has a prep kit link section."""
        assert 'id="gg-cfg-out-link"' in configurator_html


class TestConfiguratorGate:
    def test_configurator_is_gated(self, configurator_html):
        """Configurator page has a gate overlay."""
        assert 'id="gg-guide-gate"' in configurator_html

    def test_configurator_gate_has_form(self, configurator_html):
        """Configurator gate uses formsubmit.co email form."""
        assert "formsubmit.co" in configurator_html
        assert 'type="email"' in configurator_html

    def test_configurator_form_behind_gate(self, configurator_html):
        """Configurator form is inside the gated content div."""
        assert "gg-cluster-gated-content" in configurator_html
        # The configurator div should be after the gated-content div
        gate_pos = configurator_html.find("gg-cluster-gated-content")
        cfg_pos = configurator_html.find('id="gg-configurator"')
        assert gate_pos < cfg_pos, \
            "Configurator form should be inside gated content section"


class TestConfiguratorSEO:
    def test_canonical_url(self, configurator_html):
        """Configurator has correct canonical URL."""
        assert 'href="https://gravelgodcycling.com/guide/race-prep-configurator/"' \
            in configurator_html

    def test_unique_title(self, configurator_html):
        """Configurator has a unique page title."""
        assert "<title>Race Prep Configurator" in configurator_html

    def test_meta_description(self, configurator_html):
        """Configurator has a meta description."""
        assert 'name="description"' in configurator_html
        assert "personalized" in configurator_html.lower()

    def test_breadcrumb_3_items(self, configurator_html):
        """Configurator breadcrumb has 3 items: Home → Guide → Configurator."""
        assert "gg-breadcrumb" in configurator_html
        assert "Training Guide" in configurator_html
        assert "Race Prep Configurator" in configurator_html

    def test_jsonld_web_application(self, configurator_html):
        """Configurator has WebApplication JSON-LD schema."""
        assert '"WebApplication"' in configurator_html
        assert '"Gravel Race Prep Configurator"' in configurator_html

    def test_jsonld_breadcrumb(self, configurator_html):
        """Configurator has BreadcrumbList JSON-LD schema."""
        assert '"BreadcrumbList"' in configurator_html

    def test_og_tags(self, configurator_html):
        """Configurator has Open Graph tags."""
        assert 'property="og:title"' in configurator_html
        assert 'property="og:description"' in configurator_html
        assert 'property="og:image"' in configurator_html


class TestConfiguratorLinkedFromPillar:
    def test_pillar_links_to_configurator(self, pillar_html):
        """Pillar page has a link to the configurator."""
        assert 'href="/guide/race-prep-configurator/"' in pillar_html

    def test_pillar_configurator_card(self, pillar_html):
        """Pillar page has a full-width configurator card."""
        assert "gg-cluster-card--configurator" in pillar_html
        assert "INTERACTIVE TOOL" in pillar_html


class TestConfiguratorGA4:
    def test_ga4_plan_generated_event(self, configurator_html):
        """Configurator JS fires configurator_plan_generated GA4 event."""
        assert "configurator_plan_generated" in configurator_html

    def test_ga4_race_selected_event(self, configurator_html):
        """Configurator JS fires configurator_race_selected GA4 event."""
        assert "configurator_race_selected" in configurator_html

    def test_ga4_head_snippet(self, configurator_html):
        """Configurator has GA4 head snippet."""
        assert "G-EJJZ9T6M52" in configurator_html


class TestConfiguratorBrandCompliance:
    def test_shared_header(self, configurator_html):
        """Configurator uses shared site header."""
        assert "gg-site-header" in configurator_html

    def test_shared_footer(self, configurator_html):
        """Configurator uses shared mega footer."""
        assert "gg-mega-footer" in configurator_html

    def test_consent_banner(self, configurator_html):
        """Configurator has cookie consent banner."""
        assert "gg-consent" in configurator_html or "cookie" in configurator_html.lower()

    def test_tokens_css_present(self, configurator_html):
        """Configurator has CSS custom properties from tokens."""
        assert "--gg-color-primary-brown" in configurator_html
        assert "--gg-font-data" in configurator_html


class TestConfiguratorFunctions:
    """Unit tests for configurator builder functions."""

    def test_build_configurator_race_data_returns_js(self):
        """Race data builder returns JS with GG_RACES variable."""
        js = build_configurator_race_data()
        assert "var GG_RACES=" in js
        assert js.endswith(";"), "Race data JS should end with semicolon"

    def test_build_configurator_body_has_form(self):
        """Body builder returns form with all 3 steps."""
        html = build_configurator_body()
        assert "SELECT YOUR RACE" in html
        assert "YOUR RIDER TYPE" in html
        assert "RACE DATE" in html

    def test_build_configurator_css_has_classes(self):
        """CSS builder returns configurator-specific styles."""
        css = build_configurator_css()
        assert ".gg-configurator" in css
        assert ".gg-configurator__generate" in css

    def test_build_configurator_js_has_iife(self):
        """JS builder returns IIFE with event handlers."""
        js = build_configurator_js()
        assert "addEventListener" in js or "querySelector" in js

    def test_build_configurator_jsonld_has_schemas(self):
        """JSON-LD builder returns WebApplication + BreadcrumbList."""
        jsonld = build_configurator_jsonld()
        assert '"WebApplication"' in jsonld
        assert '"BreadcrumbList"' in jsonld


# ══════════════════════════════════════════════════════════════
# Hardening: Edge cases, XSS resistance, data integrity, and
# regression guards that prevent re-introducing known bugs.
# ══════════════════════════════════════════════════════════════


class TestXSSResistance:
    """Verify all renderers properly escape untrusted data."""

    def test_race_ref_escapes_html_in_name(self):
        """Race name with HTML chars must be escaped in output."""
        generate_guide._RACE_INDEX = {
            "xss-test": {
                "name": '<img src=x onerror=alert(1)>',
                "slug": "xss-test",
                "tier": 1,
                "profile_url": "/race/xss-test/",
                "elevation_ft": 5000,
                "distance_mi": 100,
                "scores": {},
            }
        }
        try:
            html = render_race_reference({"slug": "xss-test", "context": "elevation"})
            assert "<img" not in html, "Unescaped <img> tag in race reference!"
            assert "&lt;img" in html, "HTML not properly escaped in race reference"
        finally:
            generate_guide._RACE_INDEX = None

    def test_race_ref_escapes_quotes_in_slug(self):
        """Slug with quotes must be escaped in data-slug attribute."""
        generate_guide._RACE_INDEX = {
            'test"slug': {
                "name": "Test Race",
                "slug": 'test"slug',
                "tier": 1,
                "profile_url": "/race/test/",
                "scores": {},
            }
        }
        try:
            html = render_race_reference({"slug": 'test"slug'})
            assert 'data-slug="test&quot;slug"' in html
        finally:
            generate_guide._RACE_INDEX = None

    def test_callout_escapes_tier_in_attribute(self):
        """Tier value must be escaped when used in data-tier attribute."""
        generate_guide._RACE_INDEX = {
            "a": {"name": "A", "slug": "a", "tier": '" onclick="alert(1)',
                  "profile_url": "/race/a/", "scores": {}, "overall_score": 50},
            "b": {"name": "B", "slug": "b", "tier": 2,
                  "profile_url": "/race/b/", "scores": {}, "overall_score": 60},
        }
        try:
            html = render_race_callout({"slugs": ["a", "b"], "dimension": "overall_score"})
            assert 'onclick' not in html or '&quot;' in html, \
                "Unescaped tier value could break out of attribute!"
        finally:
            generate_guide._RACE_INDEX = None

    def test_callout_escapes_stat_value(self):
        """Stat values must be escaped even when they contain HTML."""
        generate_guide._RACE_INDEX = {
            "a": {"name": "A", "slug": "a", "tier": 1,
                  "profile_url": "/race/a/", "scores": {},
                  "overall_score": "<script>alert(1)</script>"},
            "b": {"name": "B", "slug": "b", "tier": 2,
                  "profile_url": "/race/b/", "scores": {}, "overall_score": 60},
        }
        try:
            html = render_race_callout({"slugs": ["a", "b"], "dimension": "overall_score"})
            assert "<script>" not in html, "Unescaped <script> in stat value!"
        finally:
            generate_guide._RACE_INDEX = None

    def test_decision_tree_escapes_json_in_attribute(self):
        """Tree JSON in data-tree attribute must be safely escaped."""
        tree = {"root": {"question": "Pick?", "options": [
            {"text": 'O\'Brien "Classic"', "result": "test-slug"}
        ]}}
        block = {"title": "Test", "tree": tree}
        html = render_decision_tree(block)
        # Must not contain raw quotes that break the attribute
        assert "data-tree='" in html
        # The attribute should be parseable after browser unescaping
        import re
        match = re.search(r"data-tree='([^']*)'", html)
        assert match, "data-tree attribute not found or broken"

    def test_configurator_js_no_innerhtml_with_race_name(self, configurator_html):
        """Configurator JS must NOT inject race.n via innerHTML.

        The prep kit link previously used innerHTML with race.n which was XSS.
        It should now use DOM API (createElement + textContent).
        """
        # Find the prep kit link section in JS
        assert "createElement" in configurator_html, \
            "Prep kit link should use createElement, not innerHTML with race data"
        # Ensure no innerHTML assignment directly uses race.n or race.u
        import re
        # Look for patterns like: innerHTML=...+race.n+... or innerHTML=...+race.u+...
        dangerous = re.findall(
            r'\.innerHTML\s*=\s*[^;]*race\.(n|u)', configurator_html
        )
        assert not dangerous, \
            f"Found innerHTML with race data (XSS vector): {dangerous}"

    def test_personalized_content_escapes_html(self):
        """Personalized content with HTML chars must be escaped."""
        from generate_guide import render_personalized_content
        block = {
            "variants": {
                "finisher": {"content": '<script>alert("xss")</script>'},
                "competitor": {"content": "Normal text"},
            }
        }
        html = render_personalized_content(block)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestEscFunctionEdgeCases:
    """Verify the esc() function handles all edge cases correctly."""

    def test_esc_zero_not_empty(self):
        """esc(0) must return '0', not empty string."""
        from generate_guide import esc
        assert esc(0) == "0", "esc(0) returned empty string — 0 is falsy but valid"

    def test_esc_false_not_empty(self):
        """esc(False) must return 'False', not empty string."""
        from generate_guide import esc
        assert esc(False) == "False"

    def test_esc_none_is_empty(self):
        """esc(None) should return empty string."""
        from generate_guide import esc
        assert esc(None) == ""

    def test_esc_empty_string_is_empty(self):
        """esc('') should return empty string."""
        from generate_guide import esc
        assert esc("") == ""

    def test_esc_html_chars(self):
        """esc() must escape <, >, &, quotes."""
        from generate_guide import esc
        result = esc('<script>"test" & \'more\'')
        assert "<" not in result
        assert ">" not in result
        assert "&lt;" in result
        assert "&amp;" in result


class TestRaceSlugIntegrity:
    """Verify all race slugs referenced in content JSON actually exist."""

    def test_all_race_reference_slugs_exist(self, content):
        """Every race_reference block must reference a slug that exists in race-index.json."""
        race_index = load_race_index()
        missing = []
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] != "race_reference":
                        continue
                    slug = b.get("slug", "")
                    if slug not in race_index:
                        missing.append(f"Ch{ch['number']}/{sec['id']}: {slug}")
        assert not missing, \
            f"Race reference slugs not found in race-index.json:\n  " + "\n  ".join(missing)

    def test_all_race_callout_slugs_exist(self, content):
        """Every race_callout block must reference slugs that exist in race-index.json."""
        race_index = load_race_index()
        missing = []
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] != "race_callout":
                        continue
                    for slug in b.get("slugs", []):
                        if slug not in race_index:
                            missing.append(f"Ch{ch['number']}/{sec['id']}: {slug}")
        assert not missing, \
            f"Race callout slugs not found in race-index.json:\n  " + "\n  ".join(missing)

    def test_all_race_callouts_have_exactly_2_slugs(self, content):
        """Every race_callout block must have exactly 2 slugs (for VS comparison)."""
        bad = []
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] != "race_callout":
                        continue
                    count = len(b.get("slugs", []))
                    if count != 2:
                        bad.append(f"Ch{ch['number']}/{sec['id']}: {count} slugs")
        assert not bad, \
            f"Race callouts with wrong slug count:\n  " + "\n  ".join(bad)

    def test_decision_tree_result_slugs_exist(self, content):
        """Decision tree result slugs should exist in race-index.json."""
        race_index = load_race_index()
        missing = []
        for ch in content["chapters"]:
            for sec in ch["sections"]:
                for b in sec["blocks"]:
                    if b["type"] != "decision_tree":
                        continue
                    tree = b.get("tree", {})
                    # Walk all nodes to find result slugs
                    for node_id, node in tree.items():
                        for opt in node.get("options", []):
                            slug = opt.get("result")
                            if slug and slug not in race_index:
                                missing.append(f"Ch{ch['number']}: tree result '{slug}'")
        assert not missing, \
            f"Decision tree result slugs not in race-index.json:\n  " + "\n  ".join(missing)


class TestCalloutRendererEdgeCases:
    """Edge cases for render_race_callout."""

    def test_callout_rejects_1_slug(self):
        """Callout with 1 slug returns error comment, not broken HTML."""
        generate_guide._RACE_INDEX = {"a": {"name": "A", "slug": "a"}}
        try:
            html = render_race_callout({"slugs": ["a"], "dimension": "overall_score"})
            assert "<!-- " in html, "1-slug callout should return HTML comment"
            assert "expected 2 slugs" in html
        finally:
            generate_guide._RACE_INDEX = None

    def test_callout_rejects_3_slugs(self):
        """Callout with 3 slugs returns error comment, not broken layout."""
        idx = {k: {"name": k, "slug": k} for k in ["a", "b", "c"]}
        generate_guide._RACE_INDEX = idx
        try:
            html = render_race_callout({"slugs": ["a", "b", "c"]})
            assert "expected 2 slugs" in html
        finally:
            generate_guide._RACE_INDEX = None

    def test_callout_handles_zero_distance(self):
        """Callout with distance_mi=0 should show em-dash, not '0'."""
        generate_guide._RACE_INDEX = {
            "a": {"name": "A", "slug": "a", "tier": 1,
                  "profile_url": "/race/a/", "scores": {}, "distance_mi": 0},
            "b": {"name": "B", "slug": "b", "tier": 2,
                  "profile_url": "/race/b/", "scores": {}, "distance_mi": 100},
        }
        try:
            html = render_race_callout({"slugs": ["a", "b"], "dimension": "distance_mi"})
            assert "\u2014" in html, "Zero distance should show em-dash"
        finally:
            generate_guide._RACE_INDEX = None

    def test_callout_missing_slug_returns_comment(self):
        """Callout with a nonexistent slug returns graceful HTML comment."""
        generate_guide._RACE_INDEX = {
            "a": {"name": "A", "slug": "a", "tier": 1,
                  "profile_url": "/race/a/", "scores": {}, "overall_score": 50},
        }
        try:
            html = render_race_callout({"slugs": ["a", "nonexistent"]})
            assert "<!-- " in html
            assert "missing slugs" in html
        finally:
            generate_guide._RACE_INDEX = None


class TestConfiguratorJSIntegrity:
    """Verify the configurator JS is structurally sound."""

    def test_js_syntax_valid(self, configurator_html):
        """Configurator JS can be extracted and parsed without syntax errors."""
        import subprocess
        # Extract all <script> content (not external src) from the page
        scripts = re.findall(r'<script>([^<]+)</script>', configurator_html)
        assert scripts, "No inline scripts found"
        # Concatenate and check syntax with Node if available
        js_code = "\n".join(scripts)
        try:
            result = subprocess.run(
                ["node", "--check", "-e", js_code],
                capture_output=True, text=True, timeout=10
            )
            # node --check -e doesn't work, use a parse-only approach
            result = subprocess.run(
                ["node", "-e", f"new Function({json.dumps(js_code)})"],
                capture_output=True, text=True, timeout=10
            )
            assert result.returncode == 0, \
                f"JS syntax error: {result.stderr[:500]}"
        except FileNotFoundError:
            pytest.skip("Node.js not available for JS syntax check")

    def test_js_null_guards_on_all_output_elements(self, configurator_html):
        """Every getElementById for output cards must have a null check."""
        output_ids = [
            "gg-cfg-out-race", "gg-cfg-out-meta", "gg-cfg-out-training",
            "gg-cfg-out-nutrition", "gg-cfg-out-hydration",
            "gg-cfg-out-gear", "gg-cfg-out-mental", "gg-cfg-out-link",
        ]
        for oid in output_ids:
            # The pattern should be: var x=$("id"); ... if(x)x.innerHTML=...
            # NOT: document.getElementById("id").innerHTML=...
            pattern = rf'getElementById\("{oid}"\)\.'
            direct_access = re.findall(pattern, configurator_html)
            assert not direct_access, \
                f"Direct property access on getElementById('{oid}') without null check. " \
                f"Use var x=$('id');if(x)x.property=... pattern."

    def test_js_persists_rider_to_localstorage(self, configurator_html):
        """Rider type selection in configurator must persist to localStorage."""
        assert "localStorage.setItem" in configurator_html
        assert "gg_guide_rider_type" in configurator_html

    def test_js_validates_rider_type(self, configurator_html):
        """Rider type from localStorage must be validated before use."""
        assert "validRiders" in configurator_html or "indexOf" in configurator_html, \
            "Rider type from localStorage should be validated against known values"

    def test_js_search_uses_dom_removal(self, configurator_html):
        """Search filter must use DOM removal (not display:none) for Safari compat."""
        assert "removeChild" in configurator_html, \
            "Search filter should use removeChild for Safari <option> compat"

    def test_js_has_keyboard_navigation(self, configurator_html):
        """Rider radiogroup must support arrow key navigation (ARIA pattern)."""
        assert "ArrowRight" in configurator_html or "ArrowDown" in configurator_html, \
            "Rider radiogroup missing keyboard navigation (ARIA radio pattern)"

    def test_js_training_peak_floor(self, configurator_html):
        """Peak/taper weeks must be at least 1 (Math.max(1,...))."""
        assert "Math.max(1,weeksOut-bw-buw)" in configurator_html, \
            "Peak weeks calculation should floor at 1 to avoid zero/negative"

    def test_js_elevation_type_check(self, configurator_html):
        """Elevation must check typeof before calling toLocaleString."""
        assert 'typeof race.e' in configurator_html, \
            "Must check typeof race.e before toLocaleString (could be string)"


class TestConfiguratorRaceCountDynamic:
    """Verify race count is computed dynamically, not hardcoded."""

    def test_placeholder_matches_actual_count(self, configurator_html):
        """Search placeholder race count must match actual race-index.json count."""
        race_index = load_race_index()
        actual_count = len(race_index)
        assert f"Search {actual_count} races" in configurator_html, \
            f"Placeholder count doesn't match actual race count ({actual_count})"

    def test_meta_description_matches_actual_count(self, configurator_html):
        """Meta description race count must match actual race-index.json count."""
        race_index = load_race_index()
        actual_count = len(race_index)
        assert f"{actual_count} scored events" in configurator_html, \
            f"Meta description count doesn't match actual ({actual_count})"

    def test_race_data_entry_count_matches(self, configurator_html):
        """Embedded GG_RACES array must have same count as race-index.json."""
        race_index = load_race_index()
        actual_count = len(race_index)
        # Count entries by counting "s": patterns (slug key)
        embedded_count = configurator_html.count('"s":')
        assert embedded_count == actual_count, \
            f"Embedded race count ({embedded_count}) != index count ({actual_count})"


class TestRendererNullSafety:
    """Verify renderers handle None/missing _RACE_INDEX gracefully."""

    def test_race_ref_with_null_index(self):
        """render_race_reference with None index returns comment, not crash."""
        generate_guide._RACE_INDEX = None
        try:
            html = render_race_reference({"slug": "test"})
            assert "<!-- " in html
            assert "race not found" in html
        finally:
            generate_guide._RACE_INDEX = None

    def test_callout_with_null_index(self):
        """render_race_callout with None index returns comment, not crash."""
        generate_guide._RACE_INDEX = None
        try:
            html = render_race_callout({"slugs": ["a", "b"]})
            assert "<!-- " in html
        finally:
            generate_guide._RACE_INDEX = None

    def test_decision_tree_with_empty_tree(self):
        """Decision tree with empty tree dict renders without crash."""
        html = render_decision_tree({"tree": {}})
        assert "gg-decision-tree" in html

    def test_decision_tree_with_no_options(self):
        """Decision tree with root but no options renders without crash."""
        tree = {"root": {"question": "Test question?"}}
        html = render_decision_tree({"tree": tree})
        assert "Test question?" in html

    def test_race_ref_with_missing_block_keys(self):
        """Race reference block with no slug returns graceful fallback."""
        generate_guide._RACE_INDEX = {"test": {"name": "T", "slug": "test"}}
        try:
            html = render_race_reference({})
            assert "<!-- " in html
        finally:
            generate_guide._RACE_INDEX = None


# ── Script Injection Safety ─────────────────────────────────


class TestScriptInjectionSafety:
    """Verify </script> sequences in JSON data don't break inline <script> tags."""

    def test_safe_json_for_script_escapes_close_tag(self):
        """_safe_json_for_script replaces </ with <\\/ to prevent script breakout."""
        from generate_guide import _safe_json_for_script
        data = {"name": "test</script><img onerror=alert(1) src=x>"}
        result = _safe_json_for_script(data)
        assert "</" not in result
        assert "<\\/" in result

    def test_safe_json_for_script_preserves_valid_json(self):
        """Output is still valid JSON when <\\/ is read by a JS parser."""
        from generate_guide import _safe_json_for_script
        import json
        data = {"a": "hello</script>world", "b": 42, "c": [1, 2, 3]}
        result = _safe_json_for_script(data)
        # <\/ is valid in JSON strings (backslash-forward-slash)
        parsed = json.loads(result)
        assert parsed["a"] == "hello</script>world"
        assert parsed["b"] == 42

    def test_safe_json_passes_kwargs(self):
        """_safe_json_for_script passes kwargs to json.dumps."""
        from generate_guide import _safe_json_for_script
        result = _safe_json_for_script({"a": 1}, separators=(",", ":"))
        assert result == '{"a":1}'

    def test_configurator_race_data_no_raw_close_script(self):
        """Configurator race data JS never contains literal </script>."""
        from generate_guide_cluster import build_configurator_race_data
        js = build_configurator_race_data()
        assert "</script" not in js.lower(), \
            "Race data JS must not contain </script (could break page)"

    def test_cluster_jsonld_no_raw_close_script(self, all_htmls):
        """All JSON-LD script tags use safe serialization."""
        import re
        for slug, html in all_htmls.items():
            # Find all JSON-LD script blocks
            ld_blocks = re.findall(
                r'<script type="application/ld\+json">(.*?)</script>',
                html, re.DOTALL
            )
            for block in ld_blocks:
                # The block should not contain a nested </script
                inner_close = block.find("</script")
                assert inner_close == -1, \
                    f"JSON-LD in {slug} contains </script at position {inner_close}"


# ── Decision Tree Validation ────────────────────────────────


class TestDecisionTreeValidation:
    """Verify decision tree build-time validation catches broken references."""

    def test_valid_tree_renders(self):
        """A well-formed tree renders without errors."""
        tree = {
            "root": {
                "question": "Pick one",
                "options": [
                    {"text": "A", "next": "node_a"},
                    {"text": "B", "result": "some-slug"},
                ],
            },
            "node_a": {
                "question": "Sub-question",
                "options": [{"text": "C", "result": "another-slug"}],
            },
        }
        html = render_decision_tree({"tree": tree})
        assert "gg-decision-tree" in html

    def test_invalid_next_ref_raises(self):
        """A next reference to a nonexistent node raises ValueError."""
        tree = {
            "root": {
                "question": "Pick one",
                "options": [{"text": "A", "next": "typo_node"}],
            },
        }
        with pytest.raises(ValueError, match="typo_node"):
            render_decision_tree({"tree": tree})

    def test_result_ref_does_not_need_node(self):
        """A result reference (leaf) does not need a matching node."""
        tree = {
            "root": {
                "question": "Pick one",
                "options": [{"text": "A", "result": "some-race-slug"}],
            },
        }
        # Should not raise
        html = render_decision_tree({"tree": tree})
        assert "gg-decision-tree" in html

    def test_actual_content_tree_is_valid(self):
        """The real decision tree in gravel-guide-content.json passes validation."""
        import json
        from pathlib import Path
        content_path = Path(__file__).parent.parent / "guide" / "gravel-guide-content.json"
        content = json.loads(content_path.read_text())
        for chapter in content["chapters"]:
            for section in chapter.get("sections", []):
                for block in section.get("blocks", []):
                    if block.get("type") == "decision_tree":
                        # Should not raise
                        render_decision_tree(block)


# ── Personalized Content Validation ─────────────────────────


class TestPersonalizedContentValidation:
    """Verify render_personalized_content rejects invalid rider types."""

    def test_misspelled_rider_raises(self):
        """Misspelled rider type key raises ValueError."""
        from generate_guide import render_personalized_content
        block = {
            "variants": {
                "finisher": {"content": "ok"},
                "compettior": {"content": "typo"},  # misspelled
            }
        }
        with pytest.raises(ValueError, match="compettior"):
            render_personalized_content(block)

    def test_valid_rider_types_accepted(self):
        """All 4 valid rider types render without error."""
        from generate_guide import render_personalized_content
        block = {
            "variants": {
                "ayahuasca": {"content": "A content"},
                "finisher": {"content": "F content"},
                "competitor": {"content": "C content"},
                "podium": {"content": "P content"},
            }
        }
        html = render_personalized_content(block)
        assert html.count("gg-personalized__variant") == 4

    def test_subset_of_riders_accepted(self):
        """Providing only some valid rider types is allowed."""
        from generate_guide import render_personalized_content
        block = {
            "variants": {
                "finisher": {"content": "F only"},
            }
        }
        html = render_personalized_content(block)
        assert 'data-rider-type="finisher"' in html


# ── Tier Badge CSS Completeness ─────────────────────────────


class TestTierBadgeCSS:
    """Verify CSS covers all 4 tier levels for callout badges."""

    def test_all_four_tiers_styled(self, chapter_htmls):
        """CSS must have color rules for tiers 1-4."""
        # Use a chapter page (has full guide CSS with callout styles)
        any_page = next(iter(chapter_htmls.values()))
        for tier in ["1", "2", "3", "4"]:
            css_rule = f'.gg-race-callout__tier[data-tier="{tier}"]'
            assert css_rule in any_page, \
                f"Missing CSS rule for tier {tier} badge: {css_rule}"


# ── Personalized Visibility (No Inline Display:None) ────────


class TestPersonalizedVisibilityCSS:
    """Verify personalized content uses CSS class visibility, not inline styles."""

    def test_no_inline_display_none_on_personalized(self, all_htmls):
        """No personalized variant divs should have inline style='display:none'."""
        import re
        for slug, html in all_htmls.items():
            matches = re.findall(
                r'class="gg-personalized__variant[^"]*"[^>]*style="display:none"',
                html
            )
            assert matches == [], \
                f"{slug} has inline display:none on personalized variants; use CSS class instead"

    def test_personalized_css_hides_inactive(self, all_htmls):
        """CSS must hide non-active personalized variants via opacity/visibility."""
        any_page = next(iter(all_htmls.values()))
        # Default state: opacity:0, visibility:hidden
        css_section = any_page.replace(" ", "")
        assert "opacity:0" in css_section
        assert "visibility:hidden" in css_section
