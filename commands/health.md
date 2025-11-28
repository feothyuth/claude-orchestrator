---
description: Verify orchestrator setup - checks agents, memory files, and configuration
---

# Orchestrator Health Check

Run diagnostic checks on the orchestrator setup.

---

## CHECKS TO PERFORM

### 1. Memory Files
Verify these files exist and contain valid JSON:
```
/home/rnd/.claude/orchestrator/memory/success_patterns.json
/home/rnd/.claude/orchestrator/memory/failure_patterns.json
/home/rnd/.claude/orchestrator/memory/project_templates.json
/home/rnd/.claude/orchestrator/memory/learning_metrics.json
```

### 2. Agent Files
Verify these agents exist and have valid YAML frontmatter:
```
/home/rnd/.claude/agents/orchestrator.md
/home/rnd/.claude/agents/rust-pro.md
/home/rnd/.claude/agents/python-pro.md
/home/rnd/.claude/agents/typescript-pro.md
/home/rnd/.claude/agents/frontend-developer.md
/home/rnd/.claude/agents/security-auditor.md
/home/rnd/.claude/agents/code-reviewer.md
/home/rnd/.claude/agents/database-admin.md
/home/rnd/.claude/agents/architecture-reviewer.md
/home/rnd/.claude/agents/performance-reviewer.md
/home/rnd/.claude/agents/simplicity-reviewer.md
/home/rnd/.claude/agents/test-writer.md
```

### 3. Directory Structure
Verify directories exist:
```
/home/rnd/.claude/orchestrator/
/home/rnd/.claude/orchestrator/memory/
/home/rnd/.claude/orchestrator/todos/
/home/rnd/.claude/orchestrator/knowledge/
/home/rnd/.claude/orchestrator/checkpoints/
/home/rnd/.claude/orchestrator/pipelines/
```

### 4. Commands
Verify commands exist:
```
/home/rnd/.claude/commands/orchestrate.md
/home/rnd/.claude/commands/delegate.md
/home/rnd/.claude/commands/todo.md
/home/rnd/.claude/commands/codify.md
/home/rnd/.claude/commands/review.md
/home/rnd/.claude/commands/health.md
/home/rnd/.claude/commands/stats.md
/home/rnd/.claude/commands/retro.md
/home/rnd/.claude/commands/context.md
```

---

## EXECUTION

1. Run all checks using Bash and Read tools
2. Collect results
3. Output report:

```markdown
## Orchestrator Health Report

### Memory Files
| File | Status | Issues |
|------|--------|--------|
| success_patterns.json | ✅ OK / ❌ FAIL | [issue] |
| failure_patterns.json | ✅ OK / ❌ FAIL | [issue] |
| project_templates.json | ✅ OK / ❌ FAIL | [issue] |
| learning_metrics.json | ✅ OK / ❌ FAIL | [issue] |

### Agents
| Agent | Status | Issues |
|-------|--------|--------|
| orchestrator | ✅ OK / ❌ FAIL | [issue] |
| rust-pro | ✅ OK / ❌ FAIL | [issue] |
| ... | ... | ... |

### Directories
| Directory | Status |
|-----------|--------|
| /orchestrator/ | ✅ OK / ❌ MISSING |
| /orchestrator/memory/ | ✅ OK / ❌ MISSING |
| ... | ... |

### Commands
| Command | Status |
|---------|--------|
| /orchestrate | ✅ OK / ❌ MISSING |
| /delegate | ✅ OK / ❌ MISSING |
| ... | ... |

### Summary
- Total Checks: X
- Passed: Y
- Failed: Z
- Health Score: Y/X (XX%)

### Recommendations
1. [Fix suggestion if any issues]
```

---

## BEGIN HEALTH CHECK

Run all checks now and output the report.
