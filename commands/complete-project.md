---
description: (Optional) Manually update memory files - usually automatic via /orchestrate
argument-hint: [project summary or leave blank]
---

# MANUAL MEMORY UPDATE

**Note:** This is usually NOT needed. `/orchestrate` automatically updates memory.
Use this only if you did work outside of orchestration and want to record it.

**Summary:** $ARGUMENTS

---

## MEMORY UPDATES

You MUST update these files NOW:

### 1. Update Learning Metrics
Edit `~/.claude/orchestrator/memory/learning_metrics.json`:
- Increment `global_metrics.total_projects` by 1
- Update `global_metrics.successful_projects` if successful
- Update `global_metrics.failed_projects` if failed
- Update `last_updated` to today's date
- Add technologies used to `most_common_technologies`

### 2. Update Success Patterns (if applicable)
Edit `~/.claude/orchestrator/memory/success_patterns.json`:
- Add new successful patterns discovered
- Update success_rate for existing patterns used
- Add to `insights.common_success_factors`

### 3. Update Failure Patterns (if applicable)
Edit `~/.claude/orchestrator/memory/failure_patterns.json`:
- Add any anti-patterns discovered
- Document warning signs encountered
- Add solutions that worked

---

## TEMPLATE FOR learning_metrics.json UPDATE

Find and update:
```json
"global_metrics": {
  "total_projects": [INCREMENT BY 1],
  "successful_projects": [INCREMENT IF SUCCESS],
  "last_updated": "[TODAY'S DATE]"
}
```

---

## EXECUTE NOW

1. Read current memory files
2. Apply updates based on project outcome
3. Edit the JSON files
4. Confirm completion to user

BEGIN MEMORY UPDATE.
