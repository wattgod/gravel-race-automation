#!/usr/bin/env python3
"""Collect the week's cross-country ski news and podcast episodes for XC Weekly.

Reads config/xc-weekly-sources.json, fetches every RSS/Atom feed, keeps the
items published inside the window and writes one evidence file. Each item
keeps a short excerpt for the drafting step only; the excerpt is never
published. A feed that fails is recorded in `coverage` with its error, never
replaced by another source.

Usage:
    python scripts/collect_xc_weekly.py --output items.json [--days 8]
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = PROJECT_ROOT / "config" / "xc-weekly-sources.json"
USER_AGENT = "XCSkiLabsWeekly/1.0 (+https://xcskilabs.com/weekly/)"
ATOM = "{http://www.w3.org/2005/Atom}"
EXCERPT_CHARS = 400
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def load_sources(path: Path = SOURCES_PATH) -> dict:
    return json.loads(path.read_text())


def clean_text(value: str | None) -> str:
    """Strip markup and entities from feed text."""
    if not value:
        return ""
    text = html.unescape(TAG_RE.sub(" ", value))
    return SPACE_RE.sub(" ", text).strip()


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def item_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:10]


def parse_feed(xml_bytes: bytes) -> tuple[list[dict], str]:
    """Return (entries, channel_link) from RSS 2.0 or Atom bytes."""
    root = ET.fromstring(xml_bytes)
    entries: list[dict] = []
    channel = root.find("channel")
    if channel is not None:
        channel_link = (channel.findtext("link") or "").strip()
        for node in channel.findall("item"):
            enclosure = node.find("enclosure")
            entries.append({
                "title": clean_text(node.findtext("title")),
                "link": (node.findtext("link") or "").strip(),
                "published": parse_date(node.findtext("pubDate")),
                "description": clean_text(node.findtext("description")),
                "categories": [clean_text(c.text) for c in node.findall("category") if c.text],
                "has_audio": enclosure is not None,
            })
        return entries, channel_link
    channel_link = ""
    for link in root.findall(f"{ATOM}link"):
        if link.get("rel", "alternate") == "alternate":
            channel_link = link.get("href", "")
    for node in root.findall(f"{ATOM}entry"):
        link = ""
        for candidate in node.findall(f"{ATOM}link"):
            if candidate.get("rel", "alternate") == "alternate":
                link = candidate.get("href", "")
        entries.append({
            "title": clean_text(node.findtext(f"{ATOM}title")),
            "link": link.strip(),
            "published": parse_date(node.findtext(f"{ATOM}published") or node.findtext(f"{ATOM}updated")),
            "description": clean_text(node.findtext(f"{ATOM}summary") or node.findtext(f"{ATOM}content")),
            "categories": [c.get("term", "") for c in node.findall(f"{ATOM}category") if c.get("term")],
            "has_audio": False,
        })
    return entries, channel_link


def _split_categories(categories: list[str]) -> list[str]:
    """TV 2 packs tags into one comma-separated category; split them."""
    out: list[str] = []
    for category in categories:
        out.extend(part.strip().lower() for part in category.split(",") if part.strip())
    return out


def keep_entry(entry: dict, source: dict) -> bool:
    """Apply the source's cross-country filters."""
    categories = _split_categories(entry["categories"])
    exclude = {c.lower() for c in source.get("exclude_categories", [])}
    if exclude and any(c in exclude for c in categories):
        return False
    keywords = [k.lower() for k in source.get("include_keywords", [])]
    if keywords:
        haystack = " ".join([entry["title"], entry["description"], *categories]).lower()
        if not any(k in haystack for k in keywords):
            return False
    return True


def page_url(feed: str, page: int) -> str:
    if page == 1:
        return feed
    parts = urlparse(feed)
    query = dict(parse_qsl(parts.query))
    query["paged"] = str(page)
    return urlunparse(parts._replace(query=urlencode(query)))


def fetch(url: str, session: requests.Session) -> bytes:
    response = session.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.content


def collect_source(source: dict, kind: str, since: datetime, session: requests.Session) -> tuple[list[dict], dict]:
    """Fetch one source; return (items, coverage)."""
    items: list[dict] = []
    coverage = {"id": source["id"], "name": source["name"], "kind": kind,
                "feed": source["feed"], "fetched": 0, "kept": 0, "oldest_seen": None, "errors": []}
    urls = [source["feed"], *source.get("extra_feeds", [])]
    oldest: datetime | None = None
    for feed in urls:
        pages = int(source.get("pages", 1)) if feed == source["feed"] else 1
        for page in range(1, pages + 1):
            url = page_url(feed, page)
            try:
                entries, channel_link = parse_feed(fetch(url, session))
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if page > 1 and status == 404:
                    break  # ran past the last page
                coverage["errors"].append(f"{url}: HTTP {status}")
                break
            except (requests.RequestException, ET.ParseError) as exc:
                coverage["errors"].append(f"{url}: {type(exc).__name__}: {exc}")
                break
            if not entries:
                break
            coverage["fetched"] += len(entries)
            page_oldest = None
            for entry in entries:
                published = entry["published"]
                if published is None:
                    continue
                if oldest is None or published < oldest:
                    oldest = published
                if page_oldest is None or published < page_oldest:
                    page_oldest = published
                if published < since:
                    continue
                link = entry["link"] or source.get("show_url", "")
                if not link.startswith("https://"):
                    continue  # no linkable page: an item we cannot attribute is dropped
                if not entry["title"] or not keep_entry(entry, source):
                    continue
                items.append({
                    "id": item_id(link + "|" + entry["title"]),
                    "kind": kind,
                    "sourceId": source["id"],
                    "sourceName": source["name"],
                    "lang": source["lang"],
                    "title": entry["title"],
                    "url": link,
                    "published": published.isoformat(),
                    "categories": entry["categories"][:6],
                    "excerpt": entry["description"][:EXCERPT_CHARS],
                })
            if page_oldest is not None and page_oldest < since:
                break
    coverage["kept"] = len(items)
    coverage["oldest_seen"] = oldest.isoformat() if oldest else None
    return items, coverage


def merge_items(*groups: list[dict]) -> list[dict]:
    """Union item lists by id, newest first."""
    merged: dict[str, dict] = {}
    for group in groups:
        for item in group:
            merged.setdefault(item["id"], item)
    return sorted(merged.values(), key=lambda item: item["published"], reverse=True)


def collect(days: float, now: datetime | None = None, config: dict | None = None,
            session: requests.Session | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    config = config or load_sources()
    session = session or requests.Session()
    all_items: list[dict] = []
    coverage: list[dict] = []
    for kind, key in (("news", "news"), ("podcast", "podcasts")):
        for source in config[key]:
            items, cov = collect_source(source, kind, since, session)
            all_items.extend(items)
            coverage.append(cov)
    return {
        "collectedAt": now.isoformat(),
        "since": since.isoformat(),
        "sourcesVerifiedOn": config.get("verified_on"),
        "items": merge_items(all_items),
        "coverage": coverage,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--days", type=float, default=8.0)
    args = parser.parse_args(argv)
    result = collect(args.days)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    failed = [c["id"] for c in result["coverage"] if c["errors"]]
    print(json.dumps({
        "items": len(result["items"]),
        "bySource": {c["id"]: c["kept"] for c in result["coverage"]},
        "failedSources": failed,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
