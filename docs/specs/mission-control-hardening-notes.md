# Mission Control hardening — build notes

Spec: `docs/specs/mission-control-hardening-spec.md` · Branch: `fix/mission-control-hardening`

## Environment

- No `python3.12` on the build machine; the virtual environment `.venv-mc/` uses
  Homebrew Python 3.14.3 (`python3 -m venv .venv-mc`). `.venv-mc/` is listed in
  `.git/info/exclude`, not `.gitignore`. `playwright install` was not run.

## Baseline (before any change)

`.venv-mc/bin/pytest mission_control/tests -q` → **3 failed, 987 passed**. All three
fail before any change and are not chased:

- `test_athlete_exit.py::TestTheWholeChain::test_every_field_survives_every_hop` and
  `test_plan_debrief.py::TestTheWholeChain::test_every_field_survives_every_hop` —
  need the Playwright Chromium browser, which was deliberately not installed.
- `test_pre_deploy_audit.py::TestPreDeployAudit::test_audit_passes_with_zero_failures` —
  the audit script finds four `mc-native-funnel*` CSS classes used in
  `analytics/index.html` but defined in no CSS file. Pre-existing, outside scope.

`node --test tests/test_fueling_lead_intake.mjs` → **44 passed, 0 failed**.

## Deviations

## Notes

