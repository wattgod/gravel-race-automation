#!/usr/bin/env python3
"""
Deterministic community dump parser.

Extracts structured facts from community research dumps using regex —
no LLM involved. Produces compact fact sheets and per-criterion
data slices for the enrichment prompt.

All community dumps follow a consistent format:
  # RACE NAME — COMMUNITY RESEARCH
  ## Section Header
  **Rider Name [LEVEL]:** "Quote..." (url)

Shared utilities (RE_NO_EVIDENCE, extract_proper_nouns) are defined here
as the single source of truth — imported by enrich_diff.py and
test_enrichment_quality.py.
"""

import re
from pathlib import Path

RESEARCH_DUMPS = Path(__file__).parent.parent / "research-dumps"

# ============================================================
# Section → criterion mapping
# ============================================================

CRITERION_SECTIONS = {
    "logistics":     ["Course Specifications & Logistics", "Rider Quotes & Race Reports"],
    "length":        ["Race Strategy & Pacing", "Rider Quotes & Race Reports"],
    "technicality":  ["Terrain Details (Rider Perspective)", "Terrain Details",
                      "Equipment & Gear Recommendations", "Equipment & Gear",
                      "DNF Risk Factors"],
    "elevation":     ["Terrain Details (Rider Perspective)", "Terrain Details",
                      "Race Strategy & Pacing"],
    "climate":       ["Weather Experienced", "DNF Risk Factors"],
    "altitude":      ["Terrain Details (Rider Perspective)", "Terrain Details"],
    "adventure":     ["Terrain Details (Rider Perspective)", "Terrain Details",
                      "DNF Risk Factors"],
    "prestige":      ["Rider Quotes & Race Reports", "Community Feel & Atmosphere"],
    "race_quality":  ["Rider Quotes & Race Reports", "Community Feel & Atmosphere",
                      "Course Specifications & Logistics"],
    "experience":    ["Rider Quotes & Race Reports", "Community Feel & Atmosphere",
                      "Race Strategy & Pacing"],
    "community":     ["Community Feel & Atmosphere", "Rider Quotes & Race Reports"],
    "field_depth":   ["Rider Quotes & Race Reports", "Race Strategy & Pacing"],
    "value":         ["Community Feel & Atmosphere", "Course Specifications & Logistics"],
    "expenses":      ["Equipment & Gear Recommendations", "Equipment & Gear",
                      "Course Specifications & Logistics"],
}


# URL extraction from community dumps
RE_PAREN_URL = re.compile(r'\(https?://[^\s)]+\)')

# ============================================================
# Shared regex patterns (imported by enrich_diff.py, tests)
# ============================================================

# False uncertainty — used by validate_enrichment() and tests
RE_NO_EVIDENCE = re.compile(
    r'(?:zero|no)\s+(?:rider|evidence|reports?|testimonials?)'
    r'|pure speculation'
    r'|remains a mystery',
    re.IGNORECASE
)

# Proper noun extraction — used by enrich_diff.py and tests
RE_PROPER_NOUN = re.compile(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+')


def extract_proper_nouns(text):
    """Extract proper nouns from text.

    Finds:
    - **Name [LEVEL]:** patterns (rider attribution)
    - Capitalized multi-word sequences (place names, person names)

    This is the single source of truth — imported by enrich_diff.py
    and test_enrichment_quality.py.
    """
    nouns = set()
    # Rider attribution: **Name [LEVEL]:**
    for match in re.finditer(r'\*\*([A-Z][a-zA-Z]+(?: [A-Za-z]+)*)\s*\[', text):
        nouns.add(match.group(1).strip())
    # Capitalized multi-word: "Silver Island Pass", "Bobby Kennedy"
    for match in RE_PROPER_NOUN.finditer(text):
        name = match.group(0)
        if len(name) > 5 and name not in {"The", "This", "That", "These", "Those"}:
            nouns.add(name)
    return nouns


def extract_source_urls(text):
    """Extract unique source URLs from a community dump.

    Community dumps embed source URLs in parentheses after each quote:
      **Rider [LEVEL]:** "Quote..." (https://example.com/article)

    Returns a list of dicts suitable for the race JSON citations array:
      [{"url": "...", "category": "community", "label": "..."}]

    Deduplicates by URL. Generates label from domain + path slug.
    """
    seen = set()
    citations = []

    for match in RE_PAREN_URL.finditer(text):
        url = match.group(0)[1:-1]  # Strip parens
        if url in seen:
            continue
        seen.add(url)

        # Generate label from domain + path
        label = _url_to_label(url)
        citations.append({
            "url": url,
            "category": "community",
            "label": label,
        })

    return citations


def _url_to_label(url):
    """Convert a URL to a human-readable citation label.

    https://keithandlindsey.com/the-salty-lizard-100/ → "keithandlindsey.com: The Salty Lizard 100"
    https://www.gravelcyclist.com/race-reports/foo-bar/ → "gravelcyclist.com: Foo Bar"
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")

    # Get last meaningful path segment
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]
    if path_parts:
        slug = path_parts[-1]
        # Convert slug to title: "the-salty-lizard-100" → "The Salty Lizard 100"
        title = slug.replace("-", " ").replace("_", " ").title()
        # Truncate long titles
        if len(title) > 60:
            title = title[:57] + "..."
        return f"{domain}: {title}"
    return domain


# ============================================================
# Parser-specific regex patterns
# ============================================================

# Line-anchored rider attribution: **Name [LEVEL]:**
# Matches at line start only. Captures everything inside [].
RE_RIDER_LINE = re.compile(
    r'^\*\*(.+?)\s*\[([^\]]+)\]',
    re.MULTILINE
)

# Temperature mentions (must be preceded by word boundary, not part of larger number)
RE_TEMPERATURE = re.compile(
    r'(?<!\d)(\d{2,3})\s*°\s*[Ff]?\b|(?<!\d)(\d{2,3})\s*degrees?\b',
    re.IGNORECASE
)

# Wind speed
RE_WIND = re.compile(r'(\d{1,3})\s*mph\s*(?:wind|gust|crosswind)', re.IGNORECASE)

# Elevation numbers
RE_ELEVATION = re.compile(
    r'([\d,]+)\s*(?:feet|ft|foot)\s*(?:of\s+)?(?:gain|climbing|elevation|vert)',
    re.IGNORECASE
)

# Field size
RE_FIELD_SIZE = re.compile(
    r'(\d{1,5})\s*(?:riders?|racers?|participants?|cyclists?|starters?|finishers?)',
    re.IGNORECASE
)

# PSI specs
RE_PSI = re.compile(r'(\d{1,3}(?:\.\d)?)\s*(?:psi|PSI)', re.IGNORECASE)

# Power data
RE_WATTS = re.compile(r'(\d{2,4})\s*(?:watts?|W)\b')

# Quoted phrases (rider quotes)
RE_QUOTE_SNIPPET = re.compile(r'"([^"]{20,120})"')


# ============================================================
# Rider extraction — structural, not blocklist
# ============================================================

# Words that appear in compound names (de la Cruz, Van der Berg, etc.)
_NAME_PARTICLES = {"de", "la", "le", "del", "van", "von", "di", "el", "al", "da", "do"}

# Last words that are never real surnames — abstract nouns, plurals, descriptors.
# This is a SUFFIX check (only the last word), not a full-name blocklist.
_NON_SURNAME_SUFFIXES = frozenset({
    # Strategy/tactics labels
    "strategy", "dynamics", "formation", "decision", "positioning",
    "management", "considerations", "approach", "overview", "analysis",
    # Race event descriptors (plural and singular)
    "delays", "crossings", "issues", "issue", "factors", "conditions",
    "details", "notes", "note", "recommendations", "challenges", "options",
    "points", "point", "sections", "section", "specifications", "logistics",
    # Equipment/gear labels
    "setup", "prep", "modifications", "configuration", "selection",
    # Generic descriptors
    "performance", "classification", "description", "character",
    "profile", "assessment", "observations", "observed", "tips", "advice",
    "benchmarks", "process", "confusion", "singletrack", "bottleneck",
    "critical", "support",
})


def extract_riders(text):
    """Extract unique rider names with levels.

    Uses line-anchored regex and structural filtering instead of
    a fragile blocklist of header words.

    Handles three community dump attribution patterns:
    - Standard: **Name [LEVEL]:** "Quote"
    - Topic prefix: **Tires - Name [LEVEL]:** (strips prefix)
    - Topic suffix: **Name [LEVEL] on topic:** (already correct)
    """
    riders = {}

    for match in RE_RIDER_LINE.finditer(text):
        raw_name = match.group(1).strip()
        level_text = match.group(2).strip()

        # Skip [UNKNOWN level] — these are topic sub-headers, not riders
        if "level" in level_text.lower():
            continue

        level = level_text.upper()

        # Strip topic prefix from multiple separator styles:
        # "Tires - Nicholas Garbis" → "Nicholas Garbis" (hyphen)
        # "Bike Setup — Joe Goettl" → "Joe Goettl" (em-dash)
        # "Tire Selection:** Steve Tilford" → "Steve Tilford" (colon-bold)
        name = raw_name
        if " - " in name:
            name = name.split(" - ")[-1].strip()
        if " — " in name:
            name = name.split(" — ")[-1].strip()
        if ":**" in name:
            name = name.split(":**")[-1].strip().lstrip("*").strip()
        # Strip trailing separators: "Bike Setup -" → "Bike Setup"
        # (from patterns like **Topic - [LEVEL] Name:** where name is after [])
        name = re.sub(r'\s*[-—]+\s*$', '', name)

        # Skip empty, too short, or too long
        if not name or len(name) < 2 or len(name) > 50:
            continue

        # Skip if starts with digit (e.g. "50km Distance Performance")
        if name[0].isdigit():
            continue

        # Skip if contains year patterns like "2024 Race"
        if re.search(r'\b20\d{2}\b', name):
            continue

        # Skip "Unnamed rider" etc.
        if "unnamed" in name.lower():
            continue

        words = name.split()

        # Skip if > 5 words — real names are 1-4 words, occasionally 5
        # (e.g. "Race Director John Hernandez" = 4 words)
        if len(words) > 5:
            continue

        # Skip if last word is a known non-surname suffix
        if words[-1].lower().rstrip(".,;:)") in _NON_SURNAME_SUFFIXES:
            continue

        # For multi-word names: skip if any word starts with lowercase
        # and isn't a name particle. This catches labels like
        # "Technical Sections as Selection Points" (the "as" gives it away)
        # but allows "Juan de la Cruz", "Oscar van der Berg".
        # Single-word names (usernames like "husterk", "JOM") are allowed
        # regardless of case.
        if len(words) > 1:
            has_bad_lowercase = False
            for w in words:
                if not w.strip(".,;:-'\""):
                    continue
                first_alpha = next((c for c in w if c.isalpha()), None)
                if first_alpha and first_alpha.islower() and w.lower() not in _NAME_PARTICLES:
                    has_bad_lowercase = True
                    break
            if has_bad_lowercase:
                continue

        if name not in riders:
            riders[name] = level

    return riders


# ============================================================
# Section parser
# ============================================================

def parse_sections(text):
    """Split community dump into {section_name: section_text} dict."""
    sections = {}
    current_section = "_header"
    current_lines = []

    for line in text.split("\n"):
        if line.startswith("## "):
            # Save previous section
            if current_lines:
                sections[current_section] = "\n".join(current_lines)
            current_section = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Save last section
    if current_lines:
        sections[current_section] = "\n".join(current_lines)

    return sections


# ============================================================
# Fact extractors
# ============================================================

def extract_terrain_features(text):
    """Extract named terrain features from terrain sections.

    Uses a SKIP set for known generic terms. Not a full blocklist approach —
    the SKIP set targets structural patterns (section headers, sentence starters)
    that are inherent to the markdown format, not race-specific content.
    """
    features = set()

    # Structural noise that appears in every community dump regardless of race
    SKIP = {
        # Sentence starters (appear in every dump)
        "The", "This", "That", "These", "Those", "However", "After",
        "Before", "During", "Around", "About", "Between", "From",
        "Into", "Some", "Most", "Many", "Several", "Other",
        # Section header fragments (from the ## headers)
        "Community Research", "Rider Quotes", "Race Reports",
        "Terrain Details", "Race Strategy", "Equipment Gear",
        "Weather Experienced", "Source URLs", "Key Takeaways",
        "Lessons Learned", "Rider Perspective", "Gear Recommendations",
        "DNF Risk", "Risk Factors", "Course Specifications",
    }

    for match in RE_PROPER_NOUN.finditer(text):
        name = match.group(0)
        if name in SKIP or len(name) < 6:
            continue
        features.add(name)
    return features


def extract_weather(sections):
    """Extract weather facts from Weather Experienced section."""
    weather_section = sections.get("Weather Experienced", "")
    if not weather_section:
        return {}

    facts = {}
    temps = RE_TEMPERATURE.findall(weather_section)
    if temps:
        # Each match has two groups (°F pattern or degrees pattern), take non-empty
        temp_vals = [g1 or g2 for g1, g2 in temps if g1 or g2]
        if temp_vals:
            facts["temperatures"] = [f"{t}°F" for t in temp_vals]

    winds = RE_WIND.findall(weather_section)
    if winds:
        facts["winds"] = [f"{w} mph" for w in winds]

    return facts


def extract_numbers(text):
    """Extract key numbers from text."""
    facts = {}

    elevations = RE_ELEVATION.findall(text)
    if elevations:
        facts["elevation_mentions"] = [e.replace(",", "") for e in elevations]

    field_sizes = RE_FIELD_SIZE.findall(text)
    if field_sizes:
        facts["field_sizes"] = field_sizes

    watts = RE_WATTS.findall(text)
    if watts:
        facts["power_data"] = [f"{w}W" for w in watts]

    psi = RE_PSI.findall(text)
    if psi:
        facts["tire_pressure"] = [f"{p} psi" for p in psi]

    return facts


# Words that signal a vivid, specific quote worth surfacing
_VIVID_SIGNALS = re.compile(
    r'\b(?:'
    # Sensory language
    r'smell|stink|stank|dust|mud|sand|gravel|rock|ice|snow|rain|wind|heat|cold|'
    r'freezing|soaked|burning|sweat|blood|pain|cramp|bonk|'
    # Concrete nouns (body, gear, terrain)
    r'tire|chain|derailleur|wheel|brake|saddle|leg|knee|lung|stomach|'
    r'hill|climb|descent|bridge|river|creek|pass|ridge|canyon|forest|'
    # Sounds and textures
    r'crunch|rattle|howl|scream|grind|chew|spit|crack|snap|'
    # Numbers and specifics
    r'mile\s+\d|mph|feet|hours|minutes|seconds|degrees|°|'
    # Emotional precision (not generic)
    r'terrif|brutal|destroy|wreck|crush|suffer|survive|hostile|angry|'
    r'beautiful|gorgeous|stunning|peaceful|eerie|haunting|bizarre|'
    # Surprise / unexpected detail
    r'bacon|beer|fry\s*bread|taco|pizza|soup|'
    r'bear|cow|cattle|snake|coyote|'
    r'police|protest|burn\s*pile|rescue|evacuat'
    r')\b',
    re.IGNORECASE
)

# Words that signal a generic, uninteresting quote
_GENERIC_SIGNALS = re.compile(
    r'\b(?:'
    r'challenging|amazing|awesome|fantastic|incredible|wonderful|'
    r'great experience|highly recommend|can.t wait|look forward|'
    r'well organized|well run|good event|nice event|fun event|'
    r'beautiful course|great course|nice course'
    r')\b',
    re.IGNORECASE
)


def _score_quote(quote):
    """Score a quote for vividness. Higher = more interesting.

    Scoring:
      +3 per vivid signal (sensory, concrete, specific)
      +2 if contains a number
      +1 per 20 chars of length (longer quotes have more detail)
      -2 per generic signal
      -3 if under 25 chars (too short to be interesting)
    """
    score = 0
    score += len(_VIVID_SIGNALS.findall(quote)) * 3
    if re.search(r'\d', quote):
        score += 2
    score += len(quote) // 20
    score -= len(_GENERIC_SIGNALS.findall(quote)) * 2
    if len(quote) < 25:
        score -= 3
    return score


def extract_key_quotes(text, max_quotes=8):
    """Extract the most vivid, specific rider quotes.

    Only extracts quotes from rider attribution lines (** at line start).
    Scores quotes by vividness (sensory language, concrete nouns, numbers,
    surprise) and returns the highest-scoring ones first.
    """
    candidates = []
    for line in text.split("\n"):
        # Only extract quotes from rider attribution lines
        if not line.startswith("**"):
            continue
        for match in RE_QUOTE_SNIPPET.finditer(line):
            quote = match.group(1).strip()
            # Skip URLs
            if any(skip in quote.lower() for skip in ["http", "www.", ".com"]):
                continue
            candidates.append((quote, _score_quote(quote)))

    # Sort by score descending, return top N
    candidates.sort(key=lambda x: x[1], reverse=True)
    return [q for q, s in candidates[:max_quotes]]


# ============================================================
# Per-criterion data slicing
# ============================================================

def _truncate_at_sentence(text, max_chars):
    """Truncate text at the last sentence boundary before max_chars.

    Falls back to max_chars if no sentence boundary found in first half.
    """
    if len(text) <= max_chars:
        return text
    # Look for sentence-ending punctuation followed by space/newline
    truncated = text[:max_chars]
    # Find last sentence boundary (. or !) followed by space, newline, or end
    last_period = -1
    for i in range(len(truncated) - 1, max_chars // 2, -1):
        if truncated[i] in ".!)" and (i + 1 >= len(truncated) or truncated[i + 1] in " \n\""):
            last_period = i + 1
            break
    if last_period > 0:
        return truncated[:last_period]
    return truncated + "..."


def get_criterion_data(criterion, sections):
    """Get the community dump sections relevant to a specific criterion."""
    relevant_section_names = CRITERION_SECTIONS.get(criterion, [])
    parts = []
    for name in relevant_section_names:
        if name in sections:
            text = sections[name]
            # Cap each section contribution at 1500 chars, sentence-aware
            parts.append(_truncate_at_sentence(text, 1500))
    return "\n".join(parts) if parts else ""


# ============================================================
# Main fact sheet builder
# ============================================================

def build_fact_sheet(slug):
    """Build a compact fact sheet from community dump.

    Returns (fact_sheet_text, sections_dict) or (None, None) if no community dump.
    """
    community_path = RESEARCH_DUMPS / f"{slug}-community.md"
    if not community_path.exists():
        return None, None

    text = community_path.read_text()
    sections = parse_sections(text)

    # Extract all facts
    riders = extract_riders(text)
    terrain_features = extract_terrain_features(
        sections.get("Terrain Details (Rider Perspective)", "") +
        sections.get("Terrain Details", "")
    )
    weather = extract_weather(sections)
    numbers = extract_numbers(text)
    key_quotes = extract_key_quotes(text)

    # Remove rider names from terrain features (people aren't terrain)
    rider_names = set(riders.keys())
    terrain_features -= rider_names
    # Also remove partial rider name matches
    terrain_features = {
        f for f in terrain_features
        if not any(f in rname or rname in f for rname in rider_names)
    }

    # Build compact fact sheet
    lines = ["COMMUNITY FACT SHEET (extracted from rider reports — USE THESE):"]

    if riders:
        rider_list = ", ".join(f"{name} ({level})" for name, level in riders.items())
        lines.append(f"  RIDERS: {rider_list}")

    if terrain_features:
        lines.append(f"  TERRAIN: {', '.join(sorted(terrain_features)[:15])}")

    if weather:
        weather_parts = []
        if "temperatures" in weather:
            weather_parts.append(f"temps: {', '.join(weather['temperatures'][:5])}")
        if "winds" in weather:
            weather_parts.append(f"winds: {', '.join(weather['winds'][:3])}")
        lines.append(f"  WEATHER: {'; '.join(weather_parts)}")

    if numbers.get("field_sizes"):
        lines.append(f"  FIELD SIZE: {', '.join(numbers['field_sizes'][:3])} riders mentioned")

    if numbers.get("elevation_mentions"):
        lines.append(f"  ELEVATION DATA: {', '.join(numbers['elevation_mentions'][:3])} ft mentioned")

    if numbers.get("power_data"):
        lines.append(f"  POWER: {', '.join(numbers['power_data'][:3])}")

    if numbers.get("tire_pressure"):
        lines.append(f"  TIRES: {', '.join(numbers['tire_pressure'][:3])}")

    if key_quotes:
        lines.append("  KEY QUOTES:")
        for q in key_quotes[:5]:
            lines.append(f'    - "{q}"')

    return "\n".join(lines), sections


def build_criterion_hints(sections):
    """Build per-criterion relevant data hints.

    Returns dict of {criterion: relevant_text_snippet}.
    Truncates at sentence boundaries, not mid-sentence.
    """
    if not sections:
        return {}

    hints = {}
    for criterion in CRITERION_SECTIONS:
        data = get_criterion_data(criterion, sections)
        if data:
            hints[criterion] = _truncate_at_sentence(data, 800)
    return hints
