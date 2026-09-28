"""Atomic bulk-upload fix (2026-09-25 incident): sync_pages()/sync_prep_kits()/
sync_markdown() used to tar straight into the LIVE /race/ directory over one
ssh pipe with a flat 300s timeout. SiteGround's SSH had a slow patch and a
transfer aborted mid-file, leaving a truncated page
(race/nordic-chase-berlin-copenhagen-gravel/prep-kit/index.html) live in
production.

The fix (_atomic_tar_deploy + helpers, scripts/push_wordpress.py) tars into a
fresh per-run staging directory, verifies every file landed intact there, and
only then moves everything into place with one fast server-side operation.
These tests cover, with subprocess mocked (no network, same pattern as
test_favicon_sync.py / test_prep_kit_deploy_gate.py):

  - the staging path is used, never the live path, for the transfer
  - a verification failure leaves the live directory untouched (the move
    script is never sent)
  - ControlMaster/ControlPath/ControlPersist options are present on every
    ssh/scp call the run makes
  - the retry-with-backoff behavior on a flaky small command
  - the generated shell scripts themselves are correct bash, run for real
    against a throwaway local directory (no network needed for this part)
  - --dry-run touches no subprocess at all
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


# ── Shell-script unit tests (run for real, no network) ──────────────────────

class TestVerifyScript:
    def _run(self, tmp_path, relpaths, check_total_count, contents):
        for rel, content in contents.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        script = pw._build_verify_script(str(tmp_path), relpaths, check_total_count)
        return subprocess.run(["bash", "-c", script], capture_output=True, text=True)

    def test_all_good_passes(self, tmp_path):
        result = self._run(
            tmp_path, ["a/index.html", "b.md"], True,
            {"a/index.html": "<html>ok</html>", "b.md": "# hi"},
        )
        assert result.returncode == 0
        assert "VERIFY_OK" in result.stdout

    def test_truncated_html_fails(self, tmp_path):
        result = self._run(
            tmp_path, ["a/index.html"], True,
            {"a/index.html": "<html><body>cut off mid-fil"},
        )
        assert result.returncode != 0
        assert "TRUNCATED:a/index.html" in result.stdout

    def test_empty_file_fails(self, tmp_path):
        result = self._run(tmp_path, ["b.md"], True, {"b.md": ""})
        assert result.returncode != 0
        assert "EMPTY:b.md" in result.stdout

    def test_missing_file_fails(self, tmp_path):
        script = pw._build_verify_script(str(tmp_path), ["nope.html"], True)
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
        assert result.returncode != 0
        assert "MISSING:nope.html" in result.stdout

    def test_extra_file_trips_count_mismatch(self, tmp_path):
        result = self._run(
            tmp_path, ["a.md"], True,
            {"a.md": "content", "extra.md": "surprise"},
        )
        assert result.returncode != 0
        assert "COUNT_MISMATCH" in result.stdout

    def test_check_total_count_false_ignores_unrelated_files(self, tmp_path):
        """Post-move verification runs against remote_base, which holds every
        other race's files too — it must not flag those as a mismatch."""
        result = self._run(
            tmp_path, ["a.md"], False,
            {"a.md": "content", "unrelated-other-race.md": "not part of this run"},
        )
        assert result.returncode == 0
        assert "COUNT_MISMATCH" not in result.stdout


class TestMoveScript:
    def test_moves_files_and_cleans_up_staging(self, tmp_path):
        staging = tmp_path / "staging"
        remote = tmp_path / "remote"
        (staging / "a").mkdir(parents=True)
        (staging / "a" / "index.html").write_text("<html>new</html>")
        (staging / "b.md").write_text("md content")
        remote.mkdir()

        script = pw._build_move_script(str(staging), str(remote))
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        assert (remote / "a" / "index.html").read_text() == "<html>new</html>"
        assert (remote / "b.md").read_text() == "md content"
        assert not staging.exists()

    def test_never_deletes_sibling_live_content(self, tmp_path):
        """The core safety property: a race dir holds both index.html and
        prep-kit/, uploaded by separate runs. Moving in a new index.html must
        never delete an existing prep-kit/ (or vice versa)."""
        staging = tmp_path / "staging"
        remote = tmp_path / "remote"
        (staging / "some-race").mkdir(parents=True)
        (staging / "some-race" / "index.html").write_text("<html>new page</html>")
        (remote / "some-race" / "prep-kit").mkdir(parents=True)
        (remote / "some-race" / "prep-kit" / "index.html").write_text("<html>existing kit</html>")

        script = pw._build_move_script(str(staging), str(remote))
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        assert (remote / "some-race" / "index.html").read_text() == "<html>new page</html>"
        assert (remote / "some-race" / "prep-kit" / "index.html").read_text() == "<html>existing kit</html>"

    def test_failed_mv_leaves_staging_intact(self, tmp_path):
        """set -e: if a move fails partway, the script stops immediately —
        whatever hasn't moved stays in staging instead of being lost."""
        staging = tmp_path / "staging"
        remote = tmp_path / "remote"
        (staging / "a").mkdir(parents=True)
        (staging / "a" / "index.html").write_text("<html>ok</html>")
        # Make remote's target path a file where the move script expects
        # a directory it can mkdir -p into, forcing the move to fail.
        remote.mkdir()
        (remote / "a").write_text("blocking file, not a directory")

        script = pw._build_move_script(str(staging), str(remote))
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)

        assert result.returncode != 0
        # Staging must still exist with its file intact — nothing was lost.
        assert (staging / "a" / "index.html").read_text() == "<html>ok</html>"

    def test_tilde_paths_actually_expand(self, tmp_path):
        """Regression: real remote_base/staging paths are `~/...` (relative
        to the server's home directory), not absolute paths. Embedding them
        inside a double-quoted shell string (e.g. `x="{remote_base}/$sub"`)
        would NOT expand a leading `~` — bash only tilde-expands an unquoted
        `~` — so files would silently land under a literal "~" subdirectory
        created inside staging instead of remote_base, while remote_base
        itself stayed empty. Exercise the actual `~` character here (fake
        HOME via env) instead of the absolute tmp_path paths the other tests
        above use, which can't catch this."""
        (tmp_path / "staging").mkdir()
        (tmp_path / "staging" / "a").mkdir()
        (tmp_path / "staging" / "a" / "index.html").write_text("<html>new</html>")
        (tmp_path / "remote").mkdir()

        script = pw._build_move_script("~/staging", "~/remote")
        env = dict(os.environ, HOME=str(tmp_path))
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)

        assert result.returncode == 0, result.stderr
        assert (tmp_path / "remote" / "a" / "index.html").read_text() == "<html>new</html>"
        assert not (tmp_path / "staging").exists()
        # No literal "~" directory should ever appear anywhere.
        assert not (tmp_path / "~").exists()
        assert not (tmp_path / "remote" / "~").exists()


# ── ControlMaster options ────────────────────────────────────────────────────

class TestConnectionReuse:
    def test_multiplex_opts_present(self):
        opts = pw._ssh_multiplex_opts("host.example.com", "user1", "18765")
        assert "ControlMaster=auto" in opts
        assert any(o.startswith("ControlPath=") for o in opts)
        assert "ControlPersist=120s" in opts

    def test_control_path_is_pid_scoped(self):
        path_a = pw._ssh_control_path("host.example.com", "user1", "18765")
        assert str(os.getpid()) in path_a

    def test_ssh_argv_includes_multiplex_opts(self):
        argv = pw._ssh_argv("host.example.com", "user1", "18765", "mkdir -p ~/x")
        assert "ControlMaster=auto" in argv
        assert argv[-1] == "mkdir -p ~/x"
        assert argv[-2] == "user1@host.example.com"


# ── _run_with_retry ───────────────────────────────────────────────────────────

class TestRunWithRetry:
    def test_succeeds_first_try_no_sleep(self, monkeypatch):
        calls = []
        monkeypatch.setattr(pw.time, "sleep", lambda s: calls.append(("sleep", s)))

        def fake_run(cmd, **kwargs):
            calls.append(("run", cmd))
            return subprocess.CompletedProcess(cmd, 0, "ok", "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        result = pw._run_with_retry(["echo", "hi"], timeout=5)
        assert result.returncode == 0
        assert [c for c in calls if c[0] == "run"] == [("run", ["echo", "hi"])]
        assert not any(c[0] == "sleep" for c in calls)

    def test_retries_transient_failure_then_succeeds(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr(pw.time, "sleep", lambda s: sleeps.append(s))
        attempts = {"n": 0}

        def fake_run(cmd, **kwargs):
            attempts["n"] += 1
            if attempts["n"] < 3:
                return subprocess.CompletedProcess(cmd, 255, "", "connection reset")
            return subprocess.CompletedProcess(cmd, 0, "ok", "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        result = pw._run_with_retry(["ssh", "flaky"], timeout=5, retries=2, backoff=2)
        assert result.returncode == 0
        assert attempts["n"] == 3
        assert sleeps == [2, 4]  # linear backoff: backoff * (attempt+1)

    def test_exhausts_retries_and_returns_last_failure(self, monkeypatch):
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        calls = {"n": 0}

        def fake_run(cmd, **kwargs):
            calls["n"] += 1
            return subprocess.CompletedProcess(cmd, 1, "", "still broken")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        result = pw._run_with_retry(["ssh", "broken"], timeout=5, retries=2)
        assert result.returncode == 1
        assert calls["n"] == 3  # initial attempt + 2 retries

    def test_all_timeouts_raises(self, monkeypatch):
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)

        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        with pytest.raises(subprocess.TimeoutExpired):
            pw._run_with_retry(["ssh", "slow"], timeout=5, retries=1)


# ── _atomic_tar_deploy end-to-end (mocked subprocess) ────────────────────────

class _FakeTarPopen:
    """Stands in for the local `tar` process — its .stdout feeds the ssh
    Popen's stdin in the real code; nothing reads it in these tests."""

    def __init__(self, *a, **k):
        self.stdout = _NullStdout()


class _NullStdout:
    def close(self):
        pass


class _FakeSshPopen:
    def __init__(self, returncode, stderr=b""):
        self._returncode = returncode
        self._stderr = stderr
        self.returncode = None

    def communicate(self, timeout=None):
        self.returncode = self._returncode
        return (b"", self._stderr)

    def kill(self):
        pass


@pytest.fixture
def deploy_harness(monkeypatch, tmp_path):
    """Mocks subprocess.Popen (the tar+ssh transfer) and subprocess.run (every
    other ssh call this module makes: mkdir, bash -s verify/move scripts,
    chmod, and the control-master close) and records every call so tests can
    assert on staging-vs-live paths and ControlMaster options."""
    monkeypatch.setattr(pw.time, "sleep", lambda s: None)

    state = {
        "popen_calls": [],
        "run_calls": [],
        "tar_returncode": 0,
        "tar_stderr": b"",
        "verify_staging_rc": 0,
        "verify_staging_out": "VERIFY_OK\n",
        "verify_postmove_rc": 0,
        "verify_postmove_out": "VERIFY_OK\n",
        "move_rc": 0,
        "mkdir_staging_rc": 0,
        "mkdir_staging_stderr": "",
    }

    def fake_popen(cmd, stdin=None, stdout=None, stderr=None):
        state["popen_calls"].append(cmd)
        if cmd and cmd[0] == "tar":
            return _FakeTarPopen()
        return _FakeSshPopen(state["tar_returncode"], state["tar_stderr"])

    def fake_run(cmd, input=None, capture_output=True, text=True, timeout=None):
        state["run_calls"].append({"cmd": list(cmd), "input": input, "timeout": timeout})
        if "-O" in cmd and "exit" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        remote_cmd = cmd[-1]
        if remote_cmd.startswith("mkdir -p") and "deploy-staging" in remote_cmd:
            return subprocess.CompletedProcess(
                cmd, state["mkdir_staging_rc"], "", state["mkdir_staging_stderr"])
        if remote_cmd.startswith("chmod 755"):
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if remote_cmd == "bash -s" and input and "find . -type f -print0" in input:
            return subprocess.CompletedProcess(cmd, state["move_rc"], "", "")
        if remote_cmd == "bash -s" and input and "VERIFY_OK" in input:
            if "actual_count=$(find . -type f" in input:
                return subprocess.CompletedProcess(
                    cmd, state["verify_staging_rc"], state["verify_staging_out"], "")
            return subprocess.CompletedProcess(
                cmd, state["verify_postmove_rc"], state["verify_postmove_out"], "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(pw.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(pw.subprocess, "run", fake_run)

    local_root = tmp_path / "local_root"
    (local_root / "some-race").mkdir(parents=True)
    (local_root / "some-race" / "index.html").write_text("<html>page</html>")
    state["local_root"] = local_root
    state["remote_base"] = "~/www/gravelgodcycling.com/public_html/race"
    return state


class TestAtomicTarDeploy:
    def test_happy_path_stages_then_verifies_then_moves(self, deploy_harness):
        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        assert ok is True

        # Staging path used for the transfer, never the live path.
        ssh_popen = deploy_harness["popen_calls"][1]  # [tar_cmd, ssh_cmd]
        remote_tar_cmd = ssh_popen[-1]
        assert "deploy-staging" in remote_tar_cmd
        assert deploy_harness["remote_base"] not in remote_tar_cmd

        # The move script (only place remote_base is written to) ran.
        move_calls = [c for c in deploy_harness["run_calls"]
                      if c["input"] and "find . -type f -print0" in c["input"]]
        assert len(move_calls) == 1
        assert deploy_harness["remote_base"] in move_calls[0]["input"]

    def test_staging_mkdir_failure_aborts_before_transfer(self, deploy_harness):
        """A non-timeout failure creating the staging directory (e.g.
        permission denied, disk full) must abort immediately, not fall
        through and attempt the tar transfer into a directory that was
        never created."""
        deploy_harness["mkdir_staging_rc"] = 1
        deploy_harness["mkdir_staging_stderr"] = "mkdir: permission denied"

        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        assert ok is False
        assert deploy_harness["popen_calls"] == []

    def test_staging_verification_failure_never_touches_live(self, deploy_harness):
        deploy_harness["verify_staging_rc"] = 1
        deploy_harness["verify_staging_out"] = "TRUNCATED:some-race/index.html\n"

        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        assert ok is False

        # The move script must never have been sent.
        move_calls = [c for c in deploy_harness["run_calls"]
                      if c["input"] and "find . -type f -print0" in c["input"]]
        assert move_calls == []
        # Nor chmod on the live directory.
        chmod_calls = [c for c in deploy_harness["run_calls"]
                       if c["cmd"][-1].startswith("chmod 755")]
        assert chmod_calls == []

    def test_move_failure_does_not_run_postmove_verify_as_success(self, deploy_harness):
        deploy_harness["move_rc"] = 1
        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        assert ok is False

    def test_tar_transfer_failure_never_reaches_verify_or_move(self, deploy_harness):
        deploy_harness["tar_returncode"] = 1
        deploy_harness["tar_stderr"] = b"ssh: connection reset"
        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        assert ok is False
        verify_calls = [c for c in deploy_harness["run_calls"]
                        if c["input"] and "VERIFY_OK" in c["input"]]
        assert verify_calls == []

    def test_every_ssh_call_carries_controlmaster_opts(self, deploy_harness):
        pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages", chmod_remote_base=True,
        )
        for cmd in deploy_harness["popen_calls"]:
            if cmd and cmd[0] == "ssh":
                assert "ControlMaster=auto" in cmd, cmd
        for call in deploy_harness["run_calls"]:
            assert "ControlMaster=auto" in call["cmd"], call["cmd"]

    def test_dry_run_makes_no_subprocess_calls(self, deploy_harness):
        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages", dry_run=True,
        )
        assert ok is True
        assert deploy_harness["popen_calls"] == []
        assert deploy_harness["run_calls"] == []

    def test_chmod_only_when_requested(self, deploy_harness):
        pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="prep-kits", chmod_remote_base=False,
        )
        chmod_calls = [c for c in deploy_harness["run_calls"]
                       if c["cmd"][-1].startswith("chmod 755")]
        assert chmod_calls == []


# ── sync_pages/sync_prep_kits/sync_markdown wiring ───────────────────────────

class TestSyncFunctionsDryRun:
    """No SSH creds needed to prove --dry-run never opens a connection: the
    functions must reach _atomic_tar_deploy's dry-run branch with zero
    subprocess calls, same no-network guarantee as the CLI e2e tests below."""

    def test_sync_pages_dry_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pw, "get_ssh_credentials", lambda: ("h", "u", "18765"))

        def boom(*a, **k):
            raise AssertionError("dry-run must not call subprocess")

        monkeypatch.setattr(pw.subprocess, "Popen", boom)
        monkeypatch.setattr(pw.subprocess, "run", boom)

        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        (pages_dir / "some-race.html").write_text("<html>page</html>")
        assert pw.sync_pages(str(pages_dir), dry_run=True) is True

    def test_sync_prep_kits_dry_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pw, "get_ssh_credentials", lambda: ("h", "u", "18765"))
        monkeypatch.setattr(pw.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
        monkeypatch.setattr(pw.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))

        pk_dir = tmp_path / "prep-kit"
        pk_dir.mkdir()
        (pk_dir / "some-race.html").write_text("<html>kit</html>")
        assert pw.sync_prep_kits(str(pk_dir), dry_run=True) is True

    def test_sync_markdown_dry_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(pw, "get_ssh_credentials", lambda: ("h", "u", "18765"))
        monkeypatch.setattr(pw.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
        monkeypatch.setattr(pw.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))

        md_dir = tmp_path / "markdown"
        md_dir.mkdir()
        (md_dir / "some-race.md").write_text("# hi")
        assert pw.sync_markdown(str(md_dir), dry_run=True) is True


class TestCliDryRunFlag:
    def test_flag_declared(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        assert '"--dry-run", action="store_true"' in source

    def test_sync_pages_dispatch_passes_dry_run(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        main_block = source[source.index('if __name__ == "__main__":'):]
        assert '_run("sync-pages", sync_pages, args.pages_dir, args.dry_run)' in main_block

    def test_sync_prep_kits_dispatch_passes_dry_run(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        main_block = source[source.index('if __name__ == "__main__":'):]
        assert '_run("sync-prep-kits", sync_prep_kits, args.prep_kit_dir, args.dry_run)' in main_block

    def test_sync_markdown_dispatch_passes_dry_run(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        main_block = source[source.index('if __name__ == "__main__":'):]
        assert 'sync_markdown(args.markdown_dir, args.dry_run)' in main_block


class TestCliEndToEnd:
    """Same no-network guard pattern as test_favicon_sync.py /
    test_prep_kit_deploy_gate.py: empty SSH creds so get_ssh_credentials()
    returns None and a real ssh/scp can never fire."""

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

    def test_sync_pages_dry_run_without_ssh_creds_still_fails_cleanly(self, tmp_path):
        # No SSH creds -> get_ssh_credentials() short-circuits before
        # dry-run even matters. Proves --dry-run doesn't bypass that gate.
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        (pages_dir / "some-race.html").write_text("<html>page</html>")
        proc = self._run(
            tmp_path, "--sync-pages", "--pages-dir", str(pages_dir),
            "--dry-run", "--no-prep-kit-gate", "--no-markdown-gate",
        )
        assert "DEPLOY FAILED" in proc.stdout
        assert "sync-pages" in proc.stdout

    def _run_with_fake_ssh_creds(self, tmp_path, *argv):
        """Same no-network guarantee, but with SSH creds present (fake host/
        key) so get_ssh_credentials() succeeds and --dry-run's own no-op
        branch inside _atomic_tar_deploy is what's actually being tested —
        if --dry-run ever regressed into making a real connection, this
        would hang or fail against the fake unreachable host instead of
        printing the dry-run summary and exiting cleanly."""
        env = dict(os.environ)
        home = tmp_path / "home"
        (home / ".ssh").mkdir(parents=True, exist_ok=True)
        (home / ".ssh" / "siteground_key").write_text("fake key, never used")
        env.update({
            "SSH_HOST": "unreachable.invalid", "SSH_USER": "testuser", "SSH_PORT": "18765",
            "WP_URL": "", "WP_USER": "", "WP_APP_PASSWORD": "",
        })
        env["HOME"] = str(home)
        env["PYTHONPATH"] = os.pathsep.join(
            p for p in [site.getusersitepackages(), env.get("PYTHONPATH", "")] if p)
        return subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "push_wordpress.py"), *argv],
            capture_output=True, text=True, env=env, cwd=PROJECT_ROOT, timeout=60)

    def test_sync_pages_dry_run_with_creds_never_connects(self, tmp_path):
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        (pages_dir / "some-race.html").write_text("<html>page</html>")
        proc = self._run_with_fake_ssh_creds(
            tmp_path, "--sync-pages", "--pages-dir", str(pages_dir),
            "--dry-run", "--no-prep-kit-gate", "--no-markdown-gate",
        )
        assert "DEPLOY FAILED" not in proc.stdout, proc.stdout + proc.stderr
        assert "[dry-run]" in proc.stdout
        assert "deploy-staging" in proc.stdout
        assert proc.returncode == 0
