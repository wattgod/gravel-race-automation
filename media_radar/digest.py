"""Render structured briefing JSON as Markdown."""

from __future__ import annotations

from datetime import date
from pathlib import Path


def render_digest(data: dict, iso_year: int | None = None, iso_week: int | None = None) -> str:
    current = date.today().isocalendar()
    year, week = iso_year or current.year, iso_week or current.week
    lines = [f"# Media Radar — {year}-W{week:02d}", "", "## TL;DR", "", data.get("tldr", "No summary available."), ""]
    sections = [
        ("Top Topics", "top_topics", lambda x: f"### {x['topic']}\n\n{x['why_it_matters']}\n\nSources: {', '.join(x.get('sources', []))}"),
        ("New Terms", "new_terms", lambda x: f"- **{x['term']}** — {x['meaning']} _(first seen: {x.get('first_seen_source', 'unknown')})_"),
        ("Pitched Angles", "article_angles", lambda x: f"### {x['headline']}\n\n{x['angle']}\n\n**Hook:** {x['hook']}"),
        ("Race-DB Items to Verify — SUGGESTIONS ONLY", "race_db_flags", lambda x: f"- **{x['race']}** — {x['claim']} (confidence: {x['confidence']}; source: {x['source']}) — **verify manually**"),
        ("Sources That Failed", "failed_sources", lambda x: f"- **{x['source']}** — {x['reason']}"),
    ]
    for title, key, formatter in sections:
        lines.extend([f"## {title}", ""])
        items = data.get(key, [])
        lines.extend([formatter(item) for item in items] or ["None."])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_digest(markdown: str, root: Path, iso_year: int, iso_week: int) -> Path:
    weekly = Path(root) / "weekly"
    weekly.mkdir(parents=True, exist_ok=True)
    path = weekly / f"{iso_year}-W{iso_week:02d}.md"
    path.write_text(markdown, encoding="utf-8")
    return path

