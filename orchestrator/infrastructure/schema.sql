-- =============================================================================
-- AI Orchestrator Hybrid Memory System Schema
-- =============================================================================
-- This schema implements a multi-faceted memory architecture combining:
-- 1. Semantic memory (knowledge graph via nodes/edges)
-- 2. Episodic memory (short-term conversation buffer)
-- 3. Procedural memory (skills and learned procedures)
-- 4. Pattern memory (success/failure cases for learning)
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- =============================================================================
-- SEMANTIC MEMORY: Knowledge Graph Nodes
-- =============================================================================
-- Stores entities (files, concepts, agents, errors, etc.) with semantic embeddings
-- Supports temporal validity tracking (when facts are true/false)
-- Importance scoring for retrieval prioritization
-- =============================================================================

CREATE TABLE memory_nodes (
    node_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Node classification and identity
    label VARCHAR(50) NOT NULL, -- FILE, ERROR, CONCEPT, AGENT, TOOL, PATTERN, etc.
    name TEXT NOT NULL,
    description TEXT,
    content_summary TEXT,

    -- Semantic search support
    embedding vector(1536), -- OpenAI ada-002 or similar embedding

    -- Retrieval scoring
    importance_score FLOAT NOT NULL DEFAULT 0.5 CHECK (importance_score >= 0 AND importance_score <= 1),

    -- Temporal tracking
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_accessed TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Temporal validity (for facts that change over time)
    valid_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), -- When this fact became true
    invalid_at TIMESTAMPTZ, -- When this fact became false (NULL = currently valid)

    -- Extensible metadata storage
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Ensure temporal validity makes sense
    CONSTRAINT valid_temporal_range CHECK (invalid_at IS NULL OR invalid_at > valid_at)
);

-- Create indexes for efficient querying
CREATE INDEX idx_memory_nodes_label ON memory_nodes(label);
CREATE INDEX idx_memory_nodes_name ON memory_nodes(name);
CREATE INDEX idx_memory_nodes_created_at ON memory_nodes(created_at DESC);
CREATE INDEX idx_memory_nodes_last_accessed ON memory_nodes(last_accessed DESC);
CREATE INDEX idx_memory_nodes_importance ON memory_nodes(importance_score DESC);
CREATE INDEX idx_memory_nodes_validity ON memory_nodes(valid_at, invalid_at) WHERE invalid_at IS NULL;
CREATE INDEX idx_memory_nodes_metadata ON memory_nodes USING gin(metadata);

-- HNSW index for semantic similarity search
CREATE INDEX idx_memory_nodes_embedding ON memory_nodes
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- SEMANTIC MEMORY: Knowledge Graph Edges
-- =============================================================================
-- Represents typed relationships between nodes
-- Supports weighted connections and temporal validity
-- Examples: FILE depends_on LIBRARY, AGENT authored FILE, ERROR fixed_by COMMIT
-- =============================================================================

CREATE TABLE memory_edges (
    edge_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Graph structure
    source_node_id UUID NOT NULL REFERENCES memory_nodes(node_id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES memory_nodes(node_id) ON DELETE CASCADE,

    -- Relationship semantics
    relation_type VARCHAR(100) NOT NULL, -- DEPENDS_ON, FIXES, AUTHORED_BY, USES, CALLS, etc.
    weight FLOAT NOT NULL DEFAULT 1.0 CHECK (weight >= 0),

    -- Temporal validity
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ, -- NULL means currently valid

    -- Extensible metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Prevent self-loops
    CONSTRAINT no_self_loops CHECK (source_node_id != target_node_id),

    -- Ensure temporal validity
    CONSTRAINT valid_edge_temporal_range CHECK (valid_until IS NULL OR valid_until > valid_from)
);

-- Create indexes for graph traversal
CREATE INDEX idx_memory_edges_source ON memory_edges(source_node_id);
CREATE INDEX idx_memory_edges_target ON memory_edges(target_node_id);
CREATE INDEX idx_memory_edges_relation ON memory_edges(relation_type);
CREATE INDEX idx_memory_edges_weight ON memory_edges(weight DESC);
CREATE INDEX idx_memory_edges_validity ON memory_edges(valid_from, valid_until) WHERE valid_until IS NULL;
CREATE INDEX idx_memory_edges_metadata ON memory_edges USING gin(metadata);

-- Composite index for efficient relationship queries
CREATE INDEX idx_memory_edges_source_relation ON memory_edges(source_node_id, relation_type);
CREATE INDEX idx_memory_edges_target_relation ON memory_edges(target_node_id, relation_type);

-- =============================================================================
-- PATTERN MEMORY: Execution Patterns
-- =============================================================================
-- Stores observed patterns of success and failure
-- Enables learning from past experiences
-- Supports retrieval of similar situations via embedding similarity
-- =============================================================================

CREATE TABLE execution_patterns (
    pattern_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Pattern classification
    pattern_type VARCHAR(20) NOT NULL CHECK (pattern_type IN ('SUCCESS', 'FAILURE')),

    -- Semantic search for similar contexts
    context_embedding vector(1536),

    -- Pattern details
    trigger_context TEXT NOT NULL, -- What situation triggered this pattern
    approach_summary TEXT NOT NULL, -- What approach was taken
    outcome_result TEXT NOT NULL, -- What happened
    correction_strategy TEXT, -- For failures: how to fix; for success: why it worked

    -- Usage statistics
    frequency_count INT NOT NULL DEFAULT 1,
    last_encountered TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Metadata for additional context
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create indexes
CREATE INDEX idx_execution_patterns_type ON execution_patterns(pattern_type);
CREATE INDEX idx_execution_patterns_frequency ON execution_patterns(frequency_count DESC);
CREATE INDEX idx_execution_patterns_last_encountered ON execution_patterns(last_encountered DESC);
CREATE INDEX idx_execution_patterns_metadata ON execution_patterns USING gin(metadata);

-- HNSW index for finding similar contexts
CREATE INDEX idx_execution_patterns_embedding ON execution_patterns
USING hnsw (context_embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- EPISODIC MEMORY: Short-term Conversation Buffer
-- =============================================================================
-- Stores recent interactions within pipeline runs
-- Acts as a working memory buffer for current context
-- Can be consolidated into long-term memory (nodes/edges) later
-- =============================================================================

CREATE TABLE episodes (
    episode_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Episode context
    pipeline_run_id UUID NOT NULL, -- Groups episodes by execution run
    step_number INT NOT NULL, -- Ordering within the run

    -- Message details
    role VARCHAR(20) NOT NULL CHECK (role IN ('USER', 'AGENT', 'SYSTEM', 'TOOL')),
    content TEXT NOT NULL,

    -- Semantic search support
    embedding vector(1536),

    -- Temporal tracking
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Extensible metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Ensure ordering makes sense
    CONSTRAINT positive_step_number CHECK (step_number >= 0)
);

-- Create indexes
CREATE INDEX idx_episodes_pipeline_run ON episodes(pipeline_run_id, step_number);
CREATE INDEX idx_episodes_created_at ON episodes(created_at DESC);
CREATE INDEX idx_episodes_role ON episodes(role);
CREATE INDEX idx_episodes_metadata ON episodes USING gin(metadata);

-- HNSW index for semantic search within episodes
CREATE INDEX idx_episodes_embedding ON episodes
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- PROCEDURAL MEMORY: Skills and Learned Procedures
-- =============================================================================
-- Stores reusable skills and how-to knowledge
-- Tracks success rates and usage patterns
-- Steps stored as JSONB for flexible procedure representation
-- =============================================================================

CREATE TABLE procedural_memory (
    skill_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Skill identity
    skill_name TEXT NOT NULL UNIQUE,
    description TEXT,

    -- Procedure definition
    steps JSONB NOT NULL DEFAULT '[]'::jsonb, -- Array of step objects

    -- Performance tracking
    success_rate FLOAT NOT NULL DEFAULT 0.0 CHECK (success_rate >= 0 AND success_rate <= 1),
    times_used INT NOT NULL DEFAULT 0,
    last_used TIMESTAMPTZ,

    -- Temporal tracking
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Extensible metadata
    metadata JSONB DEFAULT '{}'::jsonb,

    -- Ensure valid usage stats
    CONSTRAINT valid_times_used CHECK (times_used >= 0)
);

-- Create indexes
CREATE INDEX idx_procedural_memory_name ON procedural_memory(skill_name);
CREATE INDEX idx_procedural_memory_success_rate ON procedural_memory(success_rate DESC);
CREATE INDEX idx_procedural_memory_times_used ON procedural_memory(times_used DESC);
CREATE INDEX idx_procedural_memory_last_used ON procedural_memory(last_used DESC NULLS LAST);
CREATE INDEX idx_procedural_memory_metadata ON procedural_memory USING gin(metadata);

-- =============================================================================
-- CONTEXT RETRIEVAL FUNCTION
-- =============================================================================
-- Implements hybrid scoring combining:
-- - Semantic relevance (cosine similarity)
-- - Importance score
-- - Recency decay (exponential falloff)
--
-- Score formula: (0.5 * relevance) + (0.3 * importance) + (0.2 * recency_decay)
-- Recency decay: EXP(-0.0001 * seconds_since_access)
-- =============================================================================

CREATE OR REPLACE FUNCTION retrieve_context(
    query_embedding vector(1536),
    limit_count INT DEFAULT 10,
    min_score FLOAT DEFAULT 0.0
)
RETURNS TABLE (
    node_id UUID,
    label VARCHAR(50),
    name TEXT,
    description TEXT,
    content_summary TEXT,
    importance_score FLOAT,
    last_accessed TIMESTAMPTZ,
    retrieval_score FLOAT,
    relevance_score FLOAT,
    recency_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        mn.node_id,
        mn.label,
        mn.name,
        mn.description,
        mn.content_summary,
        mn.importance_score,
        mn.last_accessed,
        -- Hybrid scoring formula
        (
            (0.5 * (1 - (mn.embedding <=> query_embedding))) + -- Cosine similarity (convert distance to similarity)
            (0.3 * mn.importance_score) +
            (0.2 * EXP(-0.0001 * EXTRACT(EPOCH FROM (NOW() - mn.last_accessed))))
        ) AS retrieval_score,
        -- Individual component scores for transparency
        (1 - (mn.embedding <=> query_embedding)) AS relevance_score,
        EXP(-0.0001 * EXTRACT(EPOCH FROM (NOW() - mn.last_accessed))) AS recency_score
    FROM memory_nodes mn
    WHERE
        mn.embedding IS NOT NULL
        AND (mn.invalid_at IS NULL OR mn.invalid_at > NOW()) -- Only consider currently valid nodes
    ORDER BY retrieval_score DESC
    LIMIT limit_count;

    -- Update last_accessed for retrieved nodes (optional, uncomment if desired)
    -- UPDATE memory_nodes
    -- SET last_accessed = NOW()
    -- WHERE node_id IN (SELECT node_id FROM retrieved_nodes);
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- UTILITY FUNCTIONS
-- =============================================================================

-- Function to mark a node as invalid (soft delete)
CREATE OR REPLACE FUNCTION invalidate_node(node_uuid UUID, invalidation_time TIMESTAMPTZ DEFAULT NOW())
RETURNS VOID AS $$
BEGIN
    UPDATE memory_nodes
    SET invalid_at = invalidation_time
    WHERE node_id = node_uuid AND invalid_at IS NULL;
END;
$$ LANGUAGE plpgsql;

-- Function to update procedural memory success rate
CREATE OR REPLACE FUNCTION update_skill_performance(
    skill_uuid UUID,
    was_successful BOOLEAN
)
RETURNS VOID AS $$
DECLARE
    current_success_rate FLOAT;
    current_times_used INT;
    new_success_rate FLOAT;
BEGIN
    -- Get current stats
    SELECT success_rate, times_used
    INTO current_success_rate, current_times_used
    FROM procedural_memory
    WHERE skill_id = skill_uuid;

    -- Calculate new success rate using incremental average
    IF was_successful THEN
        new_success_rate := (current_success_rate * current_times_used + 1.0) / (current_times_used + 1);
    ELSE
        new_success_rate := (current_success_rate * current_times_used) / (current_times_used + 1);
    END IF;

    -- Update the skill
    UPDATE procedural_memory
    SET
        success_rate = new_success_rate,
        times_used = times_used + 1,
        last_used = NOW(),
        updated_at = NOW()
    WHERE skill_id = skill_uuid;
END;
$$ LANGUAGE plpgsql;

-- Function to increment pattern frequency
CREATE OR REPLACE FUNCTION increment_pattern_frequency(pattern_uuid UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE execution_patterns
    SET
        frequency_count = frequency_count + 1,
        last_encountered = NOW()
    WHERE pattern_id = pattern_uuid;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- VIEWS FOR COMMON QUERIES
-- =============================================================================

-- View for currently valid nodes only
CREATE VIEW valid_memory_nodes AS
SELECT * FROM memory_nodes
WHERE invalid_at IS NULL OR invalid_at > NOW();

-- View for currently valid edges only
CREATE VIEW valid_memory_edges AS
SELECT * FROM memory_edges
WHERE valid_until IS NULL OR valid_until > NOW();

-- View for high-importance nodes
CREATE VIEW important_nodes AS
SELECT * FROM memory_nodes
WHERE importance_score > 0.7
  AND (invalid_at IS NULL OR invalid_at > NOW())
ORDER BY importance_score DESC;

-- View for recent episodes grouped by pipeline run
CREATE VIEW recent_episodes AS
SELECT
    pipeline_run_id,
    COUNT(*) as episode_count,
    MIN(created_at) as run_started,
    MAX(created_at) as run_ended,
    ARRAY_AGG(role ORDER BY step_number) as roles,
    ARRAY_AGG(episode_id ORDER BY step_number) as episode_ids
FROM episodes
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY pipeline_run_id
ORDER BY run_started DESC;

-- View for top-performing skills
CREATE VIEW top_skills AS
SELECT
    skill_id,
    skill_name,
    description,
    success_rate,
    times_used,
    last_used,
    (success_rate * LOG(times_used + 1)) as skill_score -- Weighted by usage
FROM procedural_memory
WHERE times_used > 0
ORDER BY skill_score DESC;

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Trigger to auto-update updated_at timestamp on procedural_memory
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_procedural_memory_updated_at
    BEFORE UPDATE ON procedural_memory
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE memory_nodes IS 'Semantic memory: entities in the knowledge graph with embeddings for retrieval';
COMMENT ON TABLE memory_edges IS 'Knowledge graph relationships between memory nodes with temporal validity';
COMMENT ON TABLE execution_patterns IS 'Pattern memory: observed success/failure patterns for learning';
COMMENT ON TABLE episodes IS 'Episodic memory: short-term conversation buffer for current context';
COMMENT ON TABLE procedural_memory IS 'Procedural memory: reusable skills and learned procedures';

COMMENT ON FUNCTION retrieve_context IS 'Hybrid retrieval combining semantic similarity, importance, and recency';
COMMENT ON FUNCTION invalidate_node IS 'Soft delete a node by marking it invalid at a given timestamp';
COMMENT ON FUNCTION update_skill_performance IS 'Update skill success rate based on execution outcome';
COMMENT ON FUNCTION increment_pattern_frequency IS 'Increment pattern encounter frequency and update timestamp';

-- =============================================================================
-- END OF SCHEMA
-- =============================================================================
