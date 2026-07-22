#!/usr/bin/env python3
"""Live-site link checker — catches dead internal links before visitors do.

Born from the Jul 2026 whoops audit: five dead URLs sat in the global
nav/footer of every page for ~3 months because nothing was checking.

Seeds from the live Gravel God sitemap index/urlsets, the shared
WordPress header/footer, and a deterministic sample of 10 live race pages
whose ``data-cta`` hrefs are always checked. The CTA sample is intentional:
a sibling site's primary race-page CTA 404'd on every page for months.

Crawls capped live pages, extracts same-site links + assets, and verifies
each resolves (200, or a redirect landing on 200). Exits 1 with a report
if anything is dead — wired to a weekly GitHub Action.

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
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

SITE = "https://gravelgodcycling.com"
SITE_NETLOC = urllib.parse.urlparse(SITE).netloc
PROJECT_ROOT = Path(__file__).resolve().parent.parent

SITEMAP_URL = f"{SITE}/sitemap.xml"

# Checked for existence but not crawled.
EXTRA_URLS = [
    SITEMAP_URL,
    f"{SITE}/robots.txt",
    f"{SITE}/wp-content/uploads/race-dates.json",
    f"{SITE}/llms.txt",
]

UA = "GravelGod-LinkCheck/1.0 (+https://gravelgodcycling.com; weekly self-audit)"
SKIP_SCHEMES = ("#", "mailto:", "tel:", "data:", "javascript:")

# SiteGround's bot protection answers with HTTP 202 + an `sg-captcha` header
# instead of the page (Roadie Labs, 2026-07-22: 18 false "dead" findings, all
# 202). A 202 is never a real response from this site, so treat it as a
# challenge: back off, retry, and report still-challenged URLs separately
# rather than as dead links.
CHALLENGE_BACKOFF = (20, 45)  # seconds to wait before each retry


def normalize_url(url: str, base: str = SITE + "/", *, same_site_only: bool = True) -> str | None:
    """Resolve a URL and strip fragment/query to match the reference checker."""
    if not url or url.startswith(SKIP_SCHEMES):
        return None
    parsed = urllib.parse.urlparse(urllib.parse.urljoin(base, url))
    if parsed.scheme not in {"http", "https"}:
        return None
    if same_site_only and parsed.netloc != SITE_NETLOC:
        return None
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


class LinkExtractor(HTMLParser):
    def __init__(self, page_url: str):
        super().__init__()
        self.page_url = page_url
        self.urls: set[str] = set()
        self.cta_urls: set[str] = set()

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        for key in ("href", "src"):
            url = normalize_url(attr.get(key, ""), self.page_url, same_site_only=True)
            if url:
                self.urls.add(url)

        if "data-cta" in attr:
            cta_url = normalize_url(attr.get("href", ""), self.page_url, same_site_only=False)
            if cta_url:
                self.cta_urls.add(cta_url)


def _fetch_once(url: str, timeout: int, text_mode: bool) -> tuple[int, str, bool]:
    """GET a URL following redirects; return (final_status, body, challenged)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if text_mode:
                body = resp.read(2_000_000).decode("utf-8", "replace")
            else:
                body = resp.read(400_000).decode("utf-8", "replace") \
                    if "text/html" in resp.headers.get("Content-Type", "") else ""
            challenged = resp.status == 202 or "sg-captcha" in resp.headers
            return resp.status, body, challenged
    except urllib.error.HTTPError as e:
        challenged = e.code == 202 or (e.headers is not None and "sg-captcha" in e.headers)
        return e.code, "", challenged
    except Exception:
        return 0, "", False


def _fetch_retry(url: str, timeout: int, text_mode: bool) -> tuple[int, str, bool]:
    """_fetch_once, retrying with backoff while the WAF challenges us."""
    status, body, challenged = _fetch_once(url, timeout, text_mode)
    for pause in CHALLENGE_BACKOFF:
        if not challenged:
            break
        print(f"  WAF challenge on {url} — retrying in {pause}s")
        time.sleep(pause)
        status, body, challenged = _fetch_once(url, timeout, text_mode)
    return status, body, challenged


def fetch(url: str, timeout: int = 15) -> tuple[int, str, bool]:
    """GET a URL following redirects; return (final_status, body, challenged)."""
    return _fetch_retry(url, timeout, text_mode=False)


def fetch_text(url: str, timeout: int = 15) -> tuple[int, str, bool]:
    """GET a URL and decode text regardless of content type."""
    return _fetch_retry(url, timeout, text_mode=True)


def _local_name(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def xml_locs(xml_text: str) -> tuple[str, list[str]]:
    """Return (root_tag, canonical loc_values) for a sitemap document."""
    root = ET.fromstring(xml_text)
    tag = _local_name(root)
    locs = []
    child_tag = "sitemap" if tag == "sitemapindex" else "url"
    for child in root:
        if _local_name(child) != child_tag:
            continue
        for el in child:
            if _local_name(el) == "loc" and el.text:
                locs.append(el.text.strip())
                break
    return tag, locs


def live_sitemap_urls(delay: float) -> tuple[set[str], list[tuple[int, str]], list[tuple[int, str]]]:
    """Recursively load live sitemap indexes/urlsets and return same-site page URLs."""
    pending = [SITEMAP_URL]
    seen_sitemaps: set[str] = set()
    urls: set[str] = set()
    failures = []
    challenged_list = []

    while pending:
        sitemap_url = pending.pop(0)
        if sitemap_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap_url)
        status, body, challenged = fetch_text(sitemap_url)
        if challenged:
            challenged_list.append((status, sitemap_url))
            time.sleep(delay)
            continue
        if status != 200 or not body:
            failures.append((status, sitemap_url))
            time.sleep(delay)
            continue

        try:
            tag, locs = xml_locs(body)
        except ET.ParseError:
            failures.append((0, sitemap_url))
            time.sleep(delay)
            continue

        if tag == "sitemapindex":
            pending.extend(loc for loc in locs if loc not in seen_sitemaps)
        else:
            for loc in locs:
                normalized = normalize_url(loc, same_site_only=True)
                if normalized:
                    urls.add(normalized)
        time.sleep(delay)

    return urls, failures, challenged_list


def shared_chrome_urls() -> set[str]:
    """Render the shared header/footer and extract their hardcoded URLs."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from wordpress.shared_footer import get_mega_footer_html
    from wordpress.shared_header import get_site_header_html

    html = get_site_header_html() + get_mega_footer_html()
    ex = LinkExtractor(SITE + "/")
    ex.feed(html)
    return ex.urls | ex.cta_urls


def race_page_sample(sitemap_urls: set[str], sample_size: int = 10) -> list[str]:
    """Pick a deterministic sample of canonical race profile pages."""
    race_urls = []
    for url in sorted(sitemap_urls):
        path = urllib.parse.urlparse(url).path.strip("/")
        parts = path.split("/")
        if len(parts) == 2 and parts[0] == "race" and parts[1]:
            race_urls.append(url)
    return race_urls[:sample_size]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-urls", type=int, default=200)
    parser.add_argument("--delay", type=float, default=0.3)
    args = parser.parse_args()

    sitemap_urls, sitemap_failures, challenged_urls = live_sitemap_urls(args.delay)
    cta_sample = race_page_sample(sitemap_urls)
    required_urls = set(EXTRA_URLS) | shared_chrome_urls() | set(cta_sample)
    to_check: set[str] = set(required_urls) | set(sitemap_urls)
    dead = list(sitemap_failures)
    seed_failures = []
    cta_urls: set[str] = set()

    seed_urls = sorted(sitemap_urls)[:args.max_urls]
    for url in seed_urls:
        status, body, challenged = fetch(url)
        if challenged:
            challenged_urls.append((status, url))
            time.sleep(args.delay)
            continue
        if status != 200:
            seed_failures.append((status, url))
            time.sleep(args.delay)
            continue
        ex = LinkExtractor(url)
        ex.feed(body)
        to_check |= ex.urls
        time.sleep(args.delay)

    for url in cta_sample:
        status, body, challenged = fetch(url)
        if challenged:
            challenged_urls.append((status, url))
            time.sleep(args.delay)
            continue
        if status != 200:
            seed_failures.append((status, url))
            time.sleep(args.delay)
            continue
        ex = LinkExtractor(url)
        ex.feed(body)
        cta_urls |= ex.cta_urls
        time.sleep(args.delay)

    to_check |= cta_urls
    dead.extend(seed_failures)

    already_checked = set(seed_urls) | set(cta_sample)
    optional_urls = sorted(to_check - required_urls - already_checked)
    if len(optional_urls) > args.max_urls:
        print(f"NOTE: capping at {args.max_urls} of {len(optional_urls)} discovered URLs "
              f"(raise --max-urls to cover all)")
        optional_urls = optional_urls[:args.max_urls]

    urls = sorted(required_urls - already_checked) + optional_urls
    for url in urls:
        status, _, challenged = fetch(url)
        if challenged:
            challenged_urls.append((status, url))
        elif status != 200:
            dead.append((status, url))
        time.sleep(args.delay)

    print(f"Loaded {len(sitemap_urls)} URLs from live sitemap(s)")
    print(f"Checked {len(seed_urls)} sitemap seed pages + {len(urls)} discovered/required URLs")
    print(f"Checked data-cta hrefs from {len(cta_sample)} sampled race pages: {len(cta_urls)} CTA URLs")
    # Print challenged BEFORE dead: immune_check parses everything after the
    # "DEAD LINKS" header as dead links.
    if challenged_urls:
        print(f"\nWAF-CHALLENGED ({len(challenged_urls)}): still behind SiteGround's "
              f"bot challenge after retries — scan inconclusive, NOT dead links")
        for status, url in sorted(set(challenged_urls), key=lambda d: d[1]):
            print(f"  {status or 'ERR':>4}  {url}")
    if dead:
        print(f"\nDEAD LINKS ({len(dead)}):")
        for status, url in sorted(set(dead), key=lambda d: d[1]):
            print(f"  {status or 'ERR':>4}  {url}")
        return 1
    if challenged_urls:
        print("No dead links; some URLs unverifiable this run (WAF challenge).")
        return 0
    print("All links alive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
