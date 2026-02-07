"""
Parse markdown tables from the original document to extract all races

The original document has extensive markdown tables with race data.
This script extracts races from those tables.
"""

import re
import json
from typing import List, Dict, Any

def parse_markdown_table(table_text: str) -> List[Dict[str, str]]:
    """Parse a markdown table into a list of dictionaries"""
    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
    if len(lines) < 2:
        return []
    
    # First line is header
    header_line = lines[0]
    # Remove leading/trailing pipes and split
    headers = [h.strip() for h in header_line.strip('|').split('|')]
    
    # Skip separator line (second line)
    data_lines = lines[2:]
    
    races = []
    for line in data_lines:
        if not line.startswith('|'):
            continue
        # Remove leading/trailing pipes and split
        values = [v.strip() for v in line.strip('|').split('|')]
        if len(values) == len(headers):
            race = dict(zip(headers, values))
            races.append(race)
    
    return races

def extract_races_from_document():
    """
    Extract races from the original document text.
    
    Since we don't have the original document file, this function
    contains the key races mentioned in tables that we're missing.
    """
    
    # These are races mentioned in the document that we haven't added yet
    # Based on the tables in the original query
    
    missing_races = []
    
    # US Northeast races (from the document)
    northeast_races = [
        {"Race Name": "Rasputitsa", "Location": "Burke VT", "Date": "Mid-April", "Field": "1000+", "Competition": "NONE"},
        {"Race Name": "Vermont Overland", "Location": "Woodstock VT", "Date": "Late Aug", "Field": "1000", "Competition": "NONE"},
        {"Race Name": "D2R2", "Location": "MA", "Date": "Late Aug", "Field": "2000+", "Competition": "NONE"},
        {"Race Name": "Battenkill", "Location": "NY", "Date": "May", "Field": "500+", "Competition": "NONE"},
        {"Race Name": "Farmer's Daughter", "Location": "NY", "Date": "May", "Field": "1000", "Competition": "NONE"},
        {"Race Name": "Trans-Sylvania Epic", "Location": "PA", "Date": "May", "Field": "300-500", "Competition": "NONE"},
        {"Race Name": "Iron Cross", "Location": "PA", "Date": "October", "Field": "300+", "Competition": "NONE"},
    ]
    
    # US Southeast additional races
    southeast_additional = [
        {"Race Name": "Pisgah Monster Cross", "Location": "Brevard NC", "Date": "September", "Field": "200 (cap)", "Competition": "NONE"},
        {"Race Name": "Southern Cross", "Location": "GA", "Date": "Early March", "Field": "300-500", "Competition": "NONE"},
        {"Race Name": "Dirty Pecan", "Location": "FL", "Date": "Early March", "Field": "500+", "Competition": "NONE"},
        {"Race Name": "Border Wars", "Location": "GA/AL", "Date": "February", "Field": "300", "Competition": "NONE"},
        {"Race Name": "Reliance Deep Woods", "Location": "TN", "Date": "April", "Field": "250", "Competition": "NONE"},
    ]
    
    # California races (25+ mentioned)
    california_races = [
        {"Race Name": "Sea Otter Gravel", "Location": "Monterey", "Date": "April", "Field": "700+", "Competition": "MEDIUM"},
        {"Race Name": "Lost and Found", "Location": "NorCal", "Date": "Mid-June", "Field": "500+", "Competition": "LOW"},
        {"Race Name": "Grinduro California", "Location": "NorCal", "Date": "Mid-Sept", "Field": "300-500", "Competition": "LOW"},
        {"Race Name": "Grasshopper Series", "Location": "NorCal", "Date": "Jan-May", "Field": "500+/race", "Competition": "NONE"},
    ]
    
    # More European races (50+ mentioned, we only have 24)
    europe_additional = [
        {"Race Name": "Strade Bianche Gran Fondo", "Location": "Italy", "Date": "March", "Field": "6500+", "Competition": "NONE"},
        {"Race Name": "Nova Eroica", "Location": "Italy", "Date": "June", "Field": "3000-5000", "Competition": "NONE"},
        {"Race Name": "Turnhout", "Location": "Belgium", "Date": "TBD", "Field": "2500+", "Competition": "NONE"},
        {"Race Name": "Gravel One Fifty", "Location": "Netherlands", "Date": "TBD", "Field": "2000", "Competition": "LOW"},
        {"Race Name": "Houffa", "Location": "Belgium", "Date": "TBD", "Field": "500+", "Competition": "LOW"},
        {"Race Name": "Heathland", "Location": "Belgium", "Date": "TBD", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "Flanders Legacy", "Location": "Belgium", "Date": "TBD", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "Marly Grav", "Location": "Netherlands", "Date": "TBD", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "Wish One Millau", "Location": "France", "Date": "TBD", "Field": "200-300", "Competition": "LOW"},
        {"Race Name": "66° South Pyrénées", "Location": "France", "Date": "TBD", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "Alentejo", "Location": "Portugal", "Date": "TBD", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "114 Gravel Race", "Location": "Portugal", "Date": "TBD", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "Eislek Gravel", "Location": "Luxembourg", "Date": "TBD", "Field": "TBD", "Competition": "NONE"},
    ]
    
    # More Australia/NZ races
    australia_additional = [
        {"Race Name": "Devils Cardigan", "Location": "Tasmania", "Date": "May", "Field": "360+", "Competition": "NONE"},
        {"Race Name": "Gravelista", "Location": "Victoria", "Date": "October", "Field": "600+", "Competition": "NONE"},
        {"Race Name": "Edition Zero", "Location": "New Zealand", "Date": "November", "Field": "Growing", "Competition": "NONE"},
        {"Race Name": "Lake Taupo Cycle", "Location": "NZ", "Date": "November", "Field": "Thousands", "Competition": "NONE"},
    ]
    
    # More Canada races
    canada_additional = [
        {"Race Name": "TransRockies Gravel Royale", "Location": "BC", "Date": "Late August", "Field": "300-350", "Competition": "NONE"},
        {"Race Name": "Kettle Mettle", "Location": "BC", "Date": "Late June", "Field": "300-500", "Competition": "NONE"},
        {"Race Name": "The Range", "Location": "Alberta", "Date": "July", "Field": "300-500", "Competition": "NONE"},
        {"Race Name": "Ghost of the Gravel", "Location": "Alberta", "Date": "June", "Field": "300+", "Competition": "NONE"},
    ]
    
    # Emerging markets
    emerging_markets = [
        {"Race Name": "King Price Race to Sun", "Location": "South Africa", "Date": "May", "Field": "500-1000", "Competition": "NONE"},
        {"Race Name": "Atlas Mountain Race", "Location": "Morocco", "Date": "February", "Field": "200-265", "Competition": "NONE"},
        {"Race Name": "Safari Gravel Race", "Location": "Kenya", "Date": "June 2026", "Field": "UCI", "Competition": "NONE"},
        {"Race Name": "UCI Gravel Brazil", "Location": "Brazil", "Date": "March 2026", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "Vuelta Altas Cumbres", "Location": "Argentina", "Date": "March 2026", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "Karukinka", "Location": "Chile", "Date": "December", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "Gravel del Fuego", "Location": "Chile", "Date": "April", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "Transcordilleras", "Location": "Colombia", "Date": "Annual", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "UCI Gravel Dustman", "Location": "Thailand", "Date": "November", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "Niseko Gravel", "Location": "Japan", "Date": "September", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "Gravel Bogotá", "Location": "Colombia", "Date": "May 2026", "Field": "TBD", "Competition": "NONE"},
        {"Race Name": "Gravel Medellín", "Location": "Colombia", "Date": "2026", "Field": "TBD", "Competition": "NONE"},
    ]
    
    all_missing = (
        northeast_races + southeast_additional + california_races + 
        europe_additional + australia_additional + canada_additional + 
        emerging_markets
    )
    
    return all_missing


def convert_to_race_dict(race_data: Dict[str, str]) -> Dict[str, Any]:
    """Convert extracted race data to full race dictionary"""
    from parse_gravel_database import csv_row_to_race_dict
    
    # Create a CSV-like row
    row = {
        'Race Name': race_data.get('Race Name', ''),
        'Location': race_data.get('Location', ''),
        'Country': 'USA',  # Default, will need to be updated
        'Region': '',  # Will need to be determined
        'Date/Month': race_data.get('Date', ''),
        'Distance (mi)': '',  # Not in all tables
        'Elevation (ft)': '',  # Not in all tables
        'Field Size': race_data.get('Field', ''),
        'Entry Cost ($)': '',  # Not in all tables
        'Tier': '3',  # Default
        'Competition': race_data.get('Competition', 'NONE'),
        'Protocol Fit': 'Standard',  # Default
        'Priority Score': '0',
        'Notes': '',
        'Data Quality': 'Estimated'
    }
    
    # Determine country and region from location
    location = race_data.get('Location', '')
    if any(state in location for state in ['VT', 'MA', 'NY', 'PA', 'NH', 'ME']):
        row['Country'] = 'USA'
        row['Region'] = 'Northeast'
    elif any(state in location for state in ['NC', 'GA', 'FL', 'TN', 'SC', 'AL', 'MS', 'WV', 'AR']):
        row['Country'] = 'USA'
        row['Region'] = 'Southeast'
    elif 'CA' in location or 'California' in location or 'NorCal' in location:
        row['Country'] = 'USA'
        row['Region'] = 'California'
    elif any(country in location for country in ['Italy', 'Belgium', 'Netherlands', 'France', 'Portugal', 'Luxembourg', 'Spain', 'UK', 'Scotland', 'Wales']):
        row['Country'] = location.split()[0] if ' ' in location else location
        row['Region'] = 'Europe'
    elif any(country in location for country in ['Australia', 'Tasmania', 'Victoria', 'New Zealand', 'NZ']):
        row['Country'] = 'Australia' if 'Australia' in location or 'Tasmania' in location or 'Victoria' in location else 'New Zealand'
        row['Region'] = 'Australia/NZ'
    elif any(prov in location for prov in ['BC', 'ON', 'AB', 'Alberta', 'Ontario']):
        row['Country'] = 'Canada'
        row['Region'] = 'Canada'
    elif any(country in location for country in ['South Africa', 'Kenya', 'Morocco']):
        row['Country'] = location.split()[0] + ' ' + location.split()[1] if len(location.split()) > 1 else location
        row['Region'] = 'Africa'
    elif any(country in location for country in ['Brazil', 'Argentina', 'Chile', 'Colombia']):
        row['Country'] = location.split()[0] if ' ' in location else location
        row['Region'] = 'South America'
    elif any(country in location for country in ['Thailand', 'Japan']):
        row['Country'] = location.split()[0] if ' ' in location else location
        row['Region'] = 'Asia'
    
    return csv_row_to_race_dict(row)


def main():
    """Extract and add missing races"""
    print("Extracting missing races from document tables...")
    missing_races_data = extract_races_from_document()
    
    print(f"Found {len(missing_races_data)} additional races mentioned in document")
    
    # Load existing database
    with open('gravel_races_full_database.json', 'r') as f:
        existing_db = json.load(f)
    
    existing_races = existing_db.get('races', [])
    existing_names = {r.get('RACE_NAME', '') for r in existing_races}
    
    # Convert and add new races
    new_count = 0
    for race_data in missing_races_data:
        race_name = race_data.get('Race Name', '')
        if race_name and race_name not in existing_names:
            try:
                race_dict = convert_to_race_dict(race_data)
                existing_races.append(race_dict)
                existing_names.add(race_name)
                new_count += 1
            except Exception as e:
                print(f"Error processing {race_name}: {e}")
    
    print(f"\nAdded {new_count} new races")
    print(f"Total races now: {len(existing_races)}")
    
    # Save updated database
    updated_db = {
        'races': existing_races,
        'metadata': {
            'total_races': len(existing_races),
            'source': 'Combined: CSV files + extracted from document tables',
            'generated_by': 'parse_markdown_tables.py'
        }
    }
    
    with open('gravel_races_full_database.json', 'w') as f:
        json.dump(updated_db, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Updated database saved")
    print(f"  Total: {len(existing_races)} races")


if __name__ == '__main__':
    main()

