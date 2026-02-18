#!/usr/bin/env python3
"""
Batch profile enrichment — adds biased_opinion_ratings explanations
to thin profiles using existing research dumps.

Reads existing profile + research dump, calls Claude API to generate
per-criterion explanations in Matti voice, merges result back.

Usage:
    python scripts/batch_enrich.py --auto 10        # Enrich top 10 priority
    python scripts/batch_enrich.py --slugs unbound-200 mid-south  # Specific races
    python scripts/batch_enrich.py --dry-run --auto 5  # Preview without writing
    python scripts/batch_enrich.py --auto 50 --delay 5 # Batch with 5s delay

Requires: ANTHROPIC_API_KEY environment variable
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

RACE_DATA = Path(__file__).parent.parent / "race-data"
RESEARCH_DUMPS = Path(__file__).parent.parent / "research-dumps"
BRIEFS = Path(__file__).parent.parent / "briefs"
VOICE_GUIDE = Path(__file__).parent.parent / "skills" / "voice_guide.md"
SNAPSHOTS = Path(__file__).parent.parent / "data" / "enrichment-snapshots"

SCORE_COMPONENTS = [
    'logistics', 'length', 'technicality', 'elevation', 'climate',
    'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
    'community', 'field_depth', 'value', 'expenses'
]

# Add parent dir for triage import
sys.path.insert(0, str(Path(__file__).parent))

from community_parser import build_fact_sheet, build_criterion_hints, RE_NO_EVIDENCE
from quality_gates import check_slop_phrases


def load_voice_guide():
    """Load Matti voice guidelines."""
    if VOICE_GUIDE.exists():
        return VOICE_GUIDE.read_text()
    return "Direct, honest, no fluff. Matti voice: peer-to-peer, specific, dark humor."


def save_snapshot(slug, race):
    """Save current biased_opinion_ratings to snapshot before re-enrichment."""
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    bor = race.get("biased_opinion_ratings", {})
    if not bor:
        return
    snapshot_path = SNAPSHOTS / f"{slug}-pre.json"
    snapshot_path.write_text(json.dumps(bor, indent=2, ensure_ascii=False) + "\n")


def get_force_candidates(n, min_research_kb=3.0):
    """Get races that have community dumps but were enriched before the dump existed.

    For --force --auto: finds already-complete profiles where the community dump
    was created after the profile was last modified.
    """
    candidates = []

    for path in sorted(RACE_DATA.glob("*.json")):
        slug = path.stem
        community_path = RESEARCH_DUMPS / f"{slug}-community.md"
        if not community_path.exists():
            continue
        community_kb = community_path.stat().st_size / 1024
        if community_kb < min_research_kb:
            continue

        data = json.loads(path.read_text())
        race = data.get("race", data)

        # Only consider already-complete profiles
        bor = race.get("biased_opinion_ratings", {})
        explained = sum(1 for k in SCORE_COMPONENTS
                        if isinstance(bor.get(k), dict) and bor[k].get("explanation", "").strip())
        if explained < 14:
            continue

        # Check if community dump is newer than profile
        profile_mtime = path.stat().st_mtime
        community_mtime = community_path.stat().st_mtime
        if community_mtime > profile_mtime:
            tier = race.get("gravel_god_rating", {}).get("tier", 4)
            candidates.append({
                "slug": slug,
                "tier": tier,
                "community_kb": community_kb,
            })

    # T1 first, then bigger community dumps
    candidates.sort(key=lambda r: (r["tier"], -r["community_kb"]))
    return [r["slug"] for r in candidates[:n]]


def get_enrichment_candidates(n, min_research_kb=5.0):
    """Get top N enrichment candidates.

    Finds profiles that:
    1. Have a substantial research dump (>5KB by default)
    2. Need biased_opinion_ratings enrichment (<7 explanations)

    Sorted by tier (T1 first) then research dump size.
    """
    candidates = []

    for path in sorted(RACE_DATA.glob("*.json")):
        slug = path.stem
        dump_path = RESEARCH_DUMPS / f"{slug}-raw.md"
        if not dump_path.exists():
            continue
        dump_kb = dump_path.stat().st_size / 1024
        if dump_kb < min_research_kb:
            continue

        data = json.loads(path.read_text())
        race = data.get("race", data)
        if not needs_enrichment(race):
            continue

        tier = race.get("gravel_god_rating", {}).get("tier", 4)
        prestige = race.get("gravel_god_rating", {}).get("prestige", 0)
        candidates.append({
            "slug": slug,
            "tier": tier,
            "prestige": prestige,
            "research_kb": dump_kb,
        })

    # T1 first, then T2, etc. Within tier, bigger research = better.
    candidates.sort(key=lambda r: (-r["tier"], -r["research_kb"]))
    candidates.sort(key=lambda r: r["tier"])
    return [r["slug"] for r in candidates[:n]]


def load_research(slug):
    """Load research dump(s) or brief for a slug."""
    parts = []
    dump = RESEARCH_DUMPS / f"{slug}-raw.md"
    if dump.exists():
        parts.append(dump.read_text())
    community = RESEARCH_DUMPS / f"{slug}-community.md"
    if community.exists():
        parts.append(community.read_text())
    if parts:
        return "\n\n---\n\n".join(parts)
    brief = BRIEFS / f"{slug}-brief.md"
    if brief.exists():
        return brief.read_text()
    return None


def needs_enrichment(race):
    """Check if profile needs biased_opinion_ratings enrichment."""
    bor = race.get("biased_opinion_ratings", {})
    if not bor or not isinstance(bor, dict):
        return True
    # Check if any entry has a real explanation
    explained = sum(1 for v in bor.values()
                    if isinstance(v, dict) and v.get("explanation", "").strip())
    return explained < 7


def needs_completion(race):
    """Check if profile has partial enrichment (7-13 explanations) needing completion."""
    bor = race.get("biased_opinion_ratings", {})
    if not bor or not isinstance(bor, dict):
        return False
    explained = sum(1 for k in SCORE_COMPONENTS
                    if isinstance(bor.get(k), dict) and bor[k].get("explanation", "").strip())
    return 7 <= explained < 14


def get_missing_criteria(race):
    """Return list of criteria missing explanations."""
    bor = race.get("biased_opinion_ratings", {})
    missing = []
    for k in SCORE_COMPONENTS:
        entry = bor.get(k)
        if not isinstance(entry, dict) or not entry.get("explanation", "").strip():
            missing.append(k)
    return missing


def build_enrichment_prompt(race, research_text, voice_guide):
    """Build the API prompt for enrichment."""
    name = race.get("name", "Unknown")
    rating = race.get("gravel_god_rating", {})
    scores = {k: rating.get(k, 3) for k in SCORE_COMPONENTS}
    location = race.get("vitals", {}).get("location", "Unknown")
    distance = race.get("vitals", {}).get("distance_mi", "?")
    elevation = race.get("vitals", {}).get("elevation_ft", "?")

    scores_block = "\n".join(f"  - {k}: {v}/5" for k, v in scores.items())

    return f"""You are writing biased_opinion_ratings for the Gravel God cycling race database.

RACE: {name}
LOCATION: {location}
DISTANCE: {distance} mi | ELEVATION: {elevation} ft

EXISTING SCORES (1-5 each):
{scores_block}

VOICE GUIDE (write in this voice):
{voice_guide[:800]}

RESEARCH DATA:
{research_text[:30000]}

---

For EACH of the 14 scoring criteria below, write a 2-4 sentence explanation justifying the score. Use specific details from the research — real place names, real numbers, real rider quotes. No generic filler.

Output ONLY valid JSON in this exact format:
{{
  "prestige": {{
    "score": {scores.get('prestige', 3)},
    "explanation": "..."
  }},
  "race_quality": {{
    "score": {scores.get('race_quality', 3)},
    "explanation": "..."
  }},
  "experience": {{
    "score": {scores.get('experience', 3)},
    "explanation": "..."
  }},
  "community": {{
    "score": {scores.get('community', 3)},
    "explanation": "..."
  }},
  "field_depth": {{
    "score": {scores.get('field_depth', 3)},
    "explanation": "..."
  }},
  "value": {{
    "score": {scores.get('value', 3)},
    "explanation": "..."
  }},
  "expenses": {{
    "score": {scores.get('expenses', 3)},
    "explanation": "..."
  }},
  "length": {{
    "score": {scores.get('length', 3)},
    "explanation": "..."
  }},
  "technicality": {{
    "score": {scores.get('technicality', 3)},
    "explanation": "..."
  }},
  "elevation": {{
    "score": {scores.get('elevation', 3)},
    "explanation": "..."
  }},
  "climate": {{
    "score": {scores.get('climate', 3)},
    "explanation": "..."
  }},
  "altitude": {{
    "score": {scores.get('altitude', 3)},
    "explanation": "..."
  }},
  "logistics": {{
    "score": {scores.get('logistics', 3)},
    "explanation": "..."
  }},
  "adventure": {{
    "score": {scores.get('adventure', 3)},
    "explanation": "..."
  }}
}}

Rules:
- Keep the existing scores — don't change them
- Each explanation: 2-4 sentences, specific, Matti voice
- Reference specific course features, weather data, logistics details from research
- No generic filler ("amazing experience", "world-class")
- If research lacks detail for a criterion, say what you know honestly
- Output ONLY the JSON object, no markdown, no code blocks"""


def build_re_enrichment_prompt(race, research_text, voice_guide, slug=None):
    """Build API prompt for re-enrichment with fact sheet + per-criterion hints."""
    name = race.get("name", "Unknown")
    rating = race.get("gravel_god_rating", {})
    scores = {k: rating.get(k, 3) for k in SCORE_COMPONENTS}
    location = race.get("vitals", {}).get("location", "Unknown")
    distance = race.get("vitals", {}).get("distance_mi", "?")
    elevation = race.get("vitals", {}).get("elevation_ft", "?")

    # Compute dynamic max length so prompt can tell model the constraint
    community_path = RESEARCH_DUMPS / f"{slug}-community.md" if slug else None
    if community_path and community_path.exists():
        community_kb = community_path.stat().st_size / 1024
    else:
        community_kb = 0
    if community_kb < 5:
        max_explanation_len = 300
    elif community_kb < 10:
        max_explanation_len = 350
    else:
        max_explanation_len = 600

    bor = race.get("biased_opinion_ratings", {})

    scores_block = "\n".join(f"  - {k}: {v}/5" for k, v in scores.items())

    old_explanations = "\n".join(
        f"  {k}: \"{bor[k].get('explanation', '')}\""
        for k in SCORE_COMPONENTS
        if isinstance(bor.get(k), dict) and bor[k].get("explanation", "").strip()
    )

    # Build deterministic fact sheet + per-criterion hints
    fact_sheet_block = ""
    criterion_hints_block = ""
    if slug:
        fact_sheet, sections = build_fact_sheet(slug)
        if fact_sheet:
            fact_sheet_block = f"\n{fact_sheet}\n"
            hints = build_criterion_hints(sections)
            if hints:
                hint_parts = []
                for k in SCORE_COMPONENTS:
                    if k in hints and hints[k].strip():
                        hint_parts.append(f"  [{k}] {hints[k][:600]}")
                if hint_parts:
                    criterion_hints_block = (
                        "\nPER-CRITERION RELEVANT DATA (use these facts for each criterion):\n" +
                        "\n".join(hint_parts) + "\n"
                    )

    json_template = ",\n  ".join(
        f'"{k}": {{\n    "score": {scores.get(k, 3)},\n    "explanation": "..."\n  }}'
        for k in SCORE_COMPONENTS
    )

    return f"""You are RE-WRITING biased_opinion_ratings for the Gravel God cycling race database.

RACE: {name}
LOCATION: {location}
DISTANCE: {distance} mi | ELEVATION: {elevation} ft

EXISTING SCORES (1-5 each):
{scores_block}
{fact_sheet_block}
PREVIOUS EXPLANATIONS (written BEFORE community data existed — improve these):
{old_explanations}
{criterion_hints_block}
RESEARCH DATA (includes community dumps with rider reports, terrain details, race strategy):
{research_text[:30000]}

---

You are re-enriching these explanations because NEW community data (rider reports, race recaps, quotes) is now available that wasn't before. Your job:

1. KEEP everything good from the previous explanation (specific details, accurate claims)
2. REPLACE vague claims ("zero rider reports", "no evidence", "pure speculation") with specifics from the COMMUNITY FACT SHEET and research data above
3. ADD word-for-word quotes from riders — the more memorable, specific, and telling the better
4. NEVER fabricate section names, trail names, or rider quotes — only use what's in the research
5. Each explanation: 2-3 sentences. If the research data is thin, 1-2 sentences is better than padding.
   HARD LIMIT: Each explanation must be {max_explanation_len} characters or fewer ({community_kb:.0f}KB community dump).
   {"Short, factual statements only. One sentence per explanation is fine." if max_explanation_len <= 200 else ""}

VOICE AND TONE:
- Professional, sober, direct. Not stuffy — but not performing either.
- Let the quotes and facts carry the weight. Your job is to frame them, not upstage them.
- Droll is the ceiling. If there's a writerly reveal, it earns itself from the facts.
  Example of droll done right: "Bobby Kennedy describes the mile 81 climb as an 'unswitchbacked dirt bike trail.' It earns that description."
  Example of trying too hard: "The strongest riders are probably doing real races that weekend."
- Do NOT end explanations with a zinger, punchline, or snarky dismissal.
- Do NOT editorialize beyond what the data supports. If data is thin, be brief.

QUOTE RULES:
- Prefer direct rider quotes over your own paraphrasing. A quote in their words beats your summary.
- Every rider name you mention MUST be paired with something specific they said or did.
  GOOD: "Bobby Kennedy describes 'riding on the moon' through volcanic moondust terrain."
  BAD: "Riders like Josh Spector and Coach Dandelion gather annually in tiny Laona." (name-stuffing — names without substance)
- If a rider said something vivid, use their exact words in quotes. That's the whole point.
- Prioritize quotes with sensory detail, concrete specifics, or surprise. A quote about 'chains chewed,
  derailleurs gargled and spat' is worth ten quotes about 'great event, well organized.'
- If a rider only said generic things ("challenging course", "great experience"), don't quote them.
  Paraphrase briefly or skip. Only quote what's worth reading.

DISTINCT MATERIAL PER CRITERION:
- Each of the 14 criteria MUST use different supporting evidence.
- Do NOT reuse the same quote, anecdote, or detail across multiple criteria.
  Example: if Bobby Wintle hugs every finisher, that goes in ONE criterion. If you cite Bobby Wintle
  in another criterion, use a DIFFERENT fact — his route development, his cancellation handling, his
  decade of organizing. Not the hug again.
- Same rule for terrain features: if you cite Bovine Bypass in adventure, don't cite it again in value.
  Find different course features for different criteria.
- You CAN mention a rider in multiple criteria — just use different facts about them each time.
- When data is thin for a criterion, write a short honest assessment. Two sentences with no data beats four sentences of padding.

BANNED PATTERNS:
- Never use "legitimate", "genuine", or "real" as qualifiers. They assert specificity without providing it. Delete them.
- Never use "nobody's traveling from [place] for it" or equivalent dismissal punchlines.
- Never use "if [X] affects you here, [activity] isn't your sport" or equivalent snark closers.
- Never use "staying awake driving there" or similar bored-traveler jokes.
- Never use "bragging rights and total destruction" or similar overwrought contrast pairs.
- Never pad an explanation when data is missing. If there's no pricing data, one sentence: "No pricing data available." Stop there.
- Never use "not exactly [impressive thing]" as a formula. Just state what it IS.
- Never end an explanation with a punchline, zinger, or snarky dismissal. End on a fact or a quiet observation.

Output ONLY valid JSON:
{{
  {json_template}
}}

Rules:
- Keep the existing scores — don't change them
- Beat the previous explanation on every criterion — more specific, more community-sourced
- You MUST use rider names and terrain features from the COMMUNITY FACT SHEET
- Reference specific rider names, course features, weather data from the research
- No generic filler ("amazing experience", "world-class", "the fact that")
- No fake uncertainty ("zero rider reports") when the FACT SHEET lists real riders
- Output ONLY the JSON object, no markdown, no code blocks"""


def build_completion_prompt(race, research_text, voice_guide, missing_criteria):
    """Build API prompt for completing partial enrichment (v1 → full)."""
    name = race.get("name", "Unknown")
    rating = race.get("gravel_god_rating", {})
    location = race.get("vitals", {}).get("location", "Unknown")
    distance = race.get("vitals", {}).get("distance_mi", "?")
    elevation = race.get("vitals", {}).get("elevation_ft", "?")

    scores_block = "\n".join(f"  - {k}: {rating.get(k, 3)}/5" for k in missing_criteria)

    json_template = ",\n  ".join(
        f'"{k}": {{\n    "score": {rating.get(k, 3)},\n    "explanation": "..."\n  }}'
        for k in missing_criteria
    )

    return f"""You are writing biased_opinion_ratings for the Gravel God cycling race database.

RACE: {name}
LOCATION: {location}
DISTANCE: {distance} mi | ELEVATION: {elevation} ft

This profile already has explanations for some criteria. You are writing ONLY the missing ones listed below.

CRITERIA TO WRITE (with existing scores):
{scores_block}

VOICE GUIDE (write in this voice):
{voice_guide[:800]}

RESEARCH DATA:
{research_text[:30000]}

---

For EACH criterion listed above, write a 2-4 sentence explanation justifying the score. Use specific details from the research — real place names, real numbers, real rider quotes. No generic filler.

Output ONLY valid JSON in this exact format:
{{
  {json_template}
}}

Rules:
- Keep the existing scores — don't change them
- Each explanation: 2-4 sentences, specific, Matti voice
- Reference specific course features, weather data, logistics details from research
- No generic filler ("amazing experience", "world-class")
- If research lacks detail for a criterion, say what you know honestly
- Output ONLY the JSON object, no markdown, no code blocks"""


def call_api(prompt, max_retries=3, retry_delay=30):
    """Call Claude API with retry logic."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            if attempt < max_retries - 1:
                wait = retry_delay * (attempt + 1)
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


def parse_json_response(text):
    """Parse JSON from API response, handling code blocks."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


_RE_QUOTED = re.compile(r"""['"\u201c\u201d]([^'"\u201c\u201d]{8,}?)['"\u201c\u201d]""")
_RE_NO_DATA_PADDING = re.compile(
    r"(?:No|Zero|no|zero)\s+(?:pricing|entry fee|cost|price|fee)\s+(?:data|info|information)\s+(?:available|found|published)",
    re.IGNORECASE,
)

MAX_QUOTE_REUSE = 2  # A quoted phrase may appear in at most 2 criteria


_RE_NAME_PHRASE = re.compile(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+')


def _find_repeated_quotes(enriched):
    """Find quoted phrases that appear in 3+ different criteria.

    Returns dict mapping the repeated phrase to the list of criteria it appears in.
    """
    quote_to_criteria = {}
    for key in SCORE_COMPONENTS:
        entry = enriched.get(key)
        if not isinstance(entry, dict):
            continue
        explanation = entry.get("explanation", "")
        quotes = _RE_QUOTED.findall(explanation)
        for q in quotes:
            q_lower = q.strip().lower()
            if len(q_lower) < 8:
                continue
            quote_to_criteria.setdefault(q_lower, []).append(key)

    return {q: criteria for q, criteria in quote_to_criteria.items()
            if len(criteria) > MAX_QUOTE_REUSE}


def _find_overused_names(enriched):
    """Find proper names that appear in 6+ different criteria, OR names that
    appear in 4+ criteria with the same action/detail repeated.

    A name in 5 criteria out of 14 is natural for a dominant source (~35%).
    6+ means the model is leaning on one source. But even at 4+, repeating
    the SAME detail (e.g. "hugs every finisher" in 4 criteria) is a problem.

    Returns dict mapping the name to the list of criteria it appears in.
    """
    name_to_criteria = {}
    name_to_contexts = {}  # name -> {criterion: 8-word window around name}
    for key in SCORE_COMPONENTS:
        entry = enriched.get(key)
        if not isinstance(entry, dict):
            continue
        explanation = entry.get("explanation", "")
        names = _RE_NAME_PHRASE.findall(explanation)
        for name in names:
            name_to_criteria.setdefault(name, []).append(key)
            # Extract 8-word context window around the name
            idx = explanation.find(name)
            if idx >= 0:
                words_after = explanation[idx + len(name):].split()[:8]
                context = " ".join(words_after).lower().strip(".,;:—-'\"")
                name_to_contexts.setdefault(name, {})[key] = context

    result = {}
    for name, criteria in name_to_criteria.items():
        if len(criteria) >= 6:
            # Hard threshold: 6+ is always flagged
            result[name] = criteria
        elif len(criteria) >= 4:
            # Soft threshold: 4-5 only flagged if same context repeats
            contexts = name_to_contexts.get(name, {})
            context_values = list(contexts.values())
            # Check if any two contexts share 3+ words
            for i, c1 in enumerate(context_values):
                c1_words = set(c1.split())
                for c2 in context_values[i + 1:]:
                    c2_words = set(c2.split())
                    if len(c1_words & c2_words) >= 3:
                        result[name] = criteria
                        break
                if name in result:
                    break

    return result


def _check_no_data_padding(explanation):
    """Flag explanations that say 'no data available' then pad with filler.

    Returns True if the explanation has a no-data statement followed by 40+
    more characters of padding.
    """
    match = _RE_NO_DATA_PADDING.search(explanation)
    if not match:
        return False
    # Check how much text follows the no-data statement
    remaining = explanation[match.end():].strip()
    return len(remaining) > 40


def only_length_issue(problems):
    """Return True if every problem in the list is a 'too long' length issue."""
    return problems and all("too long" in p for p in problems)


def validate_enrichment(slug, enriched, race, force=False):
    """Post-enrichment quality gate. Returns (passed, issues, fixed_enriched, kept_old).

    Checks each explanation for:
    - Score preservation (hard reject)
    - Slop phrases (flag)
    - False uncertainty when community data exists (flag)
    - Length bounds 50-600 chars (flag)
    - No-data padding (flag)

    Cross-explanation checks:
    - Repeated quotes across 3+ criteria (flag all affected criteria)

    For force re-enrichment: on flagged criteria, keeps old explanation.
    """
    rating = race.get("gravel_god_rating", {})
    old_bor = race.get("biased_opinion_ratings", {})
    community_path = RESEARCH_DUMPS / f"{slug}-community.md"
    has_community = community_path.exists()

    issues = []
    kept_old = []

    # Dynamic max length based on community dump richness
    community_kb = community_path.stat().st_size / 1024 if has_community else 0
    if community_kb < 5:
        max_explanation_len = 300
    elif community_kb < 10:
        max_explanation_len = 350
    else:
        max_explanation_len = 600

    # Cross-explanation: detect repeated quotes and overused names
    repeated = _find_repeated_quotes(enriched)
    overused = _find_overused_names(enriched)
    repeat_flagged_criteria = set()
    for quote, criteria in repeated.items():
        for c in criteria:
            repeat_flagged_criteria.add(c)
    overuse_flagged_criteria = set()
    for name, criteria in overused.items():
        # Flag only the criteria beyond the 3rd occurrence
        for c in criteria[3:]:
            overuse_flagged_criteria.add(c)

    for key in SCORE_COMPONENTS:
        entry = enriched.get(key)
        if not isinstance(entry, dict):
            continue

        explanation = entry.get("explanation", "")
        problems = []

        # Score preservation (hard — always enforce)
        expected_score = rating.get(key)
        if expected_score is not None:
            entry["score"] = expected_score  # Force-correct score

        # Slop check
        slop_result = check_slop_phrases(explanation)
        if not slop_result["passed"]:
            phrases = [s["phrase"] for s in slop_result["slop_found"]]
            problems.append(f"slop: {phrases}")

        # False uncertainty when community data exists
        if has_community and RE_NO_EVIDENCE.search(explanation):
            problems.append("false uncertainty (community data exists)")

        # Length bounds (dynamic max based on community dump size)
        if len(explanation) < 50:
            problems.append(f"too short ({len(explanation)} chars)")
        elif len(explanation) > max_explanation_len:
            problems.append(f"too long ({len(explanation)} chars, max {max_explanation_len} for {community_kb:.0f}KB dump)")

        # No-data padding
        if _check_no_data_padding(explanation):
            problems.append("no-data padding (says no data then fills paragraph)")

        # Repeated quote across 3+ criteria
        if key in repeat_flagged_criteria:
            reused = [q for q, cs in repeated.items() if key in cs]
            problems.append(f"repeated quote in {MAX_QUOTE_REUSE + 1}+ criteria: {reused[0][:50]}")

        # Overused name (4+ criteria)
        if key in overuse_flagged_criteria:
            names = [n for n, cs in overused.items() if key in cs[3:]]
            problems.append(f"overused name ({names[0]} in 4+ criteria)")

        # If problems found and we have an old explanation, keep the old one
        # UNLESS the old explanation has the same problem (avoids infinite loop)
        if problems and force and isinstance(old_bor.get(key), dict):
            old_exp = old_bor[key].get("explanation", "")
            if old_exp.strip():
                # Check if ALL problems are name-overuse and the old also has
                # those same names — keeping old would be circular
                only_name_overuse = all("overused name" in p for p in problems)
                old_has_same_names = False
                if only_name_overuse:
                    overused_in_key = [n for n, cs in overused.items() if key in cs[3:]]
                    old_has_same_names = all(n in old_exp for n in overused_in_key)

                if old_has_same_names:
                    # Accept the new explanation — old has the same overuse
                    issues.append(f"  {key}: ACCEPTED (old also has {overused_in_key[0]})")
                elif only_length_issue(problems) and len(explanation) < len(old_exp):
                    # New is shorter than old — accept it even though it's over limit
                    issues.append(f"  {key}: ACCEPTED (new {len(explanation)} < old {len(old_exp)} chars)")
                else:
                    enriched[key]["explanation"] = old_exp
                    kept_old.append(key)
                    issues.append(f"  {key}: KEPT OLD — {'; '.join(problems)}")
                    continue

        if problems:
            issues.append(f"  {key}: {'; '.join(problems)}")

    return len(issues) == 0, issues, enriched, kept_old


def enrich_profile(slug, dry_run=False, complete_mode=False, force=False):
    """Enrich a single profile. Returns (success, message).

    complete_mode: If True, complete partial profiles (7→14) instead of
                   requiring <7 explanations.
    force: If True, re-enrich even if already complete (14/14). Saves
           snapshot of current ratings before overwriting.
    """
    profile_path = RACE_DATA / f"{slug}.json"
    if not profile_path.exists():
        return False, f"No profile: {slug}.json"

    data = json.loads(profile_path.read_text())
    race = data.get("race", data)

    if force:
        # Save snapshot before re-enrichment (skip on dry-run)
        if not dry_run:
            save_snapshot(slug, race)
        missing = None
    elif complete_mode:
        if not needs_completion(race):
            # Check if it's already full or needs full enrichment
            bor = race.get("biased_opinion_ratings", {})
            explained = sum(1 for k in SCORE_COMPONENTS
                            if isinstance(bor.get(k), dict) and bor[k].get("explanation", "").strip())
            if explained >= 14:
                return False, f"Already complete: {slug} (14/14)"
            if explained < 7:
                return False, f"Needs full enrichment, not completion: {slug} ({explained}/14)"
            return False, f"Unexpected state: {slug} ({explained}/14)"
        missing = get_missing_criteria(race)
    else:
        if not needs_enrichment(race):
            return False, f"Already enriched: {slug}"
        missing = None

    research = load_research(slug)
    if not research:
        return False, f"No research dump: {slug}"

    voice_guide = load_voice_guide()

    if force:
        prompt = build_re_enrichment_prompt(race, research, voice_guide, slug=slug)
    elif complete_mode and missing:
        prompt = build_completion_prompt(race, research, voice_guide, missing)
    else:
        prompt = build_enrichment_prompt(race, research, voice_guide)

    if dry_run:
        label = "FORCE re-enrichment" if force else (f"missing {missing}" if missing else "full enrichment")
        return True, f"Would enrich: {slug} ({label}, {len(research)} chars research)"

    try:
        response_text = call_api(prompt)
        enriched = parse_json_response(response_text)
    except json.JSONDecodeError as e:
        return False, f"Bad JSON from API: {e}"
    except Exception as e:
        return False, f"API error: {e}"

    # Validate response has expected structure
    if not isinstance(enriched, dict):
        return False, f"API returned non-dict: {type(enriched)}"

    valid_keys = set(SCORE_COMPONENTS)
    response_keys = set(enriched.keys())
    if not response_keys.intersection(valid_keys):
        return False, f"API response has no valid keys: {response_keys}"

    # Merge: set scores from gravel_god_rating
    rating = race.get("gravel_god_rating", {})
    for key in SCORE_COMPONENTS:
        if key in enriched and isinstance(enriched[key], dict):
            enriched[key]["score"] = rating.get(key, enriched[key].get("score", 3))

    # Post-enrichment quality gate
    gate_passed, gate_issues, enriched, kept_old = validate_enrichment(
        slug, enriched, race, force=force
    )
    if gate_issues:
        print(f"\n    Quality gate: {len(gate_issues)} issues", end="")
        if kept_old:
            print(f" ({len(kept_old)} kept old)", end="")
        print()
        for issue in gate_issues[:5]:
            print(f"    {issue}")

    if complete_mode:
        # Merge new explanations into existing biased_opinion_ratings
        existing_bor = race.get("biased_opinion_ratings", {})
        for key in SCORE_COMPONENTS:
            if key in enriched and isinstance(enriched[key], dict):
                existing_bor[key] = enriched[key]
        race["biased_opinion_ratings"] = existing_bor
    else:
        race["biased_opinion_ratings"] = enriched

    # Write back
    if "race" in data:
        data["race"] = race
    else:
        data = race

    profile_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    bor = race["biased_opinion_ratings"]
    explained = sum(1 for v in bor.values()
                    if isinstance(v, dict) and v.get("explanation", "").strip())
    return True, f"Enriched: {slug} ({explained}/14 explanations)"


def get_completion_candidates(n, min_research_kb=3.0):
    """Get v1 profiles that need completion (7→14 explanations)."""
    candidates = []

    for path in sorted(RACE_DATA.glob("*.json")):
        slug = path.stem
        dump_path = RESEARCH_DUMPS / f"{slug}-raw.md"
        if not dump_path.exists():
            continue
        dump_kb = dump_path.stat().st_size / 1024
        if dump_kb < min_research_kb:
            continue

        data = json.loads(path.read_text())
        race = data.get("race", data)
        if not needs_completion(race):
            continue

        tier = race.get("gravel_god_rating", {}).get("tier", 4)
        candidates.append({
            "slug": slug,
            "tier": tier,
            "research_kb": dump_kb,
        })

    candidates.sort(key=lambda r: (r["tier"], -r["research_kb"]))
    return [r["slug"] for r in candidates[:n]]


def main():
    parser = argparse.ArgumentParser(description="Batch profile enrichment")
    parser.add_argument("--auto", type=int, metavar="N",
                        help="Auto-select top N enrichment candidates")
    parser.add_argument("--complete", type=int, metavar="N",
                        help="Complete top N partial profiles (7→14 explanations)")
    parser.add_argument("--slugs", nargs="+", help="Specific slugs to enrich")
    parser.add_argument("--complete-slugs", nargs="+",
                        help="Complete specific partial profiles")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without calling API or writing files")
    parser.add_argument("--delay", type=int, default=3,
                        help="Seconds between API calls (default: 3)")
    parser.add_argument("--min-research-kb", type=float, default=5.0,
                        help="Minimum research dump size in KB (default: 5.0)")
    parser.add_argument("--force", action="store_true",
                        help="Re-enrich even if already complete (14/14). Saves snapshot first.")
    args = parser.parse_args()

    complete_mode = False
    force_mode = args.force
    if force_mode and args.auto:
        slugs = get_force_candidates(args.auto, min_research_kb=args.min_research_kb)
        print(f"Auto-selected {len(slugs)} force re-enrichment candidates (community > profile)")
    elif force_mode and args.slugs:
        slugs = args.slugs
    elif args.complete:
        slugs = get_completion_candidates(args.complete)
        complete_mode = True
        print(f"Auto-selected {len(slugs)} partial profiles to complete")
    elif args.complete_slugs:
        slugs = args.complete_slugs
        complete_mode = True
    elif args.auto:
        slugs = get_enrichment_candidates(args.auto, min_research_kb=args.min_research_kb)
        print(f"Auto-selected {len(slugs)} candidates")
    elif args.slugs:
        slugs = args.slugs
    else:
        parser.print_help()
        return

    mode_label = "FORCE RE-ENRICHING" if force_mode else ("COMPLETING" if complete_mode else "ENRICHING")
    print(f"\n{'DRY RUN - ' if args.dry_run else ''}{mode_label} {len(slugs)} profiles\n")

    success = 0
    failed = 0
    skipped = 0

    for i, slug in enumerate(slugs, 1):
        print(f"[{i}/{len(slugs)}] {slug}...", end=" ", flush=True)
        ok, msg = enrich_profile(slug, dry_run=args.dry_run, complete_mode=complete_mode, force=force_mode)
        print(msg)

        if ok:
            success += 1
        elif "Already" in msg or "No research dump" in msg:
            skipped += 1
        else:
            failed += 1

        # Rate limiting delay between API calls
        if not args.dry_run and ok and i < len(slugs):
            time.sleep(args.delay)

    print(f"\nDone: {success} enriched, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()
