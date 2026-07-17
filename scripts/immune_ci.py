#!/usr/bin/env python3
"""Ecosystem CI + cron detector for Morning Command.

The detector emits ``immune_check.Finding`` records; it does not define a
parallel alert schema. Network collectors fail soft. ``--apply-safe`` is the
explicit home-repo repair-loop entry point: known mechanical workflow changes
are kept only when the triggering static finding disappears and the immune
verifier gains no new RED finding. Successful repairs are appended to the
permanent fix ledger.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
WORKFLOW_DIR = PROJECT_ROOT / ".github" / "workflows"
HEALTH_DIR = PROJECT_ROOT / "reports" / "health"
REPORT_FILE = HEALTH_DIR / "ci-cron.json"
LEDGER_FILE = PROJECT_ROOT / "immune" / "ledger.jsonl"

sys.path.insert(0, str(SCRIPT_DIR))
from immune_check import Finding, GREEN, RED, YELLOW, classify, fingerprint, now_iso  # noqa: E402

HOME_REPO = "wattgod/gravel-race-automation"
ECOSYSTEM_REPOS = (
    HOME_REPO,
    "wattgod/road-race-automation",
    "wattgod/athlete-custom-training-plan-pipeline",
    "wattgod/endurelabs",
)
FAILED_CONCLUSIONS = {
    "failure", "timed_out", "action_required", "startup_failure", "stale",
}
KNOWN_NOISE = (
    "cancelled by a newer run",
    "dependabot expected failure",
)
MISSING_SCHEDULE_CAUSES = (
    "no such file or directory", "can't open file", "cannot find module",
    "missing script", "secret not set", "secret is empty", "missing secret",
)


def _run(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def fetch_ci_runs(limit: int = 50) -> dict:
    """Fetch the last N ecosystem runs with the exact gh surface in the spec."""
    repos: dict[str, list[dict]] = {}
    errors: dict[str, str] = {}
    fields = "workflowName,conclusion,event,databaseId"
    for repo in ECOSYSTEM_REPOS:
        try:
            proc = _run([
                "gh", "run", "list", "-R", repo, "--limit", str(limit),
                "--json", fields,
            ])
            if proc.returncode:
                errors[repo] = (proc.stderr or proc.stdout or "gh failed").strip()[:240]
                repos[repo] = []
                continue
            value = json.loads(proc.stdout or "[]")
            repos[repo] = value if isinstance(value, list) else []
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            errors[repo] = f"{type(exc).__name__}: {exc}"[:240]
            repos[repo] = []
    return {"ok": not errors, "repos": repos, "errors": errors, "limit": limit}


def fetch_failed_log(repo: str, run_id: int | str) -> str:
    try:
        proc = _run(["gh", "run", "view", str(run_id), "-R", repo, "--log-failed"])
        return (proc.stdout or proc.stderr or "")[-12000:]
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _failure_reason(log: str) -> str:
    low = log.lower()
    if any(term in low for term in KNOWN_NOISE):
        return "known-noise"
    if "::set-output" in log:
        return "invalid workflow YAML: ::set-output"
    if "strategy" in low and ("not allowed" in low or "step" in low):
        return "invalid workflow YAML: step-level strategy"
    if "fromjson" in low and ("error" in low or "invalid" in low):
        return "invalid workflow YAML: bad fromJson"
    if "node 20" in low and "websocket" in low:
        return "Node-version drift: Node 20 without native WebSocket"
    if any(term in low for term in MISSING_SCHEDULE_CAUSES):
        return "missing script or missing/empty secret"
    if any(term in low for term in ("stripe", "webhook", "checkout", "questionnaire", "coaching", "fulfillment")):
        return "money-path failure: " + next(
            term for term in ("stripe", "webhook", "checkout", "questionnaire", "coaching", "fulfillment")
            if term in low
        )
    if any(term in low for term in ("secret exposure", "credential leak", "security incident")):
        return "security incident"
    if "pytest" in low or "assertionerror" in low or re.search(r"\btests? failed\b", low):
        return "failing test"
    if "fail:" in low and ("monitor" in low or "core web" in low):
        return "monitor flagging a real site issue"
    return "workflow failure"


def _workflow_path(workflow_name: str) -> Path | None:
    for path in sorted(WORKFLOW_DIR.glob("*.y*ml")):
        try:
            match = re.search(r"(?m)^name:\s*['\"]?(.+?)['\"]?\s*$", path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if match and match.group(1).strip() == workflow_name.strip():
            return path
    return None


def classify_ci_runs(
    payload: dict,
    log_loader: Callable[[str, int | str], str] = fetch_failed_log,
) -> tuple[list[Finding], int]:
    """Surface chronic (>=2 failed among N) and newly-red workflows only."""
    findings: list[Finding] = []
    suppressed = 0
    for repo, runs in payload.get("repos", {}).items():
        grouped: dict[str, list[dict]] = defaultdict(list)
        for run in runs:
            grouped[run.get("workflowName") or "unnamed workflow"].append(run)
        for workflow, history in grouped.items():
            history = history[:5]
            failures = [r for r in history if r.get("conclusion") in FAILED_CONCLUSIONS]
            latest_failed = bool(history and history[0].get("conclusion") in FAILED_CONCLUSIONS)
            previous_failed = len(history) > 1 and history[1].get("conclusion") in FAILED_CONCLUSIONS
            chronic = len(failures) >= 2
            newly_red = latest_failed and not previous_failed
            if not (chronic or newly_red):
                suppressed += len(history)
                continue

            latest = failures[0]
            log = log_loader(repo, latest.get("databaseId", ""))
            reason = _failure_reason(log)
            if reason == "known-noise":
                suppressed += 1
                continue
            scheduled = any(r.get("event") == "schedule" for r in failures)
            consecutive = 0
            for run in history:
                if run.get("conclusion") not in FAILED_CONCLUSIONS:
                    break
                consecutive += 1
            if scheduled and consecutive >= 3 and reason == "missing script or missing/empty secret":
                policy_message = (
                    "Scheduled workflow failed 3 consecutive runs due to a "
                    "missing script or missing/empty secret"
                )
            else:
                policy_message = reason
            detail = (
                f"{policy_message}: repo={repo} workflow={workflow} "
                f"run={latest.get('databaseId')} failures={len(failures)}/{len(history)}"
            )
            local_path = _workflow_path(workflow) if repo == HOME_REPO else None
            if local_path:
                detail += f" path={local_path.relative_to(PROJECT_ROOT)}"
            finding = classify(detail, source="github-actions")
            finding.title = f"{workflow} · {repo.split('/')[-1]}"
            if repo != HOME_REPO and finding.lane == GREEN:
                finding.lane = YELLOW
                finding.auto_fix = None
                finding.remedy = (
                    "Known safe pattern, but this is a sibling repo — propose a PR "
                    "for one-click approval; never auto-commit cross-repo."
                )
            findings.append(finding)
    return findings, suppressed


def scan_local_workflows() -> list[Finding]:
    """Detect known workflow failure patterns without network access."""
    findings: list[Finding] = []
    for path in sorted(WORKFLOW_DIR.glob("*.y*ml")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        active = "\n".join(line for line in text.splitlines()
                           if not line.lstrip().startswith("#"))
        reasons: list[str] = []
        if "::set-output" in active:
            reasons.append("invalid workflow YAML: ::set-output")
        if re.search(r"fromJson\([^\n]+\)\.include\s*!=\s*['\"]\[\]['\"]", active):
            reasons.append("invalid workflow YAML: bad fromJson")
        # A strategy key indented beneath an individual list step is invalid.
        lines = active.splitlines()
        in_steps = False
        steps_indent = 0
        for line in lines:
            if re.match(r"^(\s*)steps:\s*$", line):
                in_steps = True
                steps_indent = len(line) - len(line.lstrip())
                continue
            if in_steps and line.strip() and len(line) - len(line.lstrip()) <= steps_indent:
                in_steps = False
            if in_steps and re.match(r"^\s+strategy:\s*$", line):
                reasons.append("invalid workflow YAML: step-level strategy")
                break
        for reason in dict.fromkeys(reasons):
            finding = classify(f"{reason}: path={path.relative_to(PROJECT_ROOT)}", "workflow-static")
            finding.title = path.name
            findings.append(finding)
    return findings


def _http_json(url: str, headers: dict[str, str] | None = None) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "morning-command/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def collect_cron_runs() -> dict:
    """Read a fixture/snapshot, lightweight endpoint, or Supabase REST table."""
    snapshot = os.environ.get("CRON_HEALTH_SNAPSHOT")
    if snapshot:
        try:
            value = json.loads(Path(snapshot).read_text(encoding="utf-8"))
            return {"ok": True, "source": "snapshot", "runs": value.get("runs", value)}
        except (OSError, json.JSONDecodeError) as exc:
            return {"ok": False, "source": "snapshot", "error": str(exc), "runs": []}

    url = os.environ.get("ENDURELABS_CRON_HEALTH_URL")
    headers: dict[str, str] = {}
    if url:
        token = os.environ.get("ENDURELABS_CRON_HEALTH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    else:
        base = os.environ.get("ENDURELABS_SUPABASE_URL", "").rstrip("/")
        key = os.environ.get("ENDURELABS_SUPABASE_SERVICE_KEY", "")
        if base and key:
            table = os.environ.get("ENDURELABS_CRON_TRACKER_TABLE", "cron_tracker")
            url = f"{base}/rest/v1/{urllib.parse.quote(table)}?select=*&order=created_at.desc&limit=100"
            headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if not url:
        return {"ok": False, "source": "unconfigured", "error": "cron health unavailable", "runs": []}
    try:
        value = _http_json(url, headers)
        if isinstance(value, dict):
            value = value.get("runs", value.get("data", value.get("crons", [])))
        return {"ok": True, "source": "endpoint", "runs": value if isinstance(value, list) else []}
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"ok": False, "source": "endpoint", "error": f"{type(exc).__name__}: {exc}", "runs": []}


def _cron_name(row: dict) -> str:
    return str(row.get("cron_name") or row.get("job_name") or row.get("name") or row.get("cron") or "unknown-cron")


def _cron_failed(row: dict) -> bool:
    status = str(row.get("status") or row.get("conclusion") or "").lower()
    return status in FAILED_CONCLUSIONS or status in {"failed", "error"} or row.get("success") is False


def _work_count(row: dict) -> int | None:
    for key in ("work_count", "items_processed", "rows_affected", "resolved_count", "processed"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return None


def _int_or_zero(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def classify_cron_runs(payload: dict) -> tuple[list[Finding], int]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in payload.get("runs", []):
        if isinstance(row, dict):
            grouped[_cron_name(row)].append(row)
    findings: list[Finding] = []
    suppressed = 0
    for name, history in grouped.items():
        recent = history[:5]
        summary_failures = max(
            (_int_or_zero(row.get("consecutive_failures")) for row in recent), default=0)
        summary_zero_work = max(
            (_int_or_zero(row.get("zero_work_runs")) for row in recent), default=0)
        consecutive_failures = 0
        for row in recent:
            if not _cron_failed(row):
                break
            consecutive_failures += 1
        zero_work = sum(1 for row in recent if not _cron_failed(row) and _work_count(row) == 0)
        failures = max(consecutive_failures, summary_failures)
        no_work = max(zero_work, summary_zero_work)
        if failures >= 2:
            message = f"Cron failed repeatedly ({failures} consecutive failures): {name}"
        elif no_work >= 2:
            message = f"Cron doing 0 work ({no_work}/{len(recent)} recent runs): {name}"
        else:
            suppressed += len(recent)
            continue
        finding = classify(message, source="endurelabs-cron")
        finding.title = name
        findings.append(finding)
    return findings, suppressed


def build_report(ci_payload: dict | None = None, cron_payload: dict | None = None) -> dict:
    ci_payload = ci_payload if ci_payload is not None else fetch_ci_runs()
    cron_payload = cron_payload if cron_payload is not None else collect_cron_runs()
    ci_findings, ci_suppressed = classify_ci_runs(ci_payload)
    local_findings = scan_local_workflows()
    # Deduplicate a local static finding already explained by a home-repo run.
    keys = {(f.code, f.title) for f in ci_findings}
    for finding in local_findings:
        if (finding.code, finding.title) not in keys:
            ci_findings.append(finding)
    cron_findings, cron_suppressed = classify_cron_runs(cron_payload)
    findings = ci_findings + cron_findings
    return {
        "brand": "ecosystem",
        "generated_at": now_iso(),
        "counts": {
            "total": len(findings),
            GREEN: sum(f.lane == GREEN for f in findings),
            YELLOW: sum(f.lane == YELLOW for f in findings),
            RED: sum(f.lane == RED for f in findings),
            "suppressed": ci_suppressed + cron_suppressed,
        },
        "availability": {
            "ci": {"ok": ci_payload.get("ok", False), "errors": ci_payload.get("errors", {})},
            "cron": {"ok": cron_payload.get("ok", False), "error": cron_payload.get("error")},
        },
        "findings": [asdict(f) for f in findings],
    }


def _red_fingerprints(report: dict) -> set[str]:
    return {fingerprint(Finding(**f)) for f in report.get("findings", []) if f.get("lane") == RED}


def _repair_workflow(path: Path) -> list[str]:
    """Apply only exact, known-good textual migrations; return applied patterns."""
    text = path.read_text(encoding="utf-8")
    original = text
    applied: list[str] = []
    set_output = re.compile(
        r'^(\s*)print\(f"::set-output name=matrix::\{json\.dumps\(matrix\)\}"\)\s*\n?',
        re.MULTILINE,
    )
    if set_output.search(text):
        text = set_output.sub(
            lambda m: (
                f'{m.group(1)}with open(os.environ["GITHUB_OUTPUT"], "a") as output:\n'
                f'{m.group(1)}    output.write(f"matrix={{json.dumps(matrix)}}\\n")\n'
            ), text,
        )
        applied.append("replace ::set-output with GITHUB_OUTPUT")
    bad_guard = re.compile(r"fromJson\(([^\n]+)\)\.include\s*!=\s*'\[\]'")
    if bad_guard.search(text):
        text = bad_guard.sub(r"fromJson(\1).include[0] != null", text)
        applied.append("guard empty matrix after fromJson")
    if re.search(r"node-version:\s*['\"]?20['\"]?", text, re.I) and "supabase" in text.lower():
        text = re.sub(r"node-version:\s*['\"]?20['\"]?", "node-version: 22", text, flags=re.I)
        applied.append("bump Node 20 to Node 22")
    if text != original:
        path.write_text(text, encoding="utf-8")
    if _move_step_strategy(path):
        applied.append("move step-level strategy/matrix to the job")
    return applied


def _move_step_strategy(path: Path) -> bool:
    """Move an exact strategy block nested under steps to its containing job."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    steps_index = None
    steps_indent = None
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)steps:\s*$", line.rstrip("\n"))
        if match:
            steps_index = index
            steps_indent = len(match.group(1))
            continue
        if steps_index is None or not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= steps_indent:
            steps_index = None
            steps_indent = None
            continue
        if re.match(r"^\s*strategy:\s*$", line) and indent > steps_indent:
            end = index + 1
            while end < len(lines):
                next_line = lines[end]
                next_indent = len(next_line) - len(next_line.lstrip())
                if next_line.strip() and next_indent <= indent:
                    break
                end += 1
            dedent = indent - steps_indent
            block = [entry[dedent:] if entry.strip() else entry for entry in lines[index:end]]
            del lines[index:end]
            lines[steps_index:steps_index] = block
            path.write_text("".join(lines), encoding="utf-8")
            return True
    return False


def _disable_schedule(path: Path) -> bool:
    """Comment a top-level on.schedule block while retaining manual dispatch."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    schedule_start = None
    schedule_indent = 0
    for index, line in enumerate(lines):
        match = re.match(r"^(\s+)schedule:\s*(?:#.*)?$", line.rstrip("\n"))
        if match and len(match.group(1)) == 2:
            schedule_start = index
            schedule_indent = 2
            break
    if schedule_start is None:
        return False
    end = schedule_start + 1
    while end < len(lines):
        stripped = lines[end].strip()
        indent = len(lines[end]) - len(lines[end].lstrip())
        if stripped and not stripped.startswith("#") and indent <= schedule_indent:
            break
        end += 1
    for index in range(schedule_start, end):
        if lines[index].strip() and not lines[index].lstrip().startswith("#"):
            leading = len(lines[index]) - len(lines[index].lstrip())
            lines[index] = lines[index][:leading] + "# " + lines[index][leading:]
    path.write_text("".join(lines), encoding="utf-8")
    return True


def _immune_reds() -> set[str]:
    try:
        proc = _run([sys.executable, str(SCRIPT_DIR / "immune_check.py"), "--json", "--fail-on", "red"], 120)
        report = json.loads(proc.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {"verifier-unavailable"}
    return _red_fingerprints(report)


def _yaml_valid(path: Path) -> bool:
    try:
        import yaml
        yaml.safe_load(path.read_text(encoding="utf-8"))
        return True
    except (ImportError, OSError, ValueError):
        # The static detector remains the fallback when PyYAML is unavailable.
        return not any(finding.title == path.name for finding in scan_local_workflows())
    except yaml.YAMLError:
        return False


def apply_safe_repairs(before: dict | None = None) -> list[dict]:
    """Karpathy gate: keep only locally verified repairs and log each kept fix."""
    before = before or build_report(
        ci_payload={"ok": False, "repos": {}, "errors": {"offline": "static repair"}},
        cron_payload={"ok": False, "runs": [], "error": "not checked"},
    )
    before_red = _red_fingerprints(before)
    verifier_red_before = _immune_reds()
    candidates: dict[Path, list[dict]] = defaultdict(list)
    for raw in before["findings"]:
        if raw["lane"] != GREEN or raw["source"] not in {"workflow-static", "github-actions"}:
            continue
        match = re.search(r"path=([^\s]+)", raw["detail"])
        if match:
            candidates[PROJECT_ROOT / match.group(1)].append(raw)

    kept: list[dict] = []
    for path, source_findings in candidates.items():
        original = path.read_text(encoding="utf-8")
        applied = _repair_workflow(path)
        if not applied and any(raw["code"] == "ci-disable-broken-schedule" for raw in source_findings):
            if _disable_schedule(path):
                applied.append("disable broken schedule; retain workflow_dispatch")
        if not applied:
            continue
        after = build_report(ci_payload={"ok": False, "repos": {}, "errors": {"offline": "static repair"}},
                             cron_payload={"ok": False, "runs": [], "error": "not checked"})
        after_red = _red_fingerprints(after)
        remaining = [f for f in after["findings"] if f["source"] == "workflow-static" and path.name == f["title"]]
        schedule_disabled = not re.search(
            r"(?m)^  schedule:\s*$", path.read_text(encoding="utf-8")
        )
        schedule_repair = any(raw["code"] == "ci-disable-broken-schedule" for raw in source_findings)
        verifier_red_after = _immune_reds()
        if (after_red - before_red or verifier_red_after - verifier_red_before or remaining
                or not _yaml_valid(path)
                or (schedule_repair and not schedule_disabled)):
            path.write_text(original, encoding="utf-8")
            continue
        record = {
            "ts": now_iso(), "type": "fix", "brand": "gravel-god",
            "issue_class": source_findings[0]["code"], "severity": source_findings[0]["severity"],
            "what_broke": source_findings[0]["detail"],
            "root_cause": "Known GitHub Actions workflow drift pattern",
            "fix_applied": "; ".join(applied), "lane": GREEN,
            "regression_check": "immune_ci.py scan_local_workflows()",
            "verified": "triggering static finding removed; no new RED immune finding",
        }
        LEDGER_FILE.parent.mkdir(exist_ok=True)
        with LEDGER_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        kept.append(record)
    return kept


def main() -> int:
    parser = argparse.ArgumentParser(description="Morning Command CI/cron immune detector")
    parser.add_argument("--json", action="store_true", help="print machine JSON")
    parser.add_argument("--output", type=Path, default=REPORT_FILE)
    parser.add_argument("--apply-safe", action="store_true", help="apply verified home-repo workflow repairs")
    args = parser.parse_args()

    report = build_report()
    healed = apply_safe_repairs(report) if args.apply_safe else []
    if healed:
        report = build_report()
        for record in healed:
            if "disable broken schedule" not in record.get("fix_applied", ""):
                continue
            report["findings"].append(asdict(Finding(
                "ci-schedule-disabled", YELLOW, "medium", "Scheduled workflow disabled",
                record["what_broke"],
                "Repair the missing script/secret, then review and re-enable the schedule.",
                None, "immune-ledger",
            )))
            report["counts"]["total"] += 1
            report["counts"][YELLOW] += 1
    report["auto_healed"] = healed
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"CI/cron detector: {report['counts']['total']} findings, "
              f"{report['counts']['suppressed']} suppressed, {len(healed)} auto-healed")
        for source, status in report["availability"].items():
            if not status.get("ok"):
                print(f"  {source}: unavailable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
