"""Contract and infrastructure tests for Gravel Weekly."""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_gravel_weekly import build_page, render_history_timeline  # noqa: E402
from generate_homepage import build_gravel_weekly_band  # noqa: E402
from validate_gravel_weekly import (  # noqa: E402
    IssueValidationError,
    compute_content_hash,
    load_issues,
    validate_issue,
)
from validate_gravel_weekly_history import (  # noqa: E402
    compute_history_content_hash,
    load_history_entries,
    load_public_history_entries,
    validate_history_entry,
)
from approve_gravel_weekly_history import apply_history_decision  # noqa: E402
from render_gravel_weekly_history_review import render_history_review  # noqa: E402
from seal_gravel_weekly_history import (  # noqa: E402
    main as seal_history_main,
    seal_history_entry,
)
from validate_gravel_weekly_history_decisions import validate_history_decision  # noqa: E402
from validate_gravel_weekly_backfill import validate_backfill_ledger  # noqa: E402
from no_ai_slop import audit_no_ai_slop  # noqa: E402
from prepare_gravel_weekly_backfill_ledger import build_initial_backfill_ledger  # noqa: E402
from send_gravel_weekly import SUBSCRIBER_SOURCES, build_email_html  # noqa: E402
from prepare_gravel_weekly_issue import prepare_issue  # noqa: E402
from approve_gravel_weekly_issue import approve_issue, build_decision_receipt  # noqa: E402
from seal_gravel_weekly_issue import main as seal_issue_main, seal_issue  # noqa: E402
from render_gravel_weekly_race_impact_review import render_review  # noqa: E402
from validate_gravel_weekly_decisions import validate_decision_receipt  # noqa: E402


def sample_issue():
    receipt = {
        "claimId": "claim_1",
        "canonicalUrl": "https://www.cyclingnews.com/example/",
        "publisher": "Cyclingnews",
        "publishedAt": "2026-08-27T12:00:00Z",
        "quoteExcerpt": "A bounded excerpt.",
        "transcriptStartSeconds": None,
        "transcriptEndSeconds": None,
    }
    impact = {
        "impactKind": "verify_field",
        "raceId": "gravel:unbound-gravel",
        "fieldPath": "race.vitals.distance",
        "currentValue": "200 miles",
        "proposedValue": "207 miles",
        "claimIds": ["claim_1"],
        "confidence": 0.9,
        "owner": "gravel-race-automation",
        "autoFixAllowed": False,
    }
    issue = {
        "schemaVersion": "gravel-weekly-issue/v1",
        "issueId": "gravel-weekly-001",
        "issueNumber": 1,
        "publicationDate": "2026-08-28",
        "status": "published",
        "slug": "2026-08-28",
        "title": "Gravel Weekly — August 28, 2026",
        "mastheadDeck": "The people, races, money and bad ideas moving gravel.",
        "currentThingStoryId": "story_1",
        "stories": [{
            "candidateId": "story_1",
            "headline": "Unbound changed the course",
            "dek": "The route got longer.",
            "storyKind": "route",
            "score": 93,
            "whatHappened": "The organizer published a revised distance.",
            "take": "Two hundred was apparently too tidy.",
            "takeProvenance": "human_approved",
            "receipts": [receipt],
            "raceImpacts": [impact],
        }],
        "calendarWatch": ["Registration closes Friday."],
        "raceImpacts": [impact],
        "retrospectives": [],
        "corrections": [],
        "sourceIndex": ["https://www.cyclingnews.com/example/"],
        "editorialApproval": {"approver": "Matti Rowe", "approvedAt": "2026-08-28T16:00:00Z"},
        "publishedAt": "2026-08-28T16:05:00Z",
        "updatedAt": "2026-08-28T16:05:00Z",
        "contentHash": "pending",
    }
    issue["contentHash"] = compute_content_hash(issue)
    return issue


def sample_history_entry():
    entry = {
        "schemaVersion": "gravel-weekly-history-entry/v1",
        "entryId": "history-teamification-2026",
        "activeFrom": "2026-02-10",
        "activeThrough": "2026-05-26",
        "status": "published",
        "headline": "The privateer became gravel's unpaid control group",
        "point": "Open registration survived while access to race-deciding support became less open.",
        "priorJudgment": "Top-level gravel remained unusually accessible to independent riders.",
        "changedJudgment": "The start stayed open while the competitive infrastructure became increasingly gated.",
        "stakes": "Independent riders face a different path to competitive relevance.",
        "credibleOpposition": "Teams can fund opportunity, and privateers can still win.",
        "whatHappened": "Contemporary reporting documented the arrival of larger teams and later examined financial and tactical consequences.",
        "take": "Gravel did not close the door. It installed a backstage entrance.",
        "takeProvenance": "human_approved",
        "uncertainty": "Team budgets and support access were not comprehensively public.",
        "editorialScore": 91,
        "editorialGates": {"party": "pass", "point": "pass", "friend": "pass", "craft": "pass", "hostileEditor": "pass"},
        "contemporaryReceipts": [
            {"claimId": "claim_team_1", "canonicalUrl": "https://www.cyclingnews.com/team-story/", "publisher": "Cyclingnews", "publishedAt": "2026-02-10T12:00:00Z", "quoteExcerpt": "A bounded contemporary excerpt.", "transcriptStartSeconds": None, "transcriptEndSeconds": None},
            {"claimId": "claim_team_2", "canonicalUrl": "https://velo.outsideonline.com/team-story/", "publisher": "Velo", "publishedAt": "2026-05-26T12:00:00Z", "quoteExcerpt": "A second bounded contemporary excerpt.", "transcriptStartSeconds": None, "transcriptEndSeconds": None},
        ],
        "laterEvidence": [
            {"claimId": "claim_team_later", "canonicalUrl": "https://example.com/later-analysis/", "publisher": "Official series", "publishedAt": "2026-06-10T12:00:00Z", "quoteExcerpt": "A later update.", "transcriptStartSeconds": None, "transcriptEndSeconds": None},
        ],
        "raceImpacts": [],
        "humanApprovalRequired": True,
        "autoPublishAllowed": False,
        "editorialApproval": {"approver": "Matti Rowe", "approvedAt": "2026-08-28T16:00:00Z"},
        "publishedAt": "2026-08-28T16:05:00Z",
        "updatedAt": "2026-08-28T16:05:00Z",
        "contentHash": "pending",
    }
    entry["contentHash"] = compute_history_content_hash(entry)
    return entry


def sample_history_draft():
    entry = sample_history_entry()
    entry.update({
        "status": "draft",
        "headline": "MODEL DRAFT: The privateer became gravel's control group",
        "take": "Model draft, not Matti's approved view: Gravel installed a backstage entrance.",
        "takeProvenance": "model_draft",
        "editorialApproval": None,
        "publishedAt": None,
        "updatedAt": "2026-08-27T17:00:00Z",
    })
    entry["contentHash"] = compute_history_content_hash(entry)
    return entry


def sample_history_approval(draft=None):
    draft = draft or sample_history_draft()
    return {
        "schemaVersion": "gravel-weekly-history-approval/v1",
        "entryId": draft["entryId"],
        "reviewedDraftContentHash": draft["contentHash"],
        "decision": "approve",
        "approver": "Matti Rowe",
        "decidedAt": "2026-08-28T16:00:00Z",
        "headline": "The privateer became gravel's control group",
        "take": "Gravel kept the front door open and installed a backstage entrance.",
        "editSummary": "Removed the model label and tightened the judgment.",
        "reason": None,
    }


def passing_editorial_gate():
    return {
        "partyTest": {
            "verdict": "pass",
            "rationale": "The premise is legible, consequential, and has a clean escalation.",
        },
        "pointTest": {
            "verdict": "pass",
            "point": "A small route revision exposes the weakness of preparing for a brand instead of terrain.",
        },
        "friendTest": {
            "verdict": "pass",
            "repeatableLine": "Train for the ground, not the logo.",
            "nonObviousPayoff": "The branded number is distorting preparation decisions.",
            "changedUnderstanding": "The reader stops treating the advertised distance as the preparation model.",
            "socialCost": "Low because this supplies a usable judgment, not a semantic observation.",
            "killReason": "none",
        },
        "storyArc": {
            "hook": "The 200-mile race is no longer 200 miles.",
            "stakes": "Preparation and the public record change.",
            "tension": "The mythology depends on a number the course no longer respects.",
            "turn": "The minor revision exposes misplaced certainty.",
            "landing": "Train for the ground, not the logo.",
        },
        "comedy": {
            "mechanics": ["incongruity", "specificity"],
            "setup": "The race sells a tidy number.",
            "turn": "The course file declined the assignment.",
            "tag": "Two hundred was apparently too tidy.",
            "rhetoricalLicense": "Personification is confined to the clearly rhetorical take.",
            "factualBoundary": "Distance, chronology, motives, safety, and results remain literal and sourced.",
        },
        "decision": "pass",
    }


def with_passing_prose_gate(packet):
    suggested = packet["suggestedTake"]
    packet["proseGate"] = audit_no_ai_slop({
        "headline": packet["suggestedHeadline"],
        "dek": packet["suggestedDek"],
        "what_happened": packet["whatHappened"],
        "take": suggested["copy"],
    })
    assert packet["proseGate"]["verdict"] == "pass"
    return packet


def sample_draft():
    issue = sample_issue()
    issue.update({
        "status": "draft",
        "editorialApproval": None,
        "publishedAt": None,
        "updatedAt": "2026-08-27T17:00:00Z",
    })
    issue["stories"][0]["headline"] = "MODEL DRAFT headline"
    issue["stories"][0]["dek"] = "MODEL DRAFT deck"
    issue["stories"][0]["take"] = "Editable model draft, not Matti's approved view."
    issue["stories"][0]["takeProvenance"] = "model_draft"
    issue["contentHash"] = compute_content_hash(issue)
    return issue


def sample_approval():
    return {
        "schemaVersion": "gravel-weekly-approval/v1",
        "issueId": "gravel-weekly-001",
        "approver": "Matti Rowe",
        "approvedAt": "2026-08-28T16:00:00Z",
        "currentThingStoryId": "story_1",
        "stories": [{
            "candidateId": "story_1",
            "decision": "approve",
            "headline": "The approved headline",
            "dek": "The approved deck.",
            "take": "The approved take makes a concrete judgment.",
            "editSummary": "Removed throat-clearing and sharpened the consequence.",
        }],
    }


def test_issue_contract_requires_receipts_approval_and_hash():
    issue = sample_issue()
    assert validate_issue(issue)["issueId"] == "gravel-weekly-001"

    missing_receipts = copy.deepcopy(issue)
    missing_receipts["stories"][0]["receipts"] = []
    with pytest.raises(IssueValidationError, match="receipts"):
        validate_issue(missing_receipts, verify_hash=False)

    missing_approval = copy.deepcopy(issue)
    missing_approval["editorialApproval"] = None
    with pytest.raises(IssueValidationError, match="approval"):
        validate_issue(missing_approval, verify_hash=False)

    forged = copy.deepcopy(issue)
    forged["stories"][0]["take"] = "Silently changed after approval."
    with pytest.raises(IssueValidationError, match="contentHash mismatch"):
        validate_issue(forged)

    model_copy = copy.deepcopy(issue)
    model_copy["stories"][0]["take"] = "Editable model draft, not Matti's approved view."
    with pytest.raises(IssueValidationError, match="model-draft"):
        validate_issue(model_copy, verify_hash=False)

    slopped = copy.deepcopy(issue)
    slopped["stories"][0]["take"] = "The future isn't coming. It's already here."
    with pytest.raises(IssueValidationError, match="no-ai-slop gate.*fake_profound_kicker"):
        validate_issue(slopped, verify_hash=False)

    slopped_draft = sample_draft()
    slopped_draft["stories"][0]["take"] = "The future isn't coming. It's already here."
    with pytest.raises(IssueValidationError, match="no-ai-slop gate.*fake_profound_kicker"):
        validate_issue(slopped_draft, verify_hash=False)


def test_no_ai_slop_audit_names_patterns_without_guessing_authorship():
    clean = audit_no_ai_slop({
        "headline": "Gravel Worlds Moved Lunch Forty Miles",
        "take": "Bring another bottle and stop pretending total mileage is the useful number.",
    })
    assert clean["verdict"] == "pass"
    assert clean["findings"] == []
    assert clean["humanApprovalRequired"] is True
    assert clean["autoPublishAllowed"] is False

    failed = audit_no_ai_slop({
        "headline": "This Changes Everything",
        "take": "Here's the thing: it's not a race update. It's a transformative paradigm shift.",
    })
    assert failed["verdict"] == "fail"
    assert {finding["pattern"] for finding in failed["findings"]} >= {
        "banned_word", "empty_opener", "binary_contrast",
    }
    assert len(failed["checkedTextHash"]) == 64

    factual_pair = audit_no_ai_slop({"what_happened": "Selection considered not only results but also interest in the series."})
    assert factual_pair["verdict"] == "pass"


def test_review_prepares_a_draft_but_cannot_imply_approval():
    packet = with_passing_prose_gate({
        "candidateId": "story_1",
        "editorialGate": passing_editorial_gate(),
        "suggestedTake": {"label": "model_draft", "copy": "Editable model draft, not Matti's approved view: A sharp take."},
        "suggestedHeadline": "The course moved",
        "suggestedDek": "A small mileage change hides a larger terrain question.",
        "whatHappened": "The organizer published a revised distance. It affects preparation.",
        "receipts": [sample_issue()["stories"][0]["receipts"][0]],
        "raceImpacts": sample_issue()["stories"][0]["raceImpacts"],
    })
    review = {
        "schemaVersion": "gravel-weekly-review/v1",
        "candidates": [{
            "id": "story_1", "score": 93, "headline": "Unbound changed the course",
            "storyKind": "route",
        }],
        "packets": [packet],
    }
    issue = prepare_issue(review, "2026-08-28", 1, now="2026-08-27T17:00:00Z")
    assert issue["status"] == "draft"
    assert issue["editorialApproval"] is None
    assert issue["currentThingStoryId"] == "story_1"
    assert issue["stories"][0]["headline"] == "The course moved"
    assert issue["stories"][0]["takeProvenance"] == "model_draft"
    assert validate_issue(issue)["contentHash"] == issue["contentHash"]
    preview = build_page(issue, [issue], latest=True)
    assert "DRAFT — NOT PUBLISHED" in preview
    assert "THE TAKE — MODEL DRAFT" in preview
    assert "application/ld+json" not in preview


def test_human_approval_bridge_changes_only_editorial_copy_and_stays_non_deployable():
    draft = sample_draft()
    approved = approve_issue(draft, sample_approval())

    assert approved["status"] == "approved"
    assert approved["publishedAt"] is None
    assert approved["editorialApproval"] == {
        "approver": "Matti Rowe", "approvedAt": "2026-08-28T16:00:00Z",
    }
    assert approved["stories"][0]["headline"] == "The approved headline"
    assert approved["stories"][0]["take"] == "The approved take makes a concrete judgment."
    assert approved["stories"][0]["takeProvenance"] == "human_approved"
    for field in ("score", "storyKind", "whatHappened", "receipts", "raceImpacts"):
        assert approved["stories"][0][field] == draft["stories"][0][field]
    assert approved["contentHash"] == compute_content_hash(approved)
    with pytest.raises(ValueError, match="published issue"):
        render_review(approved)


def test_human_approval_produces_a_durable_control_plane_decision_receipt():
    draft = sample_draft()
    approval = sample_approval()
    approved = approve_issue(draft, approval)
    receipt = build_decision_receipt(draft, approval, approved)

    assert receipt["reviewedDraftContentHash"] == draft["contentHash"]
    assert receipt["decidedBy"] == "Matti Rowe"
    assert receipt["decisions"] == [{
        "schemaVersion": "editorial-decision/v1",
        "issueId": "gravel-weekly-001",
        "candidateId": "story_1",
        "decision": "approve",
        "reason": "Approved for Gravel Weekly #001.",
        "decidedBy": "Matti Rowe",
        "decidedAt": "2026-08-28T16:00:00Z",
        "suggestedCopy": "Editable model draft, not Matti's approved view.",
        "approvedCopy": "The approved take makes a concrete judgment.",
        "editSummary": "Removed throat-clearing and sharpened the consequence.",
    }]
    assert validate_decision_receipt(receipt, approved) == receipt
    assert validate_decision_receipt(receipt, seal_issue(approved, "2026-08-28T16:05:00Z")) == receipt

    forged = copy.deepcopy(receipt)
    forged["decisions"][0]["approvedCopy"] = "Different copy after approval."
    with pytest.raises(ValueError, match="approved copy does not match"):
        validate_decision_receipt(forged, approved)


def test_approval_bridge_requires_an_exact_human_decision_for_every_reviewed_story():
    draft = sample_draft()
    missing = sample_approval()
    missing["stories"] = []
    with pytest.raises(ValueError, match="decide every reviewed story"):
        approve_issue(draft, missing)

    extra = sample_approval()
    extra["stories"].append({
        "candidateId": "story_unreviewed", "decision": "reject", "reason": "Not reviewed.",
    })
    with pytest.raises(ValueError, match=r"extra=\['story_unreviewed'\]"):
        approve_issue(draft, extra)

    duplicate = sample_approval()
    duplicate["stories"].append(copy.deepcopy(duplicate["stories"][0]))
    with pytest.raises(ValueError, match="must be unique"):
        approve_issue(draft, duplicate)

    rejected = sample_approval()
    rejected["stories"] = [{
        "candidateId": "story_1", "decision": "reject", "reason": "The premise is still slop.",
    }]
    rejected["currentThingStoryId"] = None
    with pytest.raises(ValueError, match="at least one approved story"):
        approve_issue(draft, rejected)

    misleading = sample_approval()
    misleading["whatHappened"] = "Quietly replace the reviewed facts."
    with pytest.raises(ValueError, match="unsupported fields"):
        approve_issue(draft, misleading)


def test_approval_bridge_rejects_copy_that_still_claims_to_be_a_model_draft():
    approval = sample_approval()
    approval["stories"][0]["take"] = "Editable model draft, not Matti's approved view."
    with pytest.raises(IssueValidationError, match="model-draft"):
        approve_issue(sample_draft(), approval)


def test_sealing_is_a_separate_copy_preserving_step_after_approval():
    approved = approve_issue(sample_draft(), sample_approval())
    sealed = seal_issue(approved, "2026-08-28T16:05:00Z")

    assert sealed["status"] == "published"
    assert sealed["publishedAt"] == "2026-08-28T16:05:00Z"
    assert sealed["stories"] == approved["stories"]
    assert sealed["raceImpacts"] == approved["raceImpacts"]
    assert sealed["contentHash"] == compute_content_hash(sealed)

    with pytest.raises(ValueError, match="status=approved"):
        seal_issue(sample_draft(), "2026-08-28T16:05:00Z")
    with pytest.raises(ValueError, match="cannot precede"):
        seal_issue(approved, "2026-08-28T15:59:59Z")
    with pytest.raises(ValueError, match="include a timezone"):
        seal_issue(approved, "2026-08-28T16:05:00")


def test_sealing_writes_the_issue_and_its_canonical_decision_receipt_together(tmp_path, monkeypatch):
    draft = sample_draft()
    approval = sample_approval()
    approved = approve_issue(draft, approval)
    receipt = build_decision_receipt(draft, approval, approved)
    approved_path = tmp_path / "approved.json"
    receipt_path = tmp_path / "receipt.json"
    issue_output = tmp_path / "issues" / "2026-08-28.json"
    decision_output = tmp_path / "decisions" / "2026-08-28.json"
    approved_path.write_text(json.dumps(approved))
    receipt_path.write_text(json.dumps(receipt))
    monkeypatch.setattr(sys, "argv", [
        "seal_gravel_weekly_issue.py", str(approved_path),
        "--published-at", "2026-08-28T16:05:00Z",
        "--decision-receipt", str(receipt_path),
        "--output", str(issue_output),
        "--decision-output", str(decision_output),
    ])

    assert seal_issue_main() == 0
    sealed = json.loads(issue_output.read_text())
    canonical_receipt = json.loads(decision_output.read_text())
    assert sealed["status"] == "published"
    assert validate_decision_receipt(canonical_receipt, sealed) == receipt

    orphan_output = tmp_path / "orphan.json"
    monkeypatch.setattr(sys, "argv", [
        "seal_gravel_weekly_issue.py", str(approved_path),
        "--published-at", "2026-08-28T16:05:00Z",
        "--decision-receipt", str(tmp_path / "missing.json"),
        "--output", str(orphan_output),
    ])
    with pytest.raises(SystemExit, match="Decision receipt not found"):
        seal_issue_main()
    assert not orphan_output.exists()


@pytest.mark.parametrize("gate_mutation", ["missing", "hold", "party_hold", "no_point", "friend_fail", "friend_kill", "no_mechanics"])
def test_review_excludes_stories_that_do_not_clear_every_editorial_gate(gate_mutation):
    gate = passing_editorial_gate()
    if gate_mutation == "hold":
        gate["decision"] = "hold"
    elif gate_mutation == "party_hold":
        gate["partyTest"]["verdict"] = "hold"
    elif gate_mutation == "no_point":
        gate["pointTest"]["point"] = ""
    elif gate_mutation == "friend_fail":
        gate["friendTest"]["verdict"] = "fail"
        gate["friendTest"]["killReason"] = "obvious_truism"
    elif gate_mutation == "friend_kill":
        gate["friendTest"]["killReason"] = "cringe_overframing"
    elif gate_mutation == "no_mechanics":
        gate["comedy"]["mechanics"] = []
    packet = with_passing_prose_gate({
        "candidateId": "story_1",
        "suggestedTake": {"label": "model_draft", "copy": "A sharp take."},
        "suggestedHeadline": "The course moved",
        "suggestedDek": "A small mileage change hides a larger terrain question.",
        "whatHappened": "The organizer published a revised distance.",
        "receipts": [sample_issue()["stories"][0]["receipts"][0]],
        "raceImpacts": sample_issue()["stories"][0]["raceImpacts"],
    })
    if gate_mutation != "missing":
        packet["editorialGate"] = gate
    review = {
        "schemaVersion": "gravel-weekly-review/v1",
        "candidates": [{"id": "story_1", "score": 93, "headline": "Unbound changed the course", "storyKind": "route"}],
        "packets": [packet],
    }
    issue = prepare_issue(review, "2026-08-28", 1, now="2026-08-27T17:00:00Z")
    assert issue["stories"] == []
    assert issue["currentThingStoryId"] is None


@pytest.mark.parametrize("prose_mutation", ["missing", "failed", "stale"])
def test_review_excludes_missing_failed_or_stale_prose_gates(prose_mutation):
    packet = with_passing_prose_gate({
        "candidateId": "story_1",
        "editorialGate": passing_editorial_gate(),
        "suggestedTake": {"label": "model_draft", "copy": "A sharp take."},
        "suggestedHeadline": "The course moved",
        "suggestedDek": "A small mileage change hides a larger terrain question.",
        "whatHappened": "The organizer published a revised distance.",
        "receipts": [sample_issue()["stories"][0]["receipts"][0]],
        "raceImpacts": sample_issue()["stories"][0]["raceImpacts"],
    })
    if prose_mutation == "missing":
        del packet["proseGate"]
    elif prose_mutation == "failed":
        packet["suggestedTake"]["copy"] = "The future isn't coming. It's already here."
        packet["proseGate"] = audit_no_ai_slop({
            "headline": packet["suggestedHeadline"],
            "dek": packet["suggestedDek"],
            "what_happened": packet["whatHappened"],
            "take": packet["suggestedTake"]["copy"],
        })
        assert packet["proseGate"]["verdict"] == "fail"
    else:
        packet["suggestedHeadline"] = "The course moved again"
    review = {
        "schemaVersion": "gravel-weekly-review/v1",
        "candidates": [{
            "id": "story_1", "score": 93,
            "headline": "Unbound changed the course", "storyKind": "route",
        }],
        "packets": [packet],
    }
    issue = prepare_issue(review, "2026-08-28", 1, now="2026-08-27T17:00:00Z")
    assert issue["stories"] == []
    assert issue["currentThingStoryId"] is None


def test_current_thing_requires_editorial_score_of_85():
    issue = sample_issue()
    issue["stories"][0]["score"] = 84
    with pytest.raises(IssueValidationError, match="at least 85"):
        validate_issue(issue, verify_hash=False)


def test_issue_race_impacts_exactly_preserve_story_impacts_and_receipts():
    issue = sample_issue()
    issue["raceImpacts"] = []
    with pytest.raises(IssueValidationError, match="exactly preserve"):
        validate_issue(issue, verify_hash=False)

    missing_receipt = sample_issue()
    missing_receipt["stories"][0]["raceImpacts"][0]["claimIds"] = ["claim_missing"]
    missing_receipt["raceImpacts"][0]["claimIds"] = ["claim_missing"]
    with pytest.raises(IssueValidationError, match="without story receipts"):
        validate_issue(missing_receipt, verify_hash=False)


def test_published_issue_renders_immutable_race_impact_review():
    review, count = render_review(sample_issue())
    assert count == 1
    assert "meaningful-race-impact-count: 1" in review
    assert "Gravel Weekly #001 race-impact review" in review
    assert "gravel:unbound-gravel" in review
    assert "claim_1" in review
    assert "content hash" in review
    assert "does not authorize or perform" in review

    draft = sample_issue()
    draft["status"] = "draft"
    draft["editorialApproval"] = None
    draft["publishedAt"] = None
    draft["contentHash"] = compute_content_hash(draft)
    with pytest.raises(ValueError, match="published issue"):
        render_review(draft)


def test_rendered_issue_preserves_site_infrastructure_and_honest_form():
    issue = sample_issue()
    page = build_page(issue, [issue], latest=True)
    assert "GRAVEL <span>WEEKLY</span>" in page
    assert "THE CURRENT THING" in page
    assert "G-EJJZ9T6M52" in page
    assert "gravel_weekly_subscribe" in page
    assert "if (!response.ok)" in page
    assert "textContent" in page
    assert "innerHTML" not in page
    assert "get_site_header_js" not in page
    assert "</main>\n<script>\n// ── Hamburger mobile menu" in page
    assert page.count("Hamburger mobile menu") == 1
    assert "/gravel-weekly/2026-08-28/" in page
    assert "rounded" not in page.lower()


def test_retrospective_requires_receipts_and_human_approval_then_renders_memory_timeline(tmp_path):
    prior = sample_issue()
    current = copy.deepcopy(prior)
    current.update({
        "issueId": "gravel-weekly-002",
        "issueNumber": 2,
        "publicationDate": "2026-09-04",
        "slug": "2026-09-04",
        "title": "Gravel Weekly — September 4, 2026",
        "publishedAt": "2026-09-04T16:05:00Z",
        "updatedAt": "2026-09-04T16:05:00Z",
        "retrospectives": [{
            "verdict": "aged_poorly",
            "priorIssueId": prior["issueId"],
            "priorStoryId": "story_1",
            "headline": "The tidy explanation did not survive the next week",
            "whatChanged": "The organizer published a second revision that contradicted the original rationale.",
            "assessment": "We treated a moving target like a settled argument. That was too confident.",
            "assessmentProvenance": "human_approved",
            "receipts": [prior["stories"][0]["receipts"][0]],
        }],
    })
    current["contentHash"] = compute_content_hash(current)
    prior_path = tmp_path / "2026-08-28.json"
    current_path = tmp_path / "2026-09-04.json"
    prior_path.write_text(json.dumps(prior))
    current_path.write_text(json.dumps(current))

    issues = load_issues(tmp_path)
    page = build_page(current, issues, latest=True)
    assert "THE RECEIPTS ON US" in page
    assert "THIS AGED POORLY" in page
    assert "/gravel-weekly/2026-08-28/#story_1" in page
    assert "We treated a moving target" in page
    assert "THE TAKE:" in page

    model_assessment = copy.deepcopy(current)
    model_assessment["retrospectives"][0]["assessmentProvenance"] = "model_draft"
    with pytest.raises(IssueValidationError, match="human-approved provenance"):
        validate_issue(model_assessment, verify_hash=False)

    missing_receipts = copy.deepcopy(current)
    missing_receipts["retrospectives"][0]["receipts"] = []
    with pytest.raises(IssueValidationError, match="receipts"):
        validate_issue(missing_receipts, verify_hash=False)


def test_retrospective_must_reference_an_earlier_archived_story(tmp_path):
    issue = sample_issue()
    issue["retrospectives"] = [{
        "verdict": "still_developing",
        "priorIssueId": "missing-issue",
        "priorStoryId": "story_1",
        "headline": "The prediction is still moving",
        "whatChanged": "New evidence arrived without resolving the original question.",
        "assessment": "Keep the take open until the organizer publishes the final course.",
        "assessmentProvenance": "human_approved",
        "receipts": [issue["stories"][0]["receipts"][0]],
    }]
    issue["contentHash"] = compute_content_hash(issue)
    (tmp_path / "2026-08-28.json").write_text(json.dumps(issue))
    with pytest.raises(IssueValidationError, match="archived issue"):
        load_issues(tmp_path)


def test_historical_current_thing_requires_contemporary_corroboration_and_human_gates(tmp_path):
    entry = sample_history_entry()
    assert validate_history_entry(entry)["entryId"] == "history-teamification-2026"
    (tmp_path / "2026-teamification.json").write_text(json.dumps(entry))
    assert load_history_entries(tmp_path)[0]["entryId"] == entry["entryId"]

    one_publisher = copy.deepcopy(entry)
    one_publisher["contemporaryReceipts"][1]["publisher"] = "Cyclingnews"
    with pytest.raises(IssueValidationError, match="two contemporary publishers"):
        validate_history_entry(one_publisher, verify_hash=False)

    held_gate = copy.deepcopy(entry)
    held_gate["editorialGates"]["friend"] = "hold"
    with pytest.raises(IssueValidationError, match="every editorial gate"):
        validate_history_entry(held_gate, verify_hash=False)

    model_take = copy.deepcopy(entry)
    model_take["takeProvenance"] = "model_draft"
    with pytest.raises(IssueValidationError, match="human-approved provenance"):
        validate_history_entry(model_take, verify_hash=False)

    slopped = copy.deepcopy(entry)
    slopped["take"] = "Here's what nobody tells you: this changes everything."
    with pytest.raises(IssueValidationError, match="no-ai-slop gate"):
        validate_history_entry(slopped, verify_hash=False)

    slopped_draft = sample_history_draft()
    slopped_draft["take"] = "Here's what nobody tells you: this changes everything."
    with pytest.raises(IssueValidationError, match="no-ai-slop gate"):
        validate_history_entry(slopped_draft, verify_hash=False)


def test_historical_approval_is_hash_bound_copy_limited_and_non_public(tmp_path):
    draft = sample_history_draft()
    approved, decision = apply_history_decision(draft, sample_history_approval(draft))

    assert approved is not None
    assert approved["status"] == "approved"
    assert approved["publishedAt"] is None
    assert approved["headline"] == "The privateer became gravel's control group"
    assert approved["take"] == "Gravel kept the front door open and installed a backstage entrance."
    assert approved["takeProvenance"] == "human_approved"
    assert approved["editorialApproval"] == {
        "approver": "Matti Rowe", "approvedAt": "2026-08-28T16:00:00Z",
    }
    for field in (
        "point", "priorJudgment", "changedJudgment", "stakes", "credibleOpposition",
        "whatHappened", "uncertainty", "editorialScore", "editorialGates",
        "contemporaryReceipts", "laterEvidence", "raceImpacts",
    ):
        assert approved[field] == draft[field]
    assert decision["reviewedDraftContentHash"] == draft["contentHash"]
    assert validate_history_decision(decision, approved) == decision

    (tmp_path / "draft.json").write_text(json.dumps(draft))
    assert load_public_history_entries(tmp_path) == []

    stale = sample_history_approval(draft)
    stale["reviewedDraftContentHash"] = "0" * 64
    with pytest.raises(ValueError, match="exact reviewed draft"):
        apply_history_decision(draft, stale)

    factual_edit = sample_history_approval(draft)
    factual_edit["whatHappened"] = "Silently replace the sourced account."
    with pytest.raises(ValueError, match="unsupported fields"):
        apply_history_decision(draft, factual_edit)


def test_historical_rejection_records_the_reason_without_approved_copy():
    draft = sample_history_draft()
    rejection = sample_history_approval(draft)
    rejection.update({
        "decision": "reject",
        "headline": None,
        "take": None,
        "editSummary": None,
        "reason": "The changed judgment is still too obvious to publish.",
    })
    approved, decision = apply_history_decision(draft, rejection)

    assert approved is None
    assert decision["decision"] == "reject"
    assert decision["reason"] == "The changed judgment is still too obvious to publish."
    assert decision["approvedHeadline"] is None
    assert decision["approvedTake"] is None
    assert validate_history_decision(decision) == decision


def test_historical_approval_cannot_rescue_a_held_editorial_gate():
    draft = sample_history_draft()
    draft["editorialGates"]["hostileEditor"] = "hold"
    draft["contentHash"] = compute_history_content_hash(draft)
    with pytest.raises(IssueValidationError, match="every editorial gate"):
        apply_history_decision(draft, sample_history_approval(draft))


def test_historical_sealing_is_separate_and_preserves_approved_copy():
    draft = sample_history_draft()
    approved, decision = apply_history_decision(draft, sample_history_approval(draft))
    assert approved is not None
    sealed = seal_history_entry(approved, "2026-08-28T16:05:00Z")

    assert sealed["status"] == "published"
    assert sealed["publishedAt"] == "2026-08-28T16:05:00Z"
    assert sealed["headline"] == approved["headline"]
    assert sealed["take"] == approved["take"]
    assert validate_history_decision(decision, sealed) == decision

    with pytest.raises(ValueError, match="status=approved"):
        seal_history_entry(draft, "2026-08-28T16:05:00Z")
    with pytest.raises(ValueError, match="cannot precede"):
        seal_history_entry(approved, "2026-08-28T15:59:59Z")


def test_historical_seal_refuses_a_canonical_draft_changed_after_review(tmp_path, monkeypatch):
    draft = sample_history_draft()
    approved, decision = apply_history_decision(draft, sample_history_approval(draft))
    assert approved is not None
    changed = copy.deepcopy(draft)
    changed["point"] = "A newly revised point after Matti reviewed the earlier draft."
    changed["contentHash"] = compute_history_content_hash(changed)
    approved_path = tmp_path / "approved.json"
    decision_path = tmp_path / "decision.json"
    canonical_path = tmp_path / "canonical.json"
    decision_output = tmp_path / "canonical-decision.json"
    approved_path.write_text(json.dumps(approved))
    decision_path.write_text(json.dumps(decision))
    canonical_path.write_text(json.dumps(changed))
    monkeypatch.setattr(sys, "argv", [
        "seal_gravel_weekly_history.py", str(approved_path),
        "--published-at", "2026-08-28T16:05:00Z",
        "--decision", str(decision_path),
        "--output", str(canonical_path),
        "--decision-output", str(decision_output),
    ])

    with pytest.raises(SystemExit, match="approval is stale"):
        seal_history_main()
    assert json.loads(canonical_path.read_text())["contentHash"] == changed["contentHash"]
    assert not decision_output.exists()


def test_private_historical_review_desk_separates_evidence_and_approval_state():
    draft = sample_history_draft()
    held = copy.deepcopy(draft)
    held["entryId"] = "history-held-2026"
    held["headline"] = "A held premise"
    held["editorialGates"]["friend"] = "hold"
    held["contentHash"] = compute_history_content_hash(held)
    slopped = copy.deepcopy(draft)
    slopped["entryId"] = "history-slopped-2026"
    slopped["headline"] = "A prose-held premise"
    slopped["take"] = "The future isn't coming. It's already here."
    slopped["contentHash"] = compute_history_content_hash(slopped)
    page = render_history_review([draft, held, slopped], 2026)

    assert "PRIVATE EDITORIAL DESK · NOT PUBLIC" in page
    assert "3 DRAFTS" in page
    assert "1 READY FOR HUMAN DECISION" in page
    assert "2 HELD BY EVIDENCE, EDITORIAL, OR PROSE GATES" in page
    assert "DECISION QUEUE" in page
    assert f'href="#{draft["entryId"]}"' in page
    assert f'href="#{held["entryId"]}"' in page
    assert "approve all READY 2026 entries as written" in page
    assert draft["entryId"] in page.split("HOLD entries remain excluded", 1)[0]
    bulk_scope = page.split("That instruction is limited to:", 1)[1].split(
        "HOLD entries remain excluded", 1
    )[0]
    assert held["entryId"] not in bulk_scope
    assert "THE TAKE · MODEL DRAFT" in page
    assert "NO-AI-SLOP PROSE GATE · PASS" in page
    assert "NO-AI-SLOP PROSE GATE · FAIL" in page
    assert "no-AI-slop prose gate" in page
    assert "fake_profound_kicker" in page
    assert "not an AI-authorship detector" in page
    assert "CONTEMPORARY RECEIPTS (2)" in page
    assert "LATER EVIDENCE (1)" in page
    assert "any decision binds to this exact draft hash" in page.lower()
    assert "approval fails closed while any hold remains" in page.lower()
    assert draft["contentHash"] in page
    assert "noindex,nofollow" in page


def test_persisted_historical_draft_corpus_clears_the_no_ai_slop_gate():
    entries = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    failures = {}
    for entry in entries:
        gate = audit_no_ai_slop({
            "headline": entry["headline"],
            "what_happened": entry["whatHappened"],
            "take": entry["take"],
        })
        if gate["verdict"] != "pass":
            failures[entry["entryId"]] = gate["findings"]
    assert failures == {}


def test_historical_race_impacts_are_review_only_and_use_canonical_race_ids():
    entry = sample_history_entry()
    entry["raceImpacts"] = [{
        "impactKind": "no_change",
        "raceId": "gravel:unbound-200",
        "fieldPath": None,
        "claimIds": [],
        "confidence": 0.9,
        "owner": "Gravel God historical editorial review",
        "autoFixAllowed": False,
    }]
    with pytest.raises(IssueValidationError, match="must be editorial_review"):
        validate_history_entry(entry, verify_hash=False)

    entry["raceImpacts"][0].update({
        "impactKind": "editorial_review",
        "raceId": "gravel:unbound-gravel-200",
        "fieldPath": "race.history",
        "claimIds": ["claim_team_1"],
    })
    with pytest.raises(IssueValidationError, match="deprecated; use gravel:unbound-200"):
        validate_history_entry(entry, verify_hash=False)


def test_historical_drafts_never_cross_the_public_loader(tmp_path):
    approved = sample_history_entry()
    draft = copy.deepcopy(approved)
    draft.update({
        "entryId": "history-held-model-draft-2026",
        "status": "draft",
        "take": "Model draft, not Matti's approved view: this stays backstage.",
        "takeProvenance": "model_draft",
        "editorialApproval": None,
    })
    draft["editorialGates"]["hostileEditor"] = "hold"
    approved["contentHash"] = compute_history_content_hash(approved)
    draft["contentHash"] = compute_history_content_hash(draft)
    (tmp_path / "approved.json").write_text(json.dumps(approved))
    (tmp_path / "draft.json").write_text(json.dumps(draft))

    assert {entry["entryId"] for entry in load_history_entries(tmp_path)} == {
        approved["entryId"],
        draft["entryId"],
    }
    assert [entry["entryId"] for entry in load_public_history_entries(tmp_path)] == [approved["entryId"]]


def test_2025_backfill_ledger_preserves_the_complete_assigning_desk_review():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2025.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 255
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 5
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 15
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 33
    assert validated["complete"] is True


def test_2024_backfill_ledger_accounts_for_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2024.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 239
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 2
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 22
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 29
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2023_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2023.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 218
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 4
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 22
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 27
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2022_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2022.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 173
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 6
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 25
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 22
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2021_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2021.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 130
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 11
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 18
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 24
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2020_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2020.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 88
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 16
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 16
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 21
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2019_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2019.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 16
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 42
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 4
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 7
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2018_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2018.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 7
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 47
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 1
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 5
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2017_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2017.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 2
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 47
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 4
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 2
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2016_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2016.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 50
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 3
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2015_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2015.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 50
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 3
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2014_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2014.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 51
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 2
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2013_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2013.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 51
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 2
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2012_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2012.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 52
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 1
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2011_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2011.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 1
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 49
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 3
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 1
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2010_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2010.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 52
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 1
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2009_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2009.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 3
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 48
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 2
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 3
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2008_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2008.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 50
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 3
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2007_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2007.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 52
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 1
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2006_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2006.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 51
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 2
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2005_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2005.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 51
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 2
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2004_backfill_ledger_starts_from_the_complete_source_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2004.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 52
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 1
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2003_backfill_ledger_reconciles_the_complete_legacy_archive_census():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2003.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert validated["sourceArchiveCoverage"] == "complete"
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 1
    assert sum(week["disposition"] == "unresearched" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 1
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 52
    assert validated["complete"] is True


def test_2002_backfill_ledger_preserves_partial_archive_limits_without_open_research_debt():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2002.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert validated["sourceArchiveCoverage"] == "partial"
    assert len(validated["sourceArchiveErrors"]) == 4
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 51
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 2
    assert sum(week["disposition"] == "unresearched" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_2001_backfill_ledger_closes_review_without_claiming_archive_coverage():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2001.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert validated["sourceArchiveCoverage"] == "unavailable"
    assert len(validated["sourceArchiveErrors"]) == 12
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "unresearched" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 53
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


@pytest.mark.parametrize(
    ("year", "archive_error_count", "covered_count", "rejected_count"),
    [
        (2000, 12, 2, 51),
        (1999, 1, 1, 52),
        (1998, 1, 1, 52),
        (1997, 1, 0, 53),
        (1996, 1, 0, 53),
        (1995, 1, 1, 52),
        (1994, 1, 2, 51),
        (1993, 1, 0, 53),
        (1992, 1, 1, 52),
        (1991, 1, 0, 53),
    ],
)
def test_1991_through_2000_backfill_ledgers_close_without_fabricating_archive_coverage(
    year, archive_error_count, covered_count, rejected_count
):
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / f"{year}.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 53
    assert validated["sourceArchiveCoverage"] == "unavailable"
    assert len(validated["sourceArchiveErrors"]) == archive_error_count
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "unresearched" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == rejected_count
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == covered_count
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 0
    assert validated["complete"] is True


def test_unavailable_archive_cannot_be_recorded_as_an_explicit_gap():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2000.json").read_text())
    dishonest = copy.deepcopy(ledger)
    week = next(week for week in dishonest["weeks"] if week["disposition"] == "rejected")
    week["disposition"] = "explicit_gap"
    week["reason"] = "No matching source card was found."

    with pytest.raises(IssueValidationError, match="source archive coverage is unavailable"):
        validate_backfill_ledger(dishonest, histories)


def test_initial_backfill_ledger_accounts_for_every_discovery_card():
    discovery = {
        "schemaVersion": "gravel-weekly-historical-ledger/v1",
        "year": 2024,
        "asOf": "2024-12-31T23:59:59Z",
        "archiveCoverage": "complete",
        "archiveMonthsRequested": 12,
        "archiveMonthsSucceeded": 12,
        "archiveMonthErrors": [],
        "sourceCardCount": 1,
        "sourceCards": [{"id": "source-1"}],
        "weeks": [
            {
                "periodStartedAt": "2023-12-30T00:00:00Z",
                "periodEndedAt": "2024-01-05T23:59:59Z",
                "sourceCardIds": ["source-1"],
                "status": "source_census_ready",
            },
            {
                "periodStartedAt": "2024-01-06T00:00:00Z",
                "periodEndedAt": "2024-01-12T23:59:59Z",
                "sourceCardIds": [],
                "status": "explicit_gap",
            },
        ],
    }
    ledger = build_initial_backfill_ledger(
        discovery,
        source_ledger_issue="https://github.com/example/project/issues/1",
        source_ledger_run="https://github.com/example/project/actions/runs/2",
        program_issue="https://github.com/example/project/issues/3",
        updated_at="2026-08-28T06:30:00Z",
    )

    assert ledger["complete"] is False
    assert [week["disposition"] for week in ledger["weeks"]] == ["pending_review", "explicit_gap"]
    assert sum(week["sourceCardCount"] for week in ledger["weeks"]) == 1


def test_initial_backfill_ledger_preserves_partial_archive_research_debt_and_rejects_bad_card_accounting():
    discovery = {
        "schemaVersion": "gravel-weekly-historical-ledger/v1",
        "year": 2024,
        "asOf": "2024-12-31T23:59:59Z",
        "archiveCoverage": "partial",
        "archiveMonthsRequested": 2,
        "archiveMonthsSucceeded": 1,
        "archiveMonthErrors": ["February failed"],
        "sourceCardCount": 0,
        "sourceCards": [],
        "weeks": [
            {
                "periodStartedAt": "2023-12-30T00:00:00Z",
                "periodEndedAt": "2024-01-05T23:59:59Z",
                "sourceCardIds": [],
                "status": "explicit_gap",
            },
            {
                "periodStartedAt": "2024-01-06T00:00:00Z",
                "periodEndedAt": "2024-01-12T23:59:59Z",
                "sourceCardIds": [],
                "status": "unresearched",
            },
        ],
    }
    ledger = build_initial_backfill_ledger(
        discovery,
        source_ledger_issue="https://github.com/example/project/issues/1",
        source_ledger_run="https://github.com/example/project/actions/runs/2",
        program_issue="https://github.com/example/project/issues/3",
        updated_at="2026-08-28T06:30:00Z",
    )
    assert ledger["sourceArchiveCoverage"] == "partial"
    assert ledger["complete"] is False
    assert [week["disposition"] for week in ledger["weeks"]] == ["explicit_gap", "unresearched"]

    discovery["sourceCardCount"] = 1
    discovery["sourceCards"] = [{"id": "source-1"}]
    discovery["weeks"][0]["sourceCardIds"] = ["unknown-source"]
    discovery["weeks"][0]["status"] = "source_census_ready"
    with pytest.raises(IssueValidationError, match="accounting mismatch"):
        build_initial_backfill_ledger(
            discovery,
            source_ledger_issue="https://github.com/example/project/issues/1",
            source_ledger_run="https://github.com/example/project/actions/runs/2",
            program_issue="https://github.com/example/project/issues/3",
            updated_at="2026-08-28T06:30:00Z",
        )


def test_2026_backfill_ledger_accounts_for_every_window_and_closes_research_review():
    histories = load_history_entries(ROOT / "data" / "gravel-weekly" / "history")
    ledger = json.loads((ROOT / "data" / "gravel-weekly" / "backfill" / "2026.json").read_text())
    validated = validate_backfill_ledger(ledger, histories)

    assert len(validated["weeks"]) == 35
    assert sum(week["sourceCardCount"] for week in validated["weeks"]) == 230
    assert sum(week["disposition"] == "covered_by_draft" for week in validated["weeks"]) == 23
    assert sum(week["disposition"] == "held_for_evidence" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "rejected" for week in validated["weeks"]) == 11
    assert sum(week["disposition"] == "pending_review" for week in validated["weeks"]) == 0
    assert sum(week["disposition"] == "explicit_gap" for week in validated["weeks"]) == 1
    assert validated["complete"] is True

    missing_window = copy.deepcopy(ledger)
    missing_window["weeks"].pop(10)
    with pytest.raises(IssueValidationError, match="contiguous"):
        validate_backfill_ledger(missing_window, histories)

    dishonest_gap = copy.deepcopy(ledger)
    dishonest_gap["weeks"][1]["disposition"] = "explicit_gap"
    with pytest.raises(IssueValidationError, match="explicit gaps"):
        validate_backfill_ledger(dishonest_gap, histories)

    premature_completion = copy.deepcopy(ledger)
    premature_completion["weeks"][-1]["disposition"] = "pending_review"
    with pytest.raises(IssueValidationError, match="no weekly window remains pending"):
        validate_backfill_ledger(premature_completion, histories)


def test_historical_timeline_visually_separates_later_evidence_from_contemporary_receipts():
    entry = sample_history_entry()
    html = render_history_timeline([entry])
    assert "THE SEASON AS A STORY" in html
    assert "WHAT WAS KNOWABLE THEN" in html
    assert "LATER EVIDENCE — NOT AVAILABLE THEN" in html
    assert "WHY IT MATTERED" in html
    assert "THE FAIR OBJECTION" in html
    assert "The privateer became gravel" in html
    assert "innerHTML" not in html
    page = build_page(sample_issue(), [sample_issue()], latest=True, history_entries=[entry])
    assert 'id="season-story"' in page
    assert page.index("THE CURRENT THING") < page.index("THE SEASON AS A STORY") < page.index("PAST ISSUES")


def test_historical_chronology_rejects_hindsight_in_contemporary_receipts_and_preexisting_later_evidence():
    future_contemporary = sample_history_entry()
    future_contemporary["contemporaryReceipts"][1]["publishedAt"] = "2026-06-01T12:00:00Z"
    with pytest.raises(IssueValidationError, match="later evidence"):
        validate_history_entry(future_contemporary, verify_hash=False)

    early_later = sample_history_entry()
    early_later["laterEvidence"][0]["publishedAt"] = "2026-05-20T12:00:00Z"
    with pytest.raises(IssueValidationError, match="must postdate"):
        validate_history_entry(early_later, verify_hash=False)


def test_worker_accepts_new_and_legacy_publication_sources():
    worker = (ROOT / "workers" / "fueling-lead-intake" / "worker.js").read_text()
    assert "'gravel_weekly_subscribe'" in worker
    assert "'gravel_tv_subscribe'" in worker


def test_deploy_path_and_legacy_redirect_are_wired():
    deploy = (ROOT / "scripts" / "push_wordpress.py").read_text()
    assert "def sync_gravel_weekly(" in deploy
    assert '"--sync-gravel-weekly"' in deploy
    assert "def sync_gravel_tv(" not in deploy
    assert '"--sync-gravel-tv"' not in deploy
    assert "^gravel-tv/?$ /gravel-weekly/" in deploy
    assert '"gravel-weekly"' in deploy
    assert not (ROOT / "wordpress" / "generate_gravel_tv.py").exists()
    assert not (ROOT / "scripts" / "draft_desk_note.py").exists()
    assert not (ROOT / "scripts" / "send_broadcast_email.py").exists()
    workflow = (ROOT / ".github" / "workflows" / "weekly-broadcast.yml").read_text()
    assert "issues: write" in workflow
    assert "render_gravel_weekly_race_impact_review.py" in workflow
    assert "meaningful-race-impact-count: 0" in workflow
    assert "validate_decision_receipt" in workflow
    assert "record_gravel_weekly_decisions.py" in workflow
    assert "CONTROL_PLANE_INGEST_SECRET" in workflow


def test_homepage_surfaces_gravel_weekly_without_a_gravel_tv_content_path():
    band = build_gravel_weekly_band()
    assert 'id="gravel-weekly"' in band
    assert 'href="/gravel-weekly/"' in band
    assert "GRAVEL <em>WEEKLY</em>" in band
    assert "Gravel TV" not in band


def test_email_preserves_legacy_subscribers_and_uses_approved_issue():
    issue = sample_issue()
    email = build_email_html(issue)
    assert SUBSCRIBER_SOURCES == ("gravel_weekly_subscribe", "gravel_tv_subscribe")
    assert "Gravel Weekly" in email
    assert "Unbound changed the course" in email
    assert "/gravel-weekly/2026-08-28/" in email
    assert "RESEND_UNSUBSCRIBE_URL" in email
