#!/usr/bin/env python3
"""
Research a gravel race using Perplexity API (sonar-deep-research).

Better web research than Claude, then Claude synthesizes.
"""

import argparse
import requests
import os
from pathlib import Path
from datetime import datetime


def research_race_perplexity(race_name: str, folder: str):
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        raise ValueError("PERPLEXITY_API_KEY not set")
    
    prompt = f"""
Research the {race_name} gravel race comprehensively. I need SPECIFIC, CITED information for a training plan product.

SEARCH AND REPORT ON:

1. OFFICIAL DATA
- Distance, elevation, date, field size, entry cost, cutoffs, aid stations
- Include the official website URL

2. COURSE & TERRAIN  
- Surface types with percentages if available
- Technical sections with mile markers
- Notable climbs (names, gradients, lengths)
- Known problem areas (sand, mud, rock gardens - where specifically)

3. WEATHER HISTORY
- Actual conditions from specific past years (2024, 2023, 2022)
- Temperature ranges, incidents, what went wrong
- Not general climate - specific race day history

4. REDDIT DEEP DIVE
- Search r/gravelcycling, r/cycling, r/Velo for "{race_name}"
- Extract exact quotes with usernames: "quote" - u/username
- Include thread URLs

5. TRAINERROAD FORUM
- Search for {race_name} threads
- Training discussions, race reports, equipment threads
- Include URLs

6. YOUTUBE RACE REPORTS
- Find race report videos
- Note key insights from videos AND comments
- Include video URLs

7. SUFFERING ZONES
- Specific mile markers where people break
- What happens at each location
- Source for each claim

8. DNF DATA
- DNF rates by year if available
- Common reasons people quit
- Where people miss cutoffs

9. EQUIPMENT CONSENSUS
- Tire widths and treads people recommend
- Pressure recommendations
- Gearing debates
- What people wish they'd brought

10. LOGISTICS
- Nearest airport
- Lodging situation (book how far ahead?)
- Parking
- Packet pickup notes
- Local tips

11. "WHAT I WISH I KNEW" QUOTES
- Direct quotes from people who've done it
- The brutal honest insights

OUTPUT REQUIREMENTS:
- Minimum 2000 words
- Include source URLs after each major claim
- Include at least 5 Reddit thread URLs
- Include at least 3 YouTube video URLs
- Exact quotes with attribution, not paraphrases
- Specific mile markers, percentages, numbers - not vague descriptions
"""

    print(f"Researching {race_name} with Perplexity...")
    
    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "sonar-deep-research",  # Their best research model
            "messages": [
                {
                    "role": "system",
                    "content": "You are a thorough researcher. Always include source URLs. Be specific, not generic."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "max_tokens": 8000,
            "temperature": 0.1,  # Low temp for factual research
        },
        timeout=300  # Deep research can take a few minutes
    )
    
    if response.status_code != 200:
        raise Exception(f"Perplexity API error: {response.status_code} - {response.text}")
    
    data = response.json()
    research_content = data["choices"][0]["message"]["content"]
    
    # Add metadata
    output = f"""---
race: {race_name}
folder: {folder}
researched_at: {datetime.now().isoformat()}
model: perplexity/sonar-deep-research
---

# {race_name.upper()} - RAW RESEARCH DUMP

{research_content}
"""
    
    # Save
    output_path = Path(f"research-dumps/{folder}-raw.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output)
    
    word_count = len(research_content.split())
    url_count = research_content.count("http")
    
    print(f"✓ Research saved to {output_path}")
    print(f"  Words: {word_count}")
    print(f"  URLs: ~{url_count}")
    
    # Run quality checks
    try:
        from quality_gates import run_all_quality_checks
        results = run_all_quality_checks(research_content, "research")
        if not results["overall_passed"]:
            print(f"⚠️  Quality issues detected:")
            for name in results["critical_failures"]:
                print(f"   - {name}: {results['checks'][name]}")
    except Exception as e:
        print(f"⚠️  Quality check failed: {e}")
    
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--race", required=True, help="Race name")
    parser.add_argument("--folder", required=True, help="Output folder name")
    args = parser.parse_args()
    
    research_race_perplexity(args.race, args.folder)

