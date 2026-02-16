"""Supabase Storage upload/download/signed-URL helpers."""

import os
from pathlib import Path

from mission_control.config import ATHLETES_DIR, STORAGE_BUCKET
from mission_control import supabase_client as db


def get_storage():
    """Return the Supabase storage client."""
    return db.get_client().storage


def upload_file(athlete_slug: str, local_path: Path, storage_subpath: str = "") -> str:
    """Upload a file to Supabase Storage.

    Args:
        athlete_slug: Athlete slug for path prefix
        local_path: Local file path
        storage_subpath: Optional subdirectory within athlete folder

    Returns:
        Storage path (e.g. "mike-wallace/workouts/W01_1Mon.zwo")
    """
    if storage_subpath:
        storage_path = f"{athlete_slug}/{storage_subpath}/{local_path.name}"
    else:
        storage_path = f"{athlete_slug}/{local_path.name}"

    with open(local_path, "rb") as f:
        content = f.read()

    storage = get_storage()
    bucket = storage.from_(STORAGE_BUCKET)

    # Try to remove existing file first (upsert behavior)
    try:
        bucket.remove([storage_path])
    except Exception:
        pass

    bucket.upload(storage_path, content)
    return storage_path


def upload_athlete_artifacts(athlete_id: str, slug: str) -> int:
    """Upload all artifacts for an athlete to Supabase Storage.

    Returns count of files uploaded.
    """
    athlete_dir = ATHLETES_DIR / slug
    if not athlete_dir.exists():
        return 0

    count = 0
    file_types = {
        "intake.json": "intake",
        "profile.yaml": "profile",
        "derived.yaml": "derived",
        "plan_config.yaml": "plan_config",
        "weekly_structure.yaml": "weekly_structure",
        "methodology.json": "methodology",
        "methodology.md": "methodology_md",
        "guide.html": "guide_html",
        "guide.pdf": "guide_pdf",
        "touchpoints.json": "touchpoints",
    }

    for filename, file_type in file_types.items():
        filepath = athlete_dir / filename
        if filepath.exists():
            try:
                storage_path = upload_file(slug, filepath)
                db.record_file(
                    athlete_id=athlete_id,
                    file_type=file_type,
                    storage_path=storage_path,
                    file_name=filename,
                    size_bytes=filepath.stat().st_size,
                )
                count += 1
            except Exception:
                pass

    # Upload workouts
    workouts_dir = athlete_dir / "workouts"
    if workouts_dir.exists():
        for zwo_file in sorted(workouts_dir.glob("*.zwo")):
            try:
                storage_path = upload_file(slug, zwo_file, "workouts")
                db.record_file(
                    athlete_id=athlete_id,
                    file_type="zwo",
                    storage_path=storage_path,
                    file_name=zwo_file.name,
                    size_bytes=zwo_file.stat().st_size,
                )
                count += 1
            except Exception:
                pass

    return count


def get_signed_url(storage_path: str, expires_in: int = 3600) -> str:
    """Generate a signed URL for a file in Supabase Storage.

    Args:
        storage_path: Path within the bucket
        expires_in: Seconds until URL expires (default 1 hour)

    Returns:
        Signed URL string
    """
    storage = get_storage()
    bucket = storage.from_(STORAGE_BUCKET)
    result = bucket.create_signed_url(storage_path, expires_in)
    return result.get("signedURL", "")


def download_file(storage_path: str) -> bytes:
    """Download a file from Supabase Storage."""
    storage = get_storage()
    bucket = storage.from_(STORAGE_BUCKET)
    return bucket.download(storage_path)


def list_athlete_files(athlete_slug: str) -> list[dict]:
    """List all files for an athlete in Storage."""
    storage = get_storage()
    bucket = storage.from_(STORAGE_BUCKET)
    try:
        files = bucket.list(athlete_slug)
        return files or []
    except Exception:
        return []
