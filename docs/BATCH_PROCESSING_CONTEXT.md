# Batch Processing Context for Claude

## What We're Building

A comprehensive database of 388 gravel races with detailed research, briefs, and landing pages for a training plan business.

## Why Batching?

**Problem:** We have 388 races to process. Each race requires:
1. Deep research (forum deep dives, YouTube comments, official data)
2. Synthesis into Matti voice brief
3. JSON generation for WordPress
4. Quality gates to prevent slop

**Solution:** Process races in batches to:
- Respect API rate limits (30,000 tokens/minute)
- Process continuously without manual intervention
- Track progress automatically
- Handle failures gracefully

## How Batching Works

### Fast Processing (2-4 Day Completion)

**Workflow:** `fast-process-races.yml`
- **Schedule:** Runs every 6 minutes
- **Process:** 1 race per run
- **Speed:** 10 races/hour = 240 races/day
- **Completion:** ~1.6 days for all 388 races

**Process:**
1. GitHub Actions triggers workflow every 6 minutes
2. Script finds next unprocessed race from database
3. Processes that ONE race: research → synthesize → generate JSON
4. Commits results to repo
5. Marks race as complete in `data/processed/completed.txt`
6. Next run picks the next race automatically

### Aggressive Processing (Faster)

**Workflow:** `aggressive-process.yml`
- **Schedule:** Runs every 3 minutes
- **Process:** 1 race per run
- **Speed:** 20 races/hour = 480 races/day
- **Completion:** ~0.8 days for all 388 races

**Trade-off:** Faster but may hit rate limits more often (retry logic handles it)

## What Claude Needs to Know

### When Processing a Single Race

**Context:**
- You're processing race #X of 388
- This is part of a systematic batch process
- Quality matters - this will be published
- Speed matters - we're processing hundreds of races

**Your Job:**
1. **Research:** Deep dive, not surface-level. Find forum threads, read YouTube comments, get real data.
2. **Synthesize:** Create brief in Matti voice - direct, honest, specific.
3. **Quality:** No slop. Specific details, real quotes, actual numbers.

### Why Sequential Processing?

**Rate Limits:**
- Anthropic API: 30,000 input tokens/minute
- Each race uses ~2,000-3,000 tokens
- Sequential = safe, predictable, reliable

**Quality:**
- One race at a time = full attention
- No rushing = better research
- Quality gates catch issues before commit

### Progress Tracking

**How We Know What's Done:**
- `data/processed/completed.txt` - list of completed race names
- Script checks this before selecting next race
- Prevents duplicate processing

**How We Know What's Left:**
- Total races in `gravel_races_full_database.json`
- Subtract completed = remaining
- Process continues until all done

## Quality Standards (Non-Negotiable)

### Research Stage
- **15-25 URLs** from diverse sources
- **Reddit + YouTube** required (most honest sources)
- **Specific mile markers** where people suffer
- **Real quotes** with usernames
- **Weather data** by year, not anecdotes
- **DNF rates** from results, not guesses

### Synthesis Stage
- **Matti voice** - direct, honest, no marketing fluff
- **No slop phrases** - quality gates will catch these
- **Specificity score 50+** - real numbers, quotes, URLs
- **All sections** present - radar scores, training implications, black pill

### Quality Gates
- **Slop detection:** 50+ phrases that indicate lazy AI output
- **Voice check:** Matti indicators must be present
- **Specificity:** Needs mile markers, quotes, URLs, years
- **Sections:** All required sections must be present
- **Source diversity:** 4+ source categories required

## What "Good" Looks Like

### Research Dump Example:
```
## REDDIT DEEP DIVE

u/graveldude42 said: "Mile 80-95 is where Unbound breaks people. 
The Teterville rollers come when your legs are cooked. I've done 
Leadville twice. Unbound 200 was harder."

Thread: https://reddit.com/r/gravelcycling/comments/abc123
- 47 comments
- Consensus: Mile 80-95 is the suffering zone
- Equipment: 40mm tires minimum, 28-32 psi
```

### Brief Example:
```
## THE BLACK PILL

Your FTP doesn't matter at mile 150. The truth is Unbound breaks 
people in the Teterville rollers (mile 80-95) when legs are cooked 
and heat hits 103°F. u/graveldude42 said it's harder than Leadville. 
35% DNF rate in hot years. Reality: you'll bonk if you ignore fueling 
at mile 60.
```

## What "Slop" Looks Like

### Bad Research:
```
This race offers an amazing opportunity for cyclists to challenge 
themselves. The course is challenging with variable terrain. Weather 
conditions can be difficult. It's worth noting that proper preparation 
is essential.
```

### Bad Brief:
```
This incredible race provides a world-class experience. Perhaps you 
might want to consider training more. It seems like the course could 
be challenging. Embrace the challenge and believe in yourself!
```

## Your Role in the Batch Process

**When processing a race:**
1. Understand this is part of a systematic 388-race database
2. Quality matters - this will be published and used for training plans
3. Speed matters - we're processing hundreds, but don't rush quality
4. Follow the methodology - forum deep dives, specific details, Matti voice
5. Trust the quality gates - they'll catch slop, but aim to pass on first try

**Remember:**
- You're not writing generic content
- You're creating training intel for serious cyclists
- Specificity > speed
- Real quotes > generic statements
- Brutal honesty > marketing fluff

## System Architecture

```
GitHub Actions (Scheduler)
    ↓
Every 6 minutes: Trigger workflow
    ↓
Find next unprocessed race
    ↓
Research (Claude + web_search)
    ↓
Synthesize (Claude + research dump)
    ↓
Generate JSON (Claude + brief)
    ↓
Quality Gates (Automated checks)
    ↓
Commit to repo
    ↓
Mark as complete
    ↓
Next run picks next race
```

## Success Metrics

**For Each Race:**
- ✅ Research: 15-25 URLs, 4+ source categories
- ✅ Brief: All sections present, Matti voice, no slop
- ✅ Quality gates: All pass
- ✅ JSON: Valid, ready for WordPress

**For Batch:**
- ✅ All 388 races processed
- ✅ Quality maintained throughout
- ✅ Completed in 2-4 days
- ✅ Zero manual intervention needed

