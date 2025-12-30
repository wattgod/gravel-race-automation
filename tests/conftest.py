"""Pytest fixtures and configuration."""

import pytest
import sys
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


@pytest.fixture
def sample_research_content():
    """Sample research content that should pass quality gates."""
    return """
# UNBOUND 200 - RAW RESEARCH DUMP

## OFFICIAL DATA
Distance: 200 miles. Elevation: 11,000 ft.
Source: https://unboundgravel.com

## TERRAIN
Flint Hills gravel. Mile 80-95 has the worst rollers.

## WEATHER HISTORY
2023: 103°F. 2022: 95°F with humidity.

## REDDIT DEEP DIVE
u/graveldude said "Mile 130 is where dreams die"
https://reddit.com/r/gravelcycling/comments/abc

## SUFFERING ZONES
Mile 80-95: Teterville rollers. 35% of DNFs happen here.

## DNF DATA
30-40% DNF rate in hot years.

## EQUIPMENT
40mm tires minimum. Run 28-32 psi.

## LOGISTICS
Book Emporia hotels 6 months out.

Sources: https://unboundgravel.com https://youtube.com/watch?v=xyz
"""


@pytest.fixture
def sample_brief_content():
    """Sample brief content that should pass quality gates."""
    return """
# UNBOUND 200 - RACE BRIEF

## RADAR SCORES (1-5 each)

| Variable | Score | Justification |
|----------|-------|---------------|
| Logistics | 3 | Emporia is remote, hotels book 6 months out |
| Length | 5 | 200 miles is brutal |
| Technicality | 2 | Mostly smooth gravel |
| Elevation | 3 | 11,000 ft over 200 miles |
| Climate | 5 | Heat kills - 103°F in 2023 |
| Altitude | 1 | Sea level |
| Adventure | 4 | Flint Hills are epic |

**PRESTIGE: 5/5** - The original gravel race.

## TRAINING PLAN IMPLICATIONS

**Protocol Triggers:**
- Heat Adaptation: Yes - Temps hit 103°F
- Altitude Protocol: No
- Technical Skills: No
- Durability Focus: Yes - Mile 80-95 breaks people
- Fueling Strategy: Yes - Aid stations sparse

**Training Emphasis:**
- Primary: Heat tolerance - Train in heat
- Secondary: Durability - Long rides
- Tertiary: Fueling - Practice eating

**THE ONE THING THAT WILL GET YOU:**
The heat. Your FTP doesn't matter if you overheat at mile 100.

## THE BLACK PILL

Unbound will break you. The truth is 30-40% DNF in hot years. Mile 80-95 is where people quit. The Teterville rollers come when you're already cooked. u/graveldude said it best: "Mile 130 is where dreams die."

## KEY QUOTES

"Mile 130 is where dreams die" - u/graveldude
"103°F and I was done" - u/heatstroke
"The rollers never end" - u/gravelrider

## LOGISTICS SNAPSHOT

Airport: Wichita (90 min drive)
Lodging: Book 6 months out
Packet pickup: Friday before race
Parking: Limited, arrive early
"""


@pytest.fixture
def slop_content():
    """Content with AI slop that should fail quality gates."""
    return """
It's worth noting that this race offers an amazing opportunity for participants.

In conclusion, it's important to note that this is truly a remarkable experience.

When it comes to training, you might want to consider perhaps embracing the challenge.

You've got this! Believe in yourself and unlock your potential on this journey.

The bottom line is that this is a world-class, cutting-edge event that leverages
state-of-the-art facilities to facilitate your endeavor.
"""

