#!/usr/bin/env python3
"""
Generate HTML worksheet files for the Deliver sport psychology course.
Each file is a self-contained, print-ready HTML document using the Clean Pro design system.

Output: wordpress/output/course/deliver/downloads/*.html
These can be converted to PDF via browser print or weasyprint.
"""

import os
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "wordpress" / "output" / "course" / "deliver" / "downloads"


def base_html(title: str, subtitle: str, body: str) -> str:
    """Wrap body content in the full HTML template with Clean Pro design system."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Deliver Course | Endure Labs</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  @page {{
    size: letter;
    margin: 0.6in 0.7in;
  }}

  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    color: #4a4a4a;
    background: #ffffff;
    line-height: 1.55;
    font-size: 11pt;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  /* Header */
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 2px solid #4ECDC4;
    padding-bottom: 12px;
    margin-bottom: 20px;
  }}
  .header-left h1 {{
    font-size: 18pt;
    font-weight: 700;
    color: #1a1a1a;
    letter-spacing: -0.02em;
    margin-bottom: 2px;
  }}
  .header-left .subtitle {{
    font-size: 10pt;
    color: #4ECDC4;
    font-weight: 500;
  }}
  .brand {{
    text-align: right;
    font-size: 8pt;
    color: #999;
    line-height: 1.4;
  }}
  .brand strong {{
    color: #4ECDC4;
    font-weight: 600;
    font-size: 9pt;
  }}

  /* Section headings */
  h2 {{
    font-size: 13pt;
    font-weight: 700;
    color: #1a1a1a;
    margin: 18px 0 8px 0;
  }}
  h3 {{
    font-size: 11pt;
    font-weight: 600;
    color: #1a1a1a;
    margin: 14px 0 6px 0;
  }}

  p {{
    margin-bottom: 8px;
  }}

  /* Accent box */
  .accent-box {{
    background: #f0faf9;
    border-left: 3px solid #4ECDC4;
    padding: 10px 14px;
    border-radius: 4px;
    margin: 12px 0;
    font-size: 10pt;
  }}
  .accent-box strong {{
    color: #1a1a1a;
  }}

  /* Write-in lines */
  .write-line {{
    border-bottom: 1px solid #ccc;
    min-height: 28px;
    margin: 6px 0;
    display: flex;
    align-items: flex-end;
    padding-bottom: 2px;
  }}
  .write-line.tall {{
    min-height: 48px;
  }}
  .write-line.extra-tall {{
    min-height: 72px;
  }}
  .write-line-label {{
    font-size: 9pt;
    color: #888;
    font-weight: 500;
    min-width: 100px;
    flex-shrink: 0;
  }}

  /* Checkbox items */
  .checkbox-item {{
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin: 6px 0;
    page-break-inside: avoid;
  }}
  .checkbox {{
    width: 16px;
    height: 16px;
    border: 1.5px solid #999;
    border-radius: 3px;
    flex-shrink: 0;
    margin-top: 2px;
  }}
  .checkbox-text {{
    font-size: 10.5pt;
  }}
  .checkbox-text strong {{
    color: #1a1a1a;
  }}

  /* Table styles */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
  }}
  th {{
    background: #1a1a1a;
    color: #ffffff;
    font-weight: 600;
    font-size: 9pt;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 8px 10px;
    text-align: left;
  }}
  td {{
    border-bottom: 1px solid #ddd;
    padding: 12px 10px;
    font-size: 10pt;
    vertical-align: top;
  }}
  tr:last-child td {{
    border-bottom: none;
  }}
  .example-row td {{
    color: #999;
    font-style: italic;
    font-size: 9.5pt;
    padding: 8px 10px;
    background: #fafafa;
  }}

  /* Rating scale */
  .rating-row {{
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 6px 0;
  }}
  .rating-label {{
    min-width: 180px;
    font-size: 10pt;
    font-weight: 500;
    color: #1a1a1a;
  }}
  .rating-circles {{
    display: flex;
    gap: 4px;
  }}
  .rating-circle {{
    width: 22px;
    height: 22px;
    border: 1.5px solid #999;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 7.5pt;
    color: #999;
  }}

  /* Numbered row */
  .numbered-row {{
    display: flex;
    gap: 10px;
    margin: 10px 0;
    page-break-inside: avoid;
  }}
  .row-number {{
    width: 24px;
    height: 24px;
    background: #4ECDC4;
    color: #fff;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10pt;
    font-weight: 700;
    flex-shrink: 0;
    margin-top: 2px;
  }}
  .row-content {{
    flex: 1;
  }}

  /* If-Then grid */
  .ifthen-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
    border-bottom: 1px solid #ddd;
    page-break-inside: avoid;
  }}
  .ifthen-cell {{
    padding: 14px 12px;
    min-height: 56px;
  }}
  .ifthen-cell:first-child {{
    border-right: 1px solid #ddd;
  }}
  .ifthen-prefix {{
    font-size: 8pt;
    font-weight: 700;
    text-transform: uppercase;
    color: #4ECDC4;
    letter-spacing: 0.06em;
    margin-bottom: 4px;
  }}

  /* Footer */
  .footer {{
    margin-top: 20px;
    padding-top: 8px;
    border-top: 1px solid #eee;
    font-size: 7.5pt;
    color: #bbb;
    display: flex;
    justify-content: space-between;
  }}

  /* Utility */
  .spacer {{ height: 10px; }}
  .small {{ font-size: 9pt; color: #888; }}
  .mt {{ margin-top: 14px; }}

  @media print {{
    body {{ background: #fff; }}
    .no-print {{ display: none; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <h1>{title}</h1>
    <div class="subtitle">{subtitle}</div>
  </div>
  <div class="brand">
    <strong>Endure Labs</strong><br>
    Deliver: Sport Psychology Course
  </div>
</div>

{body}

<div class="footer">
  <span>endurelabs.app/courses/deliver</span>
  <span>&copy; Endure Labs</span>
</div>

</body>
</html>"""


# ---------------------------------------------------------------------------
# 1. Performance Statements Card
# ---------------------------------------------------------------------------
def gen_performance_statements_card() -> str:
    body = """
<div class="accent-box">
  <strong>You can't control your thoughts. But you can answer them.</strong><br>
  Write your three Performance Statements below. Five words or fewer each.
  Memorize them. Deploy them when the chimp screams.
</div>

<h2>Instructions</h2>
<p>A Performance Statement is a pre-built, rehearsed counter-response to the negative self-talk that shows up under pressure. It's not cheerleading. It's a specific, action-directed phrase that replaces the chimp's voice with the coach's. Three types, three slots.</p>

<div class="spacer"></div>

<div class="numbered-row">
  <div class="row-number">1</div>
  <div class="row-content">
    <h3>Technical Statement</h3>
    <p class="small">What breaks down in your form when effort gets high? Write the correction as a physical cue.</p>
    <p class="small" style="color:#999; font-style:italic;">Examples: "Hips forward, light hands." &bull; "Quick feet, tall spine." &bull; "Elbows in, shoulders down."</p>
    <div class="write-line tall"></div>
  </div>
</div>

<div class="numbered-row">
  <div class="row-number">2</div>
  <div class="row-content">
    <h3>Pain Response Statement</h3>
    <p class="small">What does the chimp say when it wants you to quit? Write the honest counter-move. Something a grizzled, honest coach would say at mile 80. Calm truth, not hype.</p>
    <p class="small" style="color:#999; font-style:italic;">Examples: "You've hurt worse than this and finished." &bull; "The next checkpoint. That's all." &bull; "If you keep moving, you'll get there."</p>
    <div class="write-line tall"></div>
  </div>
</div>

<div class="numbered-row">
  <div class="row-number">3</div>
  <div class="row-content">
    <h3>Process Statement</h3>
    <p class="small">For the days you don't want to start. Not race day &mdash; Tuesday afternoon when motivation is zero. The phrase that gets you out the door.</p>
    <p class="small" style="color:#999; font-style:italic;">Examples: "Something is better than nothing." &bull; "Today's session is tomorrow's evidence." &bull; "You don't need to feel like it."</p>
    <div class="write-line tall"></div>
  </div>
</div>

<div class="spacer"></div>

<div class="accent-box">
  <strong>Deployment Protocol:</strong> Say them out loud. Repeat until automatic. In your next hard session, when the chimp fires, answer it. Out loud if alone. Under your breath if in a group. Every time. Until the response is as automatic as the negative thought.
</div>

<h3 class="mt">Bonus: Third-Person Version</h3>
<p class="small">Using your own name creates psychological distance (Kross et al., 2014). Rewrite your Technical statement in third person:</p>
<div class="write-line">
  <span class="write-line-label">"[Your name],</span>
</div>
"""
    return base_html(
        "Performance Statements Card",
        "Module 2 &mdash; Lesson 2.4 &bull; Wallet-sized reference",
        body,
    )


# ---------------------------------------------------------------------------
# 2. Race Soundtrack Card
# ---------------------------------------------------------------------------
def gen_race_soundtrack() -> str:
    body = """
<div class="accent-box">
  <strong>You're going to talk to yourself during the race anyway. Decide what you say.</strong><br>
  Assign 6 phrases to specific race moments. 3 instructional (body cues) + 3 motivational (psyche). Rehearse in training until automatic.
</div>

<h2>Instructional Cues <span class="small">(what your body should do)</span></h2>

<table>
  <thead>
    <tr><th style="width:40%">Phrase (2-4 words)</th><th style="width:35%">Assigned Race Moment</th><th style="width:25%">Deploy When</th></tr>
  </thead>
  <tbody>
    <tr class="example-row">
      <td>"Light feet, quick turnover"</td>
      <td>Technical sections / climbs</td>
      <td>Form breaks down</td>
    </tr>
    <tr><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
  </tbody>
</table>

<h2>Motivational Phrases <span class="small">(how you want to feel)</span></h2>

<table>
  <thead>
    <tr><th style="width:40%">Phrase</th><th style="width:35%">Assigned Race Moment</th><th style="width:25%">Deploy When</th></tr>
  </thead>
  <tbody>
    <tr class="example-row">
      <td>"You've been here before and survived"</td>
      <td>Mid-race fatigue / dark patch</td>
      <td>Want to quit</td>
    </tr>
    <tr><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
  </tbody>
</table>

<div class="spacer"></div>

<div class="accent-box">
  <strong>Rehearsal Protocol:</strong> Say these out loud during 2 training sessions this week. Deploy during hard intervals AND boring easy sessions. The words must be automated &mdash; instantly available without searching. If you have to think about what to say when you're suffering, it's too late.
</div>

<h3 class="mt">Race Day Quick Reference</h3>
<table>
  <thead>
    <tr><th>Race Phase</th><th>My Phrase</th></tr>
  </thead>
  <tbody>
    <tr><td>Warm-up / First 30 min</td><td><div class="write-line"></div></td></tr>
    <tr><td>Technical sections</td><td><div class="write-line"></div></td></tr>
    <tr><td>Mid-race fatigue</td><td><div class="write-line"></div></td></tr>
    <tr><td>When passed by others</td><td><div class="write-line"></div></td></tr>
    <tr><td>Final push</td><td><div class="write-line"></div></td></tr>
    <tr><td>Want to quit moment</td><td><div class="write-line"></div></td></tr>
  </tbody>
</table>
"""
    return base_html(
        "Race Soundtrack",
        "Module 3 &mdash; Lesson 3.4 &bull; Self-Talk Planning Card",
        body,
    )


# ---------------------------------------------------------------------------
# 3. Night-Before Checklist
# ---------------------------------------------------------------------------
def gen_night_before_checklist() -> str:
    body = """
<div class="accent-box">
  <strong>Structure kills anxiety.</strong> Complete this checklist the night before every race. Preparation replaces the worry loop. When it's done, close it. Trust the routine.
</div>

<p style="margin-bottom:4px;"><strong>Race:</strong> ____________________________&nbsp;&nbsp;&nbsp;<strong>Date:</strong> ______________</p>

<h2>Equipment &amp; Logistics <span class="small">(finalize by 7 PM)</span></h2>

<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Race kit</strong> laid out &mdash; jersey, shorts, socks, shoes, gloves, hat/helmet</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Race number</strong> + pins / timing chip attached</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Nutrition</strong> packed &mdash; pre-race meal, on-course fuel, post-race recovery</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Hydration</strong> &mdash; bottles filled, electrolytes packed, drop-bag stocked</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Bike/gear check</strong> &mdash; tires, brakes, chain, spare tube, CO2/pump</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Electronics</strong> charged &mdash; watch, head unit, lights, phone</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Directions &amp; parking</strong> confirmed &mdash; drive time, packet pickup details</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Alarm set</strong> with 15-min buffer &mdash; time: ________</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Weather checked</strong> (once &mdash; then stop checking)</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Bag packed</strong> by the door &mdash; nothing left to "remember" in the morning</div></div>

<h2>Mental Preparation</h2>

<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Worry Dump</strong> &mdash; open a notebook, write every fear and "what if." Don't solve, just dump. Then close it.</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Review 5 If-Then Plans</strong> (from Lesson 3.3) &mdash; read each one aloud: "If X, then I will Y"</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Review Race Soundtrack</strong> (from Lesson 3.4) &mdash; 6 phrases assigned to race moments</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Review Performance Statements</strong> &mdash; Technical / Pain / Process</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>Highlight Reel Visualization</strong> (from Lesson 3.2) &mdash; lie down, run the reel: empowering memory &rarr; crucial future moment. First person, full sensory detail.</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text"><strong>6-2-7 Breathing</strong> before lights out &mdash; inhale 6, hold 2, exhale 7. Don't count cycles. Drift off.</div></div>

<h2>Reminders</h2>

<div class="accent-box">
  <strong>Sleep banking matters more than tonight.</strong> One bad night doesn't wreck performance if you've slept well all week (Mah et al., 2011). The worry about not sleeping is more damaging than the sleep loss itself (Kolling, 2019). Nerves = readiness. Your body is getting ready.
</div>

<p class="small" style="margin-top:8px; font-style:italic;">Stop checking the weather. It hasn't changed in 90 seconds. &mdash; Coach's Note</p>
"""
    return base_html(
        "Night-Before Checklist",
        "Module 5 &mdash; Lesson 5.1 &bull; Pre-Race Preparation",
        body,
    )


# ---------------------------------------------------------------------------
# 4. Post-Race Debrief Worksheet
# ---------------------------------------------------------------------------
def gen_post_race_debrief() -> str:
    body = """
<div class="accent-box">
  <strong>Structured debrief, not rumination.</strong> Reflection is purposeful analysis with a beginning, middle, and end. Rumination is repetitive, self-critical thought that circles the same drain. Complete within 24 hours. Write it. Then close it.
</div>

<p><strong>Race:</strong> ____________________________&nbsp;&nbsp;&nbsp;<strong>Date:</strong> ______________&nbsp;&nbsp;&nbsp;<strong>Result:</strong> ______________</p>

<div class="spacer"></div>

<div class="numbered-row">
  <div class="row-number">1</div>
  <div class="row-content">
    <h3>What went well?</h3>
    <p class="small">Start here. Always. Even if the race was a disaster. Something went well. This is evidence collection for your Evidence File. If you don't catalog what went well, the chimp catalogs what went wrong.</p>
    <div class="write-line tall"></div>
    <div class="write-line tall"></div>
    <div class="write-line tall"></div>
  </div>
</div>

<div class="numbered-row">
  <div class="row-number">2</div>
  <div class="row-content">
    <h3>What was hard?</h3>
    <p class="small">Not "what went wrong." What was HARD. The language matters. "What went wrong" invites self-blame. "What was hard" invites honest assessment without judgment. Where did the chimp get loud? Where did your plan break?</p>
    <div class="write-line tall"></div>
    <div class="write-line tall"></div>
    <div class="write-line tall"></div>
  </div>
</div>

<div class="numbered-row">
  <div class="row-number">3</div>
  <div class="row-content">
    <h3>What would I do differently?</h3>
    <p class="small">Now &mdash; and only now &mdash; you problem-solve. Not "I should have been tougher." What, specifically? Actionable. Forward-looking.</p>
    <div class="write-line tall"></div>
    <div class="write-line tall"></div>
    <div class="write-line tall"></div>
  </div>
</div>

<div class="numbered-row">
  <div class="row-number">4</div>
  <div class="row-content">
    <h3>What am I proud of?</h3>
    <p class="small">End here. Always. Not the same as Question 1 &mdash; that was analytical. This is emotional. What do you respect about yourself for having done this? This deposits directly into your self-concept.</p>
    <div class="write-line tall"></div>
    <div class="write-line tall"></div>
  </div>
</div>

<div class="spacer"></div>

<h3>Process vs. Outcome Check</h3>
<table>
  <thead><tr><th style="width:50%">Process Goals (things I controlled)</th><th style="width:50%">Outcome Goals (things I didn't control)</th></tr></thead>
  <tbody>
    <tr><td><div class="write-line"></div><div class="write-line"></div></td><td><div class="write-line"></div><div class="write-line"></div></td></tr>
  </tbody>
</table>

<div class="accent-box">
  <strong>The rules:</strong> Complete within 24 hours. Write it &mdash; not in your head. Thinking about it is rumination; writing is reflection. Then close it. The debrief has a beginning, a middle, and an end. You are not your last result.
</div>
"""
    return base_html(
        "Post-Race Debrief Worksheet",
        "Module 5 &mdash; Lesson 5.6 &bull; Structured Reflection",
        body,
    )


# ---------------------------------------------------------------------------
# 5. Identity Audit Worksheet
# ---------------------------------------------------------------------------
def gen_identity_audit() -> str:
    body = """
<div class="accent-box">
  <strong>You will never outperform your self-concept.</strong> The words after "I am" set the ceiling. This worksheet helps you audit the stories driving your athletic identity &mdash; and decide which ones to keep.
</div>

<h2>The Identity Tree</h2>
<p class="small">Dr. Justin Ross's model: roots (self-concept) determine the size and health of everything above ground. Trunk (self-worth) is your fundamental value as a person. Branches (self-esteem) are sport-specific. Leaves (self-efficacy) are task-specific beliefs.</p>

<div class="spacer"></div>

<h2>Step 1: Write 5 "I am" Statements</h2>
<p class="small">Write what you actually believe about yourself as an athlete. Not what you think you should believe. The raw, gut-level truth.</p>

<table>
  <thead><tr><th style="width:5%">#</th><th style="width:40%">"I am..." Statement</th><th style="width:18%">Fact or Story?</th><th style="width:18%">Serving or Limiting?</th><th style="width:19%">Where did it come from?</th></tr></thead>
  <tbody>
    <tr class="example-row"><td>ex.</td><td>"I'm not a racer &mdash; I just train well"</td><td>Story</td><td>Limiting</td><td>One bad race in 2023</td></tr>
    <tr><td>1</td><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td>2</td><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td>3</td><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td>4</td><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td>5</td><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
  </tbody>
</table>

<h2>Step 2: Tree Layer Assessment</h2>

<h3>Roots &mdash; Self-Concept <span class="small">(deepest beliefs about who you are)</span></h3>
<p class="small">What is the core narrative you carry about yourself as an athlete? The story that runs underneath everything?</p>
<div class="write-line extra-tall"></div>

<h3>Trunk &mdash; Self-Worth <span class="small">(your value as a person, independent of sport)</span></h3>
<p class="small">Is your sense of self-worth dependent on your athletic performance? If you couldn't race for a year, would you still feel valuable?</p>
<div class="write-line extra-tall"></div>

<h3>Branches &mdash; Self-Esteem <span class="small">(sport-specific confidence)</span></h3>
<p class="small">Rate your athletic self-esteem in specific domains:</p>
<div class="rating-row"><span class="rating-label">Endurance / long efforts</span><div class="rating-circles"><span class="rating-circle">1</span><span class="rating-circle">2</span><span class="rating-circle">3</span><span class="rating-circle">4</span><span class="rating-circle">5</span></div></div>
<div class="rating-row"><span class="rating-label">Racing / competition</span><div class="rating-circles"><span class="rating-circle">1</span><span class="rating-circle">2</span><span class="rating-circle">3</span><span class="rating-circle">4</span><span class="rating-circle">5</span></div></div>
<div class="rating-row"><span class="rating-label">Technical skills</span><div class="rating-circles"><span class="rating-circle">1</span><span class="rating-circle">2</span><span class="rating-circle">3</span><span class="rating-circle">4</span><span class="rating-circle">5</span></div></div>
<div class="rating-row"><span class="rating-label">Resilience under pressure</span><div class="rating-circles"><span class="rating-circle">1</span><span class="rating-circle">2</span><span class="rating-circle">3</span><span class="rating-circle">4</span><span class="rating-circle">5</span></div></div>

<h3>Leaves &mdash; Self-Efficacy <span class="small">(task-specific belief in capability)</span></h3>
<p class="small">"I believe I can..." &mdash; list 3 specific tasks or performances you're confident in, and 2 you doubt:</p>
<table>
  <thead><tr><th style="width:50%">Confident (I believe I can...)</th><th style="width:50%">Doubtful (I'm not sure I can...)</th></tr></thead>
  <tbody>
    <tr><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td><div class="write-line"></div></td><td></td></tr>
  </tbody>
</table>

<h2>Step 3: Identity Foreclosure Check</h2>
<p class="small">If the athlete branch is your ONLY branch, vulnerability skyrockets (Brewer, Van Raalte & Linder, 1993). List your non-sport identity branches:</p>
<div class="write-line"></div>
<div class="write-line"></div>
<p class="small" style="margin-top:8px;">If you struggled to fill those lines, that's data. Have other branches. Nurture the trunk.</p>
"""
    return base_html(
        "Identity Audit Worksheet",
        "Module 2 &mdash; Lesson 2.1 &bull; The Identity Tree",
        body,
    )


# ---------------------------------------------------------------------------
# 6. Stress Audit Worksheet
# ---------------------------------------------------------------------------
def gen_stress_audit() -> str:
    body = """
<div class="accent-box">
  <strong>Stress doesn't stay in its lane.</strong> Mental stress amplifies physical pain, steals sleep, elevates cortisol, and makes every session feel harder than it is. Find the leak. Fix the leak.
</div>

<p><strong>Date:</strong> ______________</p>

<h2>5-Domain Stress Audit</h2>
<p class="small">Rate each domain 1&ndash;10. <strong>1</strong> = peaceful and stable. <strong>10</strong> = on fire and barely coping. Be honest.</p>

<table>
  <thead><tr><th style="width:25%">Domain</th><th style="width:10%">Rating<br>(1-10)</th><th style="width:35%">Primary Source of Stress</th><th style="width:30%">One Specific Action</th></tr></thead>
  <tbody>
    <tr><td><strong>Training / Sport</strong></td><td style="text-align:center;font-size:14pt;"></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td><strong>Work / School</strong></td><td style="text-align:center;font-size:14pt;"></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td><strong>Relationships</strong></td><td style="text-align:center;font-size:14pt;"></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td><strong>Sleep</strong></td><td style="text-align:center;font-size:14pt;"></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td><strong>Health</strong></td><td style="text-align:center;font-size:14pt;"></td><td><div class="write-line"></div></td><td><div class="write-line"></div></td></tr>
    <tr><td style="font-weight:700; color:#1a1a1a;">TOTAL</td><td style="text-align:center;font-size:14pt; border-top:2px solid #1a1a1a;"></td><td colspan="2" style="border-top:2px solid #1a1a1a;"><span class="small">Over 30 = your stress load is almost certainly affecting performance</span></td></tr>
  </tbody>
</table>

<div class="spacer"></div>

<h2>Find the Leak</h2>
<p class="small">Your highest single score is your leak. A 9 in one domain doesn't stay there &mdash; it bleeds into sleep, training, health. Stress cross-contaminates.</p>

<p><strong>My highest-scoring domain:</strong> ____________________________</p>
<p><strong>How is it bleeding into other domains?</strong></p>
<div class="write-line tall"></div>

<div class="spacer"></div>

<h2>Stress Relievers <span class="small">(acute &mdash; aspirin for the headache)</span></h2>
<p class="small">Quick hits to give your nervous system a break. Check the ones you'll deploy this week:</p>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text">Music &mdash; curated playlist, not background noise</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text">Time in nature &mdash; minimum 20 minutes, phone off</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text">Phone call with someone who makes you feel seen</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text">Social media unplug &mdash; 24 hours off</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text">Laughter &mdash; comedy, friends, anything that genuinely makes you laugh</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text">Other: ____________________________</div></div>

<h2>Stress Balancers <span class="small">(structural &mdash; fix the root cause)</span></h2>
<p class="small">Target your highest-scoring domain with a specific structural change:</p>

<table>
  <thead><tr><th style="width:25%">If Highest Domain Is</th><th>Structural Change</th></tr></thead>
  <tbody>
    <tr><td>Sleep</td><td>No screens after ___ PM &bull; 6-2-7 in bed &bull; Consistent wake time: ___</td></tr>
    <tr><td>Work</td><td>Reinstate one boundary this week: ____________________________</td></tr>
    <tr><td>Relationships</td><td>Have the conversation you've been avoiding: ____________________________</td></tr>
    <tr><td>Training</td><td>Adjust volume/intensity: ____________________________</td></tr>
    <tr><td>Health</td><td>Schedule the appointment: ____________________________</td></tr>
  </tbody>
</table>

<div class="accent-box" style="margin-top:14px;">
  <strong>The vicious cycle is real:</strong> Stress &rarr; poor sleep &rarr; elevated cortisol &rarr; increased inflammation &rarr; worse performance &rarr; more stress. The cycle doesn't break itself. You have to intervene. (Williams &amp; Andersen, 1998; Fullagar, 2015)
</div>
"""
    return base_html(
        "Stress Audit Worksheet",
        "Module 6 &mdash; Lesson 6.2 &bull; 5-Domain Assessment",
        body,
    )


# ---------------------------------------------------------------------------
# 7. If-Then Worksheet
# ---------------------------------------------------------------------------
def gen_if_then_worksheet() -> str:
    body = """
<div class="accent-box">
  <strong>Hope is not a race strategy. Preparation is.</strong><br>
  If-Then plans convert coping decisions into pre-programmed responses &mdash; eliminating the cognitive cost of in-race deliberation. Effect size d = .65 across 94 studies (Gollwitzer &amp; Sheeran, 2006).
</div>

<p><strong>Target Race:</strong> ____________________________&nbsp;&nbsp;&nbsp;<strong>Date:</strong> ______________</p>

<div class="spacer"></div>

<h2>Step 1: List Your 5 Most Likely Race-Day Problems</h2>
<p class="small">Not far-fetched disasters &mdash; the LIKELY ones. Think across categories: Physical (cramping, GI, bonking) &bull; Mechanical (flats, equipment) &bull; Environmental (heat, wind, rain) &bull; Tactical (too fast, dropped) &bull; Psychological (doubt spiral, wanting to quit).</p>

<div class="spacer"></div>

<h2>Step 2: Write Specific If-Then Responses</h2>

<div style="border:1px solid #ddd; border-radius:4px; overflow:hidden;">

  <div class="ifthen-row" style="background:#fafafa;">
    <div class="ifthen-cell">
      <div class="ifthen-prefix">If (specific trigger)</div>
      <span class="small" style="font-style:italic; color:#999;">Example: My stomach cramps at mile 50</span>
    </div>
    <div class="ifthen-cell">
      <div class="ifthen-prefix">Then I will (specific action)</div>
      <span class="small" style="font-style:italic; color:#999;">Switch to water only, walk for 2 min, reassess</span>
    </div>
  </div>

  <div class="ifthen-row">
    <div class="ifthen-cell">
      <div class="ifthen-prefix">If</div>
      <div class="write-line tall"></div>
    </div>
    <div class="ifthen-cell">
      <div class="ifthen-prefix">Then I will</div>
      <div class="write-line tall"></div>
    </div>
  </div>

  <div class="ifthen-row">
    <div class="ifthen-cell">
      <div class="ifthen-prefix">If</div>
      <div class="write-line tall"></div>
    </div>
    <div class="ifthen-cell">
      <div class="ifthen-prefix">Then I will</div>
      <div class="write-line tall"></div>
    </div>
  </div>

  <div class="ifthen-row">
    <div class="ifthen-cell">
      <div class="ifthen-prefix">If</div>
      <div class="write-line tall"></div>
    </div>
    <div class="ifthen-cell">
      <div class="ifthen-prefix">Then I will</div>
      <div class="write-line tall"></div>
    </div>
  </div>

  <div class="ifthen-row">
    <div class="ifthen-cell">
      <div class="ifthen-prefix">If</div>
      <div class="write-line tall"></div>
    </div>
    <div class="ifthen-cell">
      <div class="ifthen-prefix">Then I will</div>
      <div class="write-line tall"></div>
    </div>
  </div>

  <div class="ifthen-row">
    <div class="ifthen-cell">
      <div class="ifthen-prefix">If</div>
      <div class="write-line tall"></div>
    </div>
    <div class="ifthen-cell">
      <div class="ifthen-prefix">Then I will</div>
      <div class="write-line tall"></div>
    </div>
  </div>

  <div class="ifthen-row">
    <div class="ifthen-cell">
      <div class="ifthen-prefix">If</div>
      <div class="write-line tall"></div>
    </div>
    <div class="ifthen-cell">
      <div class="ifthen-prefix">Then I will</div>
      <div class="write-line tall"></div>
    </div>
  </div>

  <div class="ifthen-row" style="border-bottom:none;">
    <div class="ifthen-cell">
      <div class="ifthen-prefix">If</div>
      <div class="write-line tall"></div>
    </div>
    <div class="ifthen-cell">
      <div class="ifthen-prefix">Then I will</div>
      <div class="write-line tall"></div>
    </div>
  </div>

</div>

<div class="spacer"></div>

<h2>Step 3: Visualize &amp; Rehearse</h2>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text">Close your eyes. See each trigger happening in first person. Then see yourself executing the pre-planned response &mdash; calmly, automatically, like a drill.</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text">Review these 5 plans before every key session and race. Read them out loud.</div></div>
<div class="checkbox-item"><div class="checkbox"></div><div class="checkbox-text">After each race, audit: Did the scenario happen? Did the If-Then work? Update, refine, replace.</div></div>

<div class="accent-box" style="margin-top:10px;">
  <strong>Specificity test:</strong> If your response contains "deal with it," "adjust," or "figure it out" &mdash; it's too vague. Effective If-Then plans name the exact trigger AND the exact response. No deliberation under pressure.
</div>
"""
    return base_html(
        "If-Then Plan Worksheet",
        "Module 3 &mdash; Lesson 3.3 &bull; Disaster Planning",
        body,
    )


# ---------------------------------------------------------------------------
# 8. Flow Conditions Audit
# ---------------------------------------------------------------------------
def gen_flow_conditions_audit() -> str:
    body = """
<div class="accent-box">
  <strong>You can't force flow. But you can engineer the conditions.</strong><br>
  Csikszentmihalyi mapped the state. Jackson measured it. The three triggers &mdash; challenge-skills balance, clear goals, unambiguous feedback &mdash; are the combination to the lock.
</div>

<h2>3-Session Flow Audit</h2>
<p class="small">After each of your next 3 training sessions, immediately rate the three flow triggers (1&ndash;5). Then reflect.</p>

<div class="spacer"></div>

<h3>Session 1</h3>
<p><strong>Activity:</strong> ____________________________&nbsp;&nbsp;&nbsp;<strong>Date:</strong> ______________&nbsp;&nbsp;&nbsp;<strong>Duration:</strong> __________</p>

<table>
  <thead><tr><th style="width:35%">Flow Trigger</th><th style="width:10%">Rating<br>(1-5)</th><th style="width:55%">Notes / Why This Score?</th></tr></thead>
  <tbody>
    <tr><td><strong>Challenge-Skills Balance</strong><br><span class="small">Was I stretched to the edge of my ability &mdash; but not past it?</span></td><td></td><td><div class="write-line"></div></td></tr>
    <tr><td><strong>Clear Goals</strong><br><span class="small">Did I know exactly what I was trying to accomplish right now?</span></td><td></td><td><div class="write-line"></div></td></tr>
    <tr><td><strong>Unambiguous Feedback</strong><br><span class="small">Was I getting real-time info on how I was performing?</span></td><td></td><td><div class="write-line"></div></td></tr>
  </tbody>
</table>
<p class="small"><strong>Flow moment?</strong> &nbsp; Yes / No &nbsp;&nbsp;&nbsp; <strong>How absorbed did I feel?</strong> (1-5): ___</p>

<div class="spacer"></div>

<h3>Session 2</h3>
<p><strong>Activity:</strong> ____________________________&nbsp;&nbsp;&nbsp;<strong>Date:</strong> ______________&nbsp;&nbsp;&nbsp;<strong>Duration:</strong> __________</p>

<table>
  <thead><tr><th style="width:35%">Flow Trigger</th><th style="width:10%">Rating<br>(1-5)</th><th style="width:55%">Notes / Why This Score?</th></tr></thead>
  <tbody>
    <tr><td><strong>Challenge-Skills Balance</strong><br><span class="small">Was I stretched to the edge of my ability &mdash; but not past it?</span></td><td></td><td><div class="write-line"></div></td></tr>
    <tr><td><strong>Clear Goals</strong><br><span class="small">Did I know exactly what I was trying to accomplish right now?</span></td><td></td><td><div class="write-line"></div></td></tr>
    <tr><td><strong>Unambiguous Feedback</strong><br><span class="small">Was I getting real-time info on how I was performing?</span></td><td></td><td><div class="write-line"></div></td></tr>
  </tbody>
</table>
<p class="small"><strong>Flow moment?</strong> &nbsp; Yes / No &nbsp;&nbsp;&nbsp; <strong>How absorbed did I feel?</strong> (1-5): ___</p>

<div class="spacer"></div>

<h3>Session 3</h3>
<p><strong>Activity:</strong> ____________________________&nbsp;&nbsp;&nbsp;<strong>Date:</strong> ______________&nbsp;&nbsp;&nbsp;<strong>Duration:</strong> __________</p>

<table>
  <thead><tr><th style="width:35%">Flow Trigger</th><th style="width:10%">Rating<br>(1-5)</th><th style="width:55%">Notes / Why This Score?</th></tr></thead>
  <tbody>
    <tr><td><strong>Challenge-Skills Balance</strong><br><span class="small">Was I stretched to the edge of my ability &mdash; but not past it?</span></td><td></td><td><div class="write-line"></div></td></tr>
    <tr><td><strong>Clear Goals</strong><br><span class="small">Did I know exactly what I was trying to accomplish right now?</span></td><td></td><td><div class="write-line"></div></td></tr>
    <tr><td><strong>Unambiguous Feedback</strong><br><span class="small">Was I getting real-time info on how I was performing?</span></td><td></td><td><div class="write-line"></div></td></tr>
  </tbody>
</table>
<p class="small"><strong>Flow moment?</strong> &nbsp; Yes / No &nbsp;&nbsp;&nbsp; <strong>How absorbed did I feel?</strong> (1-5): ___</p>

<div class="spacer"></div>

<h2>Reflection</h2>

<h3>Which session felt most effortless and absorbing?</h3>
<div class="write-line tall"></div>

<h3>What was your lowest-scoring trigger across all 3 sessions? <span class="small">(This is your flow bottleneck.)</span></h3>
<div class="write-line tall"></div>

<h3>What will you change to address that bottleneck?</h3>
<table>
  <thead><tr><th style="width:35%">If Your Bottleneck Is</th><th>Adjust By</th></tr></thead>
  <tbody>
    <tr><td>Challenge-Skills Balance</td><td>Training too easy or too hard? Adjust intensity to stretch &mdash; not overwhelm.</td></tr>
    <tr><td>Clear Goals</td><td>Show up with a specific plan. "Hold X pace for Y minutes." Not "just ride."</td></tr>
    <tr><td>Unambiguous Feedback</td><td>Better internal awareness: effort feel, breathing rhythm, form check-ins.</td></tr>
  </tbody>
</table>

<p class="small mt"><strong>My specific adjustment:</strong></p>
<div class="write-line tall"></div>

<div class="accent-box" style="margin-top:10px;">
  <strong>The 9 dimensions of flow</strong> (Csikszentmihalyi, 1975): Challenge-skills balance &bull; Clear goals &bull; Unambiguous feedback &bull; Merging of action and awareness &bull; Loss of self-consciousness &bull; Sense of control &bull; Transformation of time &bull; Concentration on the task &bull; Intrinsic reward. The first three are triggers you set. The rest are what shows up when you get them right.
</div>
"""
    return base_html(
        "Flow Conditions Audit",
        "Module 4 &mdash; Lesson 4.1 &bull; 3-Session Log",
        body,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
WORKSHEETS = [
    ("performance-statements-card.html", gen_performance_statements_card),
    ("m3-race-soundtrack.html", gen_race_soundtrack),
    ("night-before-checklist.html", gen_night_before_checklist),
    ("post-race-debrief-worksheet.html", gen_post_race_debrief),
    ("identity-audit-worksheet.html", gen_identity_audit),
    ("stress-audit-worksheet.html", gen_stress_audit),
    ("m3-if-then-worksheet.html", gen_if_then_worksheet),
    ("flow-conditions-audit.html", gen_flow_conditions_audit),
]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for filename, generator in WORKSHEETS:
        filepath = OUTPUT_DIR / filename
        html = generator()
        filepath.write_text(html, encoding="utf-8")
        print(f"  Created: {filepath}")

    print(f"\n  {len(WORKSHEETS)} HTML worksheets generated in:\n  {OUTPUT_DIR}")
    print("\n  To convert to PDF, open each in a browser and Print > Save as PDF,")
    print("  or install weasyprint: pip install weasyprint && python -c \"")
    print("    from weasyprint import HTML")
    print("    for f in Path('.').glob('*.html'):")
    print("      HTML(filename=str(f)).write_pdf(f.with_suffix('.pdf'))\"")


if __name__ == "__main__":
    main()
