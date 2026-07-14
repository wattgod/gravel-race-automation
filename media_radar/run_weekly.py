"""CLI orchestrator for the Media Radar weekly briefing."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from .deliver import deliver_digest
from .digest import render_digest, write_digest
from .glossary import append_new_terms
from .ingest import ingest_sources, load_yaml
from .mine import mine_transcripts
from .store import DATA_DIR, TranscriptStore

PACKAGE_DIR = Path(__file__).parent
CRON_LINE = "0 7 * * 1 cd /Users/mattirowe/endure-plan-engine && .venv/bin/python -m media_radar.run_weekly >> data/media-radar/media-radar.log 2>&1"


def run(*, dry_run: bool = False, smoke: bool = False, data_dir: Path = DATA_DIR) -> Path:
    load_dotenv()
    config = load_yaml(PACKAGE_DIR / "sources.yaml")
    entities = load_yaml(PACKAGE_DIR / "known_entities.yaml").get("entities", {})
    store = TranscriptStore(data_dir)
    transcripts, failures = ingest_sources(config.get("sources", []), store.seen_ids(), entities, smoke=smoke)
    selected = config.get("sources", [])[:1] if smoke else config.get("sources", [])
    failed_names = {item["source"] for item in failures}
    if selected and all(source.get("name", source["id"]) in failed_names for source in selected):
        raise RuntimeError("All Media Radar sources failed; no digest was generated")
    store.save(transcripts)
    mined = mine_transcripts(transcripts, failures)
    iso = date.today().isocalendar()
    markdown = render_digest(mined, iso.year, iso.week)
    path = write_digest(markdown, data_dir, iso.year, iso.week)
    append_new_terms(Path(data_dir) / "glossary.md", mined.get("new_terms", []))
    if dry_run:
        print(markdown)
    else:
        deliver_digest(markdown, f"Media Radar — {iso.year}-W{iso.week:02d}")
    print(f"Cron (install manually): {CRON_LINE}")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Write and print the digest without emailing it")
    parser.add_argument("--smoke", action="store_true", help="Use only the first configured real source")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        run(dry_run=args.dry_run, smoke=args.smoke)
    except Exception:
        logging.exception("Media Radar run failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
