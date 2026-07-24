#!/usr/bin/env python3
"""Deterministic weekly AEO monitor for Gravel God, Roadie Labs, and XC Ski Labs.

The default command writes one public, aggregate-only artifact to data/aeo/.
Collector failures are represented in that artifact and deliberately do not
make the collection command fail; CI validates after committing so partial
artifacts survive.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.aeo_agents import (
        NON_AI_SUPPRESSION_LIST,
        REFERRAL_SOURCE_PATTERN,
        REFERRAL_SOURCE_RE,
        TAXONOMY_VERSION,
        UNKNOWN_CANDIDATE_PATTERN,
        USER_AGENT_TAXONOMY,
    )
except ImportError:  # Direct execution: python3 scripts/aeo_weekly.py
    from aeo_agents import (  # type: ignore
        NON_AI_SUPPRESSION_LIST,
        REFERRAL_SOURCE_PATTERN,
        REFERRAL_SOURCE_RE,
        TAXONOMY_VERSION,
        UNKNOWN_CANDIDATE_PATTERN,
        USER_AGENT_TAXONOMY,
    )

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = PROJECT_ROOT / "data" / "aeo"
SCHEMA_VERSION = 1
DEFAULT_LOG_CEILING_BYTES = 500 * 1024 * 1024
SSH_TIMEOUT_SECONDS = 270
MAX_UNKNOWN_CANDIDATES = 15
MAX_UNKNOWN_SAMPLE_CHARS = 120

BRANDS = {
    "gravelgod": {
        "domain": "gravelgodcycling.com",
        "env_prefix": "",
        "ga4_property_env": "GG_GA4_PROPERTY_ID",
    },
    "roadie": {
        "domain": "roadielabs.com",
        "env_prefix": "RL_",
        "ga4_property_env": "RL_GA4_PROPERTY_ID",
    },
    "xcski": {
        "domain": "xcskilabs.com",
        "env_prefix": "XC_",
        "ga4_property_env": None,
    },
}

_STATUS_CLASSES = ("2xx", "3xx", "4xx", "5xx")
_UA_BUCKETS = ("user_fetch", "search_index", "training_crawl")
_SAFE_HOST = re.compile(r"^[A-Za-z0-9.-]+$")
_SAFE_USER = re.compile(r"^[A-Za-z0-9._-]+$")


def completed_windows(run_date: date) -> tuple[dict[str, str], dict[str, str]]:
    """Return current D-7..D-1 and prior D-14..D-8 completed-day windows."""
    return (
        {
            "start": (run_date - timedelta(days=7)).isoformat(),
            "end": (run_date - timedelta(days=1)).isoformat(),
        },
        {
            "start": (run_date - timedelta(days=14)).isoformat(),
            "end": (run_date - timedelta(days=8)).isoformat(),
        },
    )


def completed_log_dates(run_date: date) -> list[str]:
    """Exactly seven filenames, oldest to newest, excluding the current day."""
    return [
        (run_date - timedelta(days=offset)).isoformat()
        for offset in range(7, 0, -1)
    ]


def _error(message: str) -> str:
    return str(message).replace("\n", " ")[:400]


def _ga4_dependencies():
    """Import the only non-stdlib dependency lazily, inside the GA4 path."""
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        DateRange,
        Dimension,
        Metric,
        RunReportRequest,
    )

    return BetaAnalyticsDataClient, DateRange, Dimension, Metric, RunReportRequest


def collect_ga4_referrals(
        brand: str,
        current_window: dict[str, str],
        prior_window: dict[str, str]) -> dict[str, Any]:
    """Collect AI-associated GA4 session sources for one configured brand."""
    meta = BRANDS[brand]
    property_env = meta["ga4_property_env"]
    if not property_env:
        return {"status": "not_configured"}

    property_id = os.environ.get(str(property_env), "").strip()
    if brand == "gravelgod" and not property_id:
        property_id = os.environ.get("GA4_PROPERTY_ID", "").strip()
    property_id = property_id.removeprefix("properties/")
    if not property_id:
        raise RuntimeError(f"{property_env} not set")

    creds = os.environ.get(
        "GA4_CREDENTIALS", str(PROJECT_ROOT / "ga4-credentials.json"))
    os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", creds)
    client_cls, date_range_cls, dimension_cls, metric_cls, request_cls = (
        _ga4_dependencies())
    client = client_cls()

    def run(window: dict[str, str]) -> dict[str, int]:
        response = client.run_report(request_cls(
            property=f"properties/{property_id}",
            date_ranges=[date_range_cls(
                start_date=window["start"], end_date=window["end"])],
            dimensions=[dimension_cls(name="sessionSource")],
            metrics=[metric_cls(name="sessions")],
            limit=250,
        ))
        sources: dict[str, int] = {}
        for row in response.rows:
            source = row.dimension_values[0].value
            if REFERRAL_SOURCE_RE.search(source):
                sources[source] = sources.get(source, 0) + int(
                    row.metric_values[0].value)
        return dict(sorted(sources.items()))

    return {
        "status": "ok",
        "referral_regex_version": TAXONOMY_VERSION,
        "referral_regex": REFERRAL_SOURCE_PATTERN,
        "current_window": run(current_window),
        "prior_window": run(prior_window),
    }


def _awk_string(value: str) -> str:
    """Quote a fixed taxonomy token for an awk string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_server_script() -> str:
    """Build the one aggregate-only shell program sent to each brand host."""
    bucket_checks = []
    for bucket in _UA_BUCKETS:
        condition = " || ".join(
            f'index(ua_lower, "{_awk_string(token.lower())}")'
            for token in USER_AGENT_TAXONOMY[bucket]
        )
        bucket_checks.append(
            f'if ({condition}) {{ bucket = "{bucket}" }}')
    known_condition = " || ".join(
        f'index(ua_lower, "{_awk_string(token.lower())}")'
        for tokens in USER_AGENT_TAXONOMY.values()
        for token in tokens
    )
    suppressed_condition = " || ".join(
        f'index(ua_lower, "{_awk_string(token.lower())}")'
        for token in NON_AI_SUPPRESSION_LIST
    )
    unknown_awk_pattern = UNKNOWN_CANDIDATE_PATTERN.removeprefix("(?i)")

    return f"""#!/usr/bin/env bash
set -o pipefail
domain="$1"
ceiling="$2"
shift 2
dates=("$@")
log_dir="$HOME/www/$domain/logs"
files=()
for day in "${{dates[@]}}"; do
  log_file="$log_dir/$domain-$day.gz"
  if [ -f "$log_file" ]; then
    files+=("$log_file")
  else
    printf 'MISSING\\t%s\\n' "$day"
  fi
done
compressed_bytes=0
if [ "${{#files[@]}}" -gt 0 ]; then
  compressed_bytes="$(du -cb -- "${{files[@]}}" 2>/dev/null | tail -n 1 | cut -f1)"
fi
case "$compressed_bytes" in
  ''|*[!0-9]*)
    printf 'ERROR\\tdu_failed\\t%s\\n' "$compressed_bytes"
    exit 2
    ;;
esac
printf 'SIZE\\t%s\\t%s\\n' "$compressed_bytes" "$ceiling"
if [ "$compressed_bytes" -gt "$ceiling" ]; then
  printf 'ERROR\\tcompressed_size_exceeds_ceiling\\t%s\\n' "$compressed_bytes"
  exit 3
fi
for day in "${{dates[@]}}"; do
  log_file="$log_dir/$domain-$day.gz"
  [ -f "$log_file" ] || continue
  if ! gzip -cd -- "$log_file" | awk -v day="$day" '
    BEGIN {{
      user_fetch = 0
      search_index = 0
      training_crawl = 0
      status_count["2xx"] = 0
      status_count["3xx"] = 0
      status_count["4xx"] = 0
      status_count["5xx"] = 0
    }}
    {{
      quote_parts = split($0, quoted, "\\"")
      if (quote_parts < 6) next
      request = quoted[2]
      status_text = quoted[3]
      ua = quoted[6]
      split(request, request_parts, " ")
      path = request_parts[2]
      sub(/\\?.*$/, "", path)
      status_part_count = split(status_text, status_parts, " ")
      status = ""
      for (i = 1; i <= status_part_count; i++) {{
        if (status_parts[i] ~ /^[0-9][0-9][0-9]$/) {{
          status = status_parts[i]
          break
        }}
      }}
      ua_lower = tolower(ua)
      bucket = ""
      {" else ".join(bucket_checks)}
      if (bucket != "") {{
        bucket_count[bucket]++
      }}
      if (bucket == "user_fetch" && status ~ /^2/) {{
        path_count[path]++
      }}
      if (path == "/llms.txt" || path ~ /\\.md$/) {{
        status_class = substr(status, 1, 1) "xx"
        if (status_class in status_count) status_count[status_class]++
      }}
      known = ({known_condition})
      suppressed = ({suppressed_condition})
      if (!known && !suppressed &&
          ua_lower ~ /{unknown_awk_pattern}/) {{
        gsub(/[\\t\\r\\n]/, " ", ua)
        sample = substr(ua, 1, {MAX_UNKNOWN_SAMPLE_CHARS})
        unknown_count[sample]++
      }}
    }}
    END {{
      printf "DAY\\t%s\\tuser_fetch\\t%d\\n", day, bucket_count["user_fetch"]
      printf "DAY\\t%s\\tsearch_index\\t%d\\n", day, bucket_count["search_index"]
      printf "DAY\\t%s\\ttraining_crawl\\t%d\\n", day, bucket_count["training_crawl"]
      printf "STATUS\\t%s\\t2xx\\t%d\\n", day, status_count["2xx"]
      printf "STATUS\\t%s\\t3xx\\t%d\\n", day, status_count["3xx"]
      printf "STATUS\\t%s\\t4xx\\t%d\\n", day, status_count["4xx"]
      printf "STATUS\\t%s\\t5xx\\t%d\\n", day, status_count["5xx"]
      for (path in path_count)
        printf "PATH\\t%s\\t%d\\n", path, path_count[path]
      for (sample in unknown_count)
        printf "UNKNOWN\\t%s\\t%d\\n", sample, unknown_count[sample]
    }}
  '; then
    printf 'ERROR\\tgzip_or_awk_failed\\t%s\\n' "$day"
    exit 4
  fi
done
"""


SERVER_SCRIPT = build_server_script()


def _log_ceiling_bytes() -> int:
    raw_bytes = os.environ.get("AEO_LOG_CEILING_BYTES", "").strip()
    raw_mb = os.environ.get("AEO_LOG_CEILING_MB", "").strip()
    try:
        if raw_bytes:
            value = int(raw_bytes)
        elif raw_mb:
            value = int(raw_mb) * 1024 * 1024
        else:
            value = DEFAULT_LOG_CEILING_BYTES
    except ValueError as exc:
        raise RuntimeError("AEO log ceiling must be an integer") from exc
    if value <= 0:
        raise RuntimeError("AEO log ceiling must be positive")
    return value


def _ssh_config(brand: str) -> dict[str, str]:
    prefix = str(BRANDS[brand]["env_prefix"])
    host = os.environ.get(f"{prefix}SSH_HOST", "").strip()
    user = os.environ.get(f"{prefix}SSH_USER", "").strip()
    port = os.environ.get(f"{prefix}SSH_PORT", "18765").strip()
    key_path = os.environ.get(f"{prefix}SSH_KEY_PATH", "").strip()
    missing = [
        name for name, value in (
            (f"{prefix}SSH_HOST", host),
            (f"{prefix}SSH_USER", user),
            (f"{prefix}SSH_KEY_PATH", key_path),
        ) if not value
    ]
    if missing:
        raise RuntimeError(f"missing SSH config: {', '.join(missing)}")
    if not _SAFE_HOST.fullmatch(host):
        raise RuntimeError(f"invalid {prefix}SSH_HOST")
    if not _SAFE_USER.fullmatch(user):
        raise RuntimeError(f"invalid {prefix}SSH_USER")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise RuntimeError(f"invalid {prefix}SSH_PORT")
    return {"host": host, "user": user, "port": port, "key_path": key_path}


def parse_server_tsv(
        output: str, expected_dates: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse aggregate server TSV; never accepts raw log records."""
    expected = set(expected_dates)
    days = {
        day: {
            **{bucket: 0 for bucket in _UA_BUCKETS},
            "status_buckets": {status: 0 for status in _STATUS_CLASSES},
        }
        for day in expected_dates
    }
    seen_days: set[str] = set()
    missing: set[str] = set()
    paths: dict[str, int] = {}
    unknown: dict[str, int] = {}
    compressed_bytes: int | None = None
    remote_error: str | None = None

    for line in output.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        record = parts[0]
        try:
            if record == "SIZE" and len(parts) == 3:
                compressed_bytes = int(parts[1])
            elif record == "MISSING" and len(parts) == 2:
                if parts[1] not in expected:
                    raise ValueError("unexpected missing-log date")
                missing.add(parts[1])
            elif record == "DAY" and len(parts) == 4:
                day, bucket, raw_count = parts[1:]
                if day not in expected or bucket not in _UA_BUCKETS:
                    raise ValueError("unexpected DAY key")
                days[day][bucket] = int(raw_count)
                seen_days.add(day)
            elif record == "STATUS" and len(parts) == 4:
                day, status_class, raw_count = parts[1:]
                if day not in expected or status_class not in _STATUS_CLASSES:
                    raise ValueError("unexpected STATUS key")
                days[day]["status_buckets"][status_class] = int(raw_count)
                seen_days.add(day)
            elif record == "PATH" and len(parts) == 3:
                path = parts[1].split("?", 1)[0]
                if "?" in path:
                    raise ValueError("query string survived path sanitization")
                paths[path] = paths.get(path, 0) + int(parts[2])
            elif record == "UNKNOWN" and len(parts) == 3:
                sample = parts[1][:MAX_UNKNOWN_SAMPLE_CHARS]
                unknown[sample] = unknown.get(sample, 0) + int(parts[2])
            elif record == "ERROR" and len(parts) >= 2:
                remote_error = ": ".join(parts[1:])
            else:
                raise ValueError(f"unexpected TSV record {record!r}")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid server TSV line: {line[:160]}") from exc

    for day in expected - seen_days - missing:
        missing.add(day)
    present_days = {
        day: values for day, values in days.items() if day not in missing
    }
    status_buckets = {
        status: sum(
            int(values["status_buckets"][status]) for values in present_days.values())
        for status in _STATUS_CLASSES
    }
    top_paths = [
        {"path": path, "hits": count}
        for path, count in sorted(paths.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]
    candidates = [
        {"user_agent": sample, "count": count}
        for sample, count in sorted(
            unknown.items(), key=lambda item: (-item[1], item[0].lower()))
    ]
    logs = {
        "status": "error" if remote_error else "ok",
        "days": present_days,
        "missing_log_dates": sorted(missing),
        "status_buckets": status_buckets,
        "compressed_bytes": compressed_bytes,
    }
    if remote_error:
        logs["error"] = remote_error
    return {"logs": logs, "top_user_fetch_paths": top_paths}, candidates


def collect_log_analysis(
        brand: str, dates: list[str]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run one bounded SSH subprocess and parse only its aggregate TSV."""
    config = _ssh_config(brand)
    ceiling = _log_ceiling_bytes()
    domain = str(BRANDS[brand]["domain"])
    command = [
        "ssh",
        "-i", config["key_path"],
        "-p", config["port"],
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=30",
        "-o", "StrictHostKeyChecking=accept-new",
        f"{config['user']}@{config['host']}",
        "bash", "-s", "--", domain, str(ceiling), *dates,
    ]
    try:
        result = subprocess.run(
            command,
            input=SERVER_SCRIPT,
            capture_output=True,
            text=True,
            timeout=SSH_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"SSH log collector timed out after {SSH_TIMEOUT_SECONDS}s") from exc
    parsed, candidates = parse_server_tsv(result.stdout, dates)
    if result.returncode != 0:
        logs = parsed["logs"]
        logs["status"] = "error"
        logs.setdefault(
            "error",
            f"SSH log collector exited {result.returncode}")
    return parsed, candidates


def _empty_log_error(message: str, dates: list[str]) -> dict[str, Any]:
    return {
        "logs": {
            "status": "error",
            "error": _error(message),
            "days": {},
            "missing_log_dates": list(dates),
            "status_buckets": {status: 0 for status in _STATUS_CLASSES},
            "compressed_bytes": None,
        },
        "top_user_fetch_paths": [],
    }


def _merge_unknown_candidates(
        by_brand: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    for brand, candidates in by_brand.items():
        for candidate in candidates:
            sample = str(candidate["user_agent"])[:MAX_UNKNOWN_SAMPLE_CHARS]
            count = int(candidate["count"])
            item = combined.setdefault(
                sample, {"user_agent": sample, "count": 0, "brands": {}})
            item["count"] += count
            item["brands"][brand] = item["brands"].get(brand, 0) + count
    return sorted(
        combined.values(),
        key=lambda item: (-int(item["count"]), str(item["user_agent"]).lower()),
    )[:MAX_UNKNOWN_CANDIDATES]


def collect_weekly(now: datetime | None = None) -> dict[str, Any]:
    """Run all collectors fail-soft and return a schema-versioned artifact."""
    generated = now or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    generated = generated.astimezone(timezone.utc)
    run_date = generated.date()
    current_window, prior_window = completed_windows(run_date)
    dates = completed_log_dates(run_date)
    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": generated.isoformat().replace("+00:00", "Z"),
        "taxonomy_version": TAXONOMY_VERSION,
        "current_window": current_window,
        "prior_window": prior_window,
        "brands": {},
        "unknown_agent_candidates": [],
    }
    unknown_by_brand: dict[str, list[dict[str, Any]]] = {}
    for brand in BRANDS:
        try:
            ga4 = collect_ga4_referrals(brand, current_window, prior_window)
        except Exception as exc:
            ga4 = {"status": "error", "error": _error(f"{type(exc).__name__}: {exc}")}
        try:
            log_result, candidates = collect_log_analysis(brand, dates)
        except Exception as exc:
            log_result = _empty_log_error(
                f"{type(exc).__name__}: {exc}", dates)
            candidates = []
        artifact["brands"][brand] = {"ga4": ga4, **log_result}
        unknown_by_brand[brand] = candidates
    artifact["unknown_agent_candidates"] = _merge_unknown_candidates(unknown_by_brand)
    return artifact


def artifact_path(artifact: dict[str, Any], output_dir: Path = ARTIFACT_DIR) -> Path:
    generated = datetime.fromisoformat(
        str(artifact["generated_at_utc"]).replace("Z", "+00:00"))
    return output_dir / f"aeo-weekly-{generated.date().isoformat()}.json"


def validate_artifact(
        artifact: Any,
        path: Path | None = None,
        require_all_ok: bool = False) -> list[str]:
    """Return contract violations; an empty list means the artifact is valid."""
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["artifact root must be an object"]
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if artifact.get("taxonomy_version") != TAXONOMY_VERSION:
        errors.append(f"taxonomy_version must be {TAXONOMY_VERSION}")
    try:
        generated = datetime.fromisoformat(
            str(artifact["generated_at_utc"]).replace("Z", "+00:00"))
        if generated.tzinfo is None:
            errors.append("generated_at_utc must include a timezone")
        generated_date = generated.date().isoformat()
    except (KeyError, TypeError, ValueError):
        errors.append("generated_at_utc must be an ISO timestamp")
        generated_date = None
    if path is not None and generated_date is not None:
        expected_name = f"aeo-weekly-{generated_date}.json"
        if path.name != expected_name:
            errors.append(
                f"filename {path.name!r} does not match {expected_name!r}")
    for window_name in ("current_window", "prior_window"):
        window = artifact.get(window_name)
        if not isinstance(window, dict) or set(window) != {"start", "end"}:
            errors.append(f"{window_name} must contain start and end")
    brands = artifact.get("brands")
    if not isinstance(brands, dict):
        errors.append("brands must be an object")
        brands = {}
    for brand in BRANDS:
        value = brands.get(brand)
        if not isinstance(value, dict):
            errors.append(f"brands.{brand} must be an object")
            continue
        ga4 = value.get("ga4")
        logs = value.get("logs")
        valid_ga4 = {"ok", "error"}
        if brand == "xcski":
            valid_ga4.add("not_configured")
        if not isinstance(ga4, dict) or ga4.get("status") not in valid_ga4:
            errors.append(f"brands.{brand}.ga4 has invalid status")
        if not isinstance(logs, dict) or logs.get("status") not in {"ok", "error"}:
            errors.append(f"brands.{brand}.logs has invalid status")
        if not isinstance(value.get("top_user_fetch_paths"), list):
            errors.append(f"brands.{brand}.top_user_fetch_paths must be a list")
        else:
            for item in value["top_user_fetch_paths"]:
                if not isinstance(item, dict) or "?" in str(item.get("path", "")):
                    errors.append(
                        f"brands.{brand}.top_user_fetch_paths contains an invalid path")
                    break
        if require_all_ok:
            expected_ga4 = "not_configured" if brand == "xcski" else "ok"
            if isinstance(ga4, dict) and ga4.get("status") != expected_ga4:
                errors.append(f"brands.{brand}.ga4 collector not ok")
            if isinstance(logs, dict) and logs.get("status") != "ok":
                errors.append(f"brands.{brand}.logs collector not ok")
    candidates = artifact.get("unknown_agent_candidates")
    if not isinstance(candidates, list):
        errors.append("unknown_agent_candidates must be a list")
    else:
        if len(candidates) > MAX_UNKNOWN_CANDIDATES:
            errors.append(
                f"unknown_agent_candidates exceeds {MAX_UNKNOWN_CANDIDATES}")
        for item in candidates:
            if (
                    not isinstance(item, dict)
                    or len(str(item.get("user_agent", ""))) > MAX_UNKNOWN_SAMPLE_CHARS):
                errors.append("unknown_agent_candidates contains an invalid sample")
                break
    return errors


def write_artifact(
        artifact: dict[str, Any], output_dir: Path = ARTIFACT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_path(artifact, output_dir)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    errors = validate_artifact(artifact, path=path)
    if errors:
        raise ValueError("; ".join(errors))
    return path


def _validate_path(path: Path, require_all_ok: bool) -> int:
    try:
        artifact = json.loads(path.read_text())
    except Exception as exc:
        print(f"invalid artifact: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    errors = validate_artifact(
        artifact, path=path, require_all_ok=require_all_ok)
    if errors:
        for error in errors:
            print(f"invalid artifact: {error}", file=sys.stderr)
        return 1
    print(f"valid artifact: {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", type=Path, help="validate one artifact")
    parser.add_argument(
        "--validate-latest", action="store_true",
        help="validate the newest data/aeo artifact")
    parser.add_argument(
        "--require-all-ok", action="store_true",
        help="validation also requires every configured collector to be ok")
    parser.add_argument("--output-dir", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args()
    if args.validate and args.validate_latest:
        parser.error("choose either --validate or --validate-latest")
    if args.validate_latest:
        paths = sorted(args.output_dir.glob("aeo-weekly-*.json"))
        if not paths:
            print("invalid artifact: no AEO artifacts found", file=sys.stderr)
            return 1
        return _validate_path(paths[-1], args.require_all_ok)
    if args.validate:
        return _validate_path(args.validate, args.require_all_ok)

    artifact = collect_weekly()
    path = write_artifact(artifact, args.output_dir)
    print(f"artifact: {path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
