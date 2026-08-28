#!/usr/bin/env python3
"""Deterministic No-AI-slop audit for exact Gravel Weekly publication copy."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping

SOURCE_URL = "https://github.com/petergyang/no-ai-slop"
SOURCE_REVISION = "d30eddb9e04562234f2070b5ee63ca4649d9a05e"

RULES = (
    ("banned_word", r"\b(?:delve|foster|leverage|utilize|facilitate|empower|streamline|robust|cutting-edge|paradigm shift|game changer|this is huge|this changes everything|tapestry|realm|beacon|multifaceted|meticulous|intricate|paramount|transformative|elevate|embark|supercharge|harness|ever-evolving)\b"),
    ("empty_opener", r"\b(?:here(?:’|')s the thing|here(?:’|')s what i mean|let me be clear|i(?:’|')ll be honest|the uncomfortable truth is|it(?:’|')s worth noting|it(?:’|')s important to note|let(?:’|')s dive in)\b"),
    ("faux_insight", r"\b(?:what (?:most people|nobody) (?:get wrong|tell you)|the part (?:everyone|most people) (?:miss|skip)|here(?:’|')s what nobody tells you)\b"),
    ("binary_contrast", r"(?:\bit(?:’|')s|\b(?:it|this|that|the (?:question|point|story)) (?:is|was))(?:n(?:’|')t| not) [^.!?\n]{1,120}[,.]?\s+(?:it(?:’|')s|(?:it|this|that) (?:is|was))\b"),
    ("binary_contrast", r"\bnot just\b[^.!?\n]{1,120}\bbut\b"),
    ("colon_reveal", r"\b(?:best|hard|funny|interesting|important|key|real|wild) (?:part|thing|detail|point|problem|truth):\s+[a-z]"),
    ("superficial_analysis", r",\s+(?:highlighting|underscoring|reflecting|showcasing)\b"),
    ("importance_puffery", r"\b(?:stands as a testament|marks a pivotal moment|plays a vital role|solidifies (?:its|the) position|underscores (?:its|the) significance)\b"),
    ("interpretive_metadiscourse", r"\b(?:that last part matters more than it sounds|the key point is|as you can see|this distinction matters|in other words)\b"),
    ("weasel_attribution", r"\b(?:experts agree|industry reports suggest|many argue|widely regarded as|studies show)\b"),
    ("fake_strong_verb", r"\b(?:serves|acts|stands) as (?:a|an|the)\b"),
    ("negative_listing", r"(?:^|[.!?]\s+)not (?:a|an|the) [^.!?]{1,80}\.\s+not (?:a|an|the) [^.!?]{1,80}\."),
    ("dramatic_fragment", r"\bthat(?:’|')s it\.\s+that(?:’|')s the whole thing\b"),
    ("rhetorical_setup", r"\b(?:what if i told you|think about it|plot twist)\s*[:?]"),
    ("fake_profound_kicker", r"\bthe future (?:isn(?:’|')t|is not) coming\.\s+it(?:’|')s already here\.?\s*$"),
    ("summary_recap", r"(?:^|\n)\s*(?:in conclusion|ultimately|overall)\b"),
)


def _excerpt(text: str, start: int, length: int) -> str:
    return re.sub(r"\s+", " ", text[max(0, start - 35):start + length + 35]).strip()


def audit_no_ai_slop(fields: Mapping[str, str]) -> dict[str, object]:
    entries = sorted((name, value) for name, value in fields.items() if isinstance(value, str) and value.strip())
    findings: list[dict[str, str]] = []
    for field, value in entries:
        for pattern, expression in RULES:
            match = re.search(expression, value, re.IGNORECASE)
            if match:
                findings.append({"pattern": pattern, "field": field, "excerpt": _excerpt(value, match.start(), len(match.group(0)))})
        em_dash_count = value.count("—")
        allowed = 0 if len(value) < 500 else 2
        if em_dash_count > allowed:
            findings.append({
                "pattern": "em_dash_cluster",
                "field": field,
                "excerpt": f"{em_dash_count} em dashes in {'short' if len(value) < 500 else 'long'} copy",
            })
    checked_text_hash = hashlib.sha256(
        json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schemaVersion": "no-ai-slop-gate/v1",
        "sourceUrl": SOURCE_URL,
        "sourceRevision": SOURCE_REVISION,
        "checkedTextHash": checked_text_hash,
        "verdict": "fail" if findings else "pass",
        "findings": findings,
        "humanChecks": [
            "Preserve Matti's vocabulary, cadence, bluntness, humor, uncertainty, and useful rough edges.",
            "Cut portable filler; keep concrete facts, mechanisms, consequences, and judgments.",
            "Read aloud for robotic symmetry, synonym cycling, fake profundity, and flattened voice.",
        ],
        "humanApprovalRequired": True,
        "autoPublishAllowed": False,
    }
