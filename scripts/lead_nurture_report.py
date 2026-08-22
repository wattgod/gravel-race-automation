#!/usr/bin/env python3
"""Print the Mission Control lead-conversation learning report.

Usage:
    railway run python3 scripts/lead_nurture_report.py
    railway run python3 scripts/lead_nurture_report.py --days 30 --json

This report is descriptive and approval-gated. It never edits sequence copy,
changes A/B weights, creates drafts, or sends email.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mission_control.services.lead_nurture import get_learning_metrics  # noqa: E402


def render(report: dict) -> str:
    lines = [
        f"Lead nurture — last {report['days']} days",
        (
            f"Sends {report['sends']} · replies {report['replies']} "
            f"({report['reply_rate']}%) · substantive {report['substantive_replies']} "
            f"· assisted wins {report['assisted_wins']}"
        ),
        (
            f"Trust: unsubscribes {report['unsubscribes']} · spam complaints "
            f"{report['spam_complaints']} · active-after-reply {report['active_after_reply']} "
            f"· draft conflicts {report['draft_conflicts']}"
        ),
        (
            f"Workflow: coach response {report['median_coach_response_hours'] or '—'}h · "
            f"suggestion acceptance "
            f"{str(report['suggestion_acceptance_rate']) + '%' if report['suggestion_acceptance_rate'] is not None else '—'} "
            f"· median edit "
            f"{str(report['median_edit_percent']) + '%' if report['median_edit_percent'] is not None else '—'}"
        ),
        "",
        f"{'question':<22}{'sends':>8}{'replies':>10}{'rate':>9}{'substantive':>14}{'median h':>10}{'state':>18}",
    ]
    for row in report["question_rows"]:
        median = "—" if row["median_reply_hours"] is None else str(row["median_reply_hours"])
        lines.append(
            f"{row['question_type']:<22}{row['sends']:>8}{row['replies']:>10}"
            f"{str(row['reply_rate']) + '%':>9}{row['substantive_replies']:>14}"
            f"{median:>10}{row['sample_state']:>18}"
        )
    lines.extend(["", "Recommendations:"])
    lines.extend(f"- {item}" for item in report["recommendations"])
    lines.extend(["", report["measurement_note"]])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.days < 1 or args.days > 730:
        parser.error("--days must be between 1 and 730")
    report = get_learning_metrics(args.days)
    print(json.dumps(report, indent=2) if args.json else render(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
