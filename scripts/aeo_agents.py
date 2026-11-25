#!/usr/bin/env python3
"""Versioned AI referral and crawler taxonomy for the AEO monitor.

The token strings are grounded in docs/research/aeo-monitor-ua-taxonomy.md.
Keep this module deterministic: collector 3 reports possible additions, but
taxonomy changes require a reviewed code change and version bump.
"""

from __future__ import annotations

import re

TAXONOMY_VERSION = 1

USER_AGENT_TAXONOMY = {
    "user_fetch": (
        "ChatGPT-User",
        "Claude-User",
        "Perplexity-User",
    ),
    "search_index": (
        "OAI-SearchBot",
        "Claude-SearchBot",
        "PerplexityBot",
    ),
    "training_crawl": (
        "GPTBot",
        "ClaudeBot",
        "meta-externalagent",
        "Amazonbot",
        "Bytespider",
        "cohere-ai",
    ),
}

# GA4 source matching is intentionally broad within known AI-associated
# products. It is a click-through proxy, not proof that a URL was cited.
REFERRAL_SOURCE_PATTERN = (
    r"(?i)(chatgpt|openai|perplexity|claude|anthropic|copilot|gemini|bard|"
    r"poe\.com|you\.com|phind|kagi)"
)
REFERRAL_SOURCE_RE = re.compile(REFERRAL_SOURCE_PATTERN)

UNKNOWN_CANDIDATE_PATTERN = r"(?i)(bot|crawler|spider|gpt|claude|llm)"
UNKNOWN_CANDIDATE_RE = re.compile(UNKNOWN_CANDIDATE_PATTERN)

# Known conventional search/indexing and SEO audit agents. These tokens are
# suppressed only from the discovery queue; their traffic is not reclassified
# as AI traffic.
NON_AI_SUPPRESSION_LIST = (
    "Googlebot",
    "GoogleOther",
    "AdsBot-Google",
    "Mediapartners-Google",
    "APIs-Google",
    "Storebot-Google",
    "Bingbot",
    "bingpreview",
    "MicrosoftPreview",
    "DuckDuckBot",
    "YandexBot",
    "Applebot",
    "AhrefsBot",
    "SemrushBot",
    "MJ12bot",
    "DotBot",
    "PetalBot",
    "BLEXBot",
    "DataForSeoBot",
    "SeobilityBot",
    "Screaming Frog SEO Spider",
    "SiteAuditBot",
    # Observed dominating the first live artifact (2026-07-23 smoke run):
    # classic non-AI search crawlers, suppressed so genuine AI candidates
    # (e.g. LinkupBot) stay visible.
    "Baiduspider",
    "Sogou web spider",
    "SeznamBot",
)

COMBINED_ALLOWLIST = tuple(
    token
    for bucket in ("user_fetch", "search_index", "training_crawl")
    for token in USER_AGENT_TAXONOMY[bucket]
)

# Readable aliases for callers that prefer the shorter contract terms.
UA_TAXONOMY = USER_AGENT_TAXONOMY
REFERRAL_REGEX = REFERRAL_SOURCE_RE
UNKNOWN_CANDIDATE_REGEX = UNKNOWN_CANDIDATE_RE
NON_AI_SUPPRESSION = NON_AI_SUPPRESSION_LIST


def classify_user_agent(user_agent: str) -> str | None:
    """Return the taxonomy bucket for a UA, matched case-insensitively."""
    lowered = (user_agent or "").lower()
    for bucket, tokens in USER_AGENT_TAXONOMY.items():
        if any(token.lower() in lowered for token in tokens):
            return bucket
    return None


def is_suppressed_non_ai(user_agent: str) -> bool:
    """Whether a bot-like UA belongs to the known non-AI suppression list."""
    lowered = (user_agent or "").lower()
    return any(token.lower() in lowered for token in NON_AI_SUPPRESSION_LIST)


def is_unknown_candidate(user_agent: str) -> bool:
    """Whether a UA should enter the spoofable-agent discovery queue."""
    return bool(
        UNKNOWN_CANDIDATE_RE.search(user_agent or "")
        and classify_user_agent(user_agent) is None
        and not is_suppressed_non_ai(user_agent)
    )


# A product name and optional numeric version are enough to spot a new
# crawler. Ignore URL paths, addresses, comments, and free-form headers.
_AGENT_PRODUCT = re.compile(
    r"(?<![\w.%+@/-])([A-Za-z][A-Za-z0-9_-]{0,31}(?:/[0-9]+(?:\.[0-9]+)*)?)(?![\w.%+@/-])"
)
UNKNOWN_AGENT_LABEL = "unknown-agent"


def public_agent_label(header: str) -> str:
    """Return a bounded crawler label suitable for public reporting."""
    for match in _AGENT_PRODUCT.finditer(header):
        label = match.group(1)
        if len(label) <= 48 and UNKNOWN_CANDIDATE_RE.search(label.split("/", 1)[0]):
            return label
    return UNKNOWN_AGENT_LABEL


def public_agent_candidates(candidates: list) -> list[dict]:
    """Fold raw or legacy crawler samples into safe public labels and counts."""
    combined = {}
    for item in candidates:
        if not isinstance(item, dict):
            continue
        label = public_agent_label(str(item.get("user_agent", "")))
        entry = combined.setdefault(label.casefold(), {"user_agent": label, "count": 0, "brands": {}})
        count = item.get("count")
        if type(count) is int and count >= 0:
            entry["count"] += count
        per_brand = item.get("brands")
        if isinstance(per_brand, dict):
            for brand, brand_count in per_brand.items():
                if brand in ("gravelgod", "roadie", "xcski") and type(brand_count) is int and brand_count >= 0:
                    entry["brands"][brand] = entry["brands"].get(brand, 0) + brand_count
    return list(combined.values())
