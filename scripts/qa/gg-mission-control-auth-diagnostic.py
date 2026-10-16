#!/usr/bin/env python3
"""Temporary read-only CI diagnostic. Never invoke the Morning Intel collector."""
import base64
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

EXPECTED_PROJECT = "dnlfmceqhvopwztnbnke"
EXPECTED_URL = "https://dnlfmceqhvopwztnbnke.supabase.co"
OUTPUT = Path("gg-mission-control-auth-safe.json")
SOURCE_PINS = {'mission_control/config.py': '9b3fe5cd608e6bdff936a86c590ad504862dd3e5d375d00d747c252dba4b02ac', 'mission_control/supabase_client.py': 'a7f9aef4d597627782c244e818c3604bd749dea319c7407e1b92ca225c7a8d87', 'supabase/migrations/20260216000002_mission_control_v2.sql': 'c1a83d17c4ddcc9f5446ffaff96128d0916cc1578492a19400b6b99c991820c4'}
CODES = {"401", "403", "404", "429", "500", "502", "503", "504", "PGRST301", "PGRST302", "PGRST303", "PGRST205"}
EXCEPTIONS = {"APIError", "HTTPError", "HTTPStatusError", "ConnectTimeout", "ReadTimeout", "PoolTimeout", "ConnectError", "ReadError", "RemoteProtocolError", "TimeoutError", "RuntimeError", "ValueError", "ImportError", "ModuleNotFoundError"}


def kind(exc):
    name = type(exc).__name__
    return name if name in EXCEPTIONS else "Other"


def legacy_binding(key):
    result = {"legacyJwtShape": False, "unverifiedClaimsProjectMatches": False,
              "unverifiedClaimsRoleServiceRole": False}
    parts = key.split(".")
    if len(parts) != 3 or len(parts[1]) > 16000:
        return result
    try:
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
        if isinstance(payload, dict):
            result.update(legacyJwtShape=True,
                          unverifiedClaimsProjectMatches=payload.get("ref") == EXPECTED_PROJECT,
                          unverifiedClaimsRoleServiceRole=payload.get("role") == "service_role")
    except (ValueError, TypeError):
        pass
    return result


def main(proof):
    phase = os.environ.get("AUTH_DIAGNOSTIC_PHASE", "")
    alias = os.environ.get("CONSUMER_SECRET_NAME", "")
    sha = os.environ.get("GITHUB_SHA", "")
    expected = os.environ.get("EXPECTED_SOURCE_SHA", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    if alias not in {"SUPABASE_SERVICE_KEY", "SUPABASE_SERVICE_ROLE_KEY"} or phase not in {"baseline", "recovery"} or not re.fullmatch(r"[a-f0-9]{40}", sha) or sha != expected or not re.fullmatch(r"[1-9][0-9]*", run_id) or not re.fullmatch(r"[1-9][0-9]*", attempt):
        proof["guardFailure"] = "INVALID_WORKFLOW_BINDING"
        return 2
    proof.update(phase=phase, consumerSecretName=alias, sourceSha=sha, runId=run_id, runAttempt=int(attempt))
    root = Path.cwd()
    if (root / ".env").exists():
        proof["guardFailure"] = "UNEXPECTED_DOTENV_FILE"
        return 2
    if not all(hashlib.sha256((root / path).read_bytes()).hexdigest() == digest for path, digest in SOURCE_PINS.items()):
        proof["guardFailure"] = "REVIEWED_SOURCE_DRIFT"
        return 2
    proof["reviewedSourceMatches"] = True
    # Import the actual reviewed configuration and SDK wrapper; no collector import.
    from mission_control import supabase_client as db
    from mission_control.config import SUPABASE_URL, SUPABASE_SERVICE_KEY
    proof["projectUrlMatches"] = SUPABASE_URL == EXPECTED_URL
    proof["keyPresent"] = bool(SUPABASE_SERVICE_KEY)
    proof.update(legacy_binding(SUPABASE_SERVICE_KEY))
    if not proof["projectUrlMatches"] or not proof["keyPresent"]:
        proof["guardFailure"] = "PROJECT_OR_KEY_BINDING_FAILED"
        return 2
    # Legacy claims are unverified hints, never authorization proof.
    if proof["legacyJwtShape"] and not (proof["unverifiedClaimsProjectMatches"] and proof["unverifiedClaimsRoleServiceRole"]):
        proof["guardFailure"] = "LEGACY_CLAIMS_BINDING_FAILED"
        return 2
    proof["sdkVersion"] = importlib.metadata.version("supabase")
    try:
        result = db.get_client().table("gg_sequence_enrollments").select("id").limit(0).execute()
        proof["sdkQuerySucceeded"] = True
        proof["sdkRowsZero"] = isinstance(result.data, list) and result.data == []
    except Exception as exc:
        code = str(getattr(exc, "code", ""))
        proof.update(sdkQuerySucceeded=False, sdkRowsZero=False,
                     sdkErrorCode=code if code in CODES else "OTHER", sdkExceptionType=kind(exc))
    # Exact approved endpoint; no Authorization header, no redirects, no row data.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    request = urllib.request.Request(EXPECTED_URL + "/rest/v1/gg_sequence_enrollments?select=id&limit=0",
                                     headers={"apikey": SUPABASE_SERVICE_KEY, "Accept": "application/json"}, method="GET")
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=10) as response:
            proof["restStatus"] = response.status
            raw = response.read(1025)
            proof["restRowsZero"] = len(raw) <= 1024 and json.loads(raw) == []
    except urllib.error.HTTPError as exc:
        proof.update(restStatus=exc.code, restRowsZero=False, restExceptionType="HTTPError")
        exc.close()
    except Exception as exc:
        proof.update(restStatus=None, restRowsZero=False, restExceptionType=kind(exc))
    proof["recoveryVerified"] = (proof["projectUrlMatches"] and proof.get("sdkQuerySucceeded") is True and proof.get("sdkRowsZero") is True and proof.get("restStatus") == 200 and proof.get("restRowsZero") is True)
    proof["outcome"] = "RECOVERY_VERIFIED" if phase == "recovery" and proof["recoveryVerified"] else "DIAGNOSTIC_ONLY" if phase == "baseline" else "RECOVERY_FAILED"
    return 0 if phase == "baseline" or proof["recoveryVerified"] else 1


if __name__ == "__main__":
    os.umask(0o077)
    # Running by path puts scripts/qa first, so explicitly use the reviewed checkout.
    sys.path.insert(0, str(Path.cwd()))
    proof = {"schemaVersion": 1, "diagnostic": "GG_MISSION_CONTROL_AUTH", "providerWrites": 0, "outcome": "GUARD_FAILED"}
    try:
        exit_code = main(proof)
    except Exception as exc:
        proof.update(guardFailure="DIAGNOSTIC_INTERNAL_ERROR", exceptionType=kind(exc))
        exit_code = 2
    # Safe allowlisted metadata only, not exception strings, response bodies, or credentials.
    with OUTPUT.open("x", encoding="utf-8") as output:
        json.dump(proof, output, indent=2)
        output.write("\n")
    print(json.dumps(proof, separators=(",", ":")))
    sys.exit(exit_code)
