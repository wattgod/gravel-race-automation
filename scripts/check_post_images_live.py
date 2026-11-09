#!/usr/bin/env python3
"""Check that every image an imported post or /articles/ page uses is live.

Reads wordpress/posts/<slug>/index.html and wordpress/articles/<slug>/index.html,
collects each picture the page points at inside its own img/ folder (src,
srcset, poster, and the og:image), and asks the live site for each one.

Exit 1 when any of them answers 404. Anything else (a WAF challenge, a timeout)
is printed but does not fail: from a datacenter runner it proves nothing.

    python3 scripts/check_post_images_live.py [--base URL] [--list]
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://gravelgodcycling.com"
ATTR = re.compile(r'(?:src|srcset|poster|content)="([^"]+)"')


def page_images(index_html: Path, page_path: str, base: str = BASE) -> set[str]:
    """Absolute URLs of the files in this page's own img/ folder it uses."""
    urls: set[str] = set()
    html = index_html.read_text(encoding="utf-8")
    own = f"{base}{page_path}img/"
    for value in ATTR.findall(html):
        for part in value.split(","):
            ref = part.strip().split(" ")[0]
            if ref.startswith("img/"):
                urls.add(f"{base}{page_path}{ref}")
            elif ref.startswith(own):
                urls.add(ref)
    return urls


def all_images(base: str = BASE) -> set[str]:
    urls: set[str] = set()
    for index in sorted((ROOT / "wordpress" / "posts").glob("*/index.html")):
        urls |= page_images(index, f"/{index.parent.name}/", base)
    for index in sorted((ROOT / "wordpress" / "articles").glob("*/index.html")):
        urls |= page_images(index, f"/articles/{index.parent.name}/", base)
    return urls


def status(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD",
                                 headers={"User-Agent": "gg-publish-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--list", action="store_true", help="print the URLs and stop")
    args = ap.parse_args()

    urls = sorted(all_images(args.base.rstrip("/")))
    if args.list:
        print("\n".join(urls))
        return 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        codes = list(pool.map(status, urls))
    missing = [u for u, c in zip(urls, codes) if c == 404]
    unsure = [(u, c) for u, c in zip(urls, codes) if c not in (200, 404)]
    print(f"Checked {len(urls)} post/article images: {len(missing)} missing, "
          f"{len(unsure)} unverified")
    for u in missing:
        print(f"  404  {u}")
    for u, c in unsure[:20]:
        print(f"  {c or 'ERR'}  {u}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
