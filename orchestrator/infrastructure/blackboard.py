"""
Redis-based Blackboard for Multi-Agent Coordination.

Implements the LbMAS (Language-based Multi-Agent System) pattern for O(1) context sharing
between agents. Provides distributed coordination primitives including artifact storage,
pub/sub event streaming, distributed locking, and pipeline state management.

Key Features:
- O(1) artifact read/write operations
- Reactive event streaming via Redis pub/sub
- Distributed locking to prevent agent collisions
- Audit trail via Redis streams
- Pipeline state tracking for orchestration
- Connection pooling and automatic retry logic
"""

import redis
import json
import time
import logging
from typing import Optional, Dict, Any, Generator, List
from dataclasses import dataclass, asdict
from enum import Enum
from contextlib import contextmanager
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ArtifactType(Enum):
    """Types of artifacts that can be stored on the blackboard."""
    PLAN = "plan"
    CODE = "code"
    TEST_RESULT = "test_result"
    REVIEW = "review"
    ERROR = "error"
    CONTEXT = "context"
    METADATA = "metadata"
    DECISION = "decision"


@dataclass
class BlackboardEvent:
    """Event emitted when blackboard state changes."""
    key: str
    action: str
    timestamp: float
    data: Optional[Dict] = None

    def to_dict(self) -> dict:
        """Convert event to dictionary representation."""
        return asdict(self)


class BlackboardError(Exception):
    """Base exception for blackboard operations."""
    pass


class LockAcquisitionError(BlackboardError):
    """Raised when unable to acquire a distributed lock."""
    pass


class ConnectionError(BlackboardError):
    """Raised when Redis connection fails."""
    pass


def retry_on_failure(max_retries: int = 3, delay: float = 0.5):
    """
    Decorator to retry Redis operations on transient failures.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (redis.ConnectionError, redis.TimeoutError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Redis operation failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(f"Redis operation failed after {max_retries} attempts")
            raise ConnectionError(f"Failed after {max_retries} retries") from last_exception
        return wrapper
    return decorator


class Blackboard:
    """
    Redis-based Blackboard for multi-agent coordination.

    Implements the LbMAS pattern for O(1) context sharing between agents.
    Agents can write artifacts, acquire locks, watch for updates, and track
    pipeline execution state.

    Architecture:
    - Artifacts: Stored as JSON in Redis keys (O(1) access)
    - Events: Published via Redis pub/sub for reactive agents
    - Audit: Logged to Redis stream for debugging and replay
    - Locks: Distributed locks using Redis SET NX with timeouts
    - Pipeline: Hash-based state tracking for orchestration

    Example:
        bb = Blackboard(host='localhost', port=6379)
        bb.write_artifact('agent:1:plan', {'steps': [...]}, ArtifactType.PLAN)

        with bb.lock('resource:1'):
            artifact = bb.read_artifact('resource:1')
            # ... modify artifact ...
            bb.write_artifact('resource:1', artifact, ArtifactType.CODE)
    """

    # Redis key prefixes
    ARTIFACT_PREFIX = "bb:artifact:"
    LOCK_PREFIX = "bb:lock:"
    PIPELINE_PREFIX = "bb:pipeline:"
    EVENT_CHANNEL = "bb:events"
    AUDIT_STREAM = "bb:audit"

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        max_connections: int = 50,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
    ):
        """
        Initialize Blackboard with Redis connection pool.

        Args:
            host: Redis host address
            port: Redis port number
            db: Redis database number
            password: Optional Redis password
            max_connections: Maximum connections in pool
            socket_timeout: Socket timeout in seconds
            socket_connect_timeout: Connection timeout in seconds
        """
        self.pool = redis.ConnectionPool(
            host=host,
            port=port,
            db=db,
            password=password,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            decode_responses=True,  # Auto-decode bytes to strings
        )
        self.redis = redis.Redis(connection_pool=self.pool)
        self._pubsub = None

        # Test connection
        try:
            self.redis.ping()
            logger.info(f"Connected to Redis at {host}:{port} (db={db})")
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise ConnectionError(f"Cannot connect to Redis at {host}:{port}") from e

    def _make_artifact_key(self, key: str) -> str:
        """Generate full Redis key for artifact."""
        return f"{self.ARTIFACT_PREFIX}{key}"

    def _make_lock_key(self, resource_id: str) -> str:
        """Generate full Redis key for lock."""
        return f"{self.LOCK_PREFIX}{resource_id}"

    def _make_pipeline_key(self, run_id: str) -> str:
        """Generate full Redis key for pipeline state."""
        return f"{self.PIPELINE_PREFIX}{run_id}"

    @retry_on_failure(max_retries=3)
    def write_artifact(
        self,
        key: str,
        value: dict,
        artifact_type: ArtifactType,
        ttl: int = 3600,
        notify: bool = True
    ) -> bool:
        """
        Write structured artifact to blackboard.

        Stores artifact as JSON with metadata, publishes update event for reactive
        agents, and logs to audit stream for debugging.

        Args:
            key: Unique artifact identifier
            value: Artifact data (must be JSON-serializable)
            artifact_type: Type classification for the artifact
            ttl: Time-to-live in seconds (0 = no expiration)
            notify: Whether to publish event notification

        Returns:
            True if write succeeded, False otherwise

        Raises:
            BlackboardError: If serialization or write fails
        """
        try:
            # Wrap artifact with metadata
            artifact = {
                'type': artifact_type.value,
                'data': value,
                'timestamp': time.time(),
                'version': 1,  # For future optimistic locking
            }

            # Serialize to JSON
            artifact_json = json.dumps(artifact)

            # Write to Redis
            redis_key = self._make_artifact_key(key)
            self.redis.set(redis_key, artifact_json)

            # Set TTL if specified
            if ttl > 0:
                self.redis.expire(redis_key, ttl)

            # Publish event for reactive agents
            if notify:
                event = BlackboardEvent(
                    key=key,
                    action='write',
                    timestamp=time.time(),
                    data={'type': artifact_type.value}
                )
                self.redis.publish(self.EVENT_CHANNEL, json.dumps(event.to_dict()))

            # Log to audit stream
            self.redis.xadd(
                self.AUDIT_STREAM,
                {
                    'action': 'write',
                    'key': key,
                    'type': artifact_type.value,
                    'timestamp': str(time.time()),
                },
                maxlen=10000  # Keep last 10k events
            )

            logger.debug(f"Wrote artifact: {key} (type={artifact_type.value})")
            return True

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to serialize artifact {key}: {e}")
            raise BlackboardError(f"Cannot serialize artifact: {e}") from e
        except redis.RedisError as e:
            logger.error(f"Redis error writing artifact {key}: {e}")
            raise BlackboardError(f"Failed to write artifact: {e}") from e

    @retry_on_failure(max_retries=3)
    def read_artifact(self, key: str) -> Optional[dict]:
        """
        Read artifact by key.

        Args:
            key: Artifact identifier

        Returns:
            Artifact data dictionary if found, None otherwise

        Raises:
            BlackboardError: If deserialization fails
        """
        try:
            redis_key = self._make_artifact_key(key)
            artifact_json = self.redis.get(redis_key)

            if artifact_json is None:
                logger.debug(f"Artifact not found: {key}")
                return None

            artifact = json.loads(artifact_json)
            logger.debug(f"Read artifact: {key} (type={artifact.get('type')})")
            return artifact

        except json.JSONDecodeError as e:
            logger.error(f"Failed to deserialize artifact {key}: {e}")
            raise BlackboardError(f"Corrupted artifact data: {e}") from e
        except redis.RedisError as e:
            logger.error(f"Redis error reading artifact {key}: {e}")
            raise BlackboardError(f"Failed to read artifact: {e}") from e

    @retry_on_failure(max_retries=3)
    def delete_artifact(self, key: str) -> bool:
        """
        Delete artifact from blackboard.

        Args:
            key: Artifact identifier

        Returns:
            True if artifact was deleted, False if not found
        """
        try:
            redis_key = self._make_artifact_key(key)
            result = self.redis.delete(redis_key)

            if result:
                # Publish deletion event
                event = BlackboardEvent(
                    key=key,
                    action='delete',
                    timestamp=time.time()
                )
                self.redis.publish(self.EVENT_CHANNEL, json.dumps(event.to_dict()))

                # Log to audit stream
                self.redis.xadd(
                    self.AUDIT_STREAM,
                    {
                        'action': 'delete',
                        'key': key,
                        'timestamp': str(time.time()),
                    },
                    maxlen=10000
                )
                logger.debug(f"Deleted artifact: {key}")

            return bool(result)

        except redis.RedisError as e:
            logger.error(f"Redis error deleting artifact {key}: {e}")
            raise BlackboardError(f"Failed to delete artifact: {e}") from e

    @retry_on_failure(max_retries=3)
    def list_artifacts(self, pattern: str = '*') -> List[str]:
        """
        List all artifact keys matching pattern.

        Args:
            pattern: Redis key pattern (e.g., 'agent:*', 'code:*')

        Returns:
            List of artifact keys (without prefix)
        """
        try:
            full_pattern = self._make_artifact_key(pattern)
            keys = self.redis.keys(full_pattern)

            # Strip prefix from keys
            prefix_len = len(self.ARTIFACT_PREFIX)
            return [key[prefix_len:] for key in keys]

        except redis.RedisError as e:
            logger.error(f"Redis error listing artifacts: {e}")
            raise BlackboardError(f"Failed to list artifacts: {e}") from e

    @retry_on_failure(max_retries=3)
    def acquire_lock(
        self,
        resource_id: str,
        timeout_ms: int = 5000,
        blocking: bool = False,
        blocking_timeout: float = 10.0
    ) -> bool:
        """
        Acquire distributed lock to prevent agent collision.

        Uses Redis SET NX (set if not exists) with automatic expiration to prevent
        deadlocks. Locks are automatically released after timeout_ms milliseconds.

        Args:
            resource_id: Unique resource identifier to lock
            timeout_ms: Lock timeout in milliseconds (auto-release)
            blocking: If True, wait for lock to become available
            blocking_timeout: Maximum time to wait for lock in seconds

        Returns:
            True if lock acquired, False if already locked

        Raises:
            LockAcquisitionError: If blocking and timeout expires
        """
        try:
            lock_key = self._make_lock_key(resource_id)
            timeout_sec = timeout_ms / 1000.0

            if blocking:
                # Poll for lock with exponential backoff
                start_time = time.time()
                wait_time = 0.01  # Start with 10ms

                while True:
                    # Try to acquire lock
                    acquired = self.redis.set(
                        lock_key,
                        '1',
                        nx=True,  # Only set if not exists
                        px=timeout_ms  # Expiration in milliseconds
                    )

                    if acquired:
                        logger.debug(f"Acquired lock: {resource_id}")
                        return True

                    # Check if we've exceeded blocking timeout
                    elapsed = time.time() - start_time
                    if elapsed >= blocking_timeout:
                        raise LockAcquisitionError(
                            f"Failed to acquire lock on {resource_id} within {blocking_timeout}s"
                        )

                    # Wait before retry (exponential backoff, max 1s)
                    time.sleep(min(wait_time, 1.0))
                    wait_time *= 2
            else:
                # Non-blocking: single attempt
                acquired = self.redis.set(
                    lock_key,
                    '1',
                    nx=True,
                    px=timeout_ms
                )

                if acquired:
                    logger.debug(f"Acquired lock: {resource_id}")
                else:
                    logger.debug(f"Lock already held: {resource_id}")

                return bool(acquired)

        except redis.RedisError as e:
            logger.error(f"Redis error acquiring lock on {resource_id}: {e}")
            raise BlackboardError(f"Failed to acquire lock: {e}") from e

    @retry_on_failure(max_retries=3)
    def release_lock(self, resource_id: str) -> bool:
        """
        Release a previously acquired lock.

        Args:
            resource_id: Resource identifier to unlock

        Returns:
            True if lock was released, False if no lock existed
        """
        try:
            lock_key = self._make_lock_key(resource_id)
            result = self.redis.delete(lock_key)

            if result:
                logger.debug(f"Released lock: {resource_id}")
            else:
                logger.debug(f"No lock to release: {resource_id}")

            return bool(result)

        except redis.RedisError as e:
            logger.error(f"Redis error releasing lock on {resource_id}: {e}")
            raise BlackboardError(f"Failed to release lock: {e}") from e

    @contextmanager
    def lock(
        self,
        resource_id: str,
        timeout_ms: int = 5000,
        blocking: bool = True,
        blocking_timeout: float = 10.0
    ):
        """
        Context manager for distributed locking.

        Automatically acquires lock on entry and releases on exit.

        Example:
            with bb.lock('resource:1'):
                # Critical section - only one agent can execute this
                artifact = bb.read_artifact('resource:1')
                artifact['data']['modified'] = True
                bb.write_artifact('resource:1', artifact['data'], ArtifactType.CODE)

        Args:
            resource_id: Resource to lock
            timeout_ms: Lock timeout in milliseconds
            blocking: If True, wait for lock
            blocking_timeout: Maximum wait time in seconds

        Raises:
            LockAcquisitionError: If lock cannot be acquired
        """
        acquired = self.acquire_lock(
            resource_id,
            timeout_ms=timeout_ms,
            blocking=blocking,
            blocking_timeout=blocking_timeout
        )

        if not acquired:
            raise LockAcquisitionError(f"Could not acquire lock on {resource_id}")

        try:
            yield
        finally:
            self.release_lock(resource_id)

    def watch(self, pattern: str = '*') -> Generator[BlackboardEvent, None, None]:
        """
        Generator yielding updates for reactive agents.

        Agents subscribe to specific patterns to receive real-time notifications
        of blackboard changes. This enables event-driven agent coordination.

        Args:
            pattern: Key pattern to watch (e.g., 'agent:*', 'code:*')

        Yields:
            BlackboardEvent objects as they occur

        Example:
            for event in bb.watch('agent:*'):
                print(f"Agent artifact changed: {event.key}")
                if event.action == 'write':
                    artifact = bb.read_artifact(event.key)
                    # React to change...
        """
        try:
            # Create new pubsub connection
            pubsub = self.redis.pubsub()
            pubsub.subscribe(self.EVENT_CHANNEL)

            logger.info(f"Watching blackboard events (pattern={pattern})")

            # Skip subscription confirmation message
            for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        event_data = json.loads(message['data'])
                        event = BlackboardEvent(**event_data)

                        # Filter by pattern (simple glob matching)
                        if self._matches_pattern(event.key, pattern):
                            yield event

                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Invalid event data: {e}")
                        continue

        except redis.RedisError as e:
            logger.error(f"Redis error in watch: {e}")
            raise BlackboardError(f"Watch failed: {e}") from e
        finally:
            if pubsub:
                pubsub.close()

    def _matches_pattern(self, key: str, pattern: str) -> bool:
        """Simple glob pattern matching for key filtering."""
        if pattern == '*':
            return True

        # Convert glob pattern to basic matching
        if '*' in pattern:
            prefix = pattern.split('*')[0]
            return key.startswith(prefix)

        return key == pattern

    @retry_on_failure(max_retries=3)
    def get_history(self, limit: int = 100) -> List[dict]:
        """
        Get recent blackboard history from audit stream.

        Useful for debugging, replay, and understanding system behavior.

        Args:
            limit: Maximum number of events to retrieve

        Returns:
            List of audit events (newest first)
        """
        try:
            # Read from stream (newest first)
            entries = self.redis.xrevrange(self.AUDIT_STREAM, count=limit)

            history = []
            for entry_id, data in entries:
                history.append({
                    'id': entry_id,
                    'action': data.get('action'),
                    'key': data.get('key'),
                    'type': data.get('type'),
                    'timestamp': float(data.get('timestamp', 0)),
                })

            logger.debug(f"Retrieved {len(history)} history events")
            return history

        except redis.RedisError as e:
            logger.error(f"Redis error reading history: {e}")
            raise BlackboardError(f"Failed to read history: {e}") from e

    @retry_on_failure(max_retries=3)
    def set_pipeline_state(
        self,
        run_id: str,
        step: int,
        status: str,
        data: Optional[dict] = None
    ) -> None:
        """
        Track pipeline execution state.

        Used by orchestrator to coordinate multi-step agent workflows.
        Stores current step, status, and optional metadata.

        Args:
            run_id: Unique pipeline run identifier
            step: Current step number
            status: Step status (e.g., 'running', 'completed', 'failed')
            data: Optional metadata about the step
        """
        try:
            pipeline_key = self._make_pipeline_key(run_id)

            state = {
                'step': str(step),
                'status': status,
                'updated_at': str(time.time()),
            }

            if data:
                state['data'] = json.dumps(data)

            # Store as Redis hash for efficient partial updates
            self.redis.hset(pipeline_key, mapping=state)

            # Set TTL to clean up old pipeline states
            self.redis.expire(pipeline_key, 86400)  # 24 hours

            logger.debug(f"Updated pipeline state: {run_id} step={step} status={status}")

        except redis.RedisError as e:
            logger.error(f"Redis error setting pipeline state: {e}")
            raise BlackboardError(f"Failed to set pipeline state: {e}") from e

    @retry_on_failure(max_retries=3)
    def get_pipeline_state(self, run_id: str) -> Optional[dict]:
        """
        Get current pipeline state.

        Args:
            run_id: Pipeline run identifier

        Returns:
            Pipeline state dictionary or None if not found
        """
        try:
            pipeline_key = self._make_pipeline_key(run_id)
            state = self.redis.hgetall(pipeline_key)

            if not state:
                return None

            # Parse stored data
            result = {
                'step': int(state.get('step', 0)),
                'status': state.get('status'),
                'updated_at': float(state.get('updated_at', 0)),
            }

            if 'data' in state:
                try:
                    result['data'] = json.loads(state['data'])
                except json.JSONDecodeError:
                    result['data'] = None

            return result

        except redis.RedisError as e:
            logger.error(f"Redis error getting pipeline state: {e}")
            raise BlackboardError(f"Failed to get pipeline state: {e}") from e

    @retry_on_failure(max_retries=3)
    def clear_pipeline_state(self, run_id: str) -> bool:
        """
        Clear pipeline state (useful for cleanup).

        Args:
            run_id: Pipeline run identifier

        Returns:
            True if state was cleared, False if not found
        """
        try:
            pipeline_key = self._make_pipeline_key(run_id)
            result = self.redis.delete(pipeline_key)
            return bool(result)

        except redis.RedisError as e:
            logger.error(f"Redis error clearing pipeline state: {e}")
            raise BlackboardError(f"Failed to clear pipeline state: {e}") from e

    def health_check(self) -> dict:
        """
        Check Redis connection health and get basic stats.

        Returns:
            Dictionary with health status and statistics
        """
        try:
            # Ping Redis
            self.redis.ping()

            # Get basic stats
            info = self.redis.info('stats')

            return {
                'status': 'healthy',
                'connected': True,
                'total_commands_processed': info.get('total_commands_processed', 0),
                'instantaneous_ops_per_sec': info.get('instantaneous_ops_per_sec', 0),
            }

        except redis.RedisError as e:
            logger.error(f"Health check failed: {e}")
            return {
                'status': 'unhealthy',
                'connected': False,
                'error': str(e),
            }

    def close(self):
        """Close Redis connection pool."""
        if self._pubsub:
            self._pubsub.close()
        self.pool.disconnect()
        logger.info("Closed Redis connection pool")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_basic_usage():
    """Example: Basic artifact read/write."""
    print("\n=== Example 1: Basic Artifact Usage ===")

    with Blackboard() as bb:
        # Write a code artifact
        code_data = {
            'file': '/path/to/file.py',
            'content': 'def hello(): return "world"',
            'language': 'python',
        }
        bb.write_artifact('agent:1:code', code_data, ArtifactType.CODE)

        # Read it back
        artifact = bb.read_artifact('agent:1:code')
        print(f"Artifact type: {artifact['type']}")
        print(f"Artifact data: {artifact['data']}")

        # List all artifacts
        all_artifacts = bb.list_artifacts()
        print(f"Total artifacts: {len(all_artifacts)}")


def example_distributed_locking():
    """Example: Using distributed locks to prevent race conditions."""
    print("\n=== Example 2: Distributed Locking ===")

    with Blackboard() as bb:
        # Initialize shared resource
        bb.write_artifact('shared:counter', {'count': 0}, ArtifactType.CONTEXT)

        # Agent 1: Increment counter (with lock)
        with bb.lock('shared:counter', blocking=True):
            artifact = bb.read_artifact('shared:counter')
            artifact['data']['count'] += 1
            bb.write_artifact('shared:counter', artifact['data'], ArtifactType.CONTEXT)
            print(f"Agent 1 incremented counter to {artifact['data']['count']}")

        # Agent 2: Increment counter (with lock)
        with bb.lock('shared:counter', blocking=True):
            artifact = bb.read_artifact('shared:counter')
            artifact['data']['count'] += 1
            bb.write_artifact('shared:counter', artifact['data'], ArtifactType.CONTEXT)
            print(f"Agent 2 incremented counter to {artifact['data']['count']}")

        # Final value
        final = bb.read_artifact('shared:counter')
        print(f"Final counter value: {final['data']['count']}")


def example_reactive_watching():
    """Example: Watching for updates (run in separate process/thread)."""
    print("\n=== Example 3: Reactive Event Watching ===")
    print("Note: This is a simplified example. In production, run watch() in separate thread/process.")

    import threading

    def watcher_agent():
        """Agent that reacts to blackboard changes."""
        with Blackboard() as bb:
            print("Watcher: Started watching for agent:* updates...")

            # In production, this would run indefinitely
            # Here we just process a few events for demo
            event_count = 0
            for event in bb.watch('agent:*'):
                print(f"Watcher: Detected {event.action} on {event.key}")
                if event.action == 'write':
                    artifact = bb.read_artifact(event.key)
                    print(f"Watcher: New artifact type = {artifact['type']}")

                event_count += 1
                if event_count >= 2:  # Stop after 2 events for demo
                    break

    # Start watcher in background
    watcher_thread = threading.Thread(target=watcher_agent, daemon=True)
    watcher_thread.start()

    # Give watcher time to subscribe
    time.sleep(0.5)

    # Write some artifacts to trigger events
    with Blackboard() as bb:
        bb.write_artifact('agent:2:plan', {'steps': ['a', 'b', 'c']}, ArtifactType.PLAN)
        bb.write_artifact('agent:3:test', {'passed': True}, ArtifactType.TEST_RESULT)

    # Wait for watcher to process
    time.sleep(0.5)


def example_pipeline_orchestration():
    """Example: Pipeline state tracking for orchestration."""
    print("\n=== Example 4: Pipeline State Tracking ===")

    with Blackboard() as bb:
        run_id = f"run_{int(time.time())}"

        # Step 1: Planning
        bb.set_pipeline_state(run_id, step=1, status='running', data={'phase': 'planning'})
        print(f"Pipeline {run_id}: Step 1 (planning) started")
        time.sleep(0.1)

        bb.set_pipeline_state(run_id, step=1, status='completed', data={'phase': 'planning'})
        print(f"Pipeline {run_id}: Step 1 (planning) completed")

        # Step 2: Implementation
        bb.set_pipeline_state(run_id, step=2, status='running', data={'phase': 'implementation'})
        print(f"Pipeline {run_id}: Step 2 (implementation) started")
        time.sleep(0.1)

        bb.set_pipeline_state(run_id, step=2, status='completed', data={'phase': 'implementation'})
        print(f"Pipeline {run_id}: Step 2 (implementation) completed")

        # Check final state
        state = bb.get_pipeline_state(run_id)
        print(f"Final pipeline state: step={state['step']}, status={state['status']}")

        # Cleanup
        bb.clear_pipeline_state(run_id)


def example_audit_history():
    """Example: Viewing audit history."""
    print("\n=== Example 5: Audit History ===")

    with Blackboard() as bb:
        # Perform some operations
        bb.write_artifact('test:1', {'value': 1}, ArtifactType.CONTEXT)
        bb.write_artifact('test:2', {'value': 2}, ArtifactType.CONTEXT)
        bb.delete_artifact('test:1')

        # View history
        history = bb.get_history(limit=5)
        print("\nRecent blackboard activity:")
        for entry in history:
            print(f"  {entry['action']:8s} {entry['key']:20s} at {entry['timestamp']:.2f}")


def example_error_handling():
    """Example: Error handling and health checks."""
    print("\n=== Example 6: Error Handling & Health ===")

    with Blackboard() as bb:
        # Health check
        health = bb.health_check()
        print(f"Redis health: {health['status']}")
        print(f"Operations/sec: {health.get('instantaneous_ops_per_sec', 0)}")

        # Try to acquire already-locked resource (non-blocking)
        bb.acquire_lock('resource:test', timeout_ms=1000)
        can_acquire = bb.acquire_lock('resource:test', timeout_ms=1000, blocking=False)
        print(f"Can acquire already-locked resource: {can_acquire}")
        bb.release_lock('resource:test')

        # Try blocking lock with timeout
        try:
            bb.acquire_lock('resource:test', timeout_ms=1000)
            # This will timeout after 1 second
            bb.acquire_lock('resource:test', timeout_ms=1000, blocking=True, blocking_timeout=1.0)
        except LockAcquisitionError as e:
            print(f"Lock acquisition timed out as expected: {e}")
        finally:
            bb.release_lock('resource:test')


if __name__ == '__main__':
    """
    Run all examples to demonstrate Blackboard capabilities.

    Prerequisites:
        - Redis server running on localhost:6379
        - Install: pip install redis

    Start Redis:
        docker run -d -p 6379:6379 redis:latest
        # or
        redis-server
    """
    print("=" * 70)
    print("Redis Blackboard for Multi-Agent Coordination")
    print("=" * 70)

    try:
        # Run examples
        example_basic_usage()
        example_distributed_locking()
        example_reactive_watching()
        example_pipeline_orchestration()
        example_audit_history()
        example_error_handling()

        print("\n" + "=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)

    except ConnectionError as e:
        print(f"\nError: Could not connect to Redis. {e}")
        print("\nPlease ensure Redis is running:")
        print("  docker run -d -p 6379:6379 redis:latest")
        print("  # or")
        print("  redis-server")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
