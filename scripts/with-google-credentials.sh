#!/usr/bin/env bash
set -euo pipefail

required=false
if [[ "${1:-}" == "--require-service-account" ]]; then
  required=true
  shift
  : "${GOOGLE_CREDENTIALS_JSON:?Google service account credentials are required}"
fi
umask 077
credentials_file=$(mktemp "${RUNNER_TEMP:?}/google-credentials.XXXXXX")
trap 'rm -f "$credentials_file"' EXIT
# An empty credential file lets callers report a missing GA4 collector
# without falling back to another identity or dropping their other reports.
printf '%s' "${GOOGLE_CREDENTIALS_JSON:-}" > "$credentials_file"
unset GOOGLE_CREDENTIALS_JSON
export GOOGLE_APPLICATION_CREDENTIALS="$credentials_file"
export GA4_CREDENTIALS="$credentials_file"

if [[ "$required" == true ]]; then
  python3 - "$credentials_file" <<'PY'
import json
import sys
from pathlib import Path

try:
    credentials = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, ValueError):
    raise SystemExit("Google service account credentials are not readable JSON")
required_fields = {"client_email", "private_key", "token_uri"}
if not isinstance(credentials, dict) or not required_fields.issubset(credentials):
    raise SystemExit("Google service account credentials have an invalid shape")
PY
fi

"$@"
