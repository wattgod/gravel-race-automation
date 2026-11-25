#!/usr/bin/env bash
set -euo pipefail

source_checkout="$(git rev-parse --show-toplevel)"
state_dir="${MONITORING_STATE_DIR:?}"
state_ref=refs/heads/monitoring-state

case "${1:-}" in
  prepare)
    remote="$(git remote get-url origin)"
    git init "$state_dir"
    git -C "$state_dir" remote add origin "$remote"
    if git ls-remote --exit-code origin "$state_ref" >/dev/null; then
      git -C "$state_dir" fetch --no-tags --depth=1 origin "$state_ref"
      git -C "$state_dir" checkout --detach FETCH_HEAD
    else
      status=$?
      if [ "$status" -ne 2 ]; then exit "$status"; fi
      # Seed existing history without attaching the source checkout's ancestry.
      git archive HEAD data/gsc-snapshots data/cwv-snapshots reports | tar -x -C "$state_dir"
    fi
    ;;
  publish)
    cd "$state_dir"
    git add --all -- ':(glob)data/gsc-snapshots/*.json' ':(glob)data/cwv-snapshots/*.json' ':(glob)reports/????-??-??.md'
    if git diff --cached --quiet; then exit 0; fi
    python "$source_checkout/scripts/validate-monitoring-publication.py"
    git config user.name "github-actions[bot]"
    git config user.email "github-actions[bot]@users.noreply.github.com"
    git commit -m "chore: daily monitoring $(date -u +%F)"
    git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin "HEAD:$state_ref"
    ;;
  *)
    echo "Usage: $0 prepare | publish" >&2
    exit 2
    ;;
esac
