"""Regression coverage for the WordPress heading normalizer."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "wordpress" / "mu-plugins" / "gg-heading-normalizer.php"
DEPLOYER = ROOT / "scripts" / "push_wordpress.py"


def test_plugin_normalizes_the_final_server_response():
    source = PLUGIN.read_text()
    assert "is_singular()" in source
    assert "ob_start( 'gg_h1_normalize_response' )" in source
    assert "template_redirect" in source


def test_plugin_repairs_empty_and_placeholder_titles():
    source = PLUGIN.read_text()
    assert "heading_text === ''" in source
    assert "POST_TITLE" in source
    assert "00A0" in source
    assert "esc_html( $title )" in source


def test_plugin_demotes_every_h1_after_the_first():
    source = PLUGIN.read_text()
    assert "if ( $seen === 1 )" in source
    assert "return '<h2' . $match[1]" in source


def test_plugin_injects_after_navigation_when_h1_is_missing():
    source = PLUGIN.read_text()
    assert "data-elementor-type" in source
    assert "wp-page" in source
    assert "gg-auto-title" in source
    assert "<main" in source


def test_deployer_exposes_and_runs_heading_sync():
    source = DEPLOYER.read_text()
    assert "def sync_headings():" in source
    assert '"--sync-headings"' in source
    assert "args.sync_headings = True" in source
    assert '_run("sync-headings", sync_headings)' in source
