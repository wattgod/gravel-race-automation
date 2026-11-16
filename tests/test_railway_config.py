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
    return re.sub(r"^\s*//.*$", "", TS.read_text(), flags=re.M)


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
    assert "startCommand" not in ts
    dockerfile = (REPO / "Dockerfile").read_text()
    assert re.search(r'^CMD \["python3", "mission_control.py"\]', dockerfile, re.M)


def test_watch_patterns_cover_the_build():
    block = re.search(r"const WATCH_PATTERNS = \[(.*?)\];", _ts(), re.S)
    assert block
    patterns = re.findall(r'"([^"]+)"', block.group(1))
    for needed in ("mission_control/**", "mission_control.py", "requirements.txt", "Dockerfile"):
        assert needed in patterns
    assert "build: {" in _ts() and "watchPatterns: WATCH_PATTERNS" in _ts()


def test_variables_are_names_only():
    ts = _ts()
    block = re.search(r"const VARIABLES = \[(.*?)\];", ts, re.S)
    assert block, "VARIABLES list missing: an apply would delete every variable"
    names = re.findall(r'"([^"]+)"', block.group(1))
    assert names == sorted(set(names))
    assert all(re.fullmatch(r"[A-Z][A-Z0-9_]*", n) for n in names)
    required = {"MISSION_CONTROL_SECRET", "RESEND_API_KEY", "SUPABASE_SERVICE_KEY",
                "SUPABASE_URL", "WEBHOOK_SECRET", "UNSUBSCRIBE_SECRET"}
    assert required - set(names) == set()
    assert "env: Object.fromEntries(VARIABLES.map((name) => [name, preserve()]))" in ts
