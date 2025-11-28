"""
Memory Consolidation System for AI Orchestrator

Implements the "Sleep Cycle" - converting episodic memory to semantic memory.
Based on research from:
- Generative Agents (Stanford, 2023)
- Reflexion (Northeastern, 2023)
- Memory consolidation in human cognition

This system processes raw episodic memories (agent interactions) and converts
them into structured semantic knowledge (entities, relations, patterns).
"""

import json
import math
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass, asdict
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class Episode:
    """Represents a single episodic memory - a raw agent interaction."""
    episode_id: str
    pipeline_run_id: str
    step_number: int
    role: str  # 'planner', 'executor', 'reviewer', etc.
    content: str
    embedding: List[float]
    created_at: datetime
    importance: Optional[float] = None
    last_accessed: Optional[datetime] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.last_accessed:
            data['last_accessed'] = self.last_accessed.isoformat()
        return data


@dataclass
class SemanticNode:
    """Represents a piece of semantic knowledge extracted from episodes."""
    name: str
    node_type: str  # 'file', 'concept', 'error', 'decision', 'pattern', etc.
    description: str
    importance: float  # 0.0 to 1.0
    sources: List[str]  # episode_ids that contributed to this node
    created_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.last_updated:
            data['last_updated'] = self.last_updated.isoformat()
        return data


@dataclass
class Relation:
    """Represents a relationship between semantic nodes."""
    source: str  # node name
    relation_type: str  # 'uses', 'fixes', 'implements', 'related_to', etc.
    target: str  # node name
    strength: float = 1.0  # 0.0 to 1.0, confidence in this relation
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None  # None means currently valid
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        if self.valid_from:
            data['valid_from'] = self.valid_from.isoformat()
        if self.valid_to:
            data['valid_to'] = self.valid_to.isoformat()
        return data


@dataclass
class Reflection:
    """Represents a learned lesson from a failure or success."""
    reflection_id: str
    context: str
    error_or_outcome: str
    insight: str
    prevention_plan: str
    created_at: datetime
    embedding: Optional[List[float]] = None
    times_referenced: int = 0
    success_rate: float = 0.0  # How often following this reflection helped

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data


@dataclass
class ConsolidationReport:
    """Summary of a consolidation run."""
    pipeline_run_id: str
    episodes_processed: int
    clusters_formed: int
    nodes_created: int
    nodes_updated: int
    relations_created: int
    reflections_generated: int
    processing_time_seconds: float
    timestamp: datetime

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class MemoryConsolidator:
    """
    Implements the memory consolidation algorithm.
    Converts episodic memories to semantic knowledge.
    Based on Generative Agents (Stanford) research.

    Architecture:
    - Episodic Memory: Raw agent interactions (short-term)
    - Semantic Memory: Extracted knowledge graph (long-term)
    - Procedural Memory: Learned patterns and reflections
    """

    def __init__(self, db_connection, llm_client, config: Optional[Dict] = None):
        """
        Initialize the consolidator.

        Args:
            db_connection: Database connection for storing/retrieving memories
            llm_client: LLM client for generating embeddings and extracting insights
            config: Optional configuration overrides
        """
        self.db = db_connection
        self.llm = llm_client

        # Default configuration
        self.config = {
            'retrieval_weights': (0.5, 0.3, 0.2),  # (relevance, importance, recency)
            'recency_decay_rate': 0.995,
            'clustering_threshold': 0.75,  # Cosine similarity threshold
            'min_cluster_size': 2,
            'max_cluster_size': 10,
            'importance_threshold_high': 0.7,
            'importance_threshold_low': 0.3,
            'utility_threshold': 0.3,
            'pattern_decay_rate': 0.01,
            'max_times_for_utility': 100,
            **(config or {})
        }

        logger.info("MemoryConsolidator initialized with config: %s", self.config)

    # ============================================
    # RETRIEVAL SCORING (Generative Agents formula)
    # ============================================

    def calculate_retrieval_score(
        self,
        memory_embedding: List[float],
        query_embedding: List[float],
        importance: float,
        last_accessed: datetime,
        weights: Optional[Tuple[float, float, float]] = None
    ) -> float:
        """
        Calculate retrieval score using Generative Agents formula:
        S(m, q) = w_rel * Relevance + w_imp * Importance + w_rec * Recency

        Args:
            memory_embedding: Embedding vector of the memory
            query_embedding: Embedding vector of the query
            importance: Importance score (0-1)
            last_accessed: When the memory was last accessed
            weights: Optional custom weights (relevance, importance, recency)

        Returns:
            Retrieval score (0-1+, higher is more relevant)

        Notes:
            Recency = e^(-λ * t) where t is hours since last access
            Default decay rate λ = 0.995 from Generative Agents paper
        """
        if weights is None:
            weights = self.config['retrieval_weights']

        w_rel, w_imp, w_rec = weights

        # Relevance: cosine similarity
        relevance = self._cosine_similarity(memory_embedding, query_embedding)

        # Recency: exponential decay
        hours_since_access = (datetime.now() - last_accessed).total_seconds() / 3600
        decay_rate = self.config['recency_decay_rate']
        recency = math.exp(-decay_rate * hours_since_access)

        score = (w_rel * relevance) + (w_imp * importance) + (w_rec * recency)

        logger.debug(
            "Retrieval score: %.3f (rel=%.3f, imp=%.3f, rec=%.3f)",
            score, relevance, importance, recency
        )

        return score

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            Cosine similarity (-1 to 1, typically 0 to 1 for embeddings)
        """
        if len(a) != len(b):
            raise ValueError(f"Vector dimensions don't match: {len(a)} vs {len(b)}")

        if not a or not b:
            return 0.0

        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    # ============================================
    # CONSOLIDATION (The "Sleep Cycle")
    # ============================================

    def consolidate(self, pipeline_run_id: str) -> ConsolidationReport:
        """
        Main consolidation entry point.

        This is the "sleep cycle" - processes raw episodic memories and
        converts them into structured semantic knowledge.

        Steps:
        1. Fetch episodes for the pipeline run
        2. Calculate importance scores for episodes
        3. Cluster similar episodes
        4. Extract entities and relations via LLM
        5. Store semantic nodes and edges
        6. Generate reflections from failures
        7. Archive raw episodes

        Args:
            pipeline_run_id: ID of the pipeline run to consolidate

        Returns:
            ConsolidationReport with statistics about the consolidation
        """
        start_time = datetime.now()
        logger.info("Starting consolidation for pipeline_run_id: %s", pipeline_run_id)

        try:
            # Step 1: Fetch episodes
            episodes = self._fetch_episodes(pipeline_run_id)
            logger.info("Fetched %d episodes", len(episodes))

            if not episodes:
                logger.warning("No episodes found for pipeline_run_id: %s", pipeline_run_id)
                return ConsolidationReport(
                    pipeline_run_id=pipeline_run_id,
                    episodes_processed=0,
                    clusters_formed=0,
                    nodes_created=0,
                    nodes_updated=0,
                    relations_created=0,
                    reflections_generated=0,
                    processing_time_seconds=0.0,
                    timestamp=datetime.now()
                )

            # Step 2: Calculate importance scores
            for episode in episodes:
                if episode.importance is None:
                    episode.importance = self._calculate_importance(episode.content)

            # Step 3: Cluster similar episodes
            clusters = self._cluster_episodes(episodes)
            logger.info("Formed %d clusters", len(clusters))

            # Step 4 & 5: Extract and store insights
            nodes_created = 0
            nodes_updated = 0
            relations_created = 0

            for cluster in clusters:
                nodes, relations = self._extract_insights(cluster)

                for node in nodes:
                    is_new = self._upsert_semantic_node(node)
                    if is_new:
                        nodes_created += 1
                    else:
                        nodes_updated += 1

                for relation in relations:
                    self._upsert_relation(relation)
                    relations_created += 1

            # Step 6: Generate reflections from failures
            reflections_generated = self._generate_reflections_from_episodes(episodes)

            # Step 7: Archive episodes
            episode_ids = [ep.episode_id for ep in episodes]
            self._archive_episodes(episode_ids)

            # Compile report
            processing_time = (datetime.now() - start_time).total_seconds()
            report = ConsolidationReport(
                pipeline_run_id=pipeline_run_id,
                episodes_processed=len(episodes),
                clusters_formed=len(clusters),
                nodes_created=nodes_created,
                nodes_updated=nodes_updated,
                relations_created=relations_created,
                reflections_generated=reflections_generated,
                processing_time_seconds=processing_time,
                timestamp=datetime.now()
            )

            logger.info("Consolidation complete: %s", report.to_dict())
            return report

        except Exception as e:
            logger.error("Consolidation failed for %s: %s", pipeline_run_id, str(e), exc_info=True)
            raise

    def _fetch_episodes(self, pipeline_run_id: str) -> List[Episode]:
        """
        Fetch all episodes for a pipeline run from the database.

        Args:
            pipeline_run_id: ID of the pipeline run

        Returns:
            List of Episode objects
        """
        # This is a placeholder - actual implementation depends on your DB schema
        try:
            query = """
                SELECT episode_id, pipeline_run_id, step_number, role, content,
                       embedding, created_at, importance, last_accessed
                FROM episodic_memory
                WHERE pipeline_run_id = ?
                ORDER BY step_number ASC
            """
            rows = self.db.execute(query, (pipeline_run_id,)).fetchall()

            episodes = []
            for row in rows:
                episodes.append(Episode(
                    episode_id=row['episode_id'],
                    pipeline_run_id=row['pipeline_run_id'],
                    step_number=row['step_number'],
                    role=row['role'],
                    content=row['content'],
                    embedding=json.loads(row['embedding']) if isinstance(row['embedding'], str) else row['embedding'],
                    created_at=datetime.fromisoformat(row['created_at']) if isinstance(row['created_at'], str) else row['created_at'],
                    importance=row.get('importance'),
                    last_accessed=datetime.fromisoformat(row['last_accessed']) if row.get('last_accessed') and isinstance(row['last_accessed'], str) else row.get('last_accessed')
                ))

            return episodes

        except Exception as e:
            logger.error("Failed to fetch episodes: %s", str(e), exc_info=True)
            return []

    def _cluster_episodes(self, episodes: List[Episode]) -> List[List[Episode]]:
        """
        Cluster episodes by semantic similarity using threshold-based clustering.

        Uses a simple greedy algorithm:
        1. Start with first episode as seed
        2. Add episodes within similarity threshold
        3. Move to next unclustered episode

        Args:
            episodes: List of episodes to cluster

        Returns:
            List of episode clusters
        """
        if not episodes:
            return []

        threshold = self.config['clustering_threshold']
        min_size = self.config['min_cluster_size']
        max_size = self.config['max_cluster_size']

        clusters: List[List[Episode]] = []
        clustered_ids: Set[str] = set()

        for seed_ep in episodes:
            if seed_ep.episode_id in clustered_ids:
                continue

            # Start new cluster with seed
            cluster = [seed_ep]
            clustered_ids.add(seed_ep.episode_id)

            # Add similar episodes
            for candidate in episodes:
                if candidate.episode_id in clustered_ids:
                    continue

                if len(cluster) >= max_size:
                    break

                # Check similarity with seed
                similarity = self._cosine_similarity(
                    seed_ep.embedding,
                    candidate.embedding
                )

                if similarity >= threshold:
                    cluster.append(candidate)
                    clustered_ids.add(candidate.episode_id)

            # Only keep clusters of sufficient size
            if len(cluster) >= min_size:
                clusters.append(cluster)
            else:
                # Create singleton clusters for important episodes
                if cluster[0].importance and cluster[0].importance >= self.config['importance_threshold_high']:
                    clusters.append(cluster)

        logger.info("Clustered %d episodes into %d clusters", len(episodes), len(clusters))
        return clusters

    def _extract_insights(self, episode_cluster: List[Episode]) -> Tuple[List[SemanticNode], List[Relation]]:
        """
        Use LLM to extract entities and relations from episode cluster.

        Args:
            episode_cluster: Cluster of related episodes

        Returns:
            Tuple of (semantic_nodes, relations)
        """
        # Prepare context for LLM
        context = self._format_cluster_for_llm(episode_cluster)

        prompt = f"""Analyze these agent interactions and extract structured knowledge.

{context}

Extract:
1. Key entities (files, concepts, errors, decisions, patterns)
2. Relationships between entities
3. Important insights or lessons learned

Return as JSON with this schema:
{{
  "entities": [
    {{
      "name": "entity name",
      "type": "file|concept|error|decision|pattern",
      "description": "what this entity represents",
      "importance": 0.0-1.0
    }}
  ],
  "relations": [
    {{
      "source": "entity name",
      "type": "uses|fixes|implements|related_to|causes|prevents",
      "target": "entity name",
      "strength": 0.0-1.0
    }}
  ]
}}

Focus on:
- Files that were created, modified, or discussed
- Errors that occurred and how they were resolved
- Decisions made and their rationale
- Patterns or best practices identified
- Concepts or techniques used

Only extract meaningful, non-trivial knowledge."""

        try:
            response = self.llm.generate(prompt, temperature=0.1, max_tokens=2000)
            data = json.loads(response)

            # Convert to dataclasses
            source_ids = [ep.episode_id for ep in episode_cluster]
            now = datetime.now()

            nodes = [
                SemanticNode(
                    name=entity['name'],
                    node_type=entity['type'],
                    description=entity['description'],
                    importance=entity['importance'],
                    sources=source_ids,
                    created_at=now,
                    last_updated=now
                )
                for entity in data.get('entities', [])
            ]

            relations = [
                Relation(
                    source=rel['source'],
                    relation_type=rel['type'],
                    target=rel['target'],
                    strength=rel.get('strength', 1.0),
                    valid_from=now
                )
                for rel in data.get('relations', [])
            ]

            logger.info("Extracted %d nodes and %d relations from cluster", len(nodes), len(relations))
            return nodes, relations

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s", str(e))
            return [], []
        except Exception as e:
            logger.error("Failed to extract insights: %s", str(e), exc_info=True)
            return [], []

    def _format_cluster_for_llm(self, cluster: List[Episode]) -> str:
        """Format episode cluster as readable context for LLM."""
        lines = []
        for i, ep in enumerate(cluster, 1):
            lines.append(f"[Step {ep.step_number}] {ep.role}:")
            lines.append(f"{ep.content}")
            if i < len(cluster):
                lines.append("")
        return "\n".join(lines)

    def _calculate_importance(self, content: str) -> float:
        """
        Calculate importance score (0-1) for a piece of content.

        High importance:
        - Errors and fixes
        - Architectural decisions
        - User preferences
        - Security issues
        - Breaking changes

        Low importance:
        - Routine operations
        - Debug logs
        - Status checks
        - Informational messages

        Args:
            content: Text content to score

        Returns:
            Importance score (0.0 to 1.0)
        """
        content_lower = content.lower()

        # High importance indicators
        high_indicators = [
            'error', 'exception', 'failed', 'failure', 'critical',
            'security', 'vulnerability', 'breach', 'exploit',
            'decision:', 'decided to', 'choosing', 'architectural',
            'breaking change', 'deprecated', 'removed',
            'user preference', 'configuration', 'setting',
            'bug', 'fix', 'patch', 'workaround',
            'performance issue', 'bottleneck', 'optimization'
        ]

        # Low importance indicators
        low_indicators = [
            'debug:', 'trace:', 'verbose:',
            'status: ok', 'success', 'completed normally',
            'starting', 'initialized', 'loading',
            'info:', 'running', 'processing'
        ]

        # Count matches
        high_count = sum(1 for indicator in high_indicators if indicator in content_lower)
        low_count = sum(1 for indicator in low_indicators if indicator in content_lower)

        # Base score
        if high_count > 0:
            base_score = 0.7 + (min(high_count, 3) * 0.1)  # Max 1.0
        elif low_count > 0:
            base_score = 0.3 - (min(low_count, 3) * 0.1)  # Min 0.0
        else:
            base_score = 0.5  # Neutral

        # Content length factor (very short or very long might be more important)
        length = len(content)
        if length < 50 or length > 500:
            base_score = min(base_score + 0.1, 1.0)

        return max(0.0, min(1.0, base_score))

    def _upsert_semantic_node(self, node: SemanticNode) -> bool:
        """
        Insert or update semantic node in database.

        Args:
            node: SemanticNode to upsert

        Returns:
            True if new node was created, False if existing node was updated
        """
        try:
            # Check if node exists
            existing = self.db.execute(
                "SELECT node_id, sources FROM semantic_memory WHERE name = ?",
                (node.name,)
            ).fetchone()

            if existing:
                # Update existing node
                merged_sources = list(set(
                    json.loads(existing['sources']) if isinstance(existing['sources'], str) else existing['sources']
                    + node.sources
                ))

                self.db.execute("""
                    UPDATE semantic_memory
                    SET description = ?,
                        importance = MAX(importance, ?),
                        sources = ?,
                        last_updated = ?
                    WHERE name = ?
                """, (
                    node.description,
                    node.importance,
                    json.dumps(merged_sources),
                    datetime.now().isoformat(),
                    node.name
                ))
                self.db.commit()

                logger.debug("Updated semantic node: %s", node.name)
                return False
            else:
                # Insert new node
                self.db.execute("""
                    INSERT INTO semantic_memory
                    (name, node_type, description, importance, sources, created_at, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    node.name,
                    node.node_type,
                    node.description,
                    node.importance,
                    json.dumps(node.sources),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                self.db.commit()

                logger.debug("Created semantic node: %s", node.name)
                return True

        except Exception as e:
            logger.error("Failed to upsert semantic node %s: %s", node.name, str(e), exc_info=True)
            return False

    def _upsert_relation(self, relation: Relation) -> bool:
        """
        Insert relation, handling temporal validity.

        If a relation already exists, invalidate the old one and create a new one.
        This allows tracking how relationships change over time.

        Args:
            relation: Relation to upsert

        Returns:
            True if successful, False otherwise
        """
        try:
            now = datetime.now()

            # Check for existing active relation
            existing = self.db.execute("""
                SELECT relation_id FROM semantic_relations
                WHERE source = ? AND relation_type = ? AND target = ?
                  AND valid_to IS NULL
            """, (relation.source, relation.relation_type, relation.target)).fetchone()

            if existing:
                # Invalidate existing relation
                self.db.execute("""
                    UPDATE semantic_relations
                    SET valid_to = ?
                    WHERE relation_id = ?
                """, (now.isoformat(), existing['relation_id']))

            # Insert new relation
            self.db.execute("""
                INSERT INTO semantic_relations
                (source, relation_type, target, strength, valid_from, valid_to, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                relation.source,
                relation.relation_type,
                relation.target,
                relation.strength,
                (relation.valid_from or now).isoformat(),
                relation.valid_to.isoformat() if relation.valid_to else None,
                json.dumps(relation.metadata) if relation.metadata else None
            ))
            self.db.commit()

            logger.debug("Upserted relation: %s -[%s]-> %s",
                        relation.source, relation.relation_type, relation.target)
            return True

        except Exception as e:
            logger.error("Failed to upsert relation: %s", str(e), exc_info=True)
            return False

    def _archive_episodes(self, episode_ids: List[str]):
        """
        Move processed episodes to archive table.

        This keeps the active episodic_memory table lean while preserving
        the raw data for potential future analysis.

        Args:
            episode_ids: List of episode IDs to archive
        """
        if not episode_ids:
            return

        try:
            # Copy to archive
            placeholders = ','.join('?' * len(episode_ids))
            self.db.execute(f"""
                INSERT INTO episodic_memory_archive
                SELECT * FROM episodic_memory
                WHERE episode_id IN ({placeholders})
            """, episode_ids)

            # Delete from active table
            self.db.execute(f"""
                DELETE FROM episodic_memory
                WHERE episode_id IN ({placeholders})
            """, episode_ids)

            self.db.commit()
            logger.info("Archived %d episodes", len(episode_ids))

        except Exception as e:
            logger.error("Failed to archive episodes: %s", str(e), exc_info=True)
            self.db.rollback()

    def _generate_reflections_from_episodes(self, episodes: List[Episode]) -> int:
        """
        Generate reflections from episodes containing failures or significant events.

        Args:
            episodes: List of episodes to analyze

        Returns:
            Number of reflections generated
        """
        count = 0

        for episode in episodes:
            # Look for errors or failures
            if self._is_failure_episode(episode):
                reflection = self.generate_reflection(
                    failure_context=episode.content,
                    error_log=episode.content  # In real implementation, might fetch related logs
                )

                if reflection:
                    count += 1

        return count

    def _is_failure_episode(self, episode: Episode) -> bool:
        """Check if episode represents a failure or error."""
        indicators = ['error', 'exception', 'failed', 'failure', 'traceback', 'stack trace']
        content_lower = episode.content.lower()
        return any(indicator in content_lower for indicator in indicators)

    # ============================================
    # UTILITY SCORING (for pattern pruning)
    # ============================================

    def calculate_utility_score(
        self,
        times_used: int,
        success_rate: float,
        last_used: datetime,
        max_times: Optional[int] = None
    ) -> float:
        """
        Calculate utility score for patterns.

        Formula:
        utility = (times_used/max * 0.4) + (success_rate * 0.3) + (recency * 0.3)

        Used to decide what to archive vs keep active.

        Args:
            times_used: How many times the pattern has been used
            success_rate: Success rate (0-1) when using this pattern
            last_used: When the pattern was last used
            max_times: Maximum times for normalization (default from config)

        Returns:
            Utility score (0-1)
        """
        if max_times is None:
            max_times = self.config['max_times_for_utility']

        # Usage score (normalized)
        usage_score = min(times_used / max_times, 1.0)

        # Recency score (exponential decay)
        days_since = (datetime.now() - last_used).days
        decay_rate = self.config['pattern_decay_rate']
        recency = math.exp(-decay_rate * days_since)

        # Weighted combination
        utility = (0.4 * usage_score) + (0.3 * success_rate) + (0.3 * recency)

        logger.debug(
            "Utility score: %.3f (usage=%.3f, success=%.3f, recency=%.3f)",
            utility, usage_score, success_rate, recency
        )

        return utility

    def prune_low_utility_patterns(self, threshold: Optional[float] = None) -> int:
        """
        Archive patterns with utility score below threshold.

        Run periodically (e.g., every 10 pipeline runs) to keep the
        procedural memory focused on useful patterns.

        Args:
            threshold: Utility threshold (default from config)

        Returns:
            Number of patterns archived
        """
        if threshold is None:
            threshold = self.config['utility_threshold']

        try:
            # Fetch all patterns with usage stats
            patterns = self.db.execute("""
                SELECT pattern_id, times_used, success_rate, last_used
                FROM procedural_memory
                WHERE archived = FALSE
            """).fetchall()

            to_archive = []

            for pattern in patterns:
                last_used = datetime.fromisoformat(pattern['last_used']) if isinstance(pattern['last_used'], str) else pattern['last_used']

                utility = self.calculate_utility_score(
                    times_used=pattern['times_used'],
                    success_rate=pattern['success_rate'],
                    last_used=last_used
                )

                if utility < threshold:
                    to_archive.append(pattern['pattern_id'])

            # Archive low-utility patterns
            if to_archive:
                placeholders = ','.join('?' * len(to_archive))
                self.db.execute(f"""
                    UPDATE procedural_memory
                    SET archived = TRUE, archived_at = ?
                    WHERE pattern_id IN ({placeholders})
                """, [datetime.now().isoformat()] + to_archive)
                self.db.commit()

            logger.info("Archived %d low-utility patterns (threshold=%.2f)", len(to_archive), threshold)
            return len(to_archive)

        except Exception as e:
            logger.error("Failed to prune patterns: %s", str(e), exc_info=True)
            return 0

    # ============================================
    # REFLECTION (Reflexion pattern)
    # ============================================

    def generate_reflection(self, failure_context: str, error_log: str) -> Optional[str]:
        """
        Generate a reflection from a failure using the Reflexion pattern.

        Reflexion prompts the agent to explicitly reason about failures and
        generate lessons learned that can guide future attempts.

        Args:
            failure_context: Context of what was being attempted
            error_log: The error or failure that occurred

        Returns:
            Reflection ID if successful, None otherwise
        """
        prompt = f"""You attempted a task but encountered a failure. Reflect on what happened and learn from it.

Context:
{failure_context}

Error/Failure:
{error_log}

Provide a structured reflection with:
1. What you were trying to accomplish
2. Why the failure occurred (root cause analysis)
3. What you learned from this failure
4. How to prevent this failure in the future (concrete steps)

Format as JSON:
{{
  "context_summary": "brief summary of what was attempted",
  "root_cause": "why the failure occurred",
  "insight": "key learning from this failure",
  "prevention_plan": "concrete steps to prevent this in the future"
}}"""

        try:
            response = self.llm.generate(prompt, temperature=0.2, max_tokens=1000)
            data = json.loads(response)

            # Generate reflection ID
            reflection_id = self._generate_reflection_id(failure_context, error_log)

            # Create embedding for retrieval
            embedding_text = f"{data['context_summary']} {data['insight']}"
            embedding = self.llm.embed(embedding_text)

            # Store reflection
            reflection = Reflection(
                reflection_id=reflection_id,
                context=data['context_summary'],
                error_or_outcome=error_log[:500],  # Truncate long errors
                insight=data['insight'],
                prevention_plan=data['prevention_plan'],
                created_at=datetime.now(),
                embedding=embedding
            )

            self.db.execute("""
                INSERT INTO procedural_memory
                (reflection_id, context, error_or_outcome, insight, prevention_plan,
                 created_at, embedding, times_referenced, success_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                reflection.reflection_id,
                reflection.context,
                reflection.error_or_outcome,
                reflection.insight,
                reflection.prevention_plan,
                reflection.created_at.isoformat(),
                json.dumps(reflection.embedding),
                0,
                0.0
            ))
            self.db.commit()

            logger.info("Generated reflection: %s", reflection_id)
            return reflection_id

        except json.JSONDecodeError as e:
            logger.error("Failed to parse reflection response as JSON: %s", str(e))
            return None
        except Exception as e:
            logger.error("Failed to generate reflection: %s", str(e), exc_info=True)
            return None

    def _generate_reflection_id(self, context: str, error: str) -> str:
        """Generate a unique ID for a reflection."""
        content = f"{context}:{error}:{datetime.now().isoformat()}"
        return f"refl_{hashlib.sha256(content.encode()).hexdigest()[:12]}"

    def get_relevant_reflections(self, task_context: str, limit: int = 3) -> List[Dict[str, str]]:
        """
        Retrieve relevant past reflections for a new task.

        Used to inject learned lessons into agent prompts before they
        attempt similar tasks.

        Args:
            task_context: Description of the current task
            limit: Maximum number of reflections to retrieve

        Returns:
            List of reflection dictionaries with insight and prevention_plan
        """
        try:
            # Generate embedding for task context
            query_embedding = self.llm.embed(task_context)

            # Fetch all reflections
            reflections = self.db.execute("""
                SELECT reflection_id, context, insight, prevention_plan,
                       embedding, times_referenced, last_referenced
                FROM procedural_memory
                WHERE archived = FALSE
                ORDER BY times_referenced DESC
                LIMIT 50
            """).fetchall()

            # Score and rank reflections
            scored_reflections = []

            for refl in reflections:
                embedding = json.loads(refl['embedding']) if isinstance(refl['embedding'], str) else refl['embedding']
                last_ref = datetime.fromisoformat(refl['last_referenced']) if refl.get('last_referenced') else datetime.now() - timedelta(days=365)

                score = self.calculate_retrieval_score(
                    memory_embedding=embedding,
                    query_embedding=query_embedding,
                    importance=0.8,  # Reflections are inherently important
                    last_accessed=last_ref
                )

                scored_reflections.append((score, refl))

            # Sort by score and take top N
            scored_reflections.sort(key=lambda x: x[0], reverse=True)
            top_reflections = scored_reflections[:limit]

            # Update access timestamps
            for _, refl in top_reflections:
                self.db.execute("""
                    UPDATE procedural_memory
                    SET times_referenced = times_referenced + 1,
                        last_referenced = ?
                    WHERE reflection_id = ?
                """, (datetime.now().isoformat(), refl['reflection_id']))
            self.db.commit()

            # Format for return
            results = [
                {
                    'context': refl['context'],
                    'insight': refl['insight'],
                    'prevention_plan': refl['prevention_plan']
                }
                for _, refl in top_reflections
            ]

            logger.info("Retrieved %d relevant reflections for task", len(results))
            return results

        except Exception as e:
            logger.error("Failed to retrieve reflections: %s", str(e), exc_info=True)
            return []


# ============================================
# USAGE EXAMPLE
# ============================================

def example_usage():
    """
    Example of how to use the MemoryConsolidator.

    This would typically be called after a pipeline run completes.
    """
    import sqlite3

    # Mock LLM client (in real usage, would be your actual LLM client)
    class MockLLMClient:
        def generate(self, prompt, temperature=0.7, max_tokens=1000):
            # Placeholder
            return json.dumps({
                "entities": [
                    {
                        "name": "user_authentication.py",
                        "type": "file",
                        "description": "User authentication module",
                        "importance": 0.8
                    }
                ],
                "relations": [
                    {
                        "source": "user_authentication.py",
                        "type": "implements",
                        "target": "JWT authentication",
                        "strength": 0.9
                    }
                ]
            })

        def embed(self, text):
            # Placeholder - return dummy embedding
            return [0.1] * 768

    # Setup
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    llm = MockLLMClient()

    # Create tables (simplified schema)
    db.execute("""
        CREATE TABLE IF NOT EXISTS episodic_memory (
            episode_id TEXT PRIMARY KEY,
            pipeline_run_id TEXT,
            step_number INTEGER,
            role TEXT,
            content TEXT,
            embedding TEXT,
            created_at TEXT,
            importance REAL,
            last_accessed TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS semantic_memory (
            node_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            node_type TEXT,
            description TEXT,
            importance REAL,
            sources TEXT,
            created_at TEXT,
            last_updated TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS procedural_memory (
            pattern_id TEXT PRIMARY KEY,
            reflection_id TEXT,
            context TEXT,
            error_or_outcome TEXT,
            insight TEXT,
            prevention_plan TEXT,
            created_at TEXT,
            embedding TEXT,
            times_referenced INTEGER DEFAULT 0,
            last_referenced TEXT,
            times_used INTEGER DEFAULT 0,
            success_rate REAL DEFAULT 0.0,
            archived BOOLEAN DEFAULT FALSE,
            archived_at TEXT
        )
    """)

    # Initialize consolidator
    consolidator = MemoryConsolidator(db, llm)

    # Run consolidation
    report = consolidator.consolidate("pipeline_run_123")

    print(f"Consolidation Report:")
    print(f"  Episodes processed: {report.episodes_processed}")
    print(f"  Clusters formed: {report.clusters_formed}")
    print(f"  Nodes created: {report.nodes_created}")
    print(f"  Nodes updated: {report.nodes_updated}")
    print(f"  Relations created: {report.relations_created}")
    print(f"  Processing time: {report.processing_time_seconds:.2f}s")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    example_usage()
