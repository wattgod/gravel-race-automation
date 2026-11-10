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

1. **Change 9 — the four daily-job services now flag their early aborts.** The spec
   wants "a run that aborts (e.g. race data fetch failed) writes nothing", but
   `run_race_countdown`, `run_race_debrief` (no race dates) and `run_race_watch` (no race
   intel; do-not-email list unreadable) logged the abort and *returned* normally, with
   `summary["aborted"]` left `False` (race_watch had no such key). "Finished without
   raising" alone would have written the done-today marker and stopped the retry. The
   conservative fix: those abort paths now set `summary["aborted"] = True`
   (`services/race_countdown.py`, `race_debrief.py`, `race_watch.py`; nothing else in
   them changed), and the scheduler writes the marker only when the run returned without
   raising **and** without `aborted`. `win_back` already set the flag.
2. **Change 9 — `test_win_back.py::test_scheduler_registers_daily_job`** asserted the old
   single slot (`hour='15'`); updated to `hour='15,18,21'`.
3. **Change 8 — `scripts/jev_client.py` added to watchPatterns** (not in the spec's list):
   `services/lead_nurture.py` imports it.
4. **Change 10 — the new `sendResendEmail` helper is used only by the new lost-lead
   alert.** The three existing senders (fueling lead, athlete review/exit, debrief alerts)
   still inline their Resend call. Moving them onto the helper would touch owner alerts
   that work today and is not needed for this change; left for a later tidy-up.
5. **Change 10 — the 8-second timeout applies to every source**, as the spec asks
   (`signal: AbortSignal.timeout(8000)` on the one Mission Control fetch). For the four
   storage-required sources a Mission Control answer slower than 8 s now gives the
   visitor the existing "could not store your answers" 503 (draft kept) instead of a
   longer wait.
6. **Change 10 — `pickem-intake` left completely unchanged** (the spec allowed a clearer
   log line; not needed), so it needs no deploy.
7. **Change 4 — a setting that is only spaces counts as missing** for `/health`. Slightly
   stricter than the spec's "set and non-empty"; a key of spaces cannot work anyway.

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
- What counts as a bad tick, checked against `process_due_sends`: suppressed contacts,
  customer suppression, a finished sequence, a stale-race skip and the one-email-a-day
  deferral all return "sent" and move the row on. Only an unknown sequence id, an unknown
  variant, a missing `RESEND_API_KEY` or a Resend error count as not sent, and the first
  two leave the row due. So if production holds active enrollments for a sequence or
  variant that no longer exists in code, every quiet tick (no other sends) is "bad" and
  `/health/jobs` goes red with no new fault. Kept the spec's rule (`processed == 0 or
  sent > 0`); could not check the database by rule. If the heartbeat goes red on a quiet
  day with `last_run.errors` equal to `last_run.processed`, look for such rows first.
- Already true before this change: uvicorn's own request log (access log) prints request
  paths with their query string, so `/unsubscribe?email=…&token=…` clicks already put
  customer emails in Railway logs. Not changed here.
- Logging: turning the root logger on at INFO also brings the app's own INFO lines to
  Railway logs. Two of them include a customer email address
  (`routers/webhooks.py` "season review updated in place for %s" and
  `services/sequence_engine.py` "enroll blocked (unsubscribed contact): %s -> %s").
  Left unchanged (outside the spec's scope); flagged for the owner.

### Change 6 — pruned areas
- `git grep` for `/reports/referral`, `/reports/`, `/webhooks/intake` across
  `workers/`, `web/`, `scripts/`, `tests/` and `.github/` found no caller (the only hits
  were the removed templates themselves), so `reports` went whole.
- Removed: routers `athletes`, `pipeline`, `touchpoints`, `reports`; `/webhooks/intake`;
  `mission_control/sync.py` and the start-up sync in `mission_control.py`; services
  `pipeline_runner`, `touchpoint_sender`, `file_storage` (each imported only by the
  removed routers, `git grep`-checked including `scripts/`); their templates and the
  `athlete_table` / `touchpoint_table` partials; `test_deliver_plan.py` (it tested
  `/athletes/{slug}/deliver`).
- Triage: removed `/triage/plans/{slug}/approve`, `/triage/touchpoints/{tp_id}/sent`,
  the "Plans Needing Action" and "Due Touchpoints" panels, the "Due Touchpoints" stat
  card, and the service functions only they used (`get_plans_needing_action`,
  `get_due_touchpoints`, `approve_plan`, `mark_touchpoint_sent`). `triage_summary` now
  counts intakes + unread replies only. The "Upcoming races" panel stays, names as plain
  text.
- Kept: every function in `supabase_client.py`, the top-level `pipeline/` package,
  `services/stats.py`, `ga4`, `revenue`, the dashboard page and its panels (only the
  `/athletes/...` links became plain text), and the Gmail bridge / tp-store-sales routes.
- Also turned into plain text: the pending-intake name link `/athletes?search=` on the
  triage page (not in the spec's line list, but it pointed at a removed page).
- Config values only the removed code read (`PIPELINE_SCRIPT`, `PRE_DELIVERY_AUDIT`,
  `STORAGE_BUCKET`, `ATHLETES_DIR`) are left in `config.py`; harmless and outside scope.
- `.github/workflows/test.yml` names no removed test file; unchanged.


### Change 7 — pins
- The local virtual environment, installed from the old floating `requirements.txt` on
  2026-11-10, resolved to exactly the spec's versions for all 17 packages (`pip freeze`).
- `pip install --dry-run --ignore-installed -r requirements.txt` resolves with the pins on
  local Python 3.14, and with `--only-binary=:all: --platform manylinux…x86_64` for
  `--python-version` 3.11, 3.12 and 3.13 (CI, Docker, publish-site). `pip check`: no
  broken requirements.
- Every pinned package declares `Requires-Python` of 3.11 or lower, so CI's 3.11 is covered.
- Other installers of this same file: `test.yml`, `deploy-race-page.yml`,
  `deploy-race-support.yml`, `gravel-weekly-*.yml`, `publish-site.yml` (3.13),
  `stripe-provider-ingestion.yml`, `weekly-broadcast.yml`, the `Makefile` and the
  `Dockerfile`. None installs anything on top that needs a newer version; the workflows
  that install other packages (`pip install anthropic requests …`) do not read this file.
  No conflict found, so no deviation.
- `pydantic` had no line before (it came in through fastapi); it is now listed and pinned
  in the Mission Control block.

### Change 8 — rebuild paths (watchPatterns)
Greps run over `mission_control/` (tests excluded) and over what it imports:
`git grep -n "REPO_ROOT\|parent.parent\|read_text\|open(\|Path("`, plus a scan of every
import that is not `mission_control.*`, the standard library or an installed package.

| Path | Why the container reads it (evidence) |
|---|---|
| `mission_control/**` | the app itself, its Jinja templates (`config.WEB_TEMPLATES_DIR`), static files (`config.STATIC_DIR`), sequence email templates (`sequence_engine._render_template`, `race_watch.py:83`) |
| `mission_control.py` | `Dockerfile` `CMD` |
| `requirements.txt`, `Dockerfile`, `railway.toml` | the build itself |
| `pipeline/__init__.py`, `pipeline/nutrition.py` | `routers/nutrition_api.py:17` imports `pipeline.nutrition` (which imports only `typing`; `__init__` is empty) |
| `scripts/jev_client.py` | `services/lead_nurture.py:37` `from scripts import jev_client` (it imports only `os`, `typing`). **Not in the spec's list; added.** |
| `race-data/**` | `services/race_data.py:20` `RACE_DATA_DIR` (races API) and `sequence_engine.py` race facts (`RACE_DATA_DIR / f"{slug}.json"`) |
| `web/race-index.json` | `services/race_data.py:19` `RACE_INDEX_PATH` |
| `data/pricing.json` | `services/pricing.py:15` `PRICING_JSON_PATH`, read at import |
| `guide/fonts/**` | `services/goal_poster.py:61` `_FONT_DIR` (poster PNG fonts) |
| `templates/emails/**` | `config.TEMPLATES_DIR`, read by `services/email_preview.py` (templates page) |

Not included, on purpose: `.env` (loaded by `config.py` but not in the repo or the
image), `runtime_credentials.py`'s temporary GA4 key file (written at start from an
environment variable), and the input paths of `provider_ingestion.py` /
`stripe_provider_ingestion.py` (command-line arguments, not used by the server).
`config.py` still names `athletes/`, `intakes/`, `plans/`, `run_pipeline.py` and
`scripts/pre_delivery_audit.py`, but after change 6 nothing at run time reads them.
There is no `.dockerignore`; `COPY . .` copies the whole repo.

Note: `race-data/**` is pushed often by the data automation, so those pushes still
redeploy Mission Control (needed: email race facts and the races API read it). See the
change 4 note about a possible false heartbeat alarm after back-to-back deploys.

### Change 9 — daily jobs
- Slots: countdown 14:00 / 17:00 / 20:00, debrief 14:30 / 17:30 / 20:30, race watch
  15:00 / 18:00 / 21:00, win-back 15:30 / 18:30 / 21:30 UTC. Same order within each slot.
- Marker: a `gg_audit_log` row, `action = 'daily_job_done'`, `entity_id = '<job>:<UTC
  date>'`, read with the existing generic `supabase_client.select` (no new function).
  If the marker cannot be read, the slot is skipped (logged at ERROR) rather than
  risking a second run; the next slot checks again.
- Accepted small windows: the check-then-run is not atomic (two containers during a
  deploy could both run in the same slot); a run that aborts after the error limit
  (`aborted` after 10 failed contacts) has already enrolled some people, so the retry
  can enroll up to one more cap's worth that day; `race_watch` saves `last_notified_at`
  right after each send, so a retry skips those people (7-day rate cap) unless that
  save itself failed for someone.
- The `win_back` run with `WIN_BACK_ENABLED` off returns normally, so it marks the day
  done — same effect as today's single slot.

### Change 10 — lost leads
- `notifyMissionControl` now returns `{ok, status}` (plus `poster_token` when present);
  `status` is the HTTP code, or `timeout` / `network error` when the fetch threw.
  Storage-required sources still throw on failure, exactly as before.
- For a source that is neither storage-required nor `fueling_calculator`, the alert is
  chained onto the Mission Control promise inside the existing `Promise.allSettled`;
  `alertLeadNotSaved` never throws, so the visitor's response and status code do not
  change.
- Alert: plain-text email to `NOTIFICATION_EMAIL`, from
  `<brand label> <noreply@gravelgodcycling.com>`, subject `Lead not saved: <source>`,
  body with email, name, source, race slug, brand and the Mission Control status.
- Flood cap: at most 5 alerts per 10 minutes per worker instance. The first suppressed
  alert in a window logs one "capped at 5" line; when the next window starts, one line
  says how many more were not alerted. Every lead, alerted or not, still has its
  `Mission Control notified: <email> <source> <status>` log line.
- Missing `RESEND_API_KEY` or `NOTIFICATION_EMAIL`: skipped, logged once per instance.
- `pickem-intake` stores every pick in KV first and has a `/resync` route that replays
  what Mission Control missed (`workers/pickem-intake/worker.js:10`, `:106`), so its
  leads are recoverable without an alert.

## Owner steps after review

0. Confirm `athlete-profiles` is the only Railway service that builds from this repo.
   `railway.toml` is at the repo root (no other `railway.toml` exists), so any other
   service built from it would pick up the new health check and watch patterns.
1. Before merging, check by name only (not value) that the Railway service
   `athlete-profiles` has all five settings `/health` now requires: `SUPABASE_URL`,
   `SUPABASE_SERVICE_KEY`, `RESEND_API_KEY`, `WEBHOOK_SECRET`, `MISSION_CONTROL_SECRET`.
   If one is missing, the new deploy health check refuses every deploy (the old one stays
   live).
2. Merge the PR. Railway deploys; the new `/health` check guards the switch-over.
3. Confirm `https://athlete-profiles-production.up.railway.app/health` and `/health/jobs`
   return 200. (`/health/jobs` is 200 straight away only on a first start in 2 hours;
   otherwise it turns 200 after the first 15-minute run.)
4. Deploy the lead worker by hand (not run here):
   ```bash
   cd workers/fueling-lead-intake && npx wrangler deploy
   ```
   Then run `bash tests/test_worker_intake.sh` (Rule #34 in `docs/LESSONS_LEARNED.md`).
   `wrangler.toml` also has an `[env.production]` block; deploy the same way the live
   worker was last deployed (plain `wrangler deploy` unless it was `--env production`).
   `pickem-intake` is unchanged: no deploy.
5. Run the heartbeat workflow once by hand (Actions → "Mission Control heartbeat" → Run
   workflow) and check it passes. To confirm the failure email reaches you: GitHub sends
   scheduled-run failures to whoever last edited the schedule. If that was a bot or agent
   account, push a trivial edit of `.github/workflows/mission-control-heartbeat.yml`
   yourself, or watch the repo's Actions notifications.
6. Expect an occasional false heartbeat alarm on busy data days: after two restarts within
   2 hours `/health/jobs` reads red for up to 15 minutes, and `race-data/**` pushes still
   redeploy the service.
7. The automatic test run (`.github/workflows/test.yml`) lists Mission Control test files
   by name, and none of the files this change adds or edits for the hardening
   (`test_health`, `test_scheduler_daily`, `test_webhooks`, `test_session_auth`,
   `test_admin_auth`, `test_sequence_engine`, `test_win_back`) is on that list. Consider
   adding them; not changed here.
8. Optional: the owner may want to drop the two app log lines that print a customer
   email at INFO (see the change 4 note).

## Final test run


After all ten changes (local Python 3.14.3, no Playwright browser):

- `.venv-mc/bin/pytest mission_control/tests -q` → **3 failed, 1028 passed**. The three
  failures are the same three as the baseline (two need the Chromium browser, one is the
  pre-existing `mc-native-funnel*` CSS check; the audit still lists exactly those four
  classes and nothing else).
- `node --test tests/test_fueling_lead_intake.mjs` → **54 passed, 0 failed** (44 before).
- `.venv-mc/bin/pytest tests/test_pickem.py -q` → 44 passed (pickem untouched).
- Also run: the top-level tests that import Mission Control (`test_daily_intel`,
  `test_exit_survey`, `test_ga4_service_events`, `test_goals_funnel_report`,
  `test_gravel_weekly`, `test_jev_lead_nurture`, `test_pricing_single_source`,
  `test_race_debrief_survey`, `test_trust_checks`) → 525 passed; and
  `test_email_capture_forms.py`, `test_fueling_lead_intake_node.py` → passed.

- Whole repo suite as CI starts it, `pytest tests/ -q` → 14256 passed, 291 skipped,
  15 failed, 54 errors. Every failure and error is in a browser test file
  (`test_mobile_playwright`, `test_race_debrief_playwright`, `test_exit_survey_playwright`,
  `test_guide_gate_playwright`) and fails with "BrowserType.launch: Executable doesn't
  exist" (no Chromium installed here). No baseline of this suite was taken before the
  change, but none of those files touches what this branch changed except through the
  lead worker, whose own tests pass.

Not verified here: tests ran on Python 3.14, CI uses 3.11; the worker's 8-second timeout
was tested in Node only, not in Cloudflare's runtime; the two browser chain tests (`TestTheWholeChain` in
`test_athlete_exit.py` and `test_plan_debrief.py`; they post through the worker to
`/webhooks/subscriber`, which this change keeps) — CI installs Chromium and runs them.
The Docker build, the Railway health check and watch patterns, and the GitHub heartbeat
were not exercised (no deploys by rule).
