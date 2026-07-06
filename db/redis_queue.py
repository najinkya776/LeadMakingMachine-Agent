"""Redis queue management for job processing."""

import json
import redis
from typing import Optional, List, Any
from datetime import datetime

from config.database import REDIS_CONFIG, QUEUES


class RedisQueue:
    """Redis-based queue for lead processing."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        password: Optional[str] = None,
    ):
        """Initialize Redis connection."""
        self.client = redis.Redis(
            host=host or REDIS_CONFIG["host"],
            port=port or REDIS_CONFIG["port"],
            db=db or REDIS_CONFIG["db"],
            password=password or REDIS_CONFIG["password"],
            decode_responses=True,
        )

    def ping(self) -> bool:
        """Test Redis connection."""
        try:
            return self.client.ping()
        except redis.ConnectionError:
            return False

    # -------------------------------------------------------------------------
    # Queue Operations
    # -------------------------------------------------------------------------

    def enqueue(self, queue_name: str, data: dict) -> int:
        """Add item to queue."""
        return self.client.rpush(queue_name, json.dumps(data))

    def dequeue(self, queue_name: str, timeout: int = 0) -> Optional[dict]:
        """Remove and return item from queue. Blocks if empty."""
        result = self.client.blpop(queue_name, timeout=timeout)
        if result:
            return json.loads(result[1])
        return None

    def peek(self, queue_name: str, count: int = 10) -> List[dict]:
        """View items without removing them."""
        items = self.client.lrange(queue_name, 0, count - 1)
        return [json.loads(item) for item in items]

    def get_length(self, queue_name: str) -> int:
        """Get queue length."""
        return self.client.llen(queue_name)

    def clear_queue(self, queue_name: str) -> int:
        """Clear all items from queue."""
        length = self.get_length(queue_name)
        self.client.delete(queue_name)
        return length

    # -------------------------------------------------------------------------
    # Lead Queue Specific Operations
    # -------------------------------------------------------------------------

    def add_raw_lead(self, lead_data: dict) -> int:
        """Add a raw lead to the processing queue."""
        lead_data["queued_at"] = datetime.utcnow().isoformat()
        return self.enqueue(QUEUES["raw"], lead_data)

    def get_next_lead(self, timeout: int = 5) -> Optional[dict]:
        """Get next lead from raw queue."""
        return self.dequeue(QUEUES["raw"], timeout=timeout)

    def move_to_qualified(self, lead_data: dict) -> int:
        """Move lead to qualified queue."""
        lead_data["qualified_at"] = datetime.utcnow().isoformat()
        return self.enqueue(QUEUES["qualified"], lead_data)

    def move_to_auditing(self, lead_data: dict) -> int:
        """Move lead to auditing queue."""
        lead_data["auditing_started_at"] = datetime.utcnow().isoformat()
        return self.enqueue(QUEUES["auditing"], lead_data)

    def move_to_scored(self, lead_data: dict) -> int:
        """Move lead to scored queue."""
        lead_data["scored_at"] = datetime.utcnow().isoformat()
        return self.enqueue(QUEUES["scored"], lead_data)

    def move_to_completed(self, lead_data: dict) -> int:
        """Mark lead as completed."""
        lead_data["completed_at"] = datetime.utcnow().isoformat()
        return self.enqueue(QUEUES["completed"], lead_data)

    def move_to_failed(self, lead_data: dict, error: str) -> int:
        """Mark lead as failed with error message."""
        lead_data["failed_at"] = datetime.utcnow().isoformat()
        lead_data["error"] = error
        return self.enqueue(QUEUES["failed"], lead_data)

    # -------------------------------------------------------------------------
    # Batch Operations
    # -------------------------------------------------------------------------

    def add_batch(self, queue_name: str, items: List[dict]) -> int:
        """Add multiple items to queue."""
        for item in items:
            self.enqueue(queue_name, item)
        return len(items)

    def get_batch(self, queue_name: str, count: int = 10) -> List[dict]:
        """Get multiple items from queue."""
        items = []
        for _ in range(count):
            item = self.dequeue(queue_name, timeout=1)
            if item:
                items.append(item)
            else:
                break
        return items

    # -------------------------------------------------------------------------
    # Status Tracking
    # -------------------------------------------------------------------------

    def set_status(self, key: str, status: str, ttl: int = 3600) -> bool:
        """Set processing status with TTL."""
        return self.client.setex(key, ttl, status)

    def get_status(self, key: str) -> Optional[str]:
        """Get processing status."""
        return self.client.get(key)

    def increment_counter(self, counter_name: str) -> int:
        """Increment a counter (for statistics)."""
        return self.client.incr(counter_name)

    def get_counter(self, counter_name: str) -> int:
        """Get counter value."""
        value = self.client.get(counter_name)
        return int(value) if value else 0

    def reset_counters(self) -> None:
        """Reset all counters."""
        self.client.delete("stats:scraped", "stats:qualified", "stats:audited", "stats:completed")

    # -------------------------------------------------------------------------
    # Queue Statistics
    # -------------------------------------------------------------------------

    def get_queue_stats(self) -> dict:
        """Get statistics for all queues."""
        stats = {}
        for name, queue_key in QUEUES.items():
            stats[name] = self.get_length(queue_key)
        return stats

    def get_pipeline_stats(self) -> dict:
        """Get overall pipeline statistics."""
        return {
            "raw": self.get_counter("stats:scraped"),
            "qualified": self.get_counter("stats:qualified"),
            "audited": self.get_counter("stats:audited"),
            "completed": self.get_counter("stats:completed"),
            "failed": self.get_length(QUEUES["failed"]),
        }


# Global instance
_queue_instance: Optional[RedisQueue] = None


def get_queue() -> RedisQueue:
    """Get or create global queue instance."""
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = RedisQueue()
    return _queue_instance