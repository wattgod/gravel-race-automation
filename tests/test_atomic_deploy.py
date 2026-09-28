"""Atomic bulk-upload fix (2026-09-25 incident): sync_pages()/sync_prep_kits()/
sync_markdown() used to tar straight into the LIVE /race/ directory over one
ssh pipe with a flat 300s timeout. SiteGround's SSH had a slow patch and a
transfer aborted mid-file, leaving a truncated page
(race/nordic-chase-berlin-copenhagen-gravel/prep-kit/index.html) live in
production.

The fix (_atomic_tar_deploy + helpers, scripts/push_wordpress.py) tars into a
fresh per-run staging directory, verifies every file landed intact there
(existence, non-empty, exact byte size vs. the local original, and an intact
`</html>` ending), then launches the move into place DETACHED on the server
(so it survives this connection dropping) and polls for its completion,
before re-verifying the live result. A second round of review (sol) on the
first version of this fix found four more real defects, all covered here:

  - the ssh ControlPath (a local Unix socket path) could exceed the ~104-byte
    platform limit, silently failing every single ssh call in a run
  - the move ran synchronously over one ssh call — a dropped connection
    mid-move left an unclear, unrecoverable state
  - nothing stopped two bulk syncs (same run or two concurrent invocations)
    from racing each other's writes under the same staging root
  - --dry-run only understood itself locally; a combined invocation like
    `--deploy-content --dry-run` would still run every OTHER flag for real

These tests cover, with subprocess mocked (no network, same pattern as
test_favicon_sync.py / test_prep_kit_deploy_gate.py) or run for real against
a throwaway local directory where no network is involved:

  - the ControlPath is short (<100 chars) even with long credentials, and a
    stale leftover socket file is removed before first use but never touched
    again mid-run
  - the staging path is used, never the live path, for the transfer
  - a verification failure leaves the live directory untouched
  - the promote step is launched detached and polled for completion,
    tolerating any single poll attempt (or the launch itself) failing
  - the remote deploy lock refuses a concurrent run, recognizes a stale
    lock, and --force-unlock only ever clears a genuinely stale one
  - --dry-run disables every other remote-touching flag in the same
    invocation instead of only understanding itself
  - the generated shell scripts themselves are correct bash (including size
    verification and real `~` expansion)
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


@pytest.fixture(autouse=True)
def _reset_ssh_module_state(monkeypatch):
    """_control_sockets_checked / _ssh_connection_used are process-lifetime
    module state by design (see their docstrings) — reset them before every
    test so one test's ssh-helper calls can't change another's behavior."""
    monkeypatch.setattr(pw, "_control_sockets_checked", set())
    monkeypatch.setattr(pw, "_ssh_connection_used", False)


# ── Shell-script unit tests (run for real, no network) ──────────────────────

class TestVerifyScript:
    def _run(self, tmp_path, relpaths, check_total_count, contents, sizes=None):
        for rel, content in contents.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        script = pw._build_verify_script(str(tmp_path), relpaths, check_total_count, sizes=sizes)
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

    def test_size_mismatch_detected(self, tmp_path):
        """Catches a subtler failure than truncation-at-the-end: an
        interleaved/partial transfer landing a file that's non-empty and
        even ends correctly, but is still the wrong size."""
        result = self._run(
            tmp_path, ["a.md"], True,
            {"a.md": "this content is much longer than the expected size"},
            sizes={"a.md": 5},
        )
        assert result.returncode != 0
        assert "SIZE_MISMATCH:a.md" in result.stdout
        assert "expected=5" in result.stdout

    def test_size_match_passes(self, tmp_path):
        content = "exact content"
        result = self._run(
            tmp_path, ["a.md"], True, {"a.md": content}, sizes={"a.md": len(content)},
        )
        assert result.returncode == 0
        assert "VERIFY_OK" in result.stdout

    def test_no_sizes_given_skips_size_check(self, tmp_path):
        # Backward compatible: the 3-positional-arg call pattern (no sizes)
        # must still work and must not spuriously flag anything.
        result = self._run(tmp_path, ["a.md"], True, {"a.md": "anything at all"})
        assert result.returncode == 0
        assert "VERIFY_OK" in result.stdout


class TestPromoteScript:
    def test_moves_files_and_cleans_up_staging(self, tmp_path):
        staging = tmp_path / "staging"
        remote = tmp_path / "remote"
        (staging / "a").mkdir(parents=True)
        (staging / "a" / "index.html").write_text("<html>new</html>")
        (staging / "b.md").write_text("md content")
        remote.mkdir()
        log_path = tmp_path / "promote.log"
        exit_path = tmp_path / "promote.exit"

        script = pw._build_promote_script(str(staging), str(remote), str(log_path), str(exit_path))
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        assert (remote / "a" / "index.html").read_text() == "<html>new</html>"
        assert (remote / "b.md").read_text() == "md content"
        assert not staging.exists()
        assert exit_path.read_text().strip() == "0"

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
        log_path = tmp_path / "promote.log"
        exit_path = tmp_path / "promote.exit"

        script = pw._build_promote_script(str(staging), str(remote), str(log_path), str(exit_path))
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        assert (remote / "some-race" / "index.html").read_text() == "<html>new page</html>"
        assert (remote / "some-race" / "prep-kit" / "index.html").read_text() == "<html>existing kit</html>"
        assert exit_path.read_text().strip() == "0"

    def test_failed_mv_leaves_staging_intact_and_reports_nonzero_exit(self, tmp_path):
        """set -e inside the subshell: if a move fails partway, the subshell
        aborts immediately — whatever hasn't moved stays in staging instead
        of being lost — and the real result (nonzero) still reaches
        exit_path even though the wrapper script's OWN process always exits
        0 (it only ever records the result; see _poll_for_promotion, which
        reads exit_path's content, not this process's exit code)."""
        staging = tmp_path / "staging"
        remote = tmp_path / "remote"
        (staging / "a").mkdir(parents=True)
        (staging / "a" / "index.html").write_text("<html>ok</html>")
        # Make remote's target path a file where the move script expects
        # a directory it can mkdir -p into, forcing the move to fail.
        remote.mkdir()
        (remote / "a").write_text("blocking file, not a directory")
        log_path = tmp_path / "promote.log"
        exit_path = tmp_path / "promote.exit"

        script = pw._build_promote_script(str(staging), str(remote), str(log_path), str(exit_path))
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        # Staging must still exist with its file intact — nothing was lost.
        assert (staging / "a" / "index.html").read_text() == "<html>ok</html>"
        recorded_exit = exit_path.read_text().strip()
        assert recorded_exit not in ("", "0")

    def test_self_cleans_up_script_and_lock_dir_on_success(self, tmp_path):
        """Regression (sol round 2): .promote.sh is a plain FILE sitting
        directly inside `staging` (uploaded by _upload_and_launch_promotion
        before this script ever runs). The move loop's `find . -type f`
        runs from inside `staging` too, so if the script deleted its own
        on-disk copy AFTER that loop instead of before, `find` would sweep
        up .promote.sh as one of "this run's files" and mv it into
        remote_base — a stray script file left live on every single
        successful deploy, undetected by post-move verification (which
        only checks the specific relpaths this run was supposed to
        upload, not for unexpected extras). It must never appear in
        remote_base, and its launch-lock dir must not block the final
        rmdir of staging either."""
        staging = tmp_path / "staging"
        remote = tmp_path / "remote"
        staging.mkdir()
        (staging / "a.md").write_text("content")
        (staging / ".promote.sh").write_text("placeholder for the real uploaded copy")
        (staging / ".promote-lock").mkdir()
        remote.mkdir()
        log_path = tmp_path / "promote.log"
        exit_path = tmp_path / "promote.exit"

        script = pw._build_promote_script(str(staging), str(remote), str(log_path), str(exit_path))
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)

        assert result.returncode == 0, result.stderr
        assert exit_path.read_text().strip() == "0"
        assert not staging.exists()
        assert (remote / "a.md").read_text() == "content"
        assert sorted(p.name for p in remote.rglob("*")) == ["a.md"]
        assert not (remote / ".promote.sh").exists()
        assert not (remote / ".promote-lock").exists()

    def test_tilde_paths_actually_expand(self, tmp_path):
        """Regression: real staging/remote_base/log_path/exit_path are all
        `~/...` (relative to the server's home directory), not absolute
        paths. Embedding one directly inside a double-quoted shell string
        (e.g. `x="{remote_base}/$sub"`) would NOT expand a leading `~` —
        bash only tilde-expands an unquoted `~` — so files would silently
        land under a literal "~" subdirectory created inside staging
        instead of remote_base, while remote_base itself stayed empty.
        Exercise the actual `~` character here (fake HOME via env) instead
        of the absolute tmp_path paths the other tests above use, which
        can't catch this."""
        (tmp_path / "staging").mkdir()
        (tmp_path / "staging" / "a").mkdir()
        (tmp_path / "staging" / "a" / "index.html").write_text("<html>new</html>")
        (tmp_path / "remote").mkdir()

        script = pw._build_promote_script(
            "~/staging", "~/remote", "~/promote.log", "~/promote.exit",
        )
        env = dict(os.environ, HOME=str(tmp_path))
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)

        assert result.returncode == 0, result.stderr
        assert (tmp_path / "remote" / "a" / "index.html").read_text() == "<html>new</html>"
        assert not (tmp_path / "staging").exists()
        assert (tmp_path / "promote.exit").read_text().strip() == "0"
        # No literal "~" path component should ever appear anywhere.
        assert not any(p.name == "~" for p in tmp_path.rglob("*"))


# ── ControlMaster options / stale sockets ────────────────────────────────────

class TestConnectionReuse:
    def test_multiplex_opts_present(self):
        opts = pw._ssh_multiplex_opts("host.example.com", "user1", "18765")
        assert "ControlMaster=auto" in opts
        assert any(o.startswith("ControlPath=") for o in opts)
        assert "ControlPersist=120s" in opts

    def test_control_path_is_pid_scoped(self, monkeypatch):
        monkeypatch.setattr(pw.os, "getpid", lambda: 11111)
        path_a = pw._ssh_control_path("host.example.com", "user1", "18765")
        monkeypatch.setattr(pw, "_control_sockets_checked", set())
        monkeypatch.setattr(pw.os, "getpid", lambda: 22222)
        path_b = pw._ssh_control_path("host.example.com", "user1", "18765")
        assert path_a != path_b

    def test_control_path_is_short(self):
        path = pw._ssh_control_path("gravelgodcycling.com", "u12345", "18765")
        assert len(path) < 100, path
        assert path.startswith("/tmp/")

    def test_control_path_short_even_with_long_credentials(self):
        # The sol-confirmed bug: tempfile.gettempdir() on macOS (a long
        # per-process sandbox path) plus the raw user/host/port baked
        # literally into the filename could exceed ~104 bytes, the AF_UNIX
        # socket path limit on macOS — every single ssh call in the run
        # then silently fails.
        long_user = "a" * 60
        long_host = "b" * 80 + ".example.com"
        path = pw._ssh_control_path(long_host, long_user, "18765")
        assert len(path) < 100, path

    def test_ssh_argv_includes_multiplex_opts(self):
        argv = pw._ssh_argv("host.example.com", "user1", "18765", "mkdir -p ~/x")
        assert "ControlMaster=auto" in argv
        assert argv[-1] == "mkdir -p ~/x"
        assert argv[-2] == "user1@host.example.com"

    def test_stale_socket_removed_before_first_use(self, tmp_path):
        fake_path = str(tmp_path / "gg-ssh-fake.sock")
        Path(fake_path).write_text("stale leftover socket")
        pw._ensure_no_stale_socket("h", "u", "18765", fake_path)
        assert not Path(fake_path).exists()

    def test_stale_socket_check_only_removes_once_per_run(self, tmp_path):
        """A live master's own socket file must not be deleted out from
        under it mid-run — only the FIRST check (before we've ever opened
        our own master at this path) may clean up a leftover."""
        fake_path = str(tmp_path / "gg-ssh-fake.sock")
        Path(fake_path).write_text("stale leftover socket")
        pw._ensure_no_stale_socket("h", "u", "18765", fake_path)
        assert not Path(fake_path).exists()
        # Recreate it (simulating our OWN live master now using this path)
        # and check again with the SAME (host, user, port) — must be left
        # alone this time.
        Path(fake_path).write_text("our live master's socket")
        pw._ensure_no_stale_socket("h", "u", "18765", fake_path)
        assert Path(fake_path).exists()


class TestSharedConnectionLifecycle:
    """pages/prep-kits/markdown share one multiplexed connection across the
    whole run instead of each closing it — see _close_shared_ssh_connection_if_used."""

    def test_atomic_tar_deploy_does_not_close_control_master_itself(self, deploy_harness):
        pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        close_calls = [c for c in deploy_harness["run_calls"]
                       if "-O" in c["cmd"] and "exit" in c["cmd"]]
        assert close_calls == []

    def test_close_shared_connection_if_used_closes_once(self, monkeypatch):
        monkeypatch.setattr(pw, "_ssh_connection_used", True)
        monkeypatch.setattr(pw, "get_ssh_credentials", lambda: ("h", "u", "18765"))
        calls = []
        monkeypatch.setattr(pw, "_close_control_master",
                             lambda host, user, port: calls.append((host, user, port)))
        pw._close_shared_ssh_connection_if_used()
        assert calls == [("h", "u", "18765")]

    def test_close_shared_connection_is_noop_if_never_used(self, monkeypatch):
        monkeypatch.setattr(pw, "_ssh_connection_used", False)
        called = {"v": False}

        def boom():
            called["v"] = True

        monkeypatch.setattr(pw, "get_ssh_credentials", boom)
        pw._close_shared_ssh_connection_if_used()
        assert called["v"] is False  # get_ssh_credentials never even called


# ── _run_with_retry / _run_ssh_level_retry ──────────────────────────────────

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


class TestRunSshLevelRetry:
    """Used only for the deploy lock's `mkdir` — genuinely NOT idempotent,
    so it must retry ssh-level connectivity failures (exit 255) but never a
    real remote non-zero exit (which could be our own just-succeeded lock,
    misread as held by someone else if we blindly retried)."""

    def test_retries_only_on_255(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr(pw.time, "sleep", lambda s: sleeps.append(s))
        attempts = {"n": 0}

        def fake_run(cmd, **kwargs):
            attempts["n"] += 1
            if attempts["n"] < 3:
                return subprocess.CompletedProcess(cmd, 255, "", "ssh: connect failed")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        result = pw._run_ssh_level_retry(["ssh", "x"], timeout=5)
        assert result.returncode == 0
        assert attempts["n"] == 3
        assert sleeps  # it did back off between the 255s

    def test_does_not_retry_a_non_255_failure(self, monkeypatch):
        attempts = {"n": 0}

        def must_not_sleep(s):
            raise AssertionError("must not retry/sleep on a non-255 failure")

        monkeypatch.setattr(pw.time, "sleep", must_not_sleep)

        def fake_run(cmd, **kwargs):
            attempts["n"] += 1
            return subprocess.CompletedProcess(cmd, 1, "", "mkdir: File exists")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        result = pw._run_ssh_level_retry(["ssh", "x"], timeout=5)
        assert result.returncode == 1
        assert attempts["n"] == 1


# ── Remote deploy lock ───────────────────────────────────────────────────────

class TestDeployLock:
    def test_acquire_succeeds_when_free(self, monkeypatch):
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        calls = []

        def fake_run(cmd, **k):
            calls.append(cmd[-1])
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        ok, msg = pw._acquire_deploy_lock("h", "u", "18765")
        assert ok is True
        assert msg == ""
        # mkdir + writing the owner marker are one combined command (not
        # two round trips), to minimize the window where the lock dir
        # exists without its owner file.
        assert any("mkdir" in c and pw.DEPLOY_LOCK_PATH in c and "owner" in c for c in calls)

    def test_acquire_refused_when_held_and_fresh(self, monkeypatch):
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)

        def fake_run(cmd, **k):
            rc = cmd[-1]
            if rc.startswith("mkdir"):
                return subprocess.CompletedProcess(cmd, 1, "", "File exists")
            if rc.startswith("cat"):
                return subprocess.CompletedProcess(cmd, 0, f"pid=999 started={int(pw.time.time())}", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        ok, msg = pw._acquire_deploy_lock("h", "u", "18765")
        assert ok is False
        assert "already running" in msg
        assert "pid=999" in msg

    def test_acquire_refused_when_stale_without_force(self, monkeypatch):
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        old_ts = int(pw.time.time()) - (31 * 60)

        def fake_run(cmd, **k):
            rc = cmd[-1]
            if rc.startswith("mkdir"):
                return subprocess.CompletedProcess(cmd, 1, "", "File exists")
            if rc.startswith("cat"):
                return subprocess.CompletedProcess(cmd, 0, f"pid=999 started={old_ts}", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        ok, msg = pw._acquire_deploy_lock("h", "u", "18765")
        assert ok is False
        assert "--force-unlock" in msg
        assert "stale" in msg

    def test_force_unlock_clears_stale_lock_and_acquires(self, monkeypatch):
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        old_ts = int(pw.time.time()) - (31 * 60)
        state = {"removed": False}

        def fake_run(cmd, **k):
            rc = cmd[-1]
            if rc.startswith("mkdir"):
                return subprocess.CompletedProcess(cmd, 0 if state["removed"] else 1, "", "")
            if rc.startswith("cat") and pw.DEPLOY_LOCK_PATH in rc:
                return subprocess.CompletedProcess(cmd, 0, f"pid=999 started={old_ts}", "")
            if rc.startswith("rm -rf"):
                state["removed"] = True
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        ok, msg = pw._acquire_deploy_lock("h", "u", "18765", force=True)
        assert ok is True
        assert state["removed"] is True

    def test_force_unlock_does_not_touch_a_fresh_lock(self, monkeypatch):
        """--force-unlock only clears a lock older than the stale threshold
        — it must never override a genuinely active concurrent deploy."""
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        removed = {"v": False}

        def fake_run(cmd, **k):
            rc = cmd[-1]
            if rc.startswith("mkdir"):
                return subprocess.CompletedProcess(cmd, 1, "", "File exists")
            if rc.startswith("cat"):
                return subprocess.CompletedProcess(cmd, 0, f"pid=999 started={int(pw.time.time())}", "")
            if rc.startswith("rm -rf"):
                removed["v"] = True
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        ok, msg = pw._acquire_deploy_lock("h", "u", "18765", force=True)
        assert ok is False
        assert removed["v"] is False

    def test_release_never_raises(self, monkeypatch):
        def boom(*a, **k):
            raise OSError("network gone")

        monkeypatch.setattr(pw.subprocess, "run", boom)
        pw._release_deploy_lock("h", "u", "18765")  # must not raise

    def test_unknown_owner_is_treated_as_stale_and_forceable(self, monkeypatch):
        """Regression (sol round 2): mkdir+owner-write are one combined
        remote command specifically so a lock dir essentially never exists
        without its owner file — but if it somehow does (e.g. our own
        earlier attempt's confirmation got lost), treating "no owner
        marker" as NOT stale would deadlock forever: it has no `started=`
        timestamp to ever age past DEPLOY_LOCK_STALE_SECONDS, so
        --force-unlock could never apply and the lock could never be
        cleared without a human manually SSHing in."""
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        state = {"removed": False}

        def fake_run(cmd, **k):
            rc = cmd[-1]
            if rc.startswith("mkdir"):
                return subprocess.CompletedProcess(cmd, 0 if state["removed"] else 1, "", "")
            if rc.startswith("cat"):
                return subprocess.CompletedProcess(cmd, 0, "", "")  # no owner file
            if rc.startswith("rm -rf"):
                state["removed"] = True
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        ok, msg = pw._acquire_deploy_lock("h", "u", "18765")
        assert ok is False
        assert "--force-unlock" in msg

        ok, msg = pw._acquire_deploy_lock("h", "u", "18765", force=True)
        assert ok is True

    def test_force_unlock_backs_off_if_owner_changed_between_check_and_delete(self, monkeypatch):
        """TOCTOU narrowing (sol round 2): if the lock's owner changes
        between the staleness check and the delete (another process's
        stale lock finished and a THIRD process grabbed a fresh one in
        that gap), --force-unlock must back off instead of deleting that
        fresh lock out from under its legitimate owner."""
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        old_ts = int(pw.time.time()) - (31 * 60)
        cat_call_count = {"n": 0}
        removed = {"v": False}

        def fake_run(cmd, **k):
            rc = cmd[-1]
            if rc.startswith("mkdir"):
                return subprocess.CompletedProcess(cmd, 1, "", "File exists")
            if rc.startswith("cat"):
                cat_call_count["n"] += 1
                if cat_call_count["n"] == 1:
                    return subprocess.CompletedProcess(cmd, 0, f"pid=999 started={old_ts}", "")
                # Someone else grabbed it between our two reads.
                return subprocess.CompletedProcess(cmd, 0, f"pid=1000 started={int(pw.time.time())}", "")
            if rc.startswith("rm -rf"):
                removed["v"] = True
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        ok, msg = pw._acquire_deploy_lock("h", "u", "18765", force=True)
        assert ok is False
        assert removed["v"] is False
        assert "changed" in msg


# ── Detached promotion: upload+launch, polling ──────────────────────────────

class TestUploadAndLaunchPromotion:
    def test_success(self, monkeypatch):
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        calls = []

        def fake_run(cmd, **k):
            calls.append(cmd[-1])
            if cmd[-1].startswith("cat >"):
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 0, "LAUNCHED\n", "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        ok, err, ambiguous = pw._upload_and_launch_promotion(
            "h", "u", "18765", "~/staging/x", "script text")
        assert ok is True
        assert err == ""
        assert ambiguous is False
        assert any(c.startswith("cat >") and ".promote.sh" in c for c in calls)
        assert any("nohup bash" in c for c in calls)

    def test_upload_failure_never_launches_and_is_not_ambiguous(self, monkeypatch):
        """The upload failing definitely means nothing was launched — the
        caller can safely release the deploy lock over this one."""
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        calls = []

        def fake_run(cmd, **k):
            calls.append(cmd[-1])
            return subprocess.CompletedProcess(cmd, 1, "", "disk full")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        ok, err, ambiguous = pw._upload_and_launch_promotion(
            "h", "u", "18765", "~/staging/x", "script text")
        assert ok is False
        assert "disk full" in err
        assert ambiguous is False
        assert not any("nohup bash" in c for c in calls)

    def test_launch_ssh_level_failure_is_ambiguous(self, monkeypatch):
        """The only realistic way the launch ssh call itself returns
        non-zero is a connection-level failure (OpenSSH's dedicated exit
        code 255) — the remote command's own last statement is an
        unconditional `echo LAUNCHED`, so a *successful* round trip always
        reports 0. That means losing this call's result doesn't prove the
        fire-and-forget `nohup ... &` never actually started — the caller
        must treat this as ambiguous, not "definitely didn't launch"."""
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)

        def fake_run(cmd, **k):
            if cmd[-1].startswith("cat >"):
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return subprocess.CompletedProcess(cmd, 255, "", "ssh: connection reset")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        ok, err, ambiguous = pw._upload_and_launch_promotion(
            "h", "u", "18765", "~/staging/x", "script text")
        assert ok is False
        assert "connection reset" in err
        assert ambiguous is True

    def test_launch_timeout_is_ambiguous(self, monkeypatch):
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)

        def fake_run(cmd, **k):
            if cmd[-1].startswith("cat >"):
                return subprocess.CompletedProcess(cmd, 0, "", "")
            raise subprocess.TimeoutExpired(cmd, k.get("timeout"))

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        ok, err, ambiguous = pw._upload_and_launch_promotion(
            "h", "u", "18765", "~/staging/x", "script text")
        assert ok is False
        assert ambiguous is True


class TestPollForPromotion:
    def test_completes_immediately(self, monkeypatch):
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        monkeypatch.setattr(
            pw.subprocess, "run",
            lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "0\n", ""),
        )
        finished, code = pw._poll_for_promotion("h", "u", "18765", "~/x/.exit", timeout=5)
        assert finished is True
        assert code == 0

    def test_tolerates_a_dropped_connection_then_succeeds(self, monkeypatch):
        """A poll attempt that fails/times out entirely must not be treated
        as a real failure — the detached script we're waiting on doesn't
        depend on this (or any) connection staying up."""
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        calls = {"n": 0}

        def fake_run(cmd, **kwargs):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
            return subprocess.CompletedProcess(cmd, 0, "0\n", "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        finished, code = pw._poll_for_promotion(
            "h", "u", "18765", "~/x/.exit", timeout=5, interval=0.001,
        )
        assert finished is True
        assert code == 0
        assert calls["n"] == 3

    def test_tolerates_pending_then_succeeds(self, monkeypatch):
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        calls = {"n": 0}

        def fake_run(cmd, **kwargs):
            calls["n"] += 1
            out = "__PENDING__" if calls["n"] < 3 else "7\n"
            return subprocess.CompletedProcess(cmd, 0, out, "")

        monkeypatch.setattr(pw.subprocess, "run", fake_run)
        finished, code = pw._poll_for_promotion(
            "h", "u", "18765", "~/x/.exit", timeout=5, interval=0.001,
        )
        assert finished is True
        assert code == 7

    def test_times_out_if_marker_never_appears(self, monkeypatch):
        monkeypatch.setattr(pw.time, "sleep", lambda s: None)
        monkeypatch.setattr(
            pw.subprocess, "run",
            lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "__PENDING__", ""),
        )
        finished, code = pw._poll_for_promotion(
            "h", "u", "18765", "~/x/.exit", timeout=0.05, interval=0.01,
        )
        assert finished is False
        assert code is None


class TestFetchAndCleanup:
    def test_fetch_remote_text_returns_stdout(self, monkeypatch):
        monkeypatch.setattr(
            pw.subprocess, "run",
            lambda cmd, **k: subprocess.CompletedProcess(cmd, 0, "log line 1\nlog line 2\n", ""),
        )
        assert pw._fetch_remote_text("h", "u", "18765", "~/x/.log") == "log line 1\nlog line 2\n"

    def test_fetch_remote_text_swallows_failure(self, monkeypatch):
        def boom(*a, **k):
            raise OSError("gone")

        monkeypatch.setattr(pw.subprocess, "run", boom)
        assert pw._fetch_remote_text("h", "u", "18765", "~/x/.log") == ""

    def test_cleanup_issues_one_rm_call(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            pw.subprocess, "run",
            lambda cmd, **k: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""),
        )
        pw._cleanup_remote_files("h", "u", "18765", ["~/x/.log", "~/x/.exit"])
        assert len(calls) == 1
        assert calls[0][-1] == "rm -f ~/x/.log ~/x/.exit"

    def test_cleanup_noop_for_empty_list(self, monkeypatch):
        def boom(*a, **k):
            raise AssertionError("must not call subprocess for an empty list")

        monkeypatch.setattr(pw.subprocess, "run", boom)
        pw._cleanup_remote_files("h", "u", "18765", [])  # must not raise


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
    """Mocks subprocess.Popen (the tar+ssh transfer) and subprocess.run
    (every other ssh call this module makes: the deploy lock, mkdir, bash -s
    verify scripts, uploading/launching/polling the detached promote script,
    chmod, and the control-master close) and records every call so tests can
    assert on staging-vs-live paths and ControlMaster options. The promote
    step "completes" on the very first poll by default (no simulated
    delay) — see promote_poll_pending_iterations to simulate one that
    doesn't."""
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
        "move_rc": 0,  # the detached promote script's own recorded exit code
        "mkdir_staging_rc": 0,
        "mkdir_staging_stderr": "",
        "lock_mkdir_rc": 0,  # 0 = lock acquired cleanly
        "upload_promote_rc": 0,
        "launch_promote_rc": 0,
        "launch_promote_stdout": "LAUNCHED",
        "promote_poll_pending_iterations": 0,
        "promote_log": "",
        "_promote_launched": False,
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

        # Deploy lock: acquire (compound `mkdir -p ROOT && mkdir LOCK`).
        if remote_cmd.startswith("mkdir -p") and pw.DEPLOY_LOCK_PATH in remote_cmd and "&&" in remote_cmd:
            return subprocess.CompletedProcess(cmd, state["lock_mkdir_rc"], "", "")
        # Deploy lock: owner marker write/read, release.
        if remote_cmd == f"cat > {pw.DEPLOY_LOCK_PATH}/owner":
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if remote_cmd.startswith("cat ") and f"{pw.DEPLOY_LOCK_PATH}/owner" in remote_cmd:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if remote_cmd.startswith("rm -rf") and pw.DEPLOY_LOCK_PATH in remote_cmd:
            return subprocess.CompletedProcess(cmd, 0, "", "")

        # Per-run staging directory (plain mkdir -p, no `&&`).
        if remote_cmd.startswith("mkdir -p") and "deploy-staging" in remote_cmd:
            return subprocess.CompletedProcess(
                cmd, state["mkdir_staging_rc"], "", state["mkdir_staging_stderr"])

        if remote_cmd.startswith("chmod 755"):
            return subprocess.CompletedProcess(cmd, 0, "", "")

        # Promote script upload.
        if remote_cmd.startswith("cat > ") and ".promote.sh" in remote_cmd:
            return subprocess.CompletedProcess(cmd, state["upload_promote_rc"], "", "")

        # Promote script launch (detached).
        if "nohup bash" in remote_cmd and ".promote.sh" in remote_cmd:
            if state["launch_promote_rc"] == 0:
                state["_promote_launched"] = True
            return subprocess.CompletedProcess(
                cmd, state["launch_promote_rc"], state["launch_promote_stdout"], "")

        # Promote completion poll.
        if remote_cmd.startswith("if [ -f") and ".exit" in remote_cmd:
            if not state["_promote_launched"] or state["promote_poll_pending_iterations"] > 0:
                if state["_promote_launched"]:
                    state["promote_poll_pending_iterations"] -= 1
                return subprocess.CompletedProcess(cmd, 0, "__PENDING__", "")
            return subprocess.CompletedProcess(cmd, 0, str(state["move_rc"]), "")

        # Promote log fetch (failure diagnostics).
        if remote_cmd.startswith("cat ") and ".log" in remote_cmd:
            return subprocess.CompletedProcess(cmd, 0, state["promote_log"], "")

        # Staging / post-move verification (bash -s, script piped via stdin).
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

        # The promote script was uploaded (only place remote_base is
        # written into) and launched, and the lock was acquired+released.
        upload_calls = [c for c in deploy_harness["run_calls"]
                        if c["input"] and "find . -type f -print0" in c["input"]]
        assert len(upload_calls) == 1
        assert deploy_harness["remote_base"] in upload_calls[0]["input"]
        launch_calls = [c for c in deploy_harness["run_calls"] if "nohup bash" in c["cmd"][-1]]
        assert len(launch_calls) == 1
        lock_acquire_calls = [c for c in deploy_harness["run_calls"]
                               if c["cmd"][-1].startswith("mkdir -p") and pw.DEPLOY_LOCK_PATH in c["cmd"][-1]]
        assert len(lock_acquire_calls) == 1
        lock_release_calls = [c for c in deploy_harness["run_calls"]
                               if c["cmd"][-1].startswith("rm -rf") and pw.DEPLOY_LOCK_PATH in c["cmd"][-1]]
        assert len(lock_release_calls) == 1

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
        # The lock was still acquired (before staging mkdir) and must still
        # be released even though this run failed.
        lock_release_calls = [c for c in deploy_harness["run_calls"]
                               if c["cmd"][-1].startswith("rm -rf") and pw.DEPLOY_LOCK_PATH in c["cmd"][-1]]
        assert len(lock_release_calls) == 1

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

        # The promote script must never have been uploaded/launched.
        upload_calls = [c for c in deploy_harness["run_calls"]
                        if c["input"] and "find . -type f -print0" in c["input"]]
        assert upload_calls == []
        launch_calls = [c for c in deploy_harness["run_calls"] if "nohup bash" in c["cmd"][-1]]
        assert launch_calls == []
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

    def test_move_never_launched_fails_cleanly(self, deploy_harness):
        """The launch itself failing (e.g. connection dropped before
        confirmation) must be reported distinctly and not treated as a
        completed-but-failed move."""
        deploy_harness["launch_promote_rc"] = 1
        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        assert ok is False
        poll_calls = [c for c in deploy_harness["run_calls"] if c["cmd"][-1].startswith("if [ -f")]
        assert poll_calls == []  # never got far enough to poll

    def test_move_survives_delayed_completion(self, deploy_harness):
        """The poll loop tolerating a few "still running" checks before the
        marker appears — simulating the ssh connection needing a moment (or
        a reconnect) to see the detached script's result — must still end
        in success."""
        deploy_harness["promote_poll_pending_iterations"] = 3
        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        assert ok is True
        poll_calls = [c for c in deploy_harness["run_calls"] if c["cmd"][-1].startswith("if [ -f")]
        assert len(poll_calls) == 4  # 3 pending + 1 final success

    def test_move_failure_reports_the_log(self, deploy_harness, capsys):
        deploy_harness["move_rc"] = 1
        deploy_harness["promote_log"] = "mv: cannot move 'x': Permission denied"
        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        assert ok is False
        assert "Permission denied" in capsys.readouterr().out

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

    def test_lock_held_refuses_before_any_staging_work(self, deploy_harness):
        deploy_harness["lock_mkdir_rc"] = 1
        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        assert ok is False
        assert deploy_harness["popen_calls"] == []
        # We never owned the lock, so we must never try to release it.
        lock_release_calls = [c for c in deploy_harness["run_calls"]
                               if c["cmd"][-1].startswith("rm -rf") and pw.DEPLOY_LOCK_PATH in c["cmd"][-1]]
        assert lock_release_calls == []

    def test_force_unlock_threaded_through(self, deploy_harness):
        """force_unlock=True must reach _acquire_deploy_lock — proven here
        by observing the lock still gets acquired+released normally when
        nothing is actually stale (force is a no-op in that case)."""
        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages", force_unlock=True,
        )
        assert ok is True

    def test_ambiguous_launch_failure_does_not_release_lock(self, deploy_harness):
        """Regression (sol round 2): the launch command is fire-and-forget
        ("... &); echo LAUNCHED") — losing its confirmation does not prove
        the move never started. Releasing the deploy lock here would let
        another bulk sync start while this one's move might actually be
        running. The lock must stay held so a human has to intervene (or
        wait for --force-unlock's staleness window)."""
        deploy_harness["launch_promote_rc"] = 255
        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        assert ok is False
        lock_release_calls = [c for c in deploy_harness["run_calls"]
                               if c["cmd"][-1].startswith("rm -rf") and pw.DEPLOY_LOCK_PATH in c["cmd"][-1]]
        assert lock_release_calls == []

    def test_poll_timeout_does_not_release_lock(self, deploy_harness, monkeypatch):
        """Same reasoning as the ambiguous-launch case: a poll that never
        saw a completion marker doesn't mean the detached move is done (or
        even that it isn't still running) — the lock must stay held.
        _poll_for_promotion itself is monkeypatched here (rather than
        actually waiting out move_timeout, which is real wall-clock time
        this loop respects even with time.sleep mocked out) since its own
        timeout behavior already has dedicated fast tests above."""
        monkeypatch.setattr(pw, "_poll_for_promotion", lambda *a, **k: (False, None))
        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        assert ok is False
        lock_release_calls = [c for c in deploy_harness["run_calls"]
                               if c["cmd"][-1].startswith("rm -rf") and pw.DEPLOY_LOCK_PATH in c["cmd"][-1]]
        assert lock_release_calls == []

    def test_confirmed_move_failure_still_releases_lock(self, deploy_harness):
        """Contrast with the two tests above: once the poll DOES confirm a
        result (even a failing one), we know the script is done running —
        no ambiguity — so the lock releases normally."""
        deploy_harness["move_rc"] = 1
        ok = pw._atomic_tar_deploy(
            host="h", user="u", port="18765",
            local_root=deploy_harness["local_root"],
            remote_base=deploy_harness["remote_base"],
            kind="pages",
        )
        assert ok is False
        lock_release_calls = [c for c in deploy_harness["run_calls"]
                               if c["cmd"][-1].startswith("rm -rf") and pw.DEPLOY_LOCK_PATH in c["cmd"][-1]]
        assert len(lock_release_calls) == 1


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

    def test_force_unlock_flag_declared(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        assert '"--force-unlock", action="store_true"' in source

    def test_sync_pages_dispatch_passes_dry_run_and_force_unlock(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        main_block = source[source.index('if __name__ == "__main__":'):]
        assert ('_run("sync-pages", sync_pages, args.pages_dir, args.dry_run, '
                'args.force_unlock)') in main_block

    def test_sync_prep_kits_dispatch_passes_dry_run_and_force_unlock(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        main_block = source[source.index('if __name__ == "__main__":'):]
        assert ('_run("sync-prep-kits", sync_prep_kits, args.prep_kit_dir, args.dry_run, '
                'args.force_unlock)') in main_block

    def test_sync_markdown_dispatch_passes_dry_run_and_force_unlock(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        main_block = source[source.index('if __name__ == "__main__":'):]
        assert 'sync_markdown(args.markdown_dir, args.dry_run, args.force_unlock)' in main_block

    def test_dry_run_globally_disables_other_syncs_before_dispatch(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        assert "_DRY_RUN_AWARE_SYNCS" in source

    def test_shared_connection_closed_once_at_end_of_run(self):
        source = (PROJECT_ROOT / "scripts" / "push_wordpress.py").read_text()
        main_block = source[source.index('if __name__ == "__main__":'):]
        assert "_close_shared_ssh_connection_if_used()" in main_block


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

    def test_deploy_content_dry_run_skips_every_other_remote_action(self, tmp_path):
        """--dry-run must be globally safe: a combined invocation like
        --deploy-content --dry-run must not run --sync-index/--sync-widget/
        --sync-llms-txt/--purge-cache for real just because --deploy-content
        turned them on — only sync_pages/sync_markdown (dry-run-aware)
        actually run, in preview mode."""
        pages_dir = tmp_path / "pages"
        pages_dir.mkdir()
        (pages_dir / "some-race.html").write_text("<html>page</html>")
        markdown_dir = tmp_path / "markdown"
        markdown_dir.mkdir()
        (markdown_dir / "some-race.md").write_text("# hi")

        proc = self._run_with_fake_ssh_creds(
            tmp_path, "--deploy-content", "--dry-run",
            "--pages-dir", str(pages_dir), "--markdown-dir", str(markdown_dir),
            "--no-prep-kit-gate", "--no-markdown-gate",
        )
        assert "DEPLOY FAILED" not in proc.stdout, proc.stdout + proc.stderr
        assert proc.returncode == 0
        assert "[dry-run]" in proc.stdout
        assert "skipping" in proc.stdout
        assert "--sync-index" in proc.stdout
        assert "--sync-widget" in proc.stdout
        assert "--sync-llms-txt" in proc.stdout
        assert "--purge-cache" in proc.stdout
