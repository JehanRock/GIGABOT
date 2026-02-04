"""
Response caching for GigaBot.

Provides LRU-based caching of LLM responses to reduce costs:
- Cache identical queries
- Track hit/miss statistics
- Automatic expiration
- Token savings tracking
"""

import hashlib
import json
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class CacheEntry:
    """A single cache entry."""
    query_hash: str
    query_preview: str  # First 100 chars for debugging
    response: str
    model_used: str
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0
    tokens_saved: int = 0  # Estimated tokens saved from hits
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query_hash": self.query_hash,
            "query_preview": self.query_preview,
            "response": self.response,
            "model_used": self.model_used,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "hit_count": self.hit_count,
            "tokens_saved": self.tokens_saved,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        return cls(
            query_hash=data["query_hash"],
            query_preview=data["query_preview"],
            response=data["response"],
            model_used=data["model_used"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            hit_count=data.get("hit_count", 0),
            tokens_saved=data.get("tokens_saved", 0),
        )
    
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        return datetime.now() > self.expires_at


@dataclass
class CacheStats:
    """Cache statistics."""
    total_entries: int = 0
    total_hits: int = 0
    total_misses: int = 0
    total_tokens_saved: int = 0
    total_evictions: int = 0
    oldest_entry: datetime | None = None
    newest_entry: datetime | None = None
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate percentage."""
        total = self.total_hits + self.total_misses
        if total == 0:
            return 0.0
        return self.total_hits / total
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_entries": self.total_entries,
            "total_hits": self.total_hits,
            "total_misses": self.total_misses,
            "hit_rate": f"{self.hit_rate:.1%}",
            "total_tokens_saved": self.total_tokens_saved,
            "total_evictions": self.total_evictions,
            "oldest_entry": self.oldest_entry.isoformat() if self.oldest_entry else None,
            "newest_entry": self.newest_entry.isoformat() if self.newest_entry else None,
        }


class ResponseCache:
    """
    LRU cache for LLM responses.
    
    Features:
    - LRU eviction when max size reached
    - Automatic expiration of old entries
    - Token savings tracking
    - Persistent storage option
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 3600,
        storage_path: Path | None = None,
    ):
        """
        Initialize the response cache.
        
        Args:
            max_size: Maximum number of entries to keep
            default_ttl: Default time-to-live in seconds
            storage_path: Optional path for persistent storage
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.storage_path = storage_path
        
        # LRU cache using OrderedDict
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # Statistics
        self._stats = CacheStats()
        
        # Load from storage if available
        if storage_path:
            self._load_from_storage()
    
    def _generate_key(self, query: str, model: str, system_prompt: str = "") -> str:
        """
        Generate a cache key from query components.
        
        Args:
            query: The user query
            model: Model being used
            system_prompt: Optional system prompt
            
        Returns:
            Hash string for cache lookup
        """
        # Normalize query (lowercase, strip whitespace)
        normalized = query.strip().lower()
        
        # Combine components
        key_material = f"{model}:{normalized}:{system_prompt}"
        
        # Generate hash
        return hashlib.sha256(key_material.encode()).hexdigest()[:32]
    
    def get(
        self,
        query: str,
        model: str,
        system_prompt: str = ""
    ) -> str | None:
        """
        Get a cached response if available.
        
        Args:
            query: The user query
            model: Model being used
            system_prompt: Optional system prompt
            
        Returns:
            Cached response or None if not found/expired
        """
        key = self._generate_key(query, model, system_prompt)
        
        if key not in self._cache:
            self._stats.total_misses += 1
            return None
        
        entry = self._cache[key]
        
        # Check expiration
        if entry.is_expired():
            self._cache.pop(key)
            self._stats.total_misses += 1
            return None
        
        # Move to end (most recently used)
        self._cache.move_to_end(key)
        
        # Update stats
        entry.hit_count += 1
        estimated_tokens = len(entry.response) // 4  # Rough estimate
        entry.tokens_saved += estimated_tokens
        self._stats.total_hits += 1
        self._stats.total_tokens_saved += estimated_tokens
        
        return entry.response
    
    def set(
        self,
        query: str,
        response: str,
        model: str,
        system_prompt: str = "",
        ttl: int | None = None
    ) -> None:
        """
        Cache a response.
        
        Args:
            query: The user query
            response: The LLM response
            model: Model that generated the response
            system_prompt: Optional system prompt
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        key = self._generate_key(query, model, system_prompt)
        ttl = ttl or self.default_ttl
        
        now = datetime.now()
        expires = now + timedelta(seconds=ttl)
        
        # Create entry
        entry = CacheEntry(
            query_hash=key,
            query_preview=query[:100],
            response=response,
            model_used=model,
            created_at=now,
            expires_at=expires,
        )
        
        # Check if we need to evict
        if len(self._cache) >= self.max_size:
            self._evict_oldest()
        
        # Add to cache
        self._cache[key] = entry
        self._cache.move_to_end(key)
        
        # Update stats
        self._update_time_stats()
        
        # Save to storage
        if self.storage_path:
            self._save_to_storage()
    
    def _evict_oldest(self) -> None:
        """Evict the oldest (least recently used) entry."""
        if self._cache:
            self._cache.popitem(last=False)
            self._stats.total_evictions += 1
    
    def _update_time_stats(self) -> None:
        """Update oldest/newest entry timestamps."""
        if not self._cache:
            self._stats.oldest_entry = None
            self._stats.newest_entry = None
            return
        
        entries = list(self._cache.values())
        self._stats.oldest_entry = min(e.created_at for e in entries)
        self._stats.newest_entry = max(e.created_at for e in entries)
    
    def invalidate(self, pattern: str | None = None) -> int:
        """
        Invalidate cache entries.
        
        Args:
            pattern: If provided, only invalidate entries containing this pattern
                    in query_preview. If None, clear all entries.
                    
        Returns:
            Number of entries removed
        """
        if pattern is None:
            count = len(self._cache)
            self._cache.clear()
            self._stats.total_entries = 0
            return count
        
        # Find matching entries
        to_remove = [
            key for key, entry in self._cache.items()
            if pattern.lower() in entry.query_preview.lower()
        ]
        
        for key in to_remove:
            del self._cache[key]
        
        return len(to_remove)
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.
        
        Returns:
            Number of entries removed
        """
        expired = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        
        for key in expired:
            del self._cache[key]
        
        return len(expired)
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        self._stats.total_entries = len(self._cache)
        self._update_time_stats()
        return self._stats
    
    def get_entries(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get recent cache entries for inspection.
        
        Args:
            limit: Maximum entries to return
            
        Returns:
            List of entry dictionaries
        """
        entries = list(self._cache.values())[-limit:]
        return [
            {
                "hash": e.query_hash[:8],
                "preview": e.query_preview[:50],
                "model": e.model_used,
                "hits": e.hit_count,
                "tokens_saved": e.tokens_saved,
                "created": e.created_at.strftime("%Y-%m-%d %H:%M"),
                "expires": e.expires_at.strftime("%Y-%m-%d %H:%M"),
            }
            for e in entries
        ]
    
    def _load_from_storage(self) -> None:
        """Load cache from persistent storage."""
        if not self.storage_path or not self.storage_path.exists():
            return
        
        try:
            data = json.loads(self.storage_path.read_text())
            
            # Load entries
            for entry_data in data.get("entries", []):
                entry = CacheEntry.from_dict(entry_data)
                if not entry.is_expired():
                    self._cache[entry.query_hash] = entry
            
            # Load stats
            stats = data.get("stats", {})
            self._stats.total_hits = stats.get("total_hits", 0)
            self._stats.total_misses = stats.get("total_misses", 0)
            self._stats.total_tokens_saved = stats.get("total_tokens_saved", 0)
            self._stats.total_evictions = stats.get("total_evictions", 0)
            
        except (json.JSONDecodeError, KeyError, IOError):
            pass  # Start fresh on error
    
    def _save_to_storage(self) -> None:
        """Save cache to persistent storage."""
        if not self.storage_path:
            return
        
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "entries": [e.to_dict() for e in self._cache.values()],
            "stats": {
                "total_hits": self._stats.total_hits,
                "total_misses": self._stats.total_misses,
                "total_tokens_saved": self._stats.total_tokens_saved,
                "total_evictions": self._stats.total_evictions,
            },
        }
        
        self.storage_path.write_text(json.dumps(data, indent=2))
    
    def save(self) -> None:
        """Explicitly save cache to storage."""
        self._save_to_storage()
