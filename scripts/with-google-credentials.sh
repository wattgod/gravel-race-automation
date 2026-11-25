#!/usr/bin/env bash
set -euo pipefail

: "${GOOGLE_CREDENTIALS_JSON:?Google service account credentials are required}"
umask 077
credentials_file=$(mktemp "${RUNNER_TEMP:?}/google-credentials.XXXXXX")
trap 'rm -f "$credentials_file"' EXIT
printf '%s' "$GOOGLE_CREDENTIALS_JSON" > "$credentials_file"
unset GOOGLE_CREDENTIALS_JSON
export GOOGLE_APPLICATION_CREDENTIALS="$credentials_file"
export GA4_CREDENTIALS="$credentials_file"

"$@"
