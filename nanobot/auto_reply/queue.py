"""
Message queue for GigaBot auto-reply.

Provides:
- Debounce for rapid messages
- Priority queue
- Rate limiting per sender
"""

import asyncio
import time
from typing import Any
from dataclasses import dataclass, field
from collections import defaultdict

from loguru import logger


@dataclass
class QueueConfig:
    """Configuration for message queue."""
    debounce_ms: int = 1000  # Wait time before processing
    max_queue_size: int = 100
    rate_limit_messages: int = 10  # Max messages per window
    rate_limit_window_seconds: int = 60
    priority_senders: list[str] = field(default_factory=list)


@dataclass
class QueuedMessage:
    """A message in the queue."""
    id: str
    sender_id: str
    chat_id: str
    content: str
    channel: str
    priority: int = 0  # Higher = more important
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other: "QueuedMessage") -> bool:
        """Compare by priority (higher first), then timestamp (older first)."""
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.timestamp < other.timestamp


class MessageQueue:
    """
    Priority queue for messages with debounce and rate limiting.
    
    Features:
    - Groups rapid messages from same sender
    - Priority handling for important senders
    - Rate limiting to prevent spam
    """
    
    def __init__(self, config: QueueConfig | None = None):
        self.config = config or QueueConfig()
        
        # Message queue (sorted by priority/timestamp)
        self._queue: asyncio.PriorityQueue[QueuedMessage] = asyncio.PriorityQueue(
            maxsize=self.config.max_queue_size
        )
        
        # Debounce tracking: sender_id -> (last_message, timer_task)
        self._debounce: dict[str, tuple[QueuedMessage, asyncio.Task]] = {}
        
        # Rate limiting: sender_id -> [timestamps]
        self._rate_limits: dict[str, list[float]] = defaultdict(list)
        
        # Stats
        self._total_received = 0
        self._total_dropped = 0
        self._total_processed = 0
    
    async def add(self, message: QueuedMessage) -> bool:
        """
        Add a message to the queue.
        
        Messages are debounced and rate-limited before being queued.
        
        Args:
            message: The message to add.
        
        Returns:
            True if added, False if dropped (rate limit/full).
        """
        self._total_received += 1
        
        # Check rate limit
        if not self._check_rate_limit(message.sender_id):
            logger.debug(f"Rate limit exceeded for {message.sender_id}")
            self._total_dropped += 1
            return False
        
        # Set priority for priority senders
        if message.sender_id in self.config.priority_senders:
            message.priority = 10
        
        # Check for existing debounce
        if message.sender_id in self._debounce:
            old_msg, timer_task = self._debounce[message.sender_id]
            
            # Cancel old timer
            if not timer_task.done():
                timer_task.cancel()
            
            # Combine messages
            combined_content = f"{old_msg.content}\n{message.content}"
            message.content = combined_content
            message.timestamp = old_msg.timestamp  # Keep original timestamp
        
        # Start debounce timer
        async def debounce_complete():
            await asyncio.sleep(self.config.debounce_ms / 1000)
            await self._queue_message(message)
            if message.sender_id in self._debounce:
                del self._debounce[message.sender_id]
        
        timer_task = asyncio.create_task(debounce_complete())
        self._debounce[message.sender_id] = (message, timer_task)
        
        return True
    
    async def _queue_message(self, message: QueuedMessage) -> None:
        """Actually add message to the queue."""
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("Message queue full, dropping oldest")
            self._total_dropped += 1
    
    async def get(self) -> QueuedMessage:
        """Get the next message from the queue."""
        message = await self._queue.get()
        self._total_processed += 1
        return message
    
    def get_nowait(self) -> QueuedMessage | None:
        """Get message without waiting."""
        try:
            message = self._queue.get_nowait()
            self._total_processed += 1
            return message
        except asyncio.QueueEmpty:
            return None
    
    def _check_rate_limit(self, sender_id: str) -> bool:
        """Check if sender is within rate limits."""
        now = time.time()
        cutoff = now - self.config.rate_limit_window_seconds
        
        # Clean old entries
        self._rate_limits[sender_id] = [
            ts for ts in self._rate_limits[sender_id]
            if ts > cutoff
        ]
        
        # Check limit
        if len(self._rate_limits[sender_id]) >= self.config.rate_limit_messages:
            return False
        
        # Record this message
        self._rate_limits[sender_id].append(now)
        return True
    
    def clear_sender(self, sender_id: str) -> None:
        """Clear rate limit for a sender."""
        if sender_id in self._rate_limits:
            del self._rate_limits[sender_id]
        
        if sender_id in self._debounce:
            _, timer = self._debounce[sender_id]
            if not timer.done():
                timer.cancel()
            del self._debounce[sender_id]
    
    @property
    def size(self) -> int:
        """Current queue size."""
        return self._queue.qsize()
    
    @property
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()
    
    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        return {
            "queue_size": self.size,
            "total_received": self._total_received,
            "total_dropped": self._total_dropped,
            "total_processed": self._total_processed,
            "pending_debounce": len(self._debounce),
            "rate_limited_senders": len(self._rate_limits),
        }
