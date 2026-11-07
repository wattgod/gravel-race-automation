# Scoped race release runner

`Deploy Race Page` now prepares a reviewable race-only release by default. It
never requires SSH or a private plans database to validate. Selecting `publish`
is an explicit production action and is restricted to the exact current main
commit. This workflow does not merge code or bypass branch protection.

## Scope and source contracts

- `scope=single` requires one active canonical `slug`; `scope=all` requires no slug.
- Published files are only selected race HTML, generated hashed CSS/JS/fonts,
  corresponding prep-kit HTML, and corresponding Markdown profiles.
- The current first-pass page contains an active custom-plan CTA for eligible
  races. The runner checks its exact destination against the existing generator
  helper and checks suppression for blocked/paused/ineligible races. Legacy TP
  commerce stays unmounted. Exact source-backed research references inside the
  citations section remain allowed; extra links or commerce controls cannot
  reuse that exception. The old workflow's required TP marketplace-link
  grep did not describe the current rendered page.
- No private plan DB or workout material is acquired, uploaded or passed to a
  review model. The current active page path does not call `build_plan_ladder`.

## Prepare without publishing

From a clean committed checkout with Python requirements and Chromium installed:

```sh
set -euo pipefail
python -c 'from scripts.prepare_race_release import disk_guard; disk_guard()'
python scripts/prepare_race_release.py prepare \
  --release-dir /absolute/fresh/release-directory --scope all
```

For one race, use `--scope single --slug barry-roubaix`. The output directory,
`wordpress/output` and `race-photos` must not already exist. The runner refuses
to overwrite another build or validation input. Preparation is designed for a
fresh disposable checkout/CI runner, rather than a protected working directory.

Preparation recovers the public sitemap and every listed training guide. Each
must return HTTP 200 at its exact canonical URL and contain intact guide HTML.
The genuine HTML files supply the Markdown generator's training-guide inventory.
It also recovers every required photo/GIF from exact source-profile public paths
with no redirects, image type/signature/length checks and SHA-256 receipts.
Media recovery permits four workers, 20 MiB per file and 2 GiB overall; guide
recovery permits 2 MiB per guide and 1 GiB overall. Any invalid/missing input
fails preparation. Files are not fabricated to satisfy a validator.

Existing generators build the selected package and real blog validation inputs
in separate directories. Local validation aliases use real ignored directories
and file links so recursive validators see all assets. The media alias is installed before any generator runs. Media and validation
blogs never enter the publishing package. Required media is recovered for every
profile in race-data, including a tombstoned profile if one is present, because
the unmodified YouTube validator scans all those profiles. Stale references must
be repaired through the source-data workflow; the release runner does not hide
them.

Every Python subprocess checks that at least 5 GiB is free. The runner executes
full `tests/`, the same Mission Control suites as the repository CI, then
`preflight.py --skip-tests` and full `preflight_quality.py`. The skip option here
avoids executing the already completed full pytest suite twice; no required
check is waived. Existing validator warnings remain visible in uploaded logs;
a successful check with missing optional tooling does not prove that tooling's
checks ran. A failed gate produces no admitted release manifest.

The manifest records exact source commit/tree, scope, file sizes and SHA-256
hashes after gates pass. Tracked source must stay unchanged throughout.
Artifacts include only the public package and receipts, excluding recovered
media, guide HTML and the larger validation tree.

## Publish the same validated bytes

After the destination Endure release and the source change have been accepted,
run the manual workflow from main with `mode=publish` and the intended scope.
The workflow builds and validates first. Only then does it create the runner's
SSH key from existing repository secrets. It does not write secrets or dispatch
another workflow. The key is removed by an unconditional cleanup step.

Immediately before the remote publisher runs, the runner verifies the package
manifest, clean exact checkout, `GITHUB_REF`, `GITHUB_SHA` and live origin/main
SHA. If main moved, prepare a new release; there is no force or override option.
Publish mode uses the shared `publish-site` concurrency group to serialize
against the broad publishing workflow. Validate mode uses a unique per-run group
so it cannot cancel a queued publish. The existing publisher also retains its
server-side lock.

The only upload command is the existing scoped `--sync-pages` path with explicit
prep-kit/Markdown directories and `--purge-cache`. Both companion gates remain
enabled; `--deploy-all`, unrelated page flags, and regeneration after validation
are excluded. Every resulting public page, companion and shared asset must then
match its admitted SHA-256 bytes at the exact URL. Verification uses at most four
requests in flight, a ten-minute overall deadline and incremental progress
receipts. A partial upload or failed purge fails the publisher before live
verification starts; the admitted manifest and workflow log survive, but there
may be no live-verification receipt. A live-verification failure preserves its
progress receipt for repair.

A validate-mode run is not production acceptance. A green source CI run is not
proof of a successfully rendered or authenticated Endure continuation. Keep
those release receipts separate.

## Local validation inputs and cleanup

The generated `wordpress/output` and `race-photos` directories contain only file
links into this release's validation inputs. Use a disposable worktree for local
preparation. Before any cleanup, verify ownership and link targets; do not remove
another checkout's artifacts or the external source/cache. Publication never
uses these alias directories as its payload.
