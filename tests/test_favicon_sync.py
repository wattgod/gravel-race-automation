"""--sync-favicons wiring: the favicon set + gg-logo.svg had no sync flag at
all before this (like gg-training-form.php once didn't — CLAUDE.md war
story). A flag needs three places wired: the argparse argument, the
has_action tuple (a flag missing there makes the CLI refuse to run even
when it's the only flag passed — the known trap at the top of main()), and
the dispatch block. These tests cover the pure gate/dispatch behavior and
the real CLI end-to-end, with the same no-network guards
test_prep_kit_deploy_gate.py uses.
"""

from __future__ import annotations

import os
import site
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import push_wordpress as pw  # noqa: E402

FAVICON_FILES = [
    "gg-logo.svg", "favicon.ico", "favicon-32.png", "favicon-16.png",
    "apple-touch-icon.png", "icon-192.png", "icon-512.png",
]


class TestSyncFaviconsFunction:
    def test_no_ssh_creds_returns_false_cleanly(self, monkeypatch):
        # Same order as sync_sitemap()/sync_success(): the SSH check comes
        # first, before any local file check, so a creds-less run (e.g. CI)
        # fails fast without ever touching the filesystem.
        monkeypatch.setattr(pw, "get_ssh_credentials", lambda: None)
        assert pw.sync_favicons("/does/not/matter") is False

    def test_missing_files_fail_after_ssh_check_passes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pw, "get_ssh_credentials", lambda: ("host", "user", "18765"))
        assert pw.sync_favicons(str(tmp_path)) is False  # empty dir, nothing uploaded


class TestRepoFaviconFiles:
    """The actual deliverable: web/ must hold every file the shared
    favicon <link> block (brand_tokens.get_favicon_head_snippet) references."""

    def test_web_dir_has_every_favicon_file(self):
        web_dir = PROJECT_ROOT / "web"
        missing = [name for name in FAVICON_FILES if not (web_dir / name).exists()]
        assert not missing, f"Missing from web/: {missing}"

    def test_favicon_ico_has_three_sizes(self):
        from PIL import Image
        with Image.open(PROJECT_ROOT / "web" / "favicon.ico") as im:
            assert im.info.get("sizes") == {(16, 16), (32, 32), (48, 48)}


class TestCliWiring:
    """The three-place trap: argument, has_action tuple, dispatch."""

    def test_flag_declared(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        assert '"--sync-favicons", action="store_true"' in source

    def test_sync_favicons_flag_is_in_has_action_tuple(self):
        """Passing --sync-favicons alone (no other flag) must not trip the
        'Provide a sync flag' refusal — that refusal fires only when a flag
        exists in argparse but was forgotten in the has_action tuple."""
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        has_action_block = source[source.index("has_action = any(["):source.index("if not has_action:")]
        assert "args.sync_favicons" in has_action_block

    def test_sync_favicons_is_dispatched(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        main_block = source[source.index('if __name__ == "__main__":'):]
        assert 'if args.sync_favicons:' in main_block
        assert '_run("sync-favicons", sync_favicons' in main_block

    def test_deploy_all_includes_favicons(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        deploy_all_block = source[source.index("if args.deploy_all:"):source.index("has_action = any([")]
        assert "args.sync_favicons = True" in deploy_all_block


class TestCliEndToEnd:
    """Same no-network guard pattern as TestCliEndToEnd in
    test_prep_kit_deploy_gate.py: empty SSH creds + HOME pointed at tmp so
    SSH_KEY cannot exist, so a real ssh/scp can never fire."""

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

    def test_sync_favicons_alone_is_accepted_and_dispatched(self, tmp_path):
        favicon_dir = tmp_path / "web"
        favicon_dir.mkdir()
        for name in FAVICON_FILES:
            (favicon_dir / name).write_bytes(b"x")
        proc = self._run(tmp_path, "--sync-favicons", "--favicon-dir", str(favicon_dir))
        assert "Provide a sync flag" not in proc.stdout + proc.stderr
        # No SSH creds configured -> get_ssh_credentials() returns None ->
        # sync_favicons() returns False -> the run reports a failed step,
        # not a missing-file or argparse error.
        assert "DEPLOY FAILED" in proc.stdout
        assert "sync-favicons" in proc.stdout

    def test_missing_favicon_files_is_a_clean_failure_not_a_crash(self, tmp_path):
        favicon_dir = tmp_path / "web"
        favicon_dir.mkdir()  # empty
        proc = self._run(tmp_path, "--sync-favicons", "--favicon-dir", str(favicon_dir))
        # No SSH creds in this guarded env, so the SSH check (same order as
        # sync_sitemap()) fails before the missing-file check is reached —
        # still a clean, non-crashing "DEPLOY FAILED", never a traceback.
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "Traceback" not in proc.stderr
        assert "DEPLOY FAILED" in proc.stdout
