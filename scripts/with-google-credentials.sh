#!/usr/bin/env bash
set -euo pipefail

umask 077
credentials_file=$(mktemp "${RUNNER_TEMP:?}/google-credentials.XXXXXX")
trap 'rm -f "$credentials_file"' EXIT
# An empty credential file lets callers report a missing GA4 collector
# without falling back to another identity or dropping their other reports.
printf '%s' "${GOOGLE_CREDENTIALS_JSON:-}" > "$credentials_file"
unset GOOGLE_CREDENTIALS_JSON
export GOOGLE_APPLICATION_CREDENTIALS="$credentials_file"
export GA4_CREDENTIALS="$credentials_file"

"$@"
