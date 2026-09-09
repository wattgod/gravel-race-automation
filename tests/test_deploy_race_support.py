"""Guard scoped uploads and ensure a captcha cannot count as deploy success."""

from io import BytesIO
from types import SimpleNamespace
import sys

import pytest

from scripts import deploy_race_support as deploy


@pytest.fixture
def payload(tmp_path):
    for directory, suffix in (("prep-kit", ".html"), ("markdown", ".md")):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / f"winterberg{suffix}").write_text("expected")
    return tmp_path


def test_payload_rejects_other_races(payload):
    (payload / "markdown" / "other.md").write_text("unrelated")
    with pytest.raises(ValueError, match="broad upload"):
        deploy.payload_files(payload, "winterberg")


@pytest.mark.parametrize("slug", ["../winterberg", "winterberg;true", "", "A B"])
def test_payload_rejects_unsafe_slug(payload, slug):
    with pytest.raises(ValueError, match="slug"):
        deploy.payload_files(payload, slug)


@pytest.mark.parametrize("status,body,success", [
    (200, b"expected", True),
    (202, b"expected", False),
    (200, b"<html>sgcaptcha</html>", False),
    (200, b"stale", False),
])
def test_verification_requires_200_and_exact_bytes(payload, monkeypatch, status, body, success):
    def fetch(*args, **kwargs):
        response = BytesIO(body)
        response.status = status
        return response
    monkeypatch.setattr(deploy.urllib.request, "urlopen", fetch)
    files = deploy.payload_files(payload, "winterberg")
    if success:
        deploy.verify(files, attempts=1)
    else:
        with pytest.raises(RuntimeError, match="verification failed"):
            deploy.verify(files, attempts=1)


def test_upload_forwards_valid_fact_packet_before_any_upload(payload, tmp_path, monkeypatch):
    baseline = tmp_path / "live"
    manifest = tmp_path / "review.json"
    baseline.mkdir()
    manifest.write_text("{}")
    calls = []
    monkeypatch.setattr(
        deploy, "validate_prep_kit_fact_release",
        lambda proposed, live, review: calls.append((proposed, live, review)))
    client = SimpleNamespace(
        sync_prep_kits=lambda path, live, review: calls.append(("prep", path, live, review)) or True,
        sync_markdown=lambda path: calls.append(("markdown", path)) or True,
        purge_cache=lambda: calls.append(("purge",)) or True,
    )
    monkeypatch.setattr(deploy, "_push_wordpress", lambda: client)
    monkeypatch.setattr(deploy, "verify", lambda files: calls.append(("verify", files)))
    monkeypatch.setattr(sys, "argv", [
        "deploy_race_support.py", "winterberg", "--payload-dir", str(payload), "--upload",
        "--prep-kit-live-baseline-dir", str(baseline),
        "--prep-kit-fact-manifest", str(manifest),
    ])
    deploy.main()
    assert calls[0] == (payload / "prep-kit", baseline, manifest)
    assert calls[1:4] == [
        ("prep", str(payload / "prep-kit"), str(baseline), str(manifest)),
        ("markdown", str(payload / "markdown")),
        ("purge",),
    ]


def test_invalid_fact_packet_blocks_prep_markdown_and_purge(payload, tmp_path, monkeypatch):
    baseline = tmp_path / "live"
    manifest = tmp_path / "review.json"
    baseline.mkdir()
    manifest.write_text("{}")
    monkeypatch.setattr(
        deploy, "validate_prep_kit_fact_release",
        lambda *args: (_ for _ in ()).throw(deploy.GateError("invalid packet")))
    client = SimpleNamespace(
        sync_prep_kits=lambda *args: pytest.fail("prep upload reached"),
        sync_markdown=lambda path: pytest.fail("markdown upload reached"),
        purge_cache=lambda: pytest.fail("cache purge reached"),
    )
    monkeypatch.setattr(deploy, "_push_wordpress", lambda: client)
    monkeypatch.setattr(sys, "argv", [
        "deploy_race_support.py", "winterberg", "--payload-dir", str(payload), "--upload",
        "--prep-kit-live-baseline-dir", str(baseline),
        "--prep-kit-fact-manifest", str(manifest),
    ])
    with pytest.raises(deploy.GateError, match="invalid packet"):
        deploy.main()


def test_workflow_validates_packet_before_ssh_and_forwards_it():
    workflow = (deploy.Path(__file__).resolve().parent.parent / ".github" / "workflows"
                / "deploy-race-support.yml").read_text()
    assert workflow.index("Validate checked-in prep-kit fact packet before SSH") < workflow.index("Configure SSH")
    assert "release/prep-kit-fact-packets/$RACE_SLUG" in workflow
    assert "--prep-kit-live-baseline-dir" in workflow
    assert "--prep-kit-fact-manifest" in workflow
