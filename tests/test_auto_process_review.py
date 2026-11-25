from pathlib import Path
import json
import os
import subprocess
import time
from types import SimpleNamespace

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


@pytest.mark.parametrize("overrides", [
    {},
    {"RACE_FOLDER": "../outside"},
    {"RACE_NAME": "First line\nother=value"},
    {"RESEARCH_ENGINE": "unknown"},
])
def test_individual_research_validates_inputs_and_isolates_draft_credentials(tmp_path, overrides):
    workflow = yaml.safe_load((ROOT / ".github/workflows/research-race.yml").read_text())
    assert set(workflow[True]) == {"workflow_dispatch", "repository_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    research, publish, draft = (workflow["jobs"][name] for name in ("research", "publish", "stage-draft"))
    assert "client_payload" in research["env"]["RACE_FOLDER"]
    assert research["steps"][0]["with"]["persist-credentials"] is False
    assert research["steps"][-1]["uses"] == "./.github/actions/stage-race-review"
    assert publish["with"]["review_kind"] == "research-race"
    assert publish["permissions"] == {"contents": "write"}
    assert draft["needs"] == ["research", "publish"]
    assert "WP_APP_PASSWORD" not in json.dumps(research)
    assert "SLACK_WEBHOOK" not in json.dumps(research)
    draft_step = next(step for step in draft["steps"] if step.get("name") == "Stage WordPress draft")
    assert '"$RUNNER_TEMP/reviewed-race/landing-pages/' in draft_step["run"]

    output = tmp_path / "outputs"
    step = next(step for step in research["steps"] if step.get("id") == "validate-inputs")
    fixture = {"RACE_NAME": "Fixture Race", "RACE_FOLDER": "fixture-race",
               "RESEARCH_ENGINE": "perplexity", "SKIP_VALIDATION": "false"}
    env = {**os.environ, "GITHUB_OUTPUT": str(output), "PYTHONPATH": str(ROOT / "scripts"),
           **fixture, **overrides}
    result = subprocess.run(["bash", "-e", "-c", step["run"]], cwd=tmp_path,
                            env=env, capture_output=True, text=True)
    if overrides:
        assert result.returncode != 0
        assert not output.exists()
    else:
        assert result.returncode == 0, result.stderr
        fields = dict(line.split("=", 1) for line in output.read_text().splitlines())
        assert json.loads(fields["matrix"]) == {
            "include": [{"race_name": "Fixture Race", "folder": "fixture-race"}],
        }


def test_individual_research_publishes_only_a_wordpress_draft_and_redacts_errors(
        tmp_path, monkeypatch, capsys):
    from scripts import notify, push_wordpress

    opaque = "synthetic provider response or sensitive webhook URL"
    file = tmp_path / "landing.json"
    file.write_text('{"race": {"name": "Fixture Race"}}')
    monkeypatch.setattr(push_wordpress, "get_wp_credentials",
                        lambda: ("https://wordpress.example.invalid", "user", "test-password"))

    def rejected_wordpress(_url, *, json, **_kwargs):
        assert json["status"] == "draft"
        return SimpleNamespace(status_code=403, text=opaque)

    monkeypatch.setattr(push_wordpress.requests, "post", rejected_wordpress)
    assert push_wordpress.push_to_wordpress(str(file)) is None

    def broken_webhook(*_args, **_kwargs):
        raise RuntimeError(opaque)

    monkeypatch.setattr(notify.requests, "post", broken_webhook)
    notify.notify_slack("Fixture Race", "complete", "https://hooks.example.invalid")
    log = capsys.readouterr().out
    assert "403" in log and "RuntimeError" in log
    assert opaque not in log


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


@pytest.mark.parametrize("kind", ["auto-process", "update-existing", "research-race"])
def test_publish_step_writes_only_review_ref_and_stops_if_push_fails(tmp_path, kind):
    jobs = yaml.safe_load((ROOT / ".github/workflows/publish-race-review.yml").read_text())
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
           "GITHUB_REPOSITORY": "fixture/project", "GITHUB_STEP_SUMMARY": str(summary), "REVIEW_KIND": kind}

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
    branch = f"review/{kind}/42-1"
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
    assert f"review/{kind}/42-2" not in summary.read_text()
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

@pytest.mark.parametrize("name,kind", [
    ("auto-process-races", "auto-process"),
    ("batch-process", "batch-process"),
    ("aggressive-process", "aggressive-process"),
    ("fast-process-races", "fast-process-races"),
])
def test_generation_jobs_use_shared_scanner_and_separate_publisher(name, kind):
    workflow = yaml.safe_load((ROOT / f".github/workflows/{name}.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    assert "permissions" not in jobs["process"]
    assert jobs["process"]["steps"][0]["with"]["persist-credentials"] is False
    assert jobs["process"]["steps"][-1]["uses"] == "./.github/actions/stage-race-review"
    publish = jobs["publish"]
    assert publish["needs"] == ["prepare", "process"]
    assert publish["permissions"] == {"contents": "write"}
    assert publish["uses"] == "./.github/workflows/publish-race-review.yml"
    assert publish["with"]["review_kind"] == kind


def test_manual_refresh_scans_the_existing_stale_brief_selection(tmp_path):
    workflow = yaml.safe_load((ROOT / ".github/workflows/update-existing.yml").read_text())
    assert set(workflow[True]) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    assert jobs["find-races"]["if"] == "github.ref == 'refs/heads/main'"
    assert jobs["refresh"]["steps"][0]["with"]["persist-credentials"] is False
    assert jobs["refresh"]["steps"][-1]["uses"] == "./.github/actions/stage-race-review"
    assert jobs["publish"]["needs"] == ["find-races", "refresh"]
    assert jobs["publish"]["uses"] == "./.github/workflows/publish-race-review.yml"
    assert jobs["publish"]["with"]["review_kind"] == "update-existing"

    brief_dir = tmp_path / "briefs"
    brief_dir.mkdir()
    stale = brief_dir / "older-race-brief.md"
    stale.touch()
    (brief_dir / "recent-race-brief.md").touch()
    older = time.time() - 31 * 86400
    os.utime(stale, (older, older))
    output = tmp_path / "outputs"
    step = next(step for step in jobs["find-races"]["steps"] if step.get("id") == "find")
    env = {**os.environ, "GITHUB_OUTPUT": str(output), "PYTHONPATH": str(ROOT / "scripts")}
    subprocess.run(["bash", "-e", "-c", step["run"]], cwd=tmp_path, env=env, check=True,
                   capture_output=True)
    fields = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert fields["count"] == "1"
    assert json.loads(fields["matrix"]) == {
        "include": [{"race_name": "Older Race", "folder": "older-race"}],
    }


def test_restore_rejects_duplicate_planned_slug_before_copying(tmp_path):
    artifacts = tmp_path / "artifacts"
    write_outputs(artifacts / "race-output-race-one", "race-one")
    checkout = tmp_path / "checkout"
    with pytest.raises(ValueError, match="Invalid race row"):
        restore_batch(artifacts, {"include": [
            {"folder": "race-one", "race_name": "First Race"},
            {"folder": "race-one", "race_name": "Second Race"},
        ]}, checkout)
    assert not checkout.exists()
