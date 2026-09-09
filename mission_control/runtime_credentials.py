"""Materialize optional runtime credentials without exposing their contents."""

import json
import os
from pathlib import Path


def prepare_ga4_credentials(runtime_dir: Path | None = None) -> str:
    """Create the GA4 credential file expected by the existing client contract.

    An explicit path always wins. Railway can provide the existing GitHub-style
    JSON secret as an environment variable, but the Google client requires a
    file. Invalid input leaves GA4 unavailable and returns a bounded reason.
    """
    explicit = os.environ.get("GA4_CREDENTIALS_PATH", "").strip()
    if explicit:
        return "explicit_path" if Path(explicit).is_file() else "invalid_explicit_path"

    raw = os.environ.get("GA4_CREDENTIALS_JSON", "")
    if not raw:
        return "json_absent"
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return "json_invalid"
    required = ("client_email", "private_key", "token_uri")
    if not isinstance(value, dict) or value.get("type") != "service_account" or any(
        not isinstance(value.get(key), str) or not value[key].strip() for key in required
    ):
        return "json_invalid_shape"

    target_dir = runtime_dir or Path("/tmp/gravel-god-mission-control")
    target_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(target_dir, 0o700)
    target = target_dir / "ga4-credentials.json"
    temporary = target.with_suffix(".tmp")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(temporary, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, separators=(",", ":"))
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
        os.environ["GA4_CREDENTIALS_PATH"] = str(target)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return "write_failed"
    return "materialized"
