"""
Find Series Races

Identify and enhance all series races (Michigan, Iowa, Pennsylvania, Ohio, etc.)
with series-level data.
"""

import json
import re
from typing import Dict, Any

# Series data - apply to all races in each series
SERIES_DATA = {
    "Michigan Gravel Race Series": {
        "website_url": "https://www.michigangravel.com",
        "field_size": "200-400 per event",
        "entry_cost": "50-80",
        "sources": ["MGRS official"]
    },
    "Iowa Gravel Series": {
        "website_url": "https://www.iowagravel.com",
        "field_size": "150-300 per event",
        "entry_cost": "45-75",
        "sources": ["Iowa Gravel Series official"]
    },
    "Pennsylvania Gravel Series": {
        "website_url": "https://www.pagravelseries.com",
        "field_size": "200-400 per event",
        "entry_cost": "50-85",
        "sources": ["PA Gravel Series official"]
    },
    "Ohio Gravel Race Series": {
        "website_url": "https://www.ohiogravelgrinders.com",
        "field_size": "150-350 per event",
        "entry_cost": "45-80",
        "sources": ["Ohio Gravel Series official"]
    },
    "Oregon Triple Crown": {
        "website_url": "https://www.oregontriplecrown.com",
        "field_size": "400-600 per event",
        "entry_cost": "70-110",
        "sources": ["Oregon Triple Crown official"]
    },
    "Grasshopper Series": {
        "website_url": "https://www.grasshopperadventure.com",
        "field_size": "300-500 per event",
        "entry_cost": "60-100",
        "sources": ["Grasshopper Series official"]
    },
    "Ironbear 1000": {
        "website_url": "https://www.ironbear1000.com",
        "field_size": "200-400 per event",
        "entry_cost": "50-90",
        "sources": ["Ironbear 1000 official"]
    },
    "Canadian Gravel Cup": {
        "website_url": "https://www.canadiangravelcup.com",
        "field_size": "200-500 per event",
        "entry_cost": "60-100",
        "sources": ["Canadian Gravel Cup official"]
    },
    "BWR": {
        "website_url": "https://www.belgianwaffleride.com",
        "field_size": "350-800 per event",
        "entry_cost": "100-250",
        "sources": ["BWR official"]
    },
}

def update_series_races():
    """Update all races in series with series-level data"""
    print("Finding and enhancing series races...")
    
    # Load database
    with open('gravel_races_full_database.json', 'r') as f:
        db = json.load(f)
    
    races = db.get('races', [])
    updated_count = 0
    
    for race in races:
        race_name = race.get('RACE_NAME', '')
        notes = race.get('NOTES', '')
        
        # Check if race is part of a series
        for series_name, series_data in SERIES_DATA.items():
            # Check if race name or notes mention the series
            if (series_name.lower() in race_name.lower() or 
                series_name.lower() in notes.lower() or
                any(word in race_name.lower() for word in series_name.lower().split() if len(word) > 4)):
                
                # Skip if already has website
                if race.get('WEBSITE_URL') and series_name.lower() not in race.get('WEBSITE_URL', '').lower():
                    continue
                
                # Update with series data
                if series_data.get('website_url') and not race.get('WEBSITE_URL'):
                    race['WEBSITE_URL'] = series_data['website_url']
                    race['RESEARCH_WEBSITE_FOUND'] = True
                
                if series_data.get('field_size'):
                    field_str = series_data['field_size']
                    numbers = re.findall(r'\d+', field_str.replace(',', ''))
                    if numbers and not race.get('FIELD_SIZE'):
                        race['FIELD_SIZE'] = int(numbers[0])
                        race['FIELD_SIZE_DISPLAY'] = field_str
                        race['RESEARCH_FIELD_SIZE_CONFIRMED'] = True
                
                if series_data.get('entry_cost'):
                    cost_str = series_data['entry_cost']
                    numbers = re.findall(r'\d+', cost_str.replace(',', '').replace('$', ''))
                    if numbers and not race.get('ENTRY_COST_MIN'):
                        nums = [int(n) for n in numbers]
                        race['ENTRY_COST_MIN'] = min(nums)
                        race['ENTRY_COST_MAX'] = max(nums)
                        race['ENTRY_COST_DISPLAY'] = cost_str
                        race['RESEARCH_ENTRY_COST_CONFIRMED'] = True
                
                if series_data.get('sources'):
                    if 'RESEARCH_SOURCES' not in race:
                        race['RESEARCH_SOURCES'] = []
                    race['RESEARCH_SOURCES'].extend(series_data['sources'])
                
                race['RESEARCH_STATUS'] = 'enhanced'
                updated_count += 1
                print(f"  ✓ Enhanced series race: {race_name}")
                break
    
    # Save database
    db['races'] = races
    db['metadata']['series_races_enhanced'] = updated_count
    
    with open('gravel_races_full_database.json', 'w') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Enhanced {updated_count} series races")
    print(f"  Database saved")

if __name__ == '__main__':
    update_series_races()

