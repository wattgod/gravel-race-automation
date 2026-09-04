"""Prep-kit deploy gate (#122): race pages must never ship without their kits.

generate_prep_kit.py ran in preflight, but publishing the kits needed the
separate --sync-prep-kits opt-in, so race-add deploys shipped race pages whose
/race/{slug}/prep-kit/ 404'd (12+ slugs by 2026-09-04). These tests cover the
pure gate decision, its filesystem wrapper, and main() wiring — no network.
"""

from __future__ import annotations

import os
import site
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import push_wordpress as pw  # noqa: E402


class TestGateDecision:
    def test_shipping_race_page_without_kit_is_flagged(self):
        gated, missing = pw.prep_kit_gate(
            page_slugs=["unbound-200", "khomas100", "best-gravel-races-iowa"],
            kit_slugs=["unbound-200"],
            race_slugs=["unbound-200", "khomas100", "mid-south"])
        assert gated == ["khomas100", "unbound-200"]
        assert missing == ["khomas100"]

    def test_non_race_flat_pages_are_not_gated(self):
        gated, missing = pw.prep_kit_gate(
            ["best-gravel-races-iowa", "unbound-200-vs-mid-south", "calendar"],
            [], ["unbound-200", "mid-south"])
        assert gated == [] and missing == []

    def test_every_kit_present_passes(self):
        gated, missing = pw.prep_kit_gate(["a", "b"], ["a", "b", "the-mid-south"], ["a", "b"])
        assert gated == ["a", "b"] and missing == []

    def test_no_kits_at_all_lists_every_gated_slug(self):
        gated, missing = pw.prep_kit_gate(["b", "a"], [], ["a", "b"])
        assert gated == missing == ["a", "b"]

    def test_backlog_pattern_from_the_issue(self):
        """The #122 shape: kits generated for the old catalog, new races added."""
        old = [f"race-{i}" for i in range(20)]
        new = ["grand-tour-3-cime-lavaredo", "khomas100", "3rides-gravel-winterberg"]
        gated, missing = pw.prep_kit_gate(old + new, old, old + new)
        assert missing == sorted(new)


class TestGateFilesystem:
    def _tree(self, tmp_path, pages, kits, races):
        pages_dir = tmp_path / "output"
        kit_dir = pages_dir / "prep-kit"
        race_dir = tmp_path / "race-data"
        for d in (pages_dir, kit_dir, race_dir):
            d.mkdir(parents=True)
        for s in pages:
            (pages_dir / f"{s}.html").write_text("<html></html>")
        for s in kits:
            (kit_dir / f"{s}.html").write_text("<html></html>")
        for s in races:
            (race_dir / f"{s}.json").write_text("{}")
        return pages_dir, kit_dir, race_dir

    def test_reads_pages_kits_and_profiles(self, tmp_path):
        pages_dir, kit_dir, race_dir = self._tree(
            tmp_path, pages=["a", "b", "coaching"], kits=["a"], races=["a", "b", "coaching"])
        gated, missing = pw.check_prep_kit_gate(pages_dir, kit_dir, race_dir)
        # "coaching" is a ROOT_CANONICAL_SLUGS utility page, never gated.
        assert gated == ["a", "b"] and missing == ["b"]

    def test_absent_kit_dir_means_every_gated_slug_is_missing(self, tmp_path):
        pages_dir, kit_dir, race_dir = self._tree(tmp_path, ["a"], [], ["a"])
        gated, missing = pw.check_prep_kit_gate(pages_dir, tmp_path / "nope", race_dir)
        assert gated == missing == ["a"]

    def test_default_profile_dir_is_the_repo_race_data(self):
        assert pw.RACE_DATA_DIR == PROJECT_ROOT / "race-data"
        assert (pw.RACE_DATA_DIR / "unbound-200.json").exists()


class TestGateWiring:
    """apply_prep_kit_gate(args): the decision the CLI makes before any sync."""

    @pytest.fixture
    def tree(self, tmp_path, monkeypatch):
        pages_dir = tmp_path / "output"
        kit_dir = pages_dir / "prep-kit"
        race_dir = tmp_path / "race-data"
        for d in (pages_dir, kit_dir, race_dir):
            d.mkdir(parents=True)
        for s in ("a", "b"):
            (pages_dir / f"{s}.html").write_text("<html></html>")
            (race_dir / f"{s}.json").write_text("{}")
        (kit_dir / "a.html").write_text("<html></html>")
        monkeypatch.setattr(pw, "RACE_DATA_DIR", race_dir)
        return pages_dir, kit_dir

    @staticmethod
    def _args(pages_dir, kit_dir, **overrides):
        base = dict(sync_pages=True, sync_prep_kits=False, no_prep_kit_gate=False,
                    pages_dir=str(pages_dir), prep_kit_dir=str(kit_dir))
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_missing_kit_exits_1_naming_the_slug(self, tree, capsys):
        args = self._args(*tree)
        with pytest.raises(SystemExit) as exc:
            pw.apply_prep_kit_gate(args)
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "PREP-KIT GATE: 1 of 2 race pages" in out
        assert "b  → /race/b/prep-kit/ would 404" in out
        assert "generate_prep_kit.py --all" in out and "--no-prep-kit-gate" in out
        assert args.sync_prep_kits is False

    def test_kits_present_forces_kit_sync_into_the_deploy(self, tree, capsys):
        pages_dir, kit_dir = tree
        (kit_dir / "b.html").write_text("<html></html>")
        args = self._args(pages_dir, kit_dir)
        pw.apply_prep_kit_gate(args)
        assert args.sync_prep_kits is True
        assert "adding --sync-prep-kits" in capsys.readouterr().out

    def test_explicit_kit_sync_is_left_alone(self, tree, capsys):
        pages_dir, kit_dir = tree
        (kit_dir / "b.html").write_text("<html></html>")
        args = self._args(pages_dir, kit_dir, sync_prep_kits=True)
        pw.apply_prep_kit_gate(args)
        assert args.sync_prep_kits is True and "adding" not in capsys.readouterr().out

    def test_escape_hatch_skips_the_gate(self, tree):
        args = self._args(*tree, no_prep_kit_gate=True)
        pw.apply_prep_kit_gate(args)  # missing kit, but no exit
        assert args.sync_prep_kits is False

    def test_deploys_without_race_pages_are_untouched(self, tree):
        args = self._args(*tree, sync_pages=False)
        pw.apply_prep_kit_gate(args)
        assert args.sync_prep_kits is False

    def test_cli_calls_the_gate_before_the_first_sync(self):
        """The __main__ block must invoke the gate ahead of any _run() dispatch."""
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        main_block = source[source.index('if __name__ == "__main__":'):]
        gate_at = main_block.index("apply_prep_kit_gate(args)")
        assert gate_at < main_block.index("_run(")
        assert gate_at > main_block.index("args = parser.parse_args()")


class TestCliEndToEnd:
    """Run the real CLI with two independent guards so no ssh/tar can fire even
    from a checkout whose .env carries live creds: SSH_HOST/SSH_USER are set to
    "" (load_dotenv never overrides an existing variable, and empty creds make
    get_ssh_credentials() return None), and HOME points at tmp so SSH_KEY
    cannot exist. The user site-packages are re-added via PYTHONPATH because
    they hang off HOME."""

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

    def test_race_page_without_kit_is_refused_and_nothing_is_pushed(self, tmp_path):
        pages_dir = tmp_path / "output"
        kit_dir = pages_dir / "prep-kit"
        kit_dir.mkdir(parents=True)
        (pages_dir / "unbound-200.html").write_text("<html></html>")  # real profile slug
        proc = self._run(tmp_path, "--sync-pages", "--pages-dir", str(pages_dir),
                         "--prep-kit-dir", str(kit_dir))
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "PREP-KIT GATE: 1 of 1 race pages" in proc.stdout
        assert "unbound-200  → /race/unbound-200/prep-kit/ would 404" in proc.stdout
        assert "Uploading" not in proc.stdout and "DEPLOY FAILED" not in proc.stdout

    def test_race_page_with_kit_pulls_the_kit_sync_into_the_run(self, tmp_path):
        pages_dir = tmp_path / "output"
        kit_dir = pages_dir / "prep-kit"
        kit_dir.mkdir(parents=True)
        (pages_dir / "unbound-200.html").write_text("<html></html>")
        (kit_dir / "unbound-200.html").write_text("<html></html>")
        proc = self._run(tmp_path, "--sync-pages", "--pages-dir", str(pages_dir),
                         "--prep-kit-dir", str(kit_dir))
        # Both steps were attempted (and both stopped at the credential check).
        assert "adding --sync-prep-kits" in proc.stdout
        assert "DEPLOY FAILED — 2 step(s): sync-pages, sync-prep-kits" in proc.stdout
        assert "Uploading" not in proc.stdout
        assert proc.returncode == 1
