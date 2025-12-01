---
description: Orchestrate complex tasks with intelligent memory, pattern learning, and multi-agent coordination
argument-hint: [task description]
allowed-tools: "Task,Read,Write,Edit,Glob,Grep,Bash(python3:*),Bash(git:*)"
---

# ORCHESTRATION MODE v3.0

**Task:** $ARGUMENTS

---

## TASK COMPLEXITY ROUTING (MANDATORY FIRST STEP)

**BEFORE doing anything else, classify the task complexity:**

```
┌─────────────────────────────────────────────────────────────┐
│  SIMPLE (target: < 2 minutes)                               │
│  ─────────────────────────────────────────────────────────  │
│  Triggers: "fix", "add logging", "rename", "typo",          │
│            "update comment", "change value", "small"        │
│  Scope: Single file, known location, obvious fix            │
│  → SKIP Steps 1-7, 9-14 → Jump directly to Step 8 + 15      │
│  → Use model="haiku" for agent                              │
│  → Timeout: 120 seconds max                                 │
├─────────────────────────────────────────────────────────────┤
│  MEDIUM (target: 2-8 minutes)                               │
│  ─────────────────────────────────────────────────────────  │
│  Triggers: "implement", "add feature", "integrate",         │
│            "connect", "new endpoint", "create"              │
│  Scope: Multi-file, known codebase area                     │
│  → SKIP Steps 3, 4, 7, 11, 14 → Run 1-2, 5-6, 8-10, 12, 15  │
│  → Use model="sonnet" for agent                             │
│  → Timeout: 300 seconds max                                 │
├─────────────────────────────────────────────────────────────┤
│  COMPLEX (target: 8-15 minutes)                             │
│  ─────────────────────────────────────────────────────────  │
│  Triggers: "design", "architect", "refactor system",        │
│            "new module", "unknown area", "investigate"      │
│  Scope: Architecture changes, new systems, exploration      │
│  → Run full 15-step pipeline                                │
│  → Use model="opus" for critical decisions                  │
│  → Timeout: 600 seconds max                                 │
└─────────────────────────────────────────────────────────────┘
```

### SIMPLE TASK FAST PATH

**If task matches SIMPLE triggers → Execute this immediately:**

```
SIMPLE TASK EXECUTION:
1. Parse task description for target file(s) and change
2. Spawn ONE agent with direct, minimal prompt:

   Task(
     subagent_type="[appropriate-agent]",
     model="haiku",
     prompt="Fix [specific issue] in [file:line]. The problem is [X]. The fix is [Y]."
   )

3. Report result to user (Step 15 only)
4. DONE - No memory, no blackboard, no verification gauntlet
```

**Example SIMPLE prompts (keep under 100 words):**
```
# BAD - too verbose:
"You are @rust-pro with PIPELINE_ID xyz. Initialize blackboard at REDIS_URL.
Read the context from Step 4. Coordinate with other agents. Write to blackboard
when done. The task is to fix a type error in src/engine.rs line 145..."
[50+ more lines]

# GOOD - direct and minimal:
"Fix type error in src/engine.rs:145. Error: expected Result<Fill>, got Fill.
Fix: wrap return value with Ok(). Run cargo check to verify."
```

### MEDIUM TASK FLOW

**If task matches MEDIUM triggers:**
```
Step 1: Quick memory check (30s max)
Step 2: Skip
Step 3: Skip
Step 4: Skip
Step 5: Brief plan (60s max) - 3-5 bullet points only
Step 6: Skip blackboard - use direct delegation
Step 7: Skip shadow workspace
Step 8: Delegate to agent(s) with PARALLEL execution if multiple files
Step 9: Basic verification (build/test only)
Step 10: One retry if fails
Step 11: Skip multi-review
Step 12: Quick success/fail note
Step 13: Skip
Step 14: Skip
Step 15: Report
```

### TIMEOUT ENFORCEMENT

**ALL agent calls MUST specify timeout:**
```
Task(
  subagent_type="...",
  model="haiku|sonnet|opus",
  prompt="...",
  timeout=120000  # milliseconds - 120s for simple, 300s for medium, 600s for complex
)
```

**If agent hits timeout → abort, use partial results, continue pipeline**

### RETRY LOGIC

**Retry with exponential backoff on transient failures:**

**Retry on:**
- API rate limits (429 status)
- Server errors (5xx status)
- Network timeouts
- Transient connection failures

**Exponential backoff schedule (max 3 retries):**
- Attempt 1: Wait 1s
- Attempt 2: Wait 2s
- Attempt 3: Wait 4s
- Attempt 4: Wait 8s
- Final attempt: Wait 16s

**Do NOT retry on:**
- Validation errors (4xx status codes except 429)
- Agent execution failures
- Budget exceeded errors
- Authentication failures

**Logging:**
- Log each retry attempt with: timestamp, error type, retry count, wait duration
- Log final success or failure after all retries exhausted

### BUDGET GUARDRAILS

**Maximum token budgets per task complexity:**
- SIMPLE: 50K tokens max
- MEDIUM: 150K tokens max
- COMPLEX: 500K tokens max

**Budget monitoring:**
```
budget_remaining = max_tokens - tokens_used
```

**If budget exceeded → abort agent immediately**

**Log warning when 80% of budget consumed**

---

### CONTEXT SUMMARIZATION

**When conversation history exceeds 5000 tokens, summarize before delegating to agents:**

```
Task(
  subagent_type="summarizer",
  model="haiku",
  prompt="Summarize the key points from this context relevant to: [task description]",
  timeout=60000  # 60s for summarization
)
```

**Requirements:**
- Keep summaries under 500 tokens
- Extract only information relevant to the current task
- Pass summarized context to agents instead of full conversation history
- Preserve critical details (file paths, error messages, specific requirements)

---

## ARCHITECTURE MODES

```
┌─────────────────────────────────────────────────────────────┐
│  LITE MODE (Default) - Works Immediately                    │
│  ─────────────────────────────────────────────────────────  │
│  SQLite → Tiered memory with Generative Agents scoring     │
│  File-based → Blackboard in SQLite for coordination        │
│  Local → Verification via native tools (no Docker needed)  │
│  Performance: ~95% of full infrastructure                  │
│                                                             │
│  Storage: ~/.claude/orchestrator/memory/orchestrator.db    │
│  Module:  infrastructure/memory_lite.py                     │
├─────────────────────────────────────────────────────────────┤
│  FULL MODE (Optional) - Maximum Performance                 │
│  ─────────────────────────────────────────────────────────  │
│  PostgreSQL → pgvector for vector similarity search        │
│  Redis → O(1) Blackboard with pub/sub                      │
│  Docker → Shadow workspace for isolated verification       │
│  MCP → Memory server for tool-based access                 │
│                                                             │
│  Setup: ./orchestrator/infrastructure/setup.sh             │
│  Requires: Docker Desktop                                   │
└─────────────────────────────────────────────────────────────┘
```

**Mode Detection:**
```python
# Auto-detect mode based on available infrastructure
import os
FULL_MODE = all([
    os.environ.get('DATABASE_URL'),
    os.environ.get('REDIS_URL'),
    os.path.exists('/var/run/docker.sock')
])
# If FULL_MODE: use PostgreSQL/Redis/Docker
# Else: use memory_lite.py (SQLite)
```

---

## MANDATORY BEHAVIOR - NO EXCEPTIONS

### RULE 1: NEVER WRITE CODE
- You MUST NOT write any implementation code
- ALL code comes from specialist agents via Task tool
- Violation of this rule = FAILURE

### RULE 2: ALWAYS USE TASK TOOL
For ANY implementation, you MUST call:
```
Task(subagent_type="general-purpose", prompt="You are @[specialist]. [detailed task]...")
```

### RULE 3: ALWAYS UPDATE MEMORY
After completion, you MUST:
- Record episode (success/failure with context)
- Update patterns with outcome
- Run consolidation if session ending
- Store reflections if failures occurred

### RULE 4: USE MODEL ROUTING
Route tasks to appropriate model based on complexity:

| Task Type | Model | Timeout | Use Case |
|-----------|-------|---------|----------|
| Exploration/Search | haiku | 60s | Codebase search, file finding, research |
| Simple fixes | haiku | 120s | Typos, small edits, logging |
| Standard implementation | sonnet | 180s | Features, bug fixes, tests |
| Architecture/Complex | opus | 300s | Design decisions, refactoring |

**CRITICAL: Exploration agents (subagent_type="Explore") MUST use model="haiku"**

### RULE 5: USE MCP TOOLS WHEN AVAILABLE

Before starting work, check for available MCP tools that can help complete the task more efficiently.

**Common MCP Tools:**
- **Search engines**: `mcp__search`, `mcp__websearch` - for web searches and research
- **Web fetch**: `mcp__fetch`, `mcp__webfetch` - for fetching web content
- **Playwright browser**: `mcp__playwright`, `mcp__browser` - for browser automation and web scraping

**Guidelines:**
- Always prefer MCP tools over manual alternatives
- Use `mcp__search` instead of manual web scraping or curl commands
- Use `mcp__playwright` for complex web interactions instead of writing custom automation
- Check available tools with list_tools() or similar inspection methods before proceeding
- MCP tools are more reliable, efficient, and better integrated with the agent system

**Example:**
- DON'T: Use curl or requests library to manually scrape websites
- DO: Use `mcp__webfetch` or `mcp__search` for web content retrieval

---

## EXECUTION FLOW (15-STEP PIPELINE)

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Initialize Infrastructure                          │
│  STEP 2: Load Tiered Memory (PostgreSQL)                    │
│  STEP 3: Retrieve Past Reflections                          │
│  STEP 4: Context Compression (AST Repo Map)                 │
│  STEP 5: Analyze & Plan (with Model Routing)                │
│  STEP 6: Write Plan to Blackboard                           │
│  STEP 7: Create Shadow Workspace (Docker)                   │
│  STEP 8: Delegate to Agents (read/write Blackboard)         │
│  STEP 9: Verification Gauntlet (in Shadow)                  │
│  STEP 10: TDD Loop (3-strike max)                           │
│  STEP 11: Multi-Perspective Review                          │
│  STEP 12: Reflexion - Generate & Store                      │
│  STEP 13: Commit Shadow or Rollback                         │
│  STEP 14: Memory Consolidation ("Sleep")                    │
│  STEP 15: Report to User                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## STEP 1: Initialize Memory System

**Goal:** Initialize the appropriate memory backend based on available infrastructure

### 1.1 LITE MODE (Default)

```python
# LITE: SQLite-based memory - works immediately
from infrastructure.memory_lite import MemoryLite

memory = MemoryLite()  # Auto-creates ~/.claude/orchestrator/memory/orchestrator.db
stats = memory.stats()
print(f"Memory ready: {stats['patterns']} patterns, {stats['episodes']} episodes")
```

**What you get:**
- ✅ Tiered memory (episodic → semantic → procedural)
- ✅ Generative Agents retrieval scoring (relevance + importance + recency)
- ✅ Pattern learning from success/failure
- ✅ Temporal knowledge graph (valid_from/valid_until)
- ✅ Blackboard for multi-step coordination
- ✅ Memory consolidation ("sleep cycle")

### 1.2 FULL MODE (Optional - requires Docker)

```bash
# Setup full infrastructure (run once)
./orchestrator/infrastructure/setup.sh

# This starts:
# - PostgreSQL with pgvector (localhost:5432)
# - Redis for Blackboard (localhost:6379)
# - Builds Shadow Workspace Docker image
```

```bash
# Verify full mode is running
docker ps | grep -E "orchestrator-(postgres|redis)"
```

**PostgreSQL Schema:**
```sql
-- Episodic Memory (raw experiences)
CREATE TABLE IF NOT EXISTS episodic_memory (
    id SERIAL PRIMARY KEY,
    pipeline_run_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(32) NOT NULL, -- 'task_start', 'agent_call', 'verification', etc.
    agent_name VARCHAR(64),
    task_description TEXT,
    context JSONB, -- Full context snapshot
    result JSONB, -- Outcome, errors, metrics
    importance FLOAT DEFAULT 0.5, -- 0.0-1.0
    last_accessed TIMESTAMPTZ DEFAULT NOW()
);

-- Semantic Memory (consolidated patterns)
CREATE TABLE IF NOT EXISTS semantic_memory (
    id SERIAL PRIMARY KEY,
    pattern_name VARCHAR(128) UNIQUE NOT NULL,
    category VARCHAR(64) NOT NULL,
    description TEXT,
    key_elements JSONB,
    success_rate FLOAT DEFAULT 1.0,
    times_used INTEGER DEFAULT 1,
    last_used TIMESTAMPTZ DEFAULT NOW(),
    utility_score FLOAT GENERATED ALWAYS AS (
        (times_used * 0.4) + (success_rate * 0.3) +
        (EXTRACT(EPOCH FROM (NOW() - last_used)) / 3600 * 0.3)
    ) STORED
);

-- Procedural Memory (reflections)
CREATE TABLE IF NOT EXISTS procedural_memory (
    id SERIAL PRIMARY KEY,
    reflection_text TEXT NOT NULL,
    failure_context JSONB, -- What failed, why, how fixed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    relevance_tags TEXT[], -- For retrieval
    applied_count INTEGER DEFAULT 0,
    last_applied TIMESTAMPTZ
);

-- Knowledge Graph: Entities
CREATE TABLE IF NOT EXISTS entities (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(64) NOT NULL, -- 'file', 'function', 'module', 'component'
    entity_name VARCHAR(255) NOT NULL,
    metadata JSONB,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_modified TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(entity_type, entity_name)
);

-- Knowledge Graph: Relations
CREATE TABLE IF NOT EXISTS relations (
    id SERIAL PRIMARY KEY,
    source_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    relation_type VARCHAR(64) NOT NULL, -- 'imports', 'calls', 'uses', 'depends_on'
    target_entity_id INTEGER REFERENCES entities(id) ON DELETE CASCADE,
    weight FLOAT DEFAULT 1.0, -- Importance of relationship
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_entity_id, relation_type, target_entity_id)
);

-- Indexes for fast retrieval
CREATE INDEX IF NOT EXISTS idx_episodic_pipeline ON episodic_memory(pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_episodic_timestamp ON episodic_memory(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_episodic_importance ON episodic_memory(importance DESC);
CREATE INDEX IF NOT EXISTS idx_semantic_category ON semantic_memory(category);
CREATE INDEX IF NOT EXISTS idx_semantic_utility ON semantic_memory(utility_score DESC);
CREATE INDEX IF NOT EXISTS idx_procedural_tags ON procedural_memory USING GIN(relevance_tags);
CREATE INDEX IF NOT EXISTS idx_entities_type_name ON entities(entity_type, entity_name);
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_entity_id);
```

### 1.3 Redis Blackboard Connection
```bash
# Test Redis connection
redis-cli -u $REDIS_URL PING 2>&1

# Initialize Blackboard structures:
# - artifacts:[pipeline_id]:* (HASH) - Stores artifacts (plan, code, tests)
# - locks:[pipeline_id]:* (STRING with expiry) - File-level locks
# - status:[pipeline_id] (HASH) - Pipeline status tracking
# - agents:[pipeline_id]:* (LIST) - Agent activity log
```

**Redis Blackboard Schema:**
```python
# Artifact structure (stored as JSON in Redis Hash)
{
    "artifact_id": "plan_v1",
    "artifact_type": "PLAN|CODE|TEST|REVIEW|REFLECTION",
    "content": "...",
    "created_by": "orchestrator|agent_name",
    "created_at": "2025-11-29T10:30:00Z",
    "version": 1,
    "dependencies": ["artifact_id_1", "artifact_id_2"]
}

# Lock structure (Redis String with TTL)
Key: locks:[pipeline_id]:src/main.py
Value: agent_name
TTL: 300 seconds (auto-release)

# Status tracking (Redis Hash)
Key: status:[pipeline_id]
Fields:
  - phase: "planning|implementation|verification|review|complete"
  - progress: "0-100"
  - active_agents: "agent1,agent2"
  - errors: "0"
```

### 1.4 Docker Shadow Workspace
```bash
# Check if Docker is running
docker info 2>&1

# Build base shadow workspace image (if not exists)
# This is a lightweight container with:
# - Git
# - Common build tools (cargo, npm, pip, etc.)
# - Testing frameworks
# - Linters/formatters

# Check for existing image
if ! docker images | grep -q "rvgb-shadow-workspace"; then
    echo "Building shadow workspace image..."
    # Build from Dockerfile (if available) or use alpine + tools
fi
```

**Shadow Workspace Dockerfile:**
```dockerfile
FROM alpine:3.19

# Install base tools
RUN apk add --no-cache \
    git \
    bash \
    curl \
    python3 py3-pip \
    nodejs npm \
    rust cargo \
    go \
    openjdk11 \
    && rm -rf /var/cache/apk/*

# Install testing frameworks
RUN pip3 install pytest pytest-cov mypy ruff bandit --break-system-packages
RUN npm install -g jest @typescript-eslint/parser eslint
RUN cargo install cargo-test

# Set working directory
WORKDIR /workspace

# Entry point: run verification gauntlet
COPY verify.sh /usr/local/bin/verify
RUN chmod +x /usr/local/bin/verify

CMD ["/bin/bash"]
```

### 1.5 MCP Memory Server
```bash
# Check if MCP Memory Server is running
curl -s http://localhost:${MCP_MEMORY_SERVER_PORT:-3000}/health 2>&1

# If not running, start it (or skip if not installed)
# MCP Memory Server provides tool-based access to PostgreSQL memory
```

**MCP Memory Tools Available:**
```
- search_memory(query, limit=5) → Search episodic + semantic memory
- get_similar_patterns(context) → Retrieve patterns by similarity
- store_episode(event_type, context, result) → Store new episode
- get_relevant_reflections(context) → Retrieve past reflections
- update_knowledge_graph(entity, relation, target) → Update graph
- consolidate_memory(pipeline_run_id) → Trigger consolidation
```

### 1.6 Infrastructure Health Report
```markdown
## Infrastructure Status
- ✅/❌ PostgreSQL: [connected/disconnected] (tables: X)
- ✅/❌ Redis Blackboard: [connected/disconnected]
- ✅/❌ Docker Daemon: [running/stopped]
- ✅/❌ Shadow Workspace Image: [built/missing]
- ✅/⚠️/❌ MCP Memory Server: [running/not installed/error]

**Fallback Mode:**
If any component unavailable, fall back to:
- PostgreSQL → JSON files in /home/rnd/.claude/orchestrator/memory/
- Redis → In-memory dict (no persistence)
- Docker → Direct workspace (no isolation)
- MCP → Direct PostgreSQL queries via psql
```

**SKIP Infrastructure Check if:**
- User says "offline mode" or "no infrastructure"
- Quick mode enabled

---

## STEP 2: Load Tiered Memory (PostgreSQL)

**Goal:** Retrieve relevant past experiences to inform current task

### 2.1 Memory Retrieval with Scoring

**Scoring Formula:**
```
Score = 0.5 * Relevance + 0.3 * Importance + 0.2 * Recency

Where:
- Relevance: Semantic similarity to current task (0.0-1.0)
- Importance: Stored importance value (0.0-1.0)
- Recency = e^(-0.995 * hours_since_access)
```

### 2.2 Episodic Memory Retrieval

**Query episodic_memory table:**
```sql
-- Retrieve top 10 relevant episodes
SELECT
    id,
    event_type,
    agent_name,
    task_description,
    context,
    result,
    importance,
    EXTRACT(EPOCH FROM (NOW() - last_accessed)) / 3600 AS hours_since,
    EXP(-0.995 * EXTRACT(EPOCH FROM (NOW() - last_accessed)) / 3600) AS recency_score
FROM episodic_memory
WHERE
    -- Filter by relevance (simple keyword match for now)
    task_description ILIKE '%[detected_keywords]%'
    OR context::text ILIKE '%[detected_keywords]%'
ORDER BY
    (0.5 * 0.8 + 0.3 * importance + 0.2 * EXP(-0.995 * EXTRACT(EPOCH FROM (NOW() - last_accessed)) / 3600)) DESC
LIMIT 10;

-- Update last_accessed for retrieved episodes
UPDATE episodic_memory
SET last_accessed = NOW()
WHERE id IN ([retrieved_ids]);
```

**Using MCP (if available):**
```
mcp__memory__search_memory(
    query="implement order matching engine with websockets",
    limit=5
)
```

### 2.3 Semantic Memory Retrieval

**Query semantic_memory table:**
```sql
-- Retrieve patterns by category and utility
SELECT
    pattern_name,
    category,
    description,
    key_elements,
    success_rate,
    times_used,
    utility_score
FROM semantic_memory
WHERE
    category = '[detected_category]' -- e.g., 'rust-async', 'frontend-react'
    AND utility_score > 0.3 -- Minimum utility threshold
ORDER BY
    utility_score DESC
LIMIT 5;

-- Update usage stats for retrieved patterns
UPDATE semantic_memory
SET last_used = NOW()
WHERE pattern_name IN ([retrieved_patterns]);
```

**Using MCP (if available):**
```
mcp__memory__get_similar_patterns(
    context="rust websocket order matching"
)
```

### 2.4 Memory Hierarchy

**TIER 1 - Always Load (Core Context):**
- Total orchestrations run
- Common technologies encountered
- Overall success rate
- Recent failure patterns

**TIER 2 - Conditionally Load (Relevant Patterns):**
- Patterns matching detected category
- Episodes with high relevance score (>0.7)
- High-utility patterns (utility_score > 0.8)

**TIER 3 - On-Demand (Archival):**
- Older episodes (>30 days old)
- Low-utility patterns (utility_score < 0.3)
- Edge cases and rare scenarios

### 2.5 Memory Loading Summary

```markdown
## Memory Loaded
**Episodic Memory:**
- Retrieved: 7 episodes (avg score: 0.82)
- Most relevant: "WebSocket connection pooling fix" (score: 0.94)
- Total episodes in DB: 1,247

**Semantic Memory:**
- Patterns loaded: 4
  - rust-async-websockets (utility: 0.91, used: 12x)
  - order-matching-algorithms (utility: 0.87, used: 8x)
  - error-handling-async (utility: 0.76, used: 15x)
  - docker-compose-setup (utility: 0.68, used: 5x)

**Fallback (if PostgreSQL unavailable):**
- Loading from JSON: /home/rnd/.claude/orchestrator/memory/
```

---

## STEP 3: Retrieve Past Reflections

**Goal:** Learn from past failures to avoid repeating mistakes

### 3.1 Reflection Retrieval

**Query procedural_memory table:**
```sql
-- Retrieve reflections by relevance tags
SELECT
    id,
    reflection_text,
    failure_context,
    created_at,
    applied_count
FROM procedural_memory
WHERE
    -- Match by tags (array overlap)
    relevance_tags && ARRAY['[detected_tag_1]', '[detected_tag_2]']::TEXT[]
ORDER BY
    applied_count ASC, -- Prefer less-used reflections (avoid over-fitting)
    created_at DESC     -- Prefer recent learnings
LIMIT 3;

-- Update applied_count for retrieved reflections
UPDATE procedural_memory
SET
    applied_count = applied_count + 1,
    last_applied = NOW()
WHERE id IN ([retrieved_ids]);
```

**Using MCP (if available):**
```
mcp__memory__get_relevant_reflections(
    context="async rust websocket error handling"
)
```

### 3.2 Inject Reflections into Agent Context

**Format reflections for agent prompts:**
```markdown
## PAST LEARNINGS (Reflexion)
These are reflections from similar tasks. Learn from them:

**Reflection 1:** [reflection_text]
- Failure: [failure_context.what_failed]
- Root Cause: [failure_context.root_cause]
- Fix: [failure_context.fix_applied]
- Lesson: [failure_context.lesson]

**Reflection 2:** [...]
```

**Reflection Example:**
```json
{
    "reflection_text": "When implementing async WebSocket handlers in Rust, always use bounded channels (not unbounded) to prevent memory exhaustion under high load.",
    "failure_context": {
        "what_failed": "WebSocket server crashed after 10K concurrent connections",
        "root_cause": "Unbounded mpsc channel accumulated messages faster than processing",
        "fix_applied": "Changed to tokio::sync::mpsc::channel(1000)",
        "lesson": "Always bound async channels with reasonable capacity"
    },
    "relevance_tags": ["rust", "async", "websocket", "memory", "channels"],
    "applied_count": 2,
    "created_at": "2025-11-15T14:20:00Z"
}
```

### 3.3 Reflection Summary

```markdown
## Reflections Retrieved
- **3 reflections** loaded from procedural memory
- Tags matched: rust, async, websocket, error-handling
- Most relevant: "Always bound async channels" (applied 2x)
- Injected into agent prompts for awareness
```

---

## STEP 4: Context Compression (AST Repo Map)

**Goal:** Minimize tokens while maximizing relevant context

### 4.1 Build Repository Map

**Scan project structure:**
```bash
# Find all source files
Glob **/*.{rs,py,ts,tsx,js,jsx,go,java}

# For each file, extract:
# - Function/method signatures (not implementations)
# - Class/struct definitions (not bodies)
# - Import/export statements
# - Type definitions
```

**AST Extraction (example for Rust):**
```rust
// src/engine.rs (actual 500 lines)
// Compressed to:
pub struct OrderEngine { /* 8 fields */ }
impl OrderEngine {
    pub fn new(config: Config) -> Self;
    pub async fn process_order(&mut self, order: Order) -> Result<Fill>;
    pub async fn match_orders(&self) -> Vec<Match>;
    // ... 5 more methods
}
```

### 4.2 PageRank Relevance Scoring

**Build call graph:**
```
Entry points (weight: 1.0):
- src/main.rs → imports src/engine.rs (0.8)
- src/engine.rs → imports src/types.rs (0.6)
- src/types.rs → imports src/utils.rs (0.4)

Centrality scores:
- src/engine.rs: 0.95 (highest, many imports)
- src/types.rs: 0.80 (shared types)
- src/main.rs: 0.75 (entry point)
- src/utils.rs: 0.45 (utility functions)
- tests/*.rs: 0.20 (low priority)
```

### 4.3 Token Budget Management

**Target: 50K tokens**

```
Priority loading:
1. Entry points (main.rs, index.ts) - FULL
2. Files mentioned in task - FULL
3. High-centrality files - SIGNATURES ONLY
4. Low-centrality files - SUMMARY ONLY
5. Tests/configs - SKIP

If exceeds budget:
- Level 1: Load only signatures (no implementations)
- Level 2: Summarize large files
- Level 3: Drop low-relevance files
- Level 4: Request user to narrow scope
```

### 4.4 Context Summary

```markdown
## Repository Map (Compressed)
**Entry Points:**
- src/main.rs (async runtime, 3 modules) - 450 tokens
- src/engine.rs (OrderEngine struct, 8 methods) - 1,200 tokens

**Core Modules:**
- src/types.rs (Order, Fill, Quote types) - 300 tokens
- src/websocket.rs (WebSocket handler, 5 methods) - 800 tokens

**Related:**
- src/utils.rs (summary: logging, time utils) - 50 tokens
- src/config.rs (summary: env loading) - 40 tokens

**Skipped:**
- tests/ (24 files)
- benches/ (3 files)
- examples/ (5 files)

**Token Budget:** 12,450 / 50,000 (24% used)
```

---

## STEP 5: Analyze & Plan (with Model Routing)

**Goal:** Create execution plan with model routing assignments

### 5.1 Task Analysis

**Detect task characteristics:**
```
- Complexity: [low/medium/high]
- Category: [detected from context]
- Technologies: [rust, websockets, async, docker]
- Novelty: [routine/moderate/novel]
- Risk: [low/medium/high]
```

### 5.2 Create Execution Plan

**Generate task breakdown:**
```markdown
## Execution Plan

### Phase 1: Architecture (High Complexity → opus)
- Design WebSocket connection pool architecture
- Define error recovery strategy
- Plan graceful shutdown mechanism

### Phase 2: Implementation (Medium Complexity → sonnet)
- Implement connection pool struct
- Add WebSocket handler with bounded channels
- Implement health check endpoint
- Write error handling for disconnections

### Phase 3: Testing (Standard Complexity → sonnet)
- Write unit tests for connection pool
- Write integration tests for WebSocket flow
- Add stress test for 10K connections

### Phase 4: Refinement (Low Complexity → haiku)
- Add debug logging
- Format code with rustfmt
- Update configuration examples
```

### 5.3 Model Routing Assignments

**Decision Matrix:**
```
┌─────────────────────────────────────────────────────────────┐
│  TASK                             │  MODEL   │  COST  │ WHY │
├───────────────────────────────────┼──────────┼────────┼─────┤
│  Architecture design              │  opus    │  $$$$  │ Critical│
│  Error recovery strategy          │  opus    │  $$$$  │ Complex │
│  Connection pool implementation   │  sonnet  │  $$    │ Standard│
│  WebSocket handler                │  sonnet  │  $$    │ Standard│
│  Unit tests                       │  sonnet  │  $$    │ Coverage│
│  Integration tests                │  sonnet  │  $$    │ Complex │
│  Stress tests                     │  sonnet  │  $$    │ Non-trivial│
│  Debug logging                    │  haiku   │  $     │ Trivial │
│  Code formatting                  │  haiku   │  $     │ Automated│
│  Config examples                  │  haiku   │  $     │ Boilerplate│
└─────────────────────────────────────────────────────────────┘
```

### 5.4 Cost Estimation

```markdown
## Model Routing Summary
| Model  | Tasks | Estimated Tokens | Est. Cost |
|--------|-------|------------------|-----------|
| opus   | 2     | ~50K out + 10K in | $0.30    |
| sonnet | 5     | ~100K out + 25K in| $0.15    |
| haiku  | 3     | ~15K out + 5K in  | $0.003   |
| **Total** | **10** |              | **$0.45** |
```

---

## STEP 6: Write Plan to Blackboard

**Goal:** Share plan with all agents via Redis Blackboard

### 6.1 Initialize Blackboard for Pipeline

```bash
# Generate unique pipeline ID
PIPELINE_ID="rvgb-$(date +%s)-$(uuidgen | cut -d'-' -f1)"

# Initialize status tracking
redis-cli -u $REDIS_URL HSET status:$PIPELINE_ID \
    phase "planning" \
    progress "0" \
    active_agents "" \
    errors "0" \
    started_at "$(date -Iseconds)"
```

### 6.2 Write Plan Artifact

```python
# Store plan as artifact on Blackboard
plan_artifact = {
    "artifact_id": "plan_v1",
    "artifact_type": "PLAN",
    "content": {
        "phases": [
            {
                "phase_name": "Architecture",
                "tasks": [
                    {
                        "task_id": "task-1",
                        "description": "Design WebSocket connection pool",
                        "assigned_agent": "@rust-architect",
                        "model": "opus",
                        "status": "pending"
                    }
                ]
            },
            # ... more phases
        ]
    },
    "created_by": "orchestrator",
    "created_at": "2025-11-29T10:30:00Z",
    "version": 1,
    "dependencies": []
}

# Write to Redis
redis-cli -u $REDIS_URL HSET artifacts:$PIPELINE_ID:plan_v1 \
    data "$(echo $plan_artifact | jq -c .)"
```

### 6.3 Blackboard Operations

**Write Artifact:**
```bash
blackboard.write_artifact(
    pipeline_id="rvgb-1732880400-a1b2c3",
    artifact_id="plan_v1",
    artifact_type="PLAN",
    content=plan_data,
    created_by="orchestrator"
)
```

**Read Artifact:**
```bash
blackboard.read_artifact(
    pipeline_id="rvgb-1732880400-a1b2c3",
    artifact_id="plan_v1"
)
```

**Acquire Lock (before editing file):**
```bash
blackboard.acquire_lock(
    pipeline_id="rvgb-1732880400-a1b2c3",
    resource="src/engine.rs",
    agent_name="@rust-pro",
    ttl=300  # 5 minutes auto-release
)
```

**Release Lock (after editing):**
```bash
blackboard.release_lock(
    pipeline_id="rvgb-1732880400-a1b2c3",
    resource="src/engine.rs",
    agent_name="@rust-pro"
)
```

### 6.4 Agent Access Pattern

**All agents read plan from Blackboard:**
```
1. Agent spawns → reads plan from Blackboard
2. Agent finds assigned tasks
3. Agent acquires lock on files to modify
4. Agent writes code artifacts to Blackboard
5. Agent releases locks
6. Agent updates task status on Blackboard
```

---

## STEP 7: Create Shadow Workspace (Docker)

**Goal:** Isolated environment for safe verification without affecting main workspace

### 7.1 Launch Shadow Container

```bash
# Create shadow workspace container
SHADOW_ID=$(docker run -d \
    --name "shadow-$PIPELINE_ID" \
    -v "$PWD:/workspace:ro" \
    -w /workspace \
    rvgb-shadow-workspace:latest \
    tail -f /dev/null)

echo "Shadow workspace created: $SHADOW_ID"
```

### 7.2 Copy Project to Shadow

```bash
# Clone project into shadow (isolated copy)
docker exec $SHADOW_ID bash -c "
    git clone /workspace /shadow-workspace
    cd /shadow-workspace
    git config user.name 'RVGB Shadow'
    git config user.email 'shadow@rvgb.local'
"
```

### 7.3 Shadow Workspace Interface

**Python-style API (conceptual):**
```python
with ShadowWorkspace(project_path) as shadow:
    # Apply changes from Blackboard
    shadow.apply_patch(agent_diff)

    # Run verification gauntlet
    results = shadow.verify_all()

    if all(r.passed for r in results):
        # Verification passed → commit to main
        shadow.commit_to_main()
    else:
        # Verification failed → rollback
        shadow.rollback()
        # Feed errors back to agent for retry
```

### 7.4 Shadow Benefits

```
┌─────────────────────────────────────────────────────────────┐
│  ✅ Complete isolation from main workspace                  │
│  ✅ Safe to run destructive tests                           │
│  ✅ Parallel verification without conflicts                 │
│  ✅ Easy rollback (just delete container)                   │
│  ✅ Reproducible environment (Dockerized)                   │
│  ✅ Can snapshot shadow state at any point                  │
└─────────────────────────────────────────────────────────────┘
```

**SKIP Shadow if:**
- Docker not available (fallback to git worktree)
- User says "direct mode"
- Read-only task (no code changes)

---

## SMART PARALLELIZATION RULES

**Goal:** Maximize speed by running independent tasks in parallel, but stay sequential when there's file conflict risk.

### Parallelization Decision Matrix

```
┌─────────────────────────────────────────────────────────────┐
│  PARALLEL (spawn multiple Task calls in ONE message):       │
│  ├─ Tasks touch DIFFERENT files                             │
│  ├─ Tasks are in DIFFERENT directories                      │
│  ├─ Read-only analysis tasks                                │
│  ├─ Independent test suites                                 │
│  ├─ Multi-perspective reviews (5 reviewers at once)         │
│  └─ Research + planning (no file writes)                    │
│                                                             │
│  SEQUENTIAL (one Task at a time):                           │
│  ├─ Tasks touch the SAME file                               │
│  ├─ Task B depends on Task A's output                       │
│  ├─ Shared state modification (config, env)                 │
│  ├─ Database migrations (order matters)                     │
│  └─ Chained transformations (parse → transform → write)     │
└─────────────────────────────────────────────────────────────┘
```

### Auto-Detection Algorithm

**Before spawning agents, analyze task list:**

```python
def can_parallelize(tasks):
    """Determine which tasks can run in parallel."""

    # Extract file targets from each task
    task_files = {}
    for task in tasks:
        task_files[task.id] = extract_target_files(task.description)

    # Build conflict graph
    conflicts = []
    for i, task_a in enumerate(tasks):
        for task_b in tasks[i+1:]:
            files_a = task_files[task_a.id]
            files_b = task_files[task_b.id]

            # Check for file overlap
            if files_a & files_b:  # Set intersection
                conflicts.append((task_a.id, task_b.id))

    # Group into parallel batches
    if not conflicts:
        return [tasks]  # All can run in parallel

    # Topological sort by dependencies
    return topological_batches(tasks, conflicts)
```

### Parallelization Examples

**GOOD - Parallel (different files):**
```xml
<!-- These touch different files - spawn together -->
<invoke name="Task">
  <parameter name="prompt">Fix auth bug in src/auth.rs</parameter>
</invoke>
<invoke name="Task">
  <parameter name="prompt">Add logging to src/websocket.rs</parameter>
</invoke>
<invoke name="Task">
  <parameter name="prompt">Write tests for src/engine.rs</parameter>
</invoke>
```

**GOOD - Parallel (all read-only):**
```xml
<!-- Reviews don't modify files - spawn together -->
<invoke name="Task">
  <parameter name="prompt">@security-auditor: Review for vulnerabilities</parameter>
</invoke>
<invoke name="Task">
  <parameter name="prompt">@performance-reviewer: Review for bottlenecks</parameter>
</invoke>
<invoke name="Task">
  <parameter name="prompt">@architecture-reviewer: Review design</parameter>
</invoke>
```

**BAD - Must be Sequential (same file):**
```xml
<!-- These touch the same file - DO NOT parallelize -->
<!-- First: -->
<invoke name="Task">
  <parameter name="prompt">Add struct definition to src/types.rs</parameter>
</invoke>
<!-- Wait for completion, THEN: -->
<invoke name="Task">
  <parameter name="prompt">Add impl block to src/types.rs</parameter>
</invoke>
```

**BAD - Must be Sequential (dependency):**
```xml
<!-- Task B needs Task A's output -->
<!-- First: -->
<invoke name="Task">
  <parameter name="prompt">Create database schema in migrations/</parameter>
</invoke>
<!-- Wait for completion, THEN: -->
<invoke name="Task">
  <parameter name="prompt">Write model that uses the new schema</parameter>
</invoke>
```

### Maximum Parallel Agents

```
Recommended limits:
- Implementation tasks: 3-5 parallel (file lock contention)
- Review tasks: 5-7 parallel (read-only, no conflicts)
- Research/analysis: 10+ parallel (no file access)

Memory consideration:
- Each agent uses ~20-50K tokens context
- 5 parallel agents = ~250K tokens concurrent
- Monitor for rate limits
```

### Parallelization Trigger Words

**Auto-detect parallel-safe patterns in user request:**
```
Parallel triggers:
- "fix A and B" (different targets)
- "add X to file1, add Y to file2"
- "review the code" (read-only)
- "analyze/research/explore" (read-only)
- "run tests for module A and module B"
- "check A, B, C, D" (list of independent items)

Sequential triggers:
- "then" / "after that" / "once done"
- "update the same file"
- "depends on" / "needs the output of"
- "in order" / "step by step"
```

### CRITICAL: Research Tasks Are ALWAYS Parallelizable

**Web searches, API checks, version lookups = NO file writes = ALWAYS parallel**

```
Example: "check dYdX, Bybit, Bitget, Kucoin, Paradex SDKs"

WRONG (sequential):
- Search dYdX → wait → Search Bybit → wait → Search Bitget...
- Total: 15+ web searches, one at a time

RIGHT (parallel):
<invoke name="Task">
  <parameter name="prompt">Research dYdX v4-clients-rs: latest version, changelog, breaking changes</parameter>
</invoke>
<invoke name="Task">
  <parameter name="prompt">Research Bybit SDK: latest version, changelog, breaking changes</parameter>
</invoke>
<invoke name="Task">
  <parameter name="prompt">Research Bitget SDK: latest version, changelog, breaking changes</parameter>
</invoke>
<invoke name="Task">
  <parameter name="prompt">Research Kucoin SDK: latest version, changelog, breaking changes</parameter>
</invoke>
<invoke name="Task">
  <parameter name="prompt">Research Paradex SDK: latest version, changelog, breaking changes</parameter>
</invoke>
<!-- ALL 5 spawn in ONE message, run simultaneously -->
<!-- Then compile results -->
```

**Rule: If task involves checking/researching MULTIPLE independent items:**
1. Split into one agent per item
2. Spawn ALL agents in single message (parallel)
3. Wait for all to complete
4. Compile results into summary

**This applies to:**
- SDK version checks (like above)
- API documentation lookups
- Competitor analysis
- Multi-file code review
- Dependency audit
- Security vulnerability scans

---

## STEP 8: Delegate to Agents (read/write Blackboard)

**Goal:** Agents execute tasks, coordinate via Blackboard

### 8.0 LITE MODE DELEGATION (Preferred - No Redis/Docker)

**For most tasks, use simple direct delegation without infrastructure:**

```xml
<!-- SIMPLE: Single agent, direct prompt, no boilerplate -->
<invoke name="Task">
  <parameter name="subagent_type">rust-pro</parameter>
  <parameter name="model">haiku</parameter>
  <parameter name="prompt">Fix type error in src/engine.rs:145.
Error: expected Result&lt;Fill&gt;, got Fill.
Solution: wrap return with Ok().
Verify: cargo check</parameter>
</invoke>
```

```xml
<!-- MEDIUM: Multiple agents in PARALLEL (one message, multiple invokes) -->
<invoke name="Task">
  <parameter name="subagent_type">rust-pro</parameter>
  <parameter name="model">sonnet</parameter>
  <parameter name="prompt">Add WebSocket reconnection in src/ws.rs:
- Exponential backoff (100ms, 200ms, 400ms...)
- Max 5 retries
- Log each attempt</parameter>
</invoke>
<invoke name="Task">
  <parameter name="subagent_type">test-writer</parameter>
  <parameter name="model">haiku</parameter>
  <parameter name="prompt">Write tests for WebSocket reconnection in tests/ws_test.rs:
- Test successful reconnect
- Test max retries exceeded
- Test backoff timing</parameter>
</invoke>
<!-- Both agents spawn simultaneously in single message -->
```

**LITE mode rules:**
- NO Redis, NO Blackboard, NO Docker
- Direct prompts under 200 words
- Use file paths explicitly
- Spawn parallel agents in ONE message
- No coordination needed - each agent works independently

### 8.0.1 STRUCTURED OUTPUT FORMAT

**To prevent "trust" errors from freeform text responses, require agents to return structured JSON:**

**Required JSON Schema:**
```json
{
  "task_id": "string - unique identifier for the task",
  "status": "string - one of: completed, failed, partial",
  "code_changes": [
    {
      "file_path": "string - absolute path to modified file",
      "action": "string - one of: created, modified, deleted",
      "verification": "string - how change was verified"
    }
  ],
  "verification_result": {
    "passed": "boolean - true if all checks passed",
    "checks": {
      "syntax": "boolean",
      "linter": "boolean",
      "tests": "boolean"
    },
    "errors": "array - any errors encountered"
  },
  "summary": "string - brief description of what was accomplished"
}
```

**Example Agent Response:**
```json
{
  "task_id": "fix-websocket-reconnect",
  "status": "completed",
  "code_changes": [
    {
      "file_path": "/workspace/src/ws.rs",
      "action": "modified",
      "verification": "cargo check passed"
    }
  ],
  "verification_result": {
    "passed": true,
    "checks": {
      "syntax": true,
      "linter": true,
      "tests": true
    },
    "errors": []
  },
  "summary": "Added exponential backoff reconnection logic with max 5 retries"
}
```

**Why This Prevents Trust Errors:**
- Structured data is machine-parseable (no ambiguous natural language)
- Explicit status codes eliminate interpretation errors
- File paths are absolute and verifiable
- Verification results are boolean, not subjective
- Orchestrator can programmatically validate completeness

**Agent Prompt Template with Structured Output:**
```xml
<invoke name="Task">
  <parameter name="subagent_type">rust-pro</parameter>
  <parameter name="model">sonnet</parameter>
  <parameter name="prompt">Fix type error in src/engine.rs:145.

Error: expected Result&lt;Fill&gt;, got Fill
Solution: wrap return with Ok()
Verify: cargo check

IMPORTANT: Return your response as JSON matching this schema:
{
  "task_id": "fix-type-error-engine-145",
  "status": "completed|failed|partial",
  "code_changes": [{file_path, action, verification}],
  "verification_result": {passed, checks, errors},
  "summary": "brief description"
}

Do NOT include freeform text outside the JSON structure.</parameter>
</invoke>
```

### CONTEXT SLICING

**Goal:** Only inject relevant subset of memory into agents, not full history

**Memory optimization rules:**
- **For code tasks:** Only include relevant file contents + error messages
- **For research:** Only include search results + key findings
- **For review:** Only include changed files + test results
- **Maximum context per agent:** 20K tokens

**Selection strategy:**
Use grep/relevance matching to select context:
```bash
# Filter relevant files only
grep -l "authentication" memory/*.md | head -5

# Extract only error messages from logs
grep "ERROR\|FAIL" memory/execution.log

# Include only changed files for review
git diff --name-only HEAD~1 | xargs cat
```

**Example - Code task context slicing:**
```xml
<invoke name="Task">
  <parameter name="subagent_type">rust-pro</parameter>
  <parameter name="model">haiku</parameter>
  <parameter name="prompt">Fix authentication bug in src/auth.rs

Relevant context (sliced):
- File: src/auth.rs (lines 45-89 only)
- Error: "invalid token signature" from logs/error.log
- Related: src/jwt.rs (verify_token function only)

DO NOT include: Full repository map, unrelated modules, all logs</parameter>
</invoke>
```

**Benefits:**
- Faster agent execution (less token processing)
- Lower costs (fewer input tokens)
- Better focus (agents not distracted by irrelevant context)
- Scales to larger codebases

### 8.1 Agent Spawning with Context

**Agent receives:**
1. Plan from Blackboard (assigned tasks)
2. Past reflections (STEP 3)
3. Repository map (STEP 4)
4. Blackboard credentials (PIPELINE_ID, REDIS_URL)
5. Shadow workspace path

**Task Call Template:**
```xml
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="model">opus</parameter>
  <parameter name="prompt">You are @rust-architect, expert in Rust system design.

TASK: Design WebSocket connection pool architecture for high-throughput order matching.

CONTEXT:
- Pipeline ID: rvgb-1732880400-a1b2c3
- Redis Blackboard: $REDIS_URL
- Shadow Workspace: /shadow-workspace (in Docker container: shadow-rvgb-1732880400-a1b2c3)

PLAN (from Blackboard):
[Read plan from Blackboard: redis-cli HGET artifacts:$PIPELINE_ID:plan_v1 data]

PAST LEARNINGS (Reflexion):
[Injected reflections from STEP 3]

REPOSITORY MAP:
[Compressed repo map from STEP 4]

REQUIREMENTS:
- Design bounded channel architecture (reflection: avoid unbounded channels)
- Plan graceful shutdown for 10K+ connections
- Error recovery strategy for network partitions

COORDINATION:
1. Read plan: redis-cli HGET artifacts:$PIPELINE_ID:plan_v1 data
2. Write your design: blackboard.write_artifact("architecture_design", content, PLAN)
3. Update status: redis-cli HSET status:$PIPELINE_ID phase "architecture_complete"

OUTPUT:
Provide architecture design document. Store on Blackboard.
  </parameter>
</invoke>
```

### 8.2 Parallel Agent Execution

**Independent tasks → Parallel calls:**
```xml
<!-- Architecture + Tests can run in parallel -->
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="model">opus</parameter>
  <parameter name="prompt">@rust-architect: [architecture task]
  PIPELINE_ID: $PIPELINE_ID
  BLACKBOARD: $REDIS_URL</parameter>
</invoke>
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="model">sonnet</parameter>
  <parameter name="prompt">@test-writer: [test generation task]
  PIPELINE_ID: $PIPELINE_ID
  BLACKBOARD: $REDIS_URL</parameter>
</invoke>
```

### 8.3 Blackboard Coordination Example

**Agent 1 (Architect) writes:**
```bash
# Agent writes architecture design to Blackboard
redis-cli -u $REDIS_URL HSET artifacts:$PIPELINE_ID:architecture_v1 \
    data '{
        "artifact_type": "PLAN",
        "content": "Use bounded mpsc channels with capacity 1000...",
        "created_by": "@rust-architect"
    }'

# Update status
redis-cli -u $REDIS_URL HSET status:$PIPELINE_ID \
    phase "architecture_complete" \
    progress "25"
```

**Agent 2 (Implementer) reads:**
```bash
# Agent reads architecture design from Blackboard
ARCHITECTURE=$(redis-cli -u $REDIS_URL HGET artifacts:$PIPELINE_ID:architecture_v1 data)

# Acquire lock before editing src/engine.rs
redis-cli -u $REDIS_URL SET locks:$PIPELINE_ID:src/engine.rs "@rust-pro" EX 300

# Implement based on architecture
# ...

# Write code artifact to Blackboard
redis-cli -u $REDIS_URL HSET artifacts:$PIPELINE_ID:code:src/engine.rs \
    data '{
        "artifact_type": "CODE",
        "content": "pub struct ConnectionPool { ... }",
        "created_by": "@rust-pro"
    }'

# Release lock
redis-cli -u $REDIS_URL DEL locks:$PIPELINE_ID:src/engine.rs
```

### 8.4 Agent Activity Logging

**Purpose:** Track agent operations for debugging without exposing full conversation history

**Log Format:**
```
[timestamp] [agent_name] [action] [target] [status]
```

**Required Log Events:**
1. **Agent Lifecycle:**
   ```
   2025-12-01T10:30:45Z @rust-pro STARTED task_delegation success
   2025-12-01T10:32:15Z @rust-pro COMPLETED task_delegation success
   ```

2. **File Operations:**
   ```
   2025-12-01T10:31:00Z @rust-pro READ src/engine.rs success
   2025-12-01T10:31:30Z @rust-pro WRITE src/engine.rs success
   2025-12-01T10:31:35Z @rust-pro WRITE tests/engine_test.rs success
   ```

3. **Tool Calls:**
   ```
   2025-12-01T10:31:10Z @rust-pro TOOL_CALL cargo_check success
   2025-12-01T10:31:45Z @test-writer TOOL_CALL cargo_test success
   ```

4. **Errors:**
   ```
   2025-12-01T10:31:20Z @rust-pro ERROR type_check failed
   2025-12-01T10:31:25Z @rust-pro RETRY type_check started
   ```

5. **Blackboard Operations:**
   ```
   2025-12-01T10:31:50Z @rust-pro WRITE artifacts:architecture_v1 success
   2025-12-01T10:31:55Z @rust-pro LOCK src/engine.rs acquired
   2025-12-01T10:32:00Z @rust-pro UNLOCK src/engine.rs released
   ```

**Storage Location:**
```
~/.claude/orchestrator/logs/
├── orchestrator_YYYYMMDD.log          # Main orchestrator log
├── agent_@rust-pro_YYYYMMDD.log       # Per-agent logs
└── pipeline_PIPELINE_ID.log           # Per-pipeline logs
```

**Implementation:**
```bash
# Log to file
LOG_DIR="$HOME/.claude/orchestrator/logs"
mkdir -p "$LOG_DIR"

log_event() {
    local agent=$1 action=$2 target=$3 status=$4
    local timestamp=$(date -Iseconds)
    local log_entry="$timestamp $agent $action $target $status"

    # Write to agent-specific log
    echo "$log_entry" >> "$LOG_DIR/agent_${agent}_$(date +%Y%m%d).log"

    # Write to pipeline log if PIPELINE_ID exists
    if [ -n "$PIPELINE_ID" ]; then
        echo "$log_entry" >> "$LOG_DIR/pipeline_${PIPELINE_ID}.log"
    fi
}

# Usage examples
log_event "@rust-pro" "STARTED" "task_delegation" "success"
log_event "@rust-pro" "READ" "src/engine.rs" "success"
log_event "@rust-pro" "TOOL_CALL" "cargo_check" "success"
log_event "@rust-pro" "ERROR" "type_check" "failed"
log_event "@rust-pro" "COMPLETED" "task_delegation" "success"
```

**Benefits:**
- Debug agent behavior without full conversation logs
- Track performance bottlenecks (time between events)
- Identify error patterns across agents
- Audit file access and modifications
- Reconstruct pipeline execution flow

---

## STEP 9: Verification Gauntlet (in Shadow)

**Goal:** Comprehensive verification in isolated shadow workspace

### 9.1 Verification Stages

**5-stage gauntlet (all must pass):**
```
1. Syntax Check (AST parse)
2. Linter (ruff/eslint/clippy)
3. Type Check (mypy/tsc/cargo check)
4. Security Scan (bandit/CodeQL/cargo-audit)
5. Unit Tests (pytest/jest/cargo test)
```

### 9.2 Execute in Shadow Workspace

```bash
# Apply changes from Blackboard to shadow workspace
docker exec shadow-$PIPELINE_ID bash -c "
    cd /shadow-workspace

    # Retrieve code artifacts from Blackboard and apply
    # For each artifact in artifacts:$PIPELINE_ID:code:*
    # Apply changes to files
"

# Run verification gauntlet
docker exec shadow-$PIPELINE_ID bash -c "
    cd /shadow-workspace
    /usr/local/bin/verify
"
```

### 9.3 Verification Script (verify.sh in Docker)

```bash
#!/bin/bash
# Verification Gauntlet for Shadow Workspace

PROJECT_ROOT="/shadow-workspace"
cd $PROJECT_ROOT

echo "=== RVGB Verification Gauntlet ==="

# Detect project type
if [ -f "Cargo.toml" ]; then
    PROJECT_TYPE="rust"
elif [ -f "package.json" ]; then
    PROJECT_TYPE="node"
elif [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
    PROJECT_TYPE="python"
else
    PROJECT_TYPE="unknown"
fi

echo "Detected project type: $PROJECT_TYPE"

# Stage 1: Syntax Check
echo -e "\n[1/5] Syntax Check..."
case $PROJECT_TYPE in
    rust)
        cargo check --message-format=json 2>&1 | tee /tmp/syntax.log
        SYNTAX_RESULT=${PIPESTATUS[0]}
        ;;
    node)
        npx tsc --noEmit 2>&1 | tee /tmp/syntax.log
        SYNTAX_RESULT=${PIPESTATUS[0]}
        ;;
    python)
        python3 -m py_compile **/*.py 2>&1 | tee /tmp/syntax.log
        SYNTAX_RESULT=$?
        ;;
esac

if [ $SYNTAX_RESULT -ne 0 ]; then
    echo "❌ SYNTAX CHECK FAILED"
    exit 1
fi
echo "✅ Syntax check passed"

# Stage 2: Linter
echo -e "\n[2/5] Linter Check..."
case $PROJECT_TYPE in
    rust)
        cargo clippy --message-format=json 2>&1 | tee /tmp/lint.log
        LINT_RESULT=${PIPESTATUS[0]}
        ;;
    node)
        npx eslint . --format json > /tmp/lint.log 2>&1
        LINT_RESULT=$?
        ;;
    python)
        ruff check . --output-format=json > /tmp/lint.log 2>&1
        LINT_RESULT=$?
        ;;
esac

if [ $LINT_RESULT -ne 0 ]; then
    echo "⚠️  LINTER WARNINGS (non-blocking)"
fi
echo "✅ Linter check complete"

# Stage 3: Type Check
echo -e "\n[3/5] Type Check..."
case $PROJECT_TYPE in
    rust)
        # Covered by cargo check
        echo "✅ Type check covered by syntax check"
        ;;
    node)
        npx tsc --noEmit 2>&1 | tee /tmp/typecheck.log
        TYPE_RESULT=${PIPESTATUS[0]}
        ;;
    python)
        mypy . --json > /tmp/typecheck.log 2>&1
        TYPE_RESULT=$?
        ;;
esac

if [ ${TYPE_RESULT:-0} -ne 0 ]; then
    echo "❌ TYPE CHECK FAILED"
    exit 3
fi
echo "✅ Type check passed"

# Stage 4: Security Scan
echo -e "\n[4/5] Security Scan..."
case $PROJECT_TYPE in
    rust)
        cargo audit --json > /tmp/security.log 2>&1
        SEC_RESULT=$?
        ;;
    node)
        npm audit --json > /tmp/security.log 2>&1
        SEC_RESULT=$?
        ;;
    python)
        bandit -r . -f json -o /tmp/security.log 2>&1
        SEC_RESULT=$?
        ;;
esac

if [ $SEC_RESULT -ne 0 ]; then
    echo "⚠️  SECURITY WARNINGS (review required)"
fi
echo "✅ Security scan complete"

# Stage 5: Unit Tests
echo -e "\n[5/5] Unit Tests..."
case $PROJECT_TYPE in
    rust)
        cargo test --message-format=json 2>&1 | tee /tmp/tests.log
        TEST_RESULT=${PIPESTATUS[0]}
        ;;
    node)
        npm test -- --json --outputFile=/tmp/tests.log 2>&1
        TEST_RESULT=$?
        ;;
    python)
        pytest --json-report --json-report-file=/tmp/tests.log 2>&1
        TEST_RESULT=$?
        ;;
esac

if [ $TEST_RESULT -ne 0 ]; then
    echo "❌ TESTS FAILED"
    exit 5
fi
echo "✅ All tests passed"

echo -e "\n=== ✅ VERIFICATION GAUNTLET PASSED ==="
exit 0
```

### 9.4 Parse Verification Results

```bash
# Extract results from shadow container
docker cp shadow-$PIPELINE_ID:/tmp/syntax.log /tmp/shadow-results/
docker cp shadow-$PIPELINE_ID:/tmp/lint.log /tmp/shadow-results/
docker cp shadow-$PIPELINE_ID:/tmp/typecheck.log /tmp/shadow-results/
docker cp shadow-$PIPELINE_ID:/tmp/security.log /tmp/shadow-results/
docker cp shadow-$PIPELINE_ID:/tmp/tests.log /tmp/shadow-results/

# Check exit code
VERIFICATION_EXIT_CODE=$?
```

### 9.5 Verification Report

```markdown
## Verification Gauntlet Results

| Stage | Status | Details |
|-------|--------|---------|
| 1. Syntax Check | ✅ PASS | No syntax errors |
| 2. Linter | ⚠️ WARN | 3 warnings (non-blocking) |
| 3. Type Check | ✅ PASS | All types valid |
| 4. Security Scan | ✅ PASS | No vulnerabilities |
| 5. Unit Tests | ✅ PASS | 47/47 tests passed |

**Overall:** ✅ PASSED (all critical stages passed)

**Warnings (non-blocking):**
- Linter: Unused import in src/utils.rs:15
- Linter: Consider using if-let instead of match in src/engine.rs:230
- Linter: Function complexity high in src/engine.rs:process_order

**Exit Code:** 0
```

**If verification fails:**
```markdown
## Verification Gauntlet Results

| Stage | Status | Details |
|-------|--------|---------|
| 1. Syntax Check | ✅ PASS | No syntax errors |
| 2. Linter | ✅ PASS | No issues |
| 3. Type Check | ❌ FAIL | Type mismatch in src/engine.rs:145 |
| 4. Security Scan | ⏭️ SKIP | Skipped due to type check failure |
| 5. Unit Tests | ⏭️ SKIP | Skipped due to type check failure |

**Overall:** ❌ FAILED (type check failed)

**Errors:**
```
error[E0308]: mismatched types
  --> src/engine.rs:145:20
   |
145 |         let result = process_async(order).await;
   |                      ^^^^^^^^^^^^^^^^^^^^^^^^ expected `Result<Fill>`, found `Fill`
```

**Next Step:** Feed error to agent for retry (TDD Loop - STEP 10)
```

---

## STEP 10: TDD Loop (3-strike max)

**Goal:** Iterative fix loop with maximum 3 attempts

### 10.1 Strike System

```
┌─────────────────────────────────────────────────────────────┐
│  STRIKE 1: Initial Verification                             │
│  ├─ Run verification gauntlet (STEP 9)                      │
│  ├─ If PASS → Continue to STEP 11                           │
│  └─ If FAIL → Extract errors, proceed to Strike 2           │
│                                                             │
│  STRIKE 2: Agent Fix Attempt                                │
│  ├─ Feed errors to original agent                           │
│  ├─ Agent fixes in shadow workspace (via Blackboard)        │
│  ├─ Re-run verification gauntlet                            │
│  ├─ If PASS → Continue to STEP 11                           │
│  └─ If FAIL → Proceed to Strike 3                           │
│                                                             │
│  STRIKE 3: Expert Escalation                                │
│  ├─ Spawn @code-reviewer to analyze root cause              │
│  ├─ Reviewer provides fix recommendations                   │
│  ├─ Original agent applies fix                              │
│  ├─ Re-run verification gauntlet                            │
│  ├─ If PASS → Continue to STEP 11                           │
│  └─ If FAIL → HALT, rollback shadow, report to user         │
└─────────────────────────────────────────────────────────────┘
```

### 10.2 Strike 2: Agent Fix

**Extract error context:**
```bash
# Parse verification logs for specific errors
SYNTAX_ERRORS=$(jq -r '.errors[]' /tmp/shadow-results/syntax.log)
TYPE_ERRORS=$(jq -r '.errors[]' /tmp/shadow-results/typecheck.log)
TEST_FAILURES=$(jq -r '.failures[]' /tmp/shadow-results/tests.log)
```

**Feed errors to agent:**
```xml
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="model">sonnet</parameter>
  <parameter name="prompt">You are @rust-pro. Fix the failing verification in shadow workspace.

PIPELINE_ID: $PIPELINE_ID
BLACKBOARD: $REDIS_URL
SHADOW WORKSPACE: shadow-$PIPELINE_ID (Docker container)

VERIFICATION FAILURES:
```
[Type Check Errors]
error[E0308]: mismatched types
  --> src/engine.rs:145:20
   |
145 |         let result = process_async(order).await;
   |                      ^^^^^^^^^^^^^^^^^^^^^^^^ expected `Result<Fill>`, found `Fill`
```

EXPECTED: process_async should return Result<Fill>
ACTUAL: process_async returns Fill directly

ROOT CAUSE: Missing error handling wrapper

FIX REQUIRED:
1. Read current code from Blackboard: artifacts:$PIPELINE_ID:code:src/engine.rs
2. Wrap process_async call with Ok() or add ? operator
3. Update code artifact on Blackboard
4. Orchestrator will re-run verification

Fix this specific error. Do not refactor unrelated code.
  </parameter>
</invoke>
```

### 10.3 Strike 3: Expert Escalation

**If Strike 2 fails, get expert analysis:**
```xml
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="model">opus</parameter>
  <parameter name="prompt">You are @code-reviewer, expert debugging specialist.

CONTEXT: Agent has failed to fix verification error after 2 attempts.

ORIGINAL ERROR (Strike 1):
```
error[E0308]: mismatched types in src/engine.rs:145
```

ATTEMPTED FIX (Strike 2):
[What agent tried]

PERSISTING ERROR (Strike 2 verification):
```
error[E0308]: still mismatched types in src/engine.rs:145
[possibly different details]
```

CODE CONTEXT:
[Read from Blackboard: artifacts:$PIPELINE_ID:code:src/engine.rs]

ANALYSIS REQUIRED:
1. Why did the first fix fail?
2. What is the actual root cause (not symptoms)?
3. What is the correct fix?

Provide detailed root cause analysis and specific fix instructions.
  </parameter>
</invoke>
```

**Apply expert fix:**
```xml
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="model">sonnet</parameter>
  <parameter name="prompt">You are @rust-pro. Apply the expert reviewer's fix.

EXPERT ANALYSIS:
[Reviewer's root cause analysis]

RECOMMENDED FIX:
[Specific instructions from reviewer]

TASK:
1. Read code from Blackboard
2. Apply the exact fix recommended
3. Update Blackboard artifact
4. Do NOT make additional changes

This is Strike 3 (final attempt). Must succeed.
  </parameter>
</invoke>
```

### 10.4 TDD Loop Exhausted

**If Strike 3 fails:**
```markdown
## ⚠️ TDD LOOP EXHAUSTED (3/3 strikes)

**Strike 1 (Initial):**
- Error: Type mismatch in src/engine.rs:145
- Details: Expected `Result<Fill>`, found `Fill`

**Strike 2 (Agent Fix):**
- Attempted: Wrapped with Ok()
- Result: Still failed - different type error
- New error: Expected `Result<Fill, Error>`, found `Result<Fill, ()>`

**Strike 3 (Expert Escalation):**
- Expert analysis: Missing error type in function signature
- Attempted: Changed return type to Result<Fill, Error>
- Result: Still failed - Error type not in scope
- Final error: Cannot find type `Error` in this scope

**RECOMMENDATION:**
This appears to be a deeper architectural issue requiring manual intervention:
1. Error type needs to be defined/imported
2. May need to refactor error handling strategy
3. Consider using thiserror or anyhow crate

**SHADOW WORKSPACE STATUS:**
- Container: shadow-$PIPELINE_ID (kept for debugging)
- Branch: rollback-$PIPELINE_ID (preserved)
- Main workspace: UNCHANGED (protected)

**NEXT STEPS:**
- Manual debugging recommended
- Review error handling architecture
- Consider adding thiserror dependency
```

**Store failure in procedural_memory for learning:**
```sql
INSERT INTO procedural_memory (reflection_text, failure_context, relevance_tags)
VALUES (
    'When encountering persistent type errors in Rust async code, check that error types are properly defined and in scope. Using error handling crates like thiserror or anyhow can prevent this.',
    '{"what_failed": "Type error in async function after 3 fix attempts",
      "root_cause": "Error type not defined/imported in scope",
      "fix_applied": "Would require defining custom Error type or using error crate",
      "lesson": "Define error types early in Rust projects"}',
    ARRAY['rust', 'async', 'error-handling', 'types']
);
```

---

## STEP 11: Multi-Perspective Review

**Goal:** Multiple specialists review the working code in parallel

**Only if verification passed in STEP 9 or 10.**

### 11.1 Parallel Review Agents

**Spawn 5 reviewers simultaneously:**
```xml
<!-- Security Review -->
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="model">sonnet</parameter>
  <parameter name="prompt">You are @security-auditor, expert in security vulnerabilities.

TASK: Review code for security issues.

CODE LOCATION:
- Read from Blackboard: artifacts:$PIPELINE_ID:code:*
- Or inspect shadow workspace: shadow-$PIPELINE_ID:/shadow-workspace

FOCUS AREAS:
- Input validation
- SQL injection / command injection
- Authentication/authorization
- Sensitive data exposure
- Cryptographic issues
- Dependencies with known CVEs

OUTPUT:
Rate each area: 🔴 Critical / 🟡 Warning / 🟢 Good
Provide specific findings with line numbers.
  </parameter>
</invoke>

<!-- Architecture Review -->
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="model">sonnet</parameter>
  <parameter name="prompt">You are @architecture-reviewer, expert in system design.

TASK: Review code for architectural quality.

FOCUS AREAS:
- Modularity and separation of concerns
- Coupling and cohesion
- Scalability considerations
- Error handling strategy
- Async/concurrency patterns

OUTPUT:
Rate: 🔴 Poor / 🟡 Acceptable / 🟢 Excellent
Suggest improvements.
  </parameter>
</invoke>

<!-- Performance Review -->
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="model">sonnet</parameter>
  <parameter name="prompt">You are @performance-reviewer, expert in optimization.

TASK: Review code for performance bottlenecks.

FOCUS AREAS:
- Algorithmic complexity
- Memory allocations
- Unnecessary cloning/copying
- Lock contention
- Database query efficiency

OUTPUT:
Rate: 🔴 Bottleneck / 🟡 Suboptimal / 🟢 Optimized
Identify hot paths.
  </parameter>
</invoke>

<!-- Simplicity Review -->
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="model">haiku</parameter>
  <parameter name="prompt">You are @simplicity-reviewer, expert in clean code.

TASK: Review code for over-engineering and complexity.

FOCUS AREAS:
- YAGNI violations (over-engineering)
- Code readability
- Naming clarity
- Documentation adequacy
- Dead code or unnecessary abstractions

OUTPUT:
Rate: 🔴 Over-engineered / 🟡 Complex / 🟢 Simple
Suggest simplifications.
  </parameter>
</invoke>

<!-- Code Quality Review -->
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="model">sonnet</parameter>
  <parameter name="prompt">You are @code-reviewer, expert in code quality.

TASK: General code review for quality and best practices.

FOCUS AREAS:
- Idiomatic code for the language
- Error handling completeness
- Test coverage adequacy
- Edge case handling
- Code duplication

OUTPUT:
Rate: 🔴 Needs work / 🟡 Acceptable / 🟢 High quality
List specific improvements.
  </parameter>
</invoke>
```

### 11.2 Aggregate Review Results

**Collect reviews from Blackboard:**
```bash
# Reviewers write to Blackboard
# artifacts:$PIPELINE_ID:review:security
# artifacts:$PIPELINE_ID:review:architecture
# artifacts:$PIPELINE_ID:review:performance
# artifacts:$PIPELINE_ID:review:simplicity
# artifacts:$PIPELINE_ID:review:quality

# Read all reviews
for review_type in security architecture performance simplicity quality; do
    redis-cli -u $REDIS_URL HGET artifacts:$PIPELINE_ID:review:$review_type data
done
```

### 11.3 Review Summary

```markdown
## Multi-Perspective Review Summary

| Reviewer | Rating | Critical Issues | Warnings | Notes |
|----------|--------|-----------------|----------|-------|
| Security | 🟢 Good | 0 | 1 | Consider rate limiting on WebSocket endpoint |
| Architecture | 🟢 Excellent | 0 | 0 | Clean separation, good error handling |
| Performance | 🟡 Acceptable | 0 | 2 | Clone in hot path (line 145), consider Arc |
| Simplicity | 🟢 Simple | 0 | 1 | Could extract helper function for validation |
| Code Quality | 🟢 High Quality | 0 | 0 | Idiomatic Rust, good test coverage |

**Overall Assessment:** ✅ APPROVED (no critical issues)

**Detailed Findings:**

### Security (🟢 Good)
- ✅ Input validation present
- ✅ No SQL injection risks (using ORM)
- ✅ Authentication enforced
- ⚠️  **Warning:** WebSocket endpoint lacks rate limiting (non-blocking)
  - Location: src/websocket.rs:89
  - Recommendation: Add per-client message rate limit

### Architecture (🟢 Excellent)
- ✅ Clean separation of concerns
- ✅ Error handling via Result types
- ✅ Bounded channels prevent memory leaks
- ✅ Graceful shutdown implemented

### Performance (🟡 Acceptable)
- ⚠️  **Warning:** Unnecessary clone in hot path
  - Location: src/engine.rs:145
  - Issue: `order.clone()` on every iteration
  - Recommendation: Use Arc<Order> or borrow
- ⚠️  **Warning:** Lock held across await point
  - Location: src/engine.rs:230
  - Recommendation: Minimize lock scope

### Simplicity (🟢 Simple)
- ✅ Readable, idiomatic code
- ✅ No over-engineering
- ⚠️  **Suggestion:** Extract validation logic to helper
  - Location: src/websocket.rs:120-140 (20 lines of validation)
  - Recommendation: Create `validate_order()` function

### Code Quality (🟢 High Quality)
- ✅ Follows Rust best practices
- ✅ Comprehensive error handling
- ✅ Good test coverage (47 tests)
- ✅ No code duplication
```

### 11.4 Critical Issues → Block Merge

**If any reviewer finds 🔴 Critical issues:**
```markdown
## ⚠️ REVIEW BLOCKED - CRITICAL ISSUES FOUND

**Security Review: 🔴 Critical**
- **CRITICAL:** SQL Injection vulnerability in query builder
  - Location: src/db.rs:56
  - Issue: User input concatenated directly into SQL query
  - Fix Required: Use parameterized queries
  - **BLOCKING:** Cannot merge until fixed

**Next Steps:**
1. Spawn agent to fix critical security issue
2. Re-run verification gauntlet
3. Re-run security review
4. Proceed only if all critical issues resolved
```

---

## STEP 12: Reflexion - Generate & Store

**Goal:** Generate reflection on the process and store learnings

### 12.1 Self-Critique Checklist

**Evaluate the completed work:**
```
┌─────────────────────────────────────────────────────────────┐
│  REFLEXION SELF-CRITIQUE                                    │
│  ├─ Does solution actually solve the stated problem? ✅/❌  │
│  ├─ Are there obvious bugs or edge cases missed? ✅/❌      │
│  ├─ Is it over-engineered for the task? ✅/❌               │
│  ├─ Did reviewers flag critical issues? ✅/❌               │
│  ├─ Would I be confident deploying this? ✅/❌              │
│  └─ What could have been done better? [free text]          │
└─────────────────────────────────────────────────────────────┘
```

### 12.2 Generate Reflection (if issues found)

**If any failures occurred during pipeline:**
```xml
<invoke name="Task">
  <parameter name="subagent_type">general-purpose</parameter>
  <parameter name="model">sonnet</parameter>
  <parameter name="prompt">You are @reflection-generator, expert in learning from experience.

TASK: Generate reflection on the orchestration process.

PIPELINE CONTEXT:
- Task: Implement WebSocket connection pool
- Outcome: Success (after 2 TDD strikes)
- Failures encountered: Type error in Strike 1, Error type scope in Strike 2

FAILURE DETAILS:
**Strike 1:** Type mismatch - expected Result<Fill>, found Fill
- Root cause: Missing error handling wrapper
- Fix: Added ? operator

**Strike 2:** Error type not in scope
- Root cause: Custom Error type not imported
- Fix: Added `use crate::errors::Error;`

GENERATE REFLECTION:
1. What was the core issue?
2. Why did it happen?
3. How was it resolved?
4. What lesson should be learned?
5. What tags are relevant? (for future retrieval)

OUTPUT FORMAT:
```json
{
  "reflection_text": "One-sentence key learning",
  "failure_context": {
    "what_failed": "...",
    "root_cause": "...",
    "fix_applied": "...",
    "lesson": "..."
  },
  "relevance_tags": ["tag1", "tag2", ...]
}
```
  </parameter>
</invoke>
```

### 12.3 Store Reflection in Procedural Memory

**Insert reflection into PostgreSQL:**
```sql
INSERT INTO procedural_memory (
    reflection_text,
    failure_context,
    relevance_tags,
    created_at
)
VALUES (
    'When implementing async Rust functions that can error, always define and import error types before using Result<T, E>',
    '{
        "what_failed": "Type errors in async function after initial implementation",
        "root_cause": "Error type not defined/imported in function signature scope",
        "fix_applied": "Added custom Error type definition and imported in module",
        "lesson": "Define error types early in module hierarchy, before implementing functions that use them"
    }'::jsonb,
    ARRAY['rust', 'async', 'error-handling', 'types', 'result'],
    NOW()
);
```

**Using MCP (if available):**
```
mcp__memory__store_reflection(
    reflection="When implementing async Rust functions that can error, always define and import error types before using Result<T, E>",
    failure_context={
        "what_failed": "Type errors in async function",
        "root_cause": "Error type not in scope",
        "fix_applied": "Defined and imported Error type",
        "lesson": "Define error types early"
    },
    tags=["rust", "async", "error-handling", "types"]
)
```

### 12.4 Link Reflection to Knowledge Graph

**Update knowledge graph with reflection:**
```sql
-- Create entity for the reflection
INSERT INTO entities (entity_type, entity_name, metadata)
VALUES (
    'reflection',
    'rust-async-error-types',
    '{"topic": "error handling", "language": "rust"}'::jsonb
)
ON CONFLICT (entity_type, entity_name) DO UPDATE
SET last_modified = NOW();

-- Link reflection to related entities
-- (e.g., link to src/engine.rs file entity)
INSERT INTO relations (source_entity_id, relation_type, target_entity_id)
SELECT
    (SELECT id FROM entities WHERE entity_type='reflection' AND entity_name='rust-async-error-types'),
    'applies_to',
    (SELECT id FROM entities WHERE entity_type='file' AND entity_name='src/engine.rs')
ON CONFLICT DO NOTHING;
```

### 12.5 Reflexion Summary

```markdown
## Reflexion Generated

**Reflection:** When implementing async Rust functions that can error, always define and import error types before using Result<T, E>

**Context:**
- What failed: Type errors in async function implementation
- Root cause: Error type not defined/imported in scope
- Fix applied: Defined custom Error type and imported in module
- Lesson: Define error types early in module hierarchy

**Stored:**
- ✅ Procedural memory (PostgreSQL)
- ✅ Knowledge graph link (reflection → src/engine.rs)
- ✅ Tags: rust, async, error-handling, types, result

**Future Impact:**
Next time a similar task is detected (async Rust + error handling), this reflection will be retrieved and injected into agent context (STEP 3).
```

**If no significant issues:**
```markdown
## Reflexion Summary

No significant failures encountered during pipeline.
Routine success - no new reflection generated.

**Process Quality:**
- ✅ First-time verification pass
- ✅ All reviews green
- ✅ No critical issues
```

---

## STEP 13: Commit Shadow or Rollback

**Goal:** Finalize changes by committing shadow workspace to main, or rollback on failure

### 13.1 Decision Logic

```
┌─────────────────────────────────────────────────────────────┐
│  COMMIT CONDITIONS (all must be true):                      │
│  ├─ ✅ Verification gauntlet passed                         │
│  ├─ ✅ TDD loop succeeded (within 3 strikes)                │
│  ├─ ✅ No 🔴 critical review findings                       │
│  └─ ✅ Reflexion check passed                               │
│                                                             │
│  IF all true → COMMIT shadow to main                        │
│  IF any false → ROLLBACK (discard shadow)                   │
└─────────────────────────────────────────────────────────────┘
```

### 13.2 Commit Shadow to Main

**Extract changes from shadow container:**
```bash
# Get diff from shadow workspace
docker exec shadow-$PIPELINE_ID bash -c "
    cd /shadow-workspace
    git diff HEAD
" > /tmp/shadow-changes.patch

# Apply diff to main workspace
cd $PROJECT_ROOT
git apply /tmp/shadow-changes.patch

# Verify changes applied correctly
git status
git diff

# Commit changes
git add -A
git commit -m "$(cat <<'EOF'
Implement WebSocket connection pool with bounded channels

- Added ConnectionPool struct with configurable capacity
- Implemented graceful shutdown for 10K+ connections
- Added error recovery for network partitions
- Comprehensive test coverage (47 tests)

Verification:
- ✅ All tests passing
- ✅ Security review: No critical issues
- ✅ Performance review: Acceptable (2 minor optimizations suggested)

RVGB Pipeline: $PIPELINE_ID

🤖 Generated with RVGB v3.0
Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### 13.3 Cleanup Shadow Container

```bash
# Stop and remove shadow container
docker stop shadow-$PIPELINE_ID
docker rm shadow-$PIPELINE_ID

# Clean up shadow files
rm -rf /tmp/shadow-results/
rm -f /tmp/shadow-changes.patch

echo "✅ Shadow workspace committed and cleaned up"
```

### 13.4 Rollback Shadow

**If any critical failures:**
```bash
# Discard shadow container (all changes lost)
docker stop shadow-$PIPELINE_ID
docker rm -f shadow-$PIPELINE_ID

# Clean up
rm -rf /tmp/shadow-results/

echo "⚠️  Shadow workspace rolled back. Main workspace unchanged."
```

### 13.5 Commit/Rollback Report

**Success (Commit):**
```markdown
## Shadow Workspace Status: ✅ COMMITTED

**Changes applied to main workspace:**
- Modified: src/engine.rs (+120 lines)
- Modified: src/websocket.rs (+85 lines)
- Added: src/connection_pool.rs (new file, 200 lines)
- Modified: tests/engine_test.rs (+30 lines)

**Verification before commit:**
- ✅ All tests passing (47/47)
- ✅ No syntax errors
- ✅ No type errors
- ✅ Security scan clean
- ✅ All reviews approved

**Commit hash:** a1b2c3d4

**Shadow container:** Cleaned up
```

**Failure (Rollback):**
```markdown
## Shadow Workspace Status: ⚠️  ROLLED BACK

**Reason:** TDD loop exhausted (3 strikes) - persistent type errors

**Main workspace:** UNCHANGED (protected)

**Shadow preserved for debugging:**
- Container ID: shadow-$PIPELINE_ID (stopped)
- To inspect: `docker start shadow-$PIPELINE_ID && docker exec -it shadow-$PIPELINE_ID bash`
- To discard: `docker rm -f shadow-$PIPELINE_ID`

**Recommendation:**
Manual intervention required. Review error handling architecture.
```

---

## STEP 14: Memory Consolidation ("Sleep")

**Goal:** Consolidate episodic memories into semantic knowledge, update knowledge graph

### 14.1 Trigger Consolidation

**Run consolidation process (simulates "sleep cycle"):**
```sql
-- Call consolidation function with pipeline ID
SELECT consolidate_pipeline_memory('$PIPELINE_ID');
```

**Using MCP (if available):**
```
mcp__memory__consolidate_memory(pipeline_run_id='$PIPELINE_ID')
```

### 14.2 Consolidation Process

**What happens during consolidation:**

**14.2.1 Extract Entities from Episodes**
```sql
-- Find all code artifacts created during pipeline
SELECT
    event_type,
    agent_name,
    context->>'file_path' AS file_path,
    context->>'function_name' AS function_name
FROM episodic_memory
WHERE
    pipeline_run_id = '$PIPELINE_ID'
    AND event_type IN ('code_created', 'code_modified');

-- Insert entities into knowledge graph
INSERT INTO entities (entity_type, entity_name, metadata)
VALUES
    ('file', 'src/connection_pool.rs', '{"created_by": "@rust-pro"}'::jsonb),
    ('function', 'ConnectionPool::new', '{"file": "src/connection_pool.rs"}'::jsonb),
    ('function', 'ConnectionPool::acquire', '{"file": "src/connection_pool.rs"}'::jsonb)
ON CONFLICT (entity_type, entity_name) DO UPDATE
SET last_modified = NOW();
```

**14.2.2 Extract Relations**
```sql
-- Identify relations from code analysis
-- (e.g., src/websocket.rs uses ConnectionPool)
INSERT INTO relations (source_entity_id, relation_type, target_entity_id, weight)
SELECT
    (SELECT id FROM entities WHERE entity_type='file' AND entity_name='src/websocket.rs'),
    'uses',
    (SELECT id FROM entities WHERE entity_type='file' AND entity_name='src/connection_pool.rs'),
    1.0
ON CONFLICT (source_entity_id, relation_type, target_entity_id) DO UPDATE
SET
    weight = relations.weight + 0.1,
    last_seen = NOW();
```

**14.2.3 Update Semantic Patterns**
```sql
-- Check if this pipeline used any existing patterns
-- Update usage stats
UPDATE semantic_memory
SET
    times_used = times_used + 1,
    last_used = NOW()
WHERE
    category = 'rust-async-websockets'
    AND pattern_name ILIKE '%connection-pool%';

-- If new pattern detected, insert
INSERT INTO semantic_memory (
    pattern_name,
    category,
    description,
    key_elements,
    success_rate,
    times_used
)
VALUES (
    'bounded-channel-connection-pool',
    'rust-async-websockets',
    'Connection pool using bounded channels to prevent memory exhaustion',
    '{"channels": "bounded", "capacity": 1000, "graceful_shutdown": true}'::jsonb,
    1.0,
    1
)
ON CONFLICT (pattern_name) DO UPDATE
SET times_used = semantic_memory.times_used + 1;
```

**14.2.4 Archive Old Episodes**
```sql
-- Archive episodes older than 30 days to cold storage
-- (Keep in DB but mark as archived, or move to separate table)
UPDATE episodic_memory
SET metadata = jsonb_set(
    COALESCE(metadata, '{}'::jsonb),
    '{archived}',
    'true'
)
WHERE
    timestamp < NOW() - INTERVAL '30 days'
    AND importance < 0.5;
```

**14.2.5 Prune Low-Utility Patterns**
```sql
-- Every 10 pipeline runs, prune patterns with utility_score < 0.3
-- (Only run if total_orchestrations % 10 == 0)

-- Archive low-utility patterns
DELETE FROM semantic_memory
WHERE
    utility_score < 0.3
    AND times_used < 2
    AND last_used < NOW() - INTERVAL '60 days';
```

### 14.3 Knowledge Graph Update

**Updated graph structure:**
```
Entities:
- file:src/connection_pool.rs (NEW)
- file:src/websocket.rs (UPDATED)
- file:src/engine.rs (UPDATED)
- function:ConnectionPool::new (NEW)
- function:ConnectionPool::acquire (NEW)
- reflection:rust-async-error-types (NEW)

Relations:
- src/websocket.rs --uses--> src/connection_pool.rs (NEW)
- src/engine.rs --uses--> src/connection_pool.rs (NEW)
- reflection:rust-async-error-types --applies_to--> src/engine.rs (NEW)
- ConnectionPool::new --called_by--> src/websocket.rs (NEW)
```

### 14.4 Consolidation Summary

```markdown
## Memory Consolidation Complete

**Episodic Memory:**
- New episodes: 23 (from this pipeline)
- Total episodes: 1,270
- Archived episodes: 145 (>30 days old, low importance)

**Semantic Memory:**
- Patterns updated: 2
  - rust-async-websockets (times_used: 12 → 13)
  - error-handling-async (times_used: 15 → 16)
- New patterns: 1
  - bounded-channel-connection-pool (utility: 0.7)
- Patterns pruned: 0 (next prune at 10-run interval)

**Knowledge Graph:**
- New entities: 5 (3 functions, 1 file, 1 reflection)
- New relations: 4
- Updated relations: 2 (weight increased)
- Total entities: 487
- Total relations: 1,203

**Procedural Memory (Reflections):**
- New reflections: 1 (rust async error handling)
- Total reflections: 34

**Next Consolidation:** After 9 more pipeline runs (every 10 runs: prune low-utility patterns)
```

---

## STEP 15: Report to User

**Goal:** Comprehensive final report on RVGB orchestration

### 15.1 Full Report Template

```markdown
# RVGB Orchestration Complete v3.0

## Task
**Requested:** Implement WebSocket connection pool with bounded channels for high-throughput order matching

**Duration:** 8 minutes 32 seconds
**Pipeline ID:** rvgb-1732880400-a1b2c3

---

## Infrastructure Status

| Component | Status | Details |
|-----------|--------|---------|
| PostgreSQL | ✅ Connected | 5 tables, 1,270 episodes |
| Redis Blackboard | ✅ Connected | 47 artifacts written |
| Docker Shadow | ✅ Running | Container: shadow-rvgb-1732880400-a1b2c3 |
| MCP Memory Server | ⚠️ Not installed | Fallback: Direct PostgreSQL queries |

---

## Memory Retrieval Stats

**Episodic Memory:**
- Retrieved: 7 episodes (avg relevance score: 0.82)
- Most relevant: "WebSocket connection pooling fix" (score: 0.94)

**Semantic Memory:**
- Patterns loaded: 4 (avg utility: 0.81)
  - rust-async-websockets (utility: 0.91, used: 12→13x)
  - order-matching-algorithms (utility: 0.87)
  - error-handling-async (utility: 0.76, used: 15→16x)
  - docker-compose-setup (utility: 0.68)

**Reflections:**
- Retrieved: 3 past reflections
- Applied: "Always bound async channels" (applied 2→3x)

---

## Context Compression

**Repository Map:**
- Files scanned: 47
- Files loaded: 12 (compressed to signatures)
- Files summarized: 8
- Files skipped: 27 (tests, configs)
- **Token budget:** 12,450 / 50,000 (24% used)

---

## Blackboard Operations

**Pipeline ID:** rvgb-1732880400-a1b2c3

| Operation | Count |
|-----------|-------|
| Artifacts written | 47 |
| Artifacts read | 89 |
| Locks acquired | 12 |
| Locks released | 12 |
| Status updates | 18 |
| Agent logs | 156 |

**Top Artifacts:**
- plan_v1 (PLAN) - read 15x
- architecture_v1 (PLAN) - read 8x
- code:src/connection_pool.rs (CODE) - updated 3x
- code:src/websocket.rs (CODE) - updated 2x

---

## Implementation

**Model Routing:**

| Agent | Task | Model | Status | Duration |
|-------|------|-------|--------|----------|
| @rust-architect | Design connection pool architecture | opus | ✅ | 2m 15s |
| @rust-pro | Implement ConnectionPool struct | sonnet | ✅ | 3m 40s |
| @rust-pro | Implement WebSocket handler | sonnet | ✅ | 2m 50s |
| @test-writer | Write unit tests | sonnet | ✅ | 1m 30s |
| @test-writer | Write integration tests | sonnet | ✅ | 2m 10s |
| @rust-pro | Add debug logging | haiku | ✅ | 0m 25s |
| @rust-pro | Format code | haiku | ✅ | 0m 10s |
| @rust-pro | Update config examples | haiku | ✅ | 0m 18s |

**Model Cost Breakdown:**

| Model | Tasks | Tokens In | Tokens Out | Est. Cost |
|-------|-------|-----------|------------|-----------|
| opus | 2 | 12,450 | 8,230 | $0.28 |
| sonnet | 5 | 28,900 | 15,670 | $0.14 |
| haiku | 3 | 6,200 | 1,450 | $0.002 |
| **Total** | **10** | **47,550** | **25,350** | **$0.42** |

---

## Shadow Workspace Verification

**Container:** shadow-rvgb-1732880400-a1b2c3

### Verification Gauntlet Results

| Stage | Status | Details |
|-------|--------|---------|
| 1. Syntax Check | ✅ PASS | No syntax errors |
| 2. Linter (clippy) | ⚠️ WARN | 3 warnings (non-blocking) |
| 3. Type Check | ✅ PASS | All types valid |
| 4. Security Scan | ✅ PASS | No vulnerabilities (cargo-audit) |
| 5. Unit Tests | ✅ PASS | 47/47 tests passed (100% coverage) |

**Overall:** ✅ PASSED

**Warnings (non-blocking):**
- Unused import in src/utils.rs:15
- Consider using if-let in src/engine.rs:230
- Function complexity high in src/engine.rs:process_order

---

## TDD Loop Results

| Strike | Action | Result | Duration |
|--------|--------|--------|----------|
| 1 | Initial verification | ❌ FAIL | - |
|   | Error: Type mismatch in src/engine.rs:145 | | |
| 2 | Agent fix attempt (@rust-pro) | ✅ PASS | 1m 20s |
|   | Fix: Added ? operator for error propagation | | |

**Total Attempts:** 2/3 (succeeded on Strike 2)

---

## Multi-Perspective Review

| Reviewer | Rating | Critical | Warnings | Notes |
|----------|--------|----------|----------|-------|
| @security-auditor | 🟢 Good | 0 | 1 | Consider rate limiting on WS endpoint |
| @architecture-reviewer | 🟢 Excellent | 0 | 0 | Clean separation, good error handling |
| @performance-reviewer | 🟡 Acceptable | 0 | 2 | Clone in hot path (line 145) |
| @simplicity-reviewer | 🟢 Simple | 0 | 1 | Extract validation helper |
| @code-reviewer | 🟢 High Quality | 0 | 0 | Idiomatic Rust, good coverage |

**Overall Assessment:** ✅ APPROVED (no critical issues)

**Detailed Findings:**
- Security: Rate limiting suggestion (src/websocket.rs:89)
- Performance: Unnecessary clone (src/engine.rs:145) - consider Arc
- Simplicity: Extract validation function (src/websocket.rs:120-140)

---

## Reflexion

**Self-Critique:** ✅ All checks passed
- ✅ Solves stated problem (connection pool with bounded channels)
- ✅ No obvious bugs (47 tests passing)
- ✅ Not over-engineered (simplicity review: 🟢)
- ✅ No critical review findings
- ✅ Confident to deploy

**Reflection Generated:**

**Learning:** When implementing async Rust functions that can error, always define and import error types before using Result<T, E>

**Context:**
- What failed: Type errors in async function (Strike 1)
- Root cause: Missing error type import
- Fix applied: Added `use crate::errors::Error;`
- Lesson: Define error types early in module hierarchy

**Stored in:**
- ✅ Procedural memory (PostgreSQL)
- ✅ Knowledge graph (reflection → src/engine.rs)
- ✅ Tags: rust, async, error-handling, types, result

---

## Shadow Workspace Status

**Status:** ✅ COMMITTED to main workspace

**Changes Applied:**
- Modified: src/engine.rs (+120 lines)
- Modified: src/websocket.rs (+85 lines)
- Added: src/connection_pool.rs (new file, 200 lines)
- Modified: tests/engine_test.rs (+30 lines)

**Commit Hash:** a1b2c3d4e5f6

**Shadow Container:** Cleaned up (stopped and removed)

---

## Memory Consolidation

**Consolidation completed at:** 2025-11-29T10:38:32Z

### Episodic Memory
- New episodes: 23 (from this pipeline)
- Total episodes: 1,270
- Archived: 145 (>30 days, low importance)

### Semantic Memory
- Patterns updated: 2 (rust-async-websockets, error-handling-async)
- New patterns: 1 (bounded-channel-connection-pool, utility: 0.7)
- Patterns pruned: 0 (next prune: 9 runs from now)

### Knowledge Graph
- New entities: 5 (3 functions, 1 file, 1 reflection)
- New relations: 4
- Updated relations: 2 (weight increased)
- **Total graph size:** 487 entities, 1,203 relations

### Procedural Memory (Reflections)
- New reflections: 1 (rust async error handling)
- Total reflections: 34

---

## Knowledge Graph Updates

**New Entities:**
- file:src/connection_pool.rs
- function:ConnectionPool::new
- function:ConnectionPool::acquire
- function:ConnectionPool::release
- reflection:rust-async-error-types

**New Relations:**
- src/websocket.rs --uses--> src/connection_pool.rs
- src/engine.rs --uses--> src/connection_pool.rs
- reflection:rust-async-error-types --applies_to--> src/engine.rs
- ConnectionPool::new --called_by--> src/websocket.rs

**Graph Insights:**
- Most central file: src/engine.rs (15 relations)
- Most reused module: src/types.rs (imported by 8 files)

---

## Final Summary

✅ **Task completed successfully**

**Key Achievements:**
- ✅ WebSocket connection pool implemented with bounded channels
- ✅ Graceful shutdown for 10K+ concurrent connections
- ✅ Comprehensive error handling and recovery
- ✅ 100% test coverage (47/47 tests passing)
- ✅ All security and quality reviews passed
- ✅ Changes committed to main workspace

**Learnings Captured:**
- 1 new reflection stored (async error handling)
- 1 new semantic pattern (bounded-channel-connection-pool)
- Knowledge graph updated with 5 entities, 4 relations

**Pipeline Efficiency:**
- Total duration: 8m 32s
- Model cost: $0.42
- TDD strikes: 2/3 (resolved on second attempt)
- Verification: First-pass after Strike 2 fix

**Next Steps:**
- Consider performance optimizations (Arc instead of clone)
- Add rate limiting to WebSocket endpoint (security suggestion)
- Extract validation helper function (simplicity suggestion)

---

## Infrastructure Cleanup

- ✅ Shadow container stopped and removed
- ✅ Redis Blackboard artifacts archived
- ✅ PostgreSQL memory consolidated
- ✅ Temporary files cleaned up

**Blackboard data retained for:** 7 days (then auto-purged)

---

**RVGB Pipeline ID:** rvgb-1732880400-a1b2c3
**Timestamp:** 2025-11-29T10:38:32Z
**Version:** RVGB v3.0
```

---

## SKIP OPTIONS

User can skip auto-steps by saying:

**Infrastructure:**
- "offline mode" → Skip infrastructure checks, use JSON fallbacks
- "no docker" → Skip shadow workspace, use git worktree instead

**Verification:**
- "skip tests" → Skip STEP 10 (TDD Loop)
- "skip review" → Skip STEP 11 (Multi-perspective review)
- "skip verification" → Skip STEP 9 (Verification gauntlet)

**Memory:**
- "skip memory" → Skip STEP 2 (Memory retrieval)
- "skip consolidation" → Skip STEP 14 (Memory consolidation)
- "skip reflection" → Skip STEP 12 (Reflexion)

**Quick Mode:**
- "quick mode" → Skip: STEP 9, 10, 11, 12, 14 (verification, TDD, reviews, reflexion, consolidation)
- "direct mode" → Skip: STEP 1, 7, 13 (infrastructure, shadow workspace, commit isolation)

**Debug Mode:**
- "keep shadow" → Don't clean up shadow container (for debugging)
- "verbose" → Include all Blackboard operations in report

---

## FALLBACK MODES

**If infrastructure unavailable:**

### PostgreSQL → JSON Files
```
Memory location: /home/rnd/.claude/orchestrator/memory/
- episodic_memory.json (raw episodes)
- semantic_memory.json (patterns)
- procedural_memory.json (reflections)
- knowledge_graph.json (entities + relations)
```

### Redis → In-Memory Dict
```python
# In-memory Blackboard (no persistence across runs)
blackboard = {
    "artifacts": {},
    "locks": {},
    "status": {},
    "agents": {}
}
```

### Docker → Git Worktree
```bash
# Use git worktree instead of Docker container
git worktree add .worktrees/$PIPELINE_ID
# Work in .worktrees/$PIPELINE_ID/
# Merge or delete worktree at end
```

### MCP → Direct Queries
```bash
# Instead of mcp__memory__search_memory()
psql $DATABASE_URL -c "SELECT * FROM episodic_memory WHERE ..."
```

---

## ORCHESTRATOR RESPONSIBILITIES

**DO:**
- ✅ Delegate ALL implementation to agents
- ✅ Coordinate via Blackboard
- ✅ Run verification in shadow workspace
- ✅ Update memory after completion
- ✅ Generate reflections from failures
- ✅ Provide comprehensive reports

**DO NOT:**
- ❌ Write implementation code yourself
- ❌ Skip verification steps (unless user says "skip")
- ❌ Forget to update memory/knowledge graph
- ❌ Commit without shadow verification
- ❌ Ignore critical review findings

---

## BEGIN RVGB ORCHESTRATION

Execute the 15-step RVGB pipeline for the task specified above.
