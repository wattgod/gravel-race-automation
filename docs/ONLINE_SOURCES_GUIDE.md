# Online Sources for Gravel Race Database Expansion

## Key Resources Discovered

Based on web search, here are the primary sources for expanding the database to 387+ races:

### 1. UCI Gravel World Series
- **URL**: https://ucigravelworldseries.com/en/
- **Events**: 33 events in 2025 across 21 countries
- **Status**: Official UCI qualifiers for World Championships
- **Action**: Visit website to get complete list of all 33 events

### 2. GravelHive
- **URL**: https://www.gravelhive.com/
- **Description**: Global directory of gravel races
- **Features**: Searchable by location, date, difficulty
- **Action**: Browse and extract race listings

### 3. Gravelevents.com
- **URL**: https://gravelevents.com/
- **Description**: Extensive calendar of gravel, bikepacking, and ultracycling events
- **Features**: Filters for country, event type, distance, date
- **Coverage**: North America, Europe, Africa, South America, Asia, Oceania
- **Action**: Use filters to extract races by region

### 4. GravelRank
- **URL**: https://gravelrank.org/
- **Description**: Real-time rankings and database of elite gravel events
- **Focus**: High-caliber events with significant participation
- **Action**: Extract races from rankings database

### 5. I Love Gravel Racing (ILGR)
- **URL**: https://ilovegravelracing.com/
- **Description**: US point series with multiple races
- **Coverage**: United States gravel races
- **Action**: Extract all races in the point series

### 6. The Nxrth
- **URL**: https://www.thenxrth.com/gravel-bike-events
- **Description**: Gravel bike events in Wisconsin, Minnesota, and Upper Peninsula of Michigan
- **Action**: Extract regional events

### 7. Gravalist
- **URL**: https://gravalist.com/
- **Description**: 500km gravel ultra-bikepacking routes worldwide
- **Focus**: Ultra-endurance events
- **Action**: Extract ultra events

### 8. Gravel-Results.com
- **URL**: https://www.gravel-results.com/
- **Description**: Comprehensive results and statistics from numerous races
- **Action**: Extract race listings from results database

### 9. CyclingNews Gravel Races
- **URL**: https://www.cyclingnews.com/gravel-races/
- **Description**: Updated list of gravel races with event details
- **Action**: Extract from race calendar

### 10. Gran Fondo Rank
- **URL**: https://www.granfondorank.cc/
- **Description**: Database of cycling race results
- **Action**: Extract gravel events from database

## Extraction Strategy

### Phase 1: UCI Gravel World Series (Priority)
1. Visit https://ucigravelworldseries.com/en/
2. Extract all 33 events with:
   - Race name
   - Location (city, country)
   - Date
   - Field size (if available)
   - Entry cost (if available)

### Phase 2: Major Platforms
1. **GravelHive**: Browse by region, extract race details
2. **Gravelevents.com**: Use filters to extract by:
   - Country
   - Date range
   - Event type
3. **GravelRank**: Extract elite events from rankings

### Phase 3: Regional Sources
1. **ILGR**: Extract all point series races
2. **The Nxrth**: Extract Wisconsin/Minnesota/Michigan events
3. **Gravalist**: Extract ultra-bikepacking events

### Phase 4: Results Databases
1. **Gravel-Results.com**: Extract races from results
2. **Gran Fondo Rank**: Extract gravel events

## Data to Extract for Each Race

When extracting from online sources, collect:

```csv
Race Name,Location,Country,Region,Date/Month,Distance (mi),Elevation (ft),Field Size,Entry Cost ($),Tier,Competition,Protocol Fit,Priority Score,Notes,Data Quality
```

**Required Fields:**
- Race Name
- Location (city, state/country)
- Date/Month
- Country
- Region

**Optional but Valuable:**
- Distance
- Elevation
- Field Size
- Entry Cost
- Tier (estimate based on field size/prestige)
- Competition (estimate: HIGH/MEDIUM/LOW/NONE)
- Protocol Fit (Altitude/Heat/Cold/Technical/Standard/Ultra)
- Priority Score (0-10)
- Notes

## Automated Extraction (Future)

Consider creating web scrapers for:
1. UCI Gravel World Series website
2. Gravelevents.com (if they have an API)
3. GravelHive (if they have an API)

## Manual Extraction Workflow

1. **Visit each source website**
2. **Extract race information** into CSV format
3. **Save to new CSV file** (e.g., `gravel_races_online_sources.csv`)
4. **Run database builder**:
   ```bash
   python3 create_full_database.py
   ```

## Current Status

- **Database**: 246 races
- **Target**: 387+ races
- **Remaining**: ~141 races
- **Sources Identified**: 10+ comprehensive platforms
- **Next Step**: Extract races from UCI Gravel World Series (33 events) and major platforms

## Quick Start

To quickly add races:

1. **Start with UCI Gravel World Series** (highest priority):
   - Visit: https://ucigravelworldseries.com/en/
   - Extract all 33 events
   - Add to CSV file

2. **Then GravelHive**:
   - Visit: https://www.gravelhive.com/
   - Browse by region
   - Extract missing races

3. **Then Gravelevents.com**:
   - Visit: https://gravelevents.com/
   - Use filters to find races not yet in database
   - Extract race details

4. **Run database update**:
   ```bash
   python3 create_full_database.py
   ```

This should get you close to or exceed the 387+ target!

