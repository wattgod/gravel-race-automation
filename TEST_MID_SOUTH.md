# Testing Mid South Race

## Test Purpose

Validate the enhanced research and synthesis prompts with:
- Batch processing context
- Anti-slop requirements
- Quality gates
- Source diversity

## Workflow Triggered

**Race:** Mid South  
**Folder:** mid-south  
**Workflow:** `research-race.yml`

## Expected Output

### Research Stage
- ✅ 15-25 URLs from diverse sources
- ✅ Reddit + YouTube sources (required)
- ✅ Specific mile markers
- ✅ Direct quotes with usernames
- ✅ Weather data by year
- ✅ DNF rates from results

### Quality Gates - Research
- ✅ No slop phrases detected
- ✅ Source diversity: 4+ categories
- ✅ Specificity score: 50+
- ✅ All required sections present

### Synthesis Stage
- ✅ Matti voice throughout
- ✅ No generic phrases
- ✅ Specific details, not vague
- ✅ Brutal honesty in Black Pill

### Quality Gates - Brief
- ✅ No slop phrases
- ✅ Matti voice indicators present
- ✅ Specificity score: 50+
- ✅ All sections present

## Monitoring

**GitHub Actions:**
https://github.com/wattgod/gravel-race-automation/actions

**Watch for:**
1. Research completes (3-5 min)
2. Quality Gate - Research passes
3. Synthesis completes
4. Quality Gate - Brief passes
5. JSON generated
6. Results committed

## If Quality Gates Fail

The workflow will stop before committing. Check logs to see:
- Which check failed
- What slop was detected
- Missing sections or sources

## After Mid South Passes

**Next Step:** Run batch on Tier 1
- Workflow: `batch-process.yml`
- Tier: 1
- Limit: 5
- Process 5 Tier 1 races sequentially

