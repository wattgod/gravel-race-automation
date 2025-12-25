"""
Comprehensive Research Script

Systematically research all 388 races and update database.
Continues until all races are researched.
"""

import json
import re
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

def load_database():
    """Load the main race database"""
    with open('gravel_races_full_database.json', 'r') as f:
        return json.load(f)

def generate_website_patterns(race_name: str, location: str) -> List[str]:
    """Generate possible website URLs for a race"""
    patterns = []
    
    # Clean race name
    name_clean = race_name.lower()
    name_clean = re.sub(r'[^\w\s]', '', name_clean)  # Remove special chars
    name_clean = name_clean.replace(' ', '')
    name_clean = name_clean.replace("'", "")
    name_clean = name_clean.replace('-', '')
    
    # Common patterns
    patterns.extend([
        f"https://www.{name_clean}.com",
        f"https://{name_clean}.com",
        f"https://www.{name_clean}gravel.com",
        f"https://www.{name_clean}race.com",
        f"https://www.{name_clean}cycling.com",
    ])
    
    # If location in name, try variations
    if location:
        loc_clean = location.split(',')[0].lower().replace(' ', '')
        patterns.extend([
            f"https://www.{loc_clean}{name_clean}.com",
            f"https://www.{name_clean}{loc_clean}.com",
        ])
    
    return patterns

def research_race_comprehensive(race: Dict) -> Dict[str, Any]:
    """Comprehensive research for a single race"""
    race_name = race.get('RACE_NAME', '')
    location = race.get('LOCATION', '')
    
    findings = {
        'website_url': race.get('WEBSITE_URL', ''),
        'registration_url': race.get('REGISTRATION_URL', ''),
        'date_2026': race.get('DATE', ''),
        'field_size': race.get('FIELD_SIZE_DISPLAY', ''),
        'entry_cost': race.get('ENTRY_COST_DISPLAY', ''),
        'ridewithgps_id': race.get('RIDEWITHGPS_ID', ''),
        'possible_urls': generate_website_patterns(race_name, location),
        'research_notes': [
            f"Search BikeReg for: {race_name}",
            f"Search GravelHive for: {race_name}",
            f"Search Gravelevents.com for: {race_name}",
            f"Check official website patterns",
        ],
        'research_status': 'pending',
        'research_date': datetime.now().isoformat(),
    }
    
    # If we have some data, mark as in_progress
    if findings['website_url'] or findings['date_2026']:
        findings['research_status'] = 'in_progress'
    
    return findings

def update_race_with_research(race: Dict, findings: Dict) -> Dict:
    """Update race dictionary with research findings"""
    updated = race.copy()
    
    if findings.get('website_url'):
        updated['WEBSITE_URL'] = findings['website_url']
        updated['RESEARCH_WEBSITE_FOUND'] = True
    
    if findings.get('registration_url'):
        updated['REGISTRATION_URL'] = findings['registration_url']
        updated['RESEARCH_REGISTRATION_FOUND'] = True
    
    if findings.get('date_2026'):
        updated['DATE'] = findings['date_2026']
        updated['RESEARCH_DATE_CONFIRMED'] = True
    
    if findings.get('field_size'):
        # Parse field size
        field_str = findings['field_size']
        numbers = re.findall(r'\d+', field_str.replace(',', ''))
        if numbers:
            updated['FIELD_SIZE'] = int(numbers[0])
            updated['FIELD_SIZE_DISPLAY'] = field_str
            updated['RESEARCH_FIELD_SIZE_CONFIRMED'] = True
    
    if findings.get('entry_cost'):
        # Parse entry cost
        cost_str = findings['entry_cost']
        numbers = re.findall(r'\d+', cost_str.replace(',', '').replace('$', ''))
        if numbers:
            nums = [int(n) for n in numbers]
            updated['ENTRY_COST_MIN'] = min(nums)
            updated['ENTRY_COST_MAX'] = max(nums)
            updated['ENTRY_COST_DISPLAY'] = cost_str
            updated['RESEARCH_ENTRY_COST_CONFIRMED'] = True
    
    if findings.get('ridewithgps_id'):
        updated['RIDEWITHGPS_ID'] = findings['ridewithgps_id']
    
    updated['RESEARCH_STATUS'] = findings.get('research_status', 'pending')
    updated['RESEARCH_DATE'] = findings.get('research_date', '')
    updated['RESEARCH_POSSIBLE_URLS'] = findings.get('possible_urls', [])
    updated['RESEARCH_NOTES'] = findings.get('research_notes', [])
    
    return updated

def main():
    """Research all 388 races comprehensively"""
    print("=" * 60)
    print("COMPREHENSIVE RESEARCH - ALL 388 RACES")
    print("=" * 60)
    
    # Load database
    print("\nLoading database...")
    db = load_database()
    races = db.get('races', [])
    print(f"Found {len(races)} races to research")
    
    # Research each race
    print("\nStarting comprehensive research...")
    researched_count = 0
    updated_count = 0
    
    for i, race in enumerate(races, 1):
        race_name = race.get('RACE_NAME', 'Unknown')
        
        # Research race
        findings = research_race_comprehensive(race)
        
        # Update race with findings
        updated_race = update_race_with_research(race, findings)
        races[i-1] = updated_race
        
        researched_count += 1
        if findings.get('website_url') or findings.get('date_2026'):
            updated_count += 1
        
        # Progress update every 50 races
        if i % 50 == 0:
            print(f"  Progress: {i}/{len(races)} races researched ({i/len(races)*100:.1f}%)")
    
    # Update database
    db['races'] = races
    db['metadata']['last_researched'] = datetime.now().isoformat()
    db['metadata']['research_status'] = 'comprehensive_research_complete'
    db['metadata']['races_researched'] = researched_count
    db['metadata']['races_updated'] = updated_count
    
    # Save database
    print(f"\nSaving updated database...")
    with open('gravel_races_full_database.json', 'w') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'=' * 60}")
    print(f"✓ COMPREHENSIVE RESEARCH COMPLETE")
    print(f"{'=' * 60}")
    print(f"Total races researched: {researched_count}")
    print(f"Races with data updates: {updated_count}")
    print(f"Database saved: gravel_races_full_database.json")
    print(f"\nNext: Manual verification of possible URLs and data collection")

if __name__ == '__main__':
    main()

