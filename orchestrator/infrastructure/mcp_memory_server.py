"""
MCP Memory Server for AI Orchestrator

A Model Context Protocol server that exposes memory operations as tools.
Provides semantic search, knowledge graph operations, and episodic memory.
"""

from mcp.server.fastmcp import FastMCP
import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncpg
import asyncio
from contextlib import asynccontextmanager

# Initialize MCP Server
mcp = FastMCP(name="OrchestratorMemory")

# Global connection pool
_pool: Optional[asyncpg.Pool] = None


# Database Connection Management
async def get_pool() -> asyncpg.Pool:
    """Get or create database connection pool."""
    global _pool
    if _pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not set")
        _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
    return _pool


@asynccontextmanager
async def get_connection():
    """Context manager for database connections."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


# Embedding Generation
async def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding vector for text.

    Currently a placeholder that returns a mock embedding.
    In production, this would call OpenAI API or a local embedding model.

    Args:
        text: Text to embed

    Returns:
        List of floats representing the embedding vector (1536 dimensions for OpenAI)
    """
    # TODO: Implement actual embedding generation
    # Option 1: OpenAI embeddings
    # import openai
    # response = await openai.embeddings.create(
    #     model="text-embedding-3-small",
    #     input=text
    # )
    # return response.data[0].embedding

    # Option 2: Local model (sentence-transformers)
    # from sentence_transformers import SentenceTransformer
    # model = SentenceTransformer('all-MiniLM-L6-v2')
    # return model.encode(text).tolist()

    # Placeholder: return zero vector of appropriate dimension
    return [0.0] * 1536


# Helper Functions
def format_timestamp(dt: Optional[datetime] = None) -> str:
    """Format datetime as ISO string."""
    if dt is None:
        dt = datetime.utcnow()
    return dt.isoformat()


def format_memory_result(record: Dict[str, Any], score: Optional[float] = None) -> Dict[str, Any]:
    """Format a memory record for output."""
    result = {
        "id": record.get("id"),
        "content": record.get("content") or record.get("description"),
        "metadata": record.get("metadata", {}),
        "created_at": record.get("created_at").isoformat() if record.get("created_at") else None,
    }
    if score is not None:
        result["relevance_score"] = round(score, 3)
    return result


# MCP Tool Implementations

@mcp.tool()
async def search_memory(query: str, limit: int = 5, filter_type: Optional[str] = None) -> str:
    """
    Semantically search long-term memory for relevant context.
    Uses hybrid vector + graph search.

    Args:
        query: Natural language search query
        limit: Max results to return (default 5)
        filter_type: Optional filter (FILE, ERROR, CONCEPT, PATTERN)

    Returns:
        JSON string of matching memories with relevance scores
    """
    try:
        # Generate query embedding
        query_embedding = await generate_embedding(query)

        async with get_connection() as conn:
            # Hybrid search: vector similarity + keyword match
            sql = """
                WITH vector_search AS (
                    SELECT
                        id,
                        content,
                        metadata,
                        created_at,
                        1 - (embedding <=> $1::vector) AS similarity
                    FROM semantic_memory
                    WHERE ($2::text IS NULL OR metadata->>'type' = $2)
                    ORDER BY embedding <=> $1::vector
                    LIMIT $3
                ),
                keyword_search AS (
                    SELECT
                        id,
                        content,
                        metadata,
                        created_at,
                        ts_rank(search_vector, plainto_tsquery($4)) AS rank
                    FROM semantic_memory
                    WHERE search_vector @@ plainto_tsquery($4)
                    AND ($2::text IS NULL OR metadata->>'type' = $2)
                    ORDER BY rank DESC
                    LIMIT $3
                )
                SELECT DISTINCT ON (id)
                    id, content, metadata, created_at,
                    COALESCE(similarity, 0) + COALESCE(rank, 0) AS score
                FROM (
                    SELECT * FROM vector_search
                    UNION ALL
                    SELECT * FROM keyword_search
                ) combined
                ORDER BY id, score DESC
                LIMIT $3
            """

            records = await conn.fetch(
                sql,
                query_embedding,
                filter_type,
                limit,
                query
            )

            results = [
                format_memory_result(dict(r), r["score"])
                for r in records
            ]

            return json.dumps({
                "query": query,
                "filter_type": filter_type,
                "results": results,
                "count": len(results)
            }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "query": query
        }, indent=2)


@mcp.tool()
async def record_pattern(
    pattern_type: str,
    trigger_context: str,
    approach: str,
    outcome: str,
    correction: Optional[str] = None
) -> str:
    """
    Record a success or failure pattern for future learning.

    Args:
        pattern_type: 'SUCCESS' or 'FAILURE'
        trigger_context: Description of the situation
        approach: Strategy used
        outcome: Result or error message
        correction: Fix applied (for failures)

    Returns:
        JSON confirmation with pattern ID
    """
    try:
        if pattern_type not in ["SUCCESS", "FAILURE"]:
            return json.dumps({
                "error": "pattern_type must be 'SUCCESS' or 'FAILURE'"
            })

        # Create composite content for embedding
        content = f"""
        Pattern Type: {pattern_type}
        Context: {trigger_context}
        Approach: {approach}
        Outcome: {outcome}
        {f'Correction: {correction}' if correction else ''}
        """.strip()

        embedding = await generate_embedding(content)

        metadata = {
            "type": "PATTERN",
            "pattern_type": pattern_type,
            "trigger_context": trigger_context,
            "approach": approach,
            "outcome": outcome,
            "correction": correction
        }

        async with get_connection() as conn:
            record = await conn.fetchrow(
                """
                INSERT INTO semantic_memory (content, embedding, metadata, search_vector)
                VALUES ($1, $2, $3, to_tsvector($1))
                RETURNING id, created_at
                """,
                content,
                embedding,
                json.dumps(metadata)
            )

            return json.dumps({
                "success": True,
                "pattern_id": record["id"],
                "pattern_type": pattern_type,
                "created_at": record["created_at"].isoformat()
            }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "pattern_type": pattern_type
        }, indent=2)


@mcp.tool()
async def create_entity(
    name: str,
    entity_type: str,
    description: str,
    importance: float = 0.5
) -> str:
    """
    Create a new entity in the knowledge graph.

    Args:
        name: Entity name (unique identifier)
        entity_type: FILE, SERVICE, CONCEPT, ERROR, USER, etc.
        description: What this entity represents
        importance: Score 0-1 (default 0.5)

    Returns:
        JSON confirmation with entity details
    """
    try:
        if not 0 <= importance <= 1:
            return json.dumps({
                "error": "importance must be between 0 and 1"
            })

        async with get_connection() as conn:
            # Check if entity already exists
            existing = await conn.fetchrow(
                "SELECT name FROM entities WHERE name = $1",
                name
            )

            if existing:
                return json.dumps({
                    "error": f"Entity '{name}' already exists",
                    "name": name
                })

            record = await conn.fetchrow(
                """
                INSERT INTO entities (name, type, description, importance, created_at)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING name, type, created_at
                """,
                name,
                entity_type,
                description,
                importance,
                datetime.utcnow()
            )

            return json.dumps({
                "success": True,
                "entity": {
                    "name": record["name"],
                    "type": record["type"],
                    "description": description,
                    "importance": importance,
                    "created_at": record["created_at"].isoformat()
                }
            }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "name": name
        }, indent=2)


@mcp.tool()
async def create_relation(
    source: str,
    relation: str,
    target: str,
    valid_from: Optional[str] = None
) -> str:
    """
    Create a relationship between entities in the knowledge graph.

    Args:
        source: Source entity name
        relation: DEPENDS_ON, USES, FIXES, AUTHORED_BY, etc.
        target: Target entity name
        valid_from: ISO timestamp (default: now)

    Returns:
        JSON confirmation with relation details
    """
    try:
        if valid_from:
            valid_from_dt = datetime.fromisoformat(valid_from.replace('Z', '+00:00'))
        else:
            valid_from_dt = datetime.utcnow()

        async with get_connection() as conn:
            # Verify both entities exist
            source_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM entities WHERE name = $1)",
                source
            )
            target_exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM entities WHERE name = $1)",
                target
            )

            if not source_exists:
                return json.dumps({
                    "error": f"Source entity '{source}' does not exist"
                })

            if not target_exists:
                return json.dumps({
                    "error": f"Target entity '{target}' does not exist"
                })

            record = await conn.fetchrow(
                """
                INSERT INTO relations (source, relation, target, valid_from)
                VALUES ($1, $2, $3, $4)
                RETURNING id, source, relation, target, valid_from
                """,
                source,
                relation,
                target,
                valid_from_dt
            )

            return json.dumps({
                "success": True,
                "relation": {
                    "id": record["id"],
                    "source": record["source"],
                    "relation": record["relation"],
                    "target": record["target"],
                    "valid_from": record["valid_from"].isoformat()
                }
            }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "source": source,
            "relation": relation,
            "target": target
        }, indent=2)


@mcp.tool()
async def invalidate_relation(source: str, relation: str, target: str) -> str:
    """
    Mark a relationship as no longer valid (temporal update).
    Sets invalid_at to current timestamp.

    Args:
        source: Source entity name
        relation: Relation type
        target: Target entity name

    Returns:
        JSON confirmation
    """
    try:
        async with get_connection() as conn:
            result = await conn.execute(
                """
                UPDATE relations
                SET invalid_at = $1
                WHERE source = $2
                AND relation = $3
                AND target = $4
                AND invalid_at IS NULL
                """,
                datetime.utcnow(),
                source,
                relation,
                target
            )

            # Extract number of rows updated
            rows_updated = int(result.split()[-1])

            if rows_updated == 0:
                return json.dumps({
                    "error": "No active relation found matching criteria",
                    "source": source,
                    "relation": relation,
                    "target": target
                })

            return json.dumps({
                "success": True,
                "invalidated": {
                    "source": source,
                    "relation": relation,
                    "target": target,
                    "invalid_at": datetime.utcnow().isoformat()
                }
            }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "source": source,
            "relation": relation,
            "target": target
        }, indent=2)


@mcp.tool()
async def get_entity_relations(entity_name: str, depth: int = 1) -> str:
    """
    Get all relationships for an entity (graph traversal).

    Args:
        entity_name: Name of entity to query
        depth: How many hops to traverse (default 1, max 3)

    Returns:
        JSON with entity details and all relations
    """
    try:
        if depth < 1 or depth > 3:
            return json.dumps({
                "error": "depth must be between 1 and 3"
            })

        async with get_connection() as conn:
            # Get entity details
            entity = await conn.fetchrow(
                "SELECT * FROM entities WHERE name = $1",
                entity_name
            )

            if not entity:
                return json.dumps({
                    "error": f"Entity '{entity_name}' not found"
                })

            # Recursive CTE for graph traversal
            relations_query = """
                WITH RECURSIVE entity_graph AS (
                    -- Base case: direct relations
                    SELECT
                        source, relation, target,
                        valid_from, invalid_at,
                        1 AS depth
                    FROM relations
                    WHERE (source = $1 OR target = $1)
                    AND invalid_at IS NULL

                    UNION

                    -- Recursive case: follow relations
                    SELECT
                        r.source, r.relation, r.target,
                        r.valid_from, r.invalid_at,
                        eg.depth + 1
                    FROM relations r
                    INNER JOIN entity_graph eg ON (
                        r.source = eg.target OR r.target = eg.source
                    )
                    WHERE eg.depth < $2
                    AND r.invalid_at IS NULL
                )
                SELECT DISTINCT * FROM entity_graph
                ORDER BY depth, source, relation, target
            """

            relations = await conn.fetch(relations_query, entity_name, depth)

            return json.dumps({
                "entity": {
                    "name": entity["name"],
                    "type": entity["type"],
                    "description": entity["description"],
                    "importance": entity["importance"],
                    "created_at": entity["created_at"].isoformat()
                },
                "relations": [
                    {
                        "source": r["source"],
                        "relation": r["relation"],
                        "target": r["target"],
                        "depth": r["depth"],
                        "valid_from": r["valid_from"].isoformat()
                    }
                    for r in relations
                ],
                "traversal_depth": depth,
                "relation_count": len(relations)
            }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "entity_name": entity_name
        }, indent=2)


@mcp.tool()
async def record_episode(
    pipeline_run_id: str,
    step_number: int,
    role: str,
    content: str
) -> str:
    """
    Record an episode to short-term memory buffer.
    Used during pipeline execution.

    Args:
        pipeline_run_id: Unique ID for this pipeline run
        step_number: Sequential step in the pipeline
        role: 'user', 'assistant', 'system', 'tool'
        content: The actual content/message

    Returns:
        JSON confirmation
    """
    try:
        async with get_connection() as conn:
            record = await conn.fetchrow(
                """
                INSERT INTO episodic_memory (pipeline_run_id, step_number, role, content, created_at)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, created_at
                """,
                pipeline_run_id,
                step_number,
                role,
                content,
                datetime.utcnow()
            )

            return json.dumps({
                "success": True,
                "episode_id": record["id"],
                "pipeline_run_id": pipeline_run_id,
                "step_number": step_number,
                "created_at": record["created_at"].isoformat()
            }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "pipeline_run_id": pipeline_run_id,
            "step_number": step_number
        }, indent=2)


@mcp.tool()
async def consolidate_episodes(pipeline_run_id: str) -> str:
    """
    Consolidate episodes into semantic memory.
    Extracts entities/relations from raw episodes.
    This is the "sleep cycle" for memory.

    Args:
        pipeline_run_id: ID of completed pipeline run

    Returns:
        JSON summary of consolidation
    """
    try:
        async with get_connection() as conn:
            # Fetch all episodes for this run
            episodes = await conn.fetch(
                """
                SELECT * FROM episodic_memory
                WHERE pipeline_run_id = $1
                ORDER BY step_number
                """,
                pipeline_run_id
            )

            if not episodes:
                return json.dumps({
                    "error": f"No episodes found for pipeline_run_id '{pipeline_run_id}'"
                })

            # Combine episodes into narrative
            narrative = "\n\n".join([
                f"Step {ep['step_number']} ({ep['role']}): {ep['content']}"
                for ep in episodes
            ])

            # Generate embedding for consolidated memory
            embedding = await generate_embedding(narrative)

            # Store in semantic memory
            metadata = {
                "type": "CONSOLIDATED_EPISODE",
                "pipeline_run_id": pipeline_run_id,
                "episode_count": len(episodes),
                "start_time": episodes[0]["created_at"].isoformat(),
                "end_time": episodes[-1]["created_at"].isoformat()
            }

            semantic_record = await conn.fetchrow(
                """
                INSERT INTO semantic_memory (content, embedding, metadata, search_vector)
                VALUES ($1, $2, $3, to_tsvector($1))
                RETURNING id
                """,
                narrative,
                embedding,
                json.dumps(metadata)
            )

            # Mark episodes as consolidated
            await conn.execute(
                """
                UPDATE episodic_memory
                SET consolidated = TRUE
                WHERE pipeline_run_id = $1
                """,
                pipeline_run_id
            )

            return json.dumps({
                "success": True,
                "pipeline_run_id": pipeline_run_id,
                "episodes_consolidated": len(episodes),
                "semantic_memory_id": semantic_record["id"],
                "narrative_length": len(narrative)
            }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "pipeline_run_id": pipeline_run_id
        }, indent=2)


@mcp.tool()
async def get_similar_patterns(
    context: str,
    pattern_type: Optional[str] = None,
    limit: int = 3
) -> str:
    """
    Find similar past patterns for analogical reasoning.
    Used before executing to learn from past attempts.

    Args:
        context: Description of current situation
        pattern_type: Optional filter for 'SUCCESS' or 'FAILURE'
        limit: Max patterns to return (default 3)

    Returns:
        JSON list of similar patterns with relevance scores
    """
    try:
        # Generate embedding for context
        context_embedding = await generate_embedding(context)

        async with get_connection() as conn:
            sql = """
                SELECT
                    id,
                    content,
                    metadata,
                    created_at,
                    1 - (embedding <=> $1::vector) AS similarity
                FROM semantic_memory
                WHERE metadata->>'type' = 'PATTERN'
                AND ($2::text IS NULL OR metadata->>'pattern_type' = $2)
                ORDER BY embedding <=> $1::vector
                LIMIT $3
            """

            records = await conn.fetch(
                sql,
                context_embedding,
                pattern_type,
                limit
            )

            patterns = []
            for r in records:
                meta = r["metadata"]
                patterns.append({
                    "id": r["id"],
                    "pattern_type": meta.get("pattern_type"),
                    "trigger_context": meta.get("trigger_context"),
                    "approach": meta.get("approach"),
                    "outcome": meta.get("outcome"),
                    "correction": meta.get("correction"),
                    "similarity": round(r["similarity"], 3),
                    "created_at": r["created_at"].isoformat()
                })

            return json.dumps({
                "context": context,
                "filter": pattern_type,
                "patterns": patterns,
                "count": len(patterns)
            }, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "context": context
        }, indent=2)


@mcp.resource("memory://stats")
async def get_memory_stats() -> str:
    """
    Return memory system statistics.

    Returns:
        JSON with counts and metrics
    """
    try:
        async with get_connection() as conn:
            stats = {}

            # Semantic memory count
            stats["semantic_memory_count"] = await conn.fetchval(
                "SELECT COUNT(*) FROM semantic_memory"
            )

            # Entity count by type
            entity_counts = await conn.fetch(
                "SELECT type, COUNT(*) as count FROM entities GROUP BY type ORDER BY count DESC"
            )
            stats["entities_by_type"] = {
                row["type"]: row["count"] for row in entity_counts
            }
            stats["total_entities"] = sum(stats["entities_by_type"].values())

            # Relation count
            stats["active_relations"] = await conn.fetchval(
                "SELECT COUNT(*) FROM relations WHERE invalid_at IS NULL"
            )
            stats["total_relations"] = await conn.fetchval(
                "SELECT COUNT(*) FROM relations"
            )

            # Episode stats
            stats["total_episodes"] = await conn.fetchval(
                "SELECT COUNT(*) FROM episodic_memory"
            )
            stats["unconsolidated_episodes"] = await conn.fetchval(
                "SELECT COUNT(*) FROM episodic_memory WHERE NOT consolidated"
            )

            # Pattern stats
            pattern_stats = await conn.fetch(
                """
                SELECT
                    metadata->>'pattern_type' as pattern_type,
                    COUNT(*) as count
                FROM semantic_memory
                WHERE metadata->>'type' = 'PATTERN'
                GROUP BY metadata->>'pattern_type'
                """
            )
            stats["patterns"] = {
                row["pattern_type"]: row["count"] for row in pattern_stats
            }

            # Database size (PostgreSQL specific)
            db_size = await conn.fetchval(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            )
            stats["database_size"] = db_size

            return json.dumps(stats, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e)
        }, indent=2)


# Lifecycle Management
@mcp.on_startup()
async def startup():
    """Initialize database connection on startup."""
    try:
        await get_pool()
        print("MCP Memory Server: Database connection established")
    except Exception as e:
        print(f"MCP Memory Server: Failed to connect to database: {e}")
        raise


@mcp.on_shutdown()
async def shutdown():
    """Clean up database connections on shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        print("MCP Memory Server: Database connection closed")


if __name__ == "__main__":
    mcp.run()
