# Research Repository - Started ✅

## Status: Research Framework Complete

Research repository structure created and ready for systematic research of all 388 races.

## Repository Structure

```
research/
├── README.md                          # Main research guide
├── top_priority/                      # Top 8 priority races
│   ├── research_top_priority_races.json
│   └── research_findings.md
├── by_region/                         # Regional research plans
│   └── research_plan.md
├── by_protocol/                       # Protocol-specific research
│   ├── altitude_races_research.md
│   ├── heat_races_research.md
│   └── zero_competition_batch_*.json (6 batches)
├── uci_series/                        # UCI Gravel World Series
│   └── uci_gravel_world_series.json
├── findings/                          # Research progress tracking
│   └── research_progress.json
└── scripts/                           # Research automation
    ├── research_automation.py
    └── update_database_from_research.py
```

## Research Phases

### Phase 1: Top Priority Races (8 races) - IN PROGRESS
- ✅ Research templates created
- ⏳ Research in progress
- **Target:** Complete website URLs, registration, dates for all 8

### Phase 2: Zero Competition Races (265 races) - READY
- ✅ Batched into 6 files (50 races each)
- ⏳ Ready for systematic research
- **Target:** Complete data for all 265 zero-competition races

### Phase 3: UCI Gravel World Series (33 events) - READY
- ✅ Batch file created (25 races found)
- ⏳ Ready for research
- **Target:** Complete UCI series coverage

### Phase 4: Protocol-Specific Races - READY
- ✅ Altitude races research plan
- ✅ Heat races research plan
- ⏳ Ready for protocol-specific research

## Research Fields

For each race, research:
- [ ] Official website URL
- [ ] Registration URL
- [ ] Confirmed 2026 date
- [ ] Actual field size
- [ ] Current entry cost
- [ ] RideWithGPS route ID
- [ ] Course description
- [ ] Elevation profile
- [ ] Prize purse (if applicable)

## Research Sources

1. **Official Race Websites** (primary)
2. **BikeReg.com** (registration platform)
3. **GravelHive.com** (race directory)
4. **Gravelevents.com** (event calendar)
5. **UCI Official Listings** (for UCI events)
6. **Race Social Media** (Instagram, Facebook)
7. **Cycling News Sites** (race announcements)

## Next Steps

1. **Start with Top 8 Priority Races**
   - Research official websites
   - Get registration URLs
   - Confirm 2026 dates
   - Update research JSON files

2. **Then Zero Competition Batches**
   - Work through batches 1-6
   - Research 50 races per batch
   - Update database as you go

3. **Then UCI Series**
   - Complete all 33 UCI events
   - Verify qualifier status
   - Get official dates

4. **Update Database**
   - Use `update_database_from_research.py`
   - Commit research findings
   - Track progress

## Research Tools Created

- ✅ Research templates for top priority races
- ✅ Batch files for zero-competition races (6 batches)
- ✅ UCI series batch file
- ✅ Protocol-specific research plans
- ✅ Database update script
- ✅ Progress tracking system

## Statistics

- **Total Races:** 388
- **Zero Competition:** 265 (68%)
- **Top Priority (10/10):** 4 races
- **UCI Events:** 33 events
- **Research Files Created:** 14 files
- **Research Batches:** 7 batches

## Research Workflow

1. **Pick a batch** (start with top_priority)
2. **Research each race** using sources above
3. **Update research JSON** with findings
4. **Run update script** to update main database
5. **Commit changes** to git
6. **Move to next batch**

## Files Ready for Research

All research files are created and ready. Start with:
- `research/top_priority/research_top_priority_races.json` (8 races)
- Then move to zero-competition batches
- Then UCI series
- Then protocol-specific races

**Research repository is complete and ready for systematic research!** 🚀

