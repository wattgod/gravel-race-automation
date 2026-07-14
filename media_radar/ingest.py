"""Fetch captioned media published during the last seven days."""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import requests
import yaml

LOGGER = logging.getLogger(__name__)
YOUTUBE_FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def _parse_feed(url: str):
    try:
        import feedparser
    except ImportError as exc:
        raise RuntimeError("feedparser not installed. Run: pip install -r requirements.txt") from exc
    return feedparser.parse(url)


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def normalize_names(text: str, entities: dict[str, list[str]]) -> str:
    normalized = text
    for canonical, variants in entities.items():
        for variant in variants:
            normalized = re.sub(
                rf"(?<!\w){re.escape(variant)}(?!\w)", canonical, normalized,
                flags=re.IGNORECASE,
            )
    return re.sub(r"\s+", " ", html.unescape(normalized)).strip()


def _published(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    return None


def _youtube_text(video_id: str) -> str:
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    transcript = api.fetch(video_id)
    snippets = getattr(transcript, "snippets", transcript)
    return " ".join(
        snippet.text if hasattr(snippet, "text") else snippet["text"]
        for snippet in snippets
    )


def _transcript_url(entry: dict) -> str | None:
    for link in entry.get("links", []):
        url = link.get("href", "")
        kind = (link.get("type") or "").lower()
        rel = (link.get("rel") or "").lower()
        if "transcript" in rel or "text/plain" in kind or "text/html" in kind and "transcript" in url.lower():
            return url
    for field in ("transcript", "podcast_transcript"):
        value = entry.get(field)
        if isinstance(value, dict):
            return value.get("url") or value.get("href")
        if isinstance(value, str):
            return value
    return None


def _clean_document(raw: str) -> str:
    without_scripts = re.sub(r"<(script|style)\b.*?</\1>", " ", raw, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", without_scripts))).strip()


def ingest_sources(
    sources: list[dict], seen_ids: set[str], entities: dict[str, list[str]],
    *, now: datetime | None = None, smoke: bool = False,
    feed_parser: Callable = _parse_feed, http_get: Callable = requests.get,
    youtube_fetcher: Callable[[str], str] = _youtube_text,
) -> tuple[list[dict], list[dict]]:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    transcripts: list[dict] = []
    failures: list[dict] = []

    for source in sources[:1] if smoke else sources:
        source_id = source["id"]
        try:
            feed_url = (
                YOUTUBE_FEED.format(channel_id=source["channel_id"])
                if source["type"] == "youtube" else source["rss_url"]
            )
            feed = feed_parser(feed_url)
            if getattr(feed, "bozo", False) and not getattr(feed, "entries", []):
                raise RuntimeError(str(getattr(feed, "bozo_exception", "invalid feed")))
            for entry in getattr(feed, "entries", []):
                published = _published(entry)
                if published is None or not cutoff <= published <= now:
                    continue
                item_id = str(entry.get("yt_videoid") or entry.get("id") or entry.get("guid") or "")
                if not item_id or item_id in seen_ids:
                    continue
                try:
                    if source["type"] == "youtube":
                        text = youtube_fetcher(item_id)
                    else:
                        url = _transcript_url(entry)
                        if not url:
                            raise RuntimeError("episode has no transcript")
                        response = http_get(url, timeout=30)
                        response.raise_for_status()
                        text = _clean_document(response.text)
                except Exception as exc:
                    reason = f"item {item_id}: {type(exc).__name__}: {exc}"
                    LOGGER.warning("WARN source=%s reason=%s", source_id, reason)
                    failures.append({"source": source.get("name", source_id), "reason": reason})
                    continue
                transcripts.append({
                    "id": item_id, "source_id": source_id,
                    "source": source.get("name", source_id),
                    "title": entry.get("title", "Untitled"),
                    "published": published.isoformat(),
                    "text": normalize_names(text, entities),
                })
        except Exception as exc:
            reason = f"{type(exc).__name__}: {exc}"
            LOGGER.warning("WARN source=%s reason=%s", source_id, reason)
            failures.append({"source": source.get("name", source_id), "reason": reason})
    return transcripts, failures
