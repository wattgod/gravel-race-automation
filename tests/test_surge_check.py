"""Tests for the Surge Check page (wordpress/generate_surge_check.py, wordpress/surge_check/).

The maths must match Endure's (parity fixture run through node), the page must
keep the repo's HTML rules (GA4, fonts, no innerHTML, no inline handlers), the
four band lines must stay fixed and clean, and the deploy step must exist.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "wordpress"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import generate_surge_check as gsc  # noqa: E402

SRC = REPO_ROOT / "wordpress" / "surge_check"
PAGE_JS = (SRC / "surge-check.js").read_text(encoding="utf-8")
CORE_JS = (SRC / "surge-core.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def page() -> str:
    return gsc.generate_page()


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("out")
    gsc.write_output(out)
    return out / gsc.SLUG


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_maths_matches_endure_parity_fixture():
    result = subprocess.run(["node", str(REPO_ROOT / "tests" / "surge_check_parity.mjs")], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def test_page_has_analytics_fonts_and_canonical(page):
    assert "gtag(" in page or "googletagmanager" in page
    assert "@font-face" in page
    assert '<link rel="canonical" href="https://gravelgodcycling.com/surge-check/">' in page
    assert '<meta name="robots" content="index, follow">' in page


def test_page_loads_its_module_from_its_own_folder(page):
    assert '<script type="module" src="/surge-check/surge-check.js"></script>' in page
    assert 'from "./vendor/fit-file-parser-2.1.0.js"' in PAGE_JS
    assert 'from "./surge-core.js"' in PAGE_JS


def test_output_folder_holds_every_imported_file(built):
    for name in gsc.ASSETS + ("index.html",):
        assert (built / name).is_file(), name
    # No CDN at run time: the parser is self-hosted.
    assert "cdn.jsdelivr.net/npm" not in (built / "index.html").read_text()
    assert "jsdelivr" not in PAGE_JS


def test_no_innerhtml_and_no_inline_handlers(page):
    for source in (PAGE_JS, CORE_JS):
        assert "innerHTML" not in source
        assert "insertAdjacentHTML" not in source
    assert not re.search(r"\son[a-z]+=", page.split("<footer")[0].split('<main class="gg-sc"')[1])


def test_embed_talks_only_to_endure_and_checks_who_answers():
    assert 'data-endure="https://endurelabs.app"' in gsc.generate_page()
    # Messages go to Endure's origin only, and replies are taken only from the frame at that origin.
    assert "postMessage(rideMessage(current.ride, current.ftp), ENDURE)" in PAGE_JS
    assert "event.origin !== ENDURE || event.source !== embed.frame.contentWindow" in PAGE_JS
    # A local Endure is only honoured when the page itself is local.
    assert "if (local && asked)" in PAGE_JS


def test_files_are_never_sent_anywhere():
    for call in ("fetch(", "XMLHttpRequest", "sendBeacon", "WebSocket"):
        assert call not in PAGE_JS, call


def test_four_fixed_band_lines_cover_every_index():
    labels = re.findall(r'label: "([^"]+)"', CORE_JS)
    assert labels == ["Smooth", "Normal", "Surgy", "Very surgy"]
    assert re.findall(r"max: (\w+), key", CORE_JS) == ["10", "20", "30", "Infinity"]
    assert CORE_JS.count("line: (many) =>") == 4


def test_band_lines_pass_the_slop_gate():
    import slop_rules

    lines = re.findall(r"line: \(many\) => `([^`]+)`", CORE_JS)
    text = " ".join(re.sub(r"\$\{[^}]+\}", "the ride", line) for line in lines)
    assert slop_rules.check_text(text) == []


def test_esc_keeps_zero():
    assert gsc.esc(0) == "0"
    assert gsc.esc(None) == ""


def test_deploy_step_exists():
    import push_wordpress

    assert callable(push_wordpress.sync_surge_check)
    source = (REPO_ROOT / "scripts" / "push_wordpress.py").read_text()
    assert '"--sync-surge-check"' in source
    assert "public_html/surge-check" in source
