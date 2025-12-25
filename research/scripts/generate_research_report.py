"""
Generate Research Report

Create a comprehensive report of research status for all races.
"""

import json
from collections import defaultdict
from pathlib import Path

def generate_report():
    """Generate comprehensive research report"""
    print("Generating research report...")
    
    # Load database
    with open('gravel_races_full_database.json', 'r') as f:
        db = json.load(f)
    
    races = db.get('races', [])
    
    # Statistics
    stats = {
        'total': len(races),
        'with_websites': 0,
        'with_registration': 0,
        'with_dates': 0,
        'with_field_size': 0,
        'with_entry_cost': 0,
        'enhanced': 0,
        'in_progress': 0,
        'pending': 0,
    }
    
    # By competition level
    by_competition = defaultdict(int)
    by_tier = defaultdict(int)
    by_protocol = defaultdict(int)
    
    # Enhanced races list
    enhanced_races = []
    races_needing_research = []
    
    for race in races:
        race_name = race.get('RACE_NAME', 'Unknown')
        
        # Count statistics
        if race.get('WEBSITE_URL'):
            stats['with_websites'] += 1
        if race.get('REGISTRATION_URL'):
            stats['with_registration'] += 1
        if race.get('DATE'):
            stats['with_dates'] += 1
        if race.get('FIELD_SIZE'):
            stats['with_field_size'] += 1
        if race.get('ENTRY_COST_MIN'):
            stats['with_entry_cost'] += 1
        
        research_status = race.get('RESEARCH_STATUS', 'pending')
        if research_status == 'enhanced':
            stats['enhanced'] += 1
            enhanced_races.append(race_name)
        elif research_status == 'in_progress':
            stats['in_progress'] += 1
        else:
            stats['pending'] += 1
            races_needing_research.append(race_name)
        
        # By category
        comp = race.get('COMPETITION', 'UNKNOWN')
        by_competition[comp] += 1
        
        tier = race.get('TIER', 'UNKNOWN')
        by_tier[tier] += 1
        
        protocol = race.get('PROTOCOL_FIT', 'UNKNOWN')
        by_protocol[protocol] += 1
    
    # Generate report
    report = f"""# Research Status Report

Generated: {Path('gravel_races_full_database.json').stat().st_mtime}

## Overall Statistics

- **Total Races:** {stats['total']}
- **Races with Websites:** {stats['with_websites']} ({stats['with_websites']/stats['total']*100:.1f}%)
- **Races with Registration URLs:** {stats['with_registration']} ({stats['with_registration']/stats['total']*100:.1f}%)
- **Races with Dates:** {stats['with_dates']} ({stats['with_dates']/stats['total']*100:.1f}%)
- **Races with Field Sizes:** {stats['with_field_size']} ({stats['with_field_size']/stats['total']*100:.1f}%)
- **Races with Entry Costs:** {stats['with_entry_cost']} ({stats['with_entry_cost']/stats['total']*100:.1f}%)

## Research Status

- **Enhanced (Complete):** {stats['enhanced']} ({stats['enhanced']/stats['total']*100:.1f}%)
- **In Progress:** {stats['in_progress']} ({stats['in_progress']/stats['total']*100:.1f}%)
- **Pending:** {stats['pending']} ({stats['pending']/stats['total']*100:.1f}%)

## By Competition Level

"""
    
    for comp, count in sorted(by_competition.items(), key=lambda x: -x[1]):
        report += f"- **{comp}:** {count} races ({count/stats['total']*100:.1f}%)\n"
    
    report += "\n## By Tier\n\n"
    for tier, count in sorted(by_tier.items(), key=lambda x: -x[1]):
        report += f"- **Tier {tier}:** {count} races ({count/stats['total']*100:.1f}%)\n"
    
    report += "\n## By Protocol Fit\n\n"
    for protocol, count in sorted(by_protocol.items(), key=lambda x: -x[1]):
        report += f"- **{protocol}:** {count} races ({count/stats['total']*100:.1f}%)\n"
    
    report += f"\n## Enhanced Races ({len(enhanced_races)})\n\n"
    for race_name in sorted(enhanced_races):
        report += f"- {race_name}\n"
    
    report += f"\n## Races Needing Research ({len(races_needing_research)})\n\n"
    report += f"Total: {len(races_needing_research)} races still need research\n"
    report += "\nTop 20 priority races needing research:\n\n"
    for i, race_name in enumerate(races_needing_research[:20], 1):
        report += f"{i}. {race_name}\n"
    
    # Save report
    with open('research/findings/RESEARCH_STATUS_REPORT.md', 'w') as f:
        f.write(report)
    
    print(f"\n✓ Report generated: research/findings/RESEARCH_STATUS_REPORT.md")
    print(f"\nSummary:")
    print(f"  Total races: {stats['total']}")
    print(f"  Enhanced: {stats['enhanced']}")
    print(f"  With websites: {stats['with_websites']}")
    print(f"  With registration: {stats['with_registration']}")
    print(f"  Needing research: {len(races_needing_research)}")

if __name__ == '__main__':
    generate_report()

