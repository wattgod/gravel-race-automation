#!/usr/bin/env python3
"""Refresh published Slow Mid 38s metadata; never copy subscriber-only bodies.

Run before wordpress/generate_articles_index.py to include new Substack posts.
The committed snapshot keeps normal builds offline and reproducible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://gravelgodcycling.substack.com"
OUTPUT = ROOT / "web/substack-index.json"
# Reposts whose canonical on-site version already exists. Preserve that URL.
LOCAL_VERSIONS = {
    "sweet-spot-isnt-that-sweet": "/articles/sweet-spot-training-cycling/",
    "maybe-a-hater-poster-is-what-youve": "/maybe-a-hate-poster-is-what-youve-been-missing/",
    "reminder-no-one-cares-if-youre-bored": "/no-one-cares-if-youre-bored/",
    "reminder-no-one-cares-if-youre-bored-0e2": "/no-one-cares-if-youre-bored/",
    "you-know-people-remember-how-you": "/you-know-people-remember-how-you-race-right/",
    "you-dont-need-to-bike-to-bike-fast": "/you-dont-need-to-bike-to-bike-fast/",
    "i-opened-a-fascat-ai-coaching-email": "/i-opened-a-fascat-ai-coaching-email-so-you-dont-have-to/",
}


def build_entries(posts):
    entries = []
    seen = set()
    for post in posts:
        slug = post["slug"]
        if slug == "coming-soon" or slug in seen:
            continue
        seen.add(slug)
        entry = {
            "slug": slug, "url": post["canonical_url"],
            "title": post["title"].strip(), "subtitle": (post.get("subtitle") or "").strip(),
            "date": post["post_date"][:10], "image": post.get("cover_image") or "",
        }
        if slug in LOCAL_VERSIONS:
            entry["local_url"] = LOCAL_VERSIONS[slug]
        entries.append(entry)
    return entries


def fetch_posts():
    posts = []
    for offset in range(0, 10000, 20):
        query = urlencode({"sort": "new", "offset": offset, "limit": 20})
        with urlopen(f"{ORIGIN}/api/v1/archive?{query}", timeout=30) as response:
            batch = json.load(response)
        if not isinstance(batch, list):
            raise ValueError("Substack archive did not return a list")
        posts.extend(batch)
        if len(batch) < 20:
            return posts
    raise ValueError("Substack archive exceeded the pagination bound; snapshot unchanged")


def main():
    entries = build_entries(fetch_posts())
    if not entries:
        raise ValueError("Empty Substack archive; snapshot unchanged")
    OUTPUT.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")
    print(f"Saved {len(entries)} published posts to {OUTPUT}")


if __name__ == "__main__":
    main()
