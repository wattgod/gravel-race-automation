import json
import os

from mission_control.runtime_credentials import prepare_ga4_credentials


def _credential():
    return {
        "type": "service_account",
        "client_email": "placeholder@example.invalid",
        "private_key": "placeholder-private-key",
        "token_uri": "https://example.invalid/token",
    }


def test_materializes_valid_json_with_private_permissions(tmp_path, monkeypatch):
    monkeypatch.delenv("GA4_CREDENTIALS_PATH", raising=False)
    monkeypatch.setenv("GA4_CREDENTIALS_JSON", json.dumps(_credential()))

    assert prepare_ga4_credentials(tmp_path) == "materialized"
    paths = list(tmp_path.glob("ga4-credentials-*.json"))
    assert len(paths) == 1
    path = paths[0]
    assert os.environ["GA4_CREDENTIALS_PATH"] == str(path)
    assert tmp_path.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text()) == _credential()


def test_rejects_symlink_runtime_directory(tmp_path, monkeypatch):
    actual = tmp_path / "actual"
    actual.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)
    monkeypatch.delenv("GA4_CREDENTIALS_PATH", raising=False)
    monkeypatch.setenv("GA4_CREDENTIALS_JSON", json.dumps(_credential()))

    assert prepare_ga4_credentials(linked) == "runtime_dir_unsafe"
    assert list(actual.iterdir()) == []
    assert "GA4_CREDENTIALS_PATH" not in os.environ


def test_explicit_path_takes_precedence(tmp_path, monkeypatch):
    explicit = tmp_path / "explicit.json"
    explicit.write_text("{}")
    monkeypatch.setenv("GA4_CREDENTIALS_PATH", str(explicit))
    monkeypatch.setenv("GA4_CREDENTIALS_JSON", "not-json")

    assert prepare_ga4_credentials(tmp_path / "unused") == "explicit_path"
    assert not (tmp_path / "unused").exists()


def test_invalid_inputs_do_not_set_path_or_echo_secret(tmp_path, monkeypatch):
    monkeypatch.delenv("GA4_CREDENTIALS_PATH", raising=False)
    monkeypatch.setenv("GA4_CREDENTIALS_JSON", '{"private_key":"do-not-echo"}')

    result = prepare_ga4_credentials(tmp_path)

    assert result == "json_invalid_shape"
    assert "do-not-echo" not in result
    assert "GA4_CREDENTIALS_PATH" not in os.environ
