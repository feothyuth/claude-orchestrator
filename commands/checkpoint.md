---
description: Save current state before risky changes - enables rollback if things break
argument-hint: [checkpoint name]
---

# Create Checkpoint

**Name:** $ARGUMENTS

---

## PURPOSE

Save the current state of modified files before making risky changes.
Enables `/rollback` if something goes wrong.

---

## EXECUTION STEPS

### Step 1: Determine Checkpoint Name

If $ARGUMENTS is empty, generate name:
```
checkpoint-YYYYMMDD-HHMMSS
```

Otherwise use provided name (sanitize for filesystem).

### Step 2: Identify Files to Save

Options:
1. **Git-tracked changes**: `git status` to find modified files
2. **Recent session files**: Files modified in current session
3. **Specified files**: If user provides file list

### Step 3: Create Checkpoint Directory

```
/home/rnd/.claude/orchestrator/checkpoints/[name]/
```

### Step 4: Save File States

For each file:
1. Copy current content to checkpoint directory
2. Preserve relative path structure
3. Record file metadata

### Step 5: Create Checkpoint Manifest

Write to `/home/rnd/.claude/orchestrator/checkpoints/[name]/manifest.json`:

```json
{
  "name": "[checkpoint name]",
  "created": "YYYY-MM-DD HH:MM:SS",
  "description": "[user-provided or auto-generated]",
  "files": [
    {
      "path": "/absolute/path/to/file",
      "relative": "relative/path",
      "size": 1234,
      "checksum": "sha256..."
    }
  ],
  "git_info": {
    "branch": "[current branch]",
    "commit": "[current commit hash]",
    "dirty": true/false
  }
}
```

### Step 6: Confirm Creation

```markdown
## Checkpoint Created

### Name
`[checkpoint name]`

### Location
`/home/rnd/.claude/orchestrator/checkpoints/[name]/`

### Files Saved
| File | Size |
|------|------|
| [path] | [size] |

### Rollback Command
```
/rollback [name]
```

### Note
This checkpoint will be kept for 7 days unless manually deleted.
```

---

## USAGE EXAMPLES

```
/checkpoint                     # Auto-named checkpoint
/checkpoint before-refactor     # Named checkpoint
/checkpoint risky-db-migration  # Descriptive name
```

---

## CHECKPOINT MANAGEMENT

List checkpoints:
```bash
ls /home/rnd/.claude/orchestrator/checkpoints/
```

Delete old checkpoints:
```bash
rm -rf /home/rnd/.claude/orchestrator/checkpoints/[name]
```

---

## BEGIN CHECKPOINT

1. Parse checkpoint name from $ARGUMENTS
2. Find files to save
3. Create checkpoint directory
4. Copy files
5. Create manifest
6. Confirm to user
