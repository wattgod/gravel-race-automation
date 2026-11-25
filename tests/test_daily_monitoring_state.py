import importlib.util
import os
from pathlib import Path
import shutil
import subprocess

src = Path(__file__).resolve().parent.parent
names = {
    "data/gsc-snapshots/2026-10-01.json": '{"overall":{"clicks": 1}}',
    "data/cwv-snapshots/2026-10-01_06-12-10.json": '{"summary":{}}',
    "reports/2026-10-01.md": "Historical report.",
    "reports/daily/fixture.md": "Historical file from another workflow.",
    "source.py": "print('internal fixture')",
}
env = {**os.environ, "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
       "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}

def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, env=env,
                                   stderr=subprocess.PIPE).strip()

def put(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n")

script = src / "scripts/daily-monitoring-state.sh"
reader_spec = importlib.util.spec_from_file_location(
    "monitoring_snapshot_history", src / "scripts/monitoring_snapshot_history.py")
reader = importlib.util.module_from_spec(reader_spec)
reader_spec.loader.exec_module(reader)

def test_monitoring_history_publication_and_readback(tmp_path, monkeypatch):
    root = tmp_path
    seed, remote = root / "seed", root / "remote"
    git(root, "init", "--initial-branch=main", str(seed))
    git(root, "init", "--bare", "--initial-branch=main", str(remote))
    for relative, text in names.items():
        put(seed, relative, text)
    (seed / "scripts").mkdir()
    shutil.copy2(src / "scripts/validate-monitoring-publication.py", seed / "scripts")
    git(seed, "add", ".")
    git(seed, "commit", "-m", "Seed")
    git(seed, "remote", "add", "origin", remote.as_uri())
    git(seed, "push", "origin", "main")
    main = git(remote, "rev-parse", "main")
    monkeypatch.setattr(reader, "REPO_ROOT", seed)

    def task(mode, state):
        return subprocess.run(["bash", str(script), mode], cwd=seed, text=True, capture_output=True,
                              env={**env, "MONITORING_STATE_DIR": str(state)})

    staged = root / "state"
    assert task("prepare", staged).returncode == 0
    put(staged, "data/gsc-snapshots/2026-10-02.json", '{"overall":{"clicks": 8}}')
    put(staged, "reports/2026-10-02.md", "Second report.")
    put(staged, "unrelated.txt", "This must stay untracked.")
    published = task("publish", staged)
    assert published.returncode == 0, published.stderr
    initial = git(remote, "rev-parse", "monitoring-state")
    assert git(remote, "rev-list", "--count", "monitoring-state") == "1"
    assert subprocess.run(["git", "-C", str(remote), "merge-base", "main", "monitoring-state"],
                          capture_output=True).returncode == 1
    allowed = {name for name in names if name.startswith("data/") or name == "reports/2026-10-01.md"}
    assert set(git(remote, "ls-tree", "-r", "--name-only", "monitoring-state").splitlines()) == allowed | {
        "data/gsc-snapshots/2026-10-02.json", "reports/2026-10-02.md"
    }

    copied = root / "next-state"
    assert task("prepare", copied).returncode == 0
    assert git(copied, "rev-parse", "HEAD") == initial
    assert not (copied / "source.py").exists()
    put(copied, "reports/2026-10-03.md", "Synthetic email marker private@example.invalid")
    result = task("publish", copied)
    assert result.returncode != 0 and "contains an email address" in result.stderr
    assert "private@example.invalid" not in result.stderr + result.stdout
    assert git(remote, "rev-parse", "monitoring-state") == initial
    put(copied, "reports/2026-10-03.md", "Third report.")
    assert task("publish", copied).returncode == 0
    assert git(remote, "rev-list", "--count", "monitoring-state") == "2"
    assert git(remote, "rev-parse", "main") == main

    branch = reader.refresh_history("UNSET_FIXTURE_HISTORY_OVERRIDE")
    assert branch == git(remote, "rev-parse", "monitoring-state")
    gsc_path = seed / "data/gsc-snapshots"
    assert reader.snapshot_names(gsc_path, branch) == {"2026-10-01.json", "2026-10-02.json"}
    assert reader.load_snapshot(gsc_path / "2026-10-02.json", branch)["overall"]["clicks"] == 8
    put(seed, "data/gsc-snapshots/2026-10-02.json", '{"overall":{"clicks": 99}}')
    assert reader.load_snapshot(gsc_path / "2026-10-02.json", branch)["overall"]["clicks"] == 99
