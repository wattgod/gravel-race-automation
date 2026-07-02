#!/usr/bin/env python3
"""Live-site link checker — catches dead internal links before visitors do.

Born from the Jul 2026 whoops audit: five dead URLs sat in the global
nav/footer of every page for ~3 months because nothing was checking.

Crawls a small seed set of live pages, extracts same-site links + assets,
and verifies each resolves (200, or a redirect landing on 200). Exits 1
with a report if anything is dead — wired to a weekly GitHub Action.

Deliberately polite to the SiteGround WAF: capped URL count, small delay,
identifiable User-Agent, GET (some servers 405 on HEAD).

Usage:
    python3 scripts/check_links.py [--max-urls 200] [--delay 0.3]
"""

import argparse
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

SITE = "https://gravelgodcycling.com"

# Pages whose outbound links get collected (keep small; nav+footer are on
# every page, so a few page types cover the shared chrome + section links).
SEED_PATHS = [
    "/",
    "/gravel-races/",
    "/guide/",
    "/race/unbound-200/",               # race page (nav, prep strip, CTAs)
    "/race/unbound-200/training-plan/",
    "/gravel-tv/",
    "/coaching/",
    "/about/",
    "/articles/",
    "/questionnaire/",
]

# Checked for existence but not crawled.
EXTRA_URLS = [
    f"{SITE}/sitemap.xml",
    f"{SITE}/robots.txt",
    f"{SITE}/wp-content/uploads/race-dates.json",
    f"{SITE}/llms.txt",
]

UA = "GravelGod-LinkCheck/1.0 (+https://gravelgodcycling.com; weekly self-audit)"


class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls: set[str] = set()

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        for key in ("href", "src"):
            val = attr.get(key)
            if not val or val.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
                continue
            url = urllib.parse.urljoin(SITE + "/", val)
            parsed = urllib.parse.urlparse(url)
            if parsed.netloc == urllib.parse.urlparse(SITE).netloc:
                # normalize: strip fragment + query
                self.urls.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")


def fetch(url: str, timeout: int = 15) -> tuple[int, str]:
    """GET a URL following redirects; return (final_status, body_or_empty)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(400_000).decode("utf-8", "replace") \
                if "text/html" in resp.headers.get("Content-Type", "") else ""
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-urls", type=int, default=200)
    parser.add_argument("--delay", type=float, default=0.3)
    args = parser.parse_args()

    to_check: set[str] = set(EXTRA_URLS)
    seed_failures = []

    for path in SEED_PATHS:
        url = SITE + path
        status, body = fetch(url)
        if status != 200:
            seed_failures.append((status, url))
            continue
        ex = LinkExtractor()
        ex.feed(body)
        to_check |= ex.urls
        time.sleep(args.delay)

    checked = dict.fromkeys(SEED_PATHS)  # seeds already verified
    urls = sorted(u for u in to_check
                  if urllib.parse.urlparse(u).path not in checked)
    if len(urls) > args.max_urls:
        print(f"NOTE: capping at {args.max_urls} of {len(urls)} discovered URLs "
              f"(raise --max-urls to cover all)")
        urls = urls[:args.max_urls]

    dead = list(seed_failures)
    for url in urls:
        status, _ = fetch(url)
        if status != 200:
            dead.append((status, url))
        time.sleep(args.delay)

    print(f"Checked {len(SEED_PATHS)} seed pages + {len(urls)} discovered URLs")
    if dead:
        print(f"\nDEAD LINKS ({len(dead)}):")
        for status, url in sorted(dead, key=lambda d: d[1]):
            print(f"  {status or 'ERR':>4}  {url}")
        return 1
    print("All links alive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
