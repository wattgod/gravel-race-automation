"""Markdown deploy gate: race pages must ship with their /race/{slug}.md mirror.

Mirror of tests/test_prep_kit_deploy_gate.py. Every race page links
<link rel="alternate" type="text/markdown" href="/race/{slug}.md">; 30 profiles
shipped without the mirror before 2026-09-09 and the weekly link-check went red.
"""
import os
import site
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import push_wordpress as pw

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestPureGate:
    def test_all_present_means_nothing_missing(self):
        gated, missing = pw.markdown_gate(["a", "b"], ["a", "b"], ["a", "b"])
        assert gated == ["a", "b"] and missing == []

    def test_non_race_pages_are_not_gated(self):
        gated, missing = pw.markdown_gate(["a", "hub"], [], ["a"])
        assert gated == ["a"] and missing == ["a"]

    def test_missing_named_in_sorted_order(self):
        gated, missing = pw.markdown_gate(["b", "a"], [], ["a", "b"])
        assert gated == ["a", "b"] and missing == ["a", "b"]

    def test_only_new_profiles_missing(self):
        old, new = ["a", "b"], ["c", "d"]
        gated, missing = pw.markdown_gate(old + new, old, old + new)
        assert missing == new


class TestFilesystemWrapper:
    def test_reads_stems_and_ignores_root_canonical(self, tmp_path):
        pages_dir, md_dir, race_dir = tmp_path / "output", tmp_path / "md", tmp_path / "race-data"
        for d in (pages_dir, md_dir, race_dir):
            d.mkdir()
        for s in ("a", "b"):
            (pages_dir / f"{s}.html").write_text("<html></html>")
            (race_dir / f"{s}.json").write_text("{}")
        (pages_dir / "about.html").write_text("<html></html>")
        (md_dir / "a.md").write_text("# a")
        gated, missing = pw.check_markdown_gate(pages_dir, md_dir, race_dir)
        assert gated == ["a", "b"] and missing == ["b"]

    def test_missing_markdown_dir_means_everything_missing(self, tmp_path):
        pages_dir, race_dir = tmp_path / "output", tmp_path / "race-data"
        pages_dir.mkdir(); race_dir.mkdir()
        (pages_dir / "a.html").write_text("<html></html>")
        (race_dir / "a.json").write_text("{}")
        gated, missing = pw.check_markdown_gate(pages_dir, tmp_path / "nope", race_dir)
        assert gated == ["a"] and missing == ["a"]


class TestGateWiring:
    @pytest.fixture
    def tree(self, tmp_path, monkeypatch):
        pages_dir = tmp_path / "output"
        md_dir = tmp_path / "markdown"
        race_dir = tmp_path / "race-data"
        for d in (pages_dir, md_dir, race_dir):
            d.mkdir(parents=True)
        for s in ("a", "b"):
            (pages_dir / f"{s}.html").write_text("<html></html>")
            (race_dir / f"{s}.json").write_text("{}")
        (md_dir / "a.md").write_text("# a")
        monkeypatch.setattr(pw, "RACE_DATA_DIR", race_dir)
        return pages_dir, md_dir

    @staticmethod
    def _args(pages_dir, md_dir, **overrides):
        base = dict(sync_pages=True, sync_markdown=False, no_markdown_gate=False,
                    pages_dir=str(pages_dir), markdown_dir=str(md_dir))
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_missing_mirror_exits_1_naming_the_slug(self, tree, capsys):
        args = self._args(*tree)
        with pytest.raises(SystemExit) as exc:
            pw.apply_markdown_gate(args)
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "MARKDOWN GATE: 1 of 2 race pages" in out
        assert "b  → /race/b.md would 404" in out
        assert "generate_markdown_profiles.py" in out and "--no-markdown-gate" in out
        assert args.sync_markdown is False

    def test_mirrors_present_forces_markdown_sync_into_the_deploy(self, tree, capsys):
        pages_dir, md_dir = tree
        (md_dir / "b.md").write_text("# b")
        args = self._args(pages_dir, md_dir)
        pw.apply_markdown_gate(args)
        assert args.sync_markdown is True
        assert "adding --sync-markdown" in capsys.readouterr().out

    def test_explicit_markdown_sync_is_left_alone(self, tree, capsys):
        pages_dir, md_dir = tree
        (md_dir / "b.md").write_text("# b")
        args = self._args(pages_dir, md_dir, sync_markdown=True)
        pw.apply_markdown_gate(args)
        assert args.sync_markdown is True and "adding" not in capsys.readouterr().out

    def test_escape_hatch_skips_the_gate(self, tree):
        args = self._args(*tree, no_markdown_gate=True)
        pw.apply_markdown_gate(args)
        assert args.sync_markdown is False

    def test_no_sync_pages_is_a_no_op(self, tree):
        args = self._args(*tree, sync_pages=False)
        pw.apply_markdown_gate(args)
        assert args.sync_markdown is False


class TestCliEndToEnd:
    """Same two guards as test_prep_kit_deploy_gate: empty SSH creds + tmp HOME."""

    def _run(self, tmp_path, *argv):
        env = dict(os.environ)
        env.update({"SSH_HOST": "", "SSH_USER": "", "WP_URL": "", "WP_USER": "", "WP_APP_PASSWORD": ""})
        home = tmp_path / "home"
        home.mkdir(exist_ok=True)
        env["HOME"] = str(home)
        env["PYTHONPATH"] = os.pathsep.join(
            p for p in [site.getusersitepackages(), env.get("PYTHONPATH", "")] if p)
        return subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "push_wordpress.py"), *argv],
            capture_output=True, text=True, env=env, cwd=PROJECT_ROOT, timeout=60)

    def test_race_page_with_kit_but_no_mirror_is_refused(self, tmp_path):
        pages_dir = tmp_path / "output"
        kit_dir = pages_dir / "prep-kit"
        md_dir = tmp_path / "markdown"
        kit_dir.mkdir(parents=True); md_dir.mkdir()
        (pages_dir / "unbound-200.html").write_text("<html></html>")
        (kit_dir / "unbound-200.html").write_text("<html></html>")
        proc = self._run(tmp_path, "--sync-pages", "--pages-dir", str(pages_dir),
                         "--prep-kit-dir", str(kit_dir), "--markdown-dir", str(md_dir))
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "MARKDOWN GATE: 1 of 1 race pages" in proc.stdout
        assert "unbound-200  → /race/unbound-200.md would 404" in proc.stdout
        assert "Uploading" not in proc.stdout and "DEPLOY FAILED" not in proc.stdout
