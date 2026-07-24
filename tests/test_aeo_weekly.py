"""Contract tests for the deterministic weekly AEO monitor."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from scripts import aeo_agents, aeo_weekly, daily_intel


@pytest.mark.parametrize(
    ("bucket", "user_agent"),
    [
        (bucket, user_agent)
        for bucket, user_agents in aeo_agents.USER_AGENT_TAXONOMY.items()
        for user_agent in user_agents
    ],
)
def test_every_taxonomy_user_agent_classifies_to_its_bucket(bucket, user_agent):
    assert aeo_agents.classify_user_agent(
        f"Mozilla/5.0 compatible; {user_agent}/1.0") == bucket


def test_user_agent_classification_is_case_insensitive():
    assert aeo_agents.classify_user_agent("claude-user") == "user_fetch"


def test_unknown_candidate_and_non_ai_suppression():
    assert aeo_agents.is_unknown_candidate("FooBot/1.0")
    assert not aeo_agents.is_unknown_candidate("Googlebot/2.1")
    assert aeo_agents.is_suppressed_non_ai("Googlebot/2.1")


def _tsv_fixture(dates: list[str]) -> str:
    lines = ["SIZE\t12345\t524288000", f"MISSING\t{dates[1]}"]
    for index, day in enumerate(dates):
        if index == 1:
            continue
        lines.extend([
            f"DAY\t{day}\tuser_fetch\t{index + 1}",
            f"DAY\t{day}\tsearch_index\t1",
            f"DAY\t{day}\ttraining_crawl\t2",
            f"STATUS\t{day}\t2xx\t2",
            f"STATUS\t{day}\t3xx\t0",
            f"STATUS\t{day}\t4xx\t{1 if index == 0 else 0}",
            f"STATUS\t{day}\t5xx\t0",
        ])
    lines.extend([
        "PATH\t/race/test?email=secret@example.com\t7",
        "PATH\t/articles/guide.md\t3",
        "UNKNOWN\tFooBot/1.0\t4",
    ])
    return "\n".join(lines)


def test_parse_server_awk_fixture_keeps_status_classes_and_strips_queries():
    dates = aeo_weekly.completed_log_dates(date(2026, 7, 20))
    parsed, candidates = aeo_weekly.parse_server_tsv(_tsv_fixture(dates), dates)

    assert parsed["logs"]["status"] == "ok"
    assert parsed["logs"]["compressed_bytes"] == 12345
    assert parsed["logs"]["missing_log_dates"] == [dates[1]]
    assert parsed["logs"]["status_buckets"]["2xx"] == 12
    assert parsed["logs"]["status_buckets"]["4xx"] == 1
    assert parsed["logs"]["status_buckets"]["2xx"] != 13  # llms.txt 404 stays non-2xx
    assert parsed["top_user_fetch_paths"][0] == {"path": "/race/test", "hits": 7}
    assert "?" not in json.dumps(parsed)
    assert candidates == [{"user_agent": "FooBot/1.0", "count": 4}]


def test_completed_log_dates_exclude_current_day_and_report_missing_dates():
    run_date = date(2026, 7, 20)
    dates = aeo_weekly.completed_log_dates(run_date)

    assert dates == [
        "2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16",
        "2026-07-17", "2026-07-18", "2026-07-19",
    ]
    assert run_date.isoformat() not in dates
    parsed, _ = aeo_weekly.parse_server_tsv(
        "\n".join([
            "SIZE\t0\t524288000",
            *[f"MISSING\t{day}" for day in dates],
        ]),
        dates,
    )
    assert parsed["logs"]["missing_log_dates"] == dates


def test_log_collector_mocks_one_ssh_call_with_timeout(monkeypatch):
    run_date = date(2026, 7, 20)
    dates = aeo_weekly.completed_log_dates(run_date)
    for name, value in {
        "SSH_HOST": "example.test",
        "SSH_USER": "reader",
        "SSH_PORT": "18765",
        "SSH_KEY_PATH": "/tmp/test-key",
    }.items():
        monkeypatch.setenv(name, value)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0, stdout=_tsv_fixture(dates), stderr="")

    monkeypatch.setattr(aeo_weekly.subprocess, "run", fake_run)

    parsed, _ = aeo_weekly.collect_log_analysis("gravelgod", dates)

    assert parsed["logs"]["status"] == "ok"
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[0] == "ssh"
    assert command.count("gravelgodcycling.com") == 1
    assert run_date.isoformat() not in command
    assert kwargs["input"] == aeo_weekly.SERVER_SCRIPT
    assert kwargs["timeout"] == 270


def test_ga4_collector_uses_two_reports_and_filters_sources_in_python(
        monkeypatch):
    class Value:
        def __init__(self, value):
            self.value = str(value)

    def row(source, sessions):
        return SimpleNamespace(
            dimension_values=[Value(source)],
            metric_values=[Value(sessions)],
        )

    class FakeType:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeClient:
        requests = []
        responses = [
            SimpleNamespace(rows=[
                row("chatgpt.com", 8),
                row("google", 100),
                row("new.openai.example", 2),
            ]),
            SimpleNamespace(rows=[
                row("perplexity.ai", 4),
                row("newsletter", 7),
            ]),
        ]

        def run_report(self, request):
            self.__class__.requests.append(request)
            return self.__class__.responses[len(self.__class__.requests) - 1]

    monkeypatch.setenv("GG_GA4_PROPERTY_ID", "properties/123")
    monkeypatch.setattr(
        aeo_weekly,
        "_ga4_dependencies",
        lambda: (FakeClient, FakeType, FakeType, FakeType, FakeType),
    )
    current, prior = aeo_weekly.completed_windows(date(2026, 7, 20))

    result = aeo_weekly.collect_ga4_referrals("gravelgod", current, prior)

    assert result["status"] == "ok"
    assert result["current_window"] == {
        "chatgpt.com": 8, "new.openai.example": 2}
    assert result["prior_window"] == {"perplexity.ai": 4}
    assert result["referral_regex_version"] == 1
    assert len(FakeClient.requests) == 2
    assert all(request.limit == 250 for request in FakeClient.requests)
    assert all(not hasattr(request, "dimension_filter") for request in FakeClient.requests)


def _brand(
        *,
        ga4_sessions: int | None,
        user_fetch: int,
        search_index: int = 2,
        training_crawl: int = 3,
        llms_2xx: int = 4,
        llms_4xx: int = 0,
        paths: list[dict] | None = None,
        ga4_status: str = "ok") -> dict:
    ga4 = {"status": ga4_status}
    if ga4_status == "ok":
        ga4.update({
            "referral_regex_version": 1,
            "referral_regex": aeo_agents.REFERRAL_SOURCE_PATTERN,
            "current_window": {"chatgpt.com": ga4_sessions or 0},
            "prior_window": {},
        })
    return {
        "ga4": ga4,
        "logs": {
            "status": "ok",
            "days": {
                "2026-07-13": {
                    "user_fetch": user_fetch,
                    "search_index": search_index,
                    "training_crawl": training_crawl,
                    "status_buckets": {
                        "2xx": llms_2xx, "3xx": 0, "4xx": llms_4xx, "5xx": 0,
                    },
                },
            },
            "missing_log_dates": [],
            "status_buckets": {
                "2xx": llms_2xx, "3xx": 0, "4xx": llms_4xx, "5xx": 0,
            },
            "compressed_bytes": 100,
        },
        "top_user_fetch_paths": paths or [],
    }


def _artifact(
        generated_date: str,
        *,
        referral: int = 10,
        user_fetch: int = 20,
        unknown: list[dict] | None = None) -> dict:
    return {
        "schema_version": 1,
        "generated_at_utc": f"{generated_date}T10:30:00Z",
        "taxonomy_version": 1,
        "current_window": {"start": "2026-07-13", "end": "2026-07-19"},
        "prior_window": {"start": "2026-07-06", "end": "2026-07-12"},
        "brands": {
            "gravelgod": _brand(
                ga4_sessions=referral,
                user_fetch=user_fetch,
                llms_4xx=1,
                paths=[
                    {"path": "/race/alpha", "hits": 9},
                    {"path": "/race/bravo", "hits": 7},
                    {"path": "/race/charlie", "hits": 5},
                    {"path": "/race/delta", "hits": 3},
                ],
            ),
            "roadie": _brand(
                ga4_sessions=2, user_fetch=4,
                paths=[{"path": "/race/road", "hits": 2}],
            ),
            "xcski": _brand(
                ga4_sessions=None, user_fetch=1, ga4_status="not_configured"),
        },
        "unknown_agent_candidates": unknown or [],
    }


def _write_artifact(directory, artifact):
    directory.mkdir(parents=True, exist_ok=True)
    path = aeo_weekly.artifact_path(artifact, directory)
    path.write_text(json.dumps(artifact))
    return path


def test_artifact_schema_round_trip_and_filename_date_agreement(tmp_path):
    artifact = _artifact("2026-07-20")

    path = aeo_weekly.write_artifact(artifact, tmp_path)
    loaded = json.loads(path.read_text())

    assert path.name == "aeo-weekly-2026-07-20.json"
    assert loaded == artifact
    assert aeo_weekly.validate_artifact(loaded, path=path) == []
    wrong_path = tmp_path / "aeo-weekly-2026-07-21.json"
    assert "does not match" in " ".join(
        aeo_weekly.validate_artifact(loaded, path=wrong_path))


def test_partial_artifact_is_written_and_strict_validation_fails(
        tmp_path, monkeypatch):
    monkeypatch.setattr(
        aeo_weekly, "collect_ga4_referrals",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("GA down")),
    )
    monkeypatch.setattr(
        aeo_weekly, "collect_log_analysis",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("SSH down")),
    )

    artifact = aeo_weekly.collect_weekly(
        datetime(2026, 7, 20, 10, 30, tzinfo=timezone.utc))
    path = aeo_weekly.write_artifact(artifact, tmp_path)

    assert path.exists()
    assert artifact["brands"]["gravelgod"]["ga4"]["status"] == "error"
    assert artifact["brands"]["roadie"]["logs"]["status"] == "error"
    assert aeo_weekly.validate_artifact(artifact, path=path) == []
    assert any(
        "collector not ok" in error
        for error in aeo_weekly.validate_artifact(
            artifact, path=path, require_all_ok=True)
    )


def test_first_run_deltas_are_null_and_render_as_baseline(tmp_path, monkeypatch):
    _write_artifact(tmp_path, _artifact("2026-07-20"))
    monkeypatch.setattr(daily_intel, "AEO_DIR", tmp_path)

    result = daily_intel.collect_aeo(today=date(2026, 7, 21))
    report = daily_intel.render_report({"aeo": result})

    gravel = result["brands"]["gravelgod"]
    assert gravel["ai_referral_delta"] is None
    assert gravel["user_fetch_delta"] is None
    assert report.count("baseline — no prior artifact") >= 2


def test_collect_aeo_computes_deltas_from_two_newest_artifacts(
        tmp_path, monkeypatch):
    _write_artifact(
        tmp_path, _artifact("2026-07-13", referral=7, user_fetch=12))
    _write_artifact(
        tmp_path, _artifact("2026-07-20", referral=10, user_fetch=20))
    monkeypatch.setattr(daily_intel, "AEO_DIR", tmp_path)

    result = daily_intel.collect_aeo(today=date(2026, 7, 21))

    gravel = result["brands"]["gravelgod"]
    assert gravel["ai_referral_delta"] == 3
    assert gravel["ai_referral_delta_text"] == "+3 WoW"
    assert gravel["user_fetch_delta"] == 8
    assert gravel["user_fetch_delta_text"] == "+8 WoW"


def test_stale_artifact_produces_exactly_one_broken_line(
        tmp_path, monkeypatch):
    _write_artifact(tmp_path, _artifact("2026-07-01"))
    monkeypatch.setattr(daily_intel, "AEO_DIR", tmp_path)

    result = daily_intel.collect_aeo(today=date(2026, 7, 20))
    report = daily_intel.render_report({"aeo": result})

    assert result["state"] == "stale"
    assert "## AEO (WEEKLY)" not in report
    assert report.count("AEO weekly artifact stale (19 days)") == 1
    broken = report.split("## BROKEN\n", 1)[1]
    assert broken.count("\n") == 0


def test_corrupt_json_returns_invalid_state_and_never_raises(
        tmp_path, monkeypatch):
    path = tmp_path / "aeo-weekly-2026-07-20.json"
    path.write_text("{not json")
    monkeypatch.setattr(daily_intel, "AEO_DIR", tmp_path)

    result = daily_intel.collect_aeo(today=date(2026, 7, 20))

    assert result["state"] == "invalid"
    assert result["ok"] is False
    assert "AEO weekly artifact invalid" in result["error"]


def test_aeo_render_fixture_snapshot(tmp_path, monkeypatch):
    unknown = [{
        "user_agent": "FooBot/1.0",
        "count": 4,
        "brands": {"gravelgod": 3, "roadie": 1},
    }]
    _write_artifact(
        tmp_path, _artifact("2026-07-20", unknown=unknown))
    monkeypatch.setattr(daily_intel, "AEO_DIR", tmp_path)
    result = daily_intel.collect_aeo(today=date(2026, 7, 21))

    report = daily_intel.render_report({"aeo": result})
    section = report.split("## AEO (WEEKLY)\n", 1)[1].split("\n\n## BROKEN", 1)[0]

    assert section == "\n".join([
        "- completed window: 2026-07-13 through 2026-07-19; AI-referral "
        "sessions are a lower-bound click-through proxy, not proof of citation.",
        "- **Gravel God:** AI-referral 10 (baseline — no prior artifact); "
        "user_fetch 20 (baseline — no prior artifact); search_index 2; "
        "training_crawl 3; llms.txt/.md 2xx 4 (1 non-2xx).",
        "- **Gravel God top fetched paths:** /race/alpha (9), /race/bravo (7), "
        "/race/charlie (5).",
        "- **Roadie Labs:** AI-referral 2 (baseline — no prior artifact); "
        "user_fetch 4 (baseline — no prior artifact); search_index 2; "
        "training_crawl 3; llms.txt/.md 2xx 4.",
        "- **Roadie Labs top fetched paths:** /race/road (2).",
        "- **XC Ski Labs:** AI-referral not configured; user_fetch 1 "
        "(baseline — no prior artifact); search_index 2; training_crawl 3; "
        "llms.txt/.md 2xx 4.",
        "- **XC Ski Labs top fetched paths:** none.",
        "- **Unknown agent candidates (spoofable):** FooBot/1.0 "
        "(4; gravelgod 3, roadie 1).",
    ])
