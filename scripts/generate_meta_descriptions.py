#!/usr/bin/env python3
"""Generate meta-descriptions.json for WordPress AIOSEO override.

Produces seo/meta-descriptions.json with meta descriptions for all WordPress
pages and posts. All entries are hand-crafted — race guide pages preserve
source=race-data linkage for cross-referencing with race-data JSON.

Usage:
    python scripts/generate_meta_descriptions.py             # Generate JSON
    python scripts/generate_meta_descriptions.py --dry-run   # Show without writing
    python scripts/generate_meta_descriptions.py --stats     # Show statistics
    python scripts/generate_meta_descriptions.py --validate  # Run validation checks
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_FILE = PROJECT_ROOT / "seo" / "meta-descriptions.json"

# ── Race guide entries: hand-crafted with race-data linkage ───────────
# Format: (wp_id, wp_slug, race_data_slug, description, focus_keyword)
# Each description uses the race's personality — no templates, no filler.

RACE_GUIDE_ENTRIES = [
    (4993, "barry-roubaix-race-guide", "barry-roubaix",
     "Barry-Roubaix race guide: Michigan's frozen-mud classic with 1,000+ starters. Tier 3, 53/100. Big field energy, modest everything else.",
     "Barry-Roubaix"),
    (4994, "belgian-waffle-ride-race-guide", "bwr-california",
     "Belgian Waffle Ride race guide: 130 miles where bike handling outweighs FTP. Tier 1, 81/100. 40% DNF rate. You've been warned.",
     "Belgian Waffle Ride"),
    (4995, "big-horn-gravel-race-guide", "big-horn-gravel",
     "Big Horn Gravel race guide: Colorado's rowdiest course where pros switch to hardtails. Tier 2, 73/100. The opening wall is personal.",
     "Big Horn Gravel"),
    (4996, "big-sugar-race-guide", "big-sugar",
     "Big Sugar race guide: the Life Time Grand Prix finale in the Ozarks. Tier 1, 80/100. Where seasons end and titles are decided.",
     "Big Sugar"),
    (4997, "bwr-cedar-city-race-guide", "bwr-cedar-city",
     "BWR Cedar City race guide: half the climbing of San Diego, all the suffering, plus playground sand. Tier 2, 77/100.",
     "BWR Cedar City"),
    (4998, "crusher-tushar-race-guide", "crusher-in-the-tushar",
     "Crusher in the Tushar race guide: 70 miles, 10,000 ft of climbing, finish at 10,400 ft. Tier 1, 86/100. Thin air decides everything.",
     "Crusher in the Tushar"),
    (4999, "dirty-reiver-race-guide", "dirty-reiver",
     "Dirty Reiver race guide: 200km through Kielder Forest in weather that doesn't negotiate. Tier 1, 77/100. Britain's original.",
     "Dirty Reiver"),
    (5000, "gravel-locos-race-guide", "gravel-locos",
     "Gravel Locos race guide: free 150-mile Unbound tune-up on gorgeous Texas gravel. Tier 2, 79/100. Texas heat is the great equalizer.",
     "Gravel Locos"),
    (5001, "gravel-worlds-race-guide", "gravel-worlds",
     "Gravel Worlds race guide: 150 miles of Nebraska rollers, pirate swords for winners. Tier 1, 79/100. Grassroots gravel at its finest.",
     "Gravel Worlds"),
    (5002, "leadville-trail-100-mtb-race-guide", "leadville-100",
     "Leadville 100 MTB race guide: 100 miles at 10,000+ feet. The belt buckle that defines the sport. Tier 1, 89/100.",
     "Leadville 100 MTB"),
    (5003, "mid-south-race-guide", "mid-south",
     "Mid South race guide: Oklahoma's weather lottery with the biggest heart in gravel. Tier 1, 76/100. Mud, wind, or heat. Pick two.",
     "Mid South"),
    (5004, "migration-gravel-race-race-guide", "migration-gravel-race",
     "Migration Gravel Race guide: four days through Kenya's Maasai Mara with zebras on course. Tier 2, 74/100. Not your local gravel.",
     "Migration Gravel Race"),
    (5005, "ned-gravel-race-guide", "ned-gravel",
     "Ned Gravel race guide: high-altitude Front Range gravel starting at 8,000 ft with ghost towns. Tier 2, 63/100. Small but honest.",
     "Ned Gravel"),
    (5006, "oregon-trail-gravel-race-guide", "oregon-trail-gravel",
     "Oregon Trail Gravel Grinder race guide: five stages across Central Oregon. Tier 2, 76/100. The Grand Tour of American gravel.",
     "Oregon Trail Gravel"),
    (5007, "rebeccas-private-idaho-race-guide", "rebeccas-private-idaho",
     "Rebecca's Private Idaho race guide: 100 miles through the Pioneer Mountains. Tier 1, 80/100. A pilgrimage, not just a race.",
     "Rebecca's Private Idaho"),
    (5008, "rooted-vermont-race-guide", "rooted-vermont",
     "Rooted Vermont race guide: rolling-to-mountainous gravel in Morrisville. Tier 3, 50/100. Pretty views, modest resume.",
     "Rooted Vermont"),
    (5009, "sbt-grvl-race-guide", "steamboat-gravel",
     "SBT GRVL race guide: champagne gravel at altitude in Steamboat Springs. Tier 1, 80/100. Festival vibes that don't ruin the racing.",
     "SBT GRVL"),
    (5010, "sea-otter-gravel-race-guide", "sea-otter-gravel",
     "Sea Otter Gravel race guide: a race wrapped in North America's biggest bike festival. Tier 2, 74/100. Experience over competition.",
     "Sea Otter Gravel"),
    (5011, "the-rad-race-guide", "rad-dirt-fest",
     "Rad Dirt Fest race guide: champagne gravel and Spanish Peaks views with a 31-mile no-service gap. Tier 2, 71/100. Pack accordingly.",
     "Rad Dirt Fest"),
    (5012, "the-rift-race-guide", "the-rift",
     "The Rift race guide: 200km across Iceland's volcanic highlands with river crossings. Tier 2, 74/100. Gravel's most alien course.",
     "The Rift"),
    (5013, "traka-360-race-guide", "the-traka",
     "Traka 360 race guide: 360km of Catalan gravel from dawn to dawn. Tier 1, 84/100. Europe's Unbound, with Garmin Hill at km 300.",
     "Traka 360"),
    (5014, "unbound-200-race-guide", "unbound-200",
     "Unbound 200 race guide: 200 miles through the Kansas Flint Hills. Tier 1, 80/100. The race by which all others are measured.",
     "Unbound 200"),
]

# Skipped pages (noindexed utility pages)
SKIP_IDS = {3938, 3246, 3245, 3244}  # cart, instructor-reg, student-reg, dashboard

MAX_DESC_LENGTH = 160
MIN_DESC_LENGTH = 50
MAX_TITLE_LENGTH = 60
MIN_TITLE_LENGTH = 30

# ── Title overrides: keyword-forward, 30-60 chars, "{Topic} | Gravel God" ──
# Indexed by wp_id. Every entry in RACE_GUIDE_ENTRIES and MANUAL_ENTRIES
# should have a corresponding title here.

TITLE_MAP = {
    # ── Race Guide Pages ──
    4993: "Barry-Roubaix Race Guide | Gravel God",
    4994: "Belgian Waffle Ride Race Guide | Gravel God",
    4995: "Big Horn Gravel Race Guide | Gravel God",
    4996: "Big Sugar Race Guide | Gravel God",
    4997: "BWR Cedar City Race Guide | Gravel God",
    4998: "Crusher in the Tushar Race Guide | Gravel God",
    4999: "Dirty Reiver Race Guide | Gravel God",
    5000: "Gravel Locos Race Guide | Gravel God",
    5001: "Gravel Worlds Race Guide | Gravel God",
    5002: "Leadville 100 MTB Race Guide | Gravel God",
    5003: "Mid South Race Guide | Gravel God",
    5004: "Migration Gravel Race Guide | Gravel God",
    5005: "Ned Gravel Race Guide | Gravel God",
    5006: "Oregon Trail Gravel Race Guide | Gravel God",
    5007: "Rebecca's Private Idaho Race Guide | Gravel God",
    5008: "Rooted Vermont Race Guide | Gravel God",
    5009: "SBT GRVL Race Guide | Gravel God",
    5010: "Sea Otter Gravel Race Guide | Gravel God",
    5011: "Rad Dirt Fest Race Guide | Gravel God",
    5012: "The Rift Race Guide | Gravel God",
    5013: "Traka 360 Race Guide | Gravel God",
    5014: "Unbound 200 Race Guide | Gravel God",

    # ── Core Pages ──
    448: "Gravel Race Database & Training Plans | Gravel God",
    451: "Contact & Support | Gravel God",
    470: "The Ultimate Gravel Cycling Guide | Gravel God",
    5016: "Gravel Training Plans | Gravel God",
    5017: "Training Plan Questionnaire | Gravel God",
    5018: "Gravel Race Database | Gravel God",
    5042: "Gravel Cycling Resources | Gravel God",
    5043: "Gravel Cycling Coaching | Gravel God",
    5045: "Gravel Cycling Articles | Gravel God",

    # ── Training Content Pages ──
    5027: "Popular Gravel Training Plans | Gravel God",
    5029: "Anaerobic Assessment for Cycling | Gravel God",
    5030: "Training and Relationships | Gravel God",
    5031: "Aerobic Endurance Test | Gravel God",
    5032: "How to Improve Cycling Performance | Gravel God",
    5033: "Frequency, Duration & Intensity | Gravel God",
    5034: "TrainingPeaks Training Zones | Gravel God",
    5035: "Aerobic Threshold Assessment | Gravel God",
    5036: "How Much Faster Could You Be? | Gravel God",
    5037: "Custom Gravel Training Plans | Gravel God",
    5038: "Is Cycling Coaching Worth It? | Gravel God",
    5039: "Training Plans FAQ | Gravel God",

    # ── Standalone Race Pages ──
    5019: "Barry-Roubaix Gravel Race | Gravel God",
    5020: "SBT GRVL Steamboat Springs | Gravel God",
    5021: "Belgian Waffle Ride | Gravel God",
    5022: "Mid South Gravel Race | Gravel God",
    5023: "Unbound Gravel 200 Breakdown | Gravel God",
    5026: "Unbound 200 Gravel Race | Gravel God",
    5028: "Crusher in the Tushar | Gravel God",

    # ── Other Pages ──
    5024: "Gravel Cycling Services | Gravel God",
    5025: "Gravel God Cycling Values | Gravel God",
    5040: "TrainingPeaks User Guide | Gravel God",
    5041: "TrainingPeaks Athlete Guide | Gravel God",

    # ── Blog Posts: Race Reports ──
    1923: "Belgian Waffle Ride Race Report | Gravel God",
    1964: "Unbound 200 Race Report | Gravel God",
    2065: "Gunni Grinder Race Report | Gravel God",
    2209: "Red Granite Grinder Race Report | Gravel God",
    2324: "SBT GRVL Race Report | Gravel God",
    2790: "Iron Horse Classic Race Report | Gravel God",
    2844: "Red Granite Grinder Part Two | Gravel God",
    3203: "Unbound 200 Best Bike Split Pacing | Gravel God",
    3353: "CO2UT Race Report | Gravel God",
    3433: "Unbound 200 Clean Ride Report | Gravel God",
    3483: "Ned Gravel Race Report | Gravel God",
    3504: "FoCo Fondo Race Report | Gravel God",
    3520: "SBT GRVL Redemption Ride | Gravel God",
    3537: "Red Granite Grinder Part Three | Gravel God",
    3749: "Unbound 2024 Race Report | Gravel God",
    3796: "Big Horn Gravel Race Report | Gravel God",

    # ── Blog Posts: Tour of the Gila (2024) ──
    3631: "Tour of the Gila Stage 3 | Gravel God",
    3641: "Tour of the Gila Stage 2 | Gravel God",
    3653: "Tour of the Gila Stage 1 | Gravel God",
    3662: "Tour of the Gila Stage 4 | Gravel God",
    3673: "Tour of the Gila Stage 5 | Gravel God",

    # ── Blog Posts: Tour of the Gila (2023) ──
    3278: "Gila Tyrone Time Trial | Gravel God",
    3281: "Gila Inner Loop Road Race | Gravel God",
    3297: "Gila Silver City Criterium | Gravel God",
    3306: "Gila Monster Stage Report | Gravel God",
    3335: "Gila Mogollon Stage Report | Gravel God",

    # ── Blog Posts: The Double ──
    2552: "The Double: Day 1 | Gravel God",
    2563: "The Double: Day 2 | Gravel God",
    2592: "The Double: Day 3 | Gravel God",
    2608: "The Double: Day 4 | Gravel God",
    2623: "The Double: Day 5 | Gravel God",
    2635: "The Double: Day 6 | Gravel God",
    2649: "The Double: Day 8 | Gravel God",
    2663: "The Double: Day 9 | Gravel God",
    2673: "The Double: Day 10 | Gravel God",
    2684: "The Double: Day 11 | Gravel God",
    2696: "The Double: Day 12 | Gravel God",
    2716: "The Double: Day 13 | Gravel God",

    # ── Blog Posts: Training & Mindset ──
    2014: "Gravel Race Hydration Guide | Gravel God",
    2161: "Dopamine and Cycling Performance | Gravel God",
    2191: "Train Your Heart for Cycling | Gravel God",
    2298: "Cycling Goal Setting | Gravel God",
    2394: "Training Consistency | Gravel God",
    2414: "The Racing Mindset Switch | Gravel God",
    2445: "Your Frame of Reference | Gravel God",
    2469: "How to Do Cycling Workouts Right | Gravel God",
    2521: "HRV for Endurance Athletes | Gravel God",
    2904: "Athletic Advice BS Detector | Gravel God",
    2927: "Stop Sandbagging Your Goals | Gravel God",
    2942: "Holiday Training Guide | Gravel God",
    2956: "Masters Cycling Advantage | Gravel God",
    1269: "Beer and Cycling Performance | Gravel God",
    1431: "Cross-Training for Cyclists | Gravel God",
    1499: "Cycling Nutrition Habits | Gravel God",
    1533: "Talent vs. Work in Cycling | Gravel God",
    1626: "Power Meter Mistakes | Gravel God",
    915: "Strength Training for Cyclists | Gravel God",

    # ── Blog Posts: Reviews & Analysis ──
    901: "WHOOP Review for Cyclists | Gravel God",
    1078: "Do You Need a Power Meter? | Gravel God",
    1186: "Why Did Tom Dumoulin Retire? | Gravel God",
    1230: "In Defense of FTP | Gravel God",
    1496: "How to Measure Cycling Fitness | Gravel God",
    4060: "FasCat AI Coaching Review | Gravel God",

    # ── Blog Posts: Culture & Philosophy ──
    922: "The Tao of Tom — Cycling Mentor | Gravel God",
    1673: "Sportsmanship in Gravel Racing | Gravel God",
    1879: "Humility Precedes Mastery | Gravel God",
    2345: "Gratitude in Cycling | Gravel God",
    2830: "Irony in Cycling Culture | Gravel God",
    2916: "End of Cycling Season | Gravel God",
    3581: "Cycling Work Ethic | Gravel God",
    3594: "Eight Years of Coaching Nate | Gravel God",
    3617: "Yoga for Cyclists | Gravel God",
    3694: "Lessons from Silver City | Gravel God",
    3791: "Stay Present on the Bike | Gravel God",
    3811: "Cycling Daily Habits | Gravel God",
    3825: "Cycling Injury Recovery | Gravel God",
    3945: "Cycling Motivation | Gravel God",
}


# ── Manual entries: hand-crafted meta descriptions ─────────────────────
# Format: (wp_id, wp_type, slug, description, og_description, focus_keyword)

MANUAL_ENTRIES = [
    # ── Core Pages ──
    (448, "page", "home",
     "Gravel cycling data, coaching, and training plans. 328 races rated and ranked on 14 criteria. Built for cyclists who take gravel seriously.",
     "Gravel cycling data, coaching, and training plans. 328 races rated and ranked on 14 criteria.",
     "gravel cycling"),
    (451, "page", "contact",
     "Contact Gravel God with questions about races, training plans, coaching, or the race database. We respond to everything.",
     None, "contact gravel god"),
    (470, "page", "the-ultimate-gravel-guide",
     "The definitive gravel cycling guide: bike setup, training, nutrition, race strategy, and everything between the start and finish line.",
     None, "gravel cycling guide"),
    (5016, "page", "training-plans",
     "Gravel training plans built for your goal race. 16-week periodized programs with race-specific prep. Data-driven. From $15/week.",
     "Gravel training plans built for your goal race. 16-week periodized programs with race-specific prep.",
     "gravel training plans"),
    (5017, "page", "questionnaire",
     "Training plan questionnaire: tell us your cycling background, goals, and target race. Your answers build a plan tailored to your life.",
     None, "training plan questionnaire"),
    (5018, "page", "gravel-races",
     "Search, filter, and compare 328 gravel races worldwide. Rated on 14 criteria including prestige, terrain, and logistics.",
     "Search and compare 328 gravel races worldwide. Rated on 14 criteria including prestige, terrain, and logistics.",
     "gravel races"),
    (5042, "page", "resources",
     "Gravel cycling resources: race calendars, training tools, nutrition calculators, and recommended gear from real experience.",
     None, "gravel cycling resources"),
    (5043, "page", "coaching",
     "Gravel cycling coaching: structured training, race strategy, and honest feedback from a real coach. Plans from $199 every 4 weeks.",
     "Gravel cycling coaching with structured training and race strategy. Plans from $199 every 4 weeks.",
     "gravel cycling coaching"),
    (5045, "page", "articles",
     "Gravel cycling articles: race reports, training insights, and analysis. First-person accounts from the start line to the finish.",
     None, "gravel cycling articles"),

    # ── Training Content Pages ──
    (5027, "page", "popular-training-plans",
     "Browse popular gravel training plans by race. Unbound, Mid South, Crusher, BWR, and more. Each plan is race-specific.",
     None, "gravel training plans"),
    (5029, "page", "the-anaerobic-assessment-2",
     "Anaerobic assessment for cycling: structured 30-second and 1-minute efforts to test your capacity. Know where you stand.",
     None, "anaerobic assessment"),
    (5030, "page", "how-to-make-sure-training-doesnt-destroy-your-relationship",
     "Cycling and relationships: how to train seriously without wrecking your partnership. Practical advice for athletes with lives.",
     None, "cycling and relationships"),
    (5031, "page", "the-aerobic-endurance-test",
     "Aerobic endurance test: a structured field protocol to assess your engine before building your training plan.",
     None, "aerobic endurance test"),
    (5032, "page", "how-to-improve-at-anything",
     "How to improve cycling performance through deliberate practice: feedback loops, progressive overload, and focused work.",
     None, "improve cycling performance"),
    (5033, "page", "the-big-three-frequency-duration-and-intensity",
     "Frequency, duration, and intensity: the three training variables that determine your fitness. Master them and you master cycling.",
     None, "training variables"),
    (5034, "page", "how-and-why-to-set-your-training-zones-in-trainingpeaks",
     "Set TrainingPeaks training zones correctly. Why it matters, how to do it, and the mistakes most athletes make.",
     None, "TrainingPeaks training zones"),
    (5035, "page", "the-assessment-aerobic-6",
     "The aerobic threshold assessment: a structured protocol to find your Zone 2 ceiling and build endurance training around it.",
     None, "aerobic threshold assessment"),
    (5036, "page", "how-much-faster-could-you-be",
     "Faster gravel cycling: how much faster could you be? A realistic breakdown of where time gains come from with structured training.",
     None, "faster gravel cycling"),
    (5037, "page", "custom-training-plans",
     "Custom gravel training plans built around your schedule, your race, and your physiology. Not a template. A real plan.",
     None, "custom gravel training plan"),
    (5038, "page", "is-coaching-worth-it",
     "Is cycling coaching worth it? An honest breakdown of when coaching works, when it doesn't, and who actually benefits.",
     None, "cycling coaching worth it"),
    (5039, "page", "training-plans-faq",
     "Training plan FAQ: how they work, what's included, how to adjust for life, and what happens when things go sideways.",
     None, "training plan FAQ"),

    # ── Standalone Race Pages (hand-crafted to avoid duplicating race-guide descriptions) ──
    (5019, "page", "barry-roubaix",
     "Barry-Roubaix: the world's largest gravel race in Hastings, Michigan. What the mud, cold, and chaos feel like from the inside.",
     None, "Barry-Roubaix"),
    (5020, "page", "sbt-grvl",
     "SBT GRVL in Steamboat Springs: champagne gravel at 7,000 feet. What the altitude does to your legs and how to manage it.",
     None, "SBT GRVL"),
    (5021, "page", "belgian-waffle-ride",
     "Belgian Waffle Ride: 130 miles of Southern California gravel with 10,000+ feet of climbing. Course strategy and pacing traps.",
     None, "Belgian Waffle Ride"),
    (5022, "page", "mid-south",
     "Mid South: the race that throws mud, wind, and heat at you on the same day. Course breakdown and survival strategy.",
     None, "Mid South"),
    (5023, "page", "unbound-200-2",
     "Unbound Gravel 200 race breakdown: 200 miles through the Kansas Flint Hills. Pacing, nutrition timing, and the wall at mile 150.",
     None, "Unbound Gravel 200"),
    (5026, "page", "unbound-200",
     "Unbound 200: everything about 200 miles of Kansas Flint Hills gravel. What the heat, wind, and distance actually demand.",
     None, "Unbound 200"),
    (5028, "page", "crusher-in-the-tushar",
     "Crusher in the Tushar: 70 miles of Utah mountain roads above 10,000 feet. Pacing strategy for the altitude and the climb.",
     None, "Crusher in the Tushar"),

    # ── Other Pages ──
    (5024, "page", "articles-2",
     "Gravel cycling services: coaching, custom training plans, consulting, and race preparation for every level of cyclist.",
     None, "gravel cycling services"),
    (5025, "page", "gravel-god-cycling-values",
     "Gravel God values: honest coaching, data-driven training, and respect for the athletes doing the actual work.",
     None, "gravel god values"),
    (5040, "page", "trainingpeaks-athlete-user-guide-2",
     "TrainingPeaks user guide: how to read your dashboard, interpret metrics, and get the most from your training plan.",
     None, "TrainingPeaks user guide"),
    (5041, "page", "trainingpeaks-athlete-user-guide",
     "TrainingPeaks guide for athletes: dashboard, metrics, compliance, and how to communicate effectively with your coach.",
     None, "TrainingPeaks guide"),

    # ── Blog Posts: Race Reports ──
    (1923, "post", "i-screwed-up-belgian-waffle-ride-so-you-dont-have-to",
     "Belgian Waffle Ride race report: what went wrong, what I learned, and what you should do differently on 130 miles of SoCal gravel.",
     None, "Belgian Waffle Ride race report"),
    (1964, "post", "i-screwed-up-unbound-gravel-200-so-you-dont-have-to",
     "Unbound 200 race report: the mistakes I made across 200 miles of Kansas Flint Hills gravel, so you can avoid them.",
     None, "Unbound 200 race report"),
    (2065, "post", "i-screwed-up-gunni-grinder-so-you-dont-have-to",
     "Gunni Grinder race report: pacing mistakes, altitude miscalculations, and lessons from Colorado's high-country gravel.",
     None, "Gunni Grinder race report"),
    (2209, "post", "i-didnt-screw-up-red-granite-grinder-and-neither-do-you",
     "Red Granite Grinder race report: how to execute a clean gravel race when everything finally goes according to plan.",
     None, "Red Granite Grinder race report"),
    (2324, "post", "i-screwed-up-sbt-grvl-so-you-dont-have-to",
     "SBT GRVL race report: altitude missteps in Steamboat Springs and the pacing lessons I keep learning the hard way.",
     None, "SBT GRVL race report"),
    (2790, "post", "i-screwed-up-the-ironhorse-classic-so-you-dont-have-to",
     "Iron Horse race report: what happens when ego writes checks your legs can't cash on Durango's climbs at the Bicycle Classic.",
     None, "Iron Horse race report"),
    (2844, "post", "i-didnt-screw-up-red-granite-grinder-again-and-neither-do-you",
     "Red Granite Grinder race report, part two: another clean execution and more proof that consistency beats heroics.",
     None, "Red Granite Grinder"),
    (3203, "post", "hacking-unbound-200-with-best-bike-split",
     "Best Bike Split for Unbound 200: how to build a data-driven pacing strategy for 200 miles of Kansas gravel.",
     None, "Best Bike Split"),
    (3353, "post", "i-screwed-up-co2ut-so-you-dont-have-to",
     "CO2UT race report: cracking in the Colorado heat and the hydration mistakes that turned a good day into a survival march.",
     None, "CO2UT race report"),
    (3433, "post", "i-didnt-screw-up-unbound-200-and-you-dont-have-to-either",
     "Unbound 200 race report: what a well-executed 200-mile gravel race looks like when you finally learn from your mistakes.",
     None, "Unbound 200 race report"),
    (3483, "post", "i-didnt-screw-up-ned-gravel-and-neither-do-you",
     "Ned Gravel race report: executing a clean race at altitude in Nederland, Colorado. High country gravel done right.",
     None, "Ned Gravel race report"),
    (3504, "post", "i-screwed-up-foco-fondo-so-you-dont-have-to",
     "FoCo Fondo race report: overcooked the start, paid the price on the climbs. Lessons from Fort Collins gravel.",
     None, "FoCo Fondo race report"),
    (3520, "post", "i-didnt-screw-up-sbt-grvl-and-neither-do-you",
     "SBT GRVL race report: a clean ride through Steamboat's champagne gravel. What redemption looks like after years of mistakes.",
     None, "SBT GRVL race report"),
    (3537, "post", "i-didnt-screw-up-red-granite-grinder-and-neither-do-you-2",
     "Red Granite Grinder race report: the third time back, another clean ride. Some races just fit your strengths.",
     None, "Red Granite Grinder"),
    (3749, "post", "i-screwed-up-unbound-2024-so-you-dont-have-to",
     "Unbound 2024 race report: the mistakes that stack up over 200 miles of Kansas gravel when heat and hubris collide.",
     None, "Unbound 2024 race report"),
    (3796, "post", "i-messed-up-big-horn-gravel-so-you-dont-have-to",
     "Big Horn Gravel race report: the opening wall, the Jeep roads, and the pacing mistakes that turned a race into a lesson.",
     None, "Big Horn Gravel race report"),

    # ── Blog Posts: Tour of the Gila (2024) ──
    (3631, "post", "tour-of-the-gila-stage-3-my-life-is-a-mistake",
     "Tour of the Gila Stage 3 race report: the Gila Monster stage, where the climbs get personal and the legs stop cooperating.",
     None, "Tour of the Gila stage 3"),
    (3641, "post", "tour-of-the-gila-stage-what-is-cole-doing",
     "Tour of the Gila Stage 2 race report: tactics, breakaways, and the chaos of racing in Silver City's high desert.",
     None, "Tour of the Gila stage 2"),
    (3653, "post", "tour-of-the-gila-stage-1-full-tilt-like-a-peter-built",
     "Tour of the Gila Stage 1 race report: full gas from the start, lessons in managing aggression over a five-day stage race.",
     None, "Tour of the Gila stage 1"),
    (3662, "post", "tour-of-the-gila-stage-4-its-not-the-rider-its-the-bike",
     "Tour of the Gila Stage 4 race report: when mechanicals test your resolve and you learn what stage racing really demands.",
     None, "Tour of the Gila stage 4"),
    (3673, "post", "tour-of-the-gila-stage-5-the-big-sad",
     "Tour of the Gila Stage 5 race report: the final stage, the emotional crash, and what five days of racing teaches you.",
     None, "Tour of the Gila stage 5"),

    # ── Blog Posts: Tour of the Gila (2023) ──
    (3278, "post", "tour-of-the-gila-tyrone-time-trial",
     "Tour of the Gila Tyrone Time Trial: racing alone against the clock on a New Mexico mine road with 2,000 feet of climbing.",
     None, "Tour of the Gila"),
    (3281, "post", "tour-of-the-gila-inner-loop-road-race",
     "Tour of the Gila Inner Loop road race: 100 miles of New Mexico desert racing with real tactics and punishing climbs.",
     None, "Tour of the Gila inner loop"),
    (3297, "post", "tour-of-the-gila-silver-city-criterium",
     "Tour of the Gila Silver City Criterium: short, fast, and chaotic. What happens when stage racers try to sprint.",
     None, "Tour of the Gila"),
    (3306, "post", "tour-of-the-gila-the-gila-monster",
     "Tour of the Gila Gila Monster stage: the queen stage with relentless climbing and a descent that redefines sketchy.",
     None, "Tour of the Gila Gila Monster"),
    (3335, "post", "tour-of-the-gila-the-mogollon",
     "Tour of the Gila Mogollon stage: the climb that defines this race. 5 miles straight up at altitude in the New Mexico sun.",
     None, "Tour of the Gila Mogollon"),

    # ── Blog Posts: The Double ──
    (2552, "post", "the-double-day-1",
     "The Double Day 1: starting a 13-day stage race experiment. Two races, two weeks, one question: is this even possible?",
     None, "The Double day 1"),
    (2563, "post", "the-double-day-2-thiccc-is-kwik",
     "The Double Day 2: learning that race weight is a myth and diesel engines win gravel. Thick legs, fast bikes.",
     None, "The Double day 2"),
    (2592, "post", "the-double-day-3-yield-to-tonnage",
     "The Double Day 3: yielding to tonnage when the bigger riders set the pace and the climbers pay the price on flat gravel.",
     None, "The Double day 3"),
    (2608, "post", "the-double-day-4-sheeesh",
     "The Double Day 4: when accumulated fatigue starts whispering and the legs negotiate every pedal stroke independently.",
     None, "The Double day 4"),
    (2623, "post", "the-double-day-5-rolly-gang-rolly-gang-rolly-gang",
     "The Double Day 5: deep into the experiment, the body adapts and the mind starts playing creative games with suffering.",
     None, "The Double day 5"),
    (2635, "post", "the-double-day-6-do-you-know-what-rolly-gang-means",
     "The Double Day 6: mid-race existential clarity and the unexpected benefits of voluntary, structured suffering.",
     None, "The Double day 6"),
    (2649, "post", "the-double-day-8-check-yourself-before-you-wreck-yourself",
     "The Double Day 8: knowing when to ease off before the body makes that decision for you. Ego management in real time.",
     None, "The Double day 8"),
    (2663, "post", "the-double-day-9-gruppetto-gods",
     "The Double Day 9: embracing the gruppetto, learning that sometimes the back of the race is where the real stories are.",
     None, "The Double day 9"),
    (2673, "post", "the-double-day-10-im-not-sure-what-an-18-hrv-means",
     "The Double Day 10: when your HRV drops to 18 and the body sends signals your brain refuses to acknowledge.",
     None, "The Double day 10"),
    (2684, "post", "the-double-day-11-how-do-you-get-excited-for-crits",
     "The Double Day 11: trying to find motivation for criteriums when stage race fatigue has consumed every reserve.",
     None, "The Double day 11"),
    (2696, "post", "the-double-day-12-i-like-the-way-you-die-boy",
     "The Double Day 12: the penultimate stage, where finishing becomes the only goal and performance is a distant memory.",
     None, "The Double day 12"),
    (2716, "post", "the-double-day-13-the-hangover",
     "The Double Day 13: the finale of a 13-day racing experiment. What 2 weeks of back-to-back stage racing does to a person.",
     None, "The Double day 13"),

    # ── Blog Posts: Training & Mindset ──
    (2014, "post", "how-to-hydrate-so-you-dont-die-in-your-gravel-race",
     "Gravel race hydration guide: how much to drink, sodium math, and the fueling mistakes that send riders to the med tent.",
     None, "gravel race hydration"),
    (2161, "post", "how-to-manage-dopamine-to-be-a-better-cyclist",
     "Dopamine cycling: how reward circuits affect your motivation and performance. Manage them to train harder and recover better.",
     None, "dopamine cycling"),
    (2191, "post", "if-you-really-want-to-race-bikes-fast-train-your-heart",
     "Why cardiac output limits endurance cycling and how to train your heart for gravel racing. The engine matters most.",
     None, "train your heart"),
    (2298, "post", "how-to-achieve-your-goals-and-stop-ruining-your-dreams",
     "Cycling goal setting that actually works: how to set targets that drive improvement instead of guaranteeing disappointment.",
     None, "cycling goal setting"),
    (2394, "post", "no-one-cares-if-youre-bored",
     "Training consistency: why boredom is a feature, not a bug. The uncomfortable truth about showing up and endurance gains.",
     None, "training consistency"),
    (2414, "post", "to-make-it-count-flip-the-switch",
     "The racing mindset switch: how to access real intensity when the effort actually matters. Training is practice, racing is war.",
     None, "racing mindset"),
    (2445, "post", "your-frame-is-all-there-is",
     "Your frame of reference shapes your cycling. How you see effort, competition, and progress determines how fast you get.",
     None, "frame of reference"),
    (2469, "post", "how-to-do-workouts-the-right-way",
     "How to execute cycling interval workouts correctly: pacing, recovery, RPE calibration, and the mistakes that waste time.",
     None, "cycling interval workouts"),
    (2521, "post", "what-is-hrv-and-why-should-i-care",
     "HRV training guide: what heart rate variability is, why it matters for endurance athletes, and how to use it for load management.",
     None, "HRV training"),
    (2904, "post", "how-to-develop-your-athletic-sht-detector",
     "How to filter cycling advice: develop an evidence-based detector for the training myths, supplement scams, and bad coaching.",
     None, "cycling advice"),
    (2927, "post", "maybe-stop-sandbagging-your-goals",
     "Stop sandbagging your cycling goals. Set targets that scare you enough to actually change your training behavior.",
     None, "cycling goals"),
    (2942, "post", "how-to-not-fk-up-your-holiday-training",
     "Holiday training done right: how to handle disruptions without losing fitness or sanity. A realistic off-season approach.",
     None, "holiday training"),
    (2956, "post", "how-to-beat-people-20-years-younger-than-you",
     "Masters cycling advantage: how experience, pacing, and consistency let older riders beat younger ones in gravel.",
     None, "masters cycling"),
    (1269, "post", "does-beer-make-you-slow",
     "Beer and cycling performance: does alcohol make you slower? The evidence on recovery, adaptation, and whether it matters.",
     None, "beer and cycling"),
    (1431, "post", "you-dont-need-to-bike-to-bike-fast",
     "Cross-training for cyclists: why off-the-bike work makes you faster on the bike, and what actually transfers to performance.",
     None, "cross-training"),
    (1499, "post", "your-eating-habits-are-killing-your-performance",
     "How your cycling nutrition habits undermine performance. Practical daily changes that make measurable differences on the bike.",
     None, "cycling nutrition habits"),
    (1533, "post", "if-youre-not-talented-you-should-probably-quit",
     "Talent vs. work in cycling: why genetic ceiling arguments miss the point and consistency beats ability every time.",
     None, "talent vs. work"),
    (1626, "post", "5-ways-to-become-a-power-meter-clown",
     "Five power meter mistakes cyclists make: staring at watts mid-ride, chasing FTP, and data obsessions that slow you down.",
     None, "power meter mistakes"),
    (915, "post", "so-why-do-you-skip-weight-training",
     "Why cyclists skip strength training and why that's a mistake. The case for weights, when to lift, and what actually helps.",
     None, "strength training"),

    # ── Blog Posts: Reviews & Analysis ──
    (901, "post", "since-no-one-asked-my-take-on-whoop",
     "WHOOP review for cyclists: what the data actually tells you, what it doesn't, and whether it's worth the subscription.",
     None, "WHOOP review"),
    (1078, "post", "controversial-opinion-you-dont-need-a-power-meter-to-be-fast",
     "Do you need a power meter to be fast? Probably not. When data helps, when it hurts, and what actually makes you faster.",
     None, "power meter"),
    (1186, "post", "since-no-one-asked-why-did-dumoulin-retire-he-just-wants-to-eat-some-cheese",
     "Why Tom Dumoulin retired from pro cycling. The pressure, the burnout, and what his exit says about sustainable performance.",
     None, "Tom Dumoulin"),
    (1230, "post", "since-no-one-asked-why-did-dumoulin-retire-he-just-wants-to-eat-some-cheese-2",
     "Why FTP matters for cycling training more than the internet says. A defense of threshold power as a tool for real athletes.",
     None, "FTP"),
    (1496, "post", "how-do-i-know-if-im-getting-fitter",
     "How to measure cycling fitness: the metrics that matter, the ones that don't, and what getting fitter actually feels like.",
     None, "cycling fitness"),
    (4060, "post", "i-opened-a-fascat-ai-coaching-email-so-you-dont-have-to",
     "FasCat AI coaching review: what their emails actually contain, how the advice compares to real coaching, and who it's for.",
     None, "FasCat AI coaching review"),

    # ── Blog Posts: Culture & Philosophy ──
    (922, "post", "the-tao-of-tom",
     "A cycling philosophy from a mentor named Tom: the ride matters more than the result. Lessons that changed how I train.",
     None, "cycling philosophy"),
    (1673, "post", "you-know-people-remember-how-you-race-right",
     "Sportsmanship in gravel racing: how you race matters as much as how you finish. Your reputation travels faster than you.",
     None, "gravel racing"),
    (1879, "post", "the-jester-precedes-the-king",
     "Cycling humility: why it precedes mastery. The athletes who get fast are the ones who stop pretending they already are.",
     None, "cycling humility"),
    (2345, "post", "gratitude-and-toilet-bowls",
     "Cycling gratitude: how perspective transforms suffering into appreciation and makes every ride count differently.",
     None, "cycling gratitude"),
    (2830, "post", "the-tyranny-of-irony-in-cycling",
     "Irony in cycling culture: how cynicism and detachment undermine the honest effort that makes this sport worth doing.",
     None, "cycling culture"),
    (2916, "post", "and-just-like-that-its-over",
     "End of cycling season reflection: what a full year of gravel racing teaches you about effort, aging, and starting over.",
     None, "end of cycling season"),
    (3581, "post", "david-beckham-has-something-to-say-to-cyclists",
     "Cycling work ethic from David Beckham: consistency, professionalism, and showing up when it's not fun.",
     None, "cycling work ethic"),
    (3594, "post", "eight-years-of-nate-wilson",
     "Eight years of long-term cycling coaching with Nate Wilson: what athlete development looks like when someone commits.",
     None, "long-term cycling coaching"),
    (3617, "post", "i-got-into-yoga-so-you-dont-have-to",
     "Yoga for cyclists: an honest review from someone who resisted it for years. What helps, what doesn't, and why I kept going.",
     None, "yoga for cyclists"),
    (3694, "post", "listening-to-robert-in-silver-city",
     "You're never fast enough to be too cool. A Silver City encounter that reframes what cycling ambition should look like.",
     None, "cycling ambition"),
    (3791, "post", "random-midweek-thought-stay-present",
     "Cycling mindfulness: stay present on the bike. A midweek reflection on why chasing future fitness ruins the ride you're on.",
     None, "cycling mindfulness"),
    (3811, "post", "but-are-you-eating-almonds-out-of-your-purse",
     "Cycling daily habits that shape performance. The almonds-in-your-purse approach to building consistency off the bike.",
     None, "cycling daily habits"),
    (3825, "post", "right-now-i-cant",
     "Cycling injury recovery: dealing with setbacks, burnout, or life disruptions as a competitive athlete. It's temporary.",
     None, "cycling injury recovery"),
    (3945, "post", "maybe-a-hate-poster-is-what-youve-been-missing",
     "Cycling motivation from an unlikely source: how a hater poster on your wall might be the missing piece in your performance.",
     None, "cycling motivation"),
]


def generate_entries():
    """Generate all meta description entries."""
    entries = []
    used_ids = set()

    # 1. Add race guide entries (hand-crafted, linked to race-data JSON)
    for wp_id, wp_slug, race_slug, desc, keyword in RACE_GUIDE_ENTRIES:
        entry = {
            "wp_id": wp_id,
            "wp_type": "page",
            "slug": wp_slug,
            "description": desc,
            "focus_keyword": keyword,
            "source": "race-data",
            "race_data_slug": race_slug,
        }
        if wp_id in TITLE_MAP:
            entry["title"] = TITLE_MAP[wp_id]
        entries.append(entry)
        used_ids.add(wp_id)

    # 2. Add manual entries
    for wp_id, wp_type, slug, desc, og_desc, keyword in MANUAL_ENTRIES:
        if wp_id in used_ids:
            print(f"  WARNING: Duplicate wp_id {wp_id} (manual entry for '{slug}' conflicts with race entry)")
            continue
        entry = {
            "wp_id": wp_id,
            "wp_type": wp_type,
            "slug": slug,
            "description": desc,
            "og_description": og_desc,
            "focus_keyword": keyword,
            "source": "manual",
        }
        if wp_id in TITLE_MAP:
            entry["title"] = TITLE_MAP[wp_id]
        entries.append(entry)
        used_ids.add(wp_id)

    # Sort by wp_id
    entries.sort(key=lambda e: e["wp_id"])

    return entries


def validate_entries(entries):
    """Run validation checks on entries. Returns (errors, warnings)."""
    errors = []
    warnings = []

    # Length checks
    for e in entries:
        desc = e["description"]
        if len(desc) < MIN_DESC_LENGTH:
            errors.append(f"Too short ({len(desc)} chars): wp_id={e['wp_id']} '{e['slug']}'")
        if len(desc) > MAX_DESC_LENGTH:
            errors.append(f"Too long ({len(desc)} chars): wp_id={e['wp_id']} '{e['slug']}'")
        if e.get("og_description") and len(e["og_description"]) > MAX_DESC_LENGTH:
            warnings.append(f"OG too long ({len(e['og_description'])} chars): wp_id={e['wp_id']}")

    # Title checks
    for e in entries:
        title = e.get("title")
        if not title:
            warnings.append(f"Missing title: wp_id={e['wp_id']} '{e['slug']}'")
            continue
        if len(title) < MIN_TITLE_LENGTH:
            errors.append(f"Title too short ({len(title)} chars): wp_id={e['wp_id']} '{e['slug']}'")
        if len(title) > MAX_TITLE_LENGTH:
            errors.append(f"Title too long ({len(title)} chars): wp_id={e['wp_id']} '{e['slug']}'")
        if not title.endswith("| Gravel God"):
            errors.append(f"Title missing '| Gravel God' suffix: wp_id={e['wp_id']} '{e['slug']}'")

    # Duplicate title checks
    seen_titles = {}
    for e in entries:
        title = e.get("title")
        if title:
            if title in seen_titles:
                errors.append(
                    f"Duplicate title: wp_id={e['wp_id']} and wp_id={seen_titles[title]}")
            seen_titles[title] = e["wp_id"]

    # Duplicate checks
    seen_descs = {}
    for e in entries:
        desc = e["description"]
        if desc in seen_descs:
            errors.append(
                f"Duplicate description: wp_id={e['wp_id']} and wp_id={seen_descs[desc]}")
        seen_descs[desc] = e["wp_id"]

    # Python repr leak check
    for e in entries:
        for field in ("description", "og_description"):
            val = e.get(field) or ""
            if "\\n" in val or "\\t" in val or val.startswith("[") or val.startswith("{"):
                errors.append(f"Possible repr leak in {field}: wp_id={e['wp_id']}")

    # WP ID uniqueness
    ids = [e["wp_id"] for e in entries]
    if len(ids) != len(set(ids)):
        dupes = [i for i in ids if ids.count(i) > 1]
        errors.append(f"Duplicate wp_ids: {set(dupes)}")

    # Focus keyword in description (warning only)
    for e in entries:
        kw = e.get("focus_keyword")
        if kw and kw.lower() not in e["description"].lower():
            warnings.append(f"Focus keyword '{kw}' not in description: wp_id={e['wp_id']}")

    return errors, warnings


def print_stats(entries):
    """Print statistics about the entries."""
    print(f"\nTotal entries: {len(entries)}")

    pages = [e for e in entries if e["wp_type"] == "page"]
    posts = [e for e in entries if e["wp_type"] == "post"]
    print(f"  Pages: {len(pages)}")
    print(f"  Posts: {len(posts)}")

    race_data = [e for e in entries if e.get("source") == "race-data"]
    manual = [e for e in entries if e.get("source") == "manual"]
    print(f"  Race-data generated: {len(race_data)}")
    print(f"  Hand-crafted: {len(manual)}")

    lengths = [len(e["description"]) for e in entries]
    print(f"\nDescription lengths:")
    print(f"  Min: {min(lengths)} chars")
    print(f"  Max: {max(lengths)} chars")
    print(f"  Avg: {sum(lengths) / len(lengths):.0f} chars")

    with_og = [e for e in entries if e.get("og_description")]
    with_kw = [e for e in entries if e.get("focus_keyword")]
    with_title = [e for e in entries if e.get("title")]
    print(f"  With og_description: {len(with_og)}")
    print(f"  With focus_keyword: {len(with_kw)}")
    print(f"  With title: {len(with_title)}")

    if with_title:
        title_lengths = [len(e["title"]) for e in with_title]
        print(f"\nTitle lengths:")
        print(f"  Min: {min(title_lengths)} chars")
        print(f"  Max: {max(title_lengths)} chars")
        print(f"  Avg: {sum(title_lengths) / len(title_lengths):.0f} chars")


def main():
    parser = argparse.ArgumentParser(description="Generate meta-descriptions.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show entries without writing to file")
    parser.add_argument("--stats", action="store_true",
                        help="Show statistics about entries")
    parser.add_argument("--validate", action="store_true",
                        help="Run validation checks")
    args = parser.parse_args()

    print("Generating meta descriptions...")
    entries = generate_entries()

    if args.stats:
        print_stats(entries)

    if args.validate:
        errors, warnings = validate_entries(entries)
        print(f"\nValidation: {len(errors)} errors, {len(warnings)} warnings")
        for e in errors:
            print(f"  ERROR: {e}")
        for w in warnings:
            print(f"  WARN: {w}")
        if errors:
            return 1

    if args.dry_run:
        print(f"\n{len(entries)} entries (dry run, not writing)")
        for e in entries:
            print(f"  [{e['wp_id']}] {e['slug']}: {e['description'][:80]}...")
        return 0

    # Write output
    output = {"entries": entries}

    # Clean None values for compact JSON
    for e in output["entries"]:
        for key in list(e.keys()):
            if e[key] is None:
                del e[key]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(entries)} entries to {OUTPUT_FILE}")

    # Always validate after generating
    errors, warnings = validate_entries(entries)
    if errors:
        print(f"\nValidation FAILED: {len(errors)} errors")
        for e in errors:
            print(f"  ERROR: {e}")
        return 1
    else:
        print(f"Validation passed ({len(warnings)} warnings)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
