#!/usr/bin/env python3
"""
Citation quality audit across all 328 race profiles.
Research only — does NOT modify any files.

Checks:
  1. Citation URL quality (generic/homepage vs real)
  2. Suspicious Reddit URLs
  3. Duplicate domains per profile
  4. research_strength.overall == 0 or null (pipeline never run)
  5. Placeholder text in logistics/vitals fields
"""

import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

RACE_DIR = Path(__file__).resolve().parent.parent / "race-data"

# --- Placeholder detection ---
PLACEHOLDER_PATTERNS = [
    re.compile(r"check\s+(the\s+)?official\s+(website|site|page)", re.I),
    re.compile(r"check\s+.*website", re.I),
    re.compile(r"^(morning|afternoon|evening)\s+start$", re.I),
    re.compile(r"^multiple\s+aid\s+stations?$", re.I),
    re.compile(r"^varies$", re.I),
    re.compile(r"^at\s+start/?finish$", re.I),
    re.compile(r"^day\s+before\s+(typically|usually|often)?\s*$", re.I),
    re.compile(r"^(tbd|tba|n/?a|unknown|not\s+available|not\s+specified)$", re.I),
    re.compile(r"^online\.?\s*cost:\s*~", re.I),  # "Online. Cost: ~$60-100"
    re.compile(r"has\s+(good|full|standard|basic)\s+(lodging|dining|food|camping)\s+options", re.I),
    re.compile(r"^(modest|various)\s+prizes?$", re.I),
    re.compile(r"generally\s+mild\s+conditions", re.I),
]

# Fields to check for placeholder text
LOGISTICS_FIELDS = ["parking", "camping", "packet_pickup", "official_site"]
VITALS_FIELDS = ["start_time", "aid_stations", "registration", "prize_purse"]


def is_generic_homepage(url: str) -> bool:
    """Return True if URL is just a domain homepage with no specific path."""
    try:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        # No path, or path is just "/" or empty
        if not path or path == "":
            return True
        # Some homepages have only a language prefix like /en or /en/
        if re.match(r"^/[a-z]{2}/?$", path):
            return True
        return False
    except Exception:
        return False


def is_suspicious_reddit(url: str) -> bool:
    """Return True if URL claims to be Reddit but doesn't match real format."""
    try:
        parsed = urlparse(url)
        if "reddit.com" not in parsed.hostname:
            return False
        path = parsed.path.rstrip("/")
        # Real reddit post: /r/subreddit/comments/ALPHANUMERIC_ID/...
        if re.search(r"/comments/[a-z0-9]+", path):
            return False
        # Real subreddit listing: /r/subreddit/ (this is generic but real)
        if re.match(r"^/r/[a-zA-Z0-9_]+/?$", path):
            return False  # valid subreddit link, though generic
        # Anything else on reddit.com is suspicious
        # But homepage reddit.com is caught by generic check
        if not path or path == "":
            return False  # homepage, caught separately
        return True
    except Exception:
        return False


def is_placeholder(text: str) -> bool:
    """Return True if text matches known placeholder patterns."""
    if not text or not isinstance(text, str):
        return False
    text = text.strip()
    for pat in PLACEHOLDER_PATTERNS:
        if pat.search(text):
            return True
    return False


def audit_profile(filepath: Path) -> dict:
    """Audit a single race profile and return findings."""
    with open(filepath) as f:
        data = json.load(f)

    race = data["race"]
    slug = race.get("slug", filepath.stem)
    name = race.get("display_name", race.get("name", slug))

    citations = race.get("citations", [])

    generic_urls = []
    suspicious_reddit = []
    real_urls = []
    domain_counter = Counter()

    for cit in citations:
        url = cit.get("url", "")
        if not url:
            continue

        try:
            domain = urlparse(url).hostname or ""
        except Exception:
            domain = ""

        domain_counter[domain] += 1

        if is_generic_homepage(url):
            generic_urls.append(url)
        elif is_suspicious_reddit(url):
            suspicious_reddit.append(url)
        else:
            real_urls.append(url)

    # Duplicate domains (>1 citation from same domain)
    dup_domains = {d: c for d, c in domain_counter.items() if c > 1}

    # Research strength
    rs = race.get("research_metadata", {}).get("research_strength", {})
    rs_overall = rs.get("overall")
    has_research_dump = rs.get("has_research_dump", False)

    # Placeholder text in vitals + logistics
    placeholders_found = {}
    vitals = race.get("vitals", {})
    logistics = race.get("logistics", {})

    for field in VITALS_FIELDS:
        val = vitals.get(field, "")
        if is_placeholder(str(val)):
            placeholders_found[f"vitals.{field}"] = str(val)[:100]

    for field in LOGISTICS_FIELDS:
        val = logistics.get(field, "")
        if is_placeholder(str(val)):
            placeholders_found[f"logistics.{field}"] = str(val)[:100]

    # Also check lodging_strategy and food in logistics
    for field in ["lodging_strategy", "food"]:
        val = logistics.get(field, "")
        if is_placeholder(str(val)):
            placeholders_found[f"logistics.{field}"] = str(val)[:100]

    return {
        "slug": slug,
        "name": name,
        "total_citations": len(citations),
        "generic_urls": generic_urls,
        "suspicious_reddit": suspicious_reddit,
        "real_urls": real_urls,
        "dup_domains": dup_domains,
        "rs_overall": rs_overall,
        "has_research_dump": has_research_dump,
        "placeholders": placeholders_found,
    }


def main():
    files = sorted(RACE_DIR.glob("*.json"))
    print(f"Scanning {len(files)} race profiles in {RACE_DIR}\n")

    results = []
    for fp in files:
        try:
            results.append(audit_profile(fp))
        except Exception as e:
            print(f"  ERROR reading {fp.name}: {e}")

    # ================================================================
    # AGGREGATE STATS
    # ================================================================
    total_citations = sum(r["total_citations"] for r in results)
    total_generic = sum(len(r["generic_urls"]) for r in results)
    total_suspicious = sum(len(r["suspicious_reddit"]) for r in results)
    total_real = sum(len(r["real_urls"]) for r in results)

    print("=" * 72)
    print("  CITATION QUALITY AUDIT REPORT")
    print("=" * 72)

    print(f"\n  Total profiles scanned:        {len(results)}")
    print(f"  Total citations across all:    {total_citations}")
    print(f"  Real citations:                {total_real}  ({total_real/max(total_citations,1)*100:.1f}%)")
    print(f"  Generic/homepage citations:    {total_generic}  ({total_generic/max(total_citations,1)*100:.1f}%)")
    print(f"  Suspicious Reddit URLs:        {total_suspicious}  ({total_suspicious/max(total_citations,1)*100:.1f}%)")

    # Average real per profile
    avg_real = total_real / max(len(results), 1)
    avg_total = total_citations / max(len(results), 1)
    print(f"\n  Avg citations per profile:     {avg_total:.1f}")
    print(f"  Avg REAL citations per profile: {avg_real:.1f}")

    # ================================================================
    # TOP 20 MOST-USED GENERIC HOMEPAGE URLs
    # ================================================================
    generic_counter = Counter()
    for r in results:
        for url in r["generic_urls"]:
            generic_counter[url] += 1

    print(f"\n{'=' * 72}")
    print("  TOP 20 MOST-USED GENERIC/HOMEPAGE URLs")
    print("=" * 72)
    for url, count in generic_counter.most_common(20):
        print(f"  {count:4d}x  {url}")

    # ================================================================
    # DISTRIBUTION: generic citations per profile
    # ================================================================
    buckets = {"0": 0, "1-3": 0, "4-6": 0, "7+": 0}
    for r in results:
        n = len(r["generic_urls"])
        if n == 0:
            buckets["0"] += 1
        elif n <= 3:
            buckets["1-3"] += 1
        elif n <= 6:
            buckets["4-6"] += 1
        else:
            buckets["7+"] += 1

    print(f"\n{'=' * 72}")
    print("  DISTRIBUTION: Generic citations per profile")
    print("=" * 72)
    for label, count in buckets.items():
        bar = "#" * (count // 2)
        print(f"  {label:>5s}: {count:4d}  ({count/len(results)*100:.1f}%)  {bar}")

    # ================================================================
    # PROFILES WITH WORST CITATION QUALITY (highest % generic)
    # ================================================================
    # Only consider profiles with at least 1 citation
    with_cits = [r for r in results if r["total_citations"] > 0]
    worst = sorted(with_cits, key=lambda r: len(r["generic_urls"]) / max(r["total_citations"], 1), reverse=True)

    print(f"\n{'=' * 72}")
    print("  TOP 30 WORST CITATION QUALITY (highest % generic)")
    print("=" * 72)
    print(f"  {'Profile':<45s} {'Total':>5s} {'Generic':>7s} {'Real':>5s} {'%Gen':>5s}")
    print(f"  {'-'*45} {'-'*5} {'-'*7} {'-'*5} {'-'*5}")
    for r in worst[:30]:
        pct = len(r["generic_urls"]) / max(r["total_citations"], 1) * 100
        print(f"  {r['name'][:45]:<45s} {r['total_citations']:>5d} {len(r['generic_urls']):>7d} {len(r['real_urls']):>5d} {pct:>5.0f}%")

    # ================================================================
    # PROFILES WITH ZERO REAL CITATIONS
    # ================================================================
    zero_real = [r for r in results if len(r["real_urls"]) == 0]
    print(f"\n{'=' * 72}")
    print(f"  PROFILES WITH ZERO REAL CITATIONS ({len(zero_real)} total)")
    print("=" * 72)
    for r in sorted(zero_real, key=lambda x: x["total_citations"], reverse=True):
        gen = len(r["generic_urls"])
        sus = len(r["suspicious_reddit"])
        print(f"  {r['name'][:50]:<50s}  total={r['total_citations']}  generic={gen}  reddit_sus={sus}")

    # ================================================================
    # PROFILES WITH ZERO CITATIONS AT ALL
    # ================================================================
    zero_cits = [r for r in results if r["total_citations"] == 0]
    print(f"\n{'=' * 72}")
    print(f"  PROFILES WITH ZERO CITATIONS ({len(zero_cits)} total)")
    print("=" * 72)
    for r in sorted(zero_cits, key=lambda x: x["name"]):
        print(f"  {r['name']}")

    # ================================================================
    # SUSPICIOUS REDDIT URLs
    # ================================================================
    all_sus_reddit = []
    for r in results:
        for url in r["suspicious_reddit"]:
            all_sus_reddit.append((r["slug"], url))

    print(f"\n{'=' * 72}")
    print(f"  SUSPICIOUS REDDIT URLs ({len(all_sus_reddit)} total)")
    print("=" * 72)
    for slug, url in all_sus_reddit[:50]:
        print(f"  {slug:<40s}  {url}")
    if len(all_sus_reddit) > 50:
        print(f"  ... and {len(all_sus_reddit) - 50} more")

    # ================================================================
    # DUPLICATE DOMAINS (profiles with same domain cited 3+ times)
    # ================================================================
    heavy_dups = []
    for r in results:
        for dom, cnt in r["dup_domains"].items():
            if cnt >= 3:
                heavy_dups.append((r["slug"], dom, cnt))
    heavy_dups.sort(key=lambda x: x[2], reverse=True)

    print(f"\n{'=' * 72}")
    print(f"  HEAVY DUPLICATE DOMAINS (3+ citations from same domain, {len(heavy_dups)} instances)")
    print("=" * 72)
    for slug, dom, cnt in heavy_dups[:40]:
        print(f"  {slug:<40s}  {dom:<35s}  {cnt}x")
    if len(heavy_dups) > 40:
        print(f"  ... and {len(heavy_dups) - 40} more")

    # ================================================================
    # RESEARCH STRENGTH = 0 or null
    # ================================================================
    no_research = [r for r in results if r["rs_overall"] is None or r["rs_overall"] == 0]
    has_dump_but_null = [r for r in no_research if r["has_research_dump"]]
    no_dump = [r for r in no_research if not r["has_research_dump"]]

    print(f"\n{'=' * 72}")
    print(f"  RESEARCH STRENGTH = 0 or null ({len(no_research)} total)")
    print("=" * 72)
    print(f"  No research dump (pipeline never run):  {len(no_dump)}")
    print(f"  Has dump but score null/0:              {len(has_dump_but_null)}")

    # Show distribution of research_strength.overall
    scored = [r for r in results if r["rs_overall"] is not None and r["rs_overall"] > 0]
    if scored:
        scores = [r["rs_overall"] for r in scored]
        print(f"\n  Among {len(scored)} profiles WITH research scores:")
        print(f"    Min:    {min(scores):.1f}")
        print(f"    Max:    {max(scores):.1f}")
        print(f"    Mean:   {sum(scores)/len(scores):.1f}")
        print(f"    Median: {sorted(scores)[len(scores)//2]:.1f}")

        # Buckets
        rs_buckets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
        for s in scores:
            if s < 20:
                rs_buckets["0-20"] += 1
            elif s < 40:
                rs_buckets["20-40"] += 1
            elif s < 60:
                rs_buckets["40-60"] += 1
            elif s < 80:
                rs_buckets["60-80"] += 1
            else:
                rs_buckets["80-100"] += 1
        print(f"\n  Research strength distribution:")
        for label, count in rs_buckets.items():
            bar = "#" * (count // 2)
            print(f"    {label:>6s}: {count:4d}  {bar}")

    # ================================================================
    # PLACEHOLDER TEXT IN LOGISTICS/VITALS
    # ================================================================
    profiles_with_placeholders = [r for r in results if r["placeholders"]]
    total_placeholders = sum(len(r["placeholders"]) for r in results)

    print(f"\n{'=' * 72}")
    print(f"  PLACEHOLDER TEXT ({total_placeholders} instances in {len(profiles_with_placeholders)} profiles)")
    print("=" * 72)

    # Count by field
    field_counter = Counter()
    for r in results:
        for field in r["placeholders"]:
            field_counter[field] += 1

    print(f"\n  By field:")
    for field, count in field_counter.most_common():
        print(f"    {field:<35s}  {count:4d}")

    # Show some examples
    print(f"\n  Sample placeholder values:")
    placeholder_examples = defaultdict(set)
    for r in results:
        for field, val in r["placeholders"].items():
            placeholder_examples[field].add(val)
    for field, vals in sorted(placeholder_examples.items()):
        print(f"    {field}:")
        for v in sorted(vals)[:5]:
            print(f"      - \"{v}\"")

    # ================================================================
    # FINAL SUMMARY
    # ================================================================
    print(f"\n{'=' * 72}")
    print("  FINAL SUMMARY")
    print("=" * 72)
    print(f"  Total profiles:                 {len(results)}")
    print(f"  Total citations:                {total_citations}")
    print(f"  Real citations:                 {total_real} ({total_real/max(total_citations,1)*100:.1f}%)")
    print(f"  Generic/homepage:               {total_generic} ({total_generic/max(total_citations,1)*100:.1f}%)")
    print(f"  Suspicious Reddit:              {total_suspicious}")
    print(f"  Profiles w/ zero citations:     {len(zero_cits)}")
    print(f"  Profiles w/ zero real cits:     {len(zero_real)}")
    print(f"  Avg real cits per profile:      {avg_real:.1f}")
    print(f"  Research never run (null/0):    {len(no_research)}")
    print(f"  Profiles w/ placeholder text:   {len(profiles_with_placeholders)}")
    print(f"  Total placeholder instances:    {total_placeholders}")
    print()


if __name__ == "__main__":
    main()
