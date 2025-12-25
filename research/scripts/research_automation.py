"""
Research Automation Script

Helps automate research tasks for the 388-race database.
Can be extended to scrape websites, search BikeReg, etc.
"""

import json
import re
from typing import Dict, Any, List
from pathlib import Path

def generate_research_tasks(race_name: str, location: str) -> List[str]:
    """Generate research tasks for a race"""
    tasks = [
        f"Search for '{race_name}' official website",
        f"Find registration URL for {race_name}",
        f"Confirm 2026 date for {race_name}",
        f"Get field size for {race_name}",
        f"Get entry cost for {race_name}",
        f"Find RideWithGPS route for {race_name}",
        f"Check BikeReg for {race_name}",
        f"Check GravelHive for {race_name}",
    ]
    return tasks

def create_research_batch(races: List[Dict], batch_name: str, output_dir: str):
    """Create a batch research file for multiple races"""
    research_batch = {
        "metadata": {
            "batch_name": batch_name,
            "total_races": len(races),
            "created": "2025-01-XX"
        },
        "races": []
    }
    
    for race in races:
        race_research = {
            "race_name": race.get("RACE_NAME", ""),
            "location": race.get("LOCATION", ""),
            "priority_score": race.get("PRIORITY_SCORE", 0),
            "competition": race.get("COMPETITION", ""),
            "research_status": "pending",
            "research_tasks": generate_research_tasks(
                race.get("RACE_NAME", ""),
                race.get("LOCATION", "")
            ),
            "research_fields": {
                "website_url": race.get("WEBSITE_URL", ""),
                "registration_url": race.get("REGISTRATION_URL", ""),
                "date_2026": race.get("DATE", ""),
                "field_size": race.get("FIELD_SIZE_DISPLAY", ""),
                "entry_cost": race.get("ENTRY_COST_DISPLAY", ""),
                "ridewithgps_id": "",
            },
            "notes": race.get("NOTES", ""),
        }
        research_batch["races"].append(race_research)
    
    output_path = Path(output_dir) / f"{batch_name}.json"
    with open(output_path, 'w') as f:
        json.dump(research_batch, f, indent=2, ensure_ascii=False)
    
    print(f"Created research batch: {output_path}")
    return output_path

def create_zero_competition_batch():
    """Create research batch for all zero-competition races"""
    with open('gravel_races_full_database.json', 'r') as f:
        db = json.load(f)
    
    zero_comp_races = [
        r for r in db.get('races', [])
        if r.get('COMPETITION', '').upper() == 'NONE'
    ]
    
    # Sort by priority score
    zero_comp_races.sort(key=lambda x: x.get('PRIORITY_SCORE', 0), reverse=True)
    
    print(f"Found {len(zero_comp_races)} zero-competition races")
    
    # Split into batches of 50
    batch_size = 50
    for i in range(0, len(zero_comp_races), batch_size):
        batch = zero_comp_races[i:i+batch_size]
        batch_num = i // batch_size + 1
        create_research_batch(
            batch,
            f"zero_competition_batch_{batch_num}",
            "research/by_protocol"
        )

def create_uci_series_batch():
    """Create research batch for UCI Gravel World Series races"""
    with open('gravel_races_full_database.json', 'r') as f:
        db = json.load(f)
    
    uci_races = [
        r for r in db.get('races', [])
        if 'UCI' in r.get('NOTES', '').upper() or 'UCI' in r.get('RACE_NAME', '').upper()
    ]
    
    print(f"Found {len(uci_races)} UCI-related races")
    
    create_research_batch(
        uci_races,
        "uci_gravel_world_series",
        "research/uci_series"
    )

def main():
    """Create research batches"""
    print("Creating research batches...")
    
    # Create zero competition batches
    print("\n1. Creating zero-competition race batches...")
    create_zero_competition_batch()
    
    # Create UCI series batch
    print("\n2. Creating UCI series batch...")
    create_uci_series_batch()
    
    print("\n✓ Research batches created")
    print("  Ready for systematic research")

if __name__ == '__main__':
    main()

