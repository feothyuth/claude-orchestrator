---
description: Run a retrospective analysis after project completion - what went well, what didn't, lessons learned
argument-hint: [optional: project name or "last" for most recent]
---

# Project Retrospective

**Target:** $ARGUMENTS

---

## PURPOSE

Analyze completed work to:
1. Identify what went well
2. Identify what went poorly
3. Extract lessons for future projects
4. Update memory with insights

---

## EXECUTION STEPS

### Step 1: Gather Context

If $ARGUMENTS is empty or "last", analyze:
- Recent git commits (if available)
- Recent file modifications
- Current session context

Otherwise, focus on the specified project/feature.

### Step 2: Analyze Outcomes

For each phase of work:

**Planning Phase**
- Was the plan accurate?
- Were estimates reasonable?
- Missing requirements discovered later?

**Implementation Phase**
- Which agents were used?
- Any agents that struggled?
- Blockers encountered?

**Testing Phase**
- Tests written?
- Bugs found?
- Edge cases missed?

**Review Phase**
- Code review feedback?
- Security issues found?
- Performance concerns?

### Step 3: Categorize Findings

| Category | Finding | Impact | Action |
|----------|---------|--------|--------|
| SUCCESS | [what worked] | [benefit] | [repeat] |
| FAILURE | [what didn't] | [cost] | [avoid] |
| LEARNING | [insight] | [value] | [apply] |

### Step 4: Update Memory

**If successes found:**
Add to `/home/rnd/.claude/orchestrator/memory/success_patterns.json`

**If failures found:**
Add to `/home/rnd/.claude/orchestrator/memory/failure_patterns.json`

### Step 5: Generate Report

```markdown
## Retrospective Report

### Project
[Name/description of what was built]

### Timeline
- Started: [date/time if known]
- Completed: [date/time if known]

### What Went Well
| Item | Why It Worked | Repeat? |
|------|---------------|---------|
| [success] | [reason] | Yes/No |

### What Went Poorly
| Item | Root Cause | Prevention |
|------|------------|------------|
| [failure] | [why] | [how to avoid] |

### Agents Used
| Agent | Task | Performance |
|-------|------|-------------|
| [agent] | [what they did] | Good/OK/Poor |

### Lessons Learned
1. [lesson 1]
2. [lesson 2]
3. [lesson 3]

### Action Items
- [ ] [action to take]
- [ ] [pattern to add to memory]
- [ ] [process to change]

### Memory Updates
- Added to success_patterns: [patterns]
- Added to failure_patterns: [patterns]
```

---

## AUTO-TRIGGER

Consider suggesting `/retro` when user says:
- "that's done"
- "finished the feature"
- "project complete"
- "let's wrap up"

---

## BEGIN RETROSPECTIVE

1. Determine scope from $ARGUMENTS
2. Gather context about the work
3. Analyze successes and failures
4. Update memory files
5. Output retrospective report
