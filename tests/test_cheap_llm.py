"""Tests for cheap_llm.py and the extractor switch in scrape_utils.py. No network."""

import io
import json
import urllib.error
from unittest.mock import patch

import pytest

import cheap_llm
import scrape_utils
from cheap_llm import (
    CheapLLMError,
    build_request_body,
    call_cheap_llm,
    call_cheap_llm_with_usage,
    estimate_cost_usd,
)


def _reply(text='{"distance_mi": 100}', usage=None, finish="stop", model="thinkingmachines/inkling-2-mini"):
    return {
        "model": model,
        "choices": [{"message": {"content": text}, "finish_reason": finish}],
        "usage": usage if usage is not None else {"prompt_tokens": 10_000, "completion_tokens": 1_000},
    }


def _http_error(code):
    return urllib.error.HTTPError(cheap_llm.OPENROUTER_URL, code, "err", {}, io.BytesIO(b""))


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    for name in ("CHEAP_LLM_MODEL", "CHEAP_LLM_PROVIDERS", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "SCRAPE_EXTRACTOR"):
        monkeypatch.delenv(name, raising=False)


class TestRequestBody:
    def test_excludes_hosts_that_keep_prompts(self):
        body = build_request_body("hi", "m", 100, True)
        assert body["provider"] == {"data_collection": "deny"}
        assert body["response_format"] == {"type": "json_object"}
        assert body["usage"] == {"include": True}

    def test_pinned_providers_disable_fallback(self, monkeypatch):
        monkeypatch.setenv("CHEAP_LLM_PROVIDERS", "Alpha, Beta ,")
        provider = build_request_body("hi", "m", 100, False)["provider"]
        assert provider["order"] == ["Alpha", "Beta"]
        assert provider["allow_fallbacks"] is False

    def test_json_mode_off_omits_response_format(self):
        assert "response_format" not in build_request_body("hi", "m", 100, False)

    def test_reasoning_effort_is_sent_only_when_asked(self):
        assert "reasoning" not in build_request_body("hi", "m", 100, True)
        assert build_request_body("hi", "m", 100, True, "low")["reasoning"] == {"effort": "low"}

    def test_model_env_override(self, monkeypatch):
        assert cheap_llm.model_id() == cheap_llm.DEFAULT_MODEL
        monkeypatch.setenv("CHEAP_LLM_MODEL", "other/model")
        assert cheap_llm.model_id() == "other/model"


class TestCost:
    def test_price_table_matches_listed_rate(self):
        cost = estimate_cost_usd("thinkingmachines/inkling-2-mini",
                                 {"prompt_tokens": 10_000, "completion_tokens": 1_000})
        assert cost == pytest.approx(0.00105)

    def test_reported_cost_wins(self):
        assert estimate_cost_usd("thinkingmachines/inkling-2-mini", {"cost": 0.5, "prompt_tokens": 1}) == 0.5

    def test_unknown_model_without_reported_cost_is_unknown(self):
        assert estimate_cost_usd("nobody/unknown", {"prompt_tokens": 5}) is None


class TestCall:
    def test_missing_key_fails_loudly(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY")
        with pytest.raises(CheapLLMError, match="OPENROUTER_API_KEY"):
            call_cheap_llm("hi", script="t")

    def test_returns_text_and_usage(self):
        with patch.object(cheap_llm, "_post", return_value=_reply()) as post:
            text, usage = call_cheap_llm_with_usage("hi", script="t")
        assert text == '{"distance_mi": 100}'
        assert usage["model"] == "thinkingmachines/inkling-2-mini"
        assert usage["cost_usd"] == pytest.approx(0.00105)
        assert post.call_args[0][1] == "test-key"

    def test_retries_then_succeeds(self):
        with patch.object(cheap_llm, "_post", side_effect=[_http_error(429), _reply()]) as post, \
             patch.object(cheap_llm.time, "sleep") as sleep:
            assert call_cheap_llm("hi", script="t") == '{"distance_mi": 100}'
        assert post.call_count == 2
        sleep.assert_called_once()

    def test_auth_error_is_not_retried(self):
        with patch.object(cheap_llm, "_post", side_effect=_http_error(401)) as post, \
             patch.object(cheap_llm.time, "sleep"):
            with pytest.raises(CheapLLMError, match="401"):
                call_cheap_llm("hi", script="t")
        assert post.call_count == 1

    def test_gives_up_after_max_retries(self):
        with patch.object(cheap_llm, "_post", side_effect=_http_error(503)) as post, \
             patch.object(cheap_llm.time, "sleep"):
            with pytest.raises(CheapLLMError, match="after 3 attempts"):
                call_cheap_llm("hi", script="t")
        assert post.call_count == 3

    def test_error_object_in_200_is_retried(self):
        with patch.object(cheap_llm, "_post", side_effect=[{"error": {"message": "upstream down"}}, _reply()]), \
             patch.object(cheap_llm.time, "sleep"):
            assert call_cheap_llm("hi", script="t")

    def test_truncated_reply_is_an_error(self):
        with patch.object(cheap_llm, "_post", return_value=_reply(finish="length")):
            with pytest.raises(CheapLLMError, match="cut off"):
                call_cheap_llm("hi", script="t")

    def test_empty_reply_is_an_error(self):
        with patch.object(cheap_llm, "_post", return_value=_reply(text="  ")):
            with pytest.raises(CheapLLMError, match="empty"):
                call_cheap_llm("hi", script="t")

    def test_no_cost_log_without_supabase(self):
        with patch.object(cheap_llm, "_post", return_value=_reply()), \
             patch.object(cheap_llm.urllib.request, "urlopen") as urlopen:
            call_cheap_llm("hi", script="t")
        urlopen.assert_not_called()

    def test_cost_log_row(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "https://db.example")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
        with patch.object(cheap_llm, "_post", return_value=_reply()), \
             patch.object(cheap_llm.urllib.request, "urlopen") as urlopen:
            call_cheap_llm("hi", script="scrape_official_sites")
        request = urlopen.call_args[0][0]
        row = json.loads(request.data)
        assert request.full_url == "https://db.example/rest/v1/gg_api_usage"
        assert row == {"provider": "openrouter", "model": "thinkingmachines/inkling-2-mini",
                       "tokens_in": 10_000, "tokens_out": 1_000, "cost_usd": 0.00105,
                       "script": "scrape_official_sites"}

    def test_cost_log_failure_does_not_break_the_call(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "https://db.example")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "svc")
        with patch.object(cheap_llm, "_post", return_value=_reply()), \
             patch.object(cheap_llm.urllib.request, "urlopen", side_effect=OSError("down")):
            assert call_cheap_llm("hi", script="t")


class TestExtractorSwitch:
    def test_default_is_claude(self, monkeypatch):
        assert scrape_utils.default_extractor() == "claude"
        monkeypatch.setenv("SCRAPE_EXTRACTOR", "Inkling")
        assert scrape_utils.default_extractor() == "inkling"
        monkeypatch.setenv("SCRAPE_EXTRACTOR", "gpt")
        assert scrape_utils.default_extractor() == "claude"

    def test_inkling_path_records_model_and_cost(self):
        with patch.object(cheap_llm, "_post", return_value=_reply('```json\n{"distance_mi": 62}\n```')) as post:
            facts = scrape_utils.extract_race_facts("<html>100 km</html>", "Test Fondo", {}, extractor="inkling")
        # Reasoning shares the output cap; the low-effort, 8,000-token setting keeps the JSON from being cut off.
        body = post.call_args[0][0]
        assert body["max_tokens"] == 8000 and body["reasoning"] == {"effort": "low"}
        assert facts == {"distance_mi": 62, "extraction_model": "thinkingmachines/inkling-2-mini",
                         "extraction_cost_usd": pytest.approx(0.00105)}

    def test_claude_path_unchanged(self):
        with patch("youtube_enrich.call_api", return_value='{"distance_mi": 62}') as call_api, \
             patch.object(cheap_llm, "_post") as post:
            facts = scrape_utils.extract_race_facts_via_claude("<html></html>", "Test Fondo")
        call_api.assert_called_once()
        post.assert_not_called()
        assert facts == {"distance_mi": 62, "extraction_model": "claude-sonnet-4-20250514"}

    def test_failure_returns_error_not_facts(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY")
        facts = scrape_utils.extract_race_facts("<html></html>", "Test Fondo", {}, extractor="inkling")
        assert set(facts) == {"error"}

    def test_non_object_reply_is_an_error(self):
        with patch.object(cheap_llm, "_post", return_value=_reply("[1, 2]")):
            facts = scrape_utils.extract_race_facts("<html></html>", "Test Fondo", {}, extractor="inkling")
        assert set(facts) == {"error"}

    def test_empty_object_is_an_error_not_an_extract(self):
        with patch.object(cheap_llm, "_post", return_value=_reply("{}")):
            facts = scrape_utils.extract_race_facts("<html></html>", "Test Fondo", {}, extractor="inkling")
        assert set(facts) == {"error"}

    def test_unknown_extractor(self):
        assert "error" in scrape_utils.extract_race_facts("<html></html>", "x", {}, extractor="gpt")


from scrape_utils import date_is_on_page, extract_race_facts_via_claude


class TestDateIsOnPage:
    def test_numeric_day_first(self):
        assert date_is_on_page("<span>27/06/2027</span>", "2027-06-27")

    def test_numeric_month_first(self):
        assert date_is_on_page("SATURDAY 05/16/2026", "2026-05-16")

    def test_iso(self):
        assert date_is_on_page("starts 2027-03-07", "2027-03-07")

    def test_month_name_then_day(self):
        assert date_is_on_page("Dartmoor Classic on June 20, 2027. Choose", "2027-06-20")

    def test_first_day_of_a_range(self):
        assert date_is_on_page("<h2>Departure on June 5 and 6, 2027</h2>", "2027-06-05")

    def test_second_day_of_a_range(self):
        assert date_is_on_page("<h2>Departure on June 5 and 6, 2027</h2>", "2027-06-06")

    def test_day_then_month_other_language(self):
        assert date_is_on_page("Domenica 16 maggio 2027", "2027-05-16")
        assert date_is_on_page("le 27 juin 2027", "2027-06-27")

    def test_projected_date_is_rejected(self):
        """The page shows 2026's date and mentions 2027 elsewhere; 2027-05-15 is invented."""
        page = 'SATURDAY 05/16/2026 <a href="/percorsi2027.aspx">Routes 2027</a>'
        assert not date_is_on_page(page, "2027-05-15")
        assert date_is_on_page(page, "2026-05-16")

    def test_right_day_wrong_year_is_rejected(self):
        assert not date_is_on_page("June 20, 2026", "2027-06-20")

    def test_day_must_be_whole_number(self):
        assert not date_is_on_page("June 20, 2027", "2027-06-02")

    def test_bad_input(self):
        assert not date_is_on_page("June 20, 2027", "June 20")
        assert not date_is_on_page("", "2027-06-20")
        assert not date_is_on_page("June 20, 2027", None)


class TestUnverifiedDateIsParked:
    def test_invented_date_is_removed_from_the_extract(self):
        from unittest.mock import patch
        with patch("youtube_enrich.call_api", return_value='{"next_edition_date": "2027-05-15"}'):
            facts = extract_race_facts_via_claude("SATURDAY 05/16/2026", "Bra Bra")
        assert facts["next_edition_date"] is None
        assert facts["unverified_date"] == "2027-05-15"

    def test_date_on_page_is_kept(self):
        from unittest.mock import patch
        with patch("youtube_enrich.call_api", return_value='{"next_edition_date": "2027-06-20"}'):
            facts = extract_race_facts_via_claude("Classic on June 20, 2027", "Dartmoor")
        assert facts["next_edition_date"] == "2027-06-20"
        assert "unverified_date" not in facts
