---
description: Capture a solved problem to the knowledge base for future reference
argument-hint: [brief description of what was solved]
---

# Knowledge Capture - Codify Solved Problem

**What was solved:** $ARGUMENTS

## Knowledge Base Location
`/home/rnd/.claude/orchestrator/knowledge/`

---

## EXECUTION STEPS

### Step 1: Gather Context
Ask or determine:
- What was the problem?
- What was the root cause?
- What was the solution?
- What files were changed?
- What technologies were involved?

### Step 2: Categorize
Select category:
- `bug-fixes` - Fixed a bug
- `performance` - Performance optimization
- `architecture` - Architectural decision
- `integration` - API/SDK integration
- `configuration` - Config/setup issues
- `patterns` - Reusable patterns discovered

### Step 3: Create Knowledge File
Write to `/home/rnd/.claude/orchestrator/knowledge/[category]/[slug].md`

```yaml
---
title: "[Descriptive title]"
category: [category]
tags: [rust, websocket, async]
date: [today]
problem_type: bug|performance|architecture|integration|config|pattern
severity: low|medium|high|critical
technologies: [list]
files_changed: [list]
---

## Problem
[What was the issue?]

## Root Cause
[Why did it happen?]

## Solution
[How was it fixed?]

## Code Changes
[Key code snippets or file references]

## Lessons Learned
[What to remember for next time]

## Related
[Links to related issues or docs]
```

### Step 4: Update Memory
Add to `/home/rnd/.claude/orchestrator/memory/success_patterns.json` if this is a reusable pattern.

### Step 5: Offer Next Actions
After creating the knowledge file:
- Add to orchestrator memory as success pattern?
- Create a new skill from this solution?
- Link to existing related knowledge?

---

## AUTO-TRIGGER PHRASES

When user says any of these, suggest running /codify:
- "that fixed it"
- "it's working now"
- "problem solved"
- "figured it out"
- "that was the issue"

---

## EXECUTE NOW

1. If $ARGUMENTS is empty, ask what was solved
2. Gather context about the solution
3. Categorize and create the knowledge file
4. Update memory if applicable
5. Offer next actions

BEGIN KNOWLEDGE CAPTURE.
