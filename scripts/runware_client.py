#!/usr/bin/env python3
"""Minimal Runware REST client shared by the avatar/thumbnail generators.

API shape (verified against runware.ai docs, Jun 2026):
- POST https://api.runware.ai/v1 with Authorization: Bearer <key>
- Body: JSON array of task objects, each with taskType + taskUUID
- Response: {"data": [...], "errors": [...]}
- Video tasks are async: poll with {"taskType": "getResponse", "taskUUID": ...}

Key is read from RUNWARE_API_KEY (env) or the repo .env — never printed.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.request
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_URL = "https://api.runware.ai/v1"

# Model AIR ids (see runware.ai/docs/models/*)
MODEL_FLUX_KONTEXT_DEV = "runware:106@1"   # reference-image editing
MODEL_FLUX_DEV = "runware:101@1"           # text-to-image
MODEL_BG_REMOVAL = "bria:2@1"              # Bria RMBG v2.0
MODEL_VIDEO_DEFAULT = "klingai:5@3"        # image-to-video

POLL_INTERVAL_SEC = 6
POLL_TIMEOUT_SEC = 480


class RunwareError(RuntimeError):
    pass


def load_api_key() -> str:
    """RUNWARE_API_KEY from the environment, falling back to repo .env.
    The value is returned for use in headers only — callers must not log it."""
    key = os.environ.get("RUNWARE_API_KEY", "").strip()
    if key:
        return key
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("RUNWARE_API_KEY=") and not line.startswith("#"):
                key = line.split("=", 1)[1].strip().strip("'\"")
                if key:
                    return key
    raise RunwareError(
        "RUNWARE_API_KEY not set. Create a key at my.runware.ai → API Keys "
        "and add RUNWARE_API_KEY=... to the repo .env")


def new_uuid() -> str:
    return str(uuid.uuid4())


def request(tasks: list[dict], api_key: str | None = None,
            timeout: int = 120) -> list[dict]:
    """POST a task array; return the data list. Raises on any task error."""
    api_key = api_key or load_api_key()
    body = json.dumps(tasks).encode()
    req = urllib.request.Request(
        API_URL, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:800]
        raise RunwareError(f"HTTP {e.code} from Runware: {detail}") from e
    errors = payload.get("errors") or []
    if errors:
        raise RunwareError(f"Runware task errors: {json.dumps(errors)[:800]}")
    return payload.get("data") or []


def poll_async(task_uuid: str, api_key: str | None = None,
               timeout_sec: int = POLL_TIMEOUT_SEC) -> dict:
    """Poll getResponse until the async task (e.g. video) completes."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        data = request([{"taskType": "getResponse", "taskUUID": task_uuid}],
                       api_key=api_key)
        for item in data:
            status = item.get("status")
            if status in (None, "success") and (
                    item.get("videoURL") or item.get("imageURL")):
                return item
            if status == "error":
                raise RunwareError(f"async task failed: {item}")
        time.sleep(POLL_INTERVAL_SEC)
    raise RunwareError(f"async task {task_uuid} timed out after {timeout_sec}s")


def image_to_data_uri(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".") or "png"
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png",
            "webp": "webp"}.get(suffix, "png")
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/{mime};base64,{encoded}"


def download(url: str, dest: Path, timeout: int = 180) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "gravel-god/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        dest.write_bytes(resp.read())
    return dest
