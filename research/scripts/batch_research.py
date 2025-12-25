"""
Batch Research Script

Research races in batches and update database systematically.
Can process zero-competition batches, UCI series, etc.
"""

import json
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

def load_batch_file(batch_path: str) -> Dict:
    """Load a research batch file"""
    with open(batch_path, 'r') as f:
        return json.load(f)

def research_race_basic(race: Dict) -> Dict[str, Any]:
    """
    Basic research for a race.
    Uses common patterns and known information.
    """
    race_name = race.get('race_name', '')
    location = race.get('location', '')
    
    findings = {
        'website_url': '',
        'registration_url': '',
        'date_2026': race.get('research_fields', {}).get('date_2026', ''),
        'field_size': race.get('research_fields', {}).get('field_size', ''),
        'entry_cost': race.get('research_fields', {}).get('entry_cost', ''),
        'sources': []
    }
    
    # Try to infer website from race name and location
    # Common patterns: racename.com, racenamegravel.com, etc.
    race_slug = race_name.lower().replace(' ', '').replace("'", "").replace('-', '')
    location_slug = location.split(',')[0].lower().replace(' ', '')
    
    # Common website patterns
    possible_urls = [
        f"https://www.{race_slug}.com",
        f"https://www.{race_slug}gravel.com",
        f"https://www.{race_slug}race.com",
        f"https://{race_slug}.com",
    ]
    
    # Add to findings (will need manual verification)
    findings['possible_urls'] = possible_urls
    findings['research_notes'] = [
        f"Check official website patterns for {race_name}",
        f"Search BikeReg for {race_name}",
        f"Check GravelHive for {race_name}",
        f"Search Gravelevents.com for {race_name}",
    ]
    
    return findings

def process_batch(batch_path: str, update_database: bool = False):
    """Process a research batch file"""
    print(f"\nProcessing batch: {batch_path}")
    
    batch_data = load_batch_file(batch_path)
    races = batch_data.get('races', [])
    
    print(f"Found {len(races)} races in batch")
    
    researched = 0
    for race in races:
        race_name = race.get('race_name', '')
        if not race_name:
            continue
        
        # Basic research
        findings = research_race_basic(race)
        
        # Update race research data
        race['research_status'] = 'in_progress'
        race['research_date'] = datetime.now().isoformat()
        race['research_fields'].update({
            'possible_urls': findings.get('possible_urls', []),
            'research_notes': findings.get('research_notes', [])
        })
        
        researched += 1
    
    # Save updated batch
    with open(batch_path, 'w') as f:
        json.dump(batch_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Researched {researched} races")
    print(f"  Saved to: {batch_path}")
    
    return researched

def main():
    """Process all research batches"""
    print("Starting batch research...")
    
    # Process zero-competition batches
    zero_comp_batches = [
        'research/by_protocol/zero_competition_batch_1.json',
        'research/by_protocol/zero_competition_batch_2.json',
        'research/by_protocol/zero_competition_batch_3.json',
        'research/by_protocol/zero_competition_batch_4.json',
        'research/by_protocol/zero_competition_batch_5.json',
        'research/by_protocol/zero_competition_batch_6.json',
    ]
    
    total_researched = 0
    for batch_path in zero_comp_batches:
        if Path(batch_path).exists():
            researched = process_batch(batch_path)
            total_researched += researched
    
    # Process UCI series
    uci_batch = 'research/uci_series/uci_gravel_world_series.json'
    if Path(uci_batch).exists():
        researched = process_batch(uci_batch)
        total_researched += researched
    
    print(f"\n✓ Batch research complete")
    print(f"  Total races researched: {total_researched}")
    print(f"\nNext steps:")
    print(f"  1. Verify possible URLs manually")
    print(f"  2. Search BikeReg, GravelHive for each race")
    print(f"  3. Update research files with confirmed data")
    print(f"  4. Run update_database_from_research.py")

if __name__ == '__main__':
    main()

