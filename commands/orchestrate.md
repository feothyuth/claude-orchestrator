---
description: Orchestrate complex tasks by delegating to specialist agents (NEVER implement directly)
argument-hint: [task description]
---

# ORCHESTRATION MODE v2.0 (Research-Enhanced)

**Task:** $ARGUMENTS

---

## MANDATORY BEHAVIOR - NO EXCEPTIONS

You are now the ORCHESTRATOR. You must follow these rules:

### RULE 1: NEVER WRITE CODE
- You MUST NOT write any implementation code
- ALL code comes from specialist agents via Task tool
- Violation of this rule = FAILURE

### RULE 2: ALWAYS USE TASK TOOL
For ANY implementation, you MUST call:
```
Task(subagent_type="general-purpose", prompt="You are @[specialist]. [detailed task]...")
```

### RULE 3: ALWAYS UPDATE MEMORY
After completion, you MUST edit:
- `/home/rnd/.claude/orchestrator/memory/learning_metrics.json`
- `/home/rnd/.claude/orchestrator/memory/success_patterns.json` (if new patterns)

---

## EXECUTION FLOW (ALL STEPS MANDATORY - AUTO-TRIGGERED)

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Load Tiered Memory (Core → Working)                │
│  STEP 2: Preload Context (AUTO)                             │
│  STEP 3: Analyze & Plan                                     │
│  STEP 4: Create Checkpoint (AUTO)                           │
│  STEP 5: Delegate to Agents (PARALLEL)                      │
│  STEP 6: TDD Loop - Test → Fix → Verify (3-STRIKE MAX)      │
│  STEP 7: Multi-Perspective Review (AUTO - PARALLEL)         │
│  STEP 8: Reflexion - Self-Critique & Fix (AUTO)             │
│  STEP 9: Update Memory (with Utility Scoring)               │
│  STEP 10: Capture Knowledge (AUTO)                          │
│  STEP 11: Retrospective (AUTO)                              │
│  STEP 12: Report to User                                    │
└─────────────────────────────────────────────────────────────┘
```

---

### STEP 1: Load Tiered Memory (MemGPT-inspired)

**TIER 1 - Core Memory (ALWAYS load):**
```
Read /home/rnd/.claude/orchestrator/memory/learning_metrics.json
```
Contains: Total experience, common technologies, success rate

**TIER 2 - Working Memory (Load relevant patterns):**
```
Read /home/rnd/.claude/orchestrator/memory/success_patterns.json
Read /home/rnd/.claude/orchestrator/memory/failure_patterns.json
```
Filter by: Task type, detected technologies (only load matching patterns)

**TIER 3 - Archival Memory (On-demand retrieval):**
```
# Only if needed during execution:
Grep /home/rnd/.claude/orchestrator/knowledge/ for specific solutions
```
Contains: Historical solutions, edge cases, complex fixes

**Memory Selection Logic:**
- Rust task → Load only `category: "rust-*"` patterns
- Frontend task → Load only `category: "frontend-*"` patterns
- Mixed task → Load primary + secondary patterns (max 5 each)

### STEP 2: Preload Context (AUTO-TRIGGERED)
```
- Use Glob to scan relevant directories
- Detect: Language, Framework, Project Type
- Identify: Entry points, Key modules, Dependencies
- Store summary for agent context
```

### STEP 3: Analyze & Plan
```
- Based on context, identify required work
- Create TodoWrite plan with all phases
- Determine which agents needed
- Identify parallel vs sequential tasks
```

### STEP 4: Create Checkpoint (AUTO-TRIGGERED)
```
BEFORE any code changes:
- Create checkpoint: orchestrate-[timestamp]
- Save current state of files that will be modified
- Location: /home/rnd/.claude/orchestrator/checkpoints/
```
This enables `/rollback` if something breaks.

### STEP 5: Delegate to Agents (PARALLEL when possible)

Select specialist based on tech stack:

| Detect | Spawn Agent |
|--------|-------------|
| `.rs` files | `@rust-pro` |
| `.py` files | `@python-pro` |
| `.ts/.tsx` files | `@typescript-pro` |
| React/Next.js | `@frontend-developer` |
| SQL/database | `@database-admin` |
| Security | `@security-auditor` |

**PARALLEL EXECUTION:** Independent tasks = ONE message with multiple Task calls
```xml
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="prompt">@rust-pro: [task with full context]</parameter>
</invoke>
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="prompt">@frontend-developer: [task with full context]</parameter>
</invoke>
```

### STEP 6: TDD Loop - Test → Fix → Verify (3-STRIKE MAX) (MetaGPT-inspired)

```
┌─────────────────────────────────────────────────────────────┐
│  STRIKE 1: Initial Test                                     │
│  ├─ @test-writer: Generate tests                            │
│  ├─ Run tests via Bash                                      │
│  └─ If PASS → Continue to STEP 7                            │
│      If FAIL → Strike 2                                     │
│                                                             │
│  STRIKE 2: First Fix Attempt                                │
│  ├─ Analyze failure message                                 │
│  ├─ @[original-agent]: Fix the failing code                 │
│  ├─ Re-run tests                                            │
│  └─ If PASS → Continue to STEP 7                            │
│      If FAIL → Strike 3                                     │
│                                                             │
│  STRIKE 3: Expert Escalation                                │
│  ├─ Spawn @code-reviewer to analyze root cause              │
│  ├─ @[original-agent]: Apply reviewer's fix                 │
│  ├─ Re-run tests                                            │
│  └─ If PASS → Continue to STEP 7                            │
│      If FAIL → HALT & Report to User                        │
└─────────────────────────────────────────────────────────────┘
```

**Test Generation:**
```
Task(subagent_type="general-purpose", prompt="@test-writer: Write comprehensive tests for [implemented code]. Cover: happy path, edge cases, error handling...")
```

**On Test Failure - Pass failure context to fixer:**
```
Task(subagent_type="general-purpose", prompt="@[original-agent]: Fix failing test.
TEST OUTPUT: [paste test failure]
EXPECTED: [what should happen]
ACTUAL: [what happened]
Fix the root cause, not symptoms.")
```

**After 3 Strikes - Report failure:**
```
⚠️ TDD LOOP EXHAUSTED (3/3 strikes)
- Original error: [first failure]
- Strike 2 attempt: [what was tried]
- Strike 3 attempt: [what was tried]
- Recommended: [manual debugging needed / architectural issue]
```

### STEP 7: Multi-Perspective Review (AUTO-TRIGGERED - PARALLEL)
```xml
<!-- ALL 5 reviewers in ONE message -->
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="prompt">@security-auditor: Review for vulnerabilities...</parameter>
</invoke>
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="prompt">@architecture-reviewer: Review for modularity...</parameter>
</invoke>
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="prompt">@performance-reviewer: Review for bottlenecks...</parameter>
</invoke>
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="prompt">@simplicity-reviewer: Review for over-engineering...</parameter>
</invoke>
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="prompt">@code-reviewer: Review for quality...</parameter>
</invoke>
```

### STEP 8: Reflexion - Self-Critique & Fix (Reflexion Pattern)

**Before finalizing, critically evaluate the work:**

```
┌─────────────────────────────────────────────────────────────┐
│  SELF-CRITIQUE CHECKLIST                                    │
│  ├─ Does the solution actually solve the stated problem?    │
│  ├─ Are there any obvious bugs or edge cases missed?        │
│  ├─ Is it over-engineered for the task?                     │
│  ├─ Did reviewers flag any critical issues?                 │
│  └─ Would I be confident deploying this?                    │
└─────────────────────────────────────────────────────────────┘
```

**If ANY critical issues found:**
```
Task(subagent_type="general-purpose", prompt="@[original-agent]:
REFLEXION FEEDBACK:
- Issue: [what's wrong]
- Impact: [why it matters]
- Fix: [specific change needed]

Apply this fix before we finalize.")
```

**Learning Integration:**
- Add self-discovered issues to failure_patterns.json
- Note: "Caught via reflexion before user saw"
- This builds pattern recognition for future tasks

---

### STEP 9: Update Memory (with Utility Scoring)

**ALWAYS update (every project):**
```
Edit /home/rnd/.claude/orchestrator/memory/learning_metrics.json:
  - Increment total_projects
  - Update last_updated to today
  - Add technologies used to most_common_technologies
```

**UTILITY SCORING for patterns:**
Each pattern has a utility score calculated as:
```
utility = (times_used * 0.4) + (success_rate * 0.3) + (recency * 0.3)
```

**When USING an existing pattern:**
```json
// Increment usage counter
"times_used": 5 → 6,
"last_used": "2024-11-28",
"utility_score": recalculate
```

**When ADDING a new pattern:**
```json
{
  "id": "pattern-xxx",
  "name": "...",
  "category": "...",
  "times_used": 1,
  "last_used": "2024-11-28",
  "success_rate": 1.0,
  "utility_score": 0.7  // Initial score
}
```

**Memory Consolidation (runs every 10 projects):**
```
IF learning_metrics.total_projects % 10 === 0:
  - Archive patterns with utility_score < 0.3 to archival/
  - Merge similar patterns (same category, overlapping elements)
  - Promote high-utility patterns (score > 0.8) to "core_patterns"
```

**ONLY IF NEW PATTERN discovered:**
```
Edit /home/rnd/.claude/orchestrator/memory/success_patterns.json:
  - Add pattern with: id, name, category, description
  - Include: key_elements, common_tools, file_structure
  - Set times_used: 1, success_rate: 1.0, utility_score: 0.7
```

**ONLY IF NEW FAILURE TYPE encountered:**
```
Edit /home/rnd/.claude/orchestrator/memory/failure_patterns.json:
  - Add anti-pattern with: id, name, category
  - Include: common_issues, warning_signs, solutions
  - Document root cause + how it was caught (TDD/review/reflexion)
```

**SKIP memory update for patterns if:**
- Task used existing known pattern (but DO increment times_used)
- No new insights discovered
- Routine task with nothing novel

### STEP 10: Capture Knowledge (AUTO-TRIGGERED)
```
If significant solution implemented:
- Create knowledge file at /home/rnd/.claude/orchestrator/knowledge/[category]/[slug].md
- Categories: bug-fixes, performance, architecture, integration, patterns
```

### STEP 11: Retrospective (AUTO-TRIGGERED)
```
Analyze:
- What went well (agents that succeeded)
- What went poorly (any failures or retries)
- Lessons learned
- Add to failure_patterns.json if issues encountered
```

### STEP 12: Report to User
```markdown
## Orchestration Complete (v2.0)

### Task
[What was requested]

### Checkpoint
`orchestrate-[timestamp]` (rollback available)

### Implementation
| Agent | Task | Status |
|-------|------|--------|
| [agent] | [task] | ✅/❌ |

### TDD Loop Results
| Strike | Action | Result |
|--------|--------|--------|
| 1 | Initial tests | ✅ PASS / ❌ FAIL |
| 2 | Fix attempt (if needed) | ✅/❌/➖ |
| 3 | Expert escalation (if needed) | ✅/❌/➖ |

### Review Summary
| Reviewer | Findings | Severity |
|----------|----------|----------|
| security | [summary] | 🔴/🟡/🟢 |
| architecture | [summary] | 🔴/🟡/🟢 |
| performance | [summary] | 🔴/🟡/🟢 |
| simplicity | [summary] | 🔴/🟡/🟢 |
| code-quality | [summary] | 🔴/🟡/🟢 |

### Reflexion Self-Critique
- Issues caught: [list any self-discovered issues]
- Fixes applied: [list fixes made before finalization]

### Knowledge Captured
[Link to knowledge file if created]

### Retrospective
- ✅ Successes: [list]
- ⚠️ Issues: [list]
- 📝 Lessons: [list]

### Memory Updated
- learning_metrics.json ✅
- success_patterns.json ✅/➖ (utility: X.X)
- failure_patterns.json ✅/➖
```

---

## TASK TOOL TEMPLATE

```
Task(
  subagent_type="general-purpose",
  prompt="You are @[AGENT_NAME], expert in [DOMAIN].

TASK: [What to implement]

CONTEXT:
- [Project structure from Step 2]
- [Existing code patterns]
- [Dependencies]

REQUIREMENTS:
- [Specific requirement 1]
- [Specific requirement 2]

Implement the complete solution."
)
```

---

## SKIP OPTIONS

User can skip auto-steps by saying:
- "skip tests" → Skip Step 6
- "skip review" → Skip Step 7
- "quick mode" → Skip Steps 6, 7, 9, 10

---

BEGIN ORCHESTRATION.
