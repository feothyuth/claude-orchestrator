---
description: Run predefined agent pipelines for common workflows
argument-hint: [pipeline name] [task description]
---

# Pipeline Runner

**Pipeline:** $ARGUMENTS

---

## PURPOSE

Run predefined sequences of agents for common workflows.
Pipelines ensure consistent quality by running the right agents in the right order.

---

## AVAILABLE PIPELINES

### `feature` - Full Feature Development
```
1. [specialist] → Implement feature (auto-detect language)
2. test-writer → Write tests
3. [security-auditor, performance-reviewer] → Review (parallel)
4. code-reviewer → Final review
```

### `bugfix` - Bug Fix Workflow
```
1. [specialist] → Fix the bug
2. test-writer → Add regression test
3. code-reviewer → Review fix
```

### `refactor` - Safe Refactoring
```
1. test-writer → Ensure tests exist first
2. [specialist] → Refactor code
3. [architecture-reviewer, simplicity-reviewer] → Review (parallel)
```

### `review` - Comprehensive Review
```
1. [security-auditor, architecture-reviewer, performance-reviewer, simplicity-reviewer, code-reviewer] → All parallel
2. Synthesize results
```

### `security` - Security-Focused
```
1. security-auditor → Full security audit
2. [specialist] → Fix issues found
3. security-auditor → Verify fixes
```

---

## PIPELINE DEFINITIONS

Pipelines are defined in `/home/rnd/.claude/orchestrator/pipelines/`

### Pipeline File Format
```yaml
name: feature
description: Full feature development pipeline
steps:
  - name: implement
    agent: auto  # auto-detect from file type
    parallel: false

  - name: test
    agent: test-writer
    parallel: false
    depends_on: implement

  - name: review
    agents:  # multiple = parallel
      - security-auditor
      - performance-reviewer
    parallel: true
    depends_on: test

  - name: final-review
    agent: code-reviewer
    parallel: false
    depends_on: review
```

---

## EXECUTION STEPS

### Step 1: Parse Arguments
```
/pipeline feature add user authentication
         ^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^
         pipeline      task description
```

### Step 2: Load Pipeline Definition
Read from `/home/rnd/.claude/orchestrator/pipelines/[name].yaml`
Or use built-in pipeline if not found.

### Step 3: Execute Steps

For each step:
1. Check dependencies complete
2. Spawn agent(s) via Task tool
3. Collect results
4. Pass context to next step

**Parallel steps:** Multiple Task calls in ONE message
**Sequential steps:** Wait for previous to complete

### Step 4: Report Results

```markdown
## Pipeline Execution: [name]

### Task
[description]

### Steps Executed
| Step | Agent(s) | Status | Duration |
|------|----------|--------|----------|
| implement | rust-pro | ✅ Done | - |
| test | test-writer | ✅ Done | - |
| review | security, perf | ✅ Done | - |
| final | code-reviewer | ✅ Done | - |

### Results Summary
[combined output from all steps]

### Files Modified
- [list of files]

### Issues Found
- [any issues from reviewers]
```

---

## CREATING CUSTOM PIPELINES

```bash
# Create new pipeline
Write to /home/rnd/.claude/orchestrator/pipelines/my-pipeline.yaml
```

---

## QUICK USAGE

```
/pipeline feature add dark mode toggle
/pipeline bugfix fix the login timeout issue
/pipeline refactor clean up the database module
/pipeline review src/main.rs
/pipeline security check auth system
```

---

## BEGIN PIPELINE

1. Parse pipeline name and task from $ARGUMENTS
2. Load pipeline definition
3. Execute steps in order (parallel where defined)
4. Report results
