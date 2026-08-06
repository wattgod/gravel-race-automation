"""Live training-guide inventory helpers shared by AEO generators."""

from __future__ import annotations

import json
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


def local_training_plan_slugs(output_dir: Path) -> set[str]:
    """Return slugs from a local flat training-plan build directory."""
    return {
        path.stem
        for path in Path(output_dir).glob("*.html")
        if path.is_file()
    }


def unavailable_training_plan_slugs(
    race_data_dir: Path = PROJECT_ROOT / "race-data",
) -> set[str]:
    """Return canonical races explicitly barred from plan-guide artifacts."""
    unavailable = set()
    for path in Path(race_data_dir).glob("*.json"):
        try:
            race = json.loads(path.read_text()).get("race", {})
        except (OSError, json.JSONDecodeError):
            continue
        if (race.get("vitals") or {}).get("pack_status") == "unavailable":
            unavailable.add(race.get("slug") or path.stem)
    return unavailable


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
