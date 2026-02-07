"""
Parse Gravel Race Database from CSV/Markdown format to JSON

Converts the comprehensive gravel race database into the JSON format
expected by the WordPress publishing system.
"""

import json
import csv
import re
from typing import Dict, List, Any
from pathlib import Path


def parse_field_size(field_size_str: str) -> int:
    """Parse field size string to integer (handles ranges, +, <, etc.)"""
    if not field_size_str or field_size_str.strip() == '':
        return 0
    
    # Remove common prefixes/suffixes
    field_size_str = field_size_str.strip().replace(',', '').replace('+', '').replace('<', '').replace('~', '')
    
    # Extract numbers
    numbers = re.findall(r'\d+', field_size_str)
    if numbers:
        # Take the first number (or average if range)
        return int(numbers[0])
    return 0


def parse_elevation(elevation_str: str) -> int:
    """Parse elevation string to integer (handles ranges, +, etc.)"""
    if not elevation_str or elevation_str.strip() == '':
        return 0
    
    # Remove common prefixes/suffixes
    elevation_str = elevation_str.strip().replace(',', '').replace('+', '').replace('~', '')
    
    # Extract numbers
    numbers = re.findall(r'\d+', elevation_str)
    if numbers:
        # Take the first number (or average if range)
        return int(numbers[0])
    return 0


def parse_entry_cost(cost_str: str) -> Dict[str, Any]:
    """Parse entry cost string to min/max dictionary"""
    if not cost_str or cost_str.strip() == '':
        return {'min': 0, 'max': 0, 'display': ''}
    
    cost_str = cost_str.strip()
    
    # Extract all numbers
    numbers = re.findall(r'\d+', cost_str)
    if numbers:
        nums = [int(n) for n in numbers]
        return {
            'min': min(nums),
            'max': max(nums),
            'display': cost_str
        }
    
    return {'min': 0, 'max': 0, 'display': cost_str}


def normalize_competition(comp_str: str) -> str:
    """Normalize competition level"""
    if not comp_str:
        return 'NONE'
    
    comp_upper = comp_str.upper()
    if 'HIGH' in comp_upper or '8+' in comp_str or 'MAXIMUM' in comp_upper:
        return 'HIGH'
    elif 'MEDIUM' in comp_upper or 'MED' in comp_upper or '4-5' in comp_str:
        return 'MEDIUM'
    elif 'LOW' in comp_upper or '1-3' in comp_str or '1-2' in comp_str:
        return 'LOW'
    elif 'NONE' in comp_upper or comp_str.strip() == '':
        return 'NONE'
    else:
        return comp_str.upper()


def csv_row_to_race_dict(row: Dict[str, str]) -> Dict[str, Any]:
    """Convert a CSV row to race dictionary format"""
    
    # Extract basic info - handle multiple date column formats
    race_name = row.get('Race Name', '').strip()
    location = row.get('Location', '').strip()
    country = row.get('Country', 'USA').strip()
    region = row.get('Region', '').strip()
    
    # Handle date fields - check for Date 2025, Date 2026, or Date/Month
    date = (row.get('Date 2026', '') or row.get('Date 2025', '') or row.get('Date/Month', '')).strip()
    
    distance = row.get('Distance (mi)', '').strip()
    elevation = row.get('Elevation (ft)', '').strip()
    field_size = row.get('Field Size', '').strip()
    entry_cost = row.get('Entry Cost ($)', '').strip()
    tier = row.get('Tier', '').strip()
    competition = row.get('Competition', '').strip()
    protocol_fit = row.get('Protocol Fit', '').strip()
    priority_score = row.get('Priority Score', '').strip()
    notes = row.get('Notes', '').strip()
    data_quality = row.get('Data Quality', '').strip()
    
    # Parse numeric fields
    field_size_int = parse_field_size(field_size)
    elevation_int = parse_elevation(elevation)
    cost_dict = parse_entry_cost(entry_cost)
    competition_normalized = normalize_competition(competition)
    
    # Try to parse priority score
    priority_float = 0.0
    try:
        priority_float = float(priority_score) if priority_score else 0.0
    except:
        pass
    
    # Build race dictionary in the format expected by push_pages.py
    race_dict = {
        # Basic fields (uppercase for compatibility)
        'RACE_NAME': race_name,
        'LOCATION': location,
        'DATE': date,
        'DISTANCE': distance,
        'ELEVATION_GAIN': f"{elevation_int} ft" if elevation_int > 0 else elevation,
        'WEBSITE_URL': '',  # Will need to be filled in separately
        'REGISTRATION_URL': '',  # Will need to be filled in separately
        
        # Extended metadata
        'COUNTRY': country,
        'REGION': region,
        'FIELD_SIZE': field_size_int,
        'FIELD_SIZE_DISPLAY': field_size,
        'ENTRY_COST_MIN': cost_dict['min'],
        'ENTRY_COST_MAX': cost_dict['max'],
        'ENTRY_COST_DISPLAY': cost_dict['display'],
        'TIER': tier,
        'COMPETITION': competition_normalized,
        'PROTOCOL_FIT': protocol_fit,
        'PRIORITY_SCORE': priority_float,
        'NOTES': notes,
        'DATA_QUALITY': data_quality,
        
        # Additional extracted fields
        'IS_UCI_QUALIFIER': 'uci' in notes.lower() if notes else False,
        'IS_CHAMPIONSHIP': any(word in notes.lower() for word in ['championship', 'nationals', 'national']) if notes else False,
        'IS_STAGE_RACE': 'stage race' in notes.lower() or 'multi-day' in notes.lower() if notes else False,
        'HAS_PRIZE_PURSE': 'prize' in notes.lower() or 'purse' in notes.lower() if notes else False,
        
        # Generate description from available data
        'DESCRIPTION': _generate_description(race_name, location, distance, elevation, notes),
        'COURSE_BREAKDOWN': _generate_course_breakdown(race_name, distance, elevation, protocol_fit, notes),
        'RACE_HISTORY': _generate_history(race_name, location, notes),
    }
    
    return race_dict


def _generate_description(race_name: str, location: str, distance: str, elevation: str, notes: str) -> str:
    """Generate a basic description from available data"""
    parts = []
    
    if race_name and location:
        parts.append(f"{race_name} is a gravel cycling race held in {location}.")
    
    # Extract key features from notes
    key_features = []
    if notes:
        notes_lower = notes.lower()
        if 'uci' in notes_lower:
            key_features.append("UCI Gravel World Series qualifier")
        if 'national' in notes_lower or 'championship' in notes_lower:
            key_features.append("national championship event")
        if 'stage race' in notes_lower or 'multi-day' in notes_lower:
            key_features.append("multi-day stage race")
        if 'prize' in notes_lower or 'purse' in notes_lower:
            prize_match = re.search(r'\$?(\d+[Kk]?)', notes)
            if prize_match:
                key_features.append(f"prize purse of ${prize_match.group(1)}")
    
    if key_features:
        parts.append(" ".join(key_features) + ".")
    
    if distance:
        # Clean up distance format
        distance_clean = distance.split('/')[0] if '/' in distance else distance
        parts.append(f"The race features a {distance_clean} course.")
    
    if elevation and elevation.lower() not in ['low', 'unknown', 'various']:
        elevation_clean = elevation.split('/')[0] if '/' in elevation else elevation
        parts.append(f"Riders will face {elevation_clean} of elevation gain.")
    
    if notes:
        # Extract first sentence or key info from notes
        sentences = notes.split('.')
        if sentences and len(sentences[0]) > 30:
            parts.append(sentences[0] + ".")
        elif len(notes) > 50 and len(notes) < 200:
            parts.append(notes)
    
    return " ".join(parts) if parts else f"Information about {race_name} gravel race."


def _generate_course_breakdown(race_name: str, distance: str, elevation: str, protocol_fit: str, notes: str) -> str:
    """Generate course breakdown from available data"""
    parts = []
    
    if distance:
        # Handle multiple distance options
        if '/' in distance:
            distances = distance.split('/')
            parts.append(f"The {race_name} offers multiple distance options: {', '.join(distances)}.")
        else:
            parts.append(f"The {race_name} course covers {distance}.")
    
    if elevation and elevation.lower() not in ['low', 'unknown', 'various']:
        if '/' in elevation:
            elevations = elevation.split('/')
            parts.append(f"Elevation gain ranges from {elevations[-1]} to {elevations[0]}, providing challenging climbs throughout the route.")
        else:
            parts.append(f"Elevation gain totals {elevation}, providing challenging climbs throughout the route.")
    
    if protocol_fit:
        protocol_map = {
            'Altitude': 'The race takes place at high altitude, requiring specialized training for altitude adaptation. Riders should prepare for reduced oxygen availability and increased cardiovascular stress.',
            'Heat': 'Riders will face extreme heat conditions, making hydration and heat management critical. Proper acclimatization and heat training protocols are essential.',
            'Cold': 'The race takes place in cold conditions, requiring proper cold-weather gear and preparation. Riders should be prepared for variable weather and potential snow or freezing temperatures.',
            'Technical': 'The course features technical terrain including challenging descents, rough gravel, singletrack sections, and demanding technical features that require strong bike handling skills.',
            'Standard': 'The course features typical gravel road conditions with a mix of terrain including rolling hills, smooth and rough gravel sections.',
            'Ultra': 'This is an ultra-endurance event requiring exceptional fitness, mental toughness, and strategic pacing. Riders should prepare for extended time in the saddle.',
        }
        
        # Check for multiple protocol fits
        protocol_parts = []
        for key, desc in protocol_map.items():
            if key.lower() in protocol_fit.lower():
                protocol_parts.append(desc)
        
        if protocol_parts:
            parts.extend(protocol_parts)
    
    # Extract course-specific info from notes
    if notes:
        notes_lower = notes.lower()
        course_keywords = ['gravel', 'climb', 'descent', 'terrain', 'road', 'trail', 'singletrack', 'mountain', 'forest']
        if any(keyword in notes_lower for keyword in course_keywords):
            # Extract relevant sentences
            sentences = [s.strip() for s in notes.split('.') if any(kw in s.lower() for kw in course_keywords)]
            if sentences:
                parts.append(sentences[0] + ".")
    
    return " ".join(parts) if parts else f"Course details for {race_name}."


def _generate_history(race_name: str, location: str, notes: str) -> str:
    """Generate race history from available data"""
    parts = []
    
    if notes:
        # Look for historical information in notes
        history_keywords = ['founded', 'established', 'since', 'annual', 'edition', 'anniversary', 'created', 'started', 'first']
        notes_lower = notes.lower()
        
        if any(word in notes_lower for word in history_keywords):
            # Extract year if mentioned
            year_match = re.search(r'\b(19|20)\d{2}\b', notes)
            if year_match:
                year = year_match.group(0)
                parts.append(f"{race_name} was established in {year}.")
            
            # Extract relevant sentences
            sentences = [s.strip() for s in notes.split('.') if any(kw in s.lower() for kw in history_keywords)]
            if sentences:
                parts.append(sentences[0] + ".")
            else:
                # Use first part of notes if it contains history info
                first_sentence = notes.split('.')[0]
                if len(first_sentence) > 30:
                    parts.append(first_sentence + ".")
        
        # Check for series or championship info
        if 'series' in notes_lower or 'championship' in notes_lower or 'qualifier' in notes_lower:
            series_info = []
            if 'uci' in notes_lower:
                series_info.append("UCI Gravel World Series")
            if 'national' in notes_lower:
                series_info.append("National Championship")
            if 'state' in notes_lower:
                series_info.append("State Championship")
            if series_info:
                parts.append(f"{race_name} is part of the {', '.join(series_info)}.")
    
    if not parts:
        parts.append(f"{race_name} is held in {location} and has become a popular event in the gravel cycling community.")
    
    return " ".join(parts)


def parse_csv_file(csv_path: str) -> List[Dict[str, Any]]:
    """Parse a CSV file and convert to race dictionaries"""
    races = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        # Try to detect delimiter
        sample = f.read(1024)
        f.seek(0)
        delimiter = ',' if sample.count(',') > sample.count(';') else ';'
        
        reader = csv.DictReader(f, delimiter=delimiter)
        
        for row in reader:
            # Skip empty rows
            if not row.get('Race Name', '').strip():
                continue
            
            race_dict = csv_row_to_race_dict(row)
            races.append(race_dict)
    
    return races


def create_database_from_csv_files(csv_files: List[str], output_path: str):
    """Create a combined database from multiple CSV files"""
    all_races = []
    
    for csv_file in csv_files:
        print(f"Processing {csv_file}...")
        races = parse_csv_file(csv_file)
        all_races.extend(races)
        print(f"  Added {len(races)} races")
    
    # Create database structure
    database = {
        'races': all_races,
        'metadata': {
            'total_races': len(all_races),
            'source_files': csv_files,
            'generated_by': 'parse_gravel_database.py'
        }
    }
    
    # Save to JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Created database with {len(all_races)} races")
    print(f"  Saved to: {output_path}")
    
    return database


def create_database_from_markdown(markdown_path: str, output_path: str):
    """Extract CSV data from markdown document and create database"""
    
    with open(markdown_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all CSV blocks in markdown (between ```csv and ```)
    csv_pattern = r'```csv\n(.*?)\n```'
    csv_blocks = re.findall(csv_pattern, content, re.DOTALL)
    
    all_races = []
    
    for i, csv_block in enumerate(csv_blocks):
        print(f"Processing CSV block {i+1}...")
        
        # Parse CSV from string
        lines = csv_block.strip().split('\n')
        if len(lines) < 2:
            continue
        
        # Parse header
        reader = csv.DictReader(lines)
        
        for row in reader:
            if not row.get('Race Name', '').strip():
                continue
            
            race_dict = csv_row_to_race_dict(row)
            all_races.append(race_dict)
        
        print(f"  Added {len([r for r in all_races if r])} races from this block")
    
    # Create database structure
    database = {
        'races': all_races,
        'metadata': {
            'total_races': len(all_races),
            'source': markdown_path,
            'generated_by': 'parse_gravel_database.py'
        }
    }
    
    # Save to JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Created database with {len(all_races)} races")
    print(f"  Saved to: {output_path}")
    
    return database


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Parse gravel race database from CSV/Markdown to JSON'
    )
    parser.add_argument('input', help='Input CSV file or Markdown file with CSV blocks')
    parser.add_argument('output', help='Output JSON database file')
    parser.add_argument('--format', choices=['csv', 'markdown', 'auto'], default='auto',
                       help='Input format (auto-detect if not specified)')
    
    args = parser.parse_args()
    
    # Auto-detect format
    if args.format == 'auto':
        if args.input.endswith('.md') or args.input.endswith('.markdown'):
            args.format = 'markdown'
        elif args.input.endswith('.csv'):
            args.format = 'csv'
        else:
            # Try to detect from content
            with open(args.input, 'r', encoding='utf-8') as f:
                sample = f.read(1024)
                if '```csv' in sample:
                    args.format = 'markdown'
                else:
                    args.format = 'csv'
    
    # Parse based on format
    if args.format == 'markdown':
        create_database_from_markdown(args.input, args.output)
    else:
        create_database_from_csv_files([args.input], args.output)


if __name__ == '__main__':
    main()

