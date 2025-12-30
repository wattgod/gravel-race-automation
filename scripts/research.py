#!/usr/bin/env python3
"""
Research a gravel race using Claude with web search.
Outputs raw research dump following comprehensive methodology.
"""

import argparse
import os
import time
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


def get_search_queries(race_name: str) -> dict:
    """Generate comprehensive search queries for diverse sources."""
    from datetime import datetime
    
    current_year = datetime.now().year
    last_year = current_year - 1
    
    return {
        "official": [
            f"{race_name} official site",
            f"{race_name} rider guide pdf",
            f"{race_name} course map",
            f"{race_name} official website",
        ],
        "forums": [
            f"{race_name} site:reddit.com/r/gravelcycling",
            f"{race_name} site:reddit.com/r/cycling",
            f"{race_name} site:reddit.com/r/Velo",
            f"{race_name} site:trainerroad.com/forum",
            f"{race_name} site:forum.slowtwitch.com",
            f"{race_name} site:ridinggravel.com",
        ],
        "race_reports": [
            f"{race_name} race report blog",
            f"{race_name} race report site:rodeo-labs.com",
            f"{race_name} race report site:nofcksgivengravel.com",
            f"{race_name} race report site:sage.bike",
            f"{race_name} race recap {current_year}",
            f"{race_name} race recap {last_year}",
        ],
        "media": [
            f"{race_name} site:velonews.com",
            f"{race_name} site:cyclingtips.com",
            f"{race_name} site:cyclingweekly.com",
            f"{race_name} site:bikeradar.com",
            f"{race_name} site:escapecollective.com",
        ],
        "video": [
            f"{race_name} race report youtube",
            f"{race_name} {current_year} youtube",
            f"{race_name} POV gopro",
            f"{race_name} race video",
        ],
        "data": [
            f"{race_name} results {current_year}",
            f"{race_name} results {last_year}",
            f"{race_name} strava segment",
            f"{race_name} DNF rate",
            f"{race_name} finish times",
            f"{race_name} results athlinks",
            f"{race_name} results runsignup",
            f"{race_name} results bikereg",
        ],
        "weather": [
            f"{race_name} weather history",
            f"{race_name} heat {current_year}",
            f"{race_name} conditions {last_year}",
            f"{race_name} weather {last_year}",
        ],
        "gear": [
            f"{race_name} tire pressure",
            f"{race_name} tire recommendation",
            f"{race_name} bike setup",
            f"{race_name} gear list",
        ],
    }


def get_weather_history(location: str, race_date: str) -> dict:
    """
    Fetch historical weather for race location.
    Uses Open-Meteo historical API (free, no key needed).
    Note: Requires geocoding location to lat/lon first.
    """
    import requests
    from datetime import datetime, timedelta
    
    # This is a placeholder - would need geocoding service
    # For now, return structure for manual data entry
    return {
        "location": location,
        "race_date": race_date,
        "note": "Weather history lookup requires geocoding. Search for historical weather data manually or use weather APIs.",
        "suggested_queries": [
            f"{location} weather history {race_date}",
            f"{location} historical weather data",
            f"weather archive {location}",
        ]
    }


def get_race_results_queries(race_name: str) -> list:
    """Generate search queries for race results/timing data."""
    from datetime import datetime
    
    current_year = datetime.now().year
    last_year = current_year - 1
    
    return [
        f"{race_name} results {current_year}",
        f"{race_name} results {last_year}",
        f"{race_name} results athlinks",
        f"{race_name} results runsignup",
        f"{race_name} results bikereg",
        f"{race_name} official results",
        f"{race_name} DNF rate",
        f"{race_name} finish times",
        f"{race_name} timing results",
    ]


def research_race(race_name: str, folder: str):
    """Research a race using Claude with web search."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    # Enhanced prompt with context about purpose and quality
    prompt = f"""Research the gravel race "{race_name}" for a training plan business.

CONTEXT:
- This becomes a WordPress landing page for cyclists training for this race
- Content must be in "Matti voice" - direct, honest, no marketing fluff
- Target: Serious cyclists who want real intel, not hype
- Research will be synthesized into training recommendations

QUALITY REQUIREMENTS (NO SLOP):
- NO generic phrases: "amazing opportunity", "world-class", "incredible experience"
- NO hedging: "perhaps", "it seems like", "you might want to"
- YES specific details: exact mile markers, actual quotes, real numbers
- YES forum deep dives: Reddit threads with 20+ comments, read YouTube comments
- YES brutal honesty: what actually sucks, where people DNF, equipment failures

REQUIRED SOURCES (use web_search):
1. {race_name} site:reddit.com/r/gravelcycling (REQUIRED - find active threads)
2. {race_name} race report youtube (REQUIRED - read comments, they're more honest)
3. {race_name} site:trainerroad.com/forum
4. {race_name} official site
5. {race_name} results 2024
6. {race_name} weather history

EXTRACT:
- Specific mile markers where people suffer (e.g., "Mile 80-95: Teterville rollers")
- Direct quotes from forum posts (include username: "u/graveldude said...")
- Weather data by year (e.g., "2023: 103°F, 2022: 95°F")
- DNF rates and reasons (from results data)
- Equipment consensus (tire pressure, tire size from multiple sources)
- Logistics gotchas (what catches people off guard)

OUTPUT FORMAT:
## OFFICIAL DATA
## TERRAIN
## WEATHER HISTORY
## REDDIT DEEP DIVE
## SUFFERING ZONES
## DNF DATA
## EQUIPMENT
## LOGISTICS

Include 15-25 URLs total. MUST have Reddit and YouTube sources. Be specific, not generic.
"""

    print(f"Researching {race_name}...")
    
    try:
        # Retry logic for rate limits
        max_retries = 3
        retry_delay = 60  # seconds
        
        for attempt in range(max_retries):
            try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,  # Further reduced to avoid rate limits
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
                break  # Success, exit retry loop
            except anthropic.RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    print(f"⚠️  Rate limit hit. Waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    raise  # Re-raise on final attempt
        
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
        
        # Run quality checks
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from quality_gates import run_all_quality_checks
            
            results = run_all_quality_checks(research_content, "research")
            if not results["overall_passed"]:
                print(f"⚠️  Quality issues detected:")
                for name in results["critical_failures"]:
                    check = results["checks"][name]
                    print(f"   - {name}: {check}")
                # Don't fail, but warn
        except ImportError:
            print("⚠️  Quality gates not available (skipping checks)")
        
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

