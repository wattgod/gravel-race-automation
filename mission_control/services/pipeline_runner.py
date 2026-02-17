"""Pipeline runner — subprocess wrapper for run_pipeline.py.

Runs pipeline as subprocess for process isolation (run_pipeline.py calls sys.exit).
Background thread keeps HTTP response non-blocking.
Uploads artifacts to Supabase Storage on completion.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from mission_control.config import ATHLETES_DIR, PIPELINE_SCRIPT, PRE_DELIVERY_AUDIT
from mission_control import supabase_client as db

logger = logging.getLogger(__name__)


def trigger_pipeline(
    athlete_id: str,
    slug: str,
    run_type: str = "draft",
    skip_pdf: bool = True,
    skip_deploy: bool = True,
    skip_deliver: bool = True,
) -> str:
    """Start a pipeline run in background thread. Returns pipeline_run UUID."""
    intake_path = ATHLETES_DIR / slug / "intake.json"
    if not intake_path.exists():
        raise FileNotFoundError(f"No intake.json for {slug}")

    # Create run record
    run = db.create_pipeline_run(
        athlete_id=athlete_id,
        run_type=run_type,
        skip_pdf=skip_pdf,
        skip_deploy=skip_deploy,
        skip_deliver=skip_deliver,
    )
    run_id = run["id"]

    # Update athlete status
    db.update_athlete(slug, {"plan_status": "pipeline_running"})

    # Update run to running
    db.update_pipeline_run(run_id, {"status": "running", "current_step": "starting"})

    # Log audit
    db.log_action("pipeline_triggered", "athlete", str(athlete_id),
                  f"run_type={run_type}, run_id={run_id}")

    # Build command
    cmd = ["python3", str(PIPELINE_SCRIPT), str(intake_path)]
    if skip_pdf:
        cmd.append("--skip-pdf")
    if skip_deploy:
        cmd.append("--skip-deploy")
    if skip_deliver:
        cmd.append("--skip-deliver")

    # Run in background thread (non-daemon so shutdown waits for completion)
    thread = threading.Thread(
        target=_run_pipeline_subprocess,
        args=(run_id, athlete_id, slug, cmd),
        name=f"pipeline-{run_id[:8]}",
    )
    thread.start()

    return run_id


def trigger_audit(athlete_id: str, slug: str) -> str:
    """Run pre-delivery audit as subprocess. Returns pipeline_run UUID."""
    athlete_dir = ATHLETES_DIR / slug
    if not athlete_dir.exists():
        raise FileNotFoundError(f"No athlete dir for {slug}")

    run = db.create_pipeline_run(athlete_id=athlete_id, run_type="audit")
    run_id = run["id"]

    db.update_pipeline_run(run_id, {"status": "running", "current_step": "auditing"})

    cmd = ["python3", str(PRE_DELIVERY_AUDIT), str(athlete_dir)]

    thread = threading.Thread(
        target=_run_pipeline_subprocess,
        args=(run_id, athlete_id, slug, cmd),
        name=f"audit-{run_id[:8]}",
    )
    thread.start()

    return run_id


def get_run_status(run_id: str) -> dict | None:
    """Get current status of a pipeline run."""
    return db.get_pipeline_run(run_id)


def _run_pipeline_subprocess(run_id: str, athlete_id: str, slug: str, cmd: list[str]) -> None:
    """Execute pipeline subprocess, updating Supabase with progress."""
    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )

        duration = time.time() - start
        stdout = result.stdout[-10000:] if len(result.stdout) > 10000 else result.stdout
        stderr = result.stderr[-5000:] if len(result.stderr) > 5000 else result.stderr

        if result.returncode == 0:
            db.update_pipeline_run(run_id, {
                "status": "completed",
                "current_step": "done",
                "stdout": stdout,
                "duration_secs": round(duration, 1),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })

            # Update athlete with derived/methodology data
            _sync_athlete_artifacts(athlete_id, slug)

            db.update_athlete(slug, {"plan_status": "pipeline_complete"})
        else:
            error_msg = stderr or stdout or f"Exit code {result.returncode}"
            db.update_pipeline_run(run_id, {
                "status": "failed",
                "current_step": "error",
                "error_message": error_msg[-2000:],
                "stdout": stdout,
                "duration_secs": round(duration, 1),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })

    except subprocess.TimeoutExpired:
        duration = time.time() - start
        db.update_pipeline_run(run_id, {
            "status": "failed",
            "current_step": "timeout",
            "error_message": "Pipeline timed out after 10 minutes",
            "duration_secs": round(duration, 1),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })

    except Exception as e:
        duration = time.time() - start
        db.update_pipeline_run(run_id, {
            "status": "failed",
            "current_step": "error",
            "error_message": str(e)[:2000],
            "duration_secs": round(duration, 1),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })


def _sync_athlete_artifacts(athlete_id: str, slug: str) -> None:
    """After pipeline completion, sync derived data and upload artifacts."""
    athlete_dir = ATHLETES_DIR / slug

    # Update derived_json
    derived_path = athlete_dir / "derived.yaml"
    if derived_path.exists():
        import yaml
        derived = yaml.safe_load(derived_path.read_text())
        db.update("gg_athletes", {"derived_json": derived}, {"id": athlete_id})

    # Update methodology_json
    methodology_path = athlete_dir / "methodology.json"
    if methodology_path.exists():
        methodology = json.loads(methodology_path.read_text())
        db.update("gg_athletes", {"methodology_json": methodology}, {"id": athlete_id})

    # Sync touchpoints
    tp_path = athlete_dir / "touchpoints.json"
    if tp_path.exists():
        data = json.loads(tp_path.read_text())
        for tp in data.get("touchpoints", []):
            db.upsert_touchpoint({
                "athlete_id": athlete_id,
                "touchpoint_id": tp["id"],
                "category": tp.get("category", ""),
                "send_date": tp["send_date"],
                "subject": tp.get("subject", ""),
                "template": tp.get("template", tp["id"]),
                "template_data": tp.get("template_data"),
                "sent": bool(tp.get("sent")),
                "sent_at": tp.get("sent_at"),
            })

    # Upload artifacts to Supabase Storage
    try:
        from mission_control.services.file_storage import upload_athlete_artifacts
        upload_athlete_artifacts(athlete_id, slug)
    except Exception:
        logger.exception("Failed to upload artifacts for athlete %s (%s)", slug, athlete_id)
