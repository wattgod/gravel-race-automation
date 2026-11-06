"""One "last updated" date per race page, shared by every surface that shows it.

The race page byline, the footer, WebPage JSON-LD `dateModified` and the
sitemap `<lastmod>` must all agree, or search engines and AI answers see a
page that contradicts itself. Before this module each surface used the data
file's mtime, which is really the checkout/build time, so every page claimed
to be fresh on every deploy.

Resolution order for a race (first hit wins):
  1. `race.updated`: an explicit ISO date set by whoever edited the facts.
  2. The newest `race.changelog[].date`: the visible "What changed" log.
  3. The last git commit that touched the data file (skipped in a shallow
     clone, where every file shares the clone's single commit date).
  4. The file's mtime, as before.
"""
from __future__ import annotations

import re
import subprocess
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valid_iso(value) -> Optional[str]:
    if not isinstance(value, str) or not _ISO_DATE.match(value.strip()):
        return None
    try:
        datetime.strptime(value.strip(), "%Y-%m-%d")
    except ValueError:
        return None
    return value.strip()


def changelog_entries(race: dict) -> list[dict]:
    """Valid changelog entries, newest first: [{date, change}]."""
    entries = []
    for entry in race.get("changelog") or []:
        if not isinstance(entry, dict):
            continue
        day = _valid_iso(entry.get("date"))
        change = str(entry.get("change") or "").strip()
        if day and change:
            entries.append({"date": day, "change": change})
    return sorted(entries, key=lambda e: e["date"], reverse=True)


@lru_cache(maxsize=None)
def _git_root_if_full_history(directory: str) -> Optional[str]:
    try:
        root = subprocess.run(
            ["git", "-C", directory, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        shallow = subprocess.run(
            ["git", "-C", root, "rev-parse", "--is-shallow-repository"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return None if shallow == "true" else root


def _git_commit_date(filepath: Path) -> Optional[str]:
    root = _git_root_if_full_history(str(filepath.parent))
    if not root:
        return None
    try:
        dirty = subprocess.run(
            ["git", "-C", root, "status", "--porcelain", "--", str(filepath)],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        if dirty:
            return None  # uncommitted edit: the mtime is the truth
        out = subprocess.run(
            ["git", "-C", root, "log", "-1", "--format=%cs", "--", str(filepath)],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return _valid_iso(out)


def race_updated_date(race: dict, filepath: Optional[Path] = None) -> str:
    """ISO date (YYYY-MM-DD) the race page's facts last changed."""
    explicit = _valid_iso(race.get("updated"))
    if explicit:
        return explicit
    entries = changelog_entries(race)
    if entries:
        return entries[0]["date"]
    if filepath is not None:
        filepath = Path(filepath)
        committed = _git_commit_date(filepath)
        if committed:
            return committed
        if filepath.exists():
            return datetime.fromtimestamp(filepath.stat().st_mtime).strftime("%Y-%m-%d")
    return datetime.now().strftime("%Y-%m-%d")


def format_display_date(iso_day: str) -> str:
    """'2026-10-25' -> 'October 25, 2026'."""
    dt = datetime.strptime(iso_day, "%Y-%m-%d")
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"
