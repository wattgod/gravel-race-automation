"""Validate and copy a Morning Intel aggregate snapshot pair."""
import argparse
from datetime import date
import json
from pathlib import Path

from daily_intel import _PUBLIC_SENSITIVE_TEXT, _validate_public_snapshot


def stage_snapshot(source: Path, destination: Path, snapshot_date: str) -> None:
    if date.fromisoformat(snapshot_date).isoformat() != snapshot_date:
        raise ValueError("Expected an ISO snapshot date")
    source, destination = source.absolute(), destination.absolute()
    names = [f"{snapshot_date}.json", f"{snapshot_date}.md"]
    files = [source / name for name in names]
    targets = [destination / name for name in names]
    if any(file.resolve() != file or not file.is_file() for file in files):
        raise ValueError("Expected two regular source files")
    if any(target.resolve() != target for target in targets):
        raise ValueError("Snapshot destination must not traverse a symlink")

    data, markdown = (file.read_bytes() for file in files)
    snapshot = json.loads(data)
    if (not isinstance(snapshot, dict) or snapshot.get("date") != snapshot_date
            or data != json.dumps(snapshot, indent=1).encode()):
        raise ValueError("Expected canonical JSON for the publication date")
    report = snapshot.get("report")
    if not isinstance(report, str) or markdown != f"# Morning Intel {snapshot_date}\n\n{report}\n".encode():
        raise ValueError("Markdown does not match snapshot")
    _validate_public_snapshot(snapshot)
    if _PUBLIC_SENSITIVE_TEXT.search(markdown.decode()):
        raise ValueError("Snapshot contains sensitive text")

    destination.mkdir(parents=True, exist_ok=True)
    for target, content in zip(targets, (data, markdown)):
        target.write_bytes(content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("snapshot_date")
    args = parser.parse_args()
    try:
        stage_snapshot(args.source, args.destination, args.snapshot_date)
    except (ValueError, OSError):
        parser.exit(1, "Morning Intel snapshot validation or staging failed.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
