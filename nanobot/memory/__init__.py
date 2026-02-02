"""
Enhanced memory system for GigaBot.

Provides:
- Daily notes storage
- Long-term memory (MEMORY.md)
- Vector store for semantic search
- Hybrid search (vector + keyword)
"""

from nanobot.memory.store import (
    MemoryStore,
    MemoryEntry,
)
from nanobot.memory.vector import (
    VectorStore,
    SearchResult,
)
from nanobot.memory.search import (
    HybridSearch,
    search_memories,
)

__all__ = [
    "MemoryStore",
    "MemoryEntry",
    "VectorStore",
    "SearchResult",
    "HybridSearch",
    "search_memories",
]
