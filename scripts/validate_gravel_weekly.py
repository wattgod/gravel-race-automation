#!/usr/bin/env python3
"""Fail-closed validation for approved Gravel Weekly issue snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from no_ai_slop import audit_no_ai_slop

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ISSUE_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "issues"

STORY_KINDS = {
    "safety", "event_status", "route", "registration", "results",
    "governance", "business", "athlete", "culture", "product", "other",
}
IMPACT_KINDS = {
    "no_change", "verify_field", "propose_fact", "editorial_review",
    "new_race_candidate",
}
RETROSPECTIVE_VERDICTS = {"aged_well", "aged_poorly", "still_developing"}
CULTURE_SOURCE_KINDS = {"bluesky", "x", "instagram", "youtube", "forum", "blog", "newsletter", "podcast"}
CULTURE_COLLECTION_METHODS = {
    "official_api", "authorized_caption", "rss", "sitemap",
    "public_metadata", "user_authorized",
}
CULTURE_RIGHTS_POLICIES = {
    "metadata_only", "short_excerpt_and_canonical_link",
    "timestamped_short_excerpt",
}
CULTURE_ARTIFACT_KEYS = {
    "artifactId", "sourceKind", "publisher", "author", "canonicalUrl",
    "publishedAt", "title", "excerpt", "timestampSeconds", "topicTags",
    "reviewReason", "collectionMethod", "rightsPolicy", "purpose",
    "canProveClaim", "canEstablishConsensus",
}
STORY_CAST_KEYS = {"name", "role", "claimIds"}
STORY_FIELD_NOTE_KEYS = {"text", "claimIds"}
QUIET_ISSUE_KEYS = {"headline", "note", "provenance"}
EDITORIAL_APPROVAL_KEYS = {
    "approver", "approvedAt", "reviewedDraftContentHash",
}
CORRECTION_KEYS = {"publishedAt", "text", "storyId", "learning"}
CORRECTION_LEARNING_KEYS = {
    "failureKey", "originalClaim", "correctedClaim", "severity",
    "evidenceUrls", "recordedBy",
}


class IssueValidationError(ValueError):
    """An issue violated the publication contract."""


def _record(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IssueValidationError(f"{name} must be an object")
    return value


def _text(value: Any, name: str, maximum: int = 8_000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IssueValidationError(f"{name} is required")
    if len(value) > maximum:
        raise IssueValidationError(f"{name} exceeds {maximum} characters")
    return value.strip()


def _iso(value: Any, name: str) -> str:
    raw = _text(value, name, 100)
    try:
        datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IssueValidationError(f"{name} must be an ISO timestamp") from exc
    return raw


def _url(value: Any, name: str) -> str:
    raw = _text(value, name, 2_000)
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IssueValidationError(f"{name} must be a public HTTP(S) URL")
    return raw


def _list(value: Any, name: str, maximum: int = 200) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        raise IssueValidationError(f"{name} must be a list with at most {maximum} items")
    return value


def _race_id(value: Any, name: str) -> str:
    raw = _text(value, name, 500)
    if not re.fullmatch(r"(?:gravel|road|nordic):[a-z0-9][a-z0-9-]*", raw):
        raise IssueValidationError(f"{name} must be a vertical-qualified race id")
    return raw


def _receipt(value: Any, name: str) -> dict[str, Any]:
    item = _record(value, name)
    _text(item.get("claimId"), f"{name}.claimId", 500)
    _url(item.get("canonicalUrl"), f"{name}.canonicalUrl")
    _text(item.get("publisher"), f"{name}.publisher", 300)
    if item.get("publishedAt") is not None:
        _iso(item["publishedAt"], f"{name}.publishedAt")
    quote = item.get("quoteExcerpt")
    if quote is not None:
        _text(quote, f"{name}.quoteExcerpt", 1_000)
    start = item.get("transcriptStartSeconds")
    end = item.get("transcriptEndSeconds")
    if (start is None) != (end is None):
        raise IssueValidationError(f"{name} transcript timestamps must be paired")
    if start is not None:
        if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end < start:
            raise IssueValidationError(f"{name} transcript timestamps are invalid")
    return item


def _impact(value: Any, name: str) -> dict[str, Any]:
    item = _record(value, name)
    kind = item.get("impactKind")
    if kind not in IMPACT_KINDS:
        raise IssueValidationError(f"{name}.impactKind is invalid")
    _race_id(item.get("raceId"), f"{name}.raceId")
    field_path = item.get("fieldPath")
    if field_path is not None:
        _text(field_path, f"{name}.fieldPath", 500)
    if kind not in {"no_change", "new_race_candidate"} and not field_path:
        raise IssueValidationError(f"{name}.fieldPath is required for {kind}")
    claim_ids = _list(item.get("claimIds"), f"{name}.claimIds")
    if kind != "no_change" and not claim_ids:
        raise IssueValidationError(f"{name}.claimIds are required for {kind}")
    for index, claim_id in enumerate(claim_ids):
        _text(claim_id, f"{name}.claimIds[{index}]", 500)
    confidence = item.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        raise IssueValidationError(f"{name}.confidence must be between 0 and 1")
    _text(item.get("owner"), f"{name}.owner", 300)
    if item.get("autoFixAllowed") is not False:
        raise IssueValidationError(f"{name}.autoFixAllowed must be false")
    return item


def _correction(value: Any, name: str, story_ids: set[str]) -> dict[str, Any]:
    item = _record(value, name)
    unknown = set(item) - CORRECTION_KEYS
    missing = CORRECTION_KEYS - set(item)
    if unknown or missing:
        raise IssueValidationError(
            f"{name} fields are invalid; missing={sorted(missing)}, extra={sorted(unknown)}"
        )
    _iso(item.get("publishedAt"), f"{name}.publishedAt")
    _text(item.get("text"), f"{name}.text", 2_000)
    story_id = item.get("storyId")
    if story_id is not None and story_id not in story_ids:
        raise IssueValidationError(f"{name}.storyId must reference an issue story")
    learning = _record(item.get("learning"), f"{name}.learning")
    unknown = set(learning) - CORRECTION_LEARNING_KEYS
    missing = CORRECTION_LEARNING_KEYS - set(learning)
    if unknown or missing:
        raise IssueValidationError(
            f"{name}.learning fields are invalid; missing={sorted(missing)}, extra={sorted(unknown)}"
        )
    failure_key = _text(learning.get("failureKey"), f"{name}.learning.failureKey", 100)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,99}", failure_key):
        raise IssueValidationError(f"{name}.learning.failureKey must be a lowercase slug")
    original = _text(learning.get("originalClaim"), f"{name}.learning.originalClaim", 2_000)
    corrected = _text(learning.get("correctedClaim"), f"{name}.learning.correctedClaim", 2_000)
    if original == corrected:
        raise IssueValidationError(f"{name}.learning must change the original claim")
    if learning.get("severity") not in {"minor", "material"}:
        raise IssueValidationError(f"{name}.learning.severity must be minor or material")
    evidence_urls = _list(learning.get("evidenceUrls"), f"{name}.learning.evidenceUrls", 20)
    if not evidence_urls:
        raise IssueValidationError(f"{name}.learning.evidenceUrls must not be empty")
    normalized_urls = [
        _url(url, f"{name}.learning.evidenceUrls[{index}]")
        for index, url in enumerate(evidence_urls)
    ]
    if len(normalized_urls) != len(set(normalized_urls)):
        raise IssueValidationError(f"{name}.learning.evidenceUrls must be unique")
    _text(learning.get("recordedBy"), f"{name}.learning.recordedBy", 300)
    return item


def _culture_artifact(value: Any, name: str) -> dict[str, Any]:
    artifact = _record(value, name)
    unknown = set(artifact) - CULTURE_ARTIFACT_KEYS
    if unknown:
        raise IssueValidationError(f"{name} has unsupported fields: {sorted(unknown)}")
    _text(artifact.get("artifactId"), f"{name}.artifactId", 500)
    if artifact.get("sourceKind") not in CULTURE_SOURCE_KINDS:
        raise IssueValidationError(f"{name}.sourceKind is invalid")
    _text(artifact.get("publisher"), f"{name}.publisher", 300)
    if artifact.get("author") is not None:
        _text(artifact["author"], f"{name}.author", 300)
    _url(artifact.get("canonicalUrl"), f"{name}.canonicalUrl")
    _iso(artifact.get("publishedAt"), f"{name}.publishedAt")
    _text(artifact.get("title"), f"{name}.title", 500)
    if artifact.get("excerpt") is not None:
        _text(artifact["excerpt"], f"{name}.excerpt", 280)
    timestamp = artifact.get("timestampSeconds")
    if timestamp is not None and (
        not isinstance(timestamp, int) or isinstance(timestamp, bool)
        or timestamp < 0 or timestamp > 86_400
    ):
        raise IssueValidationError(f"{name}.timestampSeconds is invalid")
    if artifact.get("collectionMethod") == "authorized_caption" and timestamp is None:
        raise IssueValidationError(f"{name}.timestampSeconds is required for an authorized caption")
    topics = _list(artifact.get("topicTags"), f"{name}.topicTags", 10)
    if not topics:
        raise IssueValidationError(f"{name}.topicTags must not be empty")
    for index, topic in enumerate(topics):
        raw = _text(topic, f"{name}.topicTags[{index}]", 64)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]+", raw):
            raise IssueValidationError(f"{name}.topicTags[{index}] is invalid")
    if len(topics) != len(set(topics)):
        raise IssueValidationError(f"{name}.topicTags must be unique")
    _text(artifact.get("reviewReason"), f"{name}.reviewReason", 1_000)
    if artifact.get("collectionMethod") not in CULTURE_COLLECTION_METHODS:
        raise IssueValidationError(f"{name}.collectionMethod is invalid")
    if artifact.get("rightsPolicy") not in CULTURE_RIGHTS_POLICIES:
        raise IssueValidationError(f"{name}.rightsPolicy is invalid")
    if artifact.get("purpose") != "culture_sensor":
        raise IssueValidationError(f"{name}.purpose must be culture_sensor")
    if artifact.get("canProveClaim") is not False:
        raise IssueValidationError(f"{name}.canProveClaim must be false")
    if artifact.get("canEstablishConsensus") is not False:
        raise IssueValidationError(f"{name}.canEstablishConsensus must be false")
    return artifact


def _scene_claim_ids(
    value: Any, name: str, receipt_claim_ids: set[str]
) -> list[str]:
    claim_ids = _list(value, f"{name}.claimIds", 10)
    if not claim_ids:
        raise IssueValidationError(f"{name}.claimIds must not be empty")
    normalized = [
        _text(claim_id, f"{name}.claimIds[{index}]", 500)
        for index, claim_id in enumerate(claim_ids)
    ]
    if len(normalized) != len(set(normalized)):
        raise IssueValidationError(f"{name}.claimIds must be unique")
    missing = set(normalized) - receipt_claim_ids
    if missing:
        raise IssueValidationError(
            f"{name} references claims without story receipts: {sorted(missing)}"
        )
    return normalized


def _story_cast(
    value: Any, name: str, receipt_claim_ids: set[str]
) -> list[dict[str, Any]]:
    cast = _list(value, name, 8)
    names: list[str] = []
    for index, item_value in enumerate(cast):
        item_name = f"{name}[{index}]"
        item = _record(item_value, item_name)
        unknown = set(item) - STORY_CAST_KEYS
        if unknown:
            raise IssueValidationError(
                f"{item_name} has unsupported fields: {sorted(unknown)}"
            )
        names.append(_text(item.get("name"), f"{item_name}.name", 160).casefold())
        _text(item.get("role"), f"{item_name}.role", 300)
        _scene_claim_ids(item.get("claimIds"), item_name, receipt_claim_ids)
    if len(names) != len(set(names)):
        raise IssueValidationError(f"{name} must not contain duplicate names")
    return cast


def _story_field_notes(
    value: Any, name: str, receipt_claim_ids: set[str]
) -> list[dict[str, Any]]:
    notes = _list(value, name, 6)
    texts: list[str] = []
    for index, item_value in enumerate(notes):
        item_name = f"{name}[{index}]"
        item = _record(item_value, item_name)
        unknown = set(item) - STORY_FIELD_NOTE_KEYS
        if unknown:
            raise IssueValidationError(
                f"{item_name} has unsupported fields: {sorted(unknown)}"
            )
        texts.append(_text(item.get("text"), f"{item_name}.text", 500).casefold())
        _scene_claim_ids(item.get("claimIds"), item_name, receipt_claim_ids)
    if len(texts) != len(set(texts)):
        raise IssueValidationError(f"{name} must not contain duplicate notes")
    return notes


def _retrospective(value: Any, name: str, *, status: str) -> dict[str, Any]:
    item = _record(value, name)
    if item.get("verdict") not in RETROSPECTIVE_VERDICTS:
        raise IssueValidationError(f"{name}.verdict is invalid")
    _text(item.get("priorIssueId"), f"{name}.priorIssueId", 500)
    _text(item.get("priorStoryId"), f"{name}.priorStoryId", 500)
    _text(item.get("headline"), f"{name}.headline", 300)
    _text(item.get("whatChanged"), f"{name}.whatChanged", 2_000)
    assessment = _text(item.get("assessment"), f"{name}.assessment", 4_000)
    provenance = item.get("assessmentProvenance")
    if provenance not in {"model_draft", "human_approved"}:
        raise IssueValidationError(f"{name}.assessmentProvenance is invalid")
    if status != "draft" and provenance != "human_approved":
        raise IssueValidationError(f"{name}.assessment requires human-approved provenance")
    if status != "draft" and re.search(r"model draft|not matti(?:’|')s approved", assessment, re.IGNORECASE):
        raise IssueValidationError(f"{name}.assessment still contains model-draft language")
    prose_gate = audit_no_ai_slop({"retrospective": f"{item['headline']}\n{item['whatChanged']}\n{assessment}"})
    if prose_gate["verdict"] != "pass":
        patterns = ", ".join(finding["pattern"] for finding in prose_gate["findings"])
        raise IssueValidationError(f"{name} fails the no-ai-slop gate: {patterns}")
    receipts = _list(item.get("receipts"), f"{name}.receipts", 100)
    if not receipts:
        raise IssueValidationError(f"{name}.receipts must not be empty")
    for index, receipt in enumerate(receipts):
        _receipt(receipt, f"{name}.receipts[{index}]")
    return item


def _quiet_issue(value: Any, name: str, *, status: str) -> dict[str, Any]:
    item = _record(value, name)
    unknown = set(item) - QUIET_ISSUE_KEYS
    missing = QUIET_ISSUE_KEYS - set(item)
    if unknown or missing:
        raise IssueValidationError(
            f"{name} fields are invalid; missing={sorted(missing)}, extra={sorted(unknown)}"
        )
    headline = _text(item.get("headline"), f"{name}.headline", 300)
    note = _text(item.get("note"), f"{name}.note", 1_000)
    provenance = item.get("provenance")
    if provenance not in {"model_draft", "human_approved"}:
        raise IssueValidationError(f"{name}.provenance is invalid")
    if status != "draft" and provenance != "human_approved":
        raise IssueValidationError(f"{name} requires human-approved provenance")
    if status != "draft" and re.search(
        r"model draft|not matti(?:’|')s approved", note, re.IGNORECASE
    ):
        raise IssueValidationError(f"{name} still contains model-draft language")
    prose_gate = audit_no_ai_slop({"quiet_headline": headline, "quiet_note": note})
    if prose_gate["verdict"] != "pass":
        findings = ", ".join(
            f"{finding['field']}:{finding['pattern']}"
            for finding in prose_gate["findings"]
        )
        raise IssueValidationError(f"{name} fails the no-ai-slop gate: {findings}")
    return item


def canonical_issue_json(issue: dict[str, Any]) -> str:
    payload = dict(issue)
    payload.pop("contentHash", None)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def compute_content_hash(issue: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_issue_json(issue).encode("utf-8")).hexdigest()


def validate_issue(value: Any, *, verify_hash: bool = True) -> dict[str, Any]:
    issue = _record(value, "issue")
    if issue.get("schemaVersion") != "gravel-weekly-issue/v1":
        raise IssueValidationError("unsupported Gravel Weekly issue schema")
    _text(issue.get("issueId"), "issueId", 500)
    issue_number = issue.get("issueNumber")
    if not isinstance(issue_number, int) or isinstance(issue_number, bool) or issue_number < 1:
        raise IssueValidationError("issueNumber must be a positive integer")
    publication_date = _text(issue.get("publicationDate"), "publicationDate", 10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", publication_date):
        raise IssueValidationError("publicationDate must be YYYY-MM-DD")
    try:
        datetime.strptime(publication_date, "%Y-%m-%d")
    except ValueError as exc:
        raise IssueValidationError("publicationDate is invalid") from exc
    if issue.get("slug") != publication_date:
        raise IssueValidationError("slug must equal publicationDate")
    status = issue.get("status")
    if status not in {"draft", "approved", "published"}:
        raise IssueValidationError("status is invalid")
    _text(issue.get("title"), "title", 300)
    _text(issue.get("mastheadDeck"), "mastheadDeck", 500)

    stories = _list(issue.get("stories"), "stories", 30)
    story_ids: list[str] = []
    story_impacts: list[dict[str, Any]] = []
    story_culture_urls: set[str] = set()
    publication_day = datetime.strptime(publication_date, "%Y-%m-%d").date()
    culture_window_start = datetime.combine(publication_day - timedelta(days=14), time.min, tzinfo=timezone.utc)
    culture_window_end = datetime.combine(publication_day + timedelta(days=1), time.min, tzinfo=timezone.utc)
    for index, raw_story in enumerate(stories):
        story = _record(raw_story, f"stories[{index}]")
        story_id = _text(story.get("candidateId"), f"stories[{index}].candidateId", 500)
        story_ids.append(story_id)
        headline = _text(story.get("headline"), f"stories[{index}].headline", 300)
        dek = _text(story.get("dek"), f"stories[{index}].dek", 600)
        if story.get("storyKind") not in STORY_KINDS:
            raise IssueValidationError(f"stories[{index}].storyKind is invalid")
        score = story.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or not 70 <= score <= 100:
            raise IssueValidationError(f"stories[{index}].score must be 70 to 100")
        what_happened = _text(story.get("whatHappened"), f"stories[{index}].whatHappened", 2_000)
        take = _text(story.get("take"), f"stories[{index}].take", 8_000)
        provenance = story.get("takeProvenance")
        if provenance not in {"model_draft", "human_approved"}:
            raise IssueValidationError(f"stories[{index}].takeProvenance is invalid")
        if status != "draft" and provenance != "human_approved":
            raise IssueValidationError(f"stories[{index}].take requires human-approved provenance")
        if status != "draft" and re.search(r"model draft|not matti(?:’|')s approved", take, re.IGNORECASE):
            raise IssueValidationError(f"stories[{index}].take still contains model-draft language")
        prose_gate = audit_no_ai_slop({"headline": headline, "dek": dek, "what_happened": what_happened, "take": take})
        if prose_gate["verdict"] != "pass":
            findings = ", ".join(f"{finding['field']}:{finding['pattern']}" for finding in prose_gate["findings"])
            raise IssueValidationError(f"stories[{index}] fails the no-ai-slop gate: {findings}")
        receipts = _list(story.get("receipts"), f"stories[{index}].receipts", 100)
        if not receipts:
            raise IssueValidationError(f"stories[{index}].receipts must not be empty")
        receipt_claim_ids: set[str] = set()
        for receipt_index, receipt in enumerate(receipts):
            validated_receipt = _receipt(receipt, f"stories[{index}].receipts[{receipt_index}]")
            receipt_claim_ids.add(validated_receipt["claimId"])
        _story_cast(
            story.get("cast", []),
            f"stories[{index}].cast",
            receipt_claim_ids,
        )
        _story_field_notes(
            story.get("fieldNotes", []),
            f"stories[{index}].fieldNotes",
            receipt_claim_ids,
        )
        for impact_index, impact in enumerate(_list(story.get("raceImpacts"), f"stories[{index}].raceImpacts")):
            validated_impact = _impact(impact, f"stories[{index}].raceImpacts[{impact_index}]")
            missing_claims = set(validated_impact["claimIds"]) - receipt_claim_ids
            if missing_claims:
                raise IssueValidationError(
                    f"stories[{index}].raceImpacts[{impact_index}] references claims without story receipts: {sorted(missing_claims)}"
                )
            story_impacts.append(validated_impact)
        culture_ids: set[str] = set()
        culture_urls: set[str] = set()
        for artifact_index, artifact_value in enumerate(_list(story.get("cultureArtifacts", []), f"stories[{index}].cultureArtifacts", 6)):
            artifact_name = f"stories[{index}].cultureArtifacts[{artifact_index}]"
            artifact = _culture_artifact(artifact_value, artifact_name)
            published_at = datetime.fromisoformat(
                _iso(artifact["publishedAt"], f"{artifact_name}.publishedAt").replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            if not culture_window_start <= published_at < culture_window_end:
                raise IssueValidationError(f"{artifact_name} must be dated inside the 14-day weekly culture window")
            if artifact["artifactId"] in culture_ids or artifact["canonicalUrl"] in culture_urls:
                raise IssueValidationError(f"stories[{index}].cultureArtifacts must have unique IDs and canonical URLs")
            culture_ids.add(artifact["artifactId"])
            culture_urls.add(artifact["canonicalUrl"])
            story_culture_urls.add(artifact["canonicalUrl"])
    if len(story_ids) != len(set(story_ids)):
        raise IssueValidationError("story candidate IDs must be unique")

    quiet_issue = issue.get("quietIssue")
    if stories and quiet_issue is not None:
        raise IssueValidationError("quietIssue cannot coexist with issue stories")
    if not stories:
        if quiet_issue is None:
            raise IssueValidationError("an issue without stories requires quietIssue")
        _quiet_issue(quiet_issue, "quietIssue", status=status)

    current_id = issue.get("currentThingStoryId")
    if current_id is not None:
        _text(current_id, "currentThingStoryId", 500)
        current = next((story for story in stories if story.get("candidateId") == current_id), None)
        if current is None:
            raise IssueValidationError("currentThingStoryId must reference an issue story")
        if current.get("score", 0) < 85:
            raise IssueValidationError("The Current Thing requires a score of at least 85")

    for index, item in enumerate(_list(issue.get("calendarWatch"), "calendarWatch", 100)):
        _text(item, f"calendarWatch[{index}]", 500)
    issue_impacts = [
        _impact(impact, f"raceImpacts[{index}]")
        for index, impact in enumerate(_list(issue.get("raceImpacts"), "raceImpacts"))
    ]
    impact_key = lambda impact: json.dumps(impact, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    issue_impact_keys = [impact_key(impact) for impact in issue_impacts]
    if len(issue_impact_keys) != len(set(issue_impact_keys)):
        raise IssueValidationError("raceImpacts must not contain duplicates")
    if set(issue_impact_keys) != {impact_key(impact) for impact in story_impacts}:
        raise IssueValidationError("raceImpacts must exactly preserve the deduplicated union of story raceImpacts")
    retrospective_refs: list[tuple[str, str]] = []
    for index, retrospective in enumerate(_list(issue.get("retrospectives"), "retrospectives", 30)):
        item = _retrospective(retrospective, f"retrospectives[{index}]", status=status)
        retrospective_refs.append((item["priorIssueId"], item["priorStoryId"]))
    if len(retrospective_refs) != len(set(retrospective_refs)):
        raise IssueValidationError("retrospectives must not revisit the same prior story twice")
    correction_sources: set[str] = set()
    correction_times: list[datetime] = []
    for index, correction_value in enumerate(_list(issue.get("corrections"), "corrections", 100)):
        correction = _correction(correction_value, f"corrections[{index}]", set(story_ids))
        correction_sources.update(correction["learning"]["evidenceUrls"])
        correction_times.append(
            datetime.fromisoformat(correction["publishedAt"].replace("Z", "+00:00")).astimezone(timezone.utc)
        )
    source_index = [_url(item, f"sourceIndex[{index}]") for index, item in enumerate(_list(issue.get("sourceIndex"), "sourceIndex", 200))]
    if len(source_index) != len(set(source_index)):
        raise IssueValidationError("sourceIndex must not contain duplicates")
    missing_culture_sources = story_culture_urls - set(source_index)
    if missing_culture_sources:
        raise IssueValidationError(f"sourceIndex omits culture artifact URLs: {sorted(missing_culture_sources)}")
    missing_correction_sources = correction_sources - set(source_index)
    if missing_correction_sources:
        raise IssueValidationError(f"sourceIndex omits correction evidence URLs: {sorted(missing_correction_sources)}")

    approval = issue.get("editorialApproval")
    if status != "draft" and not isinstance(approval, dict):
        raise IssueValidationError(f"{status} issues require editorial approval")
    if status == "draft" and approval is not None:
        raise IssueValidationError("draft issues cannot carry editorial approval")
    if isinstance(approval, dict):
        unknown = set(approval) - EDITORIAL_APPROVAL_KEYS
        missing = EDITORIAL_APPROVAL_KEYS - set(approval)
        if unknown or missing:
            raise IssueValidationError(
                "editorialApproval fields must exactly preserve the approver, "
                f"approval time, and reviewed draft hash; missing={sorted(missing)}, "
                f"extra={sorted(unknown)}"
            )
        _text(approval.get("approver"), "editorialApproval.approver", 300)
        _iso(approval.get("approvedAt"), "editorialApproval.approvedAt")
        reviewed_hash = _text(
            approval.get("reviewedDraftContentHash"),
            "editorialApproval.reviewedDraftContentHash",
            64,
        )
        if not re.fullmatch(r"[0-9a-f]{64}", reviewed_hash):
            raise IssueValidationError(
                "editorialApproval.reviewedDraftContentHash must be a lowercase SHA-256 hash"
            )
    if status == "published" and issue.get("publishedAt") is None:
        raise IssueValidationError("published issues require publishedAt")
    issue_published_at = None
    if issue.get("publishedAt") is not None:
        _iso(issue["publishedAt"], "publishedAt")
        issue_published_at = datetime.fromisoformat(
            issue["publishedAt"].replace("Z", "+00:00")
        ).astimezone(timezone.utc)
    updated_at_raw = _iso(issue.get("updatedAt"), "updatedAt")
    updated_at = datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    for correction_time in correction_times:
        if issue_published_at is None or correction_time < issue_published_at:
            raise IssueValidationError("corrections cannot predate the issue publication")
        if correction_time > updated_at:
            raise IssueValidationError("updatedAt must include every published correction")
    content_hash = _text(issue.get("contentHash"), "contentHash", 64)
    expected = compute_content_hash(issue)
    if verify_hash and content_hash != expected:
        raise IssueValidationError(f"contentHash mismatch: expected {expected}")
    return issue


def load_issues(issue_dir: Path = ISSUE_DIR) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not issue_dir.exists():
        return issues
    for path in sorted(issue_dir.glob("*.json")):
        try:
            issue = validate_issue(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, IssueValidationError) as exc:
            raise IssueValidationError(f"{path}: {exc}") from exc
        issues.append(issue)
    issue_numbers = [issue["issueNumber"] for issue in issues]
    dates = [issue["publicationDate"] for issue in issues]
    if len(issue_numbers) != len(set(issue_numbers)):
        raise IssueValidationError("issue numbers must be unique")
    if len(dates) != len(set(dates)):
        raise IssueValidationError("publication dates must be unique")
    by_id = {issue["issueId"]: issue for issue in issues}
    for issue in issues:
        for index, retrospective in enumerate(issue["retrospectives"]):
            prior = by_id.get(retrospective["priorIssueId"])
            name = f"{issue['issueId']}.retrospectives[{index}]"
            if prior is None:
                raise IssueValidationError(f"{name}.priorIssueId must reference an archived issue")
            if prior["publicationDate"] >= issue["publicationDate"]:
                raise IssueValidationError(f"{name} must reference an earlier issue")
            if not any(story["candidateId"] == retrospective["priorStoryId"] for story in prior["stories"]):
                raise IssueValidationError(f"{name}.priorStoryId must reference a story in the prior issue")
    return sorted(issues, key=lambda issue: issue["publicationDate"], reverse=True)


def load_public_issues(issue_dir: Path = ISSUE_DIR) -> list[dict[str, Any]]:
    """Return only sealed issue snapshots that are eligible for publication.

    ``status=approved`` is an intentionally private staging state.  Keeping the
    filter here gives the page generator and sender the same fail-closed
    boundary instead of relying on every caller to remember it.
    """
    return [issue for issue in load_issues(issue_dir) if issue["status"] == "published"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    paths = args.paths or sorted(ISSUE_DIR.glob("*.json"))
    for path in paths:
        validate_issue(json.loads(path.read_text(encoding="utf-8")))
        print(f"OK {path}")
    print(f"Validated {len(paths)} Gravel Weekly issue(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
