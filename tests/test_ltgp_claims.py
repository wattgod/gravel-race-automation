"""
Regression tests for Life Time Grand Prix claims.

LLMs frequently fabricate LTGP membership for prestigious races.
This test enforces that only actual LTGP races can make unqualified
membership claims. Races that were formerly on LTGP must use past tense.

The LTGP calendar changes annually - update the allowlists when the
new calendar is announced (typically October).
"""

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    # Stub for running without pytest
    class pytest:
        @staticmethod
        def skip(msg): raise Exception(f"SKIP: {msg}")
        @staticmethod
        def fail(msg): raise AssertionError(msg)

import json
import re
from pathlib import Path


# Actual LTGP races by year (update annually)
LTGP_RACES = {
    2024: {
        "sea-otter-gravel",      # Fuego XL 100k
        "fuego-mtb",             # Fuego XL (alternate slug)
        "fuego-xl",              # Fuego XL (alternate slug)
        "unbound-200",
        "crusher-in-the-tushar",
        "leadville-100",
        "chequamegon",           # MTB (alternate slug)
        "chequamegon-mtb",       # MTB (current slug)
        "the-rad",
        "big-sugar",
    },
    2025: {
        "sea-otter-gravel",
        "fuego-mtb",             # Fuego XL (alternate slug)
        "fuego-xl",              # Fuego XL (alternate slug)
        "unbound-200",
        "leadville-100",
        "chequamegon",           # MTB (alternate slug)
        "chequamegon-mtb",       # MTB (current slug)
        "little-sugar",          # MTB (alternate slug)
        "little-sugar-mtb",      # MTB (current slug)
        "big-sugar",
    },
    2026: {
        "sea-otter-gravel",
        "fuego-mtb",             # Fuego XL (alternate slug)
        "fuego-xl",              # Fuego XL (alternate slug)
        "unbound-200",
        "leadville-100",
        "chequamegon",           # MTB (alternate slug)
        "chequamegon-mtb",       # MTB (current slug)
        "little-sugar",          # MTB (alternate slug)
        "little-sugar-mtb",      # MTB (current slug)
        "big-sugar",
    },
}

# Races that were on LTGP but dropped - must use past tense
FORMER_LTGP_RACES = {
    "crusher-in-the-tushar",  # 2024 only
    "the-rad",                # 2024 only
}

# Current LTGP races (2025+)
CURRENT_LTGP_RACES = LTGP_RACES[2025]

# All races ever on LTGP
ALL_LTGP_RACES = set()
for year_races in LTGP_RACES.values():
    ALL_LTGP_RACES.update(year_races)

# Patterns that indicate LTGP membership claims
LTGP_CLAIM_PATTERNS = [
    r"(?i)life\s*time\s*grand\s*prix",
    r"(?i)lifetime\s*grand\s*prix",
    r"(?i)\bLTGP\b",
    r"(?i)\bLGP\b",
]

# Patterns that indicate past tense (acceptable for former races)
PAST_TENSE_PATTERNS = [
    r"(?i)was\s+(part\s+of|on|in)\s+(the\s+)?life\s*time",
    r"(?i)was\s+(an?\s+)?LTGP",
    r"(?i)former(ly)?\s+LTGP",
    r"(?i)dropped\s+(from|for)",
    r"(?i)in\s+20\d\d\s*\(",  # "in 2024 (dropped..."
    r"(?i)LTGP\s+in\s+20\d\d",
]

# Patterns that indicate NOT being LTGP (acceptable)
NEGATION_PATTERNS = [
    r"(?i)not\s+(officially\s+)?(part\s+of|on|in)\s+(the\s+)?life\s*time",
    r"(?i)not\s+(an?\s+)?LTGP",
    r"(?i)despite\s+not\s+being\s+LTGP",
    r"(?i)non-LTGP",
    r"(?i)without\s+LTGP",
]

# Patterns that indicate riders attend (not membership claim)
RIDER_PATTERNS = [
    r"(?i)LTGP\s+riders?\s+(do|attend|race|compete)",
    r"(?i)many\s+LTGP\s+riders",
    r"(?i)attracts?\s+LTGP",
    r"(?i)LTGP-caliber",
]


def get_race_data_dir():
    """Get path to race-data directory."""
    return Path(__file__).parent.parent / "race-data"


def extract_ltgp_claims(content: str) -> list[dict]:
    """Extract all LTGP-related claims from content."""
    claims = []

    for pattern in LTGP_CLAIM_PATTERNS:
        for match in re.finditer(pattern, content):
            # Get surrounding context (100 chars each side)
            start = max(0, match.start() - 100)
            end = min(len(content), match.end() + 100)
            context = content[start:end]

            claims.append({
                "match": match.group(),
                "context": context,
                "position": match.start(),
            })

    return claims


def is_past_tense_claim(context: str) -> bool:
    """Check if the claim is in past tense (acceptable for former races)."""
    for pattern in PAST_TENSE_PATTERNS:
        if re.search(pattern, context):
            return True
    return False


def is_negation_claim(context: str) -> bool:
    """Check if the claim is a negation (acceptable)."""
    for pattern in NEGATION_PATTERNS:
        if re.search(pattern, context):
            return True
    return False


def is_rider_reference(context: str) -> bool:
    """Check if the claim is about riders, not membership."""
    for pattern in RIDER_PATTERNS:
        if re.search(pattern, context):
            return True
    return False


class TestLTGPClaims:
    """Test that LTGP claims are factually accurate."""

    def test_no_fabricated_ltgp_claims(self):
        """
        Scan all race profiles for LTGP claims.
        Fail if a non-LTGP race makes an unqualified membership claim.
        """
        race_data_dir = get_race_data_dir()
        if not race_data_dir.exists():
            pytest.skip("race-data directory not found")

        violations = []

        for json_file in race_data_dir.glob("*.json"):
            slug = json_file.stem

            try:
                content = json_file.read_text()
                data = json.loads(content)
            except (json.JSONDecodeError, IOError) as e:
                continue

            # Strip youtube_data before scanning — transcripts contain
            # natural LTGP references from riders that aren't editorial claims
            scan_data = dict(data)
            if "race" in scan_data and "youtube_data" in scan_data.get("race", {}):
                scan_data = json.loads(content)
                scan_data["race"] = {k: v for k, v in scan_data["race"].items() if k != "youtube_data"}
            scan_content = json.dumps(scan_data)

            # Extract all LTGP claims from the editorial JSON content
            claims = extract_ltgp_claims(scan_content)

            if not claims:
                continue

            # Check each claim
            for claim in claims:
                context = claim["context"]

                # Skip if it's a negation ("not part of LTGP")
                if is_negation_claim(context):
                    continue

                # Skip if it's about riders attending, not membership
                if is_rider_reference(context):
                    continue

                # If race is currently on LTGP, any claim is fine
                if slug in CURRENT_LTGP_RACES:
                    continue

                # If race was formerly on LTGP, must be past tense
                if slug in FORMER_LTGP_RACES:
                    if is_past_tense_claim(context):
                        continue
                    else:
                        violations.append({
                            "file": json_file.name,
                            "slug": slug,
                            "issue": "Former LTGP race uses present tense",
                            "context": context.strip(),
                        })
                        continue

                # Race was never on LTGP - this is a fabrication
                if slug not in ALL_LTGP_RACES:
                    violations.append({
                        "file": json_file.name,
                        "slug": slug,
                        "issue": "Race was NEVER on LTGP",
                        "context": context.strip(),
                    })

        if violations:
            msg = f"\n\nFound {len(violations)} fabricated/incorrect LTGP claims:\n\n"
            for v in violations:
                msg += f"FILE: {v['file']}\n"
                msg += f"SLUG: {v['slug']}\n"
                msg += f"ISSUE: {v['issue']}\n"
                msg += f"CONTEXT: ...{v['context']}...\n\n"

            msg += "\nTo fix:\n"
            msg += "1. If race IS on LTGP, add slug to CURRENT_LTGP_RACES in this test\n"
            msg += "2. If race WAS on LTGP, use past tense ('Was part of LTGP in 2024')\n"
            msg += "3. If race was NEVER on LTGP, remove the false claim\n"

            pytest.fail(msg)

    def test_ltgp_allowlist_is_current(self):
        """Verify the LTGP allowlist includes expected races."""
        # These races should definitely be on LTGP
        expected_current = {"unbound-200", "big-sugar", "leadville-100"}

        for race in expected_current:
            assert race in CURRENT_LTGP_RACES, f"{race} should be in CURRENT_LTGP_RACES"

    def test_former_races_not_in_current(self):
        """Verify former races are not in current list."""
        for race in FORMER_LTGP_RACES:
            assert race not in CURRENT_LTGP_RACES, \
                f"{race} is in FORMER_LTGP_RACES but also in CURRENT_LTGP_RACES"


class TestLTGPPatternMatching:
    """Test the pattern matching logic."""

    def test_detects_present_tense_claim(self):
        """Should detect present tense LTGP claims."""
        content = "Part of the Lifetime Grand Prix series"
        claims = extract_ltgp_claims(content)
        assert len(claims) >= 1
        assert not is_past_tense_claim(claims[0]["context"])

    def test_detects_past_tense_claim(self):
        """Should recognize past tense claims."""
        content = "Was part of Life Time Grand Prix in 2024 (dropped for 2025+)"
        claims = extract_ltgp_claims(content)
        assert len(claims) >= 1
        assert is_past_tense_claim(claims[0]["context"])

    def test_detects_negation(self):
        """Should recognize negation claims."""
        content = "Not officially part of Life Time Grand Prix"
        claims = extract_ltgp_claims(content)
        assert len(claims) >= 1
        assert is_negation_claim(claims[0]["context"])

    def test_detects_rider_reference(self):
        """Should recognize rider references (not membership claims)."""
        content = "Many LTGP riders do the LeadBoat combo"
        claims = extract_ltgp_claims(content)
        assert len(claims) >= 1
        assert is_rider_reference(claims[0]["context"])

    def test_catches_fabricated_claim(self):
        """Should catch a fabricated claim."""
        content = "Featured on Life Time Grand Prix circuit"
        claims = extract_ltgp_claims(content)
        assert len(claims) >= 1
        # This should NOT be past tense, negation, or rider reference
        assert not is_past_tense_claim(claims[0]["context"])
        assert not is_negation_claim(claims[0]["context"])
        assert not is_rider_reference(claims[0]["context"])
