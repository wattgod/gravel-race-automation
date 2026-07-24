# AI crawler / fetcher user-agent taxonomy (research basis for aeo_weekly)

Compiled 2026-07-23. Two evidence classes: vendor documentation (the
published UA contracts) and our own server logs (empirical ground truth,
same day).

Vendor docs distinguish THREE uses (sol-review r2 correction): user-triggered
fetch, search indexing, and model-training crawl. The monitor buckets
accordingly.

## user_fetch — retrieval for a live user request (citation-adjacent)

| UA token | Vendor | Meaning | Source |
|---|---|---|---|
| `ChatGPT-User` | OpenAI | Fetch on behalf of a ChatGPT user action | https://platform.openai.com/docs/bots |
| `Claude-User` | Anthropic | Fetch on behalf of a Claude user request | https://docs.anthropic.com/en/docs/agents-and-tools/claude-for-chrome (see also support: "Does Anthropic crawl the web") |
| `Perplexity-User` | Perplexity | Fetch on behalf of a Perplexity user | https://docs.perplexity.ai/guides/bots |

## search_index — search/link-display indexing

| UA token | Vendor | Source |
|---|---|---|
| `OAI-SearchBot` | OpenAI | https://platform.openai.com/docs/bots |
| `Claude-SearchBot` | Anthropic | Anthropic support / robots docs |
| `PerplexityBot` | Perplexity | https://docs.perplexity.ai/guides/bots |

## training_crawl — model-training crawlers

| UA token | Vendor | Source |
|---|---|---|
| `GPTBot` | OpenAI (training) | https://platform.openai.com/docs/gptbot |
| `ClaudeBot` | Anthropic (training) | Anthropic robots docs |
| `meta-externalagent` | Meta (AI training) | https://developers.facebook.com/docs/sharing/webmasters/web-crawlers/ |
| `Amazonbot` | Amazon (incl. Alexa/AI) | https://developer.amazon.com/amazonbot |
| `Bytespider` | ByteDance | (no formal docs; widely observed) |
| `cohere-ai` | Cohere | (observed convention) |

Vendor docs are the contract for the token STRINGS; match case-insensitively
because logs show mixed casing (empirical: both `Claude-User` and
`claude-user` in the same GG log day).

`Google-Extended` is deliberately ABSENT from log matching: it is a
robots.txt product token, not an HTTP User-Agent (Google crawler docs).
Gemini-related fetch agents get added via collector-3 discovery once
observed in our logs — no speculative names.

## Empirical evidence (2026-07-23, our servers)

One-day access log greps, SiteGround daily-rotated
`~/www/<domain>/logs/<domain>-YYYY-MM-DD.gz`:

- gravelgodcycling.com (2026-07-22 file): **132 ChatGPT-User, 29
  Claude-User (mixed case), 5 OAI-SearchBot, 17 other anthropic-token
  hits; 432 requests to /llms.txt or .md paths.**
- roadielabs.com (2026-07-23 file): 13 AI-agent hits.
- xcskilabs.com (2026-07-23 file): 4 AI-agent hits.

Implication: answer-fetch traffic (already ~150+/day on GG) is a direct,
deterministic, zero-cost measurement of AI engines retrieving our content
for user answers — strictly better as a phase-1 signal than fragile
browser-automation citation checks. Click-throughs from those answers land
in GA4 as referrals (chatgpt.com / perplexity.ai / etc.), which collector 1
counts.

## Maintenance

`scripts/aeo_agents.py` is the single source of truth for both lists.
Collector 3 surfaces unknown bot-like UAs from our own logs, which is how
new vendors get discovered and added — no speculative weekly web research.
