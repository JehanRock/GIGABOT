"""
Hybrid search system for GigaBot memory.

Combines:
- Vector/semantic search
- Keyword/FTS search
- Recency weighting
- Importance scoring
"""

from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass, field
from pathlib import Path

from nanobot.memory.store import MemoryStore, MemoryEntry
from nanobot.memory.vector import VectorStore, SearchResult


@dataclass
class HybridSearchResult:
    """Result from hybrid search."""
    entry: MemoryEntry
    combined_score: float
    vector_score: float
    keyword_score: float
    recency_score: float


class HybridSearch:
    """
    Hybrid search combining vector and keyword search.
    
    Scoring formula:
    combined = (vector_weight * vector_score) + 
               (keyword_weight * keyword_score) + 
               (recency_weight * recency_score)
    """
    
    def __init__(
        self,
        memory_store: MemoryStore,
        vector_store: VectorStore,
        vector_weight: float = 0.6,
        keyword_weight: float = 0.3,
        recency_weight: float = 0.1,
    ):
        self.memory_store = memory_store
        self.vector_store = vector_store
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.recency_weight = recency_weight
    
    def search(
        self,
        query: str,
        k: int = 10,
        recency_days: int = 30,
    ) -> list[HybridSearchResult]:
        """
        Perform hybrid search.
        
        Args:
            query: Search query text.
            k: Number of results to return.
            recency_days: Days to consider for recency scoring.
        
        Returns:
            List of HybridSearchResults sorted by combined score.
        """
        # Vector search
        vector_results = self.vector_store.search(query, k=k * 2)
        vector_scores = {r.entry.id: r.score for r in vector_results}
        
        # Keyword search
        keyword_results = self.memory_store.search_by_keyword(query, limit=k * 2)
        keyword_scores = self._calculate_keyword_scores(query, keyword_results)
        
        # Combine all entries
        all_entry_ids = set(vector_scores.keys()) | set(keyword_scores.keys())
        all_entries = {}
        
        for result in vector_results:
            all_entries[result.entry.id] = result.entry
        for entry in keyword_results:
            all_entries[entry.id] = entry
        
        # Calculate combined scores
        results = []
        now = datetime.now()
        
        for entry_id in all_entry_ids:
            entry = all_entries[entry_id]
            
            v_score = vector_scores.get(entry_id, 0.0)
            k_score = keyword_scores.get(entry_id, 0.0)
            r_score = self._calculate_recency_score(entry.timestamp, now, recency_days)
            
            combined = (
                self.vector_weight * v_score +
                self.keyword_weight * k_score +
                self.recency_weight * r_score
            )
            
            results.append(HybridSearchResult(
                entry=entry,
                combined_score=combined,
                vector_score=v_score,
                keyword_score=k_score,
                recency_score=r_score,
            ))
        
        # Sort by combined score
        results.sort(key=lambda x: x.combined_score, reverse=True)
        
        return results[:k]
    
    def _calculate_keyword_scores(
        self,
        query: str,
        entries: list[MemoryEntry],
    ) -> dict[str, float]:
        """Calculate BM25-style keyword scores."""
        scores = {}
        query_terms = set(query.lower().split())
        
        for entry in entries:
            content_lower = entry.content.lower()
            
            # Count term matches
            matches = sum(1 for term in query_terms if term in content_lower)
            
            # Simple TF-IDF-style score
            if matches > 0:
                tf = matches / len(query_terms)
                # Boost for exact phrase match
                if query.lower() in content_lower:
                    tf *= 1.5
                scores[entry.id] = min(tf, 1.0)
        
        return scores
    
    def _calculate_recency_score(
        self,
        timestamp: datetime,
        now: datetime,
        max_days: int,
    ) -> float:
        """Calculate recency score (exponential decay)."""
        age = (now - timestamp).days
        
        if age <= 0:
            return 1.0
        if age >= max_days:
            return 0.0
        
        # Exponential decay
        return (1.0 - (age / max_days)) ** 2
    
    def index_all_memories(self) -> int:
        """
        Index all memories into the vector store.
        
        Returns:
            Number of entries indexed.
        """
        entries = self.memory_store.get_all_entries()
        
        # Clear existing
        self.vector_store.clear()
        
        # Add all entries
        self.vector_store.add_batch(entries)
        
        return len(entries)


def search_memories(
    query: str,
    workspace: Path,
    k: int = 5,
    vector_weight: float = 0.6,
) -> list[HybridSearchResult]:
    """
    Convenience function to search memories.
    
    Args:
        query: Search query text.
        workspace: Path to workspace directory.
        k: Number of results.
        vector_weight: Weight for vector search (0.0 to 1.0).
    
    Returns:
        List of search results.
    """
    memory_store = MemoryStore(workspace)
    vector_store = VectorStore(
        storage_path=workspace / "memory" / "vectors.json"
    )
    
    # Index if empty
    if vector_store.size == 0:
        entries = memory_store.get_all_entries()
        vector_store.add_batch(entries)
    
    # Ensure weights are valid (recency_weight = 0.1)
    recency_weight = 0.1
    keyword_weight = max(0.0, 1.0 - vector_weight - recency_weight)
    
    search = HybridSearch(
        memory_store=memory_store,
        vector_store=vector_store,
        vector_weight=min(vector_weight, 0.9),  # Cap to leave room for recency
        keyword_weight=keyword_weight,
        recency_weight=recency_weight,
    )
    
    return search.search(query, k=k)


class MemoryTool:
    """
    Tool interface for memory operations.
    
    Can be registered as a tool in the agent loop.
    """
    
    name = "memory"
    description = """Search and manage memories.

Actions:
- search: Search memories with a query
- add_daily: Add a memory to today's daily notes
- add_long_term: Add a memory to long-term storage
- get_recent: Get recent memories

Examples:
- Search: {"action": "search", "query": "user preferences"}
- Add daily: {"action": "add_daily", "content": "User prefers dark mode"}
- Add long-term: {"action": "add_long_term", "content": "Important fact", "section": "User Info"}
"""
    
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "add_daily", "add_long_term", "get_recent"],
                "description": "The memory action to perform"
            },
            "query": {
                "type": "string",
                "description": "Search query for search action"
            },
            "content": {
                "type": "string",
                "description": "Content for add actions"
            },
            "section": {
                "type": "string",
                "description": "Section name for add_long_term action"
            },
            "days": {
                "type": "integer",
                "description": "Number of days for get_recent action",
                "default": 7
            }
        },
        "required": ["action"]
    }
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_store = MemoryStore(workspace)
        self.vector_store = VectorStore(
            storage_path=workspace / "memory" / "vectors.json"
        )
        self._search: HybridSearch | None = None
    
    def _get_search(self) -> HybridSearch:
        """Get or create hybrid search instance."""
        if self._search is None:
            self._search = HybridSearch(self.memory_store, self.vector_store)
        return self._search
    
    async def execute(self, **kwargs: Any) -> str:
        """Execute memory action."""
        action = kwargs.get("action", "")
        
        try:
            if action == "search":
                return self._search_memories(kwargs.get("query", ""))
            
            elif action == "add_daily":
                return self._add_daily(kwargs.get("content", ""))
            
            elif action == "add_long_term":
                return self._add_long_term(
                    kwargs.get("content", ""),
                    kwargs.get("section", "")
                )
            
            elif action == "get_recent":
                return self._get_recent(kwargs.get("days", 7))
            
            else:
                return f"Unknown action: {action}"
                
        except Exception as e:
            return f"Memory error: {str(e)}"
    
    def _search_memories(self, query: str) -> str:
        """Search memories."""
        if not query:
            return "Error: Query required for search"
        
        search = self._get_search()
        results = search.search(query, k=5)
        
        if not results:
            return "No memories found matching the query."
        
        lines = [f"Found {len(results)} relevant memories:", ""]
        for i, result in enumerate(results, 1):
            lines.append(f"{i}. [Score: {result.combined_score:.2f}]")
            lines.append(f"   Source: {result.entry.source}")
            lines.append(f"   Content: {result.entry.content[:200]}...")
            lines.append("")
        
        return "\n".join(lines)
    
    def _add_daily(self, content: str) -> str:
        """Add to daily notes."""
        if not content:
            return "Error: Content required"
        
        self.memory_store.add_to_daily(content)
        
        # Update vector store
        from datetime import datetime
        entry = MemoryEntry(
            id=f"daily:{datetime.now().strftime('%Y%m%d%H%M%S')}",
            content=content,
            source="daily",
            timestamp=datetime.now(),
        )
        self.vector_store.add(entry)
        
        return "Added to daily notes"
    
    def _add_long_term(self, content: str, section: str) -> str:
        """Add to long-term memory."""
        if not content:
            return "Error: Content required"
        
        self.memory_store.add_to_long_term(content, section)
        
        # Update vector store
        from datetime import datetime
        entry = MemoryEntry(
            id=f"long_term:{datetime.now().strftime('%Y%m%d%H%M%S')}",
            content=content,
            source="long_term",
            timestamp=datetime.now(),
            metadata={"section": section},
        )
        self.vector_store.add(entry)
        
        section_info = f" in section '{section}'" if section else ""
        return f"Added to long-term memory{section_info}"
    
    def _get_recent(self, days: int) -> str:
        """Get recent memories."""
        content = self.memory_store.get_recent_memories(days)
        
        if not content:
            return f"No memories from the last {days} days"
        
        return content
