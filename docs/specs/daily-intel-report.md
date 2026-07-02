# Spec: Daily Intel Report ("Morning Intel")

**Status:** PROPOSAL — not built (Jul 2026)
**Goal:** One email, every morning, that answers three questions in under two
minutes of reading: *Is the machine working? Did we make money? What's the one
thing to do today?* Interprets, doesn't just dump numbers. Both brands, one email.

**Why now:** the pieces already exist but nobody reads six dashboards.
Tonight's whoops audit proved the failure mode: a dead A/B engine and five
dead nav links sat unnoticed for months because no daily surface said
"this broke." Per the order-killer lesson: failures invisible to customers,
LOUD to the coach.

---

## 1. What already exists (reuse, don't rebuild)

| Piece | Where | Provides |
|---|---|---|
| `funnel_report.py` | both repos | GA4 funnel: page_view→cta_click→form_start→submit→checkout→purchase |
| `checkout_monitor.py` | road repo (probes BOTH brands) | Real synthetic Stripe checkout health |
| Mission Control (Supabase) | gravel repo, Railway | Leads, enrollments, sends/opens/clicks, `log_action` error rows |
| `cwv_monitor.py` / `gsc_tracker.py` | both / gravel | Daily CWV + GSC snapshots (already on cron) |
| `check_links.yml` | both repos | Weekly dead-link sweep (Monday) |
| `daily_report.py` | gravel (works), road (hollow copy) | Prior art; road's version + its broken `daily-marketing-report.yml` get RETIRED by this |
| `ga4-credentials.json` | gravel repo root (local) | Service account — becomes a GitHub secret |

## 2. Architecture

`scripts/daily_intel.py` in the gravel repo, run by a GitHub Action daily at
12:00 UTC (06:00 MT), delivered via Resend to gravelgodcoaching@gmail.com.

**Stage 1 — Collect** (each source fail-soft; a failed source becomes a
BROKEN line, never a skipped email):
- GA4 per brand (properties: gravel G-EJJZ9T6M52, road 540984732/G-WQ7W8XN11N):
  sessions, users, top 5 pages, funnel counts, vs trailing-7-day average.
- Checkout: run the deep probe per brand (never-charged Stripe session).
- Mission Control: last-24h new leads by source/brand, sequence sends +
  opens/clicks, countdown enrollments, purchases + plan deliveries,
  `sequence_send_error` / order-error log_actions.
- Railway webhook `/health`.
- Latest link-check + CWV + checkout-monitor workflow conclusions (`gh api`).

**Stage 2 — Interpret** (one Claude API call, ~10k tokens, ANTHROPIC_API_KEY
secret; model configurable — haiku for cost, sonnet when it matters):
- Fixed prompt, deadpan register, anti-slop rules included.
- HARD RULE: may only reference numbers present in the collected JSON —
  no invented stats (same integrity bar as the email sequences).
- Output shape:
  - **TOP LINE** — 3 bullets max. What actually happened.
  - **NUMBERS** — small table per brand: sessions, leads, plan sales,
    revenue, funnel conversion, each with Δ vs 7-day avg.
  - **BROKEN** — every error/failed probe, severity-ranked. Empty = say so
    in one line.
  - **DO TODAY** — max 3 action items, each with the why and expected
    impact. If nothing's worth doing, say "nothing — let it run."
- **KPI anchor:** every report tracks plans sold yesterday + trailing-7-day
  rate against the northstar target (1/day) and the Jun 2026 baseline
  (~35 users/day, ~1 sale/mo). The report exists to watch this line move.

**Stage 3 — Deliver:** Resend (existing sender infra). Subject:
`intel {date}: {top-line hook}` — e.g. `intel jul 3: 2 plans, road funnel up, 1 breakage`.
Send failures = red Action run.

## 3. Secrets required (gravel repo GitHub settings)

`GA4_CREDENTIALS_JSON`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
`RESEND_API_KEY`, `ANTHROPIC_API_KEY`, `RAILWAY_HEALTH_URL` (optional),
`GH_TOKEN` (default token fine for workflow-status reads).

## 4. Phasing

- **P1 (half-day):** collectors for GA4 + checkout + MC counts, plain
  template email (no LLM). Retire road's broken daily-marketing-report.yml.
- **P2 (half-day):** the interpretation layer + DO TODAY action items.
- **P3:** fold in link-check/CWV/GSC statuses; Monday edition adds
  week-over-week trends + sequence A/B readout (sequence_report.py).

## 5. Guardrails

- Fail-soft everywhere; the email always sends (a mostly-BROKEN email is
  the most valuable one).
- One email. If it's ever ignored for two straight weeks, drop to weekly
  rather than letting it become inbox wallpaper — attention is the scarce
  resource this report spends.
- Cost: one LLM call/day ≈ cents; GA4/Supabase reads free-tier.
