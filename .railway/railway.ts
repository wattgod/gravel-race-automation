import { defineRailway, github, preserve, project, service } from "railway/iac";

// Railway settings for the `athlete-profiles` service (Mission Control; project
// gravel-god-services, environment production). Replaces railway.toml, which
// Railway stops reading on 2026-12-01.
//
// This file is NOT read at deploy time. Pushes to main build with the settings
// stored on the service; this file is how those settings are written. After a
// change here, run from the repo root (SDK: `npm ci --prefix .railway`):
//   railway config plan     (read-only)
//   railway config apply
//
// The same project also holds `stripe-webhook` and its order volume, owned by
// athlete-custom-training-plan-pipeline's own partial; an apply from here never
// touches them. Deletion follows recorded ownership: this partial owns the
// `athlete-profiles` service, so REMOVING IT FROM THIS FILE DELETES IT on the
// next apply. Stop managing it only with `railway config partials release`.
//
// Environment variables: every one is listed by NAME only and kept with
// preserve(), so its value stays what is set on Railway and no secret is in
// git. Apply DELETES any variable missing from this list. Before an apply, add
// any variable set since with `railway variables --set`, and read the plan:
// a "Delete variable" line means the list is behind. Never pass
// --confirm-destructive to get past one.
export const partial = "athlete-profiles";

const VARIABLES = [
  "GA4_CREDENTIALS_JSON",
  "GA4_PROPERTY_ID",
  "GG_RACE_DATES_URL",
  "MISSION_CONTROL_SECRET",
  "RACE_COUNTDOWN_MAX_PER_RUN",
  "RESEND_API_KEY",
  "RESEND_WEBHOOK_SECRET",
  "RL_RACE_DATES_URL",
  "SUPABASE_SERVICE_KEY",
  "SUPABASE_URL",
  "UNSUBSCRIBE_SECRET",
  "WEBHOOK_SECRET",
];

// Rebuild only when something the container reads at run time changes, so the
// frequent data/site pushes to main stop redeploying Mission Control. Derived
// from the code; evidence in docs/specs/mission-control-hardening-notes.md.
// Missing a path only delays a change to the next deploy; it never breaks the
// server. (.railway/ is not here: it is not read at deploy time.)
const WATCH_PATTERNS = [
  "mission_control/**",
  "mission_control.py",
  "requirements.txt",
  "Dockerfile",
  "pipeline/__init__.py",
  "pipeline/nutrition.py",
  "scripts/jev_client.py",
  "race-data/**",
  "web/race-index.json",
  "data/pricing.json",
  "guide/fonts/**",
  "templates/emails/**",
];

export default defineRailway(() => {
  const athleteProfiles = service("athlete-profiles", {
    source: github("wattgod/gravel-race-automation", {
      branch: "main",
      rootDirectory: "",
      checkSuites: false,
    }),
    // DOCKERFILE must be declared: without railway.toml the service's own
    // stored builder was RAILPACK (found 2026-11-16).
    build: {
      builder: "DOCKERFILE",
      dockerfilePath: "Dockerfile",
      watchPatterns: WATCH_PATTERNS,
    },
    // No start command: the Dockerfile CMD runs `python3 mission_control.py`
    // (EXPOSE 8000).
    // Railway only switches traffic to a new deploy once /health answers 200
    // (job timer running and required settings present); otherwise the
    // previous deploy stays live.
    // Restart policy type is not declared: Railway stores ON_FAILURE as its
    // default (null), so declaring it leaves a plan diff that never clears.
    deploy: {
      healthcheckPath: "/health",
      healthcheckTimeout: 120,
      restartPolicyMaxRetries: 3,
    },
    replicas: { "us-east4-eqdc4a": 1 },
    networking: {
      serviceDomains: { "athlete-profiles-production.up.railway.app": {} },
    },
    env: Object.fromEntries(VARIABLES.map((name) => [name, preserve()])),
  });

  return project("gravel-god-services", {
    resources: [athleteProfiles],
  });
});
