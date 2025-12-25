"""
Update main database from research findings

Takes research JSON files and updates the main gravel_races_full_database.json
with verified information.
"""

import json
from typing import Dict, Any, List
from pathlib import Path

def load_research_file(research_path: str) -> Dict:
    """Load a research JSON file"""
    with open(research_path, 'r') as f:
        return json.load(f)

def find_race_in_database(race_name: str, db: Dict) -> tuple[int, Dict]:
    """Find a race in the database by name, return index and race dict"""
    for i, race in enumerate(db.get('races', [])):
        if race.get('RACE_NAME', '').lower() == race_name.lower():
            return i, race
    return -1, {}

def update_race_from_research(race: Dict, research_data: Dict) -> Dict:
    """Update race data from research findings"""
    updated = race.copy()
    
    research_fields = research_data.get('research_fields', {})
    
    # Update website URL
    if research_fields.get('website_url') and not updated.get('WEBSITE_URL'):
        updated['WEBSITE_URL'] = research_fields['website_url']
    
    # Update registration URL
    if research_fields.get('registration_url') and not updated.get('REGISTRATION_URL'):
        updated['REGISTRATION_URL'] = research_fields['registration_url']
    
    # Update date if confirmed
    if research_fields.get('date_confirmed') and research_fields.get('date_2026'):
        updated['DATE'] = research_fields['date_2026']
    
    # Update field size if confirmed
    if research_fields.get('field_size_confirmed') and research_fields.get('field_size'):
        # Parse field size
        field_str = research_fields['field_size']
        # Try to extract number
        import re
        numbers = re.findall(r'\d+', field_str.replace(',', ''))
        if numbers:
            updated['FIELD_SIZE'] = int(numbers[0])
            updated['FIELD_SIZE_DISPLAY'] = field_str
    
    # Update entry cost if confirmed
    if research_fields.get('entry_cost_confirmed') and research_fields.get('entry_cost'):
        cost_str = research_fields['entry_cost']
        # Parse cost
        import re
        numbers = re.findall(r'\d+', cost_str.replace(',', '').replace('$', ''))
        if numbers:
            nums = [int(n) for n in numbers]
            updated['ENTRY_COST_MIN'] = min(nums)
            updated['ENTRY_COST_MAX'] = max(nums)
            updated['ENTRY_COST_DISPLAY'] = cost_str
    
    # Add RideWithGPS ID if found
    if research_fields.get('ridewithgps_id'):
        # Store in notes or create new field
        if 'RIDEWITHGPS_ID' not in updated:
            updated['RIDEWITHGPS_ID'] = research_fields['ridewithgps_id']
    
    # Update research status
    updated['RESEARCH_STATUS'] = research_data.get('research_status', 'pending')
    updated['RESEARCH_DATE'] = research_data.get('research_date', '')
    
    return updated

def main():
    """Update database from research files"""
    print("Updating database from research findings...")
    
    # Load main database
    db_path = Path('gravel_races_full_database.json')
    with open(db_path, 'r') as f:
        db = json.load(f)
    
    # Load research file
    research_path = Path('research_top_priority_races.json')
    if not research_path.exists():
        print(f"Research file not found: {research_path}")
        return
    
    research_data = load_research_file(str(research_path))
    
    # Update races from research
    updated_count = 0
    for race_research in research_data.get('races', []):
        race_name = race_research.get('race_name', '')
        if not race_name:
            continue
        
        idx, race = find_race_in_database(race_name, db)
        if idx >= 0:
            updated_race = update_race_from_research(race, race_research)
            db['races'][idx] = updated_race
            updated_count += 1
            print(f"  ✓ Updated: {race_name}")
        else:
            print(f"  ⚠ Not found in database: {race_name}")
    
    # Save updated database
    with open(db_path, 'w') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Updated {updated_count} races in database")
    print(f"  Database saved to: {db_path}")

if __name__ == '__main__':
    main()

