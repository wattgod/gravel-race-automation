# 🩺 Gravel God Cycling — Immune System

An automated "immune system" for the race database: it tests things, finds
issues, **auto-heals the safe ones, opens a PR for the judgment calls**, and keeps
a running ledger so the same mistake can't come back unseen.

This is the flagship, highest-value revenue repo in the ecosystem (757 races,
gravelgodcycling.com, the traffic engine the whole plan/course/coaching ladder
depends on) — so Layer 1 defaults to a conservative, read-only posture: it
never edits, commits, or deploys anything.

---

## The 10-second mental model

```
        ┌─────────────────────────────────────────────────────┐
        │  LAYER 1  (dumb, fast, free)   scripts/immune_check.py│
        │  score/tier math · coords · tagline/RWGPS ·           │
        │  search-index parity · money-path alive ·             │
        │  near-duplicates · security                           │
        └───────────────┬─────────────────────────────────────┘
                        │  every problem → one of three lanes
        ┌───────────────▼─────────────────────────────────────┐
        │  LAYER 2  (smart, nightly)   the scheduled Claude agent│
        │  reads Layer-1 findings, does the judgment reads,     │
        │  runs the REPAIR LOOP, sends you ONE digest email     │
        └───────────────┬─────────────────────────────────────┘
                        │
     🟢 auto-heal        🟡 PR for you            🔴 issue only
   (ship if verified)  (propose, you approve)   (money path/security)
```

Layer 1 is the **verifier** — the thing that can't be fooled. Nothing auto-heals
unless it makes Layer 1 go green *without turning anything new red*. That single
rule (borrowed from Karpathy's AutoResearch loop: *keep the change only if the
metric improved, else roll back*) is what makes autonomous repair safe.

---

## The three lanes (the whole safety model)

| Lane | What's in it | What happens |
|------|--------------|--------------|
| 🟢 **auto-heal** | stale/missing search index (`web/race-index.json` count drifted from `race-data/`) | Repair loop applies the safe fix → Layer 1 must stay green → commits. Logged. |
| 🟡 **needs you** | **all scores/tiers** (score-math, tier-math), missing tagline, bad coordinates, bad RideWithGPS ids, malformed JSON, near-duplicate races | A fix is *proposed* into a branch/PR. You get a 1-click link in the digest. |
| 🔴 **issue only** | **anything on the money path** (`/questionnaire/`, `/coaching/`), possible secret exposure, systemic breakage | No edit. Flagged red in the digest. You (or the agent, with your yes) handle it. |

**Hard rule:** the money path never auto-heals, even if the fix looks trivial.
This is encoded in `immune_check.py` (money-path findings are always RED).

The lane for every check lives in the `RULES` table in `scripts/immune_check.py`.
To move something between lanes, edit one row there — that's the whole policy surface.

---

## Layer 1 — the verifier (already built, runnable now)

```bash
python3 scripts/immune_check.py            # fast, offline: profile audit + index + duplicates + money-path wiring + security
python3 scripts/immune_check.py --live       # also hit production for dead money-path / 404s
python3 scripts/immune_check.py --json        # machine JSON (what the nightly agent reads)
python3 scripts/immune_check.py --fail-on red # CI mode: only fail the build on a true emergency
```

Note: unlike some sibling brands, this repo's own `scripts/preflight.py` is a
deploy orchestrator (a sequence of subprocess steps: pytest → audits →
generators → deploy), not a structured errors/warnings validator. The
per-profile DETECT layer here instead reuses `scripts/audit_race_data.py`'s
`audit_race()` — the actual equivalent, already battle-tested and already run
(as an optional/warn-only step) by `preflight.py` today. `scripts/check_links.py`
is reused as-is for the live check; its `DEAD LINKS` output format was already
identical to the reference implementation this was cloned from.

It writes `immune/report.json` (latest full result) and appends a run record to
`immune/ledger.jsonl`. **It never edits, commits, or deploys.**

---

## Layer 2 — the nightly agent (the REPAIR LOOP)

Once a night a scheduled Claude Code agent runs this exact routine:

1. **Scan.** `python3 scripts/immune_check.py --live --json` → the findings.
2. **For each 🟢 finding — the Karpathy repair loop:**
   - Apply the finding's safe `auto_fix` command (e.g. regenerate the index).
   - Re-run `immune_check.py`. If it's green *and nothing new went red* → keep it.
     If anything went red → **roll back** and demote the finding to 🟡 (a PR).
   - Commit the kept fix to `main` with a `[immune] auto-heal:` message.
3. **For each 🟡 finding:** write the proposed fix to a branch, open a PR titled
   `[immune] NEEDS YOU: <title>`, leave the diff for you.
4. **For each 🔴 finding:** open a GitHub issue (or reuse the open one); never edit.
5. **Log.** Append a `type:"fix"` record to `immune/ledger.jsonl` for anything
   healed or PR'd, including the `regression_check` that will now catch a recurrence.
6. **Report.** Send ONE digest email (below). Deploy only if you've turned on
   deploy authority (see switches) — otherwise it stops at "committed, awaiting deploy."

### The nightly digest (your morning ritual)
```
Subject: 🩺 Immune report — <date> (<N> need you)

✅ AUTO-HEALED (n)   <one line each>
⚠️ NEEDS YOU (n)     <title → PR link>
🔴 ISSUE (n)         <title → issue link>
🧬 <k> regressions of past bugs · streak: <d> days green
```

---

## The ledger — why the same mistake can't sneak back

`immune/ledger.jsonl` is the memory. Two record types:
- `type:"scan"` — every run's counts (the health history / streak).
- `type:"fix"` — a resolved issue: what broke, root cause, the fix, and crucially
  **`regression_check`** — the exact check in `immune_check.py` that now fails if
  it recurs.

The rule that makes it an immune system, not a diary: **every fix must name a
regression_check.** If a new class of bug appears that no check would catch, the
nightly agent's job includes adding a rule to `immune_check.py` before closing it.
(Seeded already with three real resolved issues found while building this:
the `landrun-100`/`mid-south` + `sbt-grvl`/`steamboat-gravel` duplicates, the
bare `/methodology/` 404, and the `balatonfondo` tier drift caught by the
rankings-veracity checker.)

---

## Flip-the-switch wiring (what turns the loop ON)

Layer 1 works today. To turn on the nightly Layer 2 loop, three switches — each
optional, each reversible:

1. **Schedule the nightly agent.** A `/schedule` cloud routine running the Layer-2
   routine above. (Ask Claude: "create the immune nightly routine for Gravel God
   Cycling.") Runs whether your Mac is on or not.
2. **Digest email.** Set `RESEND_API_KEY` in `.env`; the agent emails the digest to
   your address. Until then it prints the digest to the run log.
3. **Deploy authority (default OFF — keep it off until you trust it).** With it off,
   the loop commits fixes but never deploys; you deploy with
   `python3 scripts/preflight.py --deploy`. With it on, the loop may run the matching
   deploy step for 🟢 fixes only — never for money-path changes.

## CI (the cheap always-on layer)
`.github/workflows/immune.yml` runs `immune_check.py --fail-on red` on every push +
nightly — so a change that kills the money path or leaks a secret turns the build
red immediately, for free, without waiting for the nightly agent.

---

## Known false-positive class: `check_fuzzy_duplicates()`

L'Etape-by-country races (`letape-poland` vs `letape-thailand`, etc.) and other
short-common-prefix series can cross the 0.88 name-similarity threshold without
being real duplicates. This is expected — these land in 🟡 (a human triages),
never 🔴, so a false positive costs a glance, not a bad auto-edit. Several hits
found while seeding this system look like genuine duplicates from
gran-fondo/granfondo hyphenation variants (e.g. `gran-fondo-felice-gimondi` vs
`granfondo-felice-gimondi`) — worth a real triage pass, not just noise.

## Cloning to the other brands
The shape is identical; only the checks differ. This repo was itself the model
XC Ski Labs was originally cloned from — see
`../../NordicLab/nordic-race-automation/immune/` for that clone. Roadie Labs is
a near-twin of this repo (same static-site pattern) → copy `immune_check.py`,
swap paths/criteria, reuse its own `preflight`/`check_links`. Endure Labs is the
live app → the verifier checks API health + `/plan` `/calendar` timing +
Supabase advisors instead of static pages, but the lanes, ledger, repair loop,
and digest are the same.
