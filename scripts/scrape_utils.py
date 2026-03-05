#!/usr/bin/env python3
"""
scrape_utils.py — Shared utilities for scraping official race websites.

Provides tiered web fetching (fast HTTP → Cloudflare bypass), caching,
and Claude-based structured extraction from scraped HTML.

Shared functions (imported by scrape_official_sites.py, fact_check_profiles.py):
  - fetch_url(url, strategy) — tiered fetching with Scrapling
  - extract_race_facts_via_claude(html, race_name, existing_data) — structured extraction
  - get_cached(url) / set_cached(url, html, status, fetcher) — 7-day HTML cache
  - load_official_sites() — {slug: {url, name, tier}} for all races with HTTP URLs
  - is_cloudflare_blocked(html) — detect Cloudflare challenge pages

Requires: scrapling[fetchers], ANTHROPIC_API_KEY (for extraction only)

Usage:
    from scrape_utils import fetch_url, extract_race_facts_via_claude, load_official_sites
"""

import hashlib
import json
import os
import re
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
SCRAPE_CACHE_DIR = PROJECT_ROOT / "data" / "scrape-cache"
SCRAPE_EXTRACTS_DIR = PROJECT_ROOT / "data" / "scrape-extracts"

CACHE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days

# Cloudflare challenge page markers
CLOUDFLARE_MARKERS = [
    "Just a moment",
    "cf-browser-verification",
    "Checking your browser",
    "challenges.cloudflare.com",
    "Enable JavaScript and cookies to continue",
    "_cf_chl_opt",
]

# Maximum HTML size to send to Claude (chars) — keeps cost low
MAX_HTML_FOR_CLAUDE = 100_000


# ---------------------------------------------------------------------------
# Cache layer
# ---------------------------------------------------------------------------

def _cache_key(url: str) -> str:
    """Generate deterministic cache filename from URL."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def get_cached(url: str) -> dict | None:
    """Load cached scrape result if fresh. Returns dict with html, status, fetcher, timestamp."""
    SCRAPE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRAPE_CACHE_DIR / f"{_cache_key(url)}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    ts = data.get("timestamp", 0)
    if time.time() - ts > CACHE_TTL_SECONDS:
        return None
    return data


def set_cached(url: str, html: str | None, status: int, fetcher: str) -> Path:
    """Write scrape result to cache. Returns cache file path."""
    SCRAPE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRAPE_CACHE_DIR / f"{_cache_key(url)}.json"
    data = {
        "url": url,
        "html": html,
        "status": status,
        "fetcher": fetcher,
        "timestamp": time.time(),
    }
    path.write_text(json.dumps(data, ensure_ascii=False))
    return path


# ---------------------------------------------------------------------------
# Cloudflare detection
# ---------------------------------------------------------------------------

def is_cloudflare_blocked(html: str | None) -> bool:
    """Detect Cloudflare challenge / block pages."""
    if not html:
        return False
    # Only check first 5000 chars — challenge markers are in <head>
    snippet = html[:5000]
    return any(marker in snippet for marker in CLOUDFLARE_MARKERS)


# ---------------------------------------------------------------------------
# Tiered fetching
# ---------------------------------------------------------------------------

def fetch_url(url: str, strategy: str = "auto", timeout: int = 30) -> tuple:
    """Fetch a URL with tiered Scrapling fallback.

    Strategies:
      "fast"    — Fetcher only (plain HTTP, ~0.5s)
      "stealth" — StealthyFetcher only (browser, ~10-60s)
      "auto"    — fast first, stealth if blocked (default)

    Returns (html_text, status_code, fetcher_used) on success,
            (None, status_code, error_msg) on failure.
    """
    from scrapling import Fetcher, StealthyFetcher

    if strategy in ("fast", "auto"):
        try:
            response = Fetcher().get(url, timeout=timeout)
            status = response.status
            html = str(response.html_content) if response.html_content else ""

            if status == 200 and html and not is_cloudflare_blocked(html):
                return html, status, "fetcher"

            if strategy == "fast":
                return (None, status, "cloudflare_blocked") if is_cloudflare_blocked(html) else (None, status, f"http_{status}")
        except Exception as e:
            if strategy == "fast":
                return None, 0, str(e)

    # Stealth fallback
    if strategy in ("stealth", "auto"):
        try:
            response = StealthyFetcher().fetch(url, headless=True, timeout=timeout * 1000)
            status = response.status
            html = str(response.html_content) if response.html_content else ""

            if status == 200 and html and not is_cloudflare_blocked(html):
                return html, status, "stealthy"

            return (None, status, "cloudflare_blocked") if is_cloudflare_blocked(html) else (None, status, f"stealth_http_{status}")
        except Exception as e:
            return None, 0, f"stealth_error: {e}"

    return None, 0, f"unknown_strategy: {strategy}"


# ---------------------------------------------------------------------------
# Load official sites from race data
# ---------------------------------------------------------------------------

def load_official_sites(tier_filters: set | None = None,
                        slug_filter: str | None = None,
                        stale_only: bool = False) -> dict:
    """Load races with valid HTTP official_site URLs.

    Returns {slug: {"url": str, "name": str, "tier": int, "date_specific": str}}.
    """
    result = {}
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        slug = f.stem
        if slug_filter and slug != slug_filter:
            continue

        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        race = data.get("race", data)
        url = race.get("logistics", {}).get("official_site", "")
        if not url or not url.startswith("http"):
            continue

        tier = race.get("gravel_god_rating", {}).get("tier") or \
               race.get("gravel_god_rating", {}).get("display_tier")
        if tier_filters and tier not in tier_filters:
            continue

        date_specific = race.get("vitals", {}).get("date_specific", "")

        if stale_only:
            m = re.match(r"(\d{4})", str(date_specific))
            if not m or int(m.group(1)) >= 2026:
                continue

        name = race.get("display_name", race.get("name", slug))
        result[slug] = {
            "url": url,
            "name": name,
            "tier": tier,
            "date_specific": date_specific,
        }

    return result


# ---------------------------------------------------------------------------
# Claude extraction
# ---------------------------------------------------------------------------

def _truncate_html(html: str) -> str:
    """Truncate HTML to MAX_HTML_FOR_CLAUDE chars, keeping head + main content."""
    if len(html) <= MAX_HTML_FOR_CLAUDE:
        return html

    # Try to find <main> or <article> content
    for tag in ["main", "article", '[role="main"]']:
        pattern = re.compile(
            rf"<{tag}[^>]*>(.*?)</{tag.split('[')[0]}>",
            re.DOTALL | re.IGNORECASE,
        )
        m = pattern.search(html)
        if m and len(m.group(1)) > 500:
            content = m.group(1)
            if len(content) <= MAX_HTML_FOR_CLAUDE:
                return content
            return content[:MAX_HTML_FOR_CLAUDE]

    # Fallback: strip script/style tags and truncate
    cleaned = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<style[^>]*>.*?</style>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    return cleaned[:MAX_HTML_FOR_CLAUDE]


def _build_extraction_prompt(html: str, race_name: str, existing_data: dict) -> str:
    """Build prompt for Claude to extract structured race facts from HTML."""
    existing_summary = json.dumps(existing_data, indent=2) if existing_data else "{}"
    truncated = _truncate_html(html)

    return f"""Extract structured race data from this official website HTML for "{race_name}".

EXISTING PROFILE DATA (for comparison — note what differs):
{existing_summary}

OFFICIAL WEBSITE HTML:
{truncated}

Return ONLY a JSON object with these fields (use null for anything not found):
{{
  "date_2026": "YYYY-MM-DD or Month DD format if found, null if not",
  "distance_mi": number or null,
  "elevation_ft": number or null,
  "registration_status": "open|closed|sold_out|lottery|coming_soon" or null,
  "registration_cost": "$XXX" or null,
  "field_size": "description" or null,
  "start_time": "HH:MM AM/PM" or null,
  "official_site_confirmed": true,
  "location": "City, State/Country" or null,
  "aid_stations": number or description or null,
  "cutoff_time": "description" or null,
  "distances_offered": ["list of distance options"] or null,
  "source_url_title": "page title if visible"
}}

Rules:
- Only include data you can directly see in the HTML. Do not guess.
- Distances: convert km to miles if needed (1 km = 0.621371 mi). Round to nearest integer.
- Elevation: convert meters to feet if needed (1 m = 3.28084 ft). Round to nearest 100.
- For 2026 dates: look for "2026" explicitly. If only a general date pattern visible, set date_2026 to null.
- Return valid JSON only, no explanation."""


def extract_race_facts_via_claude(html: str, race_name: str,
                                  existing_data: dict | None = None) -> dict:
    """Send scraped HTML to Claude for structured extraction.

    Returns dict with extracted fields, or empty dict on failure.
    Requires ANTHROPIC_API_KEY environment variable.
    """
    from youtube_enrich import call_api, parse_json_response

    prompt = _build_extraction_prompt(html, race_name, existing_data or {})
    try:
        response = call_api(prompt)
        return parse_json_response(response)
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Load existing extract
# ---------------------------------------------------------------------------

def load_extract(slug: str) -> dict | None:
    """Load a previously saved scrape extract for a race."""
    path = SCRAPE_EXTRACTS_DIR / f"{slug}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_extract(slug: str, data: dict) -> Path:
    """Save a scrape extract for a race."""
    SCRAPE_EXTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRAPE_EXTRACTS_DIR / f"{slug}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return path
