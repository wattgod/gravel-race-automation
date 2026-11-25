import asyncio
import json

from scripts import generate_guide_media as media


def test_unexpected_provider_error_keeps_raw_text_out_of_batch_and_manifest(monkeypatch, tmp_path, capsys):
    private_detail = "synthetic-private-request-parameter"

    async def fail(*args, **kwargs):
        raise ValueError(f"private detail: {private_detail}")

    monkeypatch.setattr(media, "generate_nano_banana", fail)
    manifest_path = tmp_path / "manifest.json"
    monkeypatch.setattr(media, "MANIFEST_PATH", manifest_path)
    asset = {"id": "synthetic-cover"}
    result = asyncio.run(media.generate_batch([asset], {}))
    media.save_manifest({"assets": [asset]})

    assert result == {"synthetic-cover": "error: Media processing failed"}
    assert private_detail not in capsys.readouterr().out
    assert private_detail not in manifest_path.read_text()
    assert json.loads(manifest_path.read_text())["assets"][0]["error"] == "Media processing failed"


def test_legacy_error_is_safe_to_print_and_save(monkeypatch, tmp_path, capsys):
    private_detail = "synthetic-private-request-parameter"
    manifest_path = tmp_path / "manifest.json"
    monkeypatch.setattr(media, "MANIFEST_PATH", manifest_path)
    manifest = {"assets": [
        {"id": "legacy", "status": "failed", "error": private_detail},
        {"id": "safe", "status": "failed", "error": "Imagen request failed with HTTP 503"},
    ]}
    media.print_status(manifest)
    media.save_manifest(manifest)
    output = capsys.readouterr().out
    persisted = json.loads(manifest_path.read_text())

    assert private_detail not in output
    assert "Imagen request failed with HTTP 503" in output
    assert [asset["error"] for asset in persisted["assets"]] == [
        "Media processing failed", "Imagen request failed with HTTP 503",
    ]
