"""
Step 9: Deploy Guide

Pushes HTML guide to GitHub Pages for web access.
"""

import shutil
import subprocess
from pathlib import Path


def deploy_guide(athlete_id: str, guide_html: Path, base_dir: Path) -> str:
    """
    Deploy guide to GitHub Pages via docs/ directory.

    Returns the public URL.
    """
    slug = athlete_id.lower().replace(" ", "-")
    dest_dir = base_dir / "docs" / "guides" / slug
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_file = dest_dir / "index.html"
    shutil.copy(guide_html, dest_file)

    # Git add, commit, push
    subprocess.run(
        ["git", "add", f"docs/guides/{slug}/"],
        cwd=str(base_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", f"Deploy guide for {athlete_id}"],
        cwd=str(base_dir),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push"],
        cwd=str(base_dir),
        check=True,
        capture_output=True,
    )

    return f"https://wattgod.github.io/gravel-race-automation/guides/{slug}/"
