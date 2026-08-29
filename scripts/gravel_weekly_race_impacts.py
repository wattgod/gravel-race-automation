"""Stable identities for Gravel Weekly race-impact review records."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_impact_json(impact: dict[str, Any]) -> str:
    return json.dumps(impact, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def race_impact_hash(impact: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_impact_json(impact).encode("utf-8")).hexdigest()


def race_impact_id(impact: dict[str, Any]) -> str:
    return race_impact_hash(impact)[:12]
