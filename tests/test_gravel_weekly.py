"""Contract and infrastructure tests for Gravel Weekly."""

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_gravel_weekly import build_page  # noqa: E402
from validate_gravel_weekly import (  # noqa: E402
    IssueValidationError,
    compute_content_hash,
    validate_issue,
)
from send_gravel_weekly import SUBSCRIBER_SOURCES, build_email_html  # noqa: E402
from prepare_gravel_weekly_issue import prepare_issue  # noqa: E402


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
        "corrections": [],
        "sourceIndex": ["https://www.cyclingnews.com/example/"],
        "editorialApproval": {"approver": "Matti Rowe", "approvedAt": "2026-08-28T16:00:00Z"},
        "publishedAt": "2026-08-28T16:05:00Z",
        "updatedAt": "2026-08-28T16:05:00Z",
        "contentHash": "pending",
    }
    issue["contentHash"] = compute_content_hash(issue)
    return issue


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


def test_review_prepares_a_draft_but_cannot_imply_approval():
    packet = {
        "candidateId": "story_1",
        "suggestedTake": {"label": "model_draft", "copy": "Editable model draft, not Matti's approved view: A sharp take."},
        "suggestedHeadline": "The course moved",
        "suggestedDek": "A small mileage change hides a larger terrain question.",
        "whatHappened": "The organizer published a revised distance. It affects preparation.",
        "receipts": [sample_issue()["stories"][0]["receipts"][0]],
        "raceImpacts": sample_issue()["stories"][0]["raceImpacts"],
    }
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


def test_current_thing_requires_editorial_score_of_85():
    issue = sample_issue()
    issue["stories"][0]["score"] = 84
    with pytest.raises(IssueValidationError, match="at least 85"):
        validate_issue(issue, verify_hash=False)


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
    assert "/gravel-weekly/2026-08-28/" in page
    assert "rounded" not in page.lower()


def test_worker_accepts_new_and_legacy_publication_sources():
    worker = (ROOT / "workers" / "fueling-lead-intake" / "worker.js").read_text()
    assert "'gravel_weekly_subscribe'" in worker
    assert "'gravel_tv_subscribe'" in worker


def test_deploy_path_and_legacy_redirect_are_wired():
    deploy = (ROOT / "scripts" / "push_wordpress.py").read_text()
    assert "def sync_gravel_weekly(" in deploy
    assert '"--sync-gravel-weekly"' in deploy
    assert "^gravel-tv/?$ /gravel-weekly/" in deploy
    assert '"gravel-weekly"' in deploy


def test_email_preserves_legacy_subscribers_and_uses_approved_issue():
    issue = sample_issue()
    email = build_email_html(issue)
    assert SUBSCRIBER_SOURCES == ("gravel_weekly_subscribe", "gravel_tv_subscribe")
    assert "Gravel Weekly" in email
    assert "Unbound changed the course" in email
    assert "/gravel-weekly/2026-08-28/" in email
    assert "RESEND_UNSUBSCRIBE_URL" in email
