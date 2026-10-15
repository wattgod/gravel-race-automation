"""/athletes/ page (receipts spec §5.5, PR-5): generate_athletes.py and
receipts_components.py, rendered from the synthetic fixture only."""
from __future__ import annotations

import html as html_lib
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

import generate_athletes as ga  # noqa: E402
import receipts_components as rc  # noqa: E402
import receipts_data as rd  # noqa: E402

FIXTURE = json.loads(rd.FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(rd.ENV_PATH, raising=False)
    monkeypatch.delenv(rd.ENV_BUILD, raising=False)


@pytest.fixture
def ledger():
    return rd.load_ledger("gravelgod")


@pytest.fixture
def page(ledger):
    return ga.generate_athletes_page(ledger)


@pytest.fixture
def empty_page(ledger):
    ledger.receipts = []
    return ga.generate_athletes_page(ledger)


def _carousel(html: str) -> str:
    m = re.search(r'<div class="gg-exchange" data-exchange-carousel.*?</div></div>', html, re.S)
    assert m, "carousel not rendered"
    return m.group(0)


# A private-shaped ledger for production-path tests: the fixture with every
# fixture marker swapped for invented values production doesn't recognise as
# placeholders (".invalid" is a reserved TLD, the names are nobody).
_PRIVATE_SWAPS = (
    ("Test Rider A", "Qazwi Xenrot"),
    ("TestRider B.", "Qazwi B."), ("TestRiderC", "Qazwic"), ("Test Rider E", "Qazwe Xenrot"),
    ("https://example.com/", "https://timing.invalid/"),
    ("https://example.org/", "https://timing.invalid/"), ("Example Gravel", "Sample Gravel"),
)


def _private_ledger(tmp_path: Path) -> Path:
    """A non-synthetic, private-shaped copy of the fixture."""
    text = rd.FIXTURE_PATH.read_text(encoding="utf-8")
    for old, new in _PRIVATE_SWAPS:
        text = text.replace(old, new)
    doc = json.loads(text)
    doc.pop("synthetic")
    shutil.copytree(rd.FIXTURE_PATH.parent / "receipts_media", tmp_path / "receipts_media")
    path = tmp_path / "receipts.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


# ── Empty state ──────────────────────────────────────────────────────────


class TestEmptyState:
    def test_no_carousel_no_people(self, empty_page):
        assert "data-exchange-carousel" not in empty_page  # no markup, no carousel JS
        assert "data-receipt-id" not in empty_page
        assert "Test Rider" not in empty_page and "TestRider" not in empty_page
        assert 'id="stories"' not in empty_page
        assert 'id="archetypes"' not in empty_page

    def test_honest_empty_state_and_count(self, empty_page):
        assert 'id="empty"' in empty_page
        assert html_lib.escape(ga.COPY["empty_state"]) in empty_page
        assert 'data-receipts-count="12"' in empty_page
        # "Every story here..." would be false with no stories.
        assert rc.VERIFICATION_LINE not in empty_page

    def test_cta_still_there(self, empty_page):
        assert 'href="https://gravelgodcycling.com/coaching/"' in empty_page


# ── Fixture render ───────────────────────────────────────────────────────


class TestFixtureRender:
    def test_approved_athletes_render(self, page):
        for name in ("Test Rider A", "TestRider B.", "TestRiderC, 50-54"):
            assert name in page

    def test_unrenderable_entries_stay_out(self, page):
        assert "r-904" not in page  # count_only
        assert "r-905" not in page  # withdrawn
        assert "Test Rider E" not in page
        assert "Withdrawn, never rendered" not in page

    def test_results_link_to_official_pages(self, page):
        assert 'href="https://example.com/results/example-gravel-100"' in page
        assert "14 of 120" in page

    def test_disclosure_inline(self, page):
        assert "Coached at no charge" in page

    def test_count_and_verification_lines(self, page):
        assert ('data-receipts-count="12">12 athletes coached since 2023-10; those who chose '
                "not to be named appear only in this count") in page
        assert rc.VERIFICATION_LINE in page

    def test_every_person_element_is_inside_a_receipt(self, page):
        """Story blocks, cards, grid entries and slides all carry the id."""
        for r in rd.load_receipts():
            assert (f'<article class="gg-receipt-story" id="{r.anchor}" '
                    f'data-receipt-id="{r.id}">') in page
            assert f'<li class="gg-archetype-athlete" data-receipt-id="{r.id}">' in page

    def test_story_voice(self, page):
        by_id = {r.id: r for r in rd.load_receipts()}
        a = re.search(rf'id="{by_id["r-901"].anchor}".*?</article>', page, re.S).group(0)
        c = re.search(rf'id="{by_id["r-903"].anchor}".*?</article>', page, re.S).group(0)
        assert '<blockquote class="gg-receipt-story-quote">' in a  # athlete's words, quoted
        assert "gg-receipt-story-quote" not in c  # editorial, not dressed as a quote
        assert "Coached since November 2023" in c

    def test_no_private_fields_in_output(self, page):
        for e in FIXTURE["receipts"]:
            assert e["source_ref"] not in page
            assert e["consent_id"] not in page
        assert "source_ref" not in page and "consent_id" not in page

    def test_marked_synthetic_and_noindex(self, page):
        assert '<meta name="gg-receipts-source" content="synthetic">' in page
        assert '<meta name="robots" content="noindex, nofollow">' in page

    def test_rendered_people_are_all_synthetic(self, page):
        names = re.findall(r'class="gg-receipt-story-name">([^<]+)<', page)
        assert names and all(n.startswith("Test") for n in names)


# ── Archetype grid ───────────────────────────────────────────────────────


class TestArchetypeGrid:
    def test_matrix_shape_and_honest_empties(self, page):
        grid = re.search(r'<table class="gg-archetype-grid">.*?</table>', page, re.S).group(0)
        assert grid.count('<th scope="row">') == 4
        for band in ("Under 30", "30s", "40s", "50+"):
            assert f'<th scope="row">{html_lib.escape(band)}</th>' in grid
        assert grid.count('class="gg-archetype-cell') == 16
        assert grid.count("gg-archetype-empty") == 13  # 3 covered cells in the fixture

    def test_cells_link_to_story_anchors(self, page):
        for r in rd.load_receipts():
            assert f'href="#{r.anchor}"' in page
            assert f'id="{r.anchor}"' in page

    def test_anchors_and_media_names_are_opaque(self, page, ledger):
        """Review finding 5: URLs and anchors don't spell out the ledger id."""
        for r in ledger.receipts:
            assert r.id not in r.anchor and re.fullmatch(r"athlete-[0-9a-f]{16}", r.anchor)
            for ex in r.exchanges:
                assert r.id not in ex.media_name
                assert re.fullmatch(r"[0-9a-f]{16}\.png", ex.media_name)
        assert 'href="#athlete-synthetic' not in page
        assert "/athletes/media/synthetic" not in page


# ── Carousel markup and accessibility ────────────────────────────────────


class TestCarousel:
    def test_carousel_semantics(self, page):
        c = _carousel(page)
        assert 'aria-roledescription="carousel"' in c
        assert c.count('aria-roledescription="slide"') == 3
        assert 'tabindex="0"' in c
        assert 'aria-label="1 of 3"' in c

    def test_slides_are_receipt_figures(self, page):
        slides = re.findall(r'<figure class="gg-exchange-slide" data-receipt-id="([^"]+)" '
                            r'data-exchange-id="([^"]+)"', page)
        # Rank order: A/ex-1 (1), B/ex-1 (2), A/ex-2 (3).
        assert slides == [("r-901", "ex-1"), ("r-902", "ex-1"),
                          ("r-901", "ex-2")]

    def test_alt_is_the_verbatim_transcript(self, page):
        for e in FIXTURE["receipts"][:2]:
            for ex in e["exchanges"]:
                assert f'alt="{html_lib.escape(ex["alt"], quote=True)}"' in page

    def test_caption_name_and_month(self, page):
        assert re.search(r'<figcaption class="gg-exchange-caption">.*?Test Rider A.*?March 2026',
                         page, re.S)

    def test_nav_buttons_and_counter(self, page):
        c = _carousel(page)
        assert '<button type="button" class="gg-exchange-btn" data-exchange-prev' in c
        assert '<button type="button" class="gg-exchange-btn" data-exchange-next' in c
        assert 'aria-label="Previous exchange"' in c and 'aria-label="Next exchange"' in c
        assert ">1 / 3</span>" in c
        assert 'aria-live="polite"' in c

    def test_carousel_is_a_region(self, page):
        assert 'role="region" aria-roledescription="carousel"' in _carousel(page)

    def test_end_buttons_keep_focus(self):
        """Review finding 8: `disabled` drops keyboard focus to <body>."""
        js = rc.get_exchange_carousel_js()
        assert ".disabled" not in js
        assert "setAttribute('aria-disabled'" in js
        assert "if (atEnd(next)) return;" in js and "if (atEnd(prev)) return;" in js
        css = rc.get_receipts_css()
        assert ":disabled" not in css and '[aria-disabled="true"]' in css

    def test_buttons_disable_only_at_the_true_ends(self):
        """Re-review finding F: no disabling while part of a slide is hidden."""
        js = rc.get_exchange_carousel_js()
        assert "var atStart = track.scrollLeft <= 1;" in js
        assert "var atFinish = track.scrollLeft >= maxScroll() - 1;" in js
        assert "range[1] === total - 1 ||" not in js and "range[0] === 0 ||" not in js

    def test_counter_follows_scroll_position(self):
        """Review finding 8: the counter reports the slides on screen (measured
        from the scroll position), so "1 / 3" never jumps to "3 / 3" when two
        slides fit; it reads "1–2 / 3" then "2–3 / 3"."""
        js = rc.get_exchange_carousel_js()
        assert "function visibleRange()" in js
        assert "getBoundingClientRect()" in js
        assert "go(1)" in js and "go(-1)" in js
        assert "scroll-padding-inline" in rc.get_receipts_css()

    def test_cls_dimensions_reserved(self, page, ledger):
        imgs = re.findall(r"<img class=\"gg-exchange-img\"[^>]*>", page)
        assert len(imgs) == 3
        dims = {ex.media_name: (ex.width, ex.height) for ex in ledger.exchanges}
        for img in imgs:
            src = re.search(r'src="/athletes/media/([^"]+)"', img).group(1)
            w = int(re.search(r'width="(\d+)"', img).group(1))
            h = int(re.search(r'height="(\d+)"', img).group(1))
            assert (w, h) == dims[src]
            assert 'loading="lazy"' in img

    def test_works_without_js(self):
        css = rc.get_receipts_css()
        assert re.search(r"\.gg-exchange-track \{[^}]*overflow-x: auto", css)
        assert re.search(r"\.gg-exchange-track \{[^}]*scroll-snap-type: x mandatory", css)
        # Buttons only show once JS has wired them.
        assert re.search(r"\.gg-exchange-nav \{[^}]*display: none", css)
        assert ".gg-exchange--js .gg-exchange-nav { display: flex; }" in css


# ── JS: no autoplay, GA only on user actions, no innerHTML ───────────────


class TestScripts:
    def test_no_timers_anywhere_in_page_js(self):
        js = ga.build_athletes_js()
        for timer in ("setInterval", "setTimeout", "requestAnimationFrame", "autoplay", "autoAdvance"):
            assert timer not in js

    def test_carousel_ga_only_from_click_or_key(self):
        js = rc.get_exchange_carousel_js()
        calls = [line for line in js.splitlines() if "track_event(" in line
                 and "function track_event" not in line]
        assert calls
        for line in calls:
            assert ("addEventListener('click'" in line) or ("e.key ===" in line), line
        assert js.count("gtag(") == 1  # only inside track_event
        # The scroll handler updates the counter and never reports.
        assert "track.addEventListener('scroll', update" in js

    def test_page_ga_events_are_clicks(self):
        js = ga.build_athletes_js()
        lines = js.splitlines()
        gtag_at = [i for i, l in enumerate(lines) if "gtag('event'" in l]
        assert gtag_at
        # Each page-level gtag is the body of the click listener on the line above.
        for i in gtag_at:
            if "function track_event" in lines[i - 1]:
                continue  # carousel helper, covered above
            assert "addEventListener('click'" in lines[i - 1], lines[i - 1]
        from scroll_animations import get_scroll_animation_js
        assert "gtag" not in get_scroll_animation_js()

    def test_proof_link_event_param(self):
        """Review finding 10: the parameter is proof_type, valued 'timing'."""
        js = ga.build_athletes_js()
        assert "gtag('event', 'proof_link_click', { proof_type: el.getAttribute('data-proof') })" in js
        assert "{ timing:" not in js

    @pytest.mark.parametrize("source", ["page", "carousel"])
    def test_no_innerhtml(self, source):
        js = ga.build_athletes_js() if source == "page" else rc.get_exchange_carousel_js()
        assert "innerHTML" not in js and "outerHTML" not in js
        assert "insertAdjacentHTML" not in js and "document.write" not in js

    def test_no_inline_handlers(self, page):
        assert not re.search(r"\son(?:click|submit|keydown|load)=", page)


# ── Motion ───────────────────────────────────────────────────────────────


class TestReducedMotion:
    def test_scroll_animation_css_is_gated(self):
        css = ga.build_athletes_css()
        start = css.index("Scroll animations (shared)")
        assert "@media (prefers-reduced-motion: no-preference)" in css[start:]
        # Hidden state only applies once JS marked the page.
        assert ".gg-has-js [data-animate=\"fade-stagger\"] > *" in css

    def test_carousel_respects_reduced_motion(self):
        js = rc.get_exchange_carousel_js()
        assert "prefers-reduced-motion: reduce" in js
        assert "behavior: reduce ? 'auto' : 'smooth'" in js
        assert "@media (prefers-reduced-motion: reduce)" in rc.get_receipts_css()

    def test_only_short_blocks_animate(self, page):
        """The observer needs 20% of a block in view; tall blocks never get it."""
        assert len(re.findall(r'<div[^>]* data-animate="fade-stagger"', page)) == 1
        assert re.search(r'id="count">\s*<div class="gg-section-body" data-animate="fade-stagger">', page)

    def test_only_brand_motion(self):
        css = ga.build_athletes_css()
        assert "@keyframes" not in css
        assert "bounce" not in css.lower()


# ── Page infrastructure (matches generate_about.py) ──────────────────────


class TestInfrastructure:
    def test_ga4_fonts_header_footer_consent(self, page):
        assert "G-EJJZ9T6M52" in page
        assert "@font-face" in page
        assert 'class="gg-site-header"' in page
        assert "gg-mega-footer" in page
        assert "gg-consent" in page or "Privacy choices" in page

    def test_jsonld_webpage(self, page):
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
        data = [json.loads(b) for b in blocks]
        assert any(d.get("@type") == "WebPage" and d["url"].endswith("/athletes/") for d in data)
        assert "aggregateRating" not in page
        assert not any(d.get("@type") == "Person" for d in data)  # no athlete structured data

    def test_canonical(self, page):
        assert '<link rel="canonical" href="https://gravelgodcycling.com/athletes/">' in page

    def test_brand_rules_in_css(self):
        css = ga.build_athletes_css()
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "hex colour in athletes CSS"
        assert "border-radius" not in css
        assert "box-shadow" not in css

    def test_no_testimonial_class(self, page):
        classes = " ".join(re.findall(r'class="([^"]*)"', page))
        assert "testimonial" not in classes

    def test_class_prefixes(self):
        markup = (rc.get_receipts_css())
        for cls in set(re.findall(r"\.(gg-[a-z0-9-]+)", markup)):
            assert cls.startswith(("gg-receipt", "gg-exchange", "gg-archetype")), cls


# ── COPY briefs and production builds ────────────────────────────────────


class TestCopyAndProduction:
    def test_copy_values_are_briefs_until_matti_writes_them(self):
        """Today every COPY value is a brief. When Matti fills one in, this
        test needs no change; the production test below guards the rest."""
        for key, value in ga.COPY.items():
            assert isinstance(value, str) and value.strip(), key

    def test_production_build_fails_on_unwritten_copy(self, tmp_path, monkeypatch):
        monkeypatch.setenv(rd.ENV_BUILD, "production")
        monkeypatch.setenv(rd.ENV_PATH, str(_private_ledger(tmp_path)))
        monkeypatch.setitem(ga.COPY, "hero_headline", "[MATTI WRITES: still a brief]")
        with pytest.raises(SystemExit, match="COPY is unwritten"):
            ga.generate_athletes_page(rd.load_ledger("gravelgod"))

    def test_production_build_passes_once_copy_is_written(self, tmp_path, monkeypatch):
        monkeypatch.setenv(rd.ENV_BUILD, "production")
        monkeypatch.setenv(rd.ENV_PATH, str(_private_ledger(tmp_path)))
        for key in list(ga.COPY):
            monkeypatch.setitem(ga.COPY, key, f"Written copy for {key}.")
        html = ga.generate_athletes_page(rd.load_ledger("gravelgod"))
        assert "[MATTI WRITES" not in html
        assert "gg-receipts-source" not in html
        assert '<meta name="robots" content="index, follow">' in html

    def test_production_refuses_the_fixture(self, monkeypatch):
        monkeypatch.setenv(rd.ENV_BUILD, "production")
        with pytest.raises(rd.ReceiptsConfigError):
            rd.load_ledger("gravelgod")

    def test_production_refuses_a_synthetic_ledger_object(self, ledger, monkeypatch):
        for key in list(ga.COPY):
            monkeypatch.setitem(ga.COPY, key, f"Written copy for {key}.")
        monkeypatch.setenv(rd.ENV_BUILD, "production")
        with pytest.raises(SystemExit, match="synthetic"):
            ga.generate_athletes_page(ledger)

    def test_main_refuses_production_without_a_private_ledger(self, tmp_path, monkeypatch):
        monkeypatch.setenv(rd.ENV_BUILD, "production")
        monkeypatch.setattr(sys, "argv", ["generate_athletes.py", "--output-dir", str(tmp_path)])
        with pytest.raises(SystemExit, match="GG_RECEIPTS_PATH"):
            ga.main()


# ── Media copy ───────────────────────────────────────────────────────────


def test_media_copied_under_published_names_and_stale_files_removed(tmp_path, ledger):
    media_dir = tmp_path / "athletes" / "media"
    media_dir.mkdir(parents=True)
    (media_dir / "withdrawn-rider-ex-9.png").write_bytes(b"stale")
    names = ga.copy_exchange_media(ledger, tmp_path)
    assert names == sorted(ex.media_name for ex in ledger.exchanges)
    assert sorted(p.name for p in media_dir.iterdir()) == names
    for ex in ledger.exchanges:
        assert rd.image_size(media_dir / ex.media_name) == (ex.width, ex.height)


try:
    import PIL  # noqa: F401
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


@pytest.mark.skipif(not _HAS_PIL, reason="metadata stripping needs Pillow")
def test_media_copy_strips_metadata(tmp_path):
    """Review finding 11: EXIF/GPS/text chunks never reach the server."""
    from PIL import Image, PngImagePlugin
    src_png = tmp_path / "in.png"
    info = PngImagePlugin.PngInfo()
    info.add_text("Author", "private-author-marker")
    Image.new("RGB", (5, 4), (10, 20, 30)).save(src_png, pnginfo=info)
    src_jpg = tmp_path / "in.jpg"
    exif = Image.Exif()
    exif[0x013B] = "private-artist-marker"  # Artist
    Image.new("RGB", (5, 4), (10, 20, 30)).save(src_jpg, exif=exif.tobytes())
    for src in (src_png, src_jpg):
        dst = tmp_path / f"out{src.suffix}"
        assert ga.strip_image_metadata(src, dst)
        data = dst.read_bytes()
        assert b"private-" not in data, src.name
        with Image.open(dst) as im:
            assert im.size == (5, 4)
            assert not im.getexif()
            assert "Author" not in im.info


@pytest.mark.skipif(not _HAS_PIL, reason="needs Pillow")
def test_exif_orientation_is_applied_and_dims_follow(tmp_path):
    """Re-review finding G: a phone screenshot stored sideways with an EXIF
    Orientation tag is published upright, and the page reserves the upright
    width/height."""
    from PIL import Image
    src = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90° CW on display
    Image.new("RGB", (6, 4), (10, 20, 30)).save(src, exif=exif.tobytes())
    assert rd.image_size(src) == (4, 6)
    dst = tmp_path / "out.jpg"
    assert ga.strip_image_metadata(src, dst)
    with Image.open(dst) as im:
        assert im.size == (4, 6)
        assert not im.getexif()


def test_production_media_copy_needs_pillow(tmp_path, ledger, monkeypatch):
    monkeypatch.setattr(ga, "strip_image_metadata", lambda src, dst: False)
    monkeypatch.setenv(rd.ENV_BUILD, "production")
    with pytest.raises(SystemExit, match="Pillow"):
        ga.copy_exchange_media(ledger, tmp_path)


# ── Deploy plumbing (scripts/push_wordpress.py; code only, never run here) ─


def _push_wordpress():
    sys.path.insert(0, str(ROOT / "scripts"))
    import push_wordpress
    return push_wordpress


def test_athletes_is_a_root_page_never_shipped_under_race():
    pw = _push_wordpress()
    assert "athletes" in pw.ROOT_CANONICAL_SLUGS
    assert callable(pw.sync_athletes)


def test_deploy_refuses_synthetic_and_unwritten_builds(page, tmp_path, monkeypatch):
    pw = _push_wordpress()
    blockers = pw.athletes_ship_blockers(page)
    assert any("synthetic" in b for b in blockers)
    assert any("COPY" in b for b in blockers)
    # sync_athletes stops before touching SSH.
    out = tmp_path / "athletes.html"
    out.write_text(page, encoding="utf-8")
    monkeypatch.setattr(pw, "get_ssh_credentials",
                        lambda: pytest.fail("must not connect for a synthetic build"))
    assert pw.sync_athletes(str(out)) is None


def _production_build(tmp_path, monkeypatch):
    monkeypatch.setenv(rd.ENV_BUILD, "production")
    monkeypatch.setenv(rd.ENV_PATH, str(_private_ledger(tmp_path)))
    for key in list(ga.COPY):
        monkeypatch.setitem(ga.COPY, key, f"Written copy for {key}.")
    ledger = rd.load_ledger("gravelgod")
    html = ga.generate_athletes_page(ledger)
    out_dir = tmp_path / "output"
    ga.copy_exchange_media(ledger, out_dir)
    page = out_dir / "athletes.html"
    page.write_text(html, encoding="utf-8")
    return page


def test_deploy_accepts_a_production_build(tmp_path, monkeypatch):
    pw = _push_wordpress()
    page = _production_build(tmp_path, monkeypatch)
    html = page.read_text(encoding="utf-8")
    assert pw.athletes_ship_blockers(html) == []
    assert pw.athletes_media_problems(html, page.parent / "athletes" / "media") == []


@pytest.mark.parametrize("planted,what", [
    ('<span data-receipt-id="synthetic-rider-a"></span>', "receipt id"),
    ('<span data-receipt-id="jane-smithson"></span>', "receipt id"),
    ("<p>Test Rider A</p>", "athlete name"),
    ("<p>TestRider B.</p>", "athlete name"),
    ('<a href="https://example.com/results">x</a>', "example.com"),
    ("<p>Example quote text. Replace with the athlete's exact approved words.</p>", "template"),
])
def test_deploy_refuses_fixture_leftovers_without_the_synthetic_flag(
        tmp_path, monkeypatch, planted, what):
    """Review finding 6: the ship gate doesn't trust the synthetic flag alone."""
    pw = _push_wordpress()
    html = _production_build(tmp_path, monkeypatch).read_text(encoding="utf-8")
    blockers = pw.athletes_ship_blockers(html.replace("</body>", planted + "</body>"))
    assert any(what in b for b in blockers), blockers


def test_deploy_refuses_media_mismatches(tmp_path, monkeypatch):
    """Review finding 7: every referenced screenshot exists, nothing extra ships."""
    pw = _push_wordpress()
    page = _production_build(tmp_path, monkeypatch)
    html = page.read_text(encoding="utf-8")
    media_dir = page.parent / "athletes" / "media"
    victim = sorted(media_dir.iterdir())[0]
    victim.unlink()
    assert any("missing locally" in p for p in pw.athletes_media_problems(html, media_dir))
    (media_dir / "stray.png").write_bytes(b"x")
    assert any("not referenced" in p and "stray.png" in p
               for p in pw.athletes_media_problems(html, media_dir))
    monkeypatch.setattr(pw, "get_ssh_credentials", lambda: pytest.fail("must not connect"))
    assert pw.sync_athletes(str(page)) is None


@pytest.mark.parametrize("upload", ["ok", "fails", "raises"])
def test_sync_always_purges_the_cache(tmp_path, monkeypatch, upload):
    """Review finding 7: purge after every upload attempt, success or not."""
    pw = _push_wordpress()
    page = _production_build(tmp_path, monkeypatch)
    calls = []

    def fake_upload(html_path, media_dir):
        if upload == "raises":
            raise RuntimeError("ssh dropped")
        return "https://gravelgodcycling.com/athletes/" if upload == "ok" else None

    monkeypatch.setattr(pw, "_upload_athletes", fake_upload)
    monkeypatch.setattr(pw, "purge_cache", lambda: calls.append("purge") or True)
    if upload == "raises":
        with pytest.raises(RuntimeError):
            pw.sync_athletes(str(page))
    else:
        result = pw.sync_athletes(str(page))
        assert (result is not None) == (upload == "ok")
    assert calls == ["purge"]


def test_every_css_token_exists():
    """Preflight's token check needs the brand repo; this one runs anywhere."""
    from brand_tokens import get_tokens_css
    defined = set(re.findall(r"(--gg-[a-z0-9-]+)\s*:", get_tokens_css()))
    used = set(re.findall(r"var\((--gg-[a-z0-9-]+)\)", ga.build_athletes_css()))
    assert used and used <= defined, sorted(used - defined)
