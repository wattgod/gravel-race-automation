"""Guard scoped uploads and ensure a captcha cannot count as deploy success."""

from io import BytesIO

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
