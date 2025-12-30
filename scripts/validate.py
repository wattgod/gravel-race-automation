#!/usr/bin/env python3
"""
Validate research claims by fetching source URLs and checking content.
"""

import argparse
import re
import requests
import os
import anthropic
from pathlib import Path


def extract_urls(content: str) -> list:
    """Extract all URLs from the research dump."""
    url_pattern = r'https?://[^\s\)\]\"\'<>]+'
    return list(set(re.findall(url_pattern, content)))


def fetch_url_content(url: str) -> str:
    """Fetch and return text content from URL."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (research bot)'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text[:5000]  # First 5000 chars
    except Exception as e:
        return f"FETCH_ERROR: {e}"


def extract_claims(content: str) -> list:
    """Use Claude to extract factual claims with their source URLs."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️  ANTHROPIC_API_KEY not set, skipping validation")
        return []
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Retry logic for rate limits
    import time
    max_retries = 3
    retry_delay = 60
    
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,  # Reduced to avoid rate limits
                messages=[{
                    "role": "user",
                    "content": f"""Extract top 5 factual claims from this research:

{content[:5000]}

Format:
CLAIM: [claim]
SOURCE: [URL]
CHECKABLE: [text to verify]
"""
                }]
            )
            break  # Success
        except anthropic.RateLimitError as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1)
                print(f"⚠️  Rate limit in validation. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                print("⚠️  Rate limit hit in validation after retries. Skipping validation.")
                return []
    
    # Parse claims from response
    claims = []
    text = response.content[0].text
    
    for block in text.split("CLAIM:")[1:]:
        lines = block.strip().split("\n")
        claim = {"claim": lines[0].strip()}
        for line in lines[1:]:
            if line.startswith("SOURCE:"):
                claim["source"] = line.replace("SOURCE:", "").strip()
            elif line.startswith("CHECKABLE:"):
                claim["checkable"] = line.replace("CHECKABLE:", "").strip()
        if "source" in claim:
            claims.append(claim)
    
    return claims[:10]


def validate_claim(claim: dict, source_content: str) -> dict:
    """Check if claim is supported by source content."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{
            "role": "user", 
            "content": f"""Does this source content support this claim?

CLAIM: {claim['claim']}
CHECKABLE TEXT: {claim.get('checkable', 'N/A')}

SOURCE CONTENT:

{source_content[:3000]}

Respond with exactly one of:

[VERIFIED] - Source explicitly supports this
[PARTIAL] - Source partially supports this
[UNVERIFIED] - Source doesn't mention this
[CONFLICTING] - Source contradicts this

Then one sentence explanation.
"""
        }]
    )
    
    result = response.content[0].text
    claim["validation"] = result
    claim["status"] = result.split("]")[0].replace("[", "") if "]" in result else "UNKNOWN"
    return claim


def validate_research(input_path: str):
    """Validate research claims."""
    content = Path(input_path).read_text()
    
    print(f"Extracting claims from {input_path}...")
    claims = extract_claims(content)
    
    if not claims:
        print("⚠️  No claims extracted, skipping validation")
        return 0, []
    
    print(f"Found {len(claims)} claims to validate")
    
    results = []
    verified_count = 0
    
    for i, claim in enumerate(claims):
        print(f"Validating claim {i+1}/{len(claims)}...")
        
        if "source" in claim and claim["source"].startswith("http"):
            source_content = fetch_url_content(claim["source"])
            validated = validate_claim(claim, source_content)
        else:
            validated = claim
            validated["status"] = "NO_SOURCE"
            validated["validation"] = "No valid source URL provided"
        
        results.append(validated)
        if validated["status"] == "VERIFIED":
            verified_count += 1
    
    # Calculate score
    score = (verified_count / len(claims)) * 100 if claims else 0
    
    print(f"\n{'='*50}")
    print(f"VALIDATION SCORE: {score:.0f}% ({verified_count}/{len(claims)} verified)")
    print(f"{'='*50}\n")
    
    for r in results:
        status_icon = {"VERIFIED": "✓", "PARTIAL": "~", "UNVERIFIED": "?", "CONFLICTING": "✗"}.get(r["status"], "?")
        print(f"{status_icon} [{r['status']}] {r['claim'][:60]}...")
    
    # Warn if score too low
    if score < 60:
        print(f"\n⚠️  Validation score {score:.0f}% is below 60% threshold")
        print("Consider re-running research or manual review")
    
    return score, results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to research dump")
    args = parser.parse_args()
    
    validate_research(args.input)

