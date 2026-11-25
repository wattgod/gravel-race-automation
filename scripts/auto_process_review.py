"""Validate and stage scheduled race research for a single review branch."""

from pathlib import Path
import argparse
import json
import re
import shutil


SLUG = re.compile(r"[a-z0-9][a-z0-9()&-]{0,100}")
ARTIFACT_PREFIX = "race-output-"
COMPLETION_DIR = Path("data/processed/races")



def completed_races(checkout: Path) -> set[str]:
    legacy = checkout / "data/processed/completed.txt"
    names = set(legacy.read_text(encoding="utf-8").splitlines()) if legacy.exists() else set()
    for marker in (checkout / COMPLETION_DIR).glob("*.txt"):
        if marker.is_file() and not marker.is_symlink():
            names.add(marker.read_text(encoding="utf-8").strip())
    return names

def output_paths(slug: str) -> list[Path]:
    if not SLUG.fullmatch(slug):
        raise ValueError("Invalid race output slug")
    return [
        Path(f"research-dumps/{slug}-raw.md"),
        Path(f"briefs/{slug}-brief.md"),
        Path(f"landing-pages/{slug}.json"),
    ]


def validate_outputs(root: Path, paths: list[Path]) -> None:
    for relative in paths:
        file = root / relative
        if file.resolve() != file or not file.is_file() or not file.stat().st_size:
            raise ValueError("Expected a nonempty regular race output")
    if not isinstance(json.loads((root / paths[-1]).read_text(encoding="utf-8")), dict):
        raise ValueError("Expected a JSON object for the landing page")


def copy_outputs(source: Path, destination: Path, paths: list[Path]) -> None:
    for relative in paths:
        target = destination / relative
        if target.resolve() != target:
            raise ValueError("Cannot write through a symlink")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)


def restore_batch(artifacts: Path, matrix: dict, checkout: Path) -> None:
    expected = {row["folder"]: row["race_name"] for row in matrix["include"]}
    results = []
    for artifact in sorted(artifacts.iterdir()):
        slug = artifact.name.removeprefix(ARTIFACT_PREFIX)
        if (artifact.is_symlink() or not artifact.is_dir()
                or not artifact.name.startswith(ARTIFACT_PREFIX) or slug not in expected):
            raise ValueError("Unexpected race artifact")
        paths = output_paths(slug)
        validate_outputs(artifact, paths)
        actual = {file.relative_to(artifact) for file in artifact.rglob("*")
                  if file.is_symlink() or not file.is_dir()}
        if actual != set(paths):
            raise ValueError("Race artifact contains unexpected paths")
        results.append((artifact, paths, slug))
    if not results:
        raise ValueError("No successful race outputs to publish")

    for artifact, paths, slug in results:
        copy_outputs(artifact, checkout, paths)
        marker = checkout / COMPLETION_DIR / f"{slug}.txt"
        if marker.resolve() != marker:
            raise ValueError("Cannot write through a symlink")
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(expected[slug] + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage")
    stage.add_argument("slug")
    stage.add_argument("directory", type=Path)
    restore = commands.add_parser("restore")
    restore.add_argument("directory", type=Path)
    restore.add_argument("matrix")
    args = parser.parse_args()
    checkout = Path.cwd().resolve()
    if args.command == "stage":
        paths = output_paths(args.slug)
        validate_outputs(checkout, paths)
        copy_outputs(checkout, args.directory.absolute(), paths)
    else:
        restore_batch(args.directory.absolute(), json.loads(args.matrix), checkout)


if __name__ == "__main__":
    main()
