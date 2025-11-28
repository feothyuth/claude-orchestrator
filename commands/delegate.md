---
description: Delegate a task to a specialist agent
argument-hint: @agent-name task description
---

Delegate this task to a specialist: $ARGUMENTS

## Available Specialist Agents

### Development
- `@rust-pro` - Rust 1.75+, async/await, tokio, systems programming
- `@python-pro` - Python 3.12+, FastAPI, uv, ruff, modern tooling
- `@typescript-pro` - TypeScript 5.x, Node.js, type-level programming
- `@frontend-developer` - React, Next.js 14+, shadcn/ui, Tailwind

### Infrastructure & Security
- `@security-auditor` - OWASP, auth flows, vulnerability assessment
- `@database-admin` - SQL optimization, PostgreSQL, migrations

### Quality & Review
- `@code-reviewer` - Code quality, performance, maintainability

## Usage Examples

```
/delegate @rust-pro implement WebSocket reconnection logic
/delegate @python-pro create FastAPI endpoint for authentication
/delegate @security-auditor review auth flow in src/auth/
/delegate @frontend-developer build React form with validation
```

## Instructions

Parse the @agent-name from the arguments and use the Task tool to spawn that agent with the remaining task description. Provide full context about the current project.
