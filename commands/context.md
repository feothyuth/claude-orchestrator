---
description: Preload and summarize codebase context before orchestration - reduces token waste
argument-hint: [directory path or file pattern]
---

# Context Preloader

**Target:** $ARGUMENTS

---

## PURPOSE

Before running `/orchestrate`, preload relevant context to:
1. Reduce agent discovery time
2. Provide consistent context to all agents
3. Identify architecture patterns
4. Map dependencies

---

## EXECUTION STEPS

### Step 1: Parse Target

From $ARGUMENTS determine:
- Single file: Read and summarize
- Directory: Scan structure and key files
- Pattern (e.g., `**/*.rs`): Find and summarize matching files

### Step 2: Scan Structure

```bash
# Get directory tree
ls -la [target]

# Find key files
- README.md, Cargo.toml, package.json, pyproject.toml
- Main entry points (main.rs, index.ts, app.py)
- Configuration files
```

### Step 3: Analyze Architecture

Detect and document:
- **Language/Framework**: Rust/Tokio, Python/FastAPI, TypeScript/React, etc.
- **Project Type**: CLI, API, Library, Web App
- **Dependencies**: External crates/packages/modules
- **Module Structure**: How code is organized
- **Patterns Used**: Error handling, async, state management

### Step 4: Create Context Summary

Store at `/home/rnd/.claude/orchestrator/context_cache.md`:

```markdown
## Context Summary

### Generated
[timestamp]

### Target
[path/pattern]

### Project Overview
- Type: [CLI/API/Library/Web]
- Language: [Rust/Python/TypeScript]
- Framework: [if applicable]

### Structure
```
[directory tree]
```

### Key Files
| File | Purpose | Lines |
|------|---------|-------|
| [path] | [what it does] | [count] |

### Dependencies
| Dependency | Version | Purpose |
|------------|---------|---------|
| [name] | [ver] | [why] |

### Architecture Patterns
- [pattern 1]: [where used]
- [pattern 2]: [where used]

### Entry Points
- [main file]: [description]

### Hot Spots (frequently modified)
- [file]: [why it matters]

### Recommendations for Agents
- rust-pro: Focus on [areas]
- security-auditor: Check [concerns]
- performance-reviewer: Look at [bottlenecks]
```

### Step 5: Output Summary

Display the context summary so user can verify before orchestration.

---

## USAGE PATTERN

```
/context src/exchanges/    # Preload exchange code context
/orchestrate add new exchange handler  # Agents now have context
```

---

## QUICK MODES

| Command | Action |
|---------|--------|
| `/context .` | Scan current directory |
| `/context src/` | Scan src directory |
| `/context **/*.rs` | Scan all Rust files |
| `/context refresh` | Re-scan last target |

---

## BEGIN CONTEXT PRELOAD

1. Parse $ARGUMENTS
2. Scan target files/directories
3. Analyze architecture
4. Create context summary
5. Output for verification
