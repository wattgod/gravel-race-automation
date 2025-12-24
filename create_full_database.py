"""
Create full gravel race database from all CSV files

Combines all regional CSV files into a single comprehensive JSON database.
"""

import json
import glob
from pathlib import Path
from parse_gravel_database import parse_csv_file


def main():
    """Combine all CSV files into a single database"""
    
    # Find all CSV files
    csv_files = sorted(glob.glob('gravel_races_*.csv'))
    
    if not csv_files:
        print("No CSV files found matching 'gravel_races_*.csv'")
        return
    
    print(f"Found {len(csv_files)} CSV files:")
    for f in csv_files:
        print(f"  - {f}")
    
    # Parse all CSV files
    all_races = []
    for csv_file in csv_files:
        print(f"\nProcessing {csv_file}...")
        races = parse_csv_file(csv_file)
        all_races.extend(races)
        print(f"  Added {len(races)} races")
    
    # Create database structure
    database = {
        'races': all_races,
        'metadata': {
            'total_races': len(all_races),
            'source_files': csv_files,
            'generated_by': 'create_full_database.py',
            'regions': {
                'southeast': len([r for r in all_races if 'southeast' in r.get('REGION', '').lower()]),
                'midwest': len([r for r in all_races if 'midwest' in r.get('REGION', '').lower()]),
                'mountain_west': len([r for r in all_races if 'mountain' in r.get('REGION', '').lower()]),
                'other': len([r for r in all_races if r.get('REGION', '') not in ['Southeast', 'Midwest', 'Mountain West']]),
            }
        }
    }
    
    # Save to JSON
    output_path = 'gravel_races_full_database.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"✓ Created full database with {len(all_races)} races")
    print(f"  Saved to: {output_path}")
    print(f"\n  Regional breakdown:")
    for region, count in database['metadata']['regions'].items():
        print(f"    {region}: {count} races")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()

