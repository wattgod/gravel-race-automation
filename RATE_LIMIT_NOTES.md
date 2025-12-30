# Rate Limit Notes

## Issue

The Anthropic API has a rate limit of **30,000 input tokens per minute**. When using `web_search` tool with `max_tokens=8000`, the system calculates that the request would exceed this limit.

## Solutions

### 1. Reduce max_tokens (Implemented)
- Changed from `8000` to `4000` tokens
- This reduces the total token budget calculation

### 2. Shorten Prompt (Implemented)
- Removed full `research_prompt.md` loading
- Using condensed prompt with essential instructions only
- Reduced search query list to key examples

### 3. Wait and Retry
- Add exponential backoff for rate limit errors
- Wait 60+ seconds between requests if hitting limits

### 4. Alternative: Use Claude 3.5 Sonnet
- Different rate limits may apply
- Check current limits: https://docs.claude.com/en/api/rate-limits

### 5. Batch Processing
- Process races in smaller batches
- Add delays between requests in batch workflows

## Current Status

The research script has been optimized:
- ✅ Condensed prompt (removed full research_prompt.md)
- ✅ Reduced max_tokens to 4000
- ✅ Streamlined search instructions

## Testing

Since we're hitting rate limits, test the quality gates on sample files:

```bash
python3 scripts/quality_gates.py \
  --file research-dumps/mid-south-raw.md \
  --type research \
  --strict
```

## For Production

When running in GitHub Actions:
- The rate limit resets per minute
- Batch processing should add delays between races
- Consider processing 1-2 races per minute max

## Next Steps

1. Test with reduced max_tokens after rate limit resets
2. Add retry logic with exponential backoff
3. Consider using Claude 3.5 Sonnet if limits are different
4. Monitor rate limit usage in production

