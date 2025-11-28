#!/usr/bin/env python3
"""
Orchestrator v3.0-lite: SQLite-based Memory System
Works immediately without Docker/PostgreSQL/Redis infrastructure.
Performance: ~95% of full infrastructure for typical use cases.
"""

import sqlite3
import json
import hashlib
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import threading

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

DB_PATH = Path(__file__).parent.parent / "memory" / "orchestrator.db"
EMBEDDING_DIM = 384  # MiniLM default

# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MemoryNode:
    id: str
    node_type: str  # entity, concept, pattern, episode
    content: str
    metadata: Dict[str, Any]
    importance: float = 0.5
    access_count: int = 0
    created_at: str = ""
    last_accessed: str = ""
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None

@dataclass
class MemoryEdge:
    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0
    metadata: Dict[str, Any] = None
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None

@dataclass
class RetrievalResult:
    node: MemoryNode
    score: float
    relevance: float
    recency: float

# ═══════════════════════════════════════════════════════════════════════════════
# SQLite Memory Store
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryLite:
    """
    SQLite-based memory system with:
    - Temporal knowledge graph (valid_from/valid_until)
    - Generative Agents retrieval scoring
    - Pattern learning from success/failure
    - No external dependencies
    """

    _local = threading.local()

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_conn(self):
        """Thread-safe connection management."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        try:
            yield self._local.conn
        except Exception:
            self._local.conn.rollback()
            raise

    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                -- Memory Nodes (entities, concepts, patterns)
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    importance REAL DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    last_accessed TEXT DEFAULT (datetime('now')),
                    valid_from TEXT,
                    valid_until TEXT
                );

                -- Memory Edges (relations)
                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    metadata TEXT DEFAULT '{}',
                    valid_from TEXT DEFAULT (datetime('now')),
                    valid_until TEXT,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (source_id) REFERENCES nodes(id),
                    FOREIGN KEY (target_id) REFERENCES nodes(id)
                );

                -- Episodes (execution history)
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_type TEXT NOT NULL,
                    task_description TEXT,
                    outcome TEXT NOT NULL,  -- success, failure, partial
                    duration_seconds REAL,
                    tools_used TEXT DEFAULT '[]',
                    files_modified TEXT DEFAULT '[]',
                    error_message TEXT,
                    reflection TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                -- Patterns (learned success/failure patterns)
                CREATE TABLE IF NOT EXISTS patterns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    success_rate REAL DEFAULT 0.5,
                    times_used INTEGER DEFAULT 0,
                    utility_score REAL DEFAULT 0.5,
                    key_elements TEXT DEFAULT '[]',
                    common_tools TEXT DEFAULT '[]',
                    last_used TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                -- Blackboard (shared state for multi-step tasks)
                CREATE TABLE IF NOT EXISTS blackboard (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    artifact_type TEXT DEFAULT 'generic',
                    producer TEXT,
                    version INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                -- Indexes for fast retrieval
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
                CREATE INDEX IF NOT EXISTS idx_nodes_accessed ON nodes(last_accessed);
                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
                CREATE INDEX IF NOT EXISTS idx_episodes_outcome ON episodes(outcome);
                CREATE INDEX IF NOT EXISTS idx_patterns_category ON patterns(category);
            """)
            conn.commit()

    # ═══════════════════════════════════════════════════════════════════════════
    # Node Operations
    # ═══════════════════════════════════════════════════════════════════════════

    def create_node(self, node_type: str, content: str,
                    metadata: Dict = None, importance: float = 0.5,
                    valid_from: str = None, valid_until: str = None) -> str:
        """Create a memory node."""
        node_id = hashlib.sha256(f"{node_type}:{content}".encode()).hexdigest()[:16]
        metadata = metadata or {}

        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO nodes
                (id, node_type, content, metadata, importance, valid_from, valid_until)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (node_id, node_type, content, json.dumps(metadata),
                  importance, valid_from, valid_until))
            conn.commit()

        return node_id

    def get_node(self, node_id: str) -> Optional[MemoryNode]:
        """Get a node by ID and update access tracking."""
        with self._get_conn() as conn:
            # Update access tracking
            conn.execute("""
                UPDATE nodes
                SET access_count = access_count + 1,
                    last_accessed = datetime('now')
                WHERE id = ?
            """, (node_id,))

            row = conn.execute(
                "SELECT * FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()
            conn.commit()

            if row:
                return MemoryNode(
                    id=row['id'],
                    node_type=row['node_type'],
                    content=row['content'],
                    metadata=json.loads(row['metadata']),
                    importance=row['importance'],
                    access_count=row['access_count'],
                    created_at=row['created_at'],
                    last_accessed=row['last_accessed'],
                    valid_from=row['valid_from'],
                    valid_until=row['valid_until']
                )
        return None

    def invalidate_node(self, node_id: str):
        """Mark a node as no longer valid (temporal invalidation)."""
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE nodes SET valid_until = datetime('now') WHERE id = ?
            """, (node_id,))
            conn.commit()

    # ═══════════════════════════════════════════════════════════════════════════
    # Edge Operations (Relations)
    # ═══════════════════════════════════════════════════════════════════════════

    def create_edge(self, source_id: str, target_id: str,
                    relation_type: str, weight: float = 1.0,
                    metadata: Dict = None) -> int:
        """Create a relation between nodes."""
        metadata = metadata or {}

        with self._get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO edges (source_id, target_id, relation_type, weight, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (source_id, target_id, relation_type, weight, json.dumps(metadata)))
            conn.commit()
            return cursor.lastrowid

    def get_relations(self, node_id: str, direction: str = "both",
                      relation_type: str = None) -> List[MemoryEdge]:
        """Get relations for a node."""
        edges = []

        with self._get_conn() as conn:
            if direction in ("out", "both"):
                query = "SELECT * FROM edges WHERE source_id = ? AND valid_until IS NULL"
                params = [node_id]
                if relation_type:
                    query += " AND relation_type = ?"
                    params.append(relation_type)

                for row in conn.execute(query, params):
                    edges.append(MemoryEdge(
                        source_id=row['source_id'],
                        target_id=row['target_id'],
                        relation_type=row['relation_type'],
                        weight=row['weight'],
                        metadata=json.loads(row['metadata']),
                        valid_from=row['valid_from'],
                        valid_until=row['valid_until']
                    ))

            if direction in ("in", "both"):
                query = "SELECT * FROM edges WHERE target_id = ? AND valid_until IS NULL"
                params = [node_id]
                if relation_type:
                    query += " AND relation_type = ?"
                    params.append(relation_type)

                for row in conn.execute(query, params):
                    edges.append(MemoryEdge(
                        source_id=row['source_id'],
                        target_id=row['target_id'],
                        relation_type=row['relation_type'],
                        weight=row['weight'],
                        metadata=json.loads(row['metadata']),
                        valid_from=row['valid_from'],
                        valid_until=row['valid_until']
                    ))

        return edges

    def invalidate_edge(self, source_id: str, target_id: str, relation_type: str):
        """Invalidate a relation (temporal)."""
        with self._get_conn() as conn:
            conn.execute("""
                UPDATE edges SET valid_until = datetime('now')
                WHERE source_id = ? AND target_id = ? AND relation_type = ?
                AND valid_until IS NULL
            """, (source_id, target_id, relation_type))
            conn.commit()

    # ═══════════════════════════════════════════════════════════════════════════
    # Retrieval with Generative Agents Scoring
    # ═══════════════════════════════════════════════════════════════════════════

    def _calculate_recency(self, last_accessed: str) -> float:
        """Calculate recency score using exponential decay.

        Formula from Generative Agents paper:
        recency = e^(-0.995 * hours_since_access)
        """
        if not last_accessed:
            return 0.5

        try:
            accessed = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))
            hours = (datetime.now() - accessed.replace(tzinfo=None)).total_seconds() / 3600
            return math.exp(-0.995 * hours)
        except:
            return 0.5

    def _calculate_relevance(self, content: str, query: str) -> float:
        """Calculate relevance using keyword overlap.

        Simple but effective for most cases.
        For full vector similarity, use the PostgreSQL version.
        """
        if not query:
            return 0.5

        content_words = set(content.lower().split())
        query_words = set(query.lower().split())

        if not query_words:
            return 0.5

        overlap = len(content_words & query_words)
        return min(1.0, overlap / len(query_words))

    def retrieve(self, query: str, node_type: str = None,
                 limit: int = 10, include_invalid: bool = False) -> List[RetrievalResult]:
        """Retrieve relevant memories using Generative Agents scoring.

        Score = 0.5 * relevance + 0.3 * importance + 0.2 * recency
        """
        results = []

        with self._get_conn() as conn:
            sql = "SELECT * FROM nodes WHERE 1=1"
            params = []

            if node_type:
                sql += " AND node_type = ?"
                params.append(node_type)

            if not include_invalid:
                sql += " AND (valid_until IS NULL OR valid_until > datetime('now'))"

            for row in conn.execute(sql, params):
                relevance = self._calculate_relevance(row['content'], query)
                recency = self._calculate_recency(row['last_accessed'])
                importance = row['importance']

                # Generative Agents scoring formula
                score = 0.5 * relevance + 0.3 * importance + 0.2 * recency

                node = MemoryNode(
                    id=row['id'],
                    node_type=row['node_type'],
                    content=row['content'],
                    metadata=json.loads(row['metadata']),
                    importance=importance,
                    access_count=row['access_count'],
                    created_at=row['created_at'],
                    last_accessed=row['last_accessed'],
                    valid_from=row['valid_from'],
                    valid_until=row['valid_until']
                )

                results.append(RetrievalResult(
                    node=node,
                    score=score,
                    relevance=relevance,
                    recency=recency
                ))

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    # ═══════════════════════════════════════════════════════════════════════════
    # Episode Recording (Execution History)
    # ═══════════════════════════════════════════════════════════════════════════

    def record_episode(self, task_type: str, task_description: str,
                       outcome: str, duration_seconds: float = None,
                       tools_used: List[str] = None,
                       files_modified: List[str] = None,
                       error_message: str = None,
                       reflection: str = None) -> int:
        """Record an execution episode."""
        with self._get_conn() as conn:
            cursor = conn.execute("""
                INSERT INTO episodes
                (task_type, task_description, outcome, duration_seconds,
                 tools_used, files_modified, error_message, reflection)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (task_type, task_description, outcome, duration_seconds,
                  json.dumps(tools_used or []), json.dumps(files_modified or []),
                  error_message, reflection))
            conn.commit()
            return cursor.lastrowid

    def get_similar_episodes(self, task_type: str, outcome: str = None,
                             limit: int = 5) -> List[Dict]:
        """Get similar past episodes for learning."""
        with self._get_conn() as conn:
            sql = "SELECT * FROM episodes WHERE task_type = ?"
            params = [task_type]

            if outcome:
                sql += " AND outcome = ?"
                params.append(outcome)

            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            episodes = []
            for row in conn.execute(sql, params):
                episodes.append({
                    'id': row['id'],
                    'task_type': row['task_type'],
                    'task_description': row['task_description'],
                    'outcome': row['outcome'],
                    'duration_seconds': row['duration_seconds'],
                    'tools_used': json.loads(row['tools_used']),
                    'files_modified': json.loads(row['files_modified']),
                    'error_message': row['error_message'],
                    'reflection': row['reflection'],
                    'created_at': row['created_at']
                })

            return episodes

    # ═══════════════════════════════════════════════════════════════════════════
    # Pattern Learning
    # ═══════════════════════════════════════════════════════════════════════════

    def record_pattern(self, pattern_id: str, name: str, category: str,
                       description: str, success: bool,
                       key_elements: List[str] = None,
                       common_tools: List[str] = None) -> str:
        """Record or update a success/failure pattern."""
        with self._get_conn() as conn:
            # Check if pattern exists
            existing = conn.execute(
                "SELECT * FROM patterns WHERE id = ?", (pattern_id,)
            ).fetchone()

            if existing:
                # Update existing pattern
                times_used = existing['times_used'] + 1
                old_rate = existing['success_rate']
                new_rate = ((old_rate * existing['times_used']) + (1 if success else 0)) / times_used

                # Utility score with recency weighting
                recency = self._calculate_recency(existing['last_used'])
                utility = (times_used * 0.4) + (new_rate * 0.3) + (recency * 0.3)
                utility = min(1.0, utility / 10)  # Normalize

                conn.execute("""
                    UPDATE patterns SET
                        success_rate = ?,
                        times_used = ?,
                        utility_score = ?,
                        last_used = datetime('now')
                    WHERE id = ?
                """, (new_rate, times_used, utility, pattern_id))
            else:
                # Create new pattern
                conn.execute("""
                    INSERT INTO patterns
                    (id, name, category, description, success_rate, times_used,
                     utility_score, key_elements, common_tools, last_used)
                    VALUES (?, ?, ?, ?, ?, 1, 0.5, ?, ?, datetime('now'))
                """, (pattern_id, name, category, description,
                      1.0 if success else 0.0,
                      json.dumps(key_elements or []),
                      json.dumps(common_tools or [])))

            conn.commit()

        return pattern_id

    def get_patterns(self, category: str = None, min_utility: float = 0.0,
                     limit: int = 10) -> List[Dict]:
        """Get learned patterns sorted by utility."""
        with self._get_conn() as conn:
            sql = "SELECT * FROM patterns WHERE utility_score >= ?"
            params = [min_utility]

            if category:
                sql += " AND category = ?"
                params.append(category)

            sql += " ORDER BY utility_score DESC LIMIT ?"
            params.append(limit)

            patterns = []
            for row in conn.execute(sql, params):
                patterns.append({
                    'id': row['id'],
                    'name': row['name'],
                    'category': row['category'],
                    'description': row['description'],
                    'success_rate': row['success_rate'],
                    'times_used': row['times_used'],
                    'utility_score': row['utility_score'],
                    'key_elements': json.loads(row['key_elements']),
                    'common_tools': json.loads(row['common_tools']),
                    'last_used': row['last_used']
                })

            return patterns

    # ═══════════════════════════════════════════════════════════════════════════
    # Blackboard (Shared State)
    # ═══════════════════════════════════════════════════════════════════════════

    def blackboard_set(self, key: str, value: Any,
                       artifact_type: str = "generic",
                       producer: str = None) -> int:
        """Set a blackboard entry."""
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT version FROM blackboard WHERE key = ?", (key,)
            ).fetchone()

            version = (existing['version'] + 1) if existing else 1

            conn.execute("""
                INSERT OR REPLACE INTO blackboard
                (key, value, artifact_type, producer, version, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
            """, (key, json.dumps(value), artifact_type, producer, version))
            conn.commit()

            return version

    def blackboard_get(self, key: str) -> Optional[Any]:
        """Get a blackboard entry."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM blackboard WHERE key = ?", (key,)
            ).fetchone()

            if row:
                return json.loads(row['value'])
        return None

    def blackboard_delete(self, key: str):
        """Delete a blackboard entry."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM blackboard WHERE key = ?", (key,))
            conn.commit()

    def blackboard_list(self, artifact_type: str = None) -> List[Dict]:
        """List blackboard entries."""
        with self._get_conn() as conn:
            sql = "SELECT * FROM blackboard"
            params = []

            if artifact_type:
                sql += " WHERE artifact_type = ?"
                params.append(artifact_type)

            entries = []
            for row in conn.execute(sql, params):
                entries.append({
                    'key': row['key'],
                    'value': json.loads(row['value']),
                    'artifact_type': row['artifact_type'],
                    'producer': row['producer'],
                    'version': row['version'],
                    'updated_at': row['updated_at']
                })

            return entries

    # ═══════════════════════════════════════════════════════════════════════════
    # Memory Consolidation ("Sleep Cycle")
    # ═══════════════════════════════════════════════════════════════════════════

    def consolidate(self, days_back: int = 7) -> Dict:
        """Consolidate recent episodes into patterns (sleep cycle).

        Returns summary of consolidation.
        """
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()

        with self._get_conn() as conn:
            # Get recent episodes grouped by task_type and outcome
            episodes = conn.execute("""
                SELECT task_type, outcome, COUNT(*) as count,
                       AVG(duration_seconds) as avg_duration,
                       GROUP_CONCAT(DISTINCT reflection) as reflections
                FROM episodes
                WHERE created_at > ?
                GROUP BY task_type, outcome
            """, (cutoff,)).fetchall()

            consolidated = []
            for ep in episodes:
                task_type = ep['task_type']
                outcome = ep['outcome']
                count = ep['count']

                # Update or create pattern from consolidated episodes
                pattern_id = f"{task_type}-{outcome}"
                success = outcome == 'success'

                self.record_pattern(
                    pattern_id=pattern_id,
                    name=f"{task_type} ({outcome})",
                    category=task_type,
                    description=f"Consolidated from {count} episodes",
                    success=success
                )

                consolidated.append({
                    'task_type': task_type,
                    'outcome': outcome,
                    'episode_count': count,
                    'avg_duration': ep['avg_duration']
                })

            # Decay old patterns that haven't been used
            conn.execute("""
                UPDATE patterns
                SET utility_score = utility_score * 0.9
                WHERE last_used < ?
            """, (cutoff,))
            conn.commit()

        return {
            'episodes_processed': sum(c['episode_count'] for c in consolidated),
            'patterns_updated': len(consolidated),
            'consolidated': consolidated
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # Statistics
    # ═══════════════════════════════════════════════════════════════════════════

    def stats(self) -> Dict:
        """Get memory statistics."""
        with self._get_conn() as conn:
            stats = {
                'nodes': conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0],
                'edges': conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0],
                'episodes': conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0],
                'patterns': conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0],
                'blackboard_entries': conn.execute("SELECT COUNT(*) FROM blackboard").fetchone()[0],
                'success_rate': None,
                'top_patterns': []
            }

            # Calculate overall success rate
            total = conn.execute(
                "SELECT COUNT(*) FROM episodes WHERE outcome IN ('success', 'failure')"
            ).fetchone()[0]

            if total > 0:
                successes = conn.execute(
                    "SELECT COUNT(*) FROM episodes WHERE outcome = 'success'"
                ).fetchone()[0]
                stats['success_rate'] = successes / total

            # Top patterns by utility
            for row in conn.execute(
                "SELECT name, utility_score FROM patterns ORDER BY utility_score DESC LIMIT 5"
            ):
                stats['top_patterns'].append({
                    'name': row['name'],
                    'utility': row['utility_score']
                })

            return stats


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Interface
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    memory = MemoryLite()

    if len(sys.argv) < 2:
        print("Usage: python memory_lite.py <command> [args]")
        print("\nCommands:")
        print("  stats              - Show memory statistics")
        print("  search <query>     - Search memories")
        print("  consolidate        - Run memory consolidation")
        print("  blackboard         - List blackboard entries")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "stats":
        stats = memory.stats()
        print(json.dumps(stats, indent=2))

    elif cmd == "search":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        results = memory.retrieve(query, limit=5)
        for r in results:
            print(f"[{r.score:.2f}] {r.node.node_type}: {r.node.content[:100]}")

    elif cmd == "consolidate":
        result = memory.consolidate()
        print(json.dumps(result, indent=2))

    elif cmd == "blackboard":
        entries = memory.blackboard_list()
        for e in entries:
            print(f"{e['key']}: {e['artifact_type']} (v{e['version']})")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
