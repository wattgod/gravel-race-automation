#!/usr/bin/env python3
"""
Batch community research — second-pass search for blogs, race reports,
Reddit threads, and forum posts that the primary AI search misses.

Searches DuckDuckGo for personal race reports, fetches content, then
uses Claude to synthesize community insights into structured dumps.

Usage:
    python scripts/batch_community_research.py --auto 10
    python scripts/batch_community_research.py --slugs red-granite-grinder
    python scripts/batch_community_research.py --auto 20 --dry-run
    python scripts/batch_community_research.py --status
    python scripts/batch_community_research.py --auto 50 --concurrency 3

Pipeline:
    1. batch_research.py              (Kimi/Perplexity)  → research-dumps/{slug}-raw.md
    2. batch_community_research.py    (DuckDuckGo+Claude) → research-dumps/{slug}-community.md  ← THIS
    3. batch_enrich.py                (Claude)            → race-data/{slug}.json enriched

Requires: ANTHROPIC_API_KEY environment variable
"""

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA = PROJECT_ROOT / "race-data"
RESEARCH_DUMPS = PROJECT_ROOT / "research-dumps"
INDEX_PATH = PROJECT_ROOT / "web" / "race-index.json"

# Content limits
MAX_CONTENT_PER_SOURCE = 10_000  # chars
MAX_SOURCES_PER_RACE = 15
HTTP_TIMEOUT = 15  # seconds
MIN_CONTENT_LENGTH = 200  # chars — skip trivially short pages

# Domains to skip — already covered by batch_research.py or noise
SKIP_DOMAINS = {
    # Official/aggregator sites (already in raw research)
    "bikereg.com", "eventbrite.com", "regfox.com", "runsignup.com",
    "usacycling.org", "findarace.com", "battistrada.com",
    "ahotu.com", "cycloworld.cc", "gravelup.earth", "dirtyfreehub.org",
    # Social (not scrapeable or low signal)
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
    "tiktok.com", "pinterest.com", "linkedin.com",
    # Commerce
    "amazon.com", "amzn.to", "ebay.com",
    # URL shorteners
    "bit.ly", "t.co", "tinyurl.com", "goo.gl",
    # Maps / schema
    "maps.google.com", "maps.app.goo.gl", "schema.org", "w3.org",
    # Archive
    "web.archive.org",
    # Search engines
    "google.com", "duckduckgo.com", "bing.com",
    # Ride tracking (not article content)
    "strava.com", "ridewithgps.com", "garmin.com",
}

# Source type classification by domain
DOMAIN_TYPES = {
    "reddit.com": "reddit",
    "old.reddit.com": "reddit",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "forums.mtbr.com": "forum",
    "bikeforums.net": "forum",
    "cyclingtips.com": "media",
    "velonews.com": "media",
    "bikeradar.com": "media",
    "gravelcyclist.com": "media",
    "cxmagazine.com": "media",
    "outsideonline.com": "media",
    "gearjunkie.com": "media",
}


def classify_source(url):
    """Classify a URL as blog, reddit, youtube, forum, or media."""
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    if domain in DOMAIN_TYPES:
        return DOMAIN_TYPES[domain]
    # Forum-like domains
    if "forum" in domain:
        return "forum"
    # Everything else is likely a blog or personal site
    return "blog"


def should_skip_url(url):
    """Check if URL should be skipped (noise/already-covered domains)."""
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    return domain in SKIP_DOMAINS


# ---------------------------------------------------------------------------
# Race-name disambiguation — hard-coded content validation
# ---------------------------------------------------------------------------

# Words that don't help distinguish a race from unrelated content
STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or",
    "race", "gravel", "cycling", "bike", "ride", "event", "series",
    "gran", "fondo", "gran fondo", "mountain", "trail", "mtb",
    "100", "200", "50", "xl", "ultra",
    # Directional / geographic generics
    "mid", "south", "north", "east", "west", "big", "little", "new", "old",
}

# Cycling/gravel context words — at least one must appear for generic race names
CYCLING_CONTEXT = {
    "gravel", "cycling", "bike", "bicycle", "cyclist", "rider", "peloton",
    "paceline", "cyclocross", "pedal", "watts", "ftp", "strava", "garmin",
    "kit", "bibs", "jersey", "chamois", "derailleur", "cassette", "chainring",
    "tubeless", "sealant", "tire", "tyre", "clincher", "wheelset",
    "aid station", "feed zone", "cutoff", "dnf", "dns", "finish line",
    "race report", "race day", "start line", "bib number",
    "gravel road", "singletrack", "doubletrack", "climb", "descent",
    "headwind", "tailwind", "bonk", "cramping", "nutrition",
}


def _extract_distinctive_words(race_name):
    """Extract words from a race name that are distinctive (not stopwords).

    Returns lowercase set of words with len > 1, minus stopwords.
    Keeps short abbreviations like 'sbt', 'grvl' that are distinctive.
    """
    words = re.findall(r"[a-zA-Z]+", race_name.lower())
    return {w for w in words if len(w) > 1 and w not in STOPWORDS}


def _is_generic_name(race_name):
    """Check if a race name is too generic to search without context.

    Generic = fewer than 2 distinctive words after stripping stopwords.
    Examples: "SEVEN", "BADLANDS", "Mid South"
    """
    distinctive = _extract_distinctive_words(race_name)
    return len(distinctive) < 2


def validate_content_relevance(content, race_name, slug):
    """Hard-coded check: does this content actually relate to this race?

    For specific names (e.g., "Belgian Waffle Ride", "Crusher in the Tushar"):
      - Content must mention the race name OR slug words.

    For generic names (e.g., "BADLANDS", "SEVEN", "Mid South"):
      - Content must mention the race name AND at least one cycling context word.

    Returns True if content passes validation.
    """
    content_lower = content.lower()

    # Check 1: Does the content mention the race name?
    name_lower = race_name.lower()
    name_found = name_lower in content_lower

    # Check 2: Do slug-derived words appear?
    slug_words = {w for w in slug.split("-") if len(w) > 3}
    slug_match_count = sum(1 for w in slug_words if w in content_lower)
    slug_found = slug_match_count >= min(2, len(slug_words))  # At least 2 slug words (or all if < 2)

    # Check 3: Does any distinctive name word appear? (word boundary match)
    distinctive = _extract_distinctive_words(race_name)
    distinctive_found = any(
        re.search(r"\b" + re.escape(w) + r"\b", content_lower)
        for w in distinctive
    ) if distinctive else False

    # For generic names, require cycling context
    if _is_generic_name(race_name):
        has_cycling_context = any(term in content_lower for term in CYCLING_CONTEXT)
        # Must have (name OR slug match) AND cycling context
        return (name_found or slug_found or distinctive_found) and has_cycling_context

    # For specific names, name match OR strong slug match is sufficient
    return name_found or slug_found or distinctive_found


# ---------------------------------------------------------------------------
# Rider-level context tagging — hard-coded pattern detection
# ---------------------------------------------------------------------------

# Rider level: "elite", "competitive", "recreational", "unknown"
# These are regex-based, deterministic, no AI involved.

# Elite: pros, sponsored, podium finishers, top placements
_ELITE_PATTERNS = [
    r"\b(?:pro\s+(?:rider|racer|cyclist|field|peloton))",
    r"\b(?:world\s+tour|worldtour|pro\s+continental|pro\s+team)\b",
    r"\b(?:national\s+champ(?:ion)?|world\s+champ(?:ion)?)\b",
    r"\b(?:1st|2nd|3rd)\s+(?:overall|place|general)\b",
    r"\b(?:first|second|third)\s+(?:overall|place|general)\b",
    r"\boverall\s+(?:win(?:ner)?|victory|champion)\b",
    r"\b(?:age\s+group\s+(?:win|1st|champion|victory))\b",
    r"\btop\s+(?:[1-5])\b(?!\s*(?:mph|km|percent|%))",  # top 1-5 but not "top 5 mph"
    # "podium" is elite ONLY when not preceded by "age group" — checked in detect_rider_level()
    r"\bpro\s+race\b",
    r"\b(?:ef\s+education|trek|specialized|cannondale|lidl.trek|visma)\b",  # pro teams
]

# Competitive: strong age-groupers, serious racers with performance data
_COMPETITIVE_PATTERNS = [
    r"\bage\s+group\s+(?:podium|2nd|3rd|top\s+\d)\b",
    r"\b(?:personal\s+best|pb|pr)\b",
    r"\b(?:4\.[0-9]|5\.[0-9])\s*w/kg\b",  # 4.0+ w/kg
    r"\b(?:targeting|aiming\s+for|goal\s+(?:was|of))\s+(?:sub|under)[\s-]?\d",
    r"\b(?:racing|competed|competitive)\b.*\b(?:years?|seasons?)\b",
    r"\bftp\s*(?:of\s+)?(?:3[0-9]{2}|4[0-9]{2})\b",  # FTP 300-499
]

# Recreational: bucket-listers, first-timers, survival-mode riders
_RECREATIONAL_PATTERNS = [
    r"\b(?:bucket\s+list|first\s+(?:gravel|race|century|ultra))\b",
    r"\b(?:just\s+finish|goal\s+(?:was|is)\s+(?:to\s+)?finish)\b",
    r"\b(?:survival\s+mode|hanging\s+on|barely\s+made)\b",
    r"\b(?:back\s+of\s+(?:the\s+)?pack|last\s+(?:group|wave|finisher))\b",
    r"\b(?:time\s+(?:cutoff|limit)|just\s+(?:under|before)\s+(?:the\s+)?cutoff)\b",
    r"\b(?:beginner|newbie|first\s+timer|novice)\b",
    r"\b(?:never\s+(?:done|raced|ridden)\s+(?:a\s+)?(?:gravel|race))\b",
    r"\b(?:walk(?:ed|ing)\s+(?:my|the)\s+bike)\b.*(?:exhausted|bonk|cramp|couldn.t)",
]

# Wattage thresholds (average/NP for races > 4 hours)
# These are rough but deterministic cutoffs
_WATTS_RE = re.compile(
    r"(\d{2,3})\s*(?:w|watts?)\s*(?:avg|average|normalized|np)\b"
    r"|"
    r"(?:avg|average|normalized|np)\s*(?:of\s+|:?\s*)(\d{2,3})\s*(?:w|watts?)\b"
    r"|"
    r"(\d{2,3})\s*(?:w|watts?)\s+(?:normalized|np)\b",
    re.IGNORECASE,
)

# Finish time patterns (HH:MM or "X hours")
_FINISH_TIME_RE = re.compile(
    r"(?:finish(?:ed)?|time|total)\s*(?:of\s+|:?\s*|was\s+)?(\d{1,2}):(\d{2})(?::(\d{2}))?"
    r"|"
    r"(\d{1,2})\s*(?:hours?|hrs?)\s*(?:and\s+)?(?:(\d{1,2})\s*(?:min(?:utes?)?|mins?))?"
    r"|"
    r"(\d{1,2}):(\d{2})\s*(?:finish|total|elapsed)",
    re.IGNORECASE,
)


def detect_rider_level(content):
    """Detect rider performance level from content using hard-coded patterns.

    Returns one of: "elite", "competitive", "recreational", "unknown"

    Priority: elite > competitive > recreational > unknown
    Uses pattern matching + numeric thresholds. No AI.
    """
    content_lower = content.lower()

    # Check pattern matches
    elite_hits = sum(1 for p in _ELITE_PATTERNS if re.search(p, content_lower))
    competitive_hits = sum(1 for p in _COMPETITIVE_PATTERNS if re.search(p, content_lower))
    recreational_hits = sum(1 for p in _RECREATIONAL_PATTERNS if re.search(p, content_lower))

    # Special case: "podium" is elite UNLESS preceded by "age group"
    if re.search(r"\bpodium(?:ed)?\b", content_lower):
        if re.search(r"\bage\s+group\s+podium", content_lower):
            competitive_hits += 1  # age group podium = competitive
        else:
            elite_hits += 1  # standalone podium = elite

    # Check wattage (supplementary signal)
    watts_level = None
    for m in _WATTS_RE.finditer(content):
        w = int(next(g for g in m.groups() if g is not None))
        if w >= 280:
            watts_level = "elite"
        elif w >= 220:
            watts_level = "competitive"
        elif w >= 100:  # sanity floor — below 100W is likely not a race avg
            watts_level = "recreational"

    # Decision logic — deterministic priority
    if elite_hits >= 1:
        return "elite"
    if watts_level == "elite":
        return "elite"
    if competitive_hits >= 1:
        return "competitive"
    if watts_level == "competitive":
        return "competitive"
    if recreational_hits >= 1:
        return "recreational"
    if watts_level == "recreational":
        return "recreational"
    return "unknown"


def tag_sources_with_rider_level(sources):
    """Add rider_level field to each source dict. Mutates in place."""
    for s in sources:
        s["rider_level"] = detect_rider_level(s["content"])


def build_search_queries(race_name):
    """Build targeted queries for community content discovery."""
    return [
        f'"{race_name}" race report blog',
        f'"{race_name}" gravel race rider experience',
        f'site:reddit.com "{race_name}"',
        f'site:youtube.com "{race_name}" gravel',
        f'"{race_name}" race review forum',
    ]


def build_google_queries(race_name):
    """Build Google-specific queries that complement DuckDuckGo.

    Google often surfaces different results — especially personal blogs,
    Strava segments, and niche forums that DDG misses.
    """
    return [
        f'"{race_name}" race report',
        f'"{race_name}" reddit gravel',
        f'"{race_name}" rider review course conditions',
    ]


def ddgs_search(query, max_results=8, retries=2):
    """Run a DuckDuckGo search with retry on transient errors."""
    from ddgs import DDGS

    for attempt in range(retries + 1):
        try:
            return list(DDGS().text(query, max_results=max_results))
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
            else:
                print(f"    DDG search error: {e}")
                return []


def google_search(query, max_results=8, retries=2):
    """Run a Google search via googlesearch-python (no API key needed)."""
    try:
        from googlesearch import search as gsearch
    except ImportError:
        return []

    for attempt in range(retries + 1):
        try:
            results = []
            for url in gsearch(query, num_results=max_results, sleep_interval=2):
                results.append({"href": url, "title": "", "body": ""})
            return results
        except Exception as e:
            if attempt < retries:
                time.sleep(3)
            else:
                print(f"    Google search error: {e}")
                return []


def perplexity_search(race_name, slug="", retries=2):
    """Use Perplexity sonar to find community content DDG/Google miss.

    Perplexity does grounded web search + synthesis. We ask it specifically
    for rider reports, forum threads, and race reviews — then extract the
    cited URLs from its response for our own fetching pipeline.

    Returns list of dicts matching DDG format: {href, title, body}
    """
    import requests as req

    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        return []

    prompt = (
        f'Find personal race reports, Reddit threads, forum posts, and blog entries '
        f'about the "{race_name}" gravel bike race. I need first-person rider '
        f'experiences — course conditions, terrain descriptions, race strategy, '
        f'equipment choices, and community atmosphere. '
        f'Return the URLs of the most relevant sources you find.'
    )

    for attempt in range(retries + 1):
        try:
            resp = req.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar",
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract citations (URLs) from Perplexity response
            citations = data.get("citations", [])
            content = data["choices"][0]["message"]["content"]

            results = []
            # Citations array contains URLs Perplexity found
            for url in citations:
                results.append({"href": url, "title": "", "body": ""})

            # Also extract any URLs from the response text itself
            import re as _re
            for url_match in _re.findall(r'https?://[^\s\)>\]"\']+', content):
                clean_url = url_match.rstrip('.,;:')
                if clean_url not in {r["href"] for r in results}:
                    results.append({"href": clean_url, "title": "", "body": ""})

            return results

        except Exception as e:
            if attempt < retries:
                time.sleep(3)
            else:
                print(f"    Perplexity search error: {e}")
                return []


def fetch_content(url):
    """Fetch and extract text content from a URL. Returns (text, title)."""
    import requests

    # YouTube: don't fetch, we'll use the search snippet
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    if domain in ("youtube.com", "youtu.be"):
        return None, None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        }
        resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
    except Exception:
        return None, None

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        return None, None

    html = resp.text

    # Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    title = re.sub(r"\s+", " ", title)

    # Strip HTML to text (regex-based, no BeautifulSoup needed)
    text = html
    # Remove script/style/nav blocks
    text = re.sub(r"<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode common entities
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) < MIN_CONTENT_LENGTH:
        return None, title

    return text[:MAX_CONTENT_PER_SOURCE], title


def _process_search_results(results, seen_urls, sources, race_name, slug,
                            verbose, dry_run):
    """Process search results: dedup, fetch, validate, append to sources.

    Returns number of rejected results.
    """
    rejected = 0
    for r in results:
        url = r.get("href", r.get("url", ""))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        if should_skip_url(url):
            continue

        source_type = classify_source(url)
        snippet = r.get("body", r.get("snippet", ""))

        # For YouTube, use snippet as content
        if source_type == "youtube":
            if snippet:
                if not validate_content_relevance(snippet, race_name, slug):
                    rejected += 1
                    if verbose:
                        print(f"      REJECTED (off-topic): {url[:60]}")
                    continue
                sources.append({
                    "url": url,
                    "title": r.get("title", ""),
                    "source_type": source_type,
                    "content": snippet,
                    "snippet": snippet,
                })
            continue

        # Fetch full content for non-YouTube sources
        content, page_title = fetch_content(url)
        if content:
            if not validate_content_relevance(content, race_name, slug):
                rejected += 1
                if verbose:
                    print(f"      REJECTED (off-topic): {url[:60]}")
                continue

            sources.append({
                "url": url,
                "title": page_title or r.get("title", ""),
                "source_type": source_type,
                "content": content,
                "snippet": snippet,
            })

        if len(sources) >= MAX_SOURCES_PER_RACE:
            break

    return rejected


def search_and_fetch(race_name, slug="", dry_run=False, delay=3.0, verbose=False):
    """Search DuckDuckGo + Google + Perplexity and fetch community content.

    Three search engines with different strengths:
    - DuckDuckGo: privacy-focused, good for blogs and forums
    - Google: broadest index, catches personal blogs DDG misses
    - Perplexity: AI-grounded search, finds deep Reddit/forum threads

    Returns list of dicts: {url, title, source_type, content, snippet, rider_level}
    """
    seen_urls = set()
    sources = []
    total_rejected = 0

    # --- Pass 1: DuckDuckGo (5 queries) ---
    ddg_queries = build_search_queries(race_name)
    for i, query in enumerate(ddg_queries):
        if dry_run:
            print(f"    [DDG] Query {i+1}: {query}")
            continue

        results = ddgs_search(query, max_results=8)
        if verbose:
            print(f"    [DDG] Query {i+1}: {query} → {len(results)} results")

        total_rejected += _process_search_results(
            results, seen_urls, sources, race_name, slug, verbose, dry_run
        )

        if len(sources) >= MAX_SOURCES_PER_RACE:
            break

        if not dry_run and i < len(ddg_queries) - 1:
            time.sleep(delay)

    # --- Pass 2: Google (3 queries, fills gaps DDG missed) ---
    if len(sources) < MAX_SOURCES_PER_RACE:
        google_queries = build_google_queries(race_name)
        for i, query in enumerate(google_queries):
            if dry_run:
                print(f"    [Google] Query {i+1}: {query}")
                continue

            results = google_search(query, max_results=8)
            new_urls = [r for r in results if r.get("href", "") not in seen_urls]
            if verbose:
                print(f"    [Google] Query {i+1}: {query} → {len(results)} results ({len(new_urls)} new)")

            total_rejected += _process_search_results(
                results, seen_urls, sources, race_name, slug, verbose, dry_run
            )

            if len(sources) >= MAX_SOURCES_PER_RACE:
                break

            if not dry_run and i < len(google_queries) - 1:
                time.sleep(delay)

    # --- Pass 3: Perplexity (1 AI-grounded search, catches deep threads) ---
    if len(sources) < MAX_SOURCES_PER_RACE:
        if dry_run:
            print(f"    [Perplexity] AI search for {race_name}")
        else:
            pplx_results = perplexity_search(race_name, slug=slug)
            new_urls = [r for r in pplx_results if r.get("href", "") not in seen_urls]
            if verbose:
                print(f"    [Perplexity] → {len(pplx_results)} citations ({len(new_urls)} new)")

            total_rejected += _process_search_results(
                pplx_results, seen_urls, sources, race_name, slug, verbose, dry_run
            )

    if total_rejected > 0 and verbose:
        print(f"    Rejected {total_rejected} off-topic sources")

    # Tag rider level on all accepted sources
    tag_sources_with_rider_level(sources)

    return sources


def synthesize_community(race_name, sources):
    """Call Claude to synthesize community content into structured insights."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # Build source block for Claude — includes rider level tag
    source_blocks = []
    for s in sources:
        level = s.get("rider_level", "unknown")
        level_label = {
            "elite": "ELITE (pro/podium/top finisher)",
            "competitive": "COMPETITIVE (strong age-grouper)",
            "recreational": "RECREATIONAL (bucket-lister/first-timer/back-of-pack)",
            "unknown": "UNKNOWN LEVEL",
        }.get(level, "UNKNOWN LEVEL")
        source_blocks.append(
            f"### Source: {s['title']}\n"
            f"URL: {s['url']}\n"
            f"Type: {s['source_type']}\n"
            f"Rider Level: {level_label}\n\n"
            f"{s['content']}\n"
        )
    combined = "\n---\n\n".join(source_blocks)

    prompt = f"""You are analyzing community-sourced content about the gravel/cycling race "{race_name}".

Below are {len(sources)} sources found from blogs, race reports, Reddit threads, forums, and YouTube descriptions. Each source has a RIDER LEVEL tag (ELITE, COMPETITIVE, RECREATIONAL, or UNKNOWN). Extract and organize the most valuable community insights.

SOURCES:
{combined}

---

Create a structured community research dump with these sections. Only include sections where you found real content — skip empty sections entirely. Attribute quotes and insights to their sources.

# {race_name.upper()} — COMMUNITY RESEARCH

## Rider Quotes & Race Reports
(Direct quotes from riders who did the race. For EACH quote, include:
  - The rider's name/handle
  - Their level tag [ELITE], [COMPETITIVE], [RECREATIONAL], or [UNKNOWN]
  - Source URL
Example: **John Smith [COMPETITIVE]:** "Quote here" (source-url.com))

## Equipment & Gear Recommendations
(Tire choices, bike setup, gear that worked/failed — from actual riders.
IMPORTANT: Tag each recommendation with the rider's level. What works for a 250W elite rider may not suit a 150W recreational rider. If a recommendation is level-specific, say so explicitly.)

## Weather Experienced
(Real weather from specific years, not forecasts — attributed to year if known)

## Terrain Details (Rider Perspective)
(Course details that only someone who rode it would know — specific sections, surprises, surface conditions)

## Race Strategy & Pacing
(Pacing advice, nutrition strategy, when the race gets hard, key decision points.
CRITICAL: Tag pacing/nutrition data with rider level. A sub-10-hour elite pacing at 250W and eating 120g carbs/hr is NOT the same advice for a 16-hour finisher. Always note whose strategy this is.)

## DNF Risk Factors
(Common failure modes, sections where people drop, mechanical issues)

## Community Feel & Atmosphere
(Vibe of the event, crowd support, post-race scene, what makes it unique)

## Source URLs
(List all source URLs used, one per line)

RULES:
- Only include information actually present in the sources — do NOT fabricate
- Attribute specific claims to their source using FULL URLs (e.g., https://example.com/post), NOT just domain names
- Use direct quotes where available (with source attribution)
- ALWAYS tag performance-specific advice with rider level: [ELITE], [COMPETITIVE], [RECREATIONAL], or [UNKNOWN]
- When wattage, pacing, or nutrition numbers are mentioned, ALWAYS include the rider's level so readers can calibrate
- If a section would be empty or purely speculative, omit it entirely
- Focus on first-person experiences and specific details, not generic race descriptions
- The ## Source URLs section is MANDATORY — list every source URL used, one per line"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.content[0].text

        # If Claude's output was truncated before Source URLs, append them
        if "## Source URLs" not in result:
            url_block = "\n\n## Source URLs\n\n" + "\n".join(s["url"] for s in sources)
            result += url_block

        return result
    except Exception as e:
        print(f"    Claude API error: {e}")
        return None


def get_community_candidates(n, tier_filters=None, force=False):
    """Find races that need community research, prioritized by tier.

    Priority:
    1. Tier 1 without community dumps
    2. Tier 2 without community dumps
    3. Races with low voice_authenticity or source_diversity
    4. Within each bucket, weakest research_strength first
    """
    candidates = []

    for path in sorted(RACE_DATA.glob("*.json")):
        slug = path.stem
        community_path = RESEARCH_DUMPS / f"{slug}-community.md"
        if community_path.exists() and not force:
            continue  # Already has community research

        # Must have a raw dump (community research is a second pass)
        raw_path = RESEARCH_DUMPS / f"{slug}-raw.md"
        if not raw_path.exists():
            continue

        data = json.loads(path.read_text())
        race = data.get("race", data)
        tier = race.get("gravel_god_rating", {}).get("display_tier",
               race.get("gravel_god_rating", {}).get("tier", 4))

        if tier_filters and tier not in tier_filters:
            continue

        # Get research_strength scores if available
        rs = race.get("research_strength", {})
        overall = rs.get("overall", 50)
        voice = rs.get("dimensions", {}).get("voice_authenticity", {}).get("score", 50)
        diversity = rs.get("dimensions", {}).get("source_diversity", {}).get("score", 50)

        candidates.append({
            "slug": slug,
            "name": race.get("name", slug),
            "tier": tier,
            "overall": overall,
            "voice": voice,
            "diversity": diversity,
        })

    # Sort: tier ascending, then overall ascending (weakest first)
    candidates.sort(key=lambda r: (r["tier"], r["overall"], r["slug"]))
    return candidates[:n]


def community_research_race(race_info, dry_run=False, delay=3.0, verbose=False):
    """Run community research for a single race.

    Returns (success, message, slug).
    """
    slug = race_info["slug"]
    name = race_info["name"]

    if dry_run:
        print(f"  Queries for {name}:")
        search_and_fetch(name, slug=slug, dry_run=True)
        return True, f"Would research: {name} (T{race_info['tier']})", slug

    # Search and fetch (with relevance validation + rider-level tagging)
    sources = search_and_fetch(name, slug=slug, dry_run=False, delay=delay, verbose=verbose)

    if not sources:
        return False, "No community content found", slug

    # Synthesize with Claude
    result = synthesize_community(name, sources)
    if not result or len(result.strip()) < 200:
        return False, f"Synthesis too short ({len(result or '')} chars)", slug

    # Save community dump
    RESEARCH_DUMPS.mkdir(exist_ok=True)
    community_path = RESEARCH_DUMPS / f"{slug}-community.md"

    # Back up existing if present
    if community_path.exists():
        backup = RESEARCH_DUMPS / f"{slug}-community.bak.md"
        backup.write_text(community_path.read_text())

    community_path.write_text(result)
    kb = len(result) / 1024

    source_types = {}
    for s in sources:
        t = s["source_type"]
        source_types[t] = source_types.get(t, 0) + 1
    type_summary = ", ".join(f"{v} {k}" for k, v in sorted(source_types.items()))

    return True, f"Done: {kb:.1f}KB from {len(sources)} sources ({type_summary})", slug


def show_status():
    """Show community research coverage statistics."""
    profiles = list(RACE_DATA.glob("*.json"))
    raw_dumps = list(RESEARCH_DUMPS.glob("*-raw.md"))
    community_dumps = list(RESEARCH_DUMPS.glob("*-community.md"))

    community_slugs = {p.stem.replace("-community", "") for p in community_dumps}
    raw_slugs = {p.stem.replace("-raw", "") for p in raw_dumps}

    # Count by tier
    tier_counts = {}  # tier -> {total, raw, community}
    for f in profiles:
        data = json.loads(f.read_text())
        race = data.get("race", data)
        tier = race.get("gravel_god_rating", {}).get("display_tier",
               race.get("gravel_god_rating", {}).get("tier", 4))
        if tier not in tier_counts:
            tier_counts[tier] = {"total": 0, "raw": 0, "community": 0}
        tier_counts[tier]["total"] += 1
        if f.stem in raw_slugs:
            tier_counts[tier]["raw"] += 1
        if f.stem in community_slugs:
            tier_counts[tier]["community"] += 1

    print("\n=== COMMUNITY RESEARCH STATUS ===\n")
    print(f"{'Tier':<6} {'Profiles':<10} {'Raw Dump':<10} {'Community':<10} {'Gap':<6}")
    print("-" * 42)
    total_profiles = 0
    total_raw = 0
    total_community = 0
    for tier in sorted(tier_counts):
        c = tier_counts[tier]
        gap = c["raw"] - c["community"]
        total_profiles += c["total"]
        total_raw += c["raw"]
        total_community += c["community"]
        print(f"T{tier:<5} {c['total']:<10} {c['raw']:<10} {c['community']:<10} {gap:<6}")
    print("-" * 42)
    total_gap = total_raw - total_community
    print(f"{'Total':<6} {total_profiles:<10} {total_raw:<10} {total_community:<10} {total_gap:<6}")

    print(f"\n--- Pipeline ---")
    print(f"  Step 1: batch_research.py --auto N           → research-dumps/{{slug}}-raw.md")
    print(f"  Step 2: batch_community_research.py --auto N → research-dumps/{{slug}}-community.md")
    print(f"  Step 3: batch_enrich.py --auto N             → race-data/{{slug}}.json enriched")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Batch community research — blogs, race reports, Reddit, forums",
        epilog="Pipeline: batch_research.py → batch_community_research.py → batch_enrich.py"
    )
    parser.add_argument("--auto", type=int, metavar="N",
                        help="Auto-select top N community research candidates")
    parser.add_argument("--slugs", nargs="+",
                        help="Research specific slugs")
    parser.add_argument("--status", action="store_true",
                        help="Show community research coverage")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview search queries without API calls")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="Parallel workers (default: 1)")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="Seconds between DuckDuckGo queries (default: 3)")
    parser.add_argument("--force", action="store_true",
                        help="Re-research even if community dump exists")
    parser.add_argument("--tier", type=int, action="append", dest="tiers",
                        help="Filter by tier (repeatable: --tier 1 --tier 2)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show search details")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    # Check API key (not needed for dry-run)
    if not args.dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    # Build candidate list
    if args.slugs:
        candidates = []
        for slug in args.slugs:
            # Skip if already has community dump (unless --force)
            if not args.force:
                community_path = RESEARCH_DUMPS / f"{slug}-community.md"
                if community_path.exists():
                    print(f"Skipping {slug} — community dump exists (use --force to override)")
                    continue

            path = RACE_DATA / f"{slug}.json"
            if path.exists():
                data = json.loads(path.read_text())
                race = data.get("race", data)
                candidates.append({
                    "slug": slug,
                    "name": race.get("name", slug),
                    "tier": race.get("gravel_god_rating", {}).get("tier", 4),
                    "overall": race.get("research_strength", {}).get("overall", 50),
                    "voice": 50,
                    "diversity": 50,
                })
            else:
                candidates.append({
                    "slug": slug, "name": slug,
                    "tier": 4, "overall": 50,
                    "voice": 50, "diversity": 50,
                })
    elif args.auto:
        candidates = get_community_candidates(args.auto, tier_filters=args.tiers, force=args.force)
        print(f"Auto-selected {len(candidates)} community research candidates")
    else:
        parser.print_help()
        return

    if not candidates:
        print("No candidates found needing community research.")
        return

    label = "DRY RUN - " if args.dry_run else ""
    print(f"\n{label}Community research for {len(candidates)} races\n")

    success = 0
    failed = 0
    skipped = 0

    if args.concurrency > 1 and not args.dry_run:
        # Parallel execution
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {
                pool.submit(
                    community_research_race, c,
                    dry_run=args.dry_run, delay=args.delay, verbose=args.verbose
                ): c
                for c in candidates
            }
            for i, future in enumerate(as_completed(futures), 1):
                race_info = futures[future]
                try:
                    ok, msg, slug = future.result()
                    print(f"[{i}/{len(candidates)}] {slug}... {msg}")
                    if ok:
                        success += 1
                    else:
                        failed += 1
                except Exception as e:
                    print(f"[{i}/{len(candidates)}] {race_info['slug']}... Error: {e}")
                    failed += 1
    else:
        # Sequential execution
        for i, candidate in enumerate(candidates, 1):
            print(f"[{i}/{len(candidates)}] {candidate['slug']}...", end=" ", flush=True)
            ok, msg, slug = community_research_race(
                candidate, dry_run=args.dry_run, delay=args.delay, verbose=args.verbose
            )
            if not args.dry_run:
                print(msg)
            else:
                print()

            if ok:
                success += 1
            else:
                failed += 1

            if not args.dry_run and ok and i < len(candidates):
                time.sleep(args.delay)

    print(f"\nDone: {success} researched, {failed} failed")

    if success > 0 and not args.dry_run:
        print(f"\nNext step — enrich profiles with community data:")
        print(f"  python scripts/batch_enrich.py --auto {success} --delay 3")


if __name__ == "__main__":
    main()
