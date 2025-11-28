---
description: Restore files from a checkpoint - undo changes that broke things
argument-hint: [checkpoint name or "list" to see available]
---

# Rollback to Checkpoint

**Target:** $ARGUMENTS

---

## PURPOSE

Restore files to a previous state from a saved checkpoint.
Use when changes broke something and you need to undo.

---

## EXECUTION STEPS

### Step 1: Parse Arguments

| Argument | Action |
|----------|--------|
| `list` | Show available checkpoints |
| `[name]` | Rollback to named checkpoint |
| `latest` | Rollback to most recent checkpoint |
| (empty) | Show available checkpoints |

### Step 2: List Mode

If $ARGUMENTS is "list" or empty:

```markdown
## Available Checkpoints

| Name | Created | Files | Size |
|------|---------|-------|------|
| [name] | [date] | [count] | [total] |

### Usage
```
/rollback [name]
```
```

### Step 3: Rollback Mode

If checkpoint name provided:

1. **Verify checkpoint exists**
   ```
   /home/rnd/.claude/orchestrator/checkpoints/[name]/
   ```

2. **Read manifest**
   ```
   /home/rnd/.claude/orchestrator/checkpoints/[name]/manifest.json
   ```

3. **Confirm with user** (IMPORTANT)
   ```
   ⚠️ WARNING: This will overwrite the following files:
   - [file1]
   - [file2]

   Current changes will be LOST. Continue? (yes/no)
   ```

4. **Create backup of current state** (safety)
   ```
   Auto-create checkpoint: pre-rollback-[timestamp]
   ```

5. **Restore files**
   For each file in manifest:
   - Read from checkpoint
   - Write to original location
   - Verify restoration

6. **Confirm completion**

### Step 4: Report

```markdown
## Rollback Complete

### Checkpoint
`[name]` (created [date])

### Files Restored
| File | Status |
|------|--------|
| [path] | ✅ Restored |

### Backup Created
Before rollback, current state saved to:
`pre-rollback-[timestamp]`

### Next Steps
- Verify the restored code works
- Delete the backup if rollback successful: `/rollback delete pre-rollback-[timestamp]`
```

---

## SAFETY FEATURES

1. **Auto-backup**: Always creates backup before rollback
2. **Confirmation**: Requires confirmation before overwriting
3. **Verification**: Checks files were restored correctly

---

## USAGE EXAMPLES

```
/rollback list                  # See available checkpoints
/rollback before-refactor       # Restore to specific checkpoint
/rollback latest                # Restore to most recent
/rollback delete old-checkpoint # Delete a checkpoint
```

---

## ERROR HANDLING

| Error | Action |
|-------|--------|
| Checkpoint not found | List available checkpoints |
| File conflict | Show diff, ask for confirmation |
| Partial failure | Report which files failed, suggest manual fix |

---

## BEGIN ROLLBACK

1. Parse $ARGUMENTS
2. If list mode, show checkpoints
3. If rollback mode:
   a. Verify checkpoint
   b. Confirm with user
   c. Backup current state
   d. Restore files
   e. Report results
