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
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from race_facts import needs_date_check  # noqa: E402
from season import today  # noqa: E402
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

        if stale_only and not needs_date_check(race):
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
  "next_edition_date": "YYYY-MM-DD of the next edition after {today().isoformat()}, null if not shown",
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
- next_edition_date: only a date the page states, with its year, that falls after {today().isoformat()}. A past edition's date or a general pattern ("first Saturday in June") is null.
- elevation_ft is total climbing for the main route. A summit altitude, or climbing for a side event, is not elevation; use null.
- Return valid JSON only, no explanation."""


# Month names as organizer sites write them (en, fr, it, es, de, nl, pt).
_MONTH_WORDS = {
    1: ["january", "jan", "janvier", "gennaio", "enero", "januar", "januari", "janeiro"],
    2: ["february", "feb", "février", "fevrier", "febbraio", "febrero", "februar", "februari", "fevereiro"],
    3: ["march", "mar", "mars", "marzo", "märz", "maerz", "maart", "março", "marco"],
    4: ["april", "apr", "avril", "aprile", "abril"],
    5: ["may", "mai", "maggio", "mayo", "mei", "maio"],
    6: ["june", "jun", "juin", "giugno", "junio", "juni", "junho"],
    7: ["july", "jul", "juillet", "luglio", "julio", "juli", "julho"],
    8: ["august", "aug", "août", "aout", "agosto", "augustus"],
    9: ["september", "sep", "sept", "septembre", "settembre", "septiembre", "setembro"],
    10: ["october", "oct", "octobre", "ottobre", "octubre", "oktober", "outubro"],
    11: ["november", "nov", "novembre", "noviembre", "novembro"],
    12: ["december", "dec", "décembre", "decembre", "dicembre", "diciembre", "dezember", "dezembro"],
}


def date_is_on_page(html: str, iso_date) -> bool:
    """True when the page itself shows this day, month and year as one date.

    A model can project last year's date forward and return a plausible date
    the organizer never published. Only a date written on the page is kept.
    The year must belong to the date: "7 March 2026. See you in 2027!" does
    not show 7 March 2027.
    """
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(iso_date or "").strip())
    if not m or not html:
        return False
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        date(year, month, day)
    except ValueError:
        return False
    text = re.sub(r"<[^>]+>", " ", html).lower()
    text = re.sub(r"\s+", " ", text)

    sep = r"\s?[-/.]\s?"
    d, mo = rf"0?{day}", rf"0?{month}"
    numeric = [
        rf"(?<!\d){year}{sep}{mo}{sep}{d}(?!\d)",
        rf"(?<!\d){d}{sep}{mo}{sep}{year}(?!\d)",
        rf"(?<!\d){mo}{sep}{d}{sep}{year}(?!\d)",
    ]
    if any(re.search(p, text) for p in numeric):
        return True

    words = "|".join(re.escape(w) for w in _MONTH_WORDS[month])
    day_first = rf"(?<!\d){d}(?:st|nd|rd|th|er|\.|º)?(?:\s(?:and|et|e|y|und|en|[-–&])\s?\d{{1,2}})?\s(?:de\s|of\s)?(?:{words})\b"
    month_first = rf"\b(?:{words})\.?\s(?:\d{{1,2}}(?:st|nd|rd|th)?\s?(?:and|[-–&,])\s?)?{d}(?!\d)"
    for match in re.finditer(rf"{day_first}|{month_first}", text):
        # The first year written after the date (or the one right before it) is the date's year.
        after = re.search(r"(?<!\d)(\d{4})(?!\d)", text[match.end(): match.end() + 16])
        if after:
            if int(after.group(1)) == year:
                return True
            continue
        before = re.search(r"(?<!\d)(\d{4})\W{1,3}$", text[max(0, match.start() - 8): match.start()])
        if before and int(before.group(1)) == year:
            return True
    return False


EXTRACTORS = ("claude", "inkling")


def default_extractor() -> str:
    """The extractor named by SCRAPE_EXTRACTOR, or "claude" when unset or unknown."""
    chosen = os.environ.get("SCRAPE_EXTRACTOR", "").strip().lower()
    return chosen if chosen in EXTRACTORS else "claude"


def extract_race_facts(html: str, race_name: str, existing_data: dict | None = None,
                       extractor: str = "claude") -> dict:
    """Extract structured race facts from official-site HTML.

    extractor "claude" uses Claude Sonnet (ANTHROPIC_API_KEY); "inkling" uses
    the cheap model in cheap_llm.py (OPENROUTER_API_KEY). The page is public,
    so either provider may read it.

    Returns the extracted fields plus "extraction_model" (and
    "extraction_cost_usd" for the cheap model), or {"error": ...}.
    """
    if extractor not in EXTRACTORS:
        return {"error": f"unknown extractor: {extractor}"}

    from youtube_enrich import parse_json_response

    prompt = _build_extraction_prompt(html, race_name, existing_data or {})
    cost_usd = None
    try:
        if extractor == "inkling":
            from cheap_llm import call_cheap_llm_with_usage
            # Reasoning tokens share the output cap: at the 2,000 default, half of
            # a 30-page sample was cut off before any JSON appeared.
            response, usage = call_cheap_llm_with_usage(
                prompt, script="scrape_official_sites",
                max_tokens=8000, reasoning_effort="low")
            model = usage.get("model")
            cost_usd = usage.get("cost_usd")
        else:
            from youtube_enrich import call_api
            response = call_api(prompt)
            model = "claude-sonnet-4-20250514"
        facts = parse_json_response(response)
    except Exception as e:
        return {"error": str(e)}

    if not isinstance(facts, dict):
        return {"error": "extraction did not return a JSON object"}
    if not facts:
        # An empty object would be saved as a successful extract and replace real facts.
        return {"error": "extraction returned an empty JSON object"}

    # Keep a date only when the page shows it; park anything else for a person.
    claimed = facts.get("next_edition_date")
    if claimed and not date_is_on_page(html, claimed):
        facts["next_edition_date"] = None
        facts["unverified_date"] = claimed
    facts["extraction_model"] = model
    if cost_usd is not None:
        facts["extraction_cost_usd"] = cost_usd
    return facts


def extract_race_facts_via_claude(html: str, race_name: str,
                                  existing_data: dict | None = None) -> dict:
    """Extract race facts with Claude. Kept for existing callers."""
    return extract_race_facts(html, race_name, existing_data, extractor="claude")


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


def next_edition_date(extract: dict | None) -> str | None:
    """The scraped next-edition date; reads extracts saved before the key
    was renamed from ``date_2026``."""
    extract = extract or {}
    return extract.get("next_edition_date") or extract.get("date_2026")
