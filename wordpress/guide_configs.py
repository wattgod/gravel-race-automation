"""Guide-cluster configuration registry.

Each guide owns its URL namespace, capture behavior, analytics namespace, and
conversion surfaces.  The gravel configuration intentionally describes the
existing cluster exactly; it is the compatibility baseline for the refactor.
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping

from generate_neo_brutalist import COACHING_URL


REPO_ROOT = Path(__file__).parent.parent
GUIDE_DIR = REPO_ROOT / "guide"
OUTPUT_ROOT = Path(__file__).parent / "output"
LEAD_INTAKE_WORKER_URL = "https://fueling-lead-intake.gravelgodcoaching.workers.dev"


class GateEndpointMode(str, Enum):
    """Submission behavior for a chapter gate."""

    FORM_SUBMIT = "formsubmit"
    WORKER_FIRST = "worker_first"


@dataclass(frozen=True)
class GateFormConfig:
    """Gate form copy and delivery settings.

    ``FORM_SUBMIT`` preserves the legacy gravel gate.  ``WORKER_FIRST`` uses
    the lead-intake worker in JavaScript, unlocks immediately, and leaves the
    configured FormSubmit endpoint available only as a no-JS fallback.
    """

    subject_label: str
    worker_source_value: str
    endpoint_mode: GateEndpointMode
    worker_endpoint: str = LEAD_INTAKE_WORKER_URL
    formsubmit_endpoint: str = "https://formsubmit.co/gravelgodcoaching@gmail.com"


@dataclass(frozen=True)
class CtaSetConfig:
    """CTA blocks to render and their canonical targets."""

    pillar_blocks: tuple[str, ...]
    finale_blocks: tuple[str, ...]
    targets: Mapping[str, str]


@dataclass(frozen=True)
class GuideConfig:
    """All generator-owned settings for one independently deployable guide."""

    key: str
    content_path: Path
    output_dir: Path
    url_base: str
    chapter_meta: Mapping[str, Mapping[str, str]]
    ga4_event_label_prefix: str
    local_storage_key_prefix: str
    gate_form: GateFormConfig
    cta_set: CtaSetConfig
    glossary_source: Path
    guide_label: str = "Training Guide"
    include_configurator: bool = False
    date_published: str = "2025-06-01"
    date_modified: str = ""


GRAVEL_CHAPTER_META = {
    "what-is-gravel-racing": {
        "title_suffix": "What Is Gravel Racing? — Beginner's Guide",
        "description": "Everything you need to know about gravel racing: gear, rider categories, and what to expect. Free chapter from the Gravel God Training Guide.",
    },
    "race-selection": {
        "title_suffix": "How to Choose a Gravel Race — Selection Guide",
        "description": "How to choose the right gravel race: 14-dimension scoring system, tier rankings, and what to look for. Free chapter from the Gravel God Training Guide.",
    },
    "training-fundamentals": {
        "title_suffix": "Gravel Race Training Fundamentals",
        "description": "Training fundamentals for gravel racing: periodization, zone training, and building your base. Free chapter from the Gravel God Training Guide.",
    },
    "workout-execution": {
        "title_suffix": "Gravel Workout Execution — Interval Training Guide",
        "description": "How to execute gravel-specific workouts: intervals, endurance rides, and structured training for race performance.",
    },
    "nutrition-fueling": {
        "title_suffix": "Gravel Race Nutrition & Fueling Strategy",
        "description": "Complete gravel race nutrition guide: daily fueling, race-day calories, hydration strategy, and how to avoid bonking.",
    },
    "mental-training-race-tactics": {
        "title_suffix": "Mental Training & Race Tactics for Gravel",
        "description": "Mental training and race tactics for gravel racing: pacing strategy, decision-making under fatigue, and competitive mindset.",
    },
    "race-week": {
        "title_suffix": "Race Week Protocol — Gravel Race Preparation",
        "description": "Race week protocol for gravel racing: taper schedule, equipment checks, nutrition loading, and race morning routine.",
    },
    "post-race": {
        "title_suffix": "Post-Race Recovery & What's Next",
        "description": "Post-race recovery guide: immediate recovery, training restart timeline, and planning your next gravel race.",
    },
}


GRAVEL_GUIDE = GuideConfig(
    key="gravel",
    content_path=GUIDE_DIR / "gravel-guide-content.json",
    output_dir=OUTPUT_ROOT / "guide",
    url_base="/guide/",
    chapter_meta=GRAVEL_CHAPTER_META,
    ga4_event_label_prefix="guide",
    local_storage_key_prefix="gg_guide",
    # Grandfathered exception: retain the live FormSubmit gate unchanged.
    gate_form=GateFormConfig(
        subject_label="Guide Unlock",
        worker_source_value="training_guide",
        endpoint_mode=GateEndpointMode.FORM_SUBMIT,
    ),
    cta_set=CtaSetConfig(
        pillar_blocks=("newsletter", "training_plans", "coaching"),
        finale_blocks=("newsletter", "training_plans", "coaching"),
        targets={
            "newsletter": "https://gravelgodcycling.substack.com/",
            "training_plans": "/training-plans/",
            "coaching": COACHING_URL,
        },
    ),
    glossary_source=GUIDE_DIR / "gravel-guide-content.json",
    include_configurator=True,
    # Pin the existing live metadata so fresh checkouts render byte-identically.
    date_modified="2026-07-10",
)


BIKEPACKING_CHAPTER_META = {
    "the-ultra-demand": {
        "title_suffix": "What Ultra Bikepacking Races Actually Demand",
        "description": "Understand the repeatability, durability, systems, and judgment demands that define ultra-distance bikepacking races.",
    },
    "choosing-your-race": {
        "title_suffix": "How to Choose an Ultra Bikepacking Race",
        "description": "Compare ultra bikepacking race demands, route formats, logistics, and preparation runway before choosing your target.",
    },
    "training-for-repeatability": {
        "title_suffix": "Training for Ultra Bikepacking Repeatability",
        "description": "Build an ultra bikepacking week around repeatability, working-athlete volume, back-to-backs, recovery, and ceiling maintenance.",
    },
    "systems-that-keep-you-moving": {
        "title_suffix": "Bikepacking Systems That Keep You Moving",
        "description": "Test bike fit, contact points, repair, lighting, navigation, and sleep systems before an ultra bikepacking race.",
    },
    "energy-economy": {
        "title_suffix": "Ultra Bikepacking Fueling and Energy Economy",
        "description": "Practice hourly fueling, daily replenishment, resupply choices, and appetite management for multi-day bikepacking races.",
    },
    "the-mental-game": {
        "title_suffix": "The Mental Game for Ultra Bikepacking",
        "description": "Use pre-commitment rules, segmented goals, conservative pacing, and rested judgment during an ultra bikepacking race.",
    },
    "logistics-as-training": {
        "title_suffix": "Ultra Bikepacking Logistics as Training",
        "description": "Schedule route research, resupply mapping, gear decisions, travel, and exit planning as part of race preparation.",
    },
    "simulation-and-race-week": {
        "title_suffix": "Bikepacking Simulation Blocks and Race Week",
        "description": "Design a loaded multi-day simulation, protect its recovery window, close race-week loops, and start conservatively.",
    },
}


BIKEPACKING_GUIDE = GuideConfig(
    key="bikepacking",
    content_path=GUIDE_DIR / "bikepacking-guide-content.json",
    output_dir=OUTPUT_ROOT / "bikepacking-guide",
    url_base="/bikepacking-guide/",
    chapter_meta=BIKEPACKING_CHAPTER_META,
    ga4_event_label_prefix="bikepacking_guide",
    local_storage_key_prefix="gg_bikepacking_guide",
    gate_form=GateFormConfig(
        subject_label="Bikepacking Guide Unlock",
        worker_source_value="bikepacking_guide",
        endpoint_mode=GateEndpointMode.WORKER_FIRST,
    ),
    cta_set=CtaSetConfig(
        pillar_blocks=("ultra_shelf", "coaching_corner"),
        finale_blocks=("ultra_shelf", "coaching_corner"),
        targets={
            "ultra_shelf": "/gravel-races/?discipline=ultra",
            "coaching_corner": COACHING_URL,
        },
    ),
    glossary_source=GUIDE_DIR / "bikepacking-guide-content.json",
    guide_label="Bikepacking Race Training Guide",
    date_published="2026-07-25",
    date_modified="2026-07-25",
)


GUIDE_CONFIGS = {config.key: config for config in (GRAVEL_GUIDE, BIKEPACKING_GUIDE)}
