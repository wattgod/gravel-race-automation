"""Local transcript persistence and deduplication ledger."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

DATA_DIR = Path("data/media-radar")


class TranscriptStore:
    def __init__(self, root: Path = DATA_DIR):
        self.root = Path(root)
        self.transcript_dir = self.root / "transcripts"
        self.ledger_path = self.root / "seen_ids.json"

    def seen_ids(self) -> set[str]:
        if not self.ledger_path.exists():
            return set()
        data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"Invalid seen-id ledger: {self.ledger_path}")
        return set(data)

    def save(self, transcripts: Iterable[dict]) -> None:
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        seen = self.seen_ids()
        for item in transcripts:
            item_id = str(item["id"])
            safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", item_id)
            (self.transcript_dir / f"{safe_id}.json").write_text(
                json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            seen.add(item_id)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ledger_path.write_text(
            json.dumps(sorted(seen), indent=2) + "\n", encoding="utf-8"
        )

