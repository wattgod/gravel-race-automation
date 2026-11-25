"""Mission Control's Railway settings live in .railway/railway.ts (IaC).

Railway stops reading railway.json / railway.toml on 2026-12-01, and until
then a leftover file still overrides the service's stored settings. Without
the file, the service's own stored builder was RAILPACK (found 2026-11-16),
so these checks pin what the deploy needs: the Dockerfile builder, the
/health gate with its 120 s timeout, and the variable list (an apply deletes
any variable not listed).
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TS = REPO / ".railway" / "railway.ts"


def _ts() -> str:
    """The file with // comments removed, so text in a comment proves nothing."""
    raw = TS.read_text()
    assert "*/" not in raw, "use // comments only, so the checks below see live code"
    trailing = [l for l in raw.splitlines() if "//" in l and not l.strip().startswith("//")
                and not re.search(r'"[^"]*//[^"]*"', l)]
    assert trailing == [], "comments go on their own line, so the checks below see live code"
    return re.sub(r"^\s*//.*$", "", raw, flags=re.M)


def test_no_config_as_code_file():
    for name in ("railway.json", "railway.toml"):
        assert not (REPO / name).exists(), f"{name} is retired; use .railway/railway.ts"


def test_partial_owns_only_athlete_profiles():
    ts = _ts()
    assert 'export const partial = "athlete-profiles";' in ts
    assert re.findall(r'\bservice\("([^"]+)"', ts) == ["athlete-profiles"]
    assert "stripe-webhook-volume" not in ts and 'service("stripe-webhook"' not in ts
    assert re.search(r"resources: \[athleteProfiles\],", ts)


def test_build_and_deploy_settings():
    ts = _ts()
    assert 'github("wattgod/gravel-race-automation"' in ts
    assert 'branch: "main"' in ts
    assert 'rootDirectory: ""' in ts
    assert 'builder: "DOCKERFILE"' in ts
    assert 'dockerfilePath: "Dockerfile"' in ts
    assert 'healthcheckPath: "/health"' in ts
    assert "healthcheckTimeout: 120" in ts
    assert "restartPolicyMaxRetries: 3" in ts
    # ON_FAILURE is Railway's stored default; any other type is a change.
    assert "restartPolicyType" not in ts
    assert "export default defineRailway(" in ts
    assert "startCommand" not in ts
    dockerfile = (REPO / "Dockerfile").read_text()
    assert re.search(r'^CMD \["python3", "mission_control.py"\]', dockerfile, re.M)


def test_watch_patterns_cover_the_build():
    block = re.search(r"const WATCH_PATTERNS = \[(.*?)\];", _ts(), re.S)
    assert block
    patterns = re.findall(r'"([^"]+)"', block.group(1))
    # Every path the container reads (docs/specs/mission-control-hardening-notes.md).
    # Dropping one means a push touching it no longer redeploys Mission Control.
    assert patterns == [
        "mission_control/**",
        "mission_control.py",
        "requirements.txt",
        "Dockerfile",
        ".dockerignore",
        "pipeline/__init__.py",
        "pipeline/nutrition.py",
        "scripts/jev_client.py",
        "race-data/**",
        "web/race-index.json",
        "data/pricing.json",
        "guide/fonts/**",
        "templates/emails/**",
    ]
    assert "build: {" in _ts() and "watchPatterns: WATCH_PATTERNS" in _ts()


def test_variables_are_names_only():
    ts = _ts()
    block = re.search(r"const VARIABLES = \[(.*?)\];", ts, re.S)
    assert block, "VARIABLES list missing: an apply would delete every variable"
    names = re.findall(r'"([^"]+)"', block.group(1))
    assert names == sorted(set(names))
    assert all(re.fullmatch(r"[A-Z][A-Z0-9_]*", n) for n in names)
    # The live inventory on 2026-11-16. Apply deletes any name missing here, so
    # removing one must be a deliberate edit to this test too.
    assert names == [
        "GA4_CREDENTIALS_JSON",
        "GA4_PROPERTY_ID",
        "GG_RACE_DATES_URL",
        "MISSION_CONTROL_SECRET",
        "RACE_COUNTDOWN_MAX_PER_RUN",
        "RESEND_API_KEY",
        "RESEND_WEBHOOK_SECRET",
        "RL_RACE_DATES_URL",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_URL",
        "UNSUBSCRIBE_SECRET",
        "WEBHOOK_SECRET",
    ]
    assert "env: Object.fromEntries(VARIABLES.map((name) => [name, preserve()]))" in ts
