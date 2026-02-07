# Gravel Race Database - Setup and Usage

This directory contains tools and data for managing the comprehensive gravel race database for the WordPress publishing system.

## Files Created

### Database Files
- `gravel_races_full_database.json` - Complete JSON database with all races (currently 95 races from 3 regions)
- `gravel_races_southeast.csv` - 25 races from US Southeast
- `gravel_races_midwest.csv` - 44 races from US Upper Midwest  
- `gravel_races_mountain_west.csv` - 26 races from US Mountain West

### Scripts
- `parse_gravel_database.py` - Converts CSV files to JSON database format
- `create_full_database.py` - Combines all CSV files into a single JSON database

## Current Status

✅ **Completed:**
- US Southeast: 25 races
- US Upper Midwest: 44 races  
- US Mountain West: 26 races
- **Total: 95 races**

⏳ **Remaining to Add:**
- US Other Regions: 24 races
- UK/Europe: 24 races
- Australia/Canada: 18 races
- Must-Add Races: 5 races
- **Total Remaining: ~71 races**

## Usage

### Adding More Races

1. **Create CSV file** for the new region (or add to existing):
   ```csv
   Race Name,Location,Country,Region,Date/Month,Distance (mi),Elevation (ft),Field Size,Entry Cost ($),Tier,Competition,Protocol Fit,Priority Score,Notes,Data Quality
   ```

2. **Run the database builder**:
   ```bash
   python3 create_full_database.py
   ```

   This will automatically:
   - Find all `gravel_races_*.csv` files
   - Parse each CSV file
   - Combine into `gravel_races_full_database.json`

### Using with WordPress Publishing System

The generated JSON database is compatible with `push_pages.py`:

```bash
python3 push_pages.py \
  --template templates/template-master.json \
  --races gravel_races_full_database.json
```

## Database Structure

Each race in the JSON database contains:

```json
{
  "RACE_NAME": "Race Name",
  "LOCATION": "City, State",
  "DATE": "Month/Day",
  "DISTANCE": "100 miles",
  "ELEVATION_GAIN": "5000 ft",
  "WEBSITE_URL": "",
  "REGISTRATION_URL": "",
  "COUNTRY": "USA",
  "REGION": "Southeast",
  "FIELD_SIZE": 1000,
  "FIELD_SIZE_DISPLAY": "1000+",
  "ENTRY_COST_MIN": 75,
  "ENTRY_COST_MAX": 100,
  "ENTRY_COST_DISPLAY": "75-100",
  "TIER": "2",
  "COMPETITION": "LOW",
  "PROTOCOL_FIT": "Technical",
  "PRIORITY_SCORE": 9.5,
  "NOTES": "Additional notes...",
  "DATA_QUALITY": "Verified",
  "DESCRIPTION": "Auto-generated description...",
  "COURSE_BREAKDOWN": "Auto-generated course breakdown...",
  "RACE_HISTORY": "Auto-generated history..."
}
```

## Field Mappings

The parser automatically:
- Parses field sizes (handles ranges, `<`, `+`, etc.)
- Parses elevation (handles ranges, `+`, etc.)
- Parses entry costs (extracts min/max)
- Normalizes competition levels (HIGH/MEDIUM/LOW/NONE)
- Generates descriptions, course breakdowns, and history from available data

## Next Steps

1. **Add remaining CSV files** for:
   - US Other Regions (24 races)
   - UK/Europe (24 races)
   - Australia/Canada (18 races)
   - Must-Add Races (5 races)

2. **Enhance data quality**:
   - Add website URLs where available
   - Add registration URLs
   - Enhance auto-generated descriptions with more detail
   - Add RideWithGPS IDs for map embeds

3. **Test with WordPress**:
   - Run dry-run to preview placeholder replacements
   - Push test pages
   - Verify Elementor rendering

## Notes

- The parser handles various formats for field sizes, elevation, and costs
- Competition levels are normalized to: HIGH, MEDIUM, LOW, NONE
- Descriptions and course breakdowns are auto-generated but can be enhanced manually
- Website and registration URLs need to be added separately (not in original CSV data)

