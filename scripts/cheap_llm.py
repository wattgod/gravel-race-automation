#!/usr/bin/env python3
"""
cheap_llm.py — Low-cost model client for high-volume jobs on PUBLIC race data.

Calls OpenRouter's chat completions endpoint. The default model is Inkling 2
Mini, priced at $0.075 input / $0.30 output per million tokens on 2026-11-22.

Use it only for prompts built from public race data (organizer pages, race
profiles). Do not send customer, athlete or purchase data through it.

Environment:
  OPENROUTER_API_KEY   required
  CHEAP_LLM_MODEL      model id (default: thinkingmachines/inkling-2-mini)
  CHEAP_LLM_PROVIDERS  optional comma-separated OpenRouter provider names; when
                       set, only those hosts are used, in that order
  SUPABASE_URL, SUPABASE_SERVICE_KEY   optional; logs cost to gg_api_usage

Usage:
    from cheap_llm import call_cheap_llm
    text = call_cheap_llm(prompt, script="scrape_official_sites")
"""

import json
import os
import time
import urllib.error
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "thinkingmachines/inkling-2-mini"

# USD per million tokens. Used only when OpenRouter does not report the cost.
PRICING = {
    "thinkingmachines/inkling-2-mini": {"input": 0.075, "output": 0.30},
}

RETRY_STATUSES = {408, 429, 500, 502, 503, 504}


class CheapLLMError(RuntimeError):
    """The cheap model call failed or returned nothing usable."""


def model_id() -> str:
    return os.environ.get("CHEAP_LLM_MODEL", "").strip() or DEFAULT_MODEL


def is_configured() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


def build_request_body(prompt: str, model: str, max_tokens: int, json_mode: bool,
                       reasoning_effort: str | None = None) -> dict:
    """The OpenRouter request body. Hosts that keep or train on prompts are excluded.

    Reasoning tokens count toward max_tokens and are billed as output, so a
    structured-output job should pass reasoning_effort="low".
    """
    provider = {"data_collection": "deny"}
    pinned = [p.strip() for p in os.environ.get("CHEAP_LLM_PROVIDERS", "").split(",") if p.strip()]
    if pinned:
        provider["order"] = pinned
        provider["allow_fallbacks"] = False

    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "provider": provider,
        "usage": {"include": True},
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if reasoning_effort:
        body["reasoning"] = {"effort": reasoning_effort}
    return body


def estimate_cost_usd(model: str, usage: dict) -> float | None:
    """Cost of one call: OpenRouter's own figure when present, else the price table."""
    reported = usage.get("cost")
    if isinstance(reported, (int, float)) and not isinstance(reported, bool):
        return float(reported)
    rates = PRICING.get(model)
    if not rates:
        return None
    tokens_in = usage.get("prompt_tokens") or 0
    tokens_out = usage.get("completion_tokens") or 0
    return (tokens_in / 1_000_000) * rates["input"] + (tokens_out / 1_000_000) * rates["output"]


def _log_usage(model: str, usage: dict, script: str) -> None:
    """Best-effort cost log to gg_api_usage, the table the Anthropic calls log to."""
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not supabase_url or not supabase_key:
        return
    cost = estimate_cost_usd(model, usage)
    try:
        payload = json.dumps({
            "provider": "openrouter",
            "model": model,
            "tokens_in": usage.get("prompt_tokens") or 0,
            "tokens_out": usage.get("completion_tokens") or 0,
            "cost_usd": round(cost, 6) if cost is not None else None,
            "script": script,
        }).encode()
        req = urllib.request.Request(
            f"{supabase_url}/rest/v1/gg_api_usage", data=payload, method="POST",
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            })
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:  # logging must never break the job
        print(f"  WARN: cost log failed: {e}")


def _post(body: dict, api_key: str, timeout: int) -> dict:
    req = urllib.request.Request(
        OPENROUTER_URL, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def call_cheap_llm_with_usage(prompt: str, *, script: str, max_tokens: int = 2000,
                              json_mode: bool = True, reasoning_effort: str | None = None,
                              max_retries: int = 3,
                              retry_delay: float = 10.0, timeout: int = 120) -> tuple[str, dict]:
    """Call the cheap model. Returns (text, usage); usage carries model and cost_usd.

    Raises CheapLLMError when the key is missing, the call keeps failing, or
    the reply is empty or cut off.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise CheapLLMError("OPENROUTER_API_KEY environment variable not set")

    model = model_id()
    body = build_request_body(prompt, model, max_tokens, json_mode, reasoning_effort)

    last_error = "no attempt made"
    for attempt in range(max_retries):
        try:
            data = _post(body, api_key, timeout)
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}"
            if e.code not in RETRY_STATUSES:
                raise CheapLLMError(f"OpenRouter refused the request: HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_error = str(e)
        else:
            # OpenRouter reports some upstream failures as HTTP 200 with an error object.
            if data.get("error"):
                last_error = str(data["error"].get("message", data["error"]))
            else:
                choices = data.get("choices") or []
                choice = choices[0] if choices else {}
                text = (choice.get("message") or {}).get("content") or ""
                usage = dict(data.get("usage") or {})
                served = data.get("model") or model
                _log_usage(served, usage, script)
                if choice.get("finish_reason") == "length":
                    raise CheapLLMError(f"Reply was cut off at max_tokens={max_tokens}")
                if not text.strip():
                    raise CheapLLMError("Model returned an empty reply")
                usage["model"] = served
                usage["cost_usd"] = estimate_cost_usd(served, usage)
                return text, usage

        if attempt < max_retries - 1:
            time.sleep(retry_delay * (attempt + 1))

    raise CheapLLMError(f"OpenRouter call failed after {max_retries} attempts: {last_error}")


def call_cheap_llm(prompt: str, *, script: str, **kwargs) -> str:
    """Call the cheap model and return its text."""
    text, _usage = call_cheap_llm_with_usage(prompt, script=script, **kwargs)
    return text
