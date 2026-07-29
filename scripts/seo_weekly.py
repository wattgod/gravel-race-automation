#!/usr/bin/env python3
"""Deterministic weekly SEO update-candidates collector for Gravel God.

Mines first-party GSC Search Analytics data for the highest-leverage content
updates on gravelgodcycling.com. Unlike the AEO weekly monitor, this
collector makes no LLM calls and is not fail-soft: any API error or
incomplete pull raises, main() reports it and exits 1, and NO artifact is
written (no partials, no silent caps — see docs/specs/seo-weekly-spec.md §1).
"""

from __future__ import annotations

import argparse
import json
import re
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_DIR = PROJECT_ROOT / "data" / "seo"
SCHEMA_VERSION = 1
SCORE_VERSION = 1
SITE_URL = "sc-domain:gravelgodcycling.com"
PAGE_SIZE = 25000
COOLDOWN_DAYS = 21
CANONICAL_HOSTS = {"gravelgodcycling.com", "www.gravelgodcycling.com"}

# Piecewise-linear expected-CTR curve, position -> expected CTR fraction.
_EXPECTED_CTR_ANCHORS = sorted({
    1: 0.28, 2: 0.15, 3: 0.10, 4: 0.075, 5: 0.06, 6: 0.045, 7: 0.035,
    8: 0.03, 9: 0.025, 10: 0.02, 12: 0.02, 20: 0.01,
}.items())

_ACTION_BY_BUCKET = {
    "striking_distance": "improve_ranking",
    "ctr_underperformers": "rewrite_title_meta",
    "decliners": "refresh_content",
    "content_gaps": "create_or_link_content",
}
BUCKET_NAMES = tuple(_ACTION_BY_BUCKET)
REQUIRED_KEYS = (
    "schema_version", "score_version", "generated_at_utc", "site",
    "data_boundary", "current_window", "prior_window", "overall",
    "pulls", "noncanonical", "cooldown_excluded", "buckets", "top_candidates",
)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def get_gsc_service():
    """Build GSC API service from GOOGLE_APPLICATION_CREDENTIALS (gsc_tracker.py parity)."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS not set")

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    return build("searchconsole", "v1", credentials=creds)


def expected_ctr(position: float) -> float:
    """Piecewise-linear interpolation over the anchor table; clamped at the ends."""
    positions = [p for p, _ in _EXPECTED_CTR_ANCHORS]
    values = [v for _, v in _EXPECTED_CTR_ANCHORS]
    if position <= positions[0]:
        return values[0]
    if position >= positions[-1]:
        return values[-1]
    for i in range(len(positions) - 1):
        lo_p, hi_p = positions[i], positions[i + 1]
        if lo_p <= position <= hi_p:
            lo_v, hi_v = values[i], values[i + 1]
            fraction = (position - lo_p) / (hi_p - lo_p)
            return lo_v + fraction * (hi_v - lo_v)
    return values[-1]


def normalize_page_url(raw_url: str) -> tuple[str | None, str | None]:
    """Return (canonical_path, None) or (None, noncanonical_host_key)."""
    parts = urlsplit(raw_url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in CANONICAL_HOSTS:
        return None, f"{parts.scheme}://{host}"
    path = parts.path or "/"
    if path != "/" and not path.endswith("/"):
        path += "/"
    return path, None


def _paginated_query(
        service, site_url: str, start: str, end: str,
        dimensions: list[str]) -> tuple[list[dict], int]:
    """Loop startRow += 25000 until a short page; return (rows, request_count)."""
    rows: list[dict] = []
    requests = 0
    start_row = 0
    while True:
        resp = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start,
                "endDate": end,
                "dimensions": list(dimensions),
                "rowLimit": PAGE_SIZE,
                "startRow": start_row,
            },
        ).execute()
        requests += 1
        page = resp.get("rows") or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        start_row += PAGE_SIZE
    return rows, requests


def probe_data_boundary(service, run_date: date) -> date:
    """Pull dimensions=['date'] for the last 14 days; boundary = max date present."""
    start = (run_date - timedelta(days=13)).isoformat()
    end = run_date.isoformat()
    rows, _ = _paginated_query(service, SITE_URL, start, end, ["date"])
    dates = [r["keys"][0] for r in rows if r.get("keys")]
    if not dates:
        raise RuntimeError("date-boundary probe returned no rows")
    return date.fromisoformat(max(dates))


def compute_windows(boundary: date) -> tuple[dict[str, str], dict[str, str]]:
    current = {
        "start": (boundary - timedelta(days=27)).isoformat(),
        "end": boundary.isoformat(),
    }
    prior = {
        "start": (boundary - timedelta(days=55)).isoformat(),
        "end": (boundary - timedelta(days=28)).isoformat(),
    }
    return current, prior


def _overall_metrics(raw_rows: list[dict]) -> dict[str, Any]:
    if not raw_rows:
        return {"clicks": 0, "impressions": 0, "ctr": 0.0, "position": 0.0}
    row = raw_rows[0]
    return {
        "clicks": int(row.get("clicks", 0) or 0),
        "impressions": int(row.get("impressions", 0) or 0),
        "ctr": float(row.get("ctr", 0.0) or 0.0),
        "position": float(row.get("position", 0.0) or 0.0),
    }


def _rows_query(raw_rows: list[dict]) -> list[dict]:
    return [
        {
            "query": row["keys"][0],
            "clicks": int(row.get("clicks", 0) or 0),
            "impressions": int(row.get("impressions", 0) or 0),
            "ctr": float(row.get("ctr", 0.0) or 0.0),
            "position": float(row.get("position", 0.0) or 0.0),
        }
        for row in raw_rows
    ]


def _rows_query_page(raw_rows: list[dict], noncanonical: dict[str, int]) -> list[dict]:
    out = []
    for row in raw_rows:
        query, page_url = row["keys"]
        path, host_key = normalize_page_url(page_url)
        if path is None:
            noncanonical[host_key] = noncanonical.get(host_key, 0) + 1
            continue
        out.append({
            "query": query,
            "page": path,
            "clicks": int(row.get("clicks", 0) or 0),
            "impressions": int(row.get("impressions", 0) or 0),
            "ctr": float(row.get("ctr", 0.0) or 0.0),
            "position": float(row.get("position", 0.0) or 0.0),
        })
    return out


def _rows_page(raw_rows: list[dict], noncanonical: dict[str, int]) -> list[dict]:
    out = []
    for row in raw_rows:
        page_url = row["keys"][0]
        path, host_key = normalize_page_url(page_url)
        if path is None:
            noncanonical[host_key] = noncanonical.get(host_key, 0) + 1
            continue
        out.append({
            "page": path,
            "clicks": int(row.get("clicks", 0) or 0),
            "impressions": int(row.get("impressions", 0) or 0),
            "ctr": float(row.get("ctr", 0.0) or 0.0),
            "position": float(row.get("position", 0.0) or 0.0),
        })
    return out


def _recommended_target_path(query: str) -> str:
    slug = _SLUG_RE.sub("-", query.lower()).strip("-")
    return f"/articles/{slug or 'topic'}/"


def _sort_bucket(entries: list[dict]) -> list[dict]:
    return sorted(
        entries,
        key=lambda e: (
            -e["score"], -e["impressions"], e.get("page") or e.get("query") or ""),
    )


def build_buckets(
        *, current_qp: list[dict], prior_qp: list[dict],
        current_page: list[dict], prior_page: list[dict],
        current_query: list[dict]) -> dict[str, list[dict]]:
    """Build the four candidate buckets from normalized, floored rows."""
    prior_qp_index = {(row["query"], row["page"]): row for row in prior_qp}
    prior_page_index = {row["page"]: row for row in prior_page}
    current_qp_by_query: dict[str, list[dict]] = {}
    for row in current_qp:
        current_qp_by_query.setdefault(row["query"], []).append(row)

    striking_distance = []
    ctr_underperformers = []
    for row in current_qp:
        query, page = row["query"], row["page"]
        position, impressions, ctr, clicks = (
            row["position"], row["impressions"], row["ctr"], row["clicks"])
        prior_row = prior_qp_index.get((query, page))

        if 4 <= position <= 20 and impressions >= 30:
            target_pos = 3 if position <= 10 else 8
            exp = expected_ctr(target_pos)
            score = impressions * max(0.0, exp - ctr)
            entry = {
                "page": page, "query": query,
                "clicks": clicks, "impressions": impressions,
                "ctr": ctr, "position": position,
                "score": score,
                "reason": (
                    f"'{query}' ranks {position:.1f} on {page} with "
                    f"{impressions} impressions/28d — pushing to top "
                    f"{target_pos} could add ~{score:.0f} clicks."
                ),
            }
            if prior_row:
                entry["prior"] = {
                    key: prior_row[key]
                    for key in ("clicks", "impressions", "ctr", "position")
                }
            striking_distance.append(entry)

        if position <= 12 and impressions >= 50 and ctr < 0.4 * expected_ctr(position):
            exp = expected_ctr(position)
            score = impressions * (exp - ctr)
            entry = {
                "page": page, "query": query,
                "clicks": clicks, "impressions": impressions,
                "ctr": ctr, "position": position,
                "score": score,
                "reason": (
                    f"'{query}' on {page} gets {ctr * 100:.1f}% CTR at position "
                    f"{position:.1f}, well below the {exp * 100:.1f}% expected "
                    "— rewrite title/meta."
                ),
            }
            if prior_row:
                entry["prior"] = {
                    key: prior_row[key]
                    for key in ("clicks", "impressions", "ctr", "position")
                }
            ctr_underperformers.append(entry)

    decliners = []
    for row in current_page:
        page = row["page"]
        prior_row = prior_page_index.get(page)
        if not prior_row:
            continue
        clicks, impressions, position = row["clicks"], row["impressions"], row["position"]
        prior_clicks = prior_row["clicks"]
        prior_impressions = prior_row["impressions"]
        prior_position = prior_row["position"]

        clicks_dropped = (
            prior_clicks >= 10
            and (prior_clicks - clicks) / prior_clicks >= 0.4
        )
        position_worsened = (
            impressions >= 50 and prior_impressions >= 50
            and (position - prior_position) >= 3.0
        )
        if clicks_dropped or position_worsened:
            score = float(max(0, prior_clicks - clicks))
            decline_detail = (
                f", position worsened {prior_position:.1f} → {position:.1f}"
                if position_worsened else ""
            )
            decliners.append({
                "page": page, "query": None,
                "clicks": clicks, "impressions": impressions,
                "ctr": row["ctr"], "position": position,
                "prior": {
                    "clicks": prior_clicks, "impressions": prior_impressions,
                    "ctr": prior_row["ctr"], "position": prior_position,
                },
                "score": score,
                "reason": (
                    f"{page} clicks fell from {prior_clicks} to {clicks}"
                    f"{decline_detail} — refresh content."
                ),
            })

    content_gaps = []
    for row in current_query:
        query = row["query"]
        impressions = row["impressions"]
        if impressions < 50:
            continue
        matches = current_qp_by_query.get(query, [])
        best_page = None
        if matches:
            best_page = min(matches, key=lambda r: r["position"])["page"]
        if best_page in (None, "/", "/gravel-race-search/"):
            exp = expected_ctr(5)
            score = max(0.0, impressions * exp - row["clicks"])
            content_gaps.append({
                "page": None, "query": query,
                "clicks": row["clicks"], "impressions": impressions,
                "ctr": row["ctr"], "position": row["position"],
                "score": score,
                "recommended_target_path": _recommended_target_path(query),
                "reason": (
                    f"'{query}' gets {impressions} impressions/28d with no "
                    f"dedicated page (best match: {best_page or 'none'}) "
                    "— create or link content."
                ),
            })

    return {
        "striking_distance": _sort_bucket(striking_distance),
        "ctr_underperformers": _sort_bucket(ctr_underperformers),
        "decliners": _sort_bucket(decliners),
        "content_gaps": _sort_bucket(content_gaps),
    }


def _source_hint(target_path: str | None) -> str:
    if not target_path:
        return (
            "no source — propose new content or internal links; "
            "never invent a page silently"
        )
    if target_path.startswith("/race/"):
        return (
            "race-data/<slug>.json → seo.title/seo.description "
            "(+ profile fields for content); regenerate, preflight, deploy"
        )
    if target_path.startswith("/articles/"):
        return (
            "article source generator; regenerate → SCP to the article "
            "path (NOT --sync-blog)"
        )
    return (
        "WP-native/Elementor page — generate_meta_descriptions.py for "
        "meta; Elementor widget for body; flag for manual/JS-API edit, do "
        "not guess"
    )


def _group_key(bucket: str, entry: dict) -> tuple[str, str]:
    if bucket == "content_gaps":
        return ("query", entry["query"])
    return ("page", entry["page"])


def _load_cooldown_pages(
        boundary: date, log_dir: Path) -> tuple[set[str], list[str]]:
    """Parse updates-log.jsonl; missing file = empty. Malformed lines warn, never fail."""
    log_path = log_dir / "updates-log.jsonl"
    pages: set[str] = set()
    warnings: list[str] = []
    if not log_path.exists():
        return pages, warnings
    for line_number, raw_line in enumerate(log_path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if not isinstance(entry, dict):
                raise ValueError("log line is not an object")
            page = entry["page"]
            status = entry.get("status")
            entry_date = date.fromisoformat(entry["date"])
        except Exception as exc:
            warnings.append(
                f"malformed updates-log line {line_number}: "
                f"{type(exc).__name__}: {exc}")
            continue
        if status != "applied":
            continue
        age_days = (boundary - entry_date).days
        if 0 <= age_days < COOLDOWN_DAYS:
            pages.add(page)
    return pages, warnings


def _rank_top_candidates(
        buckets: dict[str, list[dict]],
        cooldown_pages: set[str]) -> tuple[list[dict], list[str]]:
    grouped: dict[tuple[str, str], list[tuple[str, dict]]] = {}
    for bucket_name in BUCKET_NAMES:
        for entry in buckets[bucket_name]:
            key = _group_key(bucket_name, entry)
            grouped.setdefault(key, []).append((bucket_name, entry))

    candidates = []
    for items in grouped.values():
        items_sorted = sorted(items, key=lambda bi: bi[1]["score"], reverse=True)
        rep_bucket, rep_entry = items_sorted[0]
        combined_upside = sum(entry["score"] for _, entry in items)
        supporting_queries = []
        if rep_bucket != "content_gaps":
            others = [
                entry for _, entry in items_sorted[1:]
                if entry is not rep_entry and entry.get("query")
            ]
            others_sorted = sorted(
                others, key=lambda e: e["impressions"], reverse=True)[:5]
            supporting_queries = [
                {
                    "query": e["query"], "clicks": e["clicks"],
                    "impressions": e["impressions"], "ctr": e["ctr"],
                    "position": e["position"],
                }
                for e in others_sorted
            ]
        target_path = (
            rep_entry.get("recommended_target_path")
            if rep_bucket == "content_gaps" else rep_entry.get("page")
        )
        candidate = {
            "bucket": rep_bucket,
            "action": _ACTION_BY_BUCKET[rep_bucket],
            "target_path": target_path,
            "query": rep_entry.get("query"),
            "page": rep_entry.get("page"),
            "source_hint": _source_hint(target_path),
            "reason": rep_entry["reason"],
            "clicks": rep_entry["clicks"],
            "impressions": rep_entry["impressions"],
            "ctr": rep_entry["ctr"],
            "position": rep_entry["position"],
            "score": rep_entry["score"],
            "supporting_queries": supporting_queries,
            "combined_upside": combined_upside,
        }
        if "prior" in rep_entry:
            candidate["prior"] = rep_entry["prior"]
        candidates.append(candidate)

    candidates.sort(
        key=lambda c: (
            -c["score"], -c["impressions"],
            c.get("page") or c.get("target_path") or c.get("query") or ""),
    )

    cooldown_excluded = sorted({
        c["page"] for c in candidates
        if c.get("page") and c["page"] in cooldown_pages
    })
    ranked = [
        c for c in candidates
        if not (c.get("page") and c["page"] in cooldown_pages)
    ][:5]
    for rank, candidate in enumerate(ranked, start=1):
        candidate["rank"] = rank
    return ranked, cooldown_excluded


def collect_weekly(
        now: datetime | None = None,
        service=None,
        output_dir: Path = ARTIFACT_DIR) -> dict[str, Any]:
    """Run every collector eagerly; any error/incomplete pull raises (no fail-soft)."""
    generated = now or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    generated = generated.astimezone(timezone.utc)
    run_date = generated.date()

    svc = service or get_gsc_service()
    boundary = probe_data_boundary(svc, run_date)
    current_window, prior_window = compute_windows(boundary)

    pulls: list[dict[str, Any]] = []
    noncanonical: dict[str, int] = {}

    def pull(dimensions: list[str], window_name: str, window: dict[str, str]) -> list[dict]:
        raw_rows, requests = _paginated_query(
            svc, SITE_URL, window["start"], window["end"], dimensions)
        pulls.append({
            "dimensions": list(dimensions),
            "window": window_name,
            "rows": len(raw_rows),
            "requests": requests,
        })
        return raw_rows

    current_overall_raw = pull([], "current", current_window)
    current_query_raw = pull(["query"], "current", current_window)
    current_qp_raw = pull(["query", "page"], "current", current_window)
    current_page_raw = pull(["page"], "current", current_window)
    prior_overall_raw = pull([], "prior", prior_window)
    prior_query_raw = pull(["query"], "prior", prior_window)
    prior_qp_raw = pull(["query", "page"], "prior", prior_window)
    prior_page_raw = pull(["page"], "prior", prior_window)
    del prior_query_raw  # true per-query prior totals are not consumed downstream

    current_overall = _overall_metrics(current_overall_raw)
    prior_overall = _overall_metrics(prior_overall_raw)

    current_query = _rows_query(current_query_raw)
    current_qp = [
        row for row in _rows_query_page(current_qp_raw, noncanonical)
        if row["impressions"] >= 10
    ]
    current_page = _rows_page(current_page_raw, noncanonical)
    prior_qp = _rows_query_page(prior_qp_raw, noncanonical)
    prior_page = _rows_page(prior_page_raw, noncanonical)

    buckets = build_buckets(
        current_qp=current_qp, prior_qp=prior_qp,
        current_page=current_page, prior_page=prior_page,
        current_query=current_query,
    )

    cooldown_pages, cooldown_warnings = _load_cooldown_pages(boundary, output_dir)
    for warning in cooldown_warnings:
        print(f"warning: {warning}", file=sys.stderr)

    top_candidates, cooldown_excluded = _rank_top_candidates(buckets, cooldown_pages)

    return {
        "schema_version": SCHEMA_VERSION,
        "score_version": SCORE_VERSION,
        "generated_at_utc": generated.isoformat().replace("+00:00", "Z"),
        "site": SITE_URL,
        "data_boundary": boundary.isoformat(),
        "current_window": current_window,
        "prior_window": prior_window,
        "overall": {**current_overall, "prior": prior_overall},
        "pulls": pulls,
        "noncanonical": dict(sorted(noncanonical.items())),
        "cooldown_excluded": cooldown_excluded,
        "buckets": buckets,
        "top_candidates": top_candidates,
    }


def artifact_path(artifact: dict[str, Any], output_dir: Path = ARTIFACT_DIR) -> Path:
    return output_dir / f"seo-weekly-{artifact['data_boundary']}.json"


def write_artifact(artifact: dict[str, Any], output_dir: Path = ARTIFACT_DIR) -> Path:
    path = artifact_path(artifact, output_dir)
    errors = validate_artifact(artifact, path=path)
    if errors:
        raise ValueError("; ".join(errors))
    output_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    return path


def _check_ctr(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= float(value) <= 1.0


def validate_artifact(
        artifact: Any,
        path: Path | None = None,
        require_all_ok: bool = False) -> list[str]:
    """Return contract violations; an empty list means the artifact is valid."""
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["artifact root must be an object"]
    for key in REQUIRED_KEYS:
        if key not in artifact:
            errors.append(f"missing required key: {key}")
    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if artifact.get("score_version") != SCORE_VERSION:
        errors.append(f"score_version must be {SCORE_VERSION}")
    if artifact.get("site") != SITE_URL:
        errors.append(f"site must be {SITE_URL!r}")

    try:
        generated = datetime.fromisoformat(
            str(artifact["generated_at_utc"]).replace("Z", "+00:00"))
        if generated.tzinfo is None:
            errors.append("generated_at_utc must include a timezone")
        else:
            now = datetime.now(timezone.utc)
            if generated > now + timedelta(minutes=5):
                errors.append("generated_at_utc must not be in the future")
    except (KeyError, TypeError, ValueError):
        errors.append("generated_at_utc must be an ISO timestamp")

    boundary = None
    try:
        boundary = date.fromisoformat(str(artifact["data_boundary"]))
    except (KeyError, TypeError, ValueError):
        errors.append("data_boundary must be an ISO date")

    if path is not None and boundary is not None:
        expected_name = f"seo-weekly-{boundary.isoformat()}.json"
        if path.name != expected_name:
            errors.append(f"filename {path.name!r} does not match {expected_name!r}")

    for window_name in ("current_window", "prior_window"):
        window = artifact.get(window_name)
        if not isinstance(window, dict) or set(window) != {"start", "end"}:
            errors.append(f"{window_name} must contain start and end")
            continue
        try:
            date.fromisoformat(window["start"])
            date.fromisoformat(window["end"])
        except (TypeError, ValueError):
            errors.append(f"{window_name} has invalid dates")

    if boundary is not None:
        current_window = artifact.get("current_window") or {}
        prior_window = artifact.get("prior_window") or {}
        expected_current, expected_prior = compute_windows(boundary)
        if current_window != expected_current:
            errors.append("current_window does not match data_boundary")
        if prior_window != expected_prior:
            errors.append("prior_window does not match data_boundary")

    overall = artifact.get("overall")
    if not isinstance(overall, dict):
        errors.append("overall must be an object")
    else:
        for key in ("clicks", "impressions", "ctr", "position"):
            if key not in overall:
                errors.append(f"overall missing {key}")
        if "ctr" in overall and not _check_ctr(overall["ctr"]):
            errors.append("overall.ctr must be a fraction in [0, 1]")
        prior = overall.get("prior")
        if not isinstance(prior, dict):
            errors.append("overall.prior must be an object")
        elif "ctr" in prior and not _check_ctr(prior["ctr"]):
            errors.append("overall.prior.ctr must be a fraction in [0, 1]")

    buckets = artifact.get("buckets")
    if not isinstance(buckets, dict) or set(buckets) != set(BUCKET_NAMES):
        errors.append("buckets must contain exactly the four bucket names")
        buckets = {}
    for bucket_name in BUCKET_NAMES:
        entries = buckets.get(bucket_name, [])
        if not isinstance(entries, list):
            errors.append(f"buckets.{bucket_name} must be a list")
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                errors.append(f"buckets.{bucket_name} contains a non-object entry")
                break
            if "ctr" in entry and not _check_ctr(entry["ctr"]):
                errors.append(f"buckets.{bucket_name} has a ctr outside [0, 1]")
                break
            prior_entry = entry.get("prior")
            if (isinstance(prior_entry, dict) and "ctr" in prior_entry
                    and not _check_ctr(prior_entry["ctr"])):
                errors.append(f"buckets.{bucket_name} has a prior ctr outside [0, 1]")
                break

    top_candidates = artifact.get("top_candidates")
    if not isinstance(top_candidates, list):
        errors.append("top_candidates must be a list")
    else:
        if len(top_candidates) > 5:
            errors.append("top_candidates exceeds 5")
        for candidate in top_candidates:
            if not isinstance(candidate, dict):
                errors.append("top_candidates contains a non-object entry")
                break
            if "ctr" in candidate and not _check_ctr(candidate["ctr"]):
                errors.append("top_candidates has a ctr outside [0, 1]")
                break

    if not isinstance(artifact.get("pulls"), list):
        errors.append("pulls must be a list")
    if not isinstance(artifact.get("noncanonical"), dict):
        errors.append("noncanonical must be an object")
    if not isinstance(artifact.get("cooldown_excluded"), list):
        errors.append("cooldown_excluded must be a list")

    if require_all_ok:
        pulls = artifact.get("pulls")
        if not isinstance(pulls, list) or len(pulls) != 8:
            errors.append("pulls must contain exactly 8 entries")
        else:
            for pull_entry in pulls:
                if not isinstance(pull_entry, dict) or int(pull_entry.get("requests", 0) or 0) < 1:
                    errors.append("every pull must record at least one request")
                    break
    return errors


def _validate_path(path: Path, require_all_ok: bool) -> int:
    try:
        artifact = json.loads(path.read_text())
    except Exception as exc:
        print(f"invalid artifact: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    errors = validate_artifact(artifact, path=path, require_all_ok=require_all_ok)
    if errors:
        for error in errors:
            print(f"invalid artifact: {error}", file=sys.stderr)
        return 1
    print(f"valid artifact: {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--validate-latest", action="store_true",
        help="validate the newest data/seo artifact")
    parser.add_argument(
        "--require-all-ok", action="store_true",
        help="validation also requires all 8 pulls to be structurally complete")
    parser.add_argument(
        "--date", help="override run date (YYYY-MM-DD) for the boundary probe")
    parser.add_argument("--output-dir", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args()

    if args.validate_latest:
        paths = sorted(args.output_dir.glob("seo-weekly-*.json"))
        if not paths:
            print("invalid artifact: no SEO artifacts found", file=sys.stderr)
            return 1
        return _validate_path(paths[-1], args.require_all_ok)

    now = None
    if args.date:
        now = datetime.combine(
            date.fromisoformat(args.date), datetime.min.time(), tzinfo=timezone.utc)

    try:
        artifact = collect_weekly(now=now, output_dir=args.output_dir)
        path = write_artifact(artifact, args.output_dir)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    rel = path.relative_to(PROJECT_ROOT) if path.is_relative_to(PROJECT_ROOT) else path
    print(f"artifact: {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
