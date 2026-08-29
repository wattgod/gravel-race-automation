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
from gravel_weekly_culture import culture_css, render_culture_artifacts  # noqa: E402
from gravel_weekly_visuals import (  # noqa: E402
    classify_theme,
    render_story_visual,
    timestamped_youtube_receipt,
    visual_css,
    youtube_video_id,
)
from generate_homepage import build_gravel_weekly_band  # noqa: E402
from validate_gravel_weekly import (  # noqa: E402
    IssueValidationError,
    compute_content_hash,
    load_issues,
    load_public_issues,
    validate_issue,
)
from validate_gravel_weekly_history import (  # noqa: E402
    compute_history_content_hash,
    load_history_entries,
    load_public_history_entries,
    validate_history_entry,
)
from approve_gravel_weekly_history import (  # noqa: E402
    apply_history_decision,
    reviewed_headline_copy,
    reviewed_take_copy,
)
from approve_ready_gravel_weekly_history import (  # noqa: E402
    prepare_ready_approvals,
    stage_ready_approvals,
)
from render_gravel_weekly_history_review import (  # noqa: E402
    render_history_review,
    render_history_review_index,
    review_priority,
    review_years,
)
from seal_gravel_weekly_history import (  # noqa: E402
    main as seal_history_main,
    seal_history_entry,
)
from render_gravel_weekly_history_race_impact_review import (  # noqa: E402
    render_history_race_impact_review,
)
from validate_gravel_weekly_history_decisions import validate_history_decision  # noqa: E402
from validate_gravel_weekly_backfill import validate_backfill_ledger  # noqa: E402
from no_ai_slop import audit_no_ai_slop  # noqa: E402
from prepare_gravel_weekly_backfill_ledger import build_initial_backfill_ledger  # noqa: E402
from prepare_gravel_weekly_history_culture import prepare_history_culture_proposal  # noqa: E402
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
            "cultureArtifacts": [],
            "cast": [],
            "fieldNotes": [],
        }],
        "calendarWatch": ["Registration closes Friday."],
        "raceImpacts": [impact],
        "retrospectives": [],
        "corrections": [],
        "sourceIndex": ["https://www.cyclingnews.com/example/"],
        "editorialApproval": {
            "approver": "Matti Rowe",
            "approvedAt": "2026-08-28T16:00:00Z",
            "reviewedDraftContentHash": "1" * 64,
        },
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
        "cultureArtifacts": [],
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


def sample_culture_artifact():
    return {
        "artifactId": "historical-culture_0123456789abcdef",
        "sourceKind": "x",
        "publisher": "Gravel Person",
        "author": "@gravelperson",
        "canonicalUrl": "https://x.com/gravelperson/status/123456789",
        "publishedAt": "2026-03-01T18:30:00Z",
        "title": "The team bus became the meme",
        "excerpt": "Gravel has entered its team-bus era.",
        "timestampSeconds": None,
        "topicTags": ["privateers", "teamification"],
        "reviewReason": "A contemporaneous joke compressed the same access argument into one line.",
        "collectionMethod": "official_api",
        "rightsPolicy": "short_excerpt_and_canonical_link",
        "purpose": "culture_sensor",
        "canProveClaim": False,
        "canEstablishConsensus": False,
    }


def sample_weekly_culture_artifact():
    artifact = sample_culture_artifact()
    artifact.update({
        "artifactId": "culture-artifact_0123456789abcdef",
        "sourceKind": "bluesky",
        "publisher": "Cycling Reno",
        "author": "cyclingreno.bsky.social",
        "canonicalUrl": "https://bsky.app/profile/cyclingreno.bsky.social/post/3example",
        "publishedAt": "2026-08-27T18:30:00Z",
        "title": "The Worlds field has become calendar discourse in a rainbow jersey",
        "excerpt": "Apparently the real qualification standard is having the correct flight itinerary.",
        "topicTags": ["calendar", "worlds"],
        "reviewReason": "Directly names the race in the evidence-backed story; context only.",
    })
    return artifact


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


def test_visual_theme_classification_is_deterministic_and_story_aware():
    assert classify_theme("A flat tire made gravel admit teams exist") == ("teams", "TEAMWORK")
    assert classify_theme("Leadville banned the bike its course wanted") == ("category", "CATEGORY")
    assert classify_theme("The host community paid for the wildfire") == ("community", "HOST COMMUNITY")
    assert classify_theme(
        "Gravel built a governing body by accident",
        "A team roster and a series selection policy changed.",
    ) == ("governance", "GOVERNANCE")
    assert classify_theme(
        "The women had to race everybody else",
        "Many categories and bikes shared the course.",
    ) == ("equity", "COST TRANSFER")
    assert classify_theme("A story with no matching vocabulary") == ("pulse", "THE CURRENT THING")


@pytest.mark.parametrize(("url", "expected"), [
    ("https://www.youtube.com/watch?v=abcdefghijk", "abcdefghijk"),
    ("https://youtu.be/abcdefghijk", "abcdefghijk"),
    ("https://www.youtube.com/shorts/abcdefghijk", "abcdefghijk"),
    ("https://example.com/watch?v=abcdefghijk", None),
    ("https://www.youtube.com/watch?v=too-short", None),
])
def test_youtube_video_id_fails_closed(url, expected):
    assert youtube_video_id(url) == expected


def test_only_timestamped_youtube_receipts_can_become_video_visuals():
    untimestamped = [{"canonicalUrl": "https://youtu.be/abcdefghijk", "transcriptStartSeconds": None}]
    wrong_host = [{"canonicalUrl": "https://example.com/abcdefghijk", "transcriptStartSeconds": 42}]
    invalid_timestamp = [{"canonicalUrl": "https://youtu.be/abcdefghijk", "transcriptStartSeconds": -1}]
    valid = [{"canonicalUrl": "https://youtu.be/abcdefghijk", "transcriptStartSeconds": 42, "publisher": "Race channel"}]
    assert timestamped_youtube_receipt(untimestamped) is None
    assert timestamped_youtube_receipt(wrong_host) is None
    assert timestamped_youtube_receipt(invalid_timestamp) is None
    assert timestamped_youtube_receipt(valid)["videoId"] == "abcdefghijk"


def test_procedural_visual_is_stable_labeled_and_not_documentary():
    kwargs = {
        "item_id": "story_1",
        "headline": "A flat tire made gravel admit teams exist",
        "body_text": "The team worked together.",
        "receipts": [],
        "date_label": "May 2026",
        "stable_hash": "abc123",
    }
    first = render_story_visual(**kwargs)
    second = render_story_visual(**kwargs)
    assert first == second
    assert 'data-visual-system="gravel-weekly-visual/v1"' in first
    assert "GW ART DEPT. // AUTO" in first
    assert "not a news photo" in first.casefold()
    assert "TEAMWORK" in first
    assert "<iframe" not in first
    assert "<img" not in first


def test_historical_story_turn_visual_uses_only_supplied_before_after_copy():
    visual = render_story_visual(
        item_id="history-teamification-2026",
        headline="The privateer became gravel's unpaid control group",
        body_text="Teams changed access to race-deciding support.",
        receipts=[],
        date_label="2026-02-10 → 2026-05-26",
        stable_hash="abc123",
        prior_judgment="Top-level gravel remained unusually accessible to independent riders.",
        changed_judgment="The start stayed open while competitive infrastructure became gated.",
        point="Open registration survived while race-deciding support became less open.",
    )
    assert 'data-visual-role="story-turn"' in visual
    assert 'data-story-grammar="before-after"' in visual
    assert "BEFORE" in visual and "AFTER" in visual
    assert "Top-level gravel remained" in visual
    assert "competitive infrastructure" in visual
    assert "Open registration survived" in visual
    assert "Hash-bound before → after" in visual
    assert "not a news photo" in visual
    assert "<img" not in visual and "<iframe" not in visual


def test_timestamped_video_visual_links_exact_claim_without_autoplay_or_embed():
    visual = render_story_visual(
        item_id="story_video",
        headline="A race changed",
        body_text="A timestamped rider account.",
        receipts=[{
            "canonicalUrl": "https://www.youtube.com/watch?v=abcdefghijk",
            "transcriptStartSeconds": 125,
            "publisher": "Rider channel",
        }],
        date_label="August 2026",
    )
    assert "VERIFIED SOURCE VIDEO" in visual
    assert "WATCH @ 2:05" in visual
    assert "https://www.youtube.com/watch?v=abcdefghijk&amp;t=125s" in visual
    assert "autoplay" not in visual.casefold()
    assert "<iframe" not in visual


def test_visual_css_uses_brand_tokens_and_respects_reduced_motion():
    css = visual_css()
    assert "var(--gg-color-" in css
    assert "@media (prefers-reduced-motion: no-preference)" in css
    assert "@media (max-width: 620px)" in css
    assert "linear 1 both" in css
    assert "infinite" not in css
    assert "#" not in css


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


def sample_approval(draft=None):
    draft = draft or sample_draft()
    return {
        "schemaVersion": "gravel-weekly-approval/v3",
        "issueId": "gravel-weekly-001",
        "reviewedDraftContentHash": draft["contentHash"],
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


def test_weekly_culture_artifacts_are_direct_hash_bound_context_and_survive_approval():
    artifact = sample_weekly_culture_artifact()
    published = sample_issue()
    published["stories"][0]["cultureArtifacts"] = [artifact]
    published["sourceIndex"].append(artifact["canonicalUrl"])
    published["contentHash"] = compute_content_hash(published)
    validated = validate_issue(published)
    assert validated["stories"][0]["cultureArtifacts"][0]["canProveClaim"] is False
    assert validated["stories"][0]["cultureArtifacts"][0]["canEstablishConsensus"] is False
    public = build_page(published, [published], latest=True)
    assert "THE SCENE REPORT" in public
    assert 'href="#scene-story_1"' in public
    assert 'id="scene-story_1"' in public
    assert artifact["title"] in public
    assert artifact["reviewReason"] not in public
    assert "iframe" not in public

    draft = sample_draft()
    draft["stories"][0]["cultureArtifacts"] = [artifact]
    draft["sourceIndex"].append(artifact["canonicalUrl"])
    draft["contentHash"] = compute_content_hash(draft)
    approved = approve_issue(draft, sample_approval(draft))
    assert approved["stories"][0]["cultureArtifacts"] == [artifact]

    unsafe = copy.deepcopy(published)
    unsafe["stories"][0]["cultureArtifacts"][0]["canEstablishConsensus"] = True
    with pytest.raises(IssueValidationError, match="canEstablishConsensus must be false"):
        validate_issue(unsafe, verify_hash=False)

    stale = copy.deepcopy(published)
    stale["stories"][0]["cultureArtifacts"][0]["publishedAt"] = "2026-07-01T18:30:00Z"
    with pytest.raises(IssueValidationError, match="14-day weekly culture window"):
        validate_issue(stale, verify_hash=False)

    missing_index = copy.deepcopy(published)
    missing_index["sourceIndex"].remove(artifact["canonicalUrl"])
    with pytest.raises(IssueValidationError, match="sourceIndex omits culture artifact URLs"):
        validate_issue(missing_index, verify_hash=False)


def test_timestamped_youtube_culture_card_opens_the_reviewed_moment():
    artifact = sample_culture_artifact()
    artifact.update({
        "sourceKind": "youtube",
        "canonicalUrl": "https://www.youtube.com/watch?v=abcdefghijk&list=example",
        "timestampSeconds": 3130,
        "collectionMethod": "public_metadata",
    })
    card = render_culture_artifacts([artifact])
    assert "OPEN ORIGINAL · 52:10" in card
    assert "https://www.youtube.com/watch?v=abcdefghijk&amp;list=example&amp;t=3130s" in card
    assert 'data-culture-visual="gravel-weekly-culture-visual/v1"' in card
    assert "SOURCE VIDEO // LOCAL FACADE" in card
    assert "WATCH @ 52:10" in card
    assert "no embed or thumbnail" in card
    assert "<img" not in card
    assert "iframe" not in card
    assert ".gw-culture-card:only-child { grid-column: 1 / -1; }" in culture_css()


def test_non_video_culture_artifact_gets_stable_local_poster_not_fake_source_media():
    artifact = sample_weekly_culture_artifact()
    artifact["title"] = "Privateers, team buses & <script>alert(1)</script>"
    first = render_culture_artifacts([artifact])
    second = render_culture_artifacts([artifact])

    assert first == second
    assert 'data-culture-visual="gravel-weekly-culture-visual/v1"' in first
    assert "GW CULTURE DESK // AUTO" in first
    assert "Abstract context poster; not the source image." in first
    assert "FROM THE GROUP CHAT · BLUESKY" in first
    assert "CALENDAR / WORLDS" in first
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in first
    assert "<script>" not in first
    assert "<img" not in first and "<iframe" not in first


def test_culture_poster_css_is_brand_token_only_and_accessible_without_motion():
    css = culture_css()
    assert ".gw-culture-poster" in css
    assert "var(--gg-color-" in css
    assert ":focus-visible" in css
    assert "#" not in css
    assert "infinite" not in css


def test_claim_bound_cast_and_field_notes_survive_approval_and_render_as_optional_departments():
    issue = sample_issue()
    story = issue["stories"][0]
    story["cast"] = [{
        "name": "The organizer",
        "role": "Published the revised course distance.",
        "claimIds": ["claim_1"],
    }]
    story["fieldNotes"] = [{
        "text": "The revision arrived before the final route file.",
        "claimIds": ["claim_1"],
    }]
    issue["contentHash"] = compute_content_hash(issue)
    assert validate_issue(issue)["stories"][0]["cast"] == story["cast"]
    page = build_page(issue, [issue], latest=True)
    assert 'href="#cast-story_1"' in page
    assert 'id="cast-story_1"' in page
    assert 'href="#field-notes-story_1"' in page
    assert 'id="field-notes-story_1"' in page
    assert "WHO IS ACTUALLY IN THIS STORY" in page
    assert "THE DETAILS THAT MAKE THE SCENE LEGIBLE" in page
    assert 'aria-label="Source 1: Cyclingnews"' in page

    draft = sample_draft()
    draft["stories"][0]["cast"] = copy.deepcopy(story["cast"])
    draft["stories"][0]["fieldNotes"] = copy.deepcopy(story["fieldNotes"])
    draft["contentHash"] = compute_content_hash(draft)
    approved = approve_issue(draft, sample_approval(draft))
    assert approved["stories"][0]["cast"] == story["cast"]
    assert approved["stories"][0]["fieldNotes"] == story["fieldNotes"]

    missing_claim = copy.deepcopy(issue)
    missing_claim["stories"][0]["cast"][0]["claimIds"] = ["missing_claim"]
    with pytest.raises(IssueValidationError, match="without story receipts"):
        validate_issue(missing_claim, verify_hash=False)

    invented_note = copy.deepcopy(issue)
    invented_note["stories"][0]["fieldNotes"][0]["claimIds"] = []
    with pytest.raises(IssueValidationError, match="claimIds must not be empty"):
        validate_issue(invented_note, verify_hash=False)

    unsupported = copy.deepcopy(issue)
    unsupported["stories"][0]["cast"][0]["portraitUrl"] = "https://example.com/photo.jpg"
    with pytest.raises(IssueValidationError, match="unsupported fields"):
        validate_issue(unsupported, verify_hash=False)


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
    culture_artifact = sample_weekly_culture_artifact()
    packet = with_passing_prose_gate({
        "candidateId": "story_1",
        "editorialGate": passing_editorial_gate(),
        "suggestedTake": {"label": "model_draft", "copy": "Editable model draft, not Matti's approved view: A sharp take."},
        "suggestedHeadline": "The course moved",
        "suggestedDek": "A small mileage change hides a larger terrain question.",
        "whatHappened": "The organizer published a revised distance. It affects preparation.",
        "receipts": [sample_issue()["stories"][0]["receipts"][0]],
        "raceImpacts": sample_issue()["stories"][0]["raceImpacts"],
        "cultureRead": {
            "relevance": "direct",
            "sourceUrls": [culture_artifact["canonicalUrl"]],
            "artifacts": [culture_artifact],
        },
        "cast": [{
            "name": "The organizer",
            "role": "Published the revised course distance.",
            "claimIds": ["claim_1"],
        }],
        "fieldNotes": [{
            "text": "The revision arrived before the final route file.",
            "claimIds": ["claim_1"],
        }],
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
    assert issue["stories"][0]["cultureArtifacts"] == [culture_artifact]
    assert issue["stories"][0]["cast"][0]["name"] == "The organizer"
    assert issue["stories"][0]["fieldNotes"][0]["claimIds"] == ["claim_1"]
    assert culture_artifact["canonicalUrl"] in issue["sourceIndex"]
    assert validate_issue(issue)["contentHash"] == issue["contentHash"]
    preview = build_page(issue, [issue], latest=True)
    assert "DRAFT — NOT PUBLISHED" in preview
    assert "THE TAKE — MODEL DRAFT" in preview
    assert "The model draft awaiting approval" in preview
    assert "The approved judgment" not in preview
    assert "PRIVATE CULTURE CHECK" in preview
    assert culture_artifact["reviewReason"] in preview
    assert "application/ld+json" not in preview


def test_human_approval_bridge_changes_only_editorial_copy_and_stays_non_deployable():
    draft = sample_draft()
    approved = approve_issue(draft, sample_approval(draft))

    assert approved["status"] == "approved"
    assert approved["publishedAt"] is None
    assert approved["editorialApproval"] == {
        "approver": "Matti Rowe",
        "approvedAt": "2026-08-28T16:00:00Z",
        "reviewedDraftContentHash": draft["contentHash"],
    }
    assert approved["stories"][0]["headline"] == "The approved headline"
    assert approved["stories"][0]["take"] == "The approved take makes a concrete judgment."
    assert approved["stories"][0]["takeProvenance"] == "human_approved"
    for field in (
        "score", "storyKind", "whatHappened", "receipts", "raceImpacts",
        "cultureArtifacts", "cast", "fieldNotes",
    ):
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
    with pytest.raises(ValueError, match="explicit quiet issue decision"):
        approve_issue(draft, rejected)

    misleading = sample_approval()
    misleading["whatHappened"] = "Quietly replace the reviewed facts."
    with pytest.raises(ValueError, match="unsupported fields"):
        approve_issue(draft, misleading)


def test_weekly_approval_is_bound_to_the_exact_reviewed_draft_hash():
    draft = sample_draft()
    stale = sample_approval(draft)
    stale["reviewedDraftContentHash"] = "0" * 64
    with pytest.raises(ValueError, match="exact reviewed draft"):
        approve_issue(draft, stale)

    malformed = sample_approval(draft)
    malformed["reviewedDraftContentHash"] = "not-a-hash"
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        approve_issue(draft, malformed)

    approved = approve_issue(draft, sample_approval(draft))
    receipt = build_decision_receipt(draft, sample_approval(draft), approved)
    forged = copy.deepcopy(approved)
    forged["editorialApproval"]["reviewedDraftContentHash"] = "f" * 64
    forged["contentHash"] = compute_content_hash(forged)
    with pytest.raises(ValueError, match="reviewed draft hash"):
        validate_decision_receipt(receipt, forged)


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
    assert issue["quietIssue"]["provenance"] == "model_draft"


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
    assert issue["quietIssue"]["provenance"] == "model_draft"


def test_quiet_issue_requires_explicit_human_copy_approval_and_has_a_durable_receipt():
    review = {
        "schemaVersion": "gravel-weekly-review/v1",
        "candidates": [],
        "packets": [],
    }
    draft = prepare_issue(
        review, "2026-09-04", 2, now="2026-09-03T17:00:00Z"
    )
    approval = {
        "schemaVersion": "gravel-weekly-approval/v3",
        "issueId": draft["issueId"],
        "reviewedDraftContentHash": draft["contentHash"],
        "approver": "Matti Rowe",
        "approvedAt": "2026-09-04T16:00:00Z",
        "currentThingStoryId": None,
        "stories": [],
        "quietIssue": {
            "decision": "approve",
            "headline": "Nothing cleared the gate this week.",
            "note": (
                "The Friday deadline does not turn an update into a story. "
                "Gravel Weekly will be back when there is a point worth making."
            ),
            "editSummary": "Approved the short issue without manufacturing a story.",
        },
    }

    approved = approve_issue(draft, approval)
    assert approved["status"] == "approved"
    assert approved["stories"] == []
    assert approved["currentThingStoryId"] is None
    assert approved["quietIssue"]["provenance"] == "human_approved"

    receipt = build_decision_receipt(draft, approval, approved)
    assert receipt["schemaVersion"] == "gravel-weekly-decision-receipt/v2"
    assert receipt["decisions"] == []
    assert receipt["quietIssueDecision"]["approvedHeadline"] == approved["quietIssue"]["headline"]
    assert receipt["quietIssueDecision"]["approvedNote"] == approved["quietIssue"]["note"]
    assert validate_decision_receipt(receipt, approved) == receipt

    sealed = seal_issue(approved, "2026-09-04T16:05:00Z")
    assert validate_decision_receipt(receipt, sealed) == receipt
    page = build_page(sealed, [sealed], latest=True)
    assert 'id="quiet-week"' in page
    assert "THE QUIET WEEK" in page
    assert "Nothing cleared the gate this week." in page
    assert "CALENDAR WATCH" not in page
    assert "WHAT THIS CHANGES" not in page
    assert "MODEL DRAFT" not in page
    email = build_email_html(sealed)
    assert "THE QUIET WEEK" in email
    assert approved["quietIssue"]["note"] in email


def test_rejecting_every_story_can_become_a_human_approved_quiet_issue():
    draft = sample_draft()
    approval = sample_approval(draft)
    approval["stories"] = [{
        "candidateId": "story_1",
        "decision": "reject",
        "reason": "The premise is still slop.",
    }]
    approval["currentThingStoryId"] = None
    approval["quietIssue"] = {
        "decision": "approve",
        "headline": "Nothing cleared the gate this week.",
        "note": "One candidate arrived. It did not have a point worth publishing.",
        "editSummary": "Rejected the candidate and approved the exact quiet note.",
    }

    approved = approve_issue(draft, approval)
    assert approved["stories"] == []
    assert approved["quietIssue"]["provenance"] == "human_approved"
    receipt = build_decision_receipt(draft, approval, approved)
    assert receipt["decisions"][0]["decision"] == "reject"
    assert receipt["quietIssueDecision"]["suggestedHeadline"] is None


def test_quiet_issue_cannot_coexist_with_stories_or_unapproved_copy():
    issue = sample_issue()
    issue["quietIssue"] = {
        "headline": "Nothing cleared the gate this week.",
        "note": "There is no issue.",
        "provenance": "human_approved",
    }
    with pytest.raises(IssueValidationError, match="cannot coexist"):
        validate_issue(issue, verify_hash=False)

    review = {"schemaVersion": "gravel-weekly-review/v1", "candidates": [], "packets": []}
    draft = prepare_issue(review, "2026-09-04", 2, now="2026-09-03T17:00:00Z")
    unapproved = copy.deepcopy(draft)
    unapproved["status"] = "approved"
    unapproved["editorialApproval"] = {
        "approver": "Matti Rowe",
        "approvedAt": "2026-09-04T16:00:00Z",
        "reviewedDraftContentHash": draft["contentHash"],
    }
    with pytest.raises(IssueValidationError, match="human-approved provenance"):
        validate_issue(unapproved, verify_hash=False)

    slopped = copy.deepcopy(draft)
    slopped["quietIssue"]["note"] = "The future isn't coming. It's already here."
    with pytest.raises(IssueValidationError, match="no-ai-slop gate"):
        validate_issue(slopped, verify_hash=False)


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
    assert 'class="gw-contents"' in page
    assert 'href="#record-story_1"' in page
    assert 'id="record-story_1"' in page
    assert 'href="#take-story_1"' in page
    assert 'id="take-story_1"' in page
    assert "THE RECORD" in page
    assert "WHAT THIS CHANGES" in page
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
    held_gate["editorialGateNotes"] = {
        "friend": "The story still fails the friend-at-a-party attention test."
    }
    with pytest.raises(IssueValidationError, match="every editorial gate"):
        validate_history_entry(held_gate, verify_hash=False)

    undocumented_hold = sample_history_draft()
    undocumented_hold["editorialGates"]["hostileEditor"] = "hold"
    with pytest.raises(IssueValidationError, match="exactly the non-passing"):
        validate_history_entry(undocumented_hold, verify_hash=False)

    stale_gate_note = sample_history_draft()
    stale_gate_note["editorialGateNotes"] = {
        "hostileEditor": "This note must not survive after the gate passes."
    }
    with pytest.raises(IssueValidationError, match="must be empty"):
        validate_history_entry(stale_gate_note, verify_hash=False)

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
        "contemporaryReceipts", "laterEvidence", "cultureArtifacts", "raceImpacts",
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
    draft["editorialGateNotes"] = {
        "hostileEditor": "The governing claim outruns the evidence currently attached."
    }
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
    held["editorialGateNotes"] = {
        "friend": "The premise is accurate but would lose the room before reaching a point."
    }
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
    assert "MODEL DRAFT: The privateer" not in page
    assert reviewed_headline_copy(draft) == "The privateer became gravel's control group"
    assert "The privateer became gravel&#x27;s control group" in page
    assert "Model draft, not Matti's approved view:" not in page
    assert reviewed_take_copy(draft) in page
    assert "NO-AI-SLOP PROSE GATE · PASS" in page
    assert "NO-AI-SLOP PROSE GATE · FAIL" in page
    assert "no-AI-slop prose gate" in page
    assert "fake_profound_kicker" in page
    assert "not an AI-authorship detector" in page
    assert 'data-visual-role="story-turn"' in page
    assert draft["priorJudgment"] in page
    assert draft["changedJudgment"] in page
    assert "CONTEMPORARY RECEIPTS (2)" in page
    assert "LATER EVIDENCE (1)" in page
    assert "any decision binds to this exact draft hash" in page.lower()
    assert "approval fails closed while any hold remains" in page.lower()
    assert "WHY HOLD:" in page
    assert held["editorialGateNotes"]["friend"] in page
    assert draft["contentHash"] in page
    assert "noindex,nofollow" in page
    assert "@font-face" in page
    assert 'href="index.html">← ALL YEARS</a>' in page
    assert page.index(f'href="#{draft["entryId"]}"') < page.index(f'href="#{held["entryId"]}"')


def test_historical_review_index_prioritizes_recent_ready_decisions():
    ready_2026 = sample_history_draft()
    ready_2025 = copy.deepcopy(ready_2026)
    ready_2025.update({
        "entryId": "history-ready-2025",
        "activeFrom": "2025-04-01",
        "activeThrough": "2025-04-30",
        "headline": "MODEL DRAFT: A 2025 premise",
        "editorialScore": 99,
    })
    ready_2025["contentHash"] = compute_history_content_hash(ready_2025)
    held_2026 = copy.deepcopy(ready_2026)
    held_2026.update({
        "entryId": "history-held-2026",
        "headline": "MODEL DRAFT: A held 2026 premise",
        "editorialScore": 100,
    })
    held_2026["editorialGates"]["hostileEditor"] = "hold"
    held_2026["editorialGateNotes"] = {
        "hostileEditor": "The headline claims more institutional control than the record proves."
    }
    held_2026["contentHash"] = compute_history_content_hash(held_2026)

    assert review_years([ready_2025, held_2026, ready_2026]) == [2026, 2025]
    assert sorted([held_2026, ready_2026], key=review_priority)[0]["entryId"] == ready_2026["entryId"]
    page = render_history_review_index([ready_2025, held_2026, ready_2026])

    assert "THE WHOLE<br>GRAVEL STORY" in page
    assert "2 YEARS" in page
    assert "2 READY FOR HUMAN DECISION" in page
    assert "1 HELD" in page
    assert page.index('href="2026.html"') < page.index('href="2025.html"')
    assert "@font-face" in page
    assert "noindex,nofollow" in page


def test_bulk_history_approval_is_exact_ready_only_and_non_publishing(tmp_path):
    ready = sample_history_draft()
    held = copy.deepcopy(ready)
    held["entryId"] = "history-held-2026"
    held["editorialGates"]["hostileEditor"] = "hold"
    held["editorialGateNotes"] = {
        "hostileEditor": "The conclusion outruns the evidence currently attached."
    }
    held["contentHash"] = compute_history_content_hash(held)

    prepared = prepare_ready_approvals(
        [ready, held],
        year=2026,
        phrase="approve all READY 2026 entries as written",
        approver="Matti Rowe",
        decided_at="2026-08-28T16:00:00Z",
    )

    assert [item.entry_id for item in prepared] == [ready["entryId"]]
    assert prepared[0].approved["headline"] == "The privateer became gravel's control group"
    assert prepared[0].approved["take"] == "Gravel installed a backstage entrance."
    assert prepared[0].approved["status"] == "approved"
    assert prepared[0].approved["publishedAt"] is None
    assert prepared[0].decision["reviewedDraftContentHash"] == ready["contentHash"]
    targets = stage_ready_approvals(prepared, tmp_path)
    assert len(targets) == 2
    assert not any(held["entryId"] in path.name for path in targets)

    with pytest.raises(ValueError, match="approval phrase must exactly equal"):
        prepare_ready_approvals(
            [ready],
            year=2026,
            phrase="approve the 2026 entries",
            approver="Matti Rowe",
            decided_at="2026-08-28T16:00:00Z",
        )
    with pytest.raises(FileExistsError, match="refusing to replace"):
        stage_ready_approvals(prepared, tmp_path)


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


def test_only_sealed_historical_snapshots_cross_the_public_loader(tmp_path):
    published = sample_history_entry()
    approved = copy.deepcopy(published)
    approved.update({
        "entryId": "history-approved-but-unpublished-2026",
        "status": "approved",
        "publishedAt": None,
    })
    draft = copy.deepcopy(published)
    draft.update({
        "entryId": "history-held-model-draft-2026",
        "status": "draft",
        "take": "Model draft, not Matti's approved view: this stays backstage.",
        "takeProvenance": "model_draft",
        "editorialApproval": None,
    })
    draft["editorialGates"]["hostileEditor"] = "hold"
    draft["editorialGateNotes"] = {
        "hostileEditor": "The conclusion outruns the evidence currently attached."
    }
    published["contentHash"] = compute_history_content_hash(published)
    approved["contentHash"] = compute_history_content_hash(approved)
    draft["contentHash"] = compute_history_content_hash(draft)
    (tmp_path / "published.json").write_text(json.dumps(published))
    (tmp_path / "approved.json").write_text(json.dumps(approved))
    (tmp_path / "draft.json").write_text(json.dumps(draft))

    assert {entry["entryId"] for entry in load_history_entries(tmp_path)} == {
        published["entryId"],
        approved["entryId"],
        draft["entryId"],
    }
    assert [entry["entryId"] for entry in load_public_history_entries(tmp_path)] == [published["entryId"]]


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
    assert f"gravel-weekly-history-hash: {entry['contentHash']}" in html
    assert "THE SEASON AS A STORY" in html
    assert "WHAT WAS KNOWABLE THEN" in html
    assert "LATER EVIDENCE — NOT AVAILABLE THEN" in html
    assert "WHY IT MATTERED" in html
    assert "THE FAIR OBJECTION" in html
    assert "The privateer became gravel" in html
    assert 'data-visual-role="story-turn"' in html
    assert entry["priorJudgment"] in html
    assert entry["changedJudgment"] in html
    assert "innerHTML" not in html
    page = build_page(sample_issue(), [sample_issue()], latest=True, history_entries=[entry])
    assert 'id="season-story"' in page
    assert page.index("THE CURRENT THING") < page.index("THE SEASON AS A STORY") < page.index("PAST ISSUES")


def test_historical_timeline_groups_change_points_into_accessible_year_chapters():
    entry_2026 = sample_history_entry()
    entry_2025 = copy.deepcopy(entry_2026)
    entry_2025.update({
        "entryId": "history-privateer-shift-2025",
        "activeFrom": "2025-04-01",
        "activeThrough": "2025-04-30",
        "headline": "The privateer bill arrived before the team bus",
    })
    entry_2025["contentHash"] = compute_history_content_hash(entry_2025)

    html = render_history_timeline([entry_2026, entry_2025])

    assert 'id="gravel-history-years"' in html
    assert 'aria-label="Jump to a year in gravel history"' in html
    assert 'href="#gravel-year-2026"' in html
    assert 'href="#gravel-year-2025"' in html
    assert 'id="gravel-year-2026" aria-label="Gravel in 2026"' in html
    assert 'id="gravel-year-2025" aria-label="Gravel in 2025"' in html
    assert html.index('href="#gravel-year-2026"') < html.index('href="#gravel-year-2025"')
    assert html.index('id="gravel-year-2026"') < html.index('id="gravel-year-2025"')
    assert html.count('href="#gravel-history-years"') == 2
    assert "1 approved change-point" in html
    assert "innerHTML" not in html


def test_historical_culture_artifacts_are_hash_bound_context_not_evidence():
    entry = sample_history_entry()
    original_hash = entry["contentHash"]
    entry["cultureArtifacts"] = [sample_culture_artifact()]
    entry["contentHash"] = compute_history_content_hash(entry)
    validated = validate_history_entry(entry)
    assert validated["contentHash"] != original_hash
    assert validated["cultureArtifacts"][0]["canProveClaim"] is False
    assert validated["cultureArtifacts"][0]["canEstablishConsensus"] is False

    unsafe = copy.deepcopy(entry)
    unsafe["cultureArtifacts"][0]["canProveClaim"] = True
    with pytest.raises(IssueValidationError, match="canProveClaim must be false"):
        validate_history_entry(unsafe, verify_hash=False)

    off_period = copy.deepcopy(entry)
    off_period["cultureArtifacts"][0]["publishedAt"] = "2025-03-01T18:30:00Z"
    with pytest.raises(IssueValidationError, match="inside the historical active period"):
        validate_history_entry(off_period, verify_hash=False)

    copied_media = copy.deepcopy(entry)
    copied_media["cultureArtifacts"][0]["mediaUrl"] = "https://cdn.example/copied.jpg"
    with pytest.raises(IssueValidationError, match="unsupported fields"):
        validate_history_entry(copied_media, verify_hash=False)


def test_historical_culture_cards_render_in_review_and_only_after_publication():
    entry = sample_history_entry()
    entry["cultureArtifacts"] = [sample_culture_artifact()]
    entry["contentHash"] = compute_history_content_hash(entry)
    public = render_history_timeline([entry])
    assert "THE SCENE REPORT" in public
    assert "WHAT THE GROUP CHAT WAS PASSING AROUND" in public
    assert 'data-culture-artifact="historical-culture_0123456789abcdef"' in public
    assert "Gravel has entered its team-bus era." in public
    assert "https://x.com/gravelperson/status/123456789" in public
    assert "A contemporaneous joke compressed" not in public
    assert "iframe" not in public
    assert "platform.twitter.com" not in public

    draft = sample_history_draft()
    draft["cultureArtifacts"] = [sample_culture_artifact()]
    draft["contentHash"] = compute_history_content_hash(draft)
    private = render_history_review([draft], 2026)
    assert "PRIVATE CULTURE CHECK" in private
    assert 'class="story-contents"' in private
    assert f'href="#{draft["entryId"]}-scene"' in private
    assert f'id="{draft["entryId"]}-scene"' in private
    assert "THE RECORD" in private
    assert "THE OTHER SIDE" in private
    assert "WHAT THIS CHANGES" in private
    assert "A contemporaneous joke compressed" in private
    approved, _ = apply_history_decision(draft, sample_history_approval(draft))
    assert approved is not None
    assert approved["cultureArtifacts"] == draft["cultureArtifacts"]


def test_historical_culture_sweep_becomes_diverse_topical_private_proposal():
    draft = sample_history_draft()
    sweep = {
        "schemaVersion": "historical-culture-sweep/v1",
        "year": 2026,
        "candidates": [
            {
                "id": "x_team_bus", "platform": "x", "canonicalUrl": "https://x.com/gravelperson/status/1",
                "authorHandle": "gravelperson", "authorName": "Gravel Person", "publishedAt": "2026-03-01T18:30:00Z",
                "excerpt": "Gravel has entered its team-bus era.", "queryIds": ["teamification"], "queryLabels": ["Teamification"],
                "attentionScore": 94, "purpose": "culture_sensor", "canProveClaim": False,
            },
            {
                "id": "x_generic", "platform": "x", "canonicalUrl": "https://x.com/other/status/2",
                "authorHandle": "other", "authorName": None, "publishedAt": "2026-03-02T18:30:00Z",
                "excerpt": "A viral but generic gravel post.", "queryIds": ["gravel-scene"], "queryLabels": ["Gravel scene"],
                "attentionScore": 100, "purpose": "culture_sensor", "canProveClaim": False,
            },
            {
                "id": "x_late", "platform": "x", "canonicalUrl": "https://x.com/late/status/3",
                "authorHandle": "late", "authorName": None, "publishedAt": "2026-07-02T18:30:00Z",
                "excerpt": "Right topic, wrong moment.", "queryIds": ["teamification"], "queryLabels": ["Teamification"],
                "attentionScore": 99, "purpose": "culture_sensor", "canProveClaim": False,
            },
        ],
        "supplementalArtifacts": [{
            "id": "yt_privateer", "sourceKind": "youtube", "publisher": "Bonk Bros", "author": "Bonk Bros",
            "canonicalUrl": "https://www.youtube.com/watch?v=abcdefghijk", "publishedAt": "2026-03-03T12:00:00Z",
            "title": "Privateers and the team-bus era", "excerpt": "The paddock suddenly has hierarchy.",
            "timestampSeconds": 812, "topicTags": ["privateers"], "reviewReason": "A contemporaneous discussion of the same access fight.",
            "collectionMethod": "authorized_caption", "purpose": "culture_sensor", "canProveClaim": False,
        }],
        "crossSourcePatterns": [{"topicTag": "teamification", "sourceKinds": ["x", "youtube"], "artifactIds": ["x_team_bus", "yt_privateer"], "boundary": "research only"}],
        "canEstablishConsensus": False,
        "canProveClaim": False,
        "humanApprovalRequired": True,
        "autoPublishAllowed": False,
    }
    proposal = prepare_history_culture_proposal(draft, sweep, max_artifacts=4)
    assert [artifact["artifactId"] for artifact in proposal["cultureArtifacts"]] == ["x_team_bus", "yt_privateer"]
    assert {artifact["sourceKind"] for artifact in proposal["cultureArtifacts"]} == {"x", "youtube"}
    assert all(artifact["canProveClaim"] is False for artifact in proposal["cultureArtifacts"])
    assert proposal["contentHash"] != draft["contentHash"]
    assert proposal["status"] == "draft"
    assert proposal["editorialApproval"] is None

    unsafe = copy.deepcopy(sweep)
    unsafe["canEstablishConsensus"] = True
    with pytest.raises(IssueValidationError, match="safety boundary"):
        prepare_history_culture_proposal(draft, unsafe)


def test_published_history_creates_a_controlled_hash_bound_race_impact_queue():
    draft = sample_history_draft()
    draft["raceImpacts"] = [{
        "impactKind": "editorial_review",
        "raceId": "gravel:unbound-200",
        "fieldPath": "race.history",
        "claimIds": ["claim_team_1"],
        "confidence": 0.91,
        "owner": "Gravel God historical editorial review",
        "autoFixAllowed": False,
    }]
    draft["contentHash"] = compute_history_content_hash(draft)
    approval = sample_history_approval(draft)
    approved, decision = apply_history_decision(draft, approval)
    assert approved is not None
    published = seal_history_entry(approved, "2026-08-28T16:05:00Z")

    review, count, set_hash = render_history_race_impact_review(
        [published], {published["entryId"]: decision}, year=2026
    )

    assert count == 1
    assert len(set_hash) == 64
    assert f"gravel-weekly-history-set-hash: {set_hash}" in review
    assert published["contentHash"] in review
    assert "Controlled review only" in review
    assert "does not authorize or perform a race-profile edit" in review
    assert "claim_team_1" in review
    assert "https://www.cyclingnews.com/team-story/" in review
    with pytest.raises(ValueError, match="historical decision missing"):
        render_history_race_impact_review([published], {}, year=2026)


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
    history_workflow = (ROOT / ".github" / "workflows" / "gravel-weekly-history-publish.yml").read_text()
    assert "workflow_dispatch:" in history_workflow
    assert 'group: gravel-weekly-publish' in history_workflow
    assert 'refs/heads/main' in history_workflow
    assert "load_public_history_entries" in history_workflow
    assert "validate_history_decision" in history_workflow
    assert "render_gravel_weekly_history_race_impact_review.py" in history_workflow
    assert "meaningful-history-race-impact-count: 0" in history_workflow
    assert "gravel-weekly-history-hash:" in history_workflow
    assert "--sync-gravel-weekly --sync-homepage --sync-redirects --purge-cache" in history_workflow
    assert "send_gravel_weekly.py" not in history_workflow


def test_homepage_surfaces_gravel_weekly_without_a_gravel_tv_content_path():
    band = build_gravel_weekly_band()
    assert 'id="gravel-weekly"' in band
    assert 'href="/gravel-weekly/"' in band
    assert "GRAVEL <em>WEEKLY</em>" in band
    assert "Gravel TV" not in band


def test_email_preserves_legacy_subscribers_and_renders_a_sealed_issue():
    issue = sample_issue()
    email = build_email_html(issue)
    assert SUBSCRIBER_SOURCES == ("gravel_weekly_subscribe", "gravel_tv_subscribe")
    assert "Gravel Weekly" in email
    assert "Unbound changed the course" in email
    assert "/gravel-weekly/2026-08-28/" in email
    assert "RESEND_UNSUBSCRIBE_URL" in email


def test_only_sealed_issue_snapshots_cross_the_public_loader(tmp_path):
    published = sample_issue()
    approved = copy.deepcopy(published)
    approved.update({
        "issueId": "gravel-weekly-002",
        "issueNumber": 2,
        "publicationDate": "2026-09-04",
        "slug": "2026-09-04",
        "status": "approved",
        "publishedAt": None,
        "updatedAt": "2026-09-04T16:00:00Z",
    })
    approved["contentHash"] = compute_content_hash(approved)
    (tmp_path / "2026-08-28.json").write_text(json.dumps(published))
    (tmp_path / "2026-09-04.json").write_text(json.dumps(approved))

    assert [issue["issueId"] for issue in load_issues(tmp_path)] == [
        approved["issueId"],
        published["issueId"],
    ]
    assert [issue["issueId"] for issue in load_public_issues(tmp_path)] == [
        published["issueId"],
    ]
