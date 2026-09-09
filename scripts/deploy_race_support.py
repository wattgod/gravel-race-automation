#!/usr/bin/env python3
"""Deploy only a prepared race prep kit and Markdown profile; verify live bytes."""

import argparse
from pathlib import Path
import re
import time
import urllib.request

try:
    from scripts.prep_kit_fact_gate import GateError, validate_release as validate_prep_kit_fact_release
except ImportError:  # Direct invocation from scripts/.
    from prep_kit_fact_gate import GateError, validate_release as validate_prep_kit_fact_release


def payload_files(root: Path, slug: str) -> dict[str, Path]:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ValueError("Invalid canonical race slug")
    expected = {
        f"/race/{slug}/prep-kit/": root / "prep-kit" / f"{slug}.html",
        f"/race/{slug}.md": root / "markdown" / f"{slug}.md",
    }
    for directory, suffix in (("prep-kit", ".html"), ("markdown", ".md")):
        files = set((root / directory).iterdir())
        if files != {root / directory / f"{slug}{suffix}"}:
            raise ValueError(f"Unexpected files in {directory}; refusing broad upload")
    for path in expected.values():
        if path.is_symlink() or not path.is_file() or not path.stat().st_size:
            raise ValueError(f"Missing, empty, or symlink payload: {path}")
    return expected


def verify(files: dict[str, Path], attempts: int = 8) -> None:
    pending = dict(files)
    for attempt in range(attempts):
        for route, path in list(pending.items()):
            url = f"https://gravelgodcycling.com{route}"
            try:
                request = urllib.request.Request(url, headers={
                    "User-Agent": "gg-deploy-verification/1", "Cache-Control": "no-cache",
                })
                with urllib.request.urlopen(request, timeout=20) as response:
                    body = response.read()
                    if response.status == 200 and body == path.read_bytes():
                        print(f"Verified exact live bytes: {url}", flush=True)
                        del pending[route]
                    else:
                        print(f"Not verified: {url} (HTTP {response.status})", flush=True)
            except OSError as exc:
                print(f"Not verified: {url}: {exc}", flush=True)
        if not pending:
            return
        if attempt + 1 < attempts:
            time.sleep(10)
    raise RuntimeError("Live verification failed: " + ", ".join(pending))


def _push_wordpress():
    try:
        from scripts import push_wordpress
    except ImportError:  # Direct invocation from scripts/.
        import push_wordpress
    return push_wordpress


def validate_fact_packet(payload_dir: Path, live_baseline_dir: Path | None,
                         fact_manifest: Path | None) -> None:
    """Bind the one prep-kit HTML file to its reviewed packet before imports/uploads."""
    if live_baseline_dir is None or fact_manifest is None:
        raise GateError(
            "scoped prep-kit upload requires --prep-kit-live-baseline-dir and "
            "--prep-kit-fact-manifest")
    validate_prep_kit_fact_release(
        payload_dir / "prep-kit", live_baseline_dir, fact_manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug")
    parser.add_argument("--payload-dir", type=Path, required=True)
    parser.add_argument("--prep-kit-live-baseline-dir", type=Path)
    parser.add_argument("--prep-kit-fact-manifest", type=Path)
    parser.add_argument("--upload", action="store_true")
    args = parser.parse_args()
    files = payload_files(args.payload_dir, args.slug)
    if args.upload:
        validate_fact_packet(args.payload_dir, args.prep_kit_live_baseline_dir,
                             args.prep_kit_fact_manifest)
        push_wordpress = _push_wordpress()
        if not push_wordpress.sync_prep_kits(
                str(args.payload_dir / "prep-kit"),
                str(args.prep_kit_live_baseline_dir),
                str(args.prep_kit_fact_manifest)):
            raise RuntimeError("Prep-kit upload failed")
        if not push_wordpress.sync_markdown(str(args.payload_dir / "markdown")):
            raise RuntimeError("Markdown upload failed; prep kit may already be live")
        if not push_wordpress.purge_cache():
            raise RuntimeError("Cache purge failed")
    verify(files)


if __name__ == "__main__":
    main()
