"""The fabricated-claims audit must stay clean across the whole catalog.

Every prestige claim (UCI, state championship, largest, ...) in a race
profile has to be backed by a research dump built from fetched sources,
or by a reviewed entry in scripts/claims_allowlist.json (issue #689).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import audit_fabricated_claims as audit  # noqa: E402


def test_no_unsupported_claims_in_catalog():
    findings = []
    for race_file in sorted(audit.RACE_DATA_DIR.glob("*.json")):
        findings.extend(audit.audit_race(race_file))
    summary = [f"{f['slug']}: [{f['claim_type']}] {f['field']}" for f in findings]
    assert not findings, "Unsupported claims:\n" + "\n".join(summary)
