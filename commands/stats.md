---
description: Display orchestrator metrics and usage statistics from memory files
---

# Orchestrator Statistics Dashboard

Display metrics from the orchestrator memory system.

---

## DATA SOURCES

Read from:
```
/home/rnd/.claude/orchestrator/memory/learning_metrics.json
/home/rnd/.claude/orchestrator/memory/success_patterns.json
/home/rnd/.claude/orchestrator/memory/failure_patterns.json
```

---

## METRICS TO DISPLAY

### Global Metrics
From `learning_metrics.json`:
- Total projects completed
- Last updated date
- Success rate (if tracked)

### Pattern Analysis
From `success_patterns.json`:
- Total success patterns recorded
- Most common categories
- Most used technologies

From `failure_patterns.json`:
- Total failure patterns recorded
- Common failure types
- Lessons learned

### Agent Usage (if tracked)
- Most frequently used agents
- Agent success rates
- Average agents per project

---

## OUTPUT FORMAT

```markdown
## Orchestrator Statistics

### Overview
| Metric | Value |
|--------|-------|
| Total Projects | X |
| Success Patterns | Y |
| Failure Patterns | Z |
| Last Updated | YYYY-MM-DD |

### Success Patterns by Category
| Category | Count | Examples |
|----------|-------|----------|
| [category] | X | [pattern names] |

### Top Technologies
| Technology | Occurrences |
|------------|-------------|
| Rust | X |
| Python | Y |
| TypeScript | Z |

### Failure Analysis
| Failure Type | Count | Prevention |
|--------------|-------|------------|
| [type] | X | [lesson] |

### Recent Activity
- [date]: [pattern/project]
- [date]: [pattern/project]

### Recommendations
Based on patterns:
1. [recommendation based on success patterns]
2. [recommendation based on failure patterns]
```

---

## EXECUTION

1. Read all memory files
2. Parse and aggregate data
3. Calculate statistics
4. Generate formatted report
5. Provide actionable recommendations

BEGIN STATISTICS REPORT.
