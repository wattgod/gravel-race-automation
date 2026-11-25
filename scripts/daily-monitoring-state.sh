#!/usr/bin/env bash
set -euo pipefail

source_checkout="$(git rev-parse --show-toplevel)"
state_dir="${MONITORING_STATE_DIR:?}"
profile="${2:-daily}"
case "$profile" in
  daily)
    state_ref=refs/heads/monitoring-state
    seed_paths=(data/gsc-snapshots data/cwv-snapshots reports)
    publish_paths=(':(glob)data/gsc-snapshots/*.json' ':(glob)data/cwv-snapshots/*.json' ':(glob)reports/????-??-??.md')
    ;;
  aeo)
    state_ref=refs/heads/aeo-state
    seed_paths=(data/aeo)
    publish_paths=(':(glob)data/aeo/aeo-weekly-????-??-??.json')
    ;;
  intel)
    state_ref=refs/heads/morning-intel-state
    if [[ ! "${SNAPSHOT_DATE:-}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
      echo "Missing or invalid completed snapshot date." >&2
      exit 1
    fi
    publish_paths=("data/intel-snapshots/$SNAPSHOT_DATE.json" "data/intel-snapshots/$SNAPSHOT_DATE.md")
    ;;
  *)
    echo "Unknown monitoring publication profile." >&2
    exit 2
    ;;
esac

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
      if [[ "$profile" != intel ]]; then
        # Seed existing history without attaching the source checkout's ancestry.
        git archive HEAD "${seed_paths[@]}" | tar -x -C "$state_dir"
      fi
    fi
    ;;
  publish)
    cd "$state_dir"
    if [[ "$profile" == intel ]]; then
      for path in "${publish_paths[@]}"; do
        if [[ ! -f "$path" || -L "$path" ]]; then
          echo "Expected both regular snapshot files." >&2
          exit 1
        fi
      done
    fi
    git add --all -- "${publish_paths[@]}"
    if git diff --cached --quiet; then exit 0; fi
    python3 "$source_checkout/scripts/validate-monitoring-publication.py" "$profile"
    git config user.name "github-actions[bot]"
    git config user.email "github-actions[bot]@users.noreply.github.com"
    git commit -m "chore: $profile monitoring $(date -u +%F)"
    git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin "HEAD:$state_ref"
    ;;
  *)
    echo "Usage: $0 {prepare|publish} [daily|aeo|intel]" >&2
    exit 2
    ;;
esac
