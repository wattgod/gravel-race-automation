"""
Research Top Priority Races

Research the highest priority races (Tier 1, zero competition, critical protocol fits)
to enhance database with real data: websites, dates, registration, field sizes, etc.
"""

import json
import requests
from typing import Dict, Any, List
from datetime import datetime

# Top Priority Races to Research (from original document)
TOP_PRIORITY = [
    {
        "name": "Mid South",
        "location": "Stillwater, OK",
        "priority": 10,
        "notes": "2,500 riders; low competition; unique early-season timing; famous red clay conditions",
        "research_fields": ["website", "registration", "date_2026", "field_size", "entry_cost", "ridewithgps_id"]
    },
    {
        "name": "Crusher in the Tushar",
        "location": "Beaver, UT",
        "priority": 10,
        "notes": "Zero plans exist - CRITICAL; Max altitude 11,500ft",
        "research_fields": ["website", "registration", "date_2026", "field_size", "entry_cost", "ridewithgps_id"]
    },
    {
        "name": "Big Sugar",
        "location": "Bentonville, AR",
        "priority": 10,
        "notes": "3,000 riders; LTGP finale; only Boundless has official partnership",
        "research_fields": ["website", "registration", "date_2026", "field_size", "entry_cost", "ridewithgps_id"]
    },
    {
        "name": "Rebecca's Private Idaho",
        "location": "Ketchum, ID",
        "priority": 10,
        "notes": "Zero plans - CRITICAL; Max altitude 8,200ft",
        "research_fields": ["website", "registration", "date_2026", "field_size", "entry_cost", "ridewithgps_id"]
    },
    {
        "name": "Barry-Roubaix",
        "location": "Hastings, MI",
        "priority": 9,
        "notes": "World's largest single-day gravel race; only 1 outdated plan exists",
        "research_fields": ["website", "registration", "date_2026", "field_size", "entry_cost", "ridewithgps_id"]
    },
    {
        "name": "Gravel Worlds",
        "location": "Lincoln, NE",
        "priority": 9,
        "notes": "$100K prize purse (largest in gravel); low competition",
        "research_fields": ["website", "registration", "date_2026", "field_size", "entry_cost", "ridewithgps_id"]
    },
    {
        "name": "The Traka",
        "location": "Girona, Spain",
        "priority": 9,
        "notes": "3,000+ riders; only 2-3 plans exist",
        "research_fields": ["website", "registration", "date_2026", "field_size", "entry_cost", "ridewithgps_id"]
    },
    {
        "name": "Paris to Ancaster",
        "location": "Paris, Ontario, Canada",
        "priority": 9,
        "notes": "Only Canadian UCI qualifier; 3,000 riders",
        "research_fields": ["website", "registration", "date_2026", "field_size", "entry_cost", "ridewithgps_id"]
    },
]

def load_database():
    """Load the current race database"""
    with open('gravel_races_full_database.json', 'r') as f:
        return json.load(f)

def find_race_in_database(race_name: str, db: Dict) -> Dict:
    """Find a race in the database by name"""
    for race in db.get('races', []):
        if race.get('RACE_NAME', '').lower() == race_name.lower():
            return race
    return {}

def create_research_template(race_info: Dict, existing_race: Dict) -> Dict:
    """Create a research template for a race"""
    return {
        "race_name": race_info["name"],
        "location": race_info["location"],
        "priority_score": race_info["priority"],
        "research_status": "pending",
        "research_date": datetime.now().isoformat(),
        "research_fields": {
            "website_url": existing_race.get("WEBSITE_URL", ""),
            "registration_url": existing_race.get("REGISTRATION_URL", ""),
            "date_2026": existing_race.get("DATE", ""),
            "field_size": existing_race.get("FIELD_SIZE_DISPLAY", ""),
            "entry_cost": existing_race.get("ENTRY_COST_DISPLAY", ""),
            "ridewithgps_id": "",
            "official_website_found": False,
            "registration_found": False,
            "date_confirmed": False,
            "field_size_confirmed": False,
            "entry_cost_confirmed": False,
        },
        "notes": race_info["notes"],
        "existing_data": {
            "tier": existing_race.get("TIER", ""),
            "competition": existing_race.get("COMPETITION", ""),
            "protocol_fit": existing_race.get("PROTOCOL_FIT", ""),
        },
        "research_notes": [],
        "sources": []
    }

def main():
    """Create research templates for top priority races"""
    print("Creating research templates for top priority races...")
    
    db = load_database()
    research_data = []
    
    for race_info in TOP_PRIORITY:
        existing_race = find_race_in_database(race_info["name"], db)
        if existing_race:
            research_template = create_research_template(race_info, existing_race)
            research_data.append(research_template)
            print(f"  ✓ Created template for {race_info['name']}")
        else:
            print(f"  ⚠ Race not found in database: {race_info['name']}")
    
    # Save research data
    research_file = {
        "metadata": {
            "created": datetime.now().isoformat(),
            "total_races": len(research_data),
            "research_phase": "initial",
            "priority_focus": "Tier 1 and zero-competition races"
        },
        "races": research_data
    }
    
    with open('research_top_priority_races.json', 'w') as f:
        json.dump(research_file, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Created research file: research_top_priority_races.json")
    print(f"  Total races to research: {len(research_data)}")
    print(f"\nNext steps:")
    print(f"  1. Research each race's official website")
    print(f"  2. Find registration URLs")
    print(f"  3. Confirm 2026 dates")
    print(f"  4. Get field sizes and entry costs")
    print(f"  5. Find RideWithGPS route IDs")

if __name__ == '__main__':
    main()

