"""Offline release validation for rendered prep-kit race facts.

The validator deliberately verifies release-packet bindings, not organizer-site
truth.  A human reviewer must compare the preserved capture with the rendered
claim; this module makes that decision, the captured bytes, and the exact
publication bytes auditable before ``sync_prep_kits`` can upload anything.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "prep-kit-rendered-fact-review/v1"
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_LABEL_PATTERNS = {
    "distance": ("Distance",),
    "elevation": ("Elevation",),
    "race_date": ("Race Date", "Date"),
    "location": ("Location",),
    "conditions": ("Conditions", "Expected Conditions"),
    "race_week_climate": ("Climate",),
    "race_week_challenges": ("Key Challenges",),
    "course": ("Signature Challenge", "Course"),
    "entry_fee": ("Entry Fee",),
    "trip_cost": ("Cost of Trip",),
    "nearest_airport": ("Nearest Airport",),
    "aid_stations": ("Aid Stations",),
}
_DISTANCE_RE = re.compile(r"\b\d[\d,.]*\s*(?:mi|miles|km|kilometers)\b", re.IGNORECASE)
_ELEVATION_RE = re.compile(r"\b\d[\d,.]*\s*(?:ft|feet|met(?:er|re)s?)\b", re.IGNORECASE)
_START_TIME_LABEL_RE = re.compile(
    r"(?is)<strong>\s*[^<]+?\s+Start\s+Time\s*:\s*</strong>")


class GateError(ValueError):
    """The release packet does not prove the required offline bindings."""


@dataclass(frozen=True)
class GateReport:
    proposed_pages: list[str]
    changed_facts: list[tuple[str, str]]
    new_pages: list[str]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(fragment: str) -> str:
    text = " ".join(html.unescape(re.sub(r"(?is)<[^>]+>", " ", fragment)).split())
    return re.sub(r"\s+([,.;:!?])", r"\1", text)


def _normalized_text(fragment: str) -> str:
    """Stable text normalization used for the capture/excerpt byte binding."""
    return _text(fragment).casefold()


def _label_values(page_html: str, label: str) -> list[str]:
    escaped = re.escape(label)
    label_pattern = rf"(?is)<strong>\s*{escaped}\s*:\s*</strong>"
    matches = re.findall(label_pattern + r"\s*(.*?)\s*</p\s*>", page_html)
    if re.search(label_pattern, page_html) and not matches:
        raise GateError(f"malformed rendered {label!r} field")
    values = []
    for match in matches:
        value = _text(match)
        if not value:
            raise GateError(f"malformed rendered {label!r} field has no value")
        values.append(value)
    return values


def _unique_field(field: str, values: list[str], facts: dict[str, str]) -> None:
    if not values:
        return
    distinct = set(values)
    if len(distinct) != 1:
        raise GateError(f"conflicting rendered {field} values: {sorted(distinct)!r}")
    value = values[0]
    if field in facts and facts[field] != value:
        raise GateError(f"conflicting rendered {field} values: {[facts[field], value]!r}")
    facts[field] = value


def _start_time_values(page_html: str) -> list[str]:
    """Extract the generator's race-specific start-time callout verbatim."""
    matches = re.findall(
        r"(?is)<strong>\s*[^<]+?\s+Start\s+Time\s*:\s*</strong>\s*(.*?)\s*</p\s*>",
        page_html,
    )
    if _START_TIME_LABEL_RE.search(page_html) and not matches:
        raise GateError("malformed rendered start-time field")
    values = []
    for match in matches:
        value = _text(match)
        if not value:
            raise GateError("malformed rendered start-time field has no value")
        values.append(value)
    return values


def _extract_hero_facts(page_html: str) -> dict[str, str]:
    """Parse the generator's public header, including legacy omitted vitals."""
    headers = re.findall(r"(?is)<header\s+class=[\"']gg-pk-header[\"']\s*>(.*?)</header\s*>", page_html)
    if len(headers) != 1:
        raise GateError("unrecognized prep-kit header layout")
    header = headers[0]
    titles = re.findall(r"(?is)<h1\s+class=[\"']gg-pk-header-title[\"']\s*>(.*?)</h1\s*>", header)
    if len(titles) != 1 or not _text(titles[0]):
        raise GateError("unrecognized prep-kit header title")
    ribbons = re.findall(r"(?is)<div\s+class=[\"']gg-pk-vitals-ribbon[\"']\s*>(.*?)</div\s*>", header)
    if len(ribbons) != 1:
        raise GateError("unrecognized prep-kit vitals-ribbon layout")
    stats = re.findall(r"(?is)<span\s+class=[\"']gg-pk-stat[\"']\s*>(.*?)</span\s*>", ribbons[0])
    values = [(_text(stat), bool(re.search(r"(?is)<strong\b", stat))) for stat in stats]
    if not values or any(not value[0] for value in values) or len(values) > 4:
        raise GateError("unrecognized prep-kit vitals-ribbon values")

    facts = {"name": _text(titles[0])}
    index = 0
    if index < len(values) and values[index][1]:
        if not _DISTANCE_RE.search(values[index][0]):
            raise GateError("unrecognized prep-kit distance value")
        facts["distance"] = values[index][0]
        index += 1
    if index < len(values) and values[index][1]:
        if not _ELEVATION_RE.search(values[index][0]):
            raise GateError("unrecognized prep-kit elevation value")
        facts["elevation"] = values[index][0]
        index += 1
    remaining = values[index:]
    if len(remaining) != 2:
        raise GateError("unrecognized prep-kit vitals-ribbon ordering")
    if remaining[0][1] or remaining[1][1]:
        raise GateError("unrecognized prep-kit date/location layout")
    # The legacy generator puts either a date or an explicit edition/status
    # statement in this same public slot; both are factual release content.
    facts["race_date"] = remaining[0][0]
    facts["location"] = remaining[1][0]
    return facts


def extract_rendered_facts(page_html: str) -> dict[str, str]:
    """Extract every modeled objective race fact from a known prep-kit layout.

    The public hero is mandatory and is parsed before optional race-context
    labels. Unknown/malformed hero markup refuses release rather than yielding
    an empty fact set. The extraction stays intentionally finite: it models the
    generator's factual header plus labeled race-context conditions/course data,
    not arbitrary editorial prose.
    """
    facts = _extract_hero_facts(page_html)
    for field, labels in _LABEL_PATTERNS.items():
        for label in labels:
            _unique_field(field, _label_values(page_html, label), facts)
    _unique_field("start_time", _start_time_values(page_html), facts)

    # Full-personalization kits render distance in the fueling heading instead
    # of the generic race-context box.  It is the same public distance claim.
    fueling = re.findall(
        r"(?is)<strong>\s*Your\s+Fueling\s+Math\s*\(\s*(.*?)\s+miles\s*\)\s*:",
        page_html,
    )
    _unique_field("distance", [f"{_text(value)} mi" for value in fueling], facts)
    return facts


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read release manifest {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise GateError("release manifest must be a JSON object")
    if document.get("schemaVersion") != SCHEMA_VERSION:
        raise GateError(f"release manifest schemaVersion must be {SCHEMA_VERSION!r}")
    metadata = document.get("baseline_metadata")
    if not isinstance(metadata, dict):
        raise GateError("release manifest requires baseline_metadata")
    captured_at = metadata.get("captured_at")
    if not isinstance(captured_at, str):
        raise GateError("baseline_metadata.captured_at is required")
    try:
        captured_time = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GateError("baseline_metadata.captured_at must be ISO-8601") from exc
    if captured_time.tzinfo is None or captured_time.utcoffset() is None:
        raise GateError("baseline_metadata.captured_at must include timezone")
    base_url = metadata.get("canonical_live_base_url")
    if not isinstance(base_url, str) or not base_url.startswith("https://"):
        raise GateError("baseline_metadata.canonical_live_base_url must be an https URL")
    return document


def _page_entries(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    pages = document.get("pages")
    if not isinstance(pages, list) or not pages:
        raise GateError("release manifest requires a non-empty pages list")
    result: dict[str, dict[str, Any]] = {}
    for entry in pages:
        if not isinstance(entry, dict) or not isinstance(entry.get("slug"), str):
            raise GateError("each release-manifest page requires a slug")
        slug = entry["slug"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug) or slug in result:
            raise GateError(f"invalid or duplicate manifest slug: {slug!r}")
        result[slug] = entry
    return result


def _require_hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _HASH_RE.fullmatch(value):
        raise GateError(f"{label} must be a lowercase sha256")
    return value


def _review_entries(entry: dict[str, Any], slug: str) -> dict[str, dict[str, Any]]:
    facts = entry.get("facts")
    if not isinstance(facts, list):
        raise GateError(f"{slug}: facts must be a list")
    result: dict[str, dict[str, Any]] = {}
    for review in facts:
        if not isinstance(review, dict) or not isinstance(review.get("field"), str):
            raise GateError(f"{slug}: each fact review requires field")
        field = review["field"]
        if field not in {"name", "start_time", * _LABEL_PATTERNS} or field in result:
            raise GateError(f"{slug}: invalid or duplicate fact field {field!r}")
        result[field] = review
    return result


def _capture_path(manifest_path: Path, capture: str) -> Path:
    candidate = (manifest_path.parent / capture).resolve()
    try:
        candidate.relative_to(manifest_path.parent.resolve())
    except ValueError as exc:
        raise GateError("source capture must remain inside the release packet") from exc
    return candidate


def _validate_review(
    *, slug: str, field: str, baseline_value: str | None, proposed_value: str | None,
    review: dict[str, Any], manifest_path: Path, proposed_html: str,
) -> None:
    if review.get("proposed_value") != proposed_value:
        raise GateError(f"{slug}.{field}: proposed_value does not bind rendered output")
    if "baseline_value" in review and review["baseline_value"] != baseline_value:
        raise GateError(f"{slug}.{field}: baseline_value does not bind captured live output")
    source = review.get("source")
    if not isinstance(source, dict):
        raise GateError(f"{slug}.{field}: source capture binding is required")
    if not isinstance(source.get("url"), str) or not source["url"].startswith("https://"):
        raise GateError(f"{slug}.{field}: source URL must be https")
    if not isinstance(source.get("capture"), str):
        raise GateError(f"{slug}.{field}: source capture path is required")
    capture_path = _capture_path(manifest_path, source["capture"])
    if not capture_path.is_file():
        raise GateError(f"{slug}.{field}: source capture is missing")
    if sha256_file(capture_path) != _require_hash(source.get("sha256"), f"{slug}.{field} source capture sha256"):
        raise GateError(f"{slug}.{field}: source capture sha256 does not match")
    if not isinstance(source.get("excerpt"), str) or not source["excerpt"].strip():
        raise GateError(f"{slug}.{field}: source excerpt is required")
    if _normalized_text(source["excerpt"]) not in _normalized_text(capture_path.read_text(encoding="utf-8")):
        raise GateError(f"{slug}.{field}: source excerpt does not bind captured source text")
    if not isinstance(review.get("author"), str) or not review["author"].strip():
        raise GateError(f"{slug}.{field}: review author is required")
    independent = review.get("independent_review")
    if not isinstance(independent, dict):
        raise GateError(f"{slug}.{field}: independent_review is required")
    reviewer = independent.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise GateError(f"{slug}.{field}: independent reviewer identity is required")
    if reviewer.strip() == review["author"].strip():
        raise GateError(f"{slug}.{field}: independent reviewer must differ from author")
    outcome = independent.get("outcome")
    if outcome not in {"accepted", "historical"}:
        raise GateError(f"{slug}.{field}: independent review outcome {outcome!r} is not publishable")
    reviewed_at = independent.get("reviewed_at")
    if not isinstance(reviewed_at, str):
        raise GateError(f"{slug}.{field}: independent review date is required")
    try:
        review_time = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GateError(f"{slug}.{field}: independent review date must be ISO-8601") from exc
    if review_time.tzinfo is None or review_time.utcoffset() is None:
        raise GateError(f"{slug}.{field}: independent review date must include timezone")
    status = review.get("edition_or_status")
    if status not in {"current", "planned", "historical"}:
        raise GateError(f"{slug}.{field}: edition_or_status {status!r} is not publishable")
    if status == "historical":
        historical_label = review.get("historical_label")
        if (outcome != "historical" or not isinstance(historical_label, str)
                or not historical_label.strip()
                or historical_label.casefold() not in _text(proposed_html).casefold()):
            raise GateError(f"{slug}.{field}: historical source requires historical rendered labeling")
    elif outcome != "accepted":
        raise GateError(f"{slug}.{field}: only accepted review may present a current/planned fact")

    if field in {"distance", "elevation", "course"} and proposed_value is not None:
        variant = review.get("course_variant")
        if not isinstance(variant, str) or not variant.strip():
            raise GateError(f"{slug}.{field}: course_variant is required")
    if field in {"distance", "elevation"} and proposed_value is not None:
        pair = review.get("course_pair")
        if not isinstance(pair, dict) or pair.get(field) != proposed_value:
            raise GateError(f"{slug}.{field}: course_pair must bind the selected {field}")
    if field == "elevation" and proposed_value is None:
        if not isinstance(review.get("suppression_reason"), str) or not review["suppression_reason"].strip():
            raise GateError(f"{slug}.{field}: suppressed elevation requires suppression_reason")


def _validate_pair_consistency(
    slug: str, reviews: dict[str, dict[str, Any]],
    changed: dict[str, tuple[str | None, str | None]], proposed_facts: dict[str, str],
) -> None:
    """Bind any changed course vital to the complete *rendered* vital pair.

    A distance-only edit can still leave a mismatched displayed elevation, so a
    pair is required even when elevation itself did not change.
    """
    paired_fields = [field for field in ("distance", "elevation") if field in changed and changed[field][1] is not None]
    for field in paired_fields:
        pair = reviews[field].get("course_pair")
        if not isinstance(pair, dict):
            raise GateError(f"{slug}.{field}: course_pair is required")
        for vital in ("distance", "elevation"):
            if vital in proposed_facts and pair.get(vital) != proposed_facts[vital]:
                raise GateError(f"{slug}.{field}: course_pair does not bind rendered {vital}")
    if len(paired_fields) > 1:
        variants = {reviews[field].get("course_variant") for field in paired_fields}
        pairs = {json.dumps(reviews[field].get("course_pair"), sort_keys=True) for field in paired_fields}
        if len(variants) != 1 or len(pairs) != 1:
            raise GateError(f"{slug}: changed distance/elevation reviews must share one course_variant and course_pair")


def validate_release(proposed_dir: str | Path, live_baseline_dir: str | Path, manifest_path: str | Path) -> GateReport:
    """Validate the exact offline prep-kit payload before any upload.

    The proposed-file inventory must equal the manifest. Existing pages require
    a captured-live counterpart; a missing file is never interpreted as a live
    404. New pages require an explicit ``baseline.kind: new_page`` designation.
    """
    proposed_dir = Path(proposed_dir)
    live_baseline_dir = Path(live_baseline_dir)
    manifest_path = Path(manifest_path)
    if not proposed_dir.is_dir():
        raise GateError(f"proposed prep-kit directory not found: {proposed_dir}")
    if not live_baseline_dir.is_dir():
        raise GateError(f"captured live baseline directory not found: {live_baseline_dir}")
    if not manifest_path.is_file():
        raise GateError(f"release manifest not found: {manifest_path}")
    document = _read_manifest(manifest_path)
    entries = _page_entries(document)
    proposed = {path.stem: path for path in proposed_dir.glob("*.html")}
    if set(proposed) != set(entries):
        missing = sorted(set(entries) - set(proposed))
        extra = sorted(set(proposed) - set(entries))
        raise GateError(f"proposed inventory must equal manifest (missing={missing}, extra={extra})")

    changed_facts: list[tuple[str, str]] = []
    new_pages: list[str] = []
    for slug in sorted(proposed):
        page = proposed[slug]
        entry = entries[slug]
        if sha256_file(page) != _require_hash(entry.get("proposed_sha256"), f"{slug}.proposed_sha256"):
            raise GateError(f"{slug}: proposed_sha256 does not match exact proposed bytes")
        baseline = entry.get("baseline")
        if not isinstance(baseline, dict):
            raise GateError(f"{slug}: baseline declaration is required")
        kind = baseline.get("kind")
        if kind not in {"captured_live", "new_page"}:
            raise GateError(f"{slug}: baseline.kind must be captured_live or new_page")
        proposed_html = page.read_text(encoding="utf-8")
        proposed_facts = extract_rendered_facts(proposed_html)
        if kind == "captured_live":
            baseline_file = live_baseline_dir / f"{slug}.html"
            if not baseline_file.is_file():
                raise GateError(f"{slug}: captured live baseline is missing; declare a reviewed new_page instead")
            if sha256_file(baseline_file) != _require_hash(baseline.get("sha256"), f"{slug}.baseline.sha256"):
                raise GateError(f"{slug}: baseline sha256 does not match captured live bytes")
            baseline_facts = extract_rendered_facts(baseline_file.read_text(encoding="utf-8"))
        else:
            if (live_baseline_dir / f"{slug}.html").exists():
                raise GateError(f"{slug}: new_page designation conflicts with a captured live baseline")
            baseline_facts = {}
            new_pages.append(slug)

        changed = {
            field: (baseline_facts.get(field), proposed_facts.get(field))
            for field in sorted(set(baseline_facts) | set(proposed_facts))
            if baseline_facts.get(field) != proposed_facts.get(field)
        }
        reviews = _review_entries(entry, slug)
        if set(reviews) != set(changed):
            missing_fields = [f"{slug}.{field}" for field in sorted(set(changed) - set(reviews))]
            extra_fields = [f"{slug}.{field}" for field in sorted(set(reviews) - set(changed))]
            raise GateError(
                f"{slug}: fact reviews must exactly cover rendered changes "
                f"(missing={missing_fields}, extra={extra_fields})"
            )
        for field, (baseline_value, proposed_value) in changed.items():
            _validate_review(
                slug=slug, field=field, baseline_value=baseline_value,
                proposed_value=proposed_value, review=reviews[field],
                manifest_path=manifest_path, proposed_html=proposed_html,
            )
            changed_facts.append((slug, field))
        _validate_pair_consistency(slug, reviews, changed, proposed_facts)
    return GateReport(sorted(proposed), changed_facts, new_pages)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate offline prep-kit rendered-fact release bindings")
    parser.add_argument("--proposed-dir", required=True)
    parser.add_argument("--live-baseline-dir", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        report = validate_release(args.proposed_dir, args.live_baseline_dir, args.manifest)
    except GateError as exc:
        print(f"✗ PREP-KIT FACT GATE: {exc}")
        return 1
    print(f"✓ PREP-KIT FACT GATE: {len(report.proposed_pages)} pages, {len(report.changed_facts)} reviewed factual deltas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
