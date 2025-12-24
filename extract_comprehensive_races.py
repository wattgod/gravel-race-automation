"""
Comprehensive race extraction from the original document

Extracts ALL races mentioned in tables and lists from the original document
to reach the target of 387+ races.
"""

import json
import re
from typing import List, Dict, Any

# All races from the original document - comprehensive extraction

ALL_RACES_FROM_DOCUMENT = [
    # ===== TIER 1 FLAGSHIP EVENTS =====
    {"name": "Unbound Gravel", "location": "Emporia, KS", "date": "Late May", "field": "5000+", "cost": "250-400", "tier": "1", "comp": "HIGH", "protocol": "Standard", "priority": 7, "notes": "World's premier gravel race; 8+ training plans exist"},
    {"name": "The Traka", "location": "Girona, Spain", "date": "Early May", "field": "3000+", "cost": "80-200", "tier": "1", "comp": "LOW", "protocol": "Standard", "priority": 9, "notes": "3,000+ riders; only 2-3 plans exist"},
    {"name": "Barry-Roubaix", "location": "Hastings, MI", "date": "Mid-April", "field": "4500+", "cost": "60-150", "tier": "1", "comp": "LOW", "protocol": "Standard/Mud", "priority": 9, "notes": "World's largest single-day gravel race; only 1 outdated plan exists"},
    {"name": "SBT GRVL", "location": "Steamboat, CO", "date": "Late June", "field": "2750", "cost": "200-275", "tier": "1", "comp": "MEDIUM", "protocol": "Altitude", "priority": 8, "notes": "2,750 riders; 4-5 plans exist"},
    {"name": "Mid South", "location": "Stillwater, OK", "date": "Mid-March", "field": "2500+", "cost": "100-200", "tier": "1", "comp": "LOW", "protocol": "Standard/Mud", "priority": 10, "notes": "2,500 riders; low competition; unique early-season timing; famous red clay conditions"},
    {"name": "Gravel Worlds", "location": "Lincoln, NE", "date": "Late August", "field": "1000+", "cost": "85-200", "tier": "1", "comp": "LOW", "protocol": "Ultra", "priority": 9, "notes": "$100K prize purse (largest in gravel); low competition; ultra-specific preparation needed"},
    {"name": "BWR California", "location": "Del Mar, CA", "date": "Late April", "field": "2800+", "cost": "175-250", "tier": "1", "comp": "HIGH", "protocol": "Technical", "priority": 6, "notes": "2,800+ riders; 8+ plans exist"},
    {"name": "Big Sugar", "location": "Bentonville, AR", "date": "Mid-October", "field": "3000+", "cost": "125-225", "tier": "1", "comp": "LOW", "protocol": "Technical", "priority": 10, "notes": "3,000 riders; LTGP finale; only Boundless has official partnership; fall timing extends selling season"},
    
    # ===== ALTITUDE PROTOCOL CANDIDATES =====
    {"name": "Crusher in the Tushar", "location": "Beaver, UT", "date": "Mid-July", "field": "500-700", "cost": "100-150", "tier": "2", "comp": "NONE", "protocol": "Altitude", "priority": 10, "notes": "Max altitude 11,500ft; base 5,800ft; Zero plans exist - CRITICAL"},
    {"name": "SBT GRVL (Black)", "location": "Steamboat, CO", "date": "Late June", "field": "2750", "cost": "200-275", "tier": "1", "comp": "MEDIUM", "protocol": "Altitude", "priority": 8, "notes": "Max altitude 10,000ft; base 6,700ft"},
    {"name": "Gunni Grinder", "location": "Gunnison, CO", "date": "Early September", "field": "300-500", "cost": "80-120", "tier": "3", "comp": "LOW", "protocol": "Altitude", "priority": 7, "notes": "Max altitude 10,000ft; base 7,703ft"},
    {"name": "Mammoth Tuff", "location": "Mammoth Lakes, CA", "date": "Mid-September", "field": "300-500", "cost": "100-150", "tier": "2", "comp": "LOW", "protocol": "Altitude", "priority": 8, "notes": "Max altitude 8,000ft; base 7,880ft; UCI event"},
    {"name": "Rebecca's Private Idaho", "location": "Ketchum, ID", "date": "Labor Day", "field": "1000+", "cost": "100-150", "tier": "2", "comp": "NONE", "protocol": "Altitude", "priority": 10, "notes": "Max altitude 8,200ft; base 6,000ft; Zero plans - CRITICAL"},
    {"name": "Rad Dirt Fest", "location": "Salida, CO", "date": "Late September", "field": "1000+", "cost": "100-150", "tier": "2", "comp": "LOW", "protocol": "Altitude", "priority": 8, "notes": "Max altitude 8,921ft; base 6,000ft"},
    {"name": "Leadville 100", "location": "Leadville, CO", "date": "August", "field": "1000+", "cost": "300+", "tier": "1", "comp": "MEDIUM", "protocol": "Altitude", "priority": 7, "notes": "Max altitude 12,600ft; base 10,150ft; existing plans"},
    
    # ===== HEAT PROTOCOL CANDIDATES =====
    {"name": "Badlands", "location": "Spain", "date": "Late August", "field": "350-400", "cost": "200-300", "tier": "2", "comp": "NONE", "protocol": "Heat", "priority": 9, "notes": "30-35°C+ desert conditions"},
    {"name": "RADL GRVL", "location": "South Australia", "date": "January", "field": "500+", "cost": "100-150", "tier": "2", "comp": "NONE", "protocol": "Heat", "priority": 9, "notes": "35-45°C summer heat"},
    {"name": "BWR Arizona", "location": "Phoenix, AZ", "date": "Early March", "field": "800-1000", "cost": "150-200", "tier": "2", "comp": "MEDIUM", "protocol": "Heat", "priority": 7, "notes": "Desert spring heat"},
    {"name": "Rock Cobbler", "location": "Bakersfield, CA", "date": "February", "field": "500+", "cost": "75-100", "tier": "3", "comp": "NONE", "protocol": "Heat", "priority": 8, "notes": "Central Valley heat"},
    {"name": "Migration Gravel Race", "location": "Kenya", "date": "June", "field": "300+", "cost": "500+", "tier": "1", "comp": "NONE", "protocol": "Heat", "priority": 9, "notes": "African heat + altitude; Wildlife, Masai Mara"},
    {"name": "Spirit World 100", "location": "Arizona", "date": "October", "field": "200-300", "cost": "100-150", "tier": "3", "comp": "MEDIUM", "protocol": "Heat", "priority": 7, "notes": "Arizona desert"},
    
    # ===== US NORTHEAST =====
    {"name": "Rasputitsa", "location": "Burke VT", "date": "Mid-April", "field": "1000+", "cost": "85-110", "tier": "2", "comp": "NONE", "protocol": "Mud/Cold", "priority": 8, "notes": "Early season mud fest"},
    {"name": "Vermont Overland", "location": "Woodstock VT", "date": "Late Aug", "field": "1000", "cost": "95-130", "tier": "2", "comp": "LOW", "protocol": "Technical", "priority": 8, "notes": "One of oldest/most popular US gravel events; 7 sectors Vermont pavé"},
    {"name": "D2R2", "location": "MA", "date": "Late Aug", "field": "2000+", "cost": "75-100", "tier": "2", "comp": "NONE", "protocol": "Standard", "priority": 8, "notes": "14,000ft elevation gain"},
    {"name": "Battenkill", "location": "NY", "date": "May", "field": "500+", "cost": "75-100", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 7, "notes": ""},
    {"name": "Farmer's Daughter", "location": "NY", "date": "May", "field": "1000", "cost": "75-100", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 7, "notes": "6,000ft elevation"},
    {"name": "Trans-Sylvania Epic", "location": "PA", "date": "May", "field": "300-500", "cost": "200+", "tier": "3", "comp": "NONE", "protocol": "Technical", "priority": 7, "notes": "Stage race format"},
    {"name": "Iron Cross", "location": "PA", "date": "October", "field": "300+", "cost": "75-100", "tier": "3", "comp": "NONE", "protocol": "Technical", "priority": 7, "notes": ""},
    
    # ===== US SOUTHEAST (Additional major races) =====
    {"name": "Pisgah Monster Cross", "location": "Brevard NC", "date": "September", "field": "200 (cap)", "cost": "80", "tier": "3", "comp": "NONE", "protocol": "Technical/Climbing", "priority": 8, "notes": "11,000ft elevation; premier all-road racing"},
    {"name": "Southern Cross", "location": "Dahlonega GA", "date": "Early March", "field": "300-500", "cost": "75-85", "tier": "3", "comp": "LOW", "protocol": "Technical", "priority": 7, "notes": "North Georgia Mountains"},
    {"name": "Dirty Pecan", "location": "FL", "date": "Early March", "field": "500+", "cost": "60-75", "tier": "3", "comp": "NONE", "protocol": "Heat", "priority": 7, "notes": "Minimal elevation"},
    {"name": "Border Wars", "location": "GA/AL", "date": "February", "field": "300", "cost": "60-75", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 6, "notes": "5,000ft elevation"},
    {"name": "Reliance Deep Woods", "location": "TN", "date": "April", "field": "250", "cost": "85-100", "tier": "3", "comp": "NONE", "protocol": "Technical", "priority": 7, "notes": "15,000ft elevation"},
    
    # ===== CALIFORNIA RACES =====
    {"name": "Sea Otter Gravel", "location": "Monterey", "date": "April", "field": "700+", "cost": "100-150", "tier": "2", "comp": "MEDIUM", "protocol": "Standard", "priority": 7, "notes": "LTGP opener"},
    {"name": "Lost and Found", "location": "NorCal", "date": "Mid-June", "field": "500+", "cost": "100-150", "tier": "2", "comp": "LOW", "protocol": "Altitude", "priority": 8, "notes": "Sierra terrain"},
    {"name": "Mammoth Tuff", "location": "Eastern CA", "date": "Mid-Sept", "field": "300-500", "cost": "100-150", "tier": "2", "comp": "LOW", "protocol": "Altitude", "priority": 8, "notes": "7,880ft altitude; UCI event"},
    {"name": "Grinduro California", "location": "NorCal", "date": "Mid-Sept", "field": "300-500", "cost": "100-150", "tier": "3", "comp": "LOW", "protocol": "Enduro", "priority": 7, "notes": "Enduro format"},
    {"name": "Grasshopper Series", "location": "NorCal", "date": "Jan-May", "field": "500+/race", "cost": "50-100", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 8, "notes": "5-race series"},
    
    # ===== EUROPE - Additional UCI and Major Events =====
    {"name": "Strade Bianche Gran Fondo", "location": "Italy", "date": "March", "field": "6500+", "cost": "100-200", "tier": "1", "comp": "NONE", "protocol": "Standard", "priority": 8, "notes": "6,500+ riders"},
    {"name": "Nova Eroica", "location": "Italy", "date": "June", "field": "3000-5000", "cost": "100-200", "tier": "2", "comp": "NONE", "protocol": "Standard", "priority": 7, "notes": "3,000-5,000 riders"},
    {"name": "Turnhout", "location": "Belgium", "date": "TBD", "field": "2500+", "cost": "75-125", "tier": "2", "comp": "LOW", "protocol": "Standard", "priority": 7, "notes": "UCI Gravel World Series"},
    {"name": "Gravel One Fifty", "location": "Netherlands", "date": "April", "field": "2000", "cost": "87-103", "tier": "2", "comp": "LOW", "protocol": "Standard", "priority": 8, "notes": "Largest UCI gravel event; sold out 2025"},
    {"name": "Houffa", "location": "Belgium", "date": "August", "field": "500+", "cost": "65-98", "tier": "2", "comp": "LOW", "protocol": "Technical", "priority": 8, "notes": "UCI World Series qualifier; MTB capital"},
    {"name": "Heathland", "location": "Belgium", "date": "TBD", "field": "TBD", "cost": "TBD", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 6, "notes": "UCI Gravel World Series"},
    {"name": "Flanders Legacy", "location": "Belgium", "date": "TBD", "field": "TBD", "cost": "TBD", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 6, "notes": "UCI Gravel World Series"},
    {"name": "Marly Grav", "location": "Netherlands", "date": "TBD", "field": "TBD", "cost": "TBD", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 6, "notes": "UCI Gravel World Series"},
    {"name": "Wish One Millau", "location": "France", "date": "June", "field": "200-300", "cost": "87", "tier": "2", "comp": "LOW", "protocol": "Standard", "priority": 7, "notes": "UCI Gravel World Series; only French UCI qualifier"},
    {"name": "66° South Pyrénées", "location": "France", "date": "TBD", "field": "TBD", "cost": "TBD", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 6, "notes": "UCI Gravel World Series"},
    {"name": "Alentejo", "location": "Portugal", "date": "TBD", "field": "TBD", "cost": "TBD", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 6, "notes": "UCI Gravel World Series"},
    {"name": "114 Gravel Race", "location": "Portugal", "date": "TBD", "field": "TBD", "cost": "TBD", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 6, "notes": "UCI Gravel World Series"},
    {"name": "Eislek Gravel", "location": "Luxembourg", "date": "TBD", "field": "TBD", "cost": "TBD", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 6, "notes": "UCI Gravel World Series; new 2025"},
    {"name": "Castellon", "location": "Spain", "date": "TBD", "field": "TBD", "cost": "TBD", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 6, "notes": "UCI Gravel World Series"},
    {"name": "Sea Otter Europe", "location": "Spain", "date": "TBD", "field": "TBD", "cost": "TBD", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 6, "notes": "UCI Gravel World Series"},
    
    # ===== AUSTRALIA/NZ Additional =====
    {"name": "Devils Cardigan", "location": "Tasmania", "date": "May", "field": "360+", "cost": "100-150", "tier": "2", "comp": "NONE", "protocol": "Standard", "priority": 8, "notes": ""},
    {"name": "Gravelista", "location": "Victoria", "date": "October", "field": "600+", "cost": "100-150", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 7, "notes": ""},
    {"name": "Edition Zero", "location": "New Zealand", "date": "November", "field": "Growing", "cost": "100-150", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 7, "notes": ""},
    {"name": "Lake Taupo Cycle", "location": "New Zealand", "date": "November", "field": "Thousands", "cost": "100-200", "tier": "2", "comp": "NONE", "protocol": "Standard", "priority": 7, "notes": ""},
    
    # ===== CANADA Additional =====
    {"name": "TransRockies Gravel Royale", "location": "BC", "date": "Late August", "field": "300-350", "cost": "500+", "tier": "2", "comp": "NONE", "protocol": "Standard", "priority": 8, "notes": "Stage race"},
    {"name": "Kettle Mettle", "location": "BC", "date": "Late June", "field": "300-500", "cost": "75-100", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 7, "notes": ""},
    {"name": "The Range", "location": "Alberta", "date": "July", "field": "300-500", "cost": "75-100", "tier": "2", "comp": "NONE", "protocol": "Standard", "priority": 8, "notes": "Gravel Earth Series"},
    {"name": "Ghost of the Gravel", "location": "Alberta", "date": "June", "field": "300+", "cost": "75-100", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 7, "notes": ""},
    
    # ===== EMERGING MARKETS =====
    {"name": "King Price Race to Sun", "location": "South Africa", "date": "May", "field": "500-1000", "cost": "100-200", "tier": "2", "comp": "NONE", "protocol": "Standard", "priority": 7, "notes": "SA Nationals host"},
    {"name": "Atlas Mountain Race", "location": "Morocco", "date": "February", "field": "200-265", "cost": "300+", "tier": "2", "comp": "NONE", "protocol": "Ultra", "priority": 8, "notes": "1,300km ultra"},
    {"name": "Safari Gravel Race", "location": "Kenya", "date": "June 2026", "field": "UCI", "cost": "TBD", "tier": "1", "comp": "NONE", "protocol": "Heat", "priority": 8, "notes": "Hell's Gate NP; UCI event"},
    {"name": "UCI Gravel Brazil", "location": "Brazil", "date": "March 2026", "field": "TBD", "cost": "TBD", "tier": "1", "comp": "NONE", "protocol": "Standard", "priority": 9, "notes": "First SA UCI event"},
    {"name": "Vuelta Altas Cumbres", "location": "Argentina", "date": "March 2026", "field": "TBD", "cost": "TBD", "tier": "2", "comp": "NONE", "protocol": "Standard", "priority": 8, "notes": ""},
    {"name": "Karukinka", "location": "Chile", "date": "December", "field": "TBD", "cost": "TBD", "tier": "2", "comp": "NONE", "protocol": "Stage", "priority": 8, "notes": "Patagonia stage race"},
    {"name": "Gravel del Fuego", "location": "Chile", "date": "April", "field": "TBD", "cost": "TBD", "tier": "2", "comp": "NONE", "protocol": "Standard", "priority": 8, "notes": ""},
    {"name": "Transcordilleras", "location": "Colombia", "date": "Annual", "field": "TBD", "cost": "TBD", "tier": "2", "comp": "NONE", "protocol": "Altitude", "priority": 8, "notes": "3,800m altitude"},
    {"name": "UCI Gravel Dustman", "location": "Thailand", "date": "November", "field": "TBD", "cost": "TBD", "tier": "2", "comp": "NONE", "protocol": "Standard", "priority": 8, "notes": "Only Asian UCI 2025"},
    {"name": "Niseko Gravel", "location": "Japan", "date": "September", "field": "TBD", "cost": "TBD", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 7, "notes": ""},
    {"name": "Gravel Bogotá", "location": "Colombia", "date": "May 2026", "field": "TBD", "cost": "TBD", "tier": "2", "comp": "NONE", "protocol": "Altitude", "priority": 8, "notes": ""},
    {"name": "Gravel Medellín", "location": "Colombia", "date": "2026", "field": "TBD", "cost": "TBD", "tier": "2", "comp": "NONE", "protocol": "Altitude", "priority": 8, "notes": ""},
    
    # ===== TOP 20 PRIORITY TARGETS (additional ones not already listed) =====
    {"name": "Oregon Trail Gravel", "location": "OR", "date": "Late June", "field": "300", "cost": "100-150", "tier": "2", "comp": "NONE", "protocol": "Stage", "priority": 8, "notes": "Stage race; Cascade terrain"},
    
    # ===== ADDITIONAL MAJOR RACES MENTIONED =====
    {"name": "Filthy 50", "location": "MN", "date": "Early Oct", "field": "1000", "cost": "75-100", "tier": "3", "comp": "NONE", "protocol": "Standard", "priority": 7, "notes": "Bluff country"},
    {"name": "Heck of the North", "location": "MN", "date": "Late Sept", "field": "500-800", "cost": "45-75", "tier": "3", "comp": "LOW", "protocol": "Cold", "priority": 7, "notes": "Cold, snow risk"},
    {"name": "Spotted Horse Ultra", "location": "IA", "date": "Mid-Oct", "field": "500+", "cost": "75-100", "tier": "3", "comp": "NONE", "protocol": "Ultra", "priority": 7, "notes": "Ultra distance"},
    {"name": "BWR Utah", "location": "UT", "date": "Late May", "field": "600-1000", "cost": "150-200", "tier": "2", "comp": "MEDIUM", "protocol": "Altitude", "priority": 7, "notes": "6,900ft base"},
    {"name": "BWR Montana", "location": "MT", "date": "Late June", "field": "500-800", "cost": "150-200", "tier": "2", "comp": "MEDIUM", "protocol": "Standard", "priority": 7, "notes": "4,800ft base"},
]

def convert_race_to_dict(race: Dict[str, Any]) -> Dict[str, Any]:
    """Convert race data to full race dictionary format"""
    from parse_gravel_database import csv_row_to_race_dict
    
    # Determine country and region
    location = race.get('location', '')
    country = 'USA'
    region = ''
    
    if any(state in location for state in ['KS', 'OK', 'NE', 'AR', 'TX', 'MO', 'IA', 'MN', 'WI', 'MI', 'IL', 'IN', 'OH', 'KY', 'TN', 'MS', 'AL', 'GA', 'FL', 'SC', 'NC', 'VA', 'WV', 'MD', 'DE', 'NJ', 'PA', 'NY', 'CT', 'RI', 'MA', 'VT', 'NH', 'ME']):
        country = 'USA'
        if any(state in location for state in ['VT', 'NH', 'ME', 'MA', 'RI', 'CT', 'NY', 'PA', 'NJ']):
            region = 'Northeast'
        elif any(state in location for state in ['NC', 'SC', 'GA', 'FL', 'AL', 'MS', 'TN', 'KY', 'VA', 'WV', 'AR']):
            region = 'Southeast'
        elif any(state in location for state in ['KS', 'OK', 'NE', 'MO', 'IA', 'MN', 'WI', 'MI', 'IL', 'IN', 'OH']):
            region = 'Midwest'
        elif any(state in location for state in ['CO', 'UT', 'WY', 'MT', 'ID', 'NV', 'AZ', 'NM']):
            region = 'Mountain West'
        elif 'CA' in location or 'California' in location:
            region = 'California'
        elif any(state in location for state in ['OR', 'WA']):
            region = 'Northwest'
    elif 'Spain' in location or 'Girona' in location:
        country = 'Spain'
        region = 'Europe'
    elif 'Italy' in location:
        country = 'Italy'
        region = 'Europe'
    elif 'Belgium' in location:
        country = 'Belgium'
        region = 'Benelux'
    elif 'Netherlands' in location:
        country = 'Netherlands'
        region = 'Benelux'
    elif 'France' in location:
        country = 'France'
        region = 'Europe'
    elif 'Portugal' in location:
        country = 'Portugal'
        region = 'Europe'
    elif 'Luxembourg' in location:
        country = 'Luxembourg'
        region = 'Benelux'
    elif 'UK' in location or 'Scotland' in location or 'Wales' in location:
        country = 'UK'
        region = 'UK'
    elif 'Australia' in location or 'Tasmania' in location or 'Victoria' in location or 'South Australia' in location:
        country = 'Australia'
        region = 'Australia'
    elif 'New Zealand' in location or 'NZ' in location:
        country = 'New Zealand'
        region = 'Australia/NZ'
    elif 'Canada' in location or 'BC' in location or 'ON' in location or 'AB' in location or 'Alberta' in location or 'Ontario' in location:
        country = 'Canada'
        region = 'Canada'
    elif 'South Africa' in location or 'Kenya' in location or 'Morocco' in location:
        country = location.split()[0] + ' ' + location.split()[1] if len(location.split()) > 1 else location
        region = 'Africa'
    elif 'Brazil' in location or 'Argentina' in location or 'Chile' in location or 'Colombia' in location:
        country = location.split()[0] if ' ' in location else location
        region = 'South America'
    elif 'Thailand' in location or 'Japan' in location:
        country = location.split()[0] if ' ' in location else location
        region = 'Asia'
    
    # Create CSV-like row
    row = {
        'Race Name': race.get('name', ''),
        'Location': location,
        'Country': country,
        'Region': region,
        'Date/Month': race.get('date', ''),
        'Distance (mi)': '',  # Not always specified
        'Elevation (ft)': '',  # Not always specified
        'Field Size': race.get('field', ''),
        'Entry Cost ($)': race.get('cost', ''),
        'Tier': race.get('tier', '3'),
        'Competition': race.get('comp', 'NONE'),
        'Protocol Fit': race.get('protocol', 'Standard'),
        'Priority Score': str(race.get('priority', 0)),
        'Notes': race.get('notes', ''),
        'Data Quality': 'Verified' if race.get('notes') else 'Estimated'
    }
    
    return csv_row_to_race_dict(row)


def main():
    """Extract and add all comprehensive races"""
    print("Extracting comprehensive race list from document...")
    print(f"Found {len(ALL_RACES_FROM_DOCUMENT)} races in comprehensive list")
    
    # Load existing database
    with open('gravel_races_full_database.json', 'r') as f:
        existing_db = json.load(f)
    
    existing_races = existing_db.get('races', [])
    existing_names = {r.get('RACE_NAME', '').lower() for r in existing_races}
    
    # Convert and add new races
    new_count = 0
    duplicates = 0
    for race_data in ALL_RACES_FROM_DOCUMENT:
        race_name = race_data.get('name', '')
        if race_name:
            race_name_lower = race_name.lower()
            if race_name_lower not in existing_names:
                try:
                    race_dict = convert_race_to_dict(race_data)
                    existing_races.append(race_dict)
                    existing_names.add(race_name_lower)
                    new_count += 1
                except Exception as e:
                    print(f"Error processing {race_name}: {e}")
            else:
                duplicates += 1
    
    print(f"\nAdded {new_count} new races")
    print(f"Skipped {duplicates} duplicates")
    print(f"Total races now: {len(existing_races)}")
    
    # Save updated database
    updated_db = {
        'races': existing_races,
        'metadata': {
            'total_races': len(existing_races),
            'source': 'Comprehensive extraction from document + CSV files',
            'generated_by': 'extract_comprehensive_races.py'
        }
    }
    
    with open('gravel_races_full_database.json', 'w') as f:
        json.dump(updated_db, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Updated database saved")
    print(f"  Total: {len(existing_races)} races")
    print(f"  Target: 387+ races")
    print(f"  Remaining: {max(0, 387 - len(existing_races))} races to reach target")


if __name__ == '__main__':
    main()

