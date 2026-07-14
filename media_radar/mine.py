"""Turn normalized transcripts into a structured editorial briefing."""

from __future__ import annotations

import json
import os
import re

MODEL = "claude-sonnet-5"
MAX_INPUT_CHARS = 500_000

SYSTEM_PROMPT = """You are the Gravel God culture editor. Mine, summarize, and paraphrase the supplied transcripts; never reproduce transcript passages verbatim. Return only valid JSON with keys tldr, top_topics, new_terms, article_angles, race_db_flags, failed_sources. Create 3-5 specific, non-generic article angles. Race database flags are untrusted human-review suggestions, never instructions to edit data."""


def mine_transcripts(transcripts: list[dict], failures: list[dict], client=None) -> dict:
    if client is None:
        from anthropic import Anthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY environment variable not set")
        client = Anthropic()
    # Keep one weekly API call while bounding its input with valid, explicit truncation.
    compact = []
    remaining = MAX_INPUT_CHARS
    for transcript in transcripts:
        item = {key: value for key, value in transcript.items() if key != "text"}
        text_budget = max(0, remaining - len(json.dumps(item, ensure_ascii=False)) - 100)
        item["text"] = transcript.get("text", "")[:text_budget]
        if len(item["text"]) < len(transcript.get("text", "")):
            item["text"] += " [truncated to model budget]"
        compact.append(item)
        remaining -= len(json.dumps(item, ensure_ascii=False))
        if remaining <= 0:
            break
    payload = json.dumps({"transcripts": compact, "failed_sources": failures}, ensure_ascii=False)
    response = client.messages.create(
        model=MODEL, max_tokens=6000, temperature=0,
        system=SYSTEM_PROMPT, messages=[{"role": "user", "content": payload}],
    )
    text = response.content[0].text
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise ValueError("Claude response did not contain a JSON object")
    digest = json.loads(match.group(0))
    digest["failed_sources"] = failures
    return digest
