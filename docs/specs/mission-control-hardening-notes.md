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

### Change 3 — admin login
- The failed-login limit is global (every request behind Railway's proxy carries the
  proxy's address). Anyone can therefore lock the login form for up to 10 minutes;
  Bearer access still works. Accepted trade-off.
- The signed-out redirect is decided inside `require_admin`: a `GET` that accepts
  `text/html`, carries no `Authorization` header and is not under `/api/` or
  `/webhooks/` gets a 303 to `/login`; any request with `HX-Request` gets a 401 with
  `HX-Redirect: /login`. Everything else keeps the JSON 401.

### Change 4 — health checks
- The server-start record lives in **`gg_settings`** under key `mc_last_start_utc`
  (one row, overwritten on each start), not `gg_audit_log`. It is read before it is
  written, off the main thread; a database failure counts as "not the first start".
- `/health` checks the five settings by name in the process environment; all five are
  read straight from the variable of the same name in `config.py` / `middleware/auth.py`
  (no other name or source), so the check matches what the app actually uses.
- Known side effect, accepted: the 15-minute job first runs 15 minutes after start.
  A second start within 2 hours (for example a burst of data pushes to `main`, each one
  redeploying) shows `/health/jobs` as 503 for up to 15 minutes, so the hourly
  heartbeat can fail once and send a false alarm. Not fixed with a run at start-up:
  old and new containers overlap for about a minute and their in-memory locks cannot
  see each other, which would risk double sends.
- The job health state lives in `mission_control/app.py`, not `scheduler.py`, because
  the test suite replaces `mission_control.scheduler` with a stub.
- Logging: turning the root logger on at INFO also brings the app's own INFO lines to
  Railway logs. Two of them include a customer email address
  (`routers/webhooks.py` "season review updated in place for %s" and
  `services/sequence_engine.py` "enroll blocked (unsubscribed contact): %s -> %s").
  Left unchanged (outside the spec's scope); flagged for the owner.

