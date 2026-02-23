#!/usr/bin/env python3
"""
Discover new citation sources for race profiles via DuckDuckGo web search.

For each race, runs three targeted searches:
  1. "{race_name}" site:strambecco.com
  2. "{race_name}" race report blog
  3. "{race_name}" podcast episode

Filters results for relevance, deduplicates against existing citations,
and adds new URLs respecting the 20-citation cap per profile.

Conservative: only adds URLs that contain at least one word from the race slug.
Rate-limited with configurable delay between queries.

Search backends (selected with --backend):
  ddgs     — `duckduckgo_search` library (best anti-bot handling). Install:
              pip install duckduckgo_search
  html     — Direct POST to html.duckduckgo.com (no extra deps, but
              DuckDuckGo may serve CAPTCHAs after a few queries)
  auto     — Try ddgs first, fall back to html (default)

Usage:
    python scripts/discover_new_sources.py               # All races
    python scripts/discover_new_sources.py --dry-run      # Preview only
    python scripts/discover_new_sources.py --slug foo     # Single race
    python scripts/discover_new_sources.py --delay 5      # 5s between queries
    python scripts/discover_new_sources.py --backend html # Force HTML backend
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, unquote

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library required. Install with: pip install requests")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "race-data"

MAX_CITATIONS = 20

# ── Noise domains to skip ────────────────────────────────────────────
NOISE_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "strava.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "pinterest.com",
    "amazon.com",
    "amzn.to",
    "gravelgodcycling.com",
    "google.com",
    "google.co.uk",
    "goo.gl",
    "bit.ly",
    "t.co",
    "tinyurl.com",
    "web.archive.org",
    "maps.google.com",
    "maps.app.goo.gl",
    "play.google.com",
    "apps.apple.com",
    "schema.org",
    "w3.org",
    "wp.com",
    "wordpress.com",
    "wordpress.org",
    "gravatar.com",
    "cloudflare.com",
    "cdn.shopify.com",
    "fonts.googleapis.com",
}

# YouTube shorts are noise; full YouTube videos are fine
YOUTUBE_SHORTS_RE = re.compile(r"youtube\.com/shorts/", re.I)

# ── Known media domains for category assignment ──────────────────────
MEDIA_DOMAINS = {
    "velonews.com",
    "cyclingtips.com",
    "bikeradar.com",
    "gearjunkie.com",
    "cyclingweekly.com",
    "cxmagazine.com",
    "ridinggravel.com",
    "gravelcyclist.com",
    "outsideonline.com",
    "velo.outsideonline.com",
    "bicycling.com",
    "cyclingnews.com",
    "escapecollective.com",
    "pelotonmagazine.com",
    "road.cc",
    "bikemag.com",
    "bikepackingjournal.com",
    "bikepacking.com",
    "adventurecycling.org",
}


# ── Category assignment ──────────────────────────────────────────────
def assign_category(url: str) -> str:
    """Assign a citation category based on domain."""
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return "blog"

    if "strambecco.com" in domain:
        return "activity"
    if "reddit.com" in domain or "redd.it" in domain:
        return "community"
    if "trainerroad.com" in domain:
        return "community"
    if any(md in domain for md in MEDIA_DOMAINS):
        return "media"
    if "youtube.com" in domain or "youtu.be" in domain:
        return "video"
    if "ridewithgps.com" in domain:
        return "route"
    if "wikipedia.org" in domain:
        return "reference"

    return "blog"


def assign_label(url: str) -> str:
    """Generate a human-readable label from the URL domain."""
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return "Web"

    # Known labels
    LABELS = {
        "strambecco.com": "Strambecco",
        "reddit.com": "Reddit",
        "youtube.com": "YouTube",
        "youtu.be": "YouTube",
        "velonews.com": "VeloNews",
        "cyclingtips.com": "CyclingTips",
        "bikeradar.com": "BikeRadar",
        "gearjunkie.com": "GearJunkie",
        "cyclingweekly.com": "Cycling Weekly",
        "cxmagazine.com": "CX Magazine",
        "ridinggravel.com": "Riding Gravel",
        "gravelcyclist.com": "Gravel Cyclist",
        "outsideonline.com": "Outside",
        "velo.outsideonline.com": "Velo",
        "bicycling.com": "Bicycling",
        "cyclingnews.com": "CyclingNews",
        "escapecollective.com": "Escape Collective",
        "bikepacking.com": "Bikepacking",
        "trainerroad.com": "TrainerRoad",
        "ridewithgps.com": "RideWithGPS",
        "wikipedia.org": "Wikipedia",
    }

    for key, label in LABELS.items():
        if key in domain:
            return label

    # Fallback: capitalize the domain base
    return domain.split(".")[0].title()


# ── Search backends ──────────────────────────────────────────────────

# --- Backend: duckduckgo_search library (ddgs) ---
_ddgs_available = False
_DDGS = None
try:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            from ddgs import DDGS as _DDGS_cls
        except ImportError:
            from duckduckgo_search import DDGS as _DDGS_cls
        _DDGS = _DDGS_cls
        _ddgs_available = True
except ImportError:
    pass


def search_ddgs(query: str) -> list:
    """Search using the duckduckgo_search / ddgs library. Returns list of URLs."""
    if not _ddgs_available or _DDGS is None:
        return []
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ddgs = _DDGS()
            results = ddgs.text(query, max_results=10)
        urls = []
        for r in results:
            href = r.get("href", "")
            if href and href.startswith("http"):
                urls.append(href)
        return urls
    except Exception as e:
        print(f"    WARN: ddgs search failed: {e}")
        return []


# --- Backend: HTML scraping ---
SEARCH_URL = "https://html.duckduckgo.com/html/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# DDG result link patterns
DDG_LINK_RE = re.compile(r'class="result__a"\s+href="([^"]+)"', re.I)
DDG_URL_RE = re.compile(r'class="result__url"\s*[^>]*>([^<]+)<', re.I)
DDG_REDIRECT_RE = re.compile(r"uddg=([^&]+)", re.I)

# Detect CAPTCHA / anomaly page
DDG_CAPTCHA_RE = re.compile(r"anomaly-modal|bots use DuckDuckGo", re.I)

_captcha_warned = False


def search_html(query: str, session: requests.Session) -> list:
    """Search DuckDuckGo HTML endpoint. Returns list of URLs."""
    global _captcha_warned

    try:
        resp = session.post(
            SEARCH_URL,
            data={"q": query, "b": ""},
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"    WARN: HTML search failed for '{query[:60]}': {e}")
        return []

    html = resp.text

    # Detect CAPTCHA
    if DDG_CAPTCHA_RE.search(html):
        if not _captcha_warned:
            print("    WARN: DuckDuckGo is serving a CAPTCHA. HTML backend rate-limited.")
            print("          Try increasing --delay or use --backend ddgs.")
            _captcha_warned = True
        return []

    urls = []

    # Extract from href attributes
    for match in DDG_LINK_RE.finditer(html):
        href = match.group(1)
        redir = DDG_REDIRECT_RE.search(href)
        if redir:
            real_url = unquote(redir.group(1))
            if real_url.startswith("http"):
                urls.append(real_url)
        elif href.startswith("http"):
            urls.append(href)

    # Fallback: result__url spans
    if not urls:
        for match in DDG_URL_RE.finditer(html):
            raw = match.group(1).strip()
            if not raw.startswith("http"):
                raw = "https://" + raw
            urls.append(raw)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for u in urls:
        norm = u.split("#")[0].rstrip("/")
        if norm not in seen:
            seen.add(norm)
            unique.append(u)

    return unique[:10]


def make_searcher(backend: str, session: requests.Session):
    """Return a search function based on the chosen backend."""
    if backend == "ddgs":
        if not _ddgs_available:
            print("ERROR: duckduckgo_search library not installed.")
            print("  Install with: pip install duckduckgo_search")
            sys.exit(1)
        return lambda q: search_ddgs(q)

    if backend == "html":
        return lambda q: search_html(q, session)

    # auto: try ddgs, fall back to html
    if _ddgs_available:
        def auto_search(q):
            results = search_ddgs(q)
            if results:
                return results
            return search_html(q, session)
        return auto_search
    else:
        return lambda q: search_html(q, session)


# ── Relevance filtering ──────────────────────────────────────────────
def is_noise_domain(url: str) -> bool:
    """Return True if URL belongs to a noise domain."""
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return True

    for noise in NOISE_DOMAINS:
        if noise in domain:
            return True

    # YouTube shorts specifically
    if YOUTUBE_SHORTS_RE.search(url):
        return True

    return False


def is_relevant_to_race(url: str, slug: str) -> bool:
    """Return True if URL contains at least one word from the race slug.

    Conservative filter: requires the URL (path or domain) to contain
    at least one slug word that is 4+ characters long, OR any slug word
    of 3+ characters if the slug only has short words.
    """
    slug_parts = slug.split("-")
    url_lower = url.lower()

    # Try long words first (4+ chars)
    long_words = [w for w in slug_parts if len(w) >= 4]
    if long_words:
        return any(w in url_lower for w in long_words)

    # Fallback for slugs with only short words (3+ chars)
    medium_words = [w for w in slug_parts if len(w) >= 3]
    if medium_words:
        return any(w in url_lower for w in medium_words)

    # Ultra-short slug -- match any part
    return any(w in url_lower for w in slug_parts if w)


def is_generic_homepage(url: str) -> bool:
    """Return True if URL is just a domain homepage with no specific path."""
    try:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if not path:
            return True
        if re.match(r"^/[a-z]{2}$", path):
            return True
        return False
    except Exception:
        return False


# ── Main processing ──────────────────────────────────────────────────
def get_search_queries(race_name: str) -> list:
    """Build the three search queries for a race."""
    return [
        f'"{race_name}" site:strambecco.com',
        f'"{race_name}" race report blog',
        f'"{race_name}" podcast episode',
    ]


def process_race(
    filepath: Path,
    search_fn,
    delay: float,
    dry_run: bool = False,
) -> dict:
    """Process a single race profile. Returns report dict."""
    slug = filepath.stem
    data = json.loads(filepath.read_text())
    race = data["race"]

    race_name = race.get("display_name", "") or race.get("name", slug)
    existing_citations = race.get("citations", [])
    existing_urls = {c.get("url", "").split("#")[0].rstrip("/") for c in existing_citations}

    # Check if already at cap
    if len(existing_citations) >= MAX_CITATIONS:
        return {
            "slug": slug,
            "searched": False,
            "reason": "at_cap",
            "added": [],
            "skipped_noise": 0,
            "skipped_irrelevant": 0,
            "skipped_duplicate": 0,
        }

    queries = get_search_queries(race_name)
    candidates = []
    skipped_noise = 0
    skipped_irrelevant = 0
    skipped_duplicate = 0

    for i, query in enumerate(queries):
        if i > 0:
            time.sleep(delay)

        results = search_fn(query)

        for url in results:
            # Clean the URL
            url = url.split("#:~:text=")[0]  # Strip Google text fragments
            norm = url.split("#")[0].rstrip("/")

            # Filter: noise domain
            if is_noise_domain(url):
                skipped_noise += 1
                continue

            # Filter: generic homepage
            if is_generic_homepage(url):
                skipped_noise += 1
                continue

            # Filter: already cited
            if norm in existing_urls:
                skipped_duplicate += 1
                continue

            # Filter: relevance -- URL must contain a slug word
            if not is_relevant_to_race(url, slug):
                skipped_irrelevant += 1
                continue

            # Deduplicate within this run's candidates
            if norm not in {c["url"].split("#")[0].rstrip("/") for c in candidates}:
                candidates.append({
                    "url": url,
                    "category": assign_category(url),
                    "label": assign_label(url),
                })
                existing_urls.add(norm)

    # Respect the 20-citation cap
    slots_available = MAX_CITATIONS - len(existing_citations)
    added = candidates[:slots_available]

    if added and not dry_run:
        race["citations"] = existing_citations + added
        data["race"] = race
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    return {
        "slug": slug,
        "searched": True,
        "reason": None,
        "added": added,
        "skipped_noise": skipped_noise,
        "skipped_irrelevant": skipped_irrelevant,
        "skipped_duplicate": skipped_duplicate,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Discover new citation sources for race profiles via DuckDuckGo"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview discoveries without writing to files",
    )
    parser.add_argument(
        "--slug",
        help="Process only this race slug",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Seconds between search queries (default: 3)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max races to process (0 = all, useful for testing)",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "ddgs", "html"],
        default="auto",
        help="Search backend: ddgs (library), html (scraper), auto (default)",
    )
    args = parser.parse_args()

    files = sorted(DATA_DIR.glob("*.json"))
    if args.slug:
        target = DATA_DIR / f"{args.slug}.json"
        if not target.exists():
            print(f"ERROR: {target} not found")
            sys.exit(1)
        files = [target]

    if args.limit > 0:
        files = files[: args.limit]

    session = requests.Session()
    search_fn = make_searcher(args.backend, session)

    results = []
    total_added = 0
    races_enriched = 0
    at_cap = 0
    total_noise = 0
    total_irrelevant = 0
    total_duplicate = 0

    backend_label = args.backend
    if args.backend == "auto":
        backend_label = "ddgs+html" if _ddgs_available else "html"

    print(f"Discovering new citation sources for {len(files)} race(s)...")
    print(f"  Backend: {backend_label}")
    print(f"  Delay: {args.delay}s between queries")
    if args.dry_run:
        print("  Mode: DRY RUN (no files modified)")
    print()

    for i, fp in enumerate(files):
        slug = fp.stem

        # Rate limit between races (3 queries per race)
        if i > 0:
            time.sleep(args.delay)

        result = process_race(fp, search_fn, args.delay, dry_run=args.dry_run)
        results.append(result)

        if not result["searched"]:
            at_cap += 1
            continue

        total_noise += result["skipped_noise"]
        total_irrelevant += result["skipped_irrelevant"]
        total_duplicate += result["skipped_duplicate"]

        if result["added"]:
            races_enriched += 1
            total_added += len(result["added"])
            print(f"  {slug}: +{len(result['added'])} citations")
            for c in result["added"]:
                print(f"    [{c['category']}] {c['label']}: {c['url'][:90]}")

    # ── Summary ──────────────────────────────────────────────────────
    searched = len(files) - at_cap
    prefix = "DRY RUN -- " if args.dry_run else ""
    print(f"\n{prefix}Discovery Summary:")
    print(f"  Races scanned:       {len(files)}")
    print(f"  Already at cap:      {at_cap}")
    print(f"  Searched:            {searched}")
    print(f"  Races enriched:      {races_enriched}")
    print(f"  New citations added: {total_added}")
    print(f"  Skipped (noise):     {total_noise}")
    print(f"  Skipped (irrelevant): {total_irrelevant}")
    print(f"  Skipped (duplicate):  {total_duplicate}")

    if args.dry_run and total_added > 0:
        print(f"\n  Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
