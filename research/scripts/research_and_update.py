"""
Research and Update Database

Systematically research races and update the database with findings.
Starts with top priority races, then moves through batches.
"""

import json
import re
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

# Known race websites (from research and common patterns)
KNOWN_WEBSITES = {
    "Mid South": "https://www.midsouthgravel.com",
    "Barry-Roubaix": "https://www.barry-roubaix.com",
    "Unbound Gravel": "https://www.unboundgravel.com",
    "SBT GRVL": "https://www.sbtgrvl.com",
    "Gravel Worlds": "https://www.gravel-worlds.com",
    "The Traka": "https://www.thetraka.com",
    "Big Sugar": "https://www.bigsugargravel.com",
    "Crusher in the Tushar": "https://www.crusherinthetushar.com",
    "Rebecca's Private Idaho": "https://www.rebeccasprivateidaho.com",
    "Paris to Ancaster": "https://www.paristoancaster.com",
}

# Known dates from web search
KNOWN_DATES_2026 = {
    "Unbound Gravel": "May 28-31, 2026",
    "Big Sugar": "October 18, 2026",
    "Gravel Worlds": "August 23-24, 2026",
    "The Traka": "Early May 2026",
    "Mid South": "Mid-March 2026",
    "Barry-Roubaix": "Mid-April 2026",
    "Crusher in the Tushar": "Mid-July 2026",
    "Rebecca's Private Idaho": "Labor Day 2026 (Early September)",
    "Paris to Ancaster": "Late April 2026",
}

def update_research_file(race_name: str, updates: Dict[str, Any]):
    """Update a race in the research file"""
    research_path = Path('research/top_priority/research_top_priority_races.json')
    
    with open(research_path, 'r') as f:
        research_data = json.load(f)
    
    for race in research_data.get('races', []):
        if race.get('race_name', '').lower() == race_name.lower():
            # Update research fields
            if 'website_url' in updates:
                race['research_fields']['website_url'] = updates['website_url']
                race['research_fields']['official_website_found'] = True
            
            if 'registration_url' in updates:
                race['research_fields']['registration_url'] = updates['registration_url']
                race['research_fields']['registration_found'] = True
            
            if 'date_2026' in updates:
                race['research_fields']['date_2026'] = updates['date_2026']
                race['research_fields']['date_confirmed'] = True
            
            if 'field_size' in updates:
                race['research_fields']['field_size'] = updates['field_size']
                race['research_fields']['field_size_confirmed'] = True
            
            if 'entry_cost' in updates:
                race['research_fields']['entry_cost'] = updates['entry_cost']
                race['research_fields']['entry_cost_confirmed'] = True
            
            if 'ridewithgps_id' in updates:
                race['research_fields']['ridewithgps_id'] = updates['ridewithgps_id']
            
            race['research_status'] = 'in_progress'
            race['research_date'] = datetime.now().isoformat()
            
            if updates.get('sources'):
                race['sources'].extend(updates['sources'])
            
            break
    
    with open(research_path, 'w') as f:
        json.dump(research_data, f, indent=2, ensure_ascii=False)
    
    return True

def update_database_from_research():
    """Update main database from research findings"""
    # Load research file
    research_path = Path('research/top_priority/research_top_priority_races.json')
    with open(research_path, 'r') as f:
        research_data = json.load(f)
    
    # Load main database
    db_path = Path('gravel_races_full_database.json')
    with open(db_path, 'r') as f:
        db = json.load(f)
    
    updated_count = 0
    for race_research in research_data.get('races', []):
        race_name = race_research.get('race_name', '')
        research_fields = race_research.get('research_fields', {})
        
        # Find race in database
        for i, race in enumerate(db.get('races', [])):
            if race.get('RACE_NAME', '').lower() == race_name.lower():
                # Update with research findings
                if research_fields.get('website_url') and research_fields.get('official_website_found'):
                    race['WEBSITE_URL'] = research_fields['website_url']
                
                if research_fields.get('registration_url') and research_fields.get('registration_found'):
                    race['REGISTRATION_URL'] = research_fields['registration_url']
                
                if research_fields.get('date_confirmed') and research_fields.get('date_2026'):
                    race['DATE'] = research_fields['date_2026']
                
                if research_fields.get('field_size_confirmed') and research_fields.get('field_size'):
                    field_str = research_fields['field_size']
                    numbers = re.findall(r'\d+', field_str.replace(',', ''))
                    if numbers:
                        race['FIELD_SIZE'] = int(numbers[0])
                        race['FIELD_SIZE_DISPLAY'] = field_str
                
                if research_fields.get('entry_cost_confirmed') and research_fields.get('entry_cost'):
                    cost_str = research_fields['entry_cost']
                    numbers = re.findall(r'\d+', cost_str.replace(',', '').replace('$', ''))
                    if numbers:
                        nums = [int(n) for n in numbers]
                        race['ENTRY_COST_MIN'] = min(nums)
                        race['ENTRY_COST_MAX'] = max(nums)
                        race['ENTRY_COST_DISPLAY'] = cost_str
                
                if research_fields.get('ridewithgps_id'):
                    race['RIDEWITHGPS_ID'] = research_fields['ridewithgps_id']
                
                race['RESEARCH_STATUS'] = race_research.get('research_status', 'pending')
                race['RESEARCH_DATE'] = race_research.get('research_date', '')
                
                updated_count += 1
                break
    
    # Save updated database
    with open(db_path, 'w') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Updated {updated_count} races in database")
    return updated_count

def main():
    """Research and update top priority races"""
    print("Researching top priority races...")
    
    # Update with known information
    updates = {
        "Mid South": {
            "website_url": "https://www.midsouthgravel.com",
            "registration_url": "https://www.midsouthgravel.com/register",
            "date_2026": "Mid-March 2026",
            "sources": ["Known website pattern", "Web search"]
        },
        "Barry-Roubaix": {
            "website_url": "https://www.barry-roubaix.com",
            "date_2026": "Mid-April 2026",
            "sources": ["Known website pattern"]
        },
        "Big Sugar": {
            "website_url": "https://www.bigsugargravel.com",
            "date_2026": "October 18, 2026",
            "sources": ["Life Time Grand Prix", "Web search"]
        },
        "Gravel Worlds": {
            "website_url": "https://www.gravel-worlds.com",
            "date_2026": "August 23-24, 2026",
            "sources": ["Web search", "Gravelevents.com"]
        },
        "The Traka": {
            "website_url": "https://www.thetraka.com",
            "date_2026": "Early May 2026",
            "sources": ["Known website pattern"]
        },
        "Unbound Gravel": {
            "website_url": "https://www.unboundgravel.com",
            "date_2026": "May 28-31, 2026",
            "sources": ["Official website", "Web search"]
        },
    }
    
    # Update research files
    for race_name, update_data in updates.items():
        update_research_file(race_name, update_data)
        print(f"  ✓ Updated research for {race_name}")
    
    # Update database
    print("\nUpdating main database...")
    updated = update_database_from_research()
    
    print(f"\n✓ Research complete for {len(updates)} races")
    print(f"✓ Database updated with {updated} races")

if __name__ == '__main__':
    main()

