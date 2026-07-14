from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from media_radar.digest import render_digest
from media_radar.glossary import append_new_terms
from media_radar.ingest import ingest_sources, normalize_names
from media_radar.store import TranscriptStore


def entry(item_id, days_old=1):
    dt = datetime(2026, 7, 14 - days_old, tzinfo=timezone.utc)
    return {"id": item_id, "yt_videoid": item_id, "title": "Episode", "published_parsed": dt.timetuple()}


def test_ingest_windowing_and_network_is_mocked():
    feed = SimpleNamespace(entries=[entry("new"), entry("old", 10)], bozo=False)
    items, failures = ingest_sources(
        [{"id": "yt", "name": "YT", "type": "youtube", "channel_id": "x"}],
        set(), {}, now=datetime(2026, 7, 14, tzinfo=timezone.utc),
        feed_parser=lambda _: feed, youtube_fetcher=lambda _: "captions",
    )
    assert [item["id"] for item in items] == ["new"]
    assert failures == []


def test_seen_ledger_deduplicates(tmp_path):
    store = TranscriptStore(tmp_path)
    store.save([{"id": "episode-1", "text": "x"}])
    store.save([{"id": "episode-1", "text": "new"}, {"id": "episode-2", "text": "y"}])
    assert store.seen_ids() == {"episode-1", "episode-2"}


def test_name_normalization():
    assert normalize_names("Kegan Swenson won unbound gravel", {"Keegan Swenson": ["Kegan Swenson"], "Unbound Gravel": ["unbound gravel"]}) == "Keegan Swenson won Unbound Gravel"


def test_digest_renders_all_sections_and_manual_warning():
    data = {"tldr": "Week in gravel.", "top_topics": [{"topic": "Mud", "why_it_matters": "Tires.", "sources": ["Bonk"]}], "new_terms": [], "article_angles": [], "race_db_flags": [{"race": "Test", "claim": "New date", "source": "Bonk", "confidence": "low"}], "failed_sources": [{"source": "RSS", "reason": "timeout"}]}
    output = render_digest(data, 2026, 29)
    assert "SUGGESTIONS ONLY" in output and "verify manually" in output
    assert "Sources That Failed" in output and "timeout" in output


def test_glossary_deduplicates_case_insensitively(tmp_path):
    path = tmp_path / "glossary.md"
    terms = [{"term": "Spirit of Gravel", "meaning": "A contested ideal.", "first_seen_source": "Bonk"}]
    assert append_new_terms(path, terms, date(2026, 7, 14)) == ["Spirit of Gravel"]
    assert append_new_terms(path, [{**terms[0], "term": "spirit of gravel"}]) == []
    assert path.read_text().count("## Spirit of Gravel") == 1


def test_all_sources_failed_returns_nonzero(monkeypatch, tmp_path):
    from media_radar import run_weekly
    monkeypatch.setattr(run_weekly, "load_yaml", lambda path: {"sources": [{"id": "x"}]} if path.name == "sources.yaml" else {"entities": {}})
    monkeypatch.setattr(run_weekly, "ingest_sources", lambda *args, **kwargs: ([], [{"source": "x", "reason": "boom"}]))
    with pytest.raises(RuntimeError, match="All Media Radar sources failed"):
        run_weekly.run(dry_run=True, data_dir=tmp_path)
    monkeypatch.setattr(run_weekly, "run", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("All Media Radar sources failed")))
    assert run_weekly.main(["--dry-run"]) == 1
