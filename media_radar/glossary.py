"""Append genuinely new culture terms to the durable glossary."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path


def append_new_terms(path: Path, terms: list[dict], observed: date | None = None) -> list[str]:
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Media Radar Glossary\n"
    known = {term.casefold() for term in re.findall(r"^## (.+)$", existing, flags=re.M)}
    additions = []
    stamp = (observed or date.today()).isoformat()
    for item in terms:
        term = item["term"].strip()
        if term.casefold() in known:
            continue
        additions.append(term)
        existing += f"\n## {term}\n\n{item['meaning']}\n\n_First seen: {item.get('first_seen_source', 'unknown')} · {stamp}_\n"
        known.add(term.casefold())
    if additions:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(existing, encoding="utf-8")
    return additions

