#!/usr/bin/env python3
"""
Synthesize research dump into race brief with radar scores and training implications.
"""

import argparse
import os
import anthropic
from pathlib import Path
from datetime import datetime


def load_voice_guide():
    """Load Matti voice guidelines."""
    voice_path = Path("skills/voice_guide.md")
    if voice_path.exists():
        return voice_path.read_text()
    else:
        # Fallback voice guide
        return """
# Matti Voice Guidelines

- Direct, no hedging, no corporate speak
- Honest: If it sucks, say it sucks
- Specific: Real numbers, real consequences
- Short, declarative, visceral sentences
- Dark, knowing humor - never soft
- Provocative - challenge assumptions
- No formal cadence - avoid "coachly encouragement"
- Every line builds the myth or exposes the reality

Phrases to USE:
- "The thing nobody tells you..."
- "Your FTP doesn't matter if..."
- "This isn't about watts, it's about..."
- "Show up undertrained and you'll..."

Phrases to AVOID:
- "Amazing opportunity"
- "World-class experience"
- "Don't miss out"
- Generic marketing language
"""


def synthesize_brief(input_path: str, output_path: str):
    """Synthesize research into race brief."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    research = Path(input_path).read_text()
    voice_guide = load_voice_guide()
    
    # Load research brief template if available
    brief_template_path = Path("skills/RACE_RESEARCH_BRIEF_SKILL_UPDATED.md")
    if brief_template_path.exists():
        brief_template = brief_template_path.read_text()
    else:
        brief_template = ""
    
    prompt = f"""
You are creating a Race Research Brief for a training plan business.

CONTEXT:
- This becomes a WordPress landing page for cyclists training for this race
- Target audience: Serious cyclists who want real intel, not marketing hype
- Content will be used to create training recommendations
- Voice: "Matti voice" - direct, honest, peer-to-peer, no corporate fluff

CRITICAL - NO SLOP:
- NO generic phrases: "amazing opportunity", "world-class", "incredible experience"
- NO hedging: "perhaps", "it seems like", "you might want to"
- NO encouragement: "you've got this", "embrace the challenge"
- YES specific details: exact mile markers, actual quotes, real numbers
- YES brutal honesty: what actually sucks, where people DNF
- YES direct language: "Your FTP doesn't matter if..." not "It's important to consider..."

VOICE GUIDELINES (CRITICAL - ALL CONTENT MUST BE IN MATTI VOICE):

{voice_guide}

---

RESEARCH BRIEF TEMPLATE:

{brief_template[:2000] if brief_template else "Use standard research brief format"}

---

Using this research, create a complete Race Brief in Matti voice. Be specific, not generic. Use real quotes. Tell the truth, not the marketing version.

{research[:15000]}

---

OUTPUT FORMAT:

# [RACE NAME] - RACE BRIEF

## RADAR SCORES (1-5 each)

Score each with one-sentence justification from the research:

| Variable | Score | Justification |
|----------|-------|---------------|
| Logistics | X | [why] |
| Length | X | [why] |
| Technicality | X | [why] |
| Elevation | X | [why] |
| Climate | X | [why] |
| Altitude | X | [why] |
| Adventure | X | [why] |

**PRESTIGE: X/5** - [one sentence on cultural weight in gravel world]

## TRAINING PLAN IMPLICATIONS

**Protocol Triggers:**
- Heat Adaptation: [Yes/No] - [specifics]
- Altitude Protocol: [Yes/No] - [specifics]
- Technical Skills: [Yes/No] - [specifics]
- Durability Focus: [Yes/No] - [where race breaks people]
- Fueling Strategy: [Yes/No] - [aid gaps, calorie needs]

**Training Emphasis:**
- Primary: [demand] - [how to train it]
- Secondary: [demand] - [how to train it]
- Tertiary: [demand] - [how to train it]

**THE ONE THING THAT WILL GET YOU:**
[Single most important insight from forum consensus]

## THE BLACK PILL

[2-3 paragraphs of brutal honesty. Use raw quotes from forums. What sucks. What breaks people. No marketing softening. Matti voice - dry, direct, peer-to-peer.]

## KEY QUOTES

[3-5 of the best forum quotes that capture the race's character]

## LOGISTICS SNAPSHOT

[Quick-hit logistics: airport, lodging, parking, packet pickup, local tips]

---

Write in Matti voice throughout. Dry, direct, no hype. If it feels sweaty, cut it.
"""

    print(f"Synthesizing brief from {input_path}...")
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    brief_content = response.content[0].text
    
    # Basic quality check
    if len(brief_content) < 500:
        raise ValueError(f"Brief too short ({len(brief_content)} chars) - likely generation failure")
    
    # Check for required sections
    required_sections = ["RADAR SCORES", "TRAINING PLAN IMPLICATIONS", "THE BLACK PILL"]
    missing = [s for s in required_sections if s not in brief_content]
    if missing:
        raise ValueError(f"Brief missing required sections: {', '.join(missing)}")
    
    # Add metadata
    output = f"""---
generated_at: {datetime.now().isoformat()}
source: {input_path}
model: claude-sonnet-4-20250514
---

{brief_content}
"""
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(output)
    
    # Run quality checks
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from quality_gates import run_all_quality_checks
        
        results = run_all_quality_checks(brief_content, "brief")
        if results["checks"]["slop"]["slop_count"] > 0:
            print(f"⚠️  Slop detected ({results['checks']['slop']['slop_count']} phrases) - review brief")
            for slop in results["checks"]["slop"]["slop_found"][:3]:
                print(f"   - '{slop['phrase']}' in context: ...{slop['context'][:50]}...")
        if not results["overall_passed"]:
            print(f"⚠️  Quality issues detected:")
            for name in results["critical_failures"]:
                print(f"   - {name}")
    except ImportError:
        print("⚠️  Quality gates not available (skipping checks)")
    
    print(f"✓ Brief saved to {output_path}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    
    synthesize_brief(args.input, args.output)

