---
description: Create or manage file-based todos with YAML frontmatter
argument-hint: [create|list|complete|ready] [description]
---

# File-Based Todo Management

**Command:** $ARGUMENTS

## Todo File Location
`/home/rnd/.claude/orchestrator/todos/`

## Commands

### Create Todo
```
/todo create Fix the N+1 query in users controller
```
Creates: `todos/001-fix-n-plus-one-query.md`

### List Todos
```
/todo list              # All todos
/todo list pending      # Only pending
/todo list ready        # Ready to work
```

### Mark Ready
```
/todo ready 001         # Mark todo 001 as ready to work
```

### Complete Todo
```
/todo complete 001      # Mark todo 001 as complete
```

---

## Todo File Format

```yaml
---
id: "001"
status: pending|ready|complete
priority: p1|p2|p3
created: 2025-11-28
tags: [performance, database]
dependencies: []
---

## Problem
[Description of the issue]

## Proposed Solution
[How to fix it]

## Acceptance Criteria
- [ ] Criteria 1
- [ ] Criteria 2

## Work Log
- [date] Started investigation
```

---

## Execution

Parse the command from $ARGUMENTS:

1. **create [description]**:
   - Generate next ID (scan existing files)
   - Create slug from description
   - Write new todo file with template
   - Default: status=pending, priority=p2

2. **list [filter]**:
   - Read all files in todos/
   - Parse YAML frontmatter
   - Display filtered list

3. **ready [id]**:
   - Find todo by ID
   - Change status: pending → ready

4. **complete [id]**:
   - Find todo by ID
   - Change status: ready → complete

Execute the requested command now.
