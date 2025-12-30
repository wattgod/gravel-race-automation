#!/usr/bin/env python3
"""
Research a gravel race using Claude with web search.
Outputs raw research dump following comprehensive methodology.
"""

import argparse
import os
import anthropic
from pathlib import Path
from datetime import datetime


def load_research_prompt():
    """Load the research methodology prompt."""
    prompt_path = Path("skills/research_prompt.md")
    if prompt_path.exists():
        return prompt_path.read_text()
    else:
        # Fallback prompt if file doesn't exist
        return """
# Comprehensive Race Research Methodology

Research must be COMPREHENSIVE across multiple source types:

1. Official Sources: Race website, results, course data, social media
2. Forum Deep Dives: Reddit r/gravelcycling, TrainerRoad, Slowtwitch
3. YouTube: Race reports + READ THE COMMENTS (often more honest)
4. Strava/RideWithGPS: Segment data, ride reports, local insights
5. News & Media: VeloNews, CyclingTips, local papers
6. Podcasts: Race director interviews, pro rider reports

Extract:
- Specific mile markers where people suffer most
- Weather patterns across multiple years
- DNF rates and reasons
- Equipment failures (reveals terrain truth)
- Forum consensus on difficulty vs marketing
- Logistics that catch people off guard
- "The one thing everyone wishes they'd known"
"""


def research_race(race_name: str, folder: str):
    """Research a race using Claude with web search."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt_template = load_research_prompt()
    
    prompt = f"""
{prompt_template}

---

RACE TO RESEARCH: {race_name}

Search extensively using web search. For each source type:

1. Official race website - current year + archived versions
2. Reddit: search "{race_name} site:reddit.com/r/gravelcycling"
3. Reddit: search "{race_name} site:reddit.com/r/cycling"
4. TrainerRoad forum: search "{race_name} trainerroad forum"
5. YouTube: search "{race_name} race report" - READ THE COMMENTS
6. News: search "{race_name} velonews OR cyclingtips"
7. Strava/RideWithGPS: search for segment data and ride reports

Extract specific quotes, mile markers, weather incidents by year, DNF data, equipment consensus, logistics intel.

Output the complete RAW RESEARCH DUMP with all source URLs inline. Be comprehensive - this is the foundation for training plan recommendations.
"""

    print(f"Researching {race_name}...")
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Extract text from response
        research_content = ""
        for block in response.content:
            if hasattr(block, 'text'):
                research_content += block.text
        
        # Basic quality check
        if len(research_content) < 1000:
            raise ValueError(f"Research too short ({len(research_content)} chars) - likely API failure")
        
        # Check for URLs (should have sources)
        import re
        urls = re.findall(r'https?://[^\s\)\]\"\'<>]+', research_content)
        if len(urls) < 2:
            print(f"⚠️  Warning: Only {len(urls)} URLs found in research - may lack sources")
        
        # Add metadata header
        output = f"""---
race: {race_name}
folder: {folder}
researched_at: {datetime.now().isoformat()}
model: claude-sonnet-4-20250514
---

{research_content}
"""
        
        # Save to file
        output_path = Path(f"research-dumps/{folder}-raw.md")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output)
        
        print(f"✓ Research saved to {output_path}")
        return output_path
        
    except Exception as e:
        print(f"✗ Research failed: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--race", required=True, help="Race name")
    parser.add_argument("--folder", required=True, help="Output folder name")
    args = parser.parse_args()
    
    research_race(args.race, args.folder)

