#!/usr/bin/env python3
"""Build the XC Ski Labs Weekly in two steps, with Matti reacting in between.

1. ``--brief``: merge the evidence files from collect_xc_weekly.py, keep the
   last seven days, and ask Claude for the week's shortlist (headline, blurb
   and link per story, podcasts). Writes brief.json, evidence.json, brief.md.
   Matti reads it and replies with his reactions.
2. ``--from-brief DIR --reactions FILE``: write the issue from that shortlist
   and Matti's reactions. The take states his judgments, not the model's.
   The publication gate in xc_weekly_issue.validate_issue runs on the result;
   a draft that fails gets one repair attempt, then nothing is staged.
   Writes issue.json, evidence.json, preview.html, review.md, manifest.json.

There is no template, fallback issue, or take without Matti's reactions.
Nothing here sends email.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from collect_xc_weekly import load_sources, merge_items  # noqa: E402
from xc_weekly_issue import (  # noqa: E402
    IssueError, assemble_brief, assemble_issue, check_draft_limits, render_brief_markdown, render_email_html,
    render_review_markdown, validate_brief, validate_issue,
)

MODEL = "claude-opus-5-5"
VOICE_PATH = PROJECT_ROOT / "prompts" / "xc-weekly-voice.md"
WINDOW_DAYS = 7

# A comment that only approves the staged issue is not a reaction to redraft
# from; sending is a separate, manual step with the approved hash.
APPROVAL_ONLY = re.compile(
    r"^\W*(go|send|send it|ship it|approved?|lgtm|looks good|good to go|yes)\W*$", re.I)

SELECTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["subject", "preheader", "take", "stories", "podcasts"],
    "properties": {
        "subject": {"type": "string"},
        "preheader": {"type": "string"},
        "take": {"type": "array", "items": {"type": "string"}},
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["itemId", "alsoItemIds", "headline", "blurb"],
                "properties": {
                    "itemId": {"type": "string"},
                    # Other collected news items about the same event, shown as
                    # "also at" links. Empty when only one outlet covered it.
                    "alsoItemIds": {"type": "array", "items": {"type": "string"}},
                    "headline": {"type": "string"},
                    "blurb": {"type": "string"},
                },
            },
        },
        "podcasts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["itemId", "blurb"],
                "properties": {
                    "itemId": {"type": "string"},
                    "blurb": {"type": "string"},
                },
            },
        },
    },
}


_ITEM_SCHEMAS = {k: SELECTION_SCHEMA["properties"][k] for k in ("stories", "podcasts")}
BRIEF_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["stories", "podcasts"],
    "properties": _ITEM_SCHEMAS,
}


def load_evidence(paths: list[Path], now: datetime) -> dict:
    """Merge evidence files and keep the items from the last WINDOW_DAYS.

    Coverage keeps every run's errors, not just the latest run's, so a failed
    Wednesday still shows when Monday's fetch worked.
    """
    since = now - timedelta(days=WINDOW_DAYS)
    groups, coverage = [], {}
    for path in paths:
        data = json.loads(path.read_text())
        groups.append(data["items"])
        if datetime.fromisoformat(data["collectedAt"]) < since:
            continue  # a run before the week cannot vouch for this week's coverage
        for cov in data["coverage"]:
            row = coverage.setdefault(cov["id"], {**cov, "runs": 0, "failedRuns": [], "_at": ""})
            row["runs"] += 1
            if cov["errors"]:
                row["failedRuns"].append({"at": data["collectedAt"], "errors": cov["errors"]})
            if data["collectedAt"] >= row["_at"]:
                row.update({k: v for k, v in cov.items() if k != "kept"}, _at=data["collectedAt"])
    items = [i for i in merge_items(*groups)
             if since <= datetime.fromisoformat(i["published"]) <= now]
    for cov in coverage.values():
        cov["kept"] = sum(1 for i in items if i["sourceId"] == cov["id"])
        cov["failedRuns"].sort(key=lambda r: r["at"])
        cov.pop("_at", None)
    return {"since": since.isoformat(), "collectedAt": now.isoformat(),
            "items": items, "coverage": sorted(coverage.values(), key=lambda c: (c["kind"], c["id"]))}


def missing_core_sources(evidence: dict, core_ids: set[str] | None = None) -> list[str]:
    """Core sources (from config) that never fetched cleanly in a run this week."""
    if core_ids is None:
        core_ids = {s["id"] for s in load_sources()["news"] if s.get("core")}
    rows = {c["id"]: c for c in evidence["coverage"]}
    missing = []
    for source_id in sorted(core_ids):
        row = rows.get(source_id)
        if row is None or row.get("runs", 1) <= len(row.get("failedRuns", [])):
            missing.append(row["name"] if row else source_id)
    return missing


def evidence_prompt(evidence: dict) -> str:
    rows = [{
        "id": i["id"], "kind": i["kind"], "outlet": i["sourceName"], "lang": i["lang"],
        "published": i["published"][:16], "title": i["title"], "excerpt": i["excerpt"],
        "detail": i.get("detail", ""),
        "categories": i["categories"],
    } for i in evidence["items"]]
    return (
        f"The week runs from {evidence['since'][:10]} to {evidence['collectedAt'][:10]}. "
        f"Here are the {len(rows)} items collected from the cross-country outlets and podcasts. "
        "Pick and write the issue. Refer to items only by their id.\n\n"
        + json.dumps(rows, ensure_ascii=False, indent=1)
    )


def ask_claude(client, messages: list[dict], schema: dict = SELECTION_SCHEMA) -> tuple[dict, list]:
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": "high",
                       "format": {"type": "json_schema", "schema": schema}},
        system=VOICE_PATH.read_text(),
        messages=messages,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("the model declined to draft this week's issue")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("the draft hit max_tokens before finishing")
    text = "".join(block.text for block in response.content if block.type == "text")
    return json.loads(text), response.content


def _with_one_repair(client, messages: list[dict], schema: dict, build) -> dict:
    """Ask, build and gate; on a gate failure ask once more with the problems."""
    selection, content = ask_claude(client, messages, schema)
    try:
        return build(selection)
    except IssueError as exc:
        problems = str(exc)
    messages = messages + [
        {"role": "assistant", "content": content},
        {"role": "user", "content": (
            "The issue failed the publication check. Fix every problem below and return "
            "the whole issue again. Do not drop the take or the citations to get around a "
            f"rule.\n\nProblems: {problems}")},
    ]
    selection, _ = ask_claude(client, messages, schema)
    return build(selection)


def _client(client):
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    return client


def shortlist(evidence: dict, client=None) -> dict:
    """Step 1: the week's stories and podcasts for Matti to read. No take."""
    messages = [{"role": "user", "content": (
        evidence_prompt(evidence)
        + "\n\nThis is the shortlist step. Matti reads these headlines and reacts before "
        "anything else is written, so return only the stories and podcasts, each with its "
        "headline and blurb. Order the stories by what a cross-country skier would most "
        "want to know.")}]
    return _with_one_repair(_client(client), messages, BRIEF_SCHEMA,
                            lambda sel: validate_brief(assemble_brief(sel, evidence), evidence))


def reactions_from_comments(bodies: list[str]) -> str | None:
    """Matti's reactions, oldest first, or None when there is nothing to draft from.

    The latest comment decides: if it only approves the staged issue, nothing
    is redrafted (sending is a separate manual step).
    """
    kept = [b.strip() for b in bodies if b and b.strip()]
    if not kept or APPROVAL_ONLY.match(kept[-1]):
        return None
    kept = [b for b in kept if not APPROVAL_ONLY.match(b)]
    return "\n\n---\n\n".join(kept)


def reaction_prompt(evidence: dict, brief: dict, reactions: str) -> str:
    listed = [{"n": n, "itemId": s["itemId"], "alsoItemIds": [a["itemId"] for a in s.get("also", [])],
               "headline": s["headline"], "blurb": s["blurb"]}
              for n, s in enumerate(brief["stories"], 1)]
    pods = [{"itemId": p["itemId"], "blurb": p["blurb"]} for p in brief["podcasts"]]
    return (
        evidence_prompt(evidence)
        + "\n\nThis is the shortlist Matti read, numbered as he saw it:\n"
        + json.dumps({"stories": listed, "podcasts": pods}, ensure_ascii=False, indent=1)
        + "\n\nThese are Matti's reactions, oldest first; where they disagree, the later one "
        "wins. When he refers to a number, he means the shortlist number above.\n"
        "<reactions>\n" + reactions + "\n</reactions>\n\n"
        "Write the issue. Keep the shortlist's stories, headlines and blurbs unless his "
        "reactions ask you to add, drop, reorder or change one. The take states the "
        "judgments in his reactions, in his first person, keeping his own phrasing where it "
        "reads well. Add no opinion he did not give. If he reacted to only one story, the "
        "take is about that story. Cite stories by their number in your final story order."
    )


def draft(evidence: dict, brief: dict, reactions: str, issue_number: int, issue_date: str,
          client=None) -> dict:
    """Step 2: the issue, written from the shortlist and Matti's reactions."""
    if not reactions or not reactions.strip():
        raise IssueError("no reactions from Matti; the take is never written without them")
    messages = [{"role": "user", "content": reaction_prompt(evidence, brief, reactions)}]
    return _with_one_repair(
        _client(client), messages, SELECTION_SCHEMA,
        lambda sel: validate_issue(check_draft_limits(assemble_issue(sel, evidence, issue_number, issue_date)),
                                   evidence))


def stage_brief(brief: dict, evidence: dict, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "brief.json").write_text(json.dumps(brief, ensure_ascii=False, indent=2))
    (out / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    (out / "brief.md").write_text(render_brief_markdown(brief, evidence["coverage"]))
    return {"stories": len(brief["stories"]), "podcasts": len(brief["podcasts"]),
            "since": evidence["since"], "until": evidence["collectedAt"]}


def stage(issue: dict, evidence: dict, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "issue.json").write_text(json.dumps(issue, ensure_ascii=False, indent=2))
    (out / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    (out / "preview.html").write_text(render_email_html(issue))
    (out / "review.md").write_text(render_review_markdown(issue, evidence["coverage"]))
    manifest = {
        "issueNumber": issue["issueNumber"],
        "issueDate": issue["issueDate"],
        "contentHash": issue["contentHash"],
        "stories": len(issue["stories"]),
        "podcasts": len(issue["podcasts"]),
        "humanApprovalRequired": True,
        "autoSendAllowed": False,
        "model": MODEL,
        "stagedAt": datetime.now(timezone.utc).isoformat(),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", nargs="*", type=Path, help="collector output (with --brief)")
    parser.add_argument("--brief", action="store_true", help="step 1: write the headline shortlist")
    parser.add_argument("--from-brief", type=Path, help="step 2: a staged brief directory")
    parser.add_argument("--reactions", type=Path,
                        help="step 2: JSON list of Matti's comment bodies, oldest first")
    parser.add_argument("--issue-number", type=int)
    parser.add_argument("--issue-date", help="YYYY-MM-DD; defaults to today (UTC)")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.brief == bool(args.from_brief):
        parser.error("use exactly one of --brief or --from-brief")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set; nothing drafted", file=sys.stderr)
        return 1
    now = datetime.now(timezone.utc)

    if args.brief:
        if not args.evidence:
            parser.error("--brief needs at least one evidence file")
        evidence = load_evidence(args.evidence, now)
        missing = missing_core_sources(evidence)
        if missing:
            print(f"Core sources never fetched this week: {', '.join(missing)}; "
                  "a partial week is not staged", file=sys.stderr)
            return 1
        news = sum(1 for i in evidence["items"] if i["kind"] == "news")
        if news < 4:
            print(f"Only {news} news items this week; not enough for an issue, nothing staged", file=sys.stderr)
            return 1
        try:
            brief = shortlist(evidence)
        except (IssueError, RuntimeError, json.JSONDecodeError) as exc:
            print(f"XC Weekly shortlist refused: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(stage_brief(brief, evidence, args.output_dir)))
        return 0

    if args.reactions is None or args.issue_number is None:
        parser.error("--from-brief needs --reactions and --issue-number")
    reactions = reactions_from_comments(json.loads(args.reactions.read_text()))
    if reactions is None:
        print("No new reaction from Matti to draft from; nothing staged", file=sys.stderr)
        return 3
    evidence = json.loads((args.from_brief / "evidence.json").read_text())
    brief = json.loads((args.from_brief / "brief.json").read_text())
    issue_date = args.issue_date or now.date().isoformat()
    try:
        issue = draft(evidence, brief, reactions, args.issue_number, issue_date)
    except (IssueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"XC Weekly draft refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(stage(issue, evidence, args.output_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
