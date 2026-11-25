from pathlib import Path
import json
import os
import subprocess

import pytest
import yaml

from auto_process_review import completed_races, copy_outputs, output_paths, restore_batch, validate_outputs


ROOT = Path(__file__).resolve().parents[1]


def write_outputs(root, slug):
    paths = output_paths(slug)
    for path in paths:
        file = root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("{}" if file.suffix == ".json" else "# reviewed research output", encoding="utf-8")
    return paths


def test_review_batch_preserves_successful_outputs_and_completed_records(tmp_path):
    checkout, artifacts = tmp_path / "checkout", tmp_path / "artifacts"
    captured = tmp_path / "capture"
    paths = write_outputs(captured, "race-one")
    validate_outputs(captured, paths)
    copy_outputs(captured, artifacts / "race-output-race-one", paths)
    write_outputs(artifacts / "race-output-race-two", "race-two")
    existing = checkout / "data/processed/completed.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("Earlier Race\n", encoding="utf-8")
    matrix = {"include": [
        {"folder": "race-one", "race_name": "Race One"},
        {"folder": "race-two", "race_name": "Race Two"},
        {"folder": "failed-race", "race_name": "Failed Race"},
    ]}
    restore_batch(artifacts, matrix, checkout)
    restore_batch(artifacts, matrix, checkout)
    assert existing.read_text() == "Earlier Race\n"
    assert completed_races(checkout) == {"Earlier Race", "Race One", "Race Two"}
    assert (checkout / paths[0]).read_text() == "# reviewed research output"
    assert (checkout / "landing-pages/race-two.json").read_text() == "{}"
    assert not (checkout / "landing-pages/failed-race.json").exists()


def test_review_rejects_extra_files_before_copying_valid_results(tmp_path):
    artifacts = tmp_path / "artifacts"
    write_outputs(artifacts / "race-output-race-one", "race-one")
    write_outputs(artifacts / "race-output-race-two", "race-two")
    (artifacts / "race-output-race-two/unexpected.txt").write_text("unexpected")
    matrix = {"include": [
        {"folder": "race-one", "race_name": "Race One"},
        {"folder": "race-two", "race_name": "Race Two"},
    ]}
    checkout = tmp_path / "checkout"
    with pytest.raises(ValueError, match="unexpected paths"):
        restore_batch(artifacts, matrix, checkout)
    assert not checkout.exists()


def test_pending_processing_refuses_empty_or_unplanned_artifact_batches(tmp_path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    with pytest.raises(ValueError, match="No successful race outputs"):
        restore_batch(artifacts, {"include": []}, tmp_path / "checkout")
    write_outputs(artifacts / "race-output-race-one", "race-one")
    with pytest.raises(ValueError, match="Unexpected race artifact"):
        restore_batch(artifacts, {"include": []}, tmp_path / "checkout")
    with pytest.raises(ValueError, match="Invalid race output slug"):
        output_paths("unplanned/path")


def test_staging_rejects_invalid_json_and_symlinks(tmp_path):
    paths = write_outputs(tmp_path, "race-one")
    landing = tmp_path / paths[-1]
    landing.write_text("[]")
    with pytest.raises(ValueError, match="JSON object"):
        validate_outputs(tmp_path, paths)
    landing.write_text("{}")
    first = tmp_path / paths[0]
    first.unlink()
    first.symlink_to(landing)
    with pytest.raises(ValueError, match="nonempty regular"):
        validate_outputs(tmp_path, paths)


def test_publish_step_writes_only_review_ref_and_stops_if_push_fails(tmp_path):
    jobs = yaml.safe_load((ROOT / ".github/workflows/auto-process-races.yml").read_text())
    assert jobs["permissions"] == {"contents": "read"}
    assert "permissions" not in jobs["jobs"]["process"]
    publish = jobs["jobs"]["publish"]
    assert publish["permissions"] == {"contents": "write"}
    steps = publish["steps"]
    assert steps[0]["with"]["persist-credentials"] is False
    step = next(step for step in steps if step.get("name") == "Publish research for review")
    checkout, remote = tmp_path / "checkout", tmp_path / "remote"
    checkout.mkdir()
    remote.mkdir()
    summary = tmp_path / "summary"
    env = {**os.environ, "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
           "GITHUB_RUN_ID": "42", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SERVER_URL": "https://github.com",
           "GITHUB_REPOSITORY": "fixture/project", "GITHUB_STEP_SUMMARY": str(summary)}

    def git(cwd, *args):
        return subprocess.check_output(["git", "-C", str(cwd), *args], env=env, text=True, stderr=subprocess.PIPE).strip()

    git(checkout, "init", "--initial-branch=main")
    git(remote, "init", "--bare", "--initial-branch=main")
    git(checkout, "commit", "--allow-empty", "-m", "Seed")
    git(checkout, "remote", "add", "origin", remote.resolve().as_uri())
    git(checkout, "push", "origin", "main")
    main = git(remote, "rev-parse", "main")
    paths = write_outputs(checkout, "race-one")
    completed = checkout / "data/processed/races/race-one.txt"
    completed.parent.mkdir(parents=True)
    completed.write_text("Race One\n")

    def run_publish():
        return subprocess.run(["bash", "-e", "-c", step["run"]], cwd=checkout,
                              capture_output=True, text=True, env=env)
    assert run_publish().returncode == 0
    branch = "review/auto-process/42-1"
    files = set(git(remote, "diff", "--name-only", main, branch).splitlines())
    assert files == {str(path) for path in paths} | {"data/processed/races/race-one.txt"}
    assert branch in summary.read_text()
    assert git(remote, "rev-parse", "main") == main

    hook = remote / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o700)
    completed.write_text("Race Two\n")
    env["GITHUB_RUN_ATTEMPT"] = "2"
    assert run_publish().returncode != 0
    assert "review/auto-process/42-2" not in summary.read_text()
    assert git(remote, "rev-parse", "main") == main


@pytest.mark.parametrize("name", ["auto-process-races", "batch-process", "aggressive-process", "fast-process-races"])
def test_prepare_job_honors_both_completion_formats(tmp_path, name):
    workflow = yaml.safe_load((ROOT / f".github/workflows/{name}.yml").read_text())
    step = next(step for step in workflow["jobs"]["prepare"]["steps"] if step.get("id") == "set-matrix")
    db = tmp_path / "db"
    db.mkdir()
    (db / "gravel_races_full_database.json").write_text(
        '{"races":[{"RACE_NAME":"First Race","TIER":2},{"RACE_NAME":"Second Race","TIER":2}]}'
    )
    helpers = tmp_path / "scripts"
    helpers.mkdir()
    (helpers / "auto_process_review.py").write_bytes((ROOT / "scripts/auto_process_review.py").read_bytes())
    completed = tmp_path / "data/processed/completed.txt"
    completed.parent.mkdir(parents=True)
    output = tmp_path / "outputs"
    env = {**os.environ, "PROCESS_TIER": "2", "PROCESS_LIMIT": "5", "GITHUB_OUTPUT": str(output)}
    marker = completed.parent / "races/second-race.txt"
    marker.parent.mkdir()
    for expected in ("true", "false"):
        if expected == "false":
            marker.write_text("Second Race\n")
        completed.write_text("First Race\n")
        output.write_text("")
        subprocess.run(["bash", "-e", "-c", step["run"]], cwd=tmp_path, env=env, check=True, capture_output=True)
        fields = dict(line.split("=", 1) for line in output.read_text().splitlines())
        if name == "auto-process-races":
            assert fields["has_work"] == expected
        selected = [race["folder"] for race in json.loads(fields["matrix"])["include"]]
        assert selected == (["second-race"] if expected == "true" else [])


def test_disjoint_review_batches_merge_without_completion_conflicts(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    env = {**os.environ, "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
           "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}

    def git(*args):
        subprocess.run(["git", *args], cwd=checkout, env=env, check=True, capture_output=True)

    git("init", "--initial-branch=main")
    legacy = checkout / "data/processed/completed.txt"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("Earlier Race\n")
    git("add", ".")
    git("commit", "-m", "Seed")
    for slug, name in [("race-one", "Race One"), ("race-two", "Race Two")]:
        git("checkout", "-b", slug, "main")
        artifacts = tmp_path / slug
        write_outputs(artifacts / f"race-output-{slug}", slug)
        restore_batch(artifacts, {"include": [{"folder": slug, "race_name": name}]}, checkout)
        git("add", ".")
        git("commit", "-m", f"Review {name}")
    git("checkout", "main")
    git("merge", "--no-ff", "--no-edit", "race-one")
    git("merge", "--no-ff", "--no-edit", "race-two")
    assert completed_races(checkout) == {"Earlier Race", "Race One", "Race Two"}
    assert legacy.read_text() == "Earlier Race\n"
