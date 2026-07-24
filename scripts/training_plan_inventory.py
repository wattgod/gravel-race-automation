"""Live training-guide inventory helpers shared by AEO generators."""

from __future__ import annotations

import re
from pathlib import Path

from dotenv import load_dotenv


TRAINING_PLAN_PATH_RE = re.compile(r"/race/([^/]+)/training-plan/")
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def training_plan_slugs_from_inventory(live_paths: set[str]) -> set[str]:
    """Extract race slugs whose training guides exist in the live SSH inventory."""
    return {
        match.group(1)
        for path in live_paths
        if (match := TRAINING_PLAN_PATH_RE.fullmatch(path))
    }


def fetch_live_training_plan_slugs() -> set[str]:
    """Fetch SiteGround once and return the live per-race training-guide slugs."""
    # The generators are also run directly from the repository root, outside
    # push_wordpress.py (which normally loads .env for its child process).
    load_dotenv(PROJECT_ROOT / ".env")

    try:
        from scripts.deploy_parity import ssh_inventory
    except ModuleNotFoundError:
        # Direct execution (`python scripts/generate_*.py`) puts scripts/
        # rather than the repository root on sys.path.
        from deploy_parity import ssh_inventory

    return training_plan_slugs_from_inventory(ssh_inventory())
