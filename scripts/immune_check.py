#!/usr/bin/env python3
"""
Gravel God Cycling — Immune System, Layer 1: deterministic verifier + lane classifier.

This is the "immune system's" senses. It does three things and NOTHING else:

  1. DETECT   — reuse audit_race_data.py's per-profile static checks (score/tier
                math, coords, tagline, RWGPS ids) plus a few extra immune-specific
                checks (search-index parity, money-path CTA wiring, near-duplicate
                races, hardcoded secrets), and optionally the live 404 / money-path
                checker. Every problem becomes one structured Finding.
  2. CLASSIFY — sort each Finding into exactly one lane:
        GREEN  (auto-heal)  safe & mechanical — a regenerate fixes it
        YELLOW (needs you)  judgment — a fix is proposed, but a human approves
        RED    (issue only) unsafe to auto-fix — money path / security / systemic
  3. REPORT   — write immune/report.json, append a run record to
                immune/ledger.jsonl, and print a human digest.

IMPORTANT: this script never edits data, commits, or deploys. It is the *verifier*
the nightly repair loop checks its candidate fixes against — the Karpathy rule:
a candidate fix only ships if it makes this script go green WITHOUT turning
anything new red. Anything else becomes a PR (YELLOW) or an issue (RED).

Note: unlike some sibling brands, this repo's own scripts/preflight.py is a
deploy-orchestrator (a sequence of subprocess steps), not a structured
errors/warnings validator — so the per-profile DETECT layer here reuses
scripts/audit_race_data.py's audit_race() instead (the actual equivalent:
it returns one issue string per problem, covering score math, tier math,
coordinates, tagline, and RideWithGPS ids across all 757 profiles).

Usage:
    python3 scripts/immune_check.py            # fast, offline: data + index checks
    python3 scripts/immune_check.py --live       # also run the live money-path / 404 check
    python3 scripts/immune_check.py --json        # print machine JSON only (for the agent)

Exit code: 0 if no RED and no YELLOW findings, else 1 (so CI can gate on it).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
WEB_DIR = PROJECT_ROOT / "web"
RACE_INDEX_FILE = WEB_DIR / "race-index.json"
IMMUNE_DIR = PROJECT_ROOT / "immune"
REPORT_FILE = IMMUNE_DIR / "report.json"      # latest snapshot (gitignored — churns every run)
SCANS_FILE = IMMUNE_DIR / "scans.jsonl"       # scan telemetry / streak (gitignored)
LEDGER_FILE = IMMUNE_DIR / "ledger.jsonl"     # permanent FIX log (tracked — the memory)
BASELINE_FILE = IMMUNE_DIR / "baseline.json"  # known/accepted backlog fingerprints (tracked)

BRAND = "gravel-god"
GREEN, YELLOW, RED = "green", "yellow", "red"

# Money-path CTA markers — the conversion links a visitor clicks (buy the plan /
# talk to a coach). Anything on these paths is RED, never auto-healed.
MONEY_PATH_MARKERS = ("/questionnaire/", "/coaching/")

# Make audit_race_data.py importable and reuse its logic (don't reinvent it).
sys.path.insert(0, str(SCRIPT_DIR))
import audit_race_data  # noqa: E402


@dataclass
class Finding:
    code: str            # short stable slug, e.g. "score-math"
    lane: str            # green | yellow | red
    severity: str        # critical | high | medium | low
    title: str           # one-line human summary
    detail: str          # the raw message / specifics
    remedy: str           # what a fix would do, in plain words
    auto_fix: str | None = None   # the exact safe command (GREEN only), else None
    source: str = "audit_race_data"     # which detector raised it
    new: bool = True              # not in the accepted baseline (a new/worsening finding)


# ── Classification table ──────────────────────────────────────────────────────
# Each rule: (regex on the raw message, code, lane, severity, remedy, auto_fix cmd)
# Ordered — first match wins. Unmatched errors default to YELLOW/high (a human
# decides), which is the safe direction: never auto-touch something we can't
# confidently classify.
REGEN_INDEX = "python3 scripts/generate_index.py --with-jsonld"

RULES: list[tuple[str, str, str, str, str, str | None]] = [
    # ── GREEN: safe, mechanical, deterministic regenerate ──
    (r"race-index\.json (not found|count mismatch)",
     "index-drift", GREEN, "high",
     "Search index is stale/missing/out of sync with race-data — regenerate it.",
     REGEN_INDEX),
    # ── YELLOW: judgment — propose a fix, human approves (includes ALL ratings) ──
    (r"SCORE MISMATCH",
     "score-math", YELLOW, "high",
     "A race's overall_score doesn't equal round((sum of 14 criteria + "
     "cultural_impact) / 70 * 100). Proposed: recompute the score — but confirm "
     "the criteria are what you intended (a score IS a rating, see "
     "docs/GRAVEL_GOD_SCORING_SYSTEM.md).", None),
    (r"TIER MISMATCH|DISPLAY_TIER MISMATCH",
     "tier-math", YELLOW, "high",
     "A race's tier (or display_tier) doesn't match its score/prestige-override "
     "rule. Proposed: recompute via scripts/recalculate_tiers.py --dry-run — "
     "confirm the inputs before applying.", None),
    (r"MISSING SCORE FIELDS|SCORE OUT OF RANGE",
     "rating-broken", YELLOW, "high",
     "A race's scoring criteria are missing or out of the 1-5 range — needs a "
     "human rating call per docs/GRAVEL_GOD_SCORING_SYSTEM.md.", None),
    (r"PARSE ERROR",
     "json-invalid", YELLOW, "critical",
     "A profile file is malformed JSON — needs a careful human fix (auto-repair "
     "could silently change data).", None),
    (r"MISSING TAGLINE",
     "missing-content", YELLOW, "high",
     "A race is missing its tagline — a human writes one (exact-match tagline "
     "validation elsewhere depends on this being specific, not generic).", None),
    (r"MISSING COORDS|INVALID LAT TYPE|INVALID LNG TYPE|LAT IMPOSSIBLE|"
     r"LNG IMPOSSIBLE|LAT OUT OF HABITABLE RANGE|GEO MISMATCH|POSSIBLE LAT/LNG SWAP",
     "bad-geo", YELLOW, "high",
     "A race's coordinates are missing, malformed, or geographically implausible "
     "— a human confirms/re-geocodes (scripts/geocode_races.py can propose a "
     "value, but the result needs a look before it ships).", None),
    (r"RWGPS PLACEHOLDER|RWGPS NON-NUMERIC",
     "bad-rwgps-id", YELLOW, "low",
     "A race's RideWithGPS route id is a placeholder or non-numeric — a human "
     "finds/confirms the real route id.", None),
    (r"Duplicate slugs|Duplicate names|Near-Duplicate Name",
     "duplicate-race", YELLOW, "high",
     "Two profiles look like the same event — a human picks the canonical one to "
     "keep (see docs/LESSONS_LEARNED.md — this has bitten the database before: "
     "landrun-100/mid-south, sbt-grvl/steamboat-gravel).", None),
    # ── RED: unsafe to auto-fix, ever ──
    (r"\.env not in \.gitignore|Possible hardcoded API key|Possible hardcoded (secret|key)",
     "security", RED, "critical",
     "Possible secret exposure — handle by hand, never auto-touch secrets.", None),
]


def classify(message: str, source: str = "audit_race_data") -> Finding:
    for pattern, code, lane, severity, remedy, auto in RULES:
        if re.search(pattern, message):
            title = message.split(":")[0].strip() if ":" in message else code.replace("-", " ").title()
            return Finding(code, lane, severity, title.title(), message, remedy, auto, source)
    # Unknown error → safe default: a human looks at it.
    return Finding("unclassified", YELLOW, "high", "Unclassified Issue",
                   message, "New kind of problem — a human should look and, once "
                   "understood, add a rule for it.", None, source)


# ── Detectors ─────────────────────────────────────────────────────────────────
def run_profile_audit() -> list[Finding]:
    """Run audit_race_data.audit_race() over every profile and classify every issue."""
    findings: list[Finding] = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        for issue in audit_race_data.audit_race(f):
            # Prefix the race slug so each finding is race-specific: makes the
            # digest actionable AND gives every occurrence its own baseline
            # fingerprint (else a new race's missing tagline hides behind the
            # generic "MISSING TAGLINE" already in the baseline).
            findings.append(classify(f"{f.stem}: {issue}"))
    return findings


def check_search_index_parity() -> list[Finding]:
    """Offline guard: web/race-index.json must exist and match race-data's count.
    A drifted or missing index means the search page silently shows the wrong
    races — safe to auto-heal by regenerating from the profiles."""
    n_profiles = sum(1 for _ in RACE_DATA_DIR.glob("*.json"))
    if not RACE_INDEX_FILE.exists():
        return [Finding("index-drift", GREEN, "high", "Index Drift",
                        "race-index.json not found", "Search index is missing — "
                        "regenerate it from the profiles.", REGEN_INDEX, "immune")]
    try:
        n_index = len(json.loads(RACE_INDEX_FILE.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as e:
        return [Finding("index-drift", GREEN, "high", "Index Drift",
                        f"race-index.json unreadable: {e}", "Search index is "
                        "corrupt — regenerate it from the profiles.",
                        REGEN_INDEX, "immune")]
    if n_index != n_profiles:
        return [classify(f"race-index.json count mismatch: index has {n_index}, "
                          f"race-data has {n_profiles}")]
    return []


def check_tombstone_resurrection() -> list[Finding]:
    """Fabricated races purged 2026-07-22 (config/tombstones.json) must never
    reappear in race-data or any active artifact — a resurrected tombstone
    means a bad restore, a stale branch merge, or a generator regression."""
    tomb_file = PROJECT_ROOT / "config" / "tombstones.json"
    if not tomb_file.exists():
        return [Finding("tombstones-missing", YELLOW, "medium", "Tombstone Registry Missing",
                        "config/tombstones.json not found",
                        "The fabricated-race tombstone registry is gone — exclusion "
                        "sets in 8 generators load from it and will crash.",
                        None, "immune")]
    slugs = {t["slug"] for t in json.loads(tomb_file.read_text())["tombstones"]}
    findings = []
    resurrected = sorted(s for s in slugs if (RACE_DATA_DIR / f"{s}.json").exists())
    if resurrected:
        findings.append(Finding(
            "tombstone-resurrected", RED, "critical", "Fabricated Race Resurrected",
            f"tombstoned profiles reappeared in race-data: {' '.join(resurrected)}",
            "A fabricated race profile is back in the catalog — bad restore, stale "
            "branch merge, or manual re-add. It will regenerate pages on next build. "
            "Delete it and find how it returned.", None, "immune"))
    if RACE_INDEX_FILE.exists():
        try:
            idx = RACE_INDEX_FILE.read_text(encoding="utf-8")
            leaked = sorted(s for s in slugs if s in idx)
            if leaked:
                findings.append(Finding(
                    "tombstone-in-index", RED, "critical", "Fabricated Race In Search Index",
                    f"tombstoned slugs present in race-index.json: {' '.join(leaked)}",
                    "The search index references a fabricated race — the exclusion "
                    "in generate_index.py failed or the index is stale.",
                    None, "immune"))
        except OSError:
            pass
    return findings


def check_money_path_wiring() -> list[Finding]:
    """Offline guard: the live race-page generator must still emit the money-path
    CTA(s). If a future edit drops it, that's a money-path regression — RED,
    never auto."""
    gen = PROJECT_ROOT / "wordpress" / "generate_neo_brutalist.py"
    try:
        src = gen.read_text(encoding="utf-8")
    except OSError:
        return [Finding("money-path-generator-missing", RED, "critical",
                        "Money Path Generator Missing", str(gen),
                        "The race-page generator is unreadable — the money path "
                        "can't be verified.", None, "immune")]
    missing = [m for m in MONEY_PATH_MARKERS if m not in src]
    if missing:
        return [Finding("money-path-cta-dropped", RED, "critical",
                        "Money Path CTA Dropped",
                        f"generate_neo_brutalist.py no longer contains: {', '.join(missing)}",
                        "A 'Build my plan' / 'Talk to a coach' CTA vanished from "
                        "the race-page generator — restore it before deploying. "
                        "Money path, so never auto-fixed.", None, "immune")]
    return []


def check_fuzzy_duplicates() -> list[Finding]:
    """Catch near-duplicate events hiding under different slugs (e.g.
    landrun-100 vs mid-south, sbt-grvl vs steamboat-gravel — both have bitten
    this database before, see docs/LESSONS_LEARNED.md).

    Primary signal is a HIGH fuzzy-similarity between event names — precise
    enough to avoid flagging a whole race series that merely shares one
    organizer website. Sharing a website only raises confidence; it never
    flags on its own."""
    from difflib import SequenceMatcher

    findings: list[Finding] = []
    profiles: list[tuple[str, dict]] = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        try:
            profiles.append((f.stem, json.loads(f.read_text(encoding="utf-8")).get("race", {})))
        except (OSError, json.JSONDecodeError):
            continue

    def canon(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())

    def site_of(race: dict) -> str:
        return (race.get("vitals", {}).get("website") or "").strip().lower().rstrip("/")

    NAME_THRESHOLD = 0.88  # tuned: catches near-duplicates, skips series
    for i in range(len(profiles)):
        slug_a, race_a = profiles[i]
        name_a = canon(race_a.get("name") or slug_a)
        for j in range(i + 1, len(profiles)):
            slug_b, race_b = profiles[j]
            name_b = canon(race_b.get("name") or slug_b)
            if not name_a or not name_b:
                continue
            ratio = SequenceMatcher(None, name_a, name_b).ratio()
            if ratio >= NAME_THRESHOLD:
                same_site = site_of(race_a) and site_of(race_a) == site_of(race_b)
                conf = "same website too" if same_site else "distinct websites"
                findings.append(Finding(
                    "duplicate-race", YELLOW, "high", "Near-Duplicate Name",
                    f"'{slug_a}' and '{slug_b}' names ~{int(ratio * 100)}% similar "
                    f"({conf})",
                    "Likely the same event under two slugs — a human merges/removes one.",
                    None, "immune"))
    return findings


def check_security() -> list[Finding]:
    """Offline guard: .env must stay out of git, and no script should carry a
    hardcoded secret. Mirrors the pattern used across the other brand repos'
    preflight security checks (this repo's own scripts/preflight.py doesn't run
    this class of check — it's a deploy orchestrator, not a validator)."""
    findings: list[Finding] = []
    gitignore = PROJECT_ROOT / ".gitignore"
    if not gitignore.exists():
        findings.append(classify("No .gitignore found"))
    elif ".env" not in gitignore.read_text(encoding="utf-8"):
        findings.append(classify(".env not in .gitignore — API keys could be exposed"))

    key_patterns = [
        re.compile(r"sk-ant-api\d{2}-[A-Za-z0-9_-]{20,}"),   # Anthropic
        re.compile(r"AIzaSy[A-Za-z0-9_-]{30,}"),              # Google
        re.compile(r"sk_live_[A-Za-z0-9]{20,}"),              # Stripe live secret key
        re.compile(r"re_[A-Za-z0-9_]{20,}"),                  # Resend
    ]
    this_file = Path(__file__).resolve()
    for f in sorted(SCRIPT_DIR.glob("*.py")):
        if f.resolve() == this_file:
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for kp in key_patterns:
            if kp.search(content):
                findings.append(classify(f"{f.name}: Possible hardcoded API key"))
                break
    return findings


def run_live_link_check() -> list[Finding]:
    """Run the existing live checker as a subprocess and parse its DEAD LINKS
    block. A dead link on the money path (/questionnaire/ or /coaching/) is a
    RED P0."""
    try:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "check_links.py"), "--max-urls", "300"],
            capture_output=True, text=True, timeout=900)
    except Exception as e:  # noqa: BLE001
        return [Finding("live-check-failed", YELLOW, "medium", "Live Check Failed",
                        str(e), "The live link checker couldn't run — check network/site.",
                        None, "check_links")]
    findings: list[Finding] = []
    # Sectioned parse: an entry line only counts for the section whose header
    # was seen last, and any non-entry line closes the section.
    challenged: list[str] = []
    dead: list[tuple[str, str]] = []
    section = None
    for line in proc.stdout.splitlines():
        if line.startswith("WAF-CHALLENGED"):
            section = "waf"
            continue
        if line.startswith("DEAD LINKS"):
            section = "dead"
            continue
        m = re.match(r"\s+(\d+|ERR)\s+(\S+)$", line)
        if not m:
            section = None
            continue
        if section == "waf":
            challenged.append(m.group(2))
        elif section == "dead":
            dead.append((m.group(1), m.group(2)))
    if challenged:
        shown = sorted(set(challenged))
        findings.append(Finding(
            "live-check-challenged", YELLOW, "low", "Live Check Challenged by WAF",
            f"{len(shown)} URLs unverifiable behind SiteGround's bot challenge "
            f"(HTTP 202) after backoff retries: " + " ".join(shown[:12])
            + (f" (+{len(shown) - 12} more)" if len(shown) > 12 else ""),
            "The scanner tripped SiteGround's bot protection, so these URLs could not "
            "be verified this run — an inconclusive scan, not an outage (Roadie Labs "
            "2026-07-22: 18 false money-path-404/dead-link findings were exactly "
            "this). Re-run later; investigate only if it persists across days.",
            None, "check_links"))
    for status, url in dead:
        money = any(marker in url for marker in MONEY_PATH_MARKERS)
        findings.append(Finding(
            "money-path-404" if money else "dead-link",
            RED if money else YELLOW,
            "critical" if money else "medium",
            "Money-Path 404" if money else "Dead Link",
            f"{status}  {url}",
            ("A conversion link a visitor clicks is dead — likely the "
             "questionnaire/coaching page isn't deployed or the cache "
             "wasn't purged. Money path, so a human confirms the "
             "re-deploy.") if money else
            "A same-site link is dead — a human confirms the fix.",
            None, "check_links"))
    # A crash or parse drift must be a finding, never a silent green:
    # rc 0 = clean, rc 1 = dead links (must have parsed some),
    # rc 2 = inconclusive (must have parsed a WAF block).
    rc = proc.returncode
    if rc not in (0, 1, 2) or (rc == 1 and not dead) or (rc == 2 and not challenged):
        findings.append(Finding(
            "live-check-failed", YELLOW, "medium", "Live Check Failed",
            f"check_links.py exited {rc} but its output parsed to "
            f"{len(dead)} dead / {len(challenged)} challenged URLs; "
            f"stderr tail: {proc.stderr[-400:].strip() or '(empty)'}",
            "The live link checker crashed or its output format drifted from what "
            "this parser expects — the site was NOT verified this run.",
            None, "check_links"))
    return findings


# ── Report + ledger ───────────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fingerprint(f: Finding) -> str:
    """Stable identity for a finding, so the baseline can recognise a recurrence."""
    return f"{f.code}::{f.detail}"


def load_baseline() -> set[str]:
    """Fingerprints the user has accepted as known backlog (not alerted nightly)."""
    if not BASELINE_FILE.exists():
        return set()
    try:
        return set(json.loads(BASELINE_FILE.read_text(encoding="utf-8")).get("fingerprints", []))
    except (OSError, json.JSONDecodeError):
        return set()


def mark_new(findings: list[Finding], baseline: set[str]) -> None:
    """Flag each finding new/known vs the baseline. SAFETY: RED findings (money
    path / security / systemic) are ALWAYS treated as new — you can never
    accidentally baseline away an emergency."""
    for f in findings:
        f.new = f.lane == RED or fingerprint(f) not in baseline


def write_outputs(findings: list[Finding], mode: dict) -> dict:
    IMMUNE_DIR.mkdir(exist_ok=True)
    lanes = {GREEN: 0, YELLOW: 0, RED: 0}
    for f in findings:
        lanes[f.lane] += 1
    new_ct = sum(1 for f in findings if f.new)
    report = {
        "brand": BRAND,
        "generated_at": now_iso(),
        "mode": mode,
        "counts": {"total": len(findings), **lanes,
                   "new": new_ct, "backlog": len(findings) - new_ct},
        "findings": [asdict(f) for f in findings],
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    # Append a compact run record to the scan telemetry (gitignored; feeds the streak).
    # The permanent ledger.jsonl is reserved for type:"fix" records (the memory) so it
    # only changes when something is actually healed — no git noise from routine scans.
    run_record = {
        "ts": report["generated_at"], "type": "scan", "brand": BRAND,
        "mode": mode, "counts": report["counts"],
        "codes": sorted({f.code for f in findings}),
    }
    with SCANS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(run_record) + "\n")
    return report


def print_digest(report: dict) -> None:
    findings = [Finding(**f) for f in report["findings"]]
    c = report["counts"]
    new = [f for f in findings if f.new]
    known = [f for f in findings if not f.new]
    print("=" * 60)
    print(f"🩺 {BRAND} — Immune scan  ({report['generated_at']})")
    print(f"   mode: {report['mode']}")
    print("=" * 60)

    def block(items, lane, emoji, label):
        items = [f for f in items if f.lane == lane]
        if not items:
            return
        print(f"\n{emoji} {label} ({len(items)})")
        # Group by code so a big class shows as a count + a few examples, not a wall.
        by_code: dict[str, list[Finding]] = {}
        for f in items:
            by_code.setdefault(f.code, []).append(f)
        for code, group in sorted(by_code.items(), key=lambda kv: -len(kv[1])):
            head = group[0]
            print(f"   • {code} ({len(group)}) — {head.remedy}")
            for f in group[:3]:
                print(f"       – {f.detail}")
            if len(group) > 3:
                print(f"       … +{len(group) - 3} more")

    if new:
        print(f"\n🆕 NEW SINCE LAST ACCEPTED BASELINE ({len(new)}) — this is what to look at")
        block(new, RED, "🔴", "ISSUE (money path / security / systemic — never auto-fixed)")
        block(new, YELLOW, "🟡", "NEEDS YOU (a fix is proposed → PR for your approval)")
        block(new, GREEN, "🟢", "AUTO-HEALABLE (the loop would fix these itself)")

    if known:
        by_code: dict[str, int] = {}
        for f in known:
            by_code[f.code] = by_code.get(f.code, 0) + 1
        print(f"\n📉 KNOWN BACKLOG ({len(known)}) — accepted, tracked, not alerted")
        for code, n in sorted(by_code.items(), key=lambda kv: -kv[1]):
            print(f"   · {n:>4}  {code}")

    print("\n" + "-" * 60)
    print(f"total {c['total']}  |  🆕 new {c.get('new', c['total'])}  📉 backlog {c.get('backlog', 0)}"
          f"  |  🟢 {c['green']}  🟡 {c['yellow']}  🔴 {c['red']}")
    if c["total"] == 0:
        print("🧬 All clear. Streak intact.")
    elif not new:
        print("🧬 Nothing new — all findings are accepted backlog.")
    print("-" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Gravel God Cycling immune system — Layer 1 verifier")
    parser.add_argument("--live", action="store_true",
                        help="also run the live money-path / 404 check (network)")
    parser.add_argument("--json", action="store_true", help="print machine JSON only")
    parser.add_argument("--fail-on", choices=["red", "any"], default="any",
                        help="exit non-zero on RED only, or on any NEW RED/YELLOW (default: any)")
    parser.add_argument("--accept-baseline", action="store_true",
                        help="catalogue ALL current findings as accepted backlog "
                             "(they stop alerting; only new/worsening issues alert after)")
    args = parser.parse_args()

    findings: list[Finding] = []
    findings += run_profile_audit()
    findings += check_search_index_parity()
    findings += check_tombstone_resurrection()
    findings += check_money_path_wiring()
    findings += check_fuzzy_duplicates()
    findings += check_security()
    if args.live:
        findings += run_live_link_check()

    if args.accept_baseline:
        # RED is never baselined (mark_new keeps it alerting); only accept non-RED.
        fps = sorted({fingerprint(f) for f in findings if f.lane != RED})
        IMMUNE_DIR.mkdir(exist_ok=True)
        BASELINE_FILE.write_text(json.dumps(
            {"accepted_at": now_iso(), "brand": BRAND, "fingerprints": fps}, indent=2) + "\n",
            encoding="utf-8")
        reds = sum(1 for f in findings if f.lane == RED)
        print(f"✅ Accepted {len(fps)} findings as known backlog for {BRAND}.")
        if reds:
            print(f"⚠️  {reds} RED finding(s) were NOT baselined — they will keep alerting.")
        return 0

    mark_new(findings, load_baseline())
    mode = {"live": args.live}
    report = write_outputs(findings, mode)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_digest(report)

    # Non-zero only on NEW attention-worthy findings, so CI / the agent gate on
    # what changed, not on accepted backlog.
    new = [f for f in findings if f.new]
    if args.fail_on == "red":
        return 1 if any(f.lane == RED for f in new) else 0
    return 1 if new else 0


if __name__ == "__main__":
    sys.exit(main())
