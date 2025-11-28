---
description: Multi-perspective code review using parallel agents
argument-hint: [file path, PR number, or "recent" for recent changes]
---

# Multi-Perspective Code Review

**Target:** $ARGUMENTS

---

## MANDATORY: Run ALL Reviewers in PARALLEL

You MUST spawn these agents in ONE message (parallel execution):

```xml
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="description">Security review</parameter>
  <parameter name="prompt">@security-auditor: Review [target] for security issues...</parameter>
</invoke>
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="description">Architecture review</parameter>
  <parameter name="prompt">@architecture-reviewer: Review [target] for architectural issues...</parameter>
</invoke>
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="description">Performance review</parameter>
  <parameter name="prompt">@performance-reviewer: Review [target] for performance issues...</parameter>
</invoke>
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="description">Simplicity review</parameter>
  <parameter name="prompt">@simplicity-reviewer: Review [target] for over-engineering...</parameter>
</invoke>
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="description">Code quality review</parameter>
  <parameter name="prompt">@code-reviewer: Review [target] for code quality...</parameter>
</invoke>
```

---

## Review Perspectives

| Agent | Focus |
|-------|-------|
| security-auditor | Vulnerabilities, auth, input validation |
| architecture-reviewer | Modularity, dependencies, scalability |
| performance-reviewer | Algorithms, memory, queries, bottlenecks |
| simplicity-reviewer | Over-engineering, unnecessary complexity |
| code-reviewer | Quality, maintainability, best practices |

---

## EXECUTION FLOW

### Step 1: Identify Target
Parse $ARGUMENTS:
- File path → Read the file
- PR number → Get PR diff with `gh pr diff`
- "recent" → Get recent changes with `git diff HEAD~5`

### Step 2: Spawn Reviewers (PARALLEL)
Send ONE message with 5 Task tool calls.

### Step 3: Synthesize Results
After all agents complete:
1. Combine all findings
2. Deduplicate similar issues
3. Sort by severity (HIGH → MEDIUM → LOW)

### Step 4: Create Todos (Optional)
For HIGH severity issues, create file-based todos:
```
/home/rnd/.claude/orchestrator/todos/[id]-[slug].md
```

### Step 5: Output Summary

```markdown
## Multi-Perspective Review Summary

### Target
[What was reviewed]

### Critical Issues (HIGH)
| Source | Issue | Location | Recommendation |
|--------|-------|----------|----------------|

### Warnings (MEDIUM)
| Source | Issue | Location | Recommendation |
|--------|-------|----------|----------------|

### Suggestions (LOW)
| Source | Issue | Location | Recommendation |
|--------|-------|----------|----------------|

### Todos Created
- [ ] TODO-001: [issue]
- [ ] TODO-002: [issue]
```

---

## BEGIN REVIEW

1. Parse target from: $ARGUMENTS
2. Read/fetch the code
3. Spawn 5 reviewers in parallel
4. Synthesize and output results
