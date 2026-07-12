#!/usr/bin/env python3
"""
Gravel God Cycling — Immune System digest email.

Renders immune/report.json into the morning digest and sends it via Resend.
Called at the end of the nightly immune run. Safe to run any time; if there's
nothing to report and --only-if-findings is set, it sends nothing.

Env (.env or environment):
    RESEND_API_KEY   required — your Resend key
    DIGEST_TO        recipient (default: gravelgodcoaching@gmail.com)
    DIGEST_FROM      sender    (default: immune@gravelgodcycling.com — must be a
                     Resend-verified domain)

Usage:
    python3 scripts/send_digest.py                 # always send
    python3 scripts/send_digest.py --only-if-findings   # send only when something needs attention
    python3 scripts/send_digest.py --print          # print the digest, don't send (dry run)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:  # noqa: BLE001
    pass

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_FILE = PROJECT_ROOT / "immune" / "report.json"
SCANS_FILE = PROJECT_ROOT / "immune" / "scans.jsonl"


def clean_scan_streak() -> int:
    """Count consecutive most-recent scans with zero findings (trust streak)."""
    if not SCANS_FILE.exists():
        return 0
    scans = [json.loads(l) for l in SCANS_FILE.read_text().splitlines() if l.strip()]
    streak = 0
    for rec in reversed(scans):
        if rec.get("counts", {}).get("total", 1) == 0:
            streak += 1
        else:
            break
    return streak


def render(report: dict) -> tuple[str, str, str]:
    """Return (subject, text_body, html_body). Leads with what's NEW since the
    accepted baseline; collapses accepted backlog to per-class counts."""
    c = report["counts"]
    findings = report["findings"]
    date = report["generated_at"][:10]
    brand = report.get("brand", "immune")
    new = [f for f in findings if f.get("new", True)]
    known = [f for f in findings if not f.get("new", True)]
    new_red = [f for f in new if f["lane"] == "red"]
    need = len(new)
    icon = "🚨" if new_red else "🩺"
    subject = f"{icon} Immune report — {date} ({need} new)" if need else \
              f"🩺 Immune report — {date} (all clear)"

    lines = [f"{brand} — Immune report · {date}", ""]

    def grouped_block(items, lane, emoji, label):
        items = [f for f in items if f["lane"] == lane]
        if not items:
            return
        by_code: dict[str, list] = {}
        for f in items:
            by_code.setdefault(f["code"], []).append(f)
        lines.append(f"{emoji} {label} ({len(items)})")
        for code, group in sorted(by_code.items(), key=lambda kv: -len(kv[1])):
            lines.append(f"   • {code} ({len(group)}) → {group[0]['remedy']}")
            for f in group[:3]:
                lines.append(f"       – {f['detail']}")
            if len(group) > 3:
                lines.append(f"       … +{len(group) - 3} more")
        lines.append("")

    if new:
        lines.append(f"🆕 NEW since last baseline ({len(new)}) — this is what to look at")
        lines.append("")
        grouped_block(new, "red", "🔴", "ISSUE (money path / security / systemic)")
        grouped_block(new, "yellow", "⚠️", "NEEDS YOU (proposed fix → PR)")
        grouped_block(new, "green", "✅", "AUTO-HEALABLE (loop would fix once enabled)")
    else:
        lines.append("🆕 Nothing new since your last baseline.")
        lines.append("")

    if known:
        by_code: dict[str, int] = {}
        for f in known:
            by_code[f["code"]] = by_code.get(f["code"], 0) + 1
        lines.append(f"📉 Known backlog ({len(known)}) — accepted, tracked, working down:")
        for code, n in sorted(by_code.items(), key=lambda kv: -kv[1]):
            lines.append(f"   · {n:>4}  {code}")
        lines.append("")

    if not findings:
        lines.append("🧬 All clear — nothing broke.")
    n = clean_scan_streak()
    lines.append(f"🧬 {n} clean scan{'s' if n != 1 else ''} in a row.")
    text = "\n".join(lines)

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = "<div style='font-family:monospace;white-space:pre-wrap;font-size:14px'>" \
           + esc(text) + "</div>"
    return subject, text, html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-if-findings", action="store_true")
    ap.add_argument("--print", dest="dry", action="store_true")
    args = ap.parse_args()

    if not REPORT_FILE.exists():
        print("No report.json — run immune_check.py first.", file=sys.stderr)
        return 1
    report = json.loads(REPORT_FILE.read_text())
    subject, text, html = render(report)

    if args.only_if_findings and report["counts"]["total"] == 0:
        print("No findings; skipping email.")
        return 0
    if args.dry:
        print(subject + "\n" + "-" * 60 + "\n" + text)
        return 0

    key = os.environ.get("RESEND_API_KEY")
    if not key:
        print("RESEND_API_KEY not set — printing digest instead of sending.\n", file=sys.stderr)
        print(subject + "\n" + text)
        return 0
    to = os.environ.get("DIGEST_TO", "gravelgodcoaching@gmail.com")
    sender = os.environ.get("DIGEST_FROM", "immune@gravelgodcycling.com")
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"from": sender, "to": [to], "subject": subject, "text": text, "html": html},
        timeout=30)
    if resp.status_code >= 300:
        print(f"Resend error {resp.status_code}: {resp.text}", file=sys.stderr)
        return 1
    print(f"Digest sent to {to}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
