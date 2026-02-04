"""
Memory storage for GigaBot.

Manages:
- Daily notes (YYYY-MM-DD.md files)
- Long-term memory (MEMORY.md)
- Memory entries with metadata
- Evolution tracking (access counts, decay, cross-references)
"""

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field, asdict


@dataclass
class MemoryEntry:
    """
    A single memory entry with evolution tracking.
    
    Evolution fields enable:
    - Auto-promotion of frequently accessed memories
    - Decay of unused memories
    - Cross-referencing related memories
    - Archival of old, unaccessed content
    """
    id: str
    content: str
    source: str  # "daily", "long_term", "session"
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5  # 0.0 to 1.0
    tags: list[str] = field(default_factory=list)
    
    # Evolution tracking fields
    access_count: int = 0
    last_accessed: datetime | None = None
    promotion_score: float = 0.0  # Accumulated promotion points
    decay_rate: float = 0.01      # How fast importance decays
    cross_references: list[str] = field(default_factory=list)  # Related entry IDs
    archived: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['last_accessed'] = self.last_accessed.isoformat() if self.last_accessed else None
        return data
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEntry":
        """Create from dictionary."""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if data.get('last_accessed'):
            data['last_accessed'] = datetime.fromisoformat(data['last_accessed'])
        return cls(**data)


class MemoryStore:
    """
    Enhanced memory store with structured storage, retrieval, and evolution tracking.
    
    Storage structure:
    - memory/MEMORY.md - Long-term important memories
    - memory/YYYY-MM-DD.md - Daily notes
    - memory/index.json - Metadata index with evolution data
    - memory/archive/ - Archived memories
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.long_term_file = self.memory_dir / "MEMORY.md"
        self.index_file = self.memory_dir / "index.json"
        self.archive_dir = self.memory_dir / "archive"
        
        # In-memory cache
        self._cache: dict[str, list[MemoryEntry]] = {}
        self._cache_valid = False
        
        # Evolution index (entry_id -> evolution data)
        self._evolution_index: dict[str, dict[str, Any]] = {}
        self._load_evolution_index()
    
    def get_long_term_memory(self) -> str:
        """Get long-term memory content."""
        if self.long_term_file.exists():
            return self.long_term_file.read_text()
        return ""
    
    def get_daily_notes(self, date: datetime | None = None) -> str:
        """Get daily notes for a specific date."""
        date = date or datetime.now()
        filename = date.strftime("%Y-%m-%d.md")
        daily_file = self.memory_dir / filename
        
        if daily_file.exists():
            return daily_file.read_text()
        return ""
    
    def get_recent_memories(self, days: int = 7) -> str:
        """Get memories from the last N days."""
        memories = []
        today = datetime.now()
        
        # Long-term memory
        lt_content = self.get_long_term_memory()
        if lt_content:
            memories.append("## Long-term Memory\n\n" + lt_content)
        
        # Daily notes
        for i in range(days):
            date = today - timedelta(days=i)
            content = self.get_daily_notes(date)
            if content:
                date_str = date.strftime("%Y-%m-%d")
                memories.append(f"## Daily Notes ({date_str})\n\n{content}")
        
        return "\n\n".join(memories)
    
    def add_to_daily(self, content: str, date: datetime | None = None) -> None:
        """Add content to daily notes."""
        date = date or datetime.now()
        filename = date.strftime("%Y-%m-%d.md")
        daily_file = self.memory_dir / filename
        
        existing = ""
        if daily_file.exists():
            existing = daily_file.read_text()
        
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M")
        entry = f"\n### {timestamp}\n\n{content}\n"
        
        daily_file.write_text(existing + entry)
        self._cache_valid = False
    
    def add_to_long_term(self, content: str, section: str = "") -> None:
        """Add content to long-term memory."""
        existing = self.get_long_term_memory()
        
        if section:
            # Try to find and append to existing section
            section_pattern = rf"(## {re.escape(section)}.*?)(?=\n## |\Z)"
            match = re.search(section_pattern, existing, re.DOTALL)
            
            if match:
                # Append to existing section
                section_content = match.group(1)
                new_section = section_content.rstrip() + f"\n\n{content}\n"
                existing = existing[:match.start()] + new_section + existing[match.end():]
            else:
                # Add new section
                existing = existing.rstrip() + f"\n\n## {section}\n\n{content}\n"
        else:
            # Append to end
            existing = existing.rstrip() + f"\n\n{content}\n"
        
        self.long_term_file.write_text(existing)
        self._cache_valid = False
    
    def get_all_entries(self) -> list[MemoryEntry]:
        """Get all memory entries for indexing."""
        if self._cache_valid and "all" in self._cache:
            return self._cache["all"]
        
        entries = []
        
        # Parse long-term memory
        lt_content = self.get_long_term_memory()
        if lt_content:
            entries.extend(self._parse_memory_content(
                lt_content, "long_term", datetime.now()
            ))
        
        # Parse daily notes
        for file in sorted(self.memory_dir.glob("????-??-??.md")):
            date_str = file.stem
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d")
                content = file.read_text()
                entries.extend(self._parse_memory_content(content, "daily", date))
            except ValueError:
                continue
        
        self._cache["all"] = entries
        self._cache_valid = True
        
        return entries
    
    def _parse_memory_content(
        self, 
        content: str, 
        source: str, 
        date: datetime
    ) -> list[MemoryEntry]:
        """Parse memory content into entries."""
        entries = []
        
        # Split by headers
        sections = re.split(r"^(#+\s+.+)$", content, flags=re.MULTILINE)
        
        current_header = ""
        for i, section in enumerate(sections):
            if section.startswith("#"):
                current_header = section.strip("# \n")
            elif section.strip():
                # Create entry for this section
                entry_id = f"{source}:{date.strftime('%Y%m%d')}:{i}"
                
                entries.append(MemoryEntry(
                    id=entry_id,
                    content=section.strip(),
                    source=source,
                    timestamp=date,
                    metadata={"header": current_header},
                    tags=self._extract_tags(section),
                ))
        
        return entries
    
    def _extract_tags(self, content: str) -> list[str]:
        """Extract tags from content (e.g., #tag or [[tag]])."""
        tags = []
        
        # Hashtags
        tags.extend(re.findall(r"#(\w+)", content))
        
        # Wiki-style links
        tags.extend(re.findall(r"\[\[([^\]]+)\]\]", content))
        
        return list(set(tags))
    
    def search_by_keyword(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Simple keyword search across memories."""
        entries = self.get_all_entries()
        query_lower = query.lower()
        
        results = []
        for entry in entries:
            if query_lower in entry.content.lower():
                results.append(entry)
                if len(results) >= limit:
                    break
        
        return results
    
    def search_by_date_range(
        self, 
        start: datetime, 
        end: datetime | None = None
    ) -> list[MemoryEntry]:
        """Get entries within a date range."""
        end = end or datetime.now()
        entries = self.get_all_entries()
        
        return [
            e for e in entries 
            if start <= e.timestamp <= end
        ]
    
    def get_context_for_prompt(self, max_tokens: int = 2000) -> str:
        """
        Get memory context suitable for LLM prompt.
        
        Prioritizes:
        1. Recent daily notes
        2. Long-term memory
        3. Relevant tags
        """
        context_parts = []
        estimated_tokens = 0
        
        # Long-term memory (most important)
        lt_content = self.get_long_term_memory()
        if lt_content:
            lt_tokens = len(lt_content) // 4  # Rough estimate
            if estimated_tokens + lt_tokens < max_tokens:
                context_parts.append("# Long-term Memory\n\n" + lt_content)
                estimated_tokens += lt_tokens
        
        # Recent daily notes
        for i in range(7):
            date = datetime.now() - timedelta(days=i)
            content = self.get_daily_notes(date)
            if content:
                content_tokens = len(content) // 4
                if estimated_tokens + content_tokens < max_tokens:
                    date_str = date.strftime("%Y-%m-%d")
                    context_parts.append(f"# Daily Notes ({date_str})\n\n{content}")
                    estimated_tokens += content_tokens
                else:
                    break
        
        return "\n\n---\n\n".join(context_parts)
    
    def invalidate_cache(self) -> None:
        """Invalidate the memory cache."""
        self._cache_valid = False
        self._cache.clear()
    
    # =========================================================================
    # Evolution Tracking Methods
    # =========================================================================
    
    def _load_evolution_index(self) -> None:
        """Load evolution index from disk."""
        if self.index_file.exists():
            try:
                self._evolution_index = json.loads(self.index_file.read_text())
            except (json.JSONDecodeError, IOError):
                self._evolution_index = {}
        else:
            self._evolution_index = {}
    
    def _save_evolution_index(self) -> None:
        """Save evolution index to disk."""
        self.index_file.write_text(json.dumps(self._evolution_index, indent=2))
    
    def record_access(self, entry_id: str) -> None:
        """
        Record that a memory was accessed.
        
        Updates:
        - access_count: +1
        - last_accessed: now
        - promotion_score: +0.02 per access
        """
        if entry_id not in self._evolution_index:
            self._evolution_index[entry_id] = {
                "access_count": 0,
                "last_accessed": None,
                "promotion_score": 0.0,
                "decay_rate": 0.01,
                "cross_references": [],
                "archived": False,
            }
        
        data = self._evolution_index[entry_id]
        data["access_count"] = data.get("access_count", 0) + 1
        data["last_accessed"] = datetime.now().isoformat()
        data["promotion_score"] = data.get("promotion_score", 0.0) + 0.02
        
        self._save_evolution_index()
    
    def get_evolution_data(self, entry_id: str) -> dict[str, Any]:
        """Get evolution data for an entry."""
        return self._evolution_index.get(entry_id, {
            "access_count": 0,
            "last_accessed": None,
            "promotion_score": 0.0,
            "decay_rate": 0.01,
            "cross_references": [],
            "archived": False,
        })
    
    def update_evolution_data(self, entry_id: str, updates: dict[str, Any]) -> None:
        """Update evolution data for an entry."""
        if entry_id not in self._evolution_index:
            self._evolution_index[entry_id] = {
                "access_count": 0,
                "last_accessed": None,
                "promotion_score": 0.0,
                "decay_rate": 0.01,
                "cross_references": [],
                "archived": False,
            }
        
        self._evolution_index[entry_id].update(updates)
        self._save_evolution_index()
    
    def add_cross_reference(self, entry_id: str, related_id: str) -> None:
        """Add a cross-reference between two entries."""
        data = self.get_evolution_data(entry_id)
        refs = data.get("cross_references", [])
        if related_id not in refs:
            refs.append(related_id)
            self.update_evolution_data(entry_id, {"cross_references": refs})
        
        # Bidirectional reference
        related_data = self.get_evolution_data(related_id)
        related_refs = related_data.get("cross_references", [])
        if entry_id not in related_refs:
            related_refs.append(entry_id)
            self.update_evolution_data(related_id, {"cross_references": related_refs})
    
    def get_entries_by_importance(
        self,
        min_importance: float = 0.0,
        include_archived: bool = False
    ) -> list[MemoryEntry]:
        """Get entries filtered by importance threshold."""
        entries = self.get_all_entries()
        
        result = []
        for entry in entries:
            evo_data = self.get_evolution_data(entry.id)
            
            # Skip archived unless requested
            if evo_data.get("archived", False) and not include_archived:
                continue
            
            # Calculate effective importance
            effective_importance = entry.importance + evo_data.get("promotion_score", 0.0)
            
            if effective_importance >= min_importance:
                # Enrich entry with evolution data
                entry.access_count = evo_data.get("access_count", 0)
                entry.promotion_score = evo_data.get("promotion_score", 0.0)
                entry.cross_references = evo_data.get("cross_references", [])
                entry.archived = evo_data.get("archived", False)
                if evo_data.get("last_accessed"):
                    entry.last_accessed = datetime.fromisoformat(evo_data["last_accessed"])
                result.append(entry)
        
        return result
    
    def archive_entry(self, entry_id: str) -> bool:
        """Mark an entry as archived."""
        self.update_evolution_data(entry_id, {"archived": True})
        return True
    
    def get_memory_stats(self) -> dict[str, Any]:
        """
        Get statistics about the memory store.
        
        Returns:
            Dictionary with counts, importance distribution, etc.
        """
        entries = self.get_all_entries()
        
        # Basic counts
        total = len(entries)
        archived = sum(
            1 for e in entries
            if self.get_evolution_data(e.id).get("archived", False)
        )
        
        # Importance distribution
        importance_buckets = {"high": 0, "medium": 0, "low": 0}
        for entry in entries:
            evo = self.get_evolution_data(entry.id)
            eff_importance = entry.importance + evo.get("promotion_score", 0.0)
            if eff_importance >= 0.7:
                importance_buckets["high"] += 1
            elif eff_importance >= 0.3:
                importance_buckets["medium"] += 1
            else:
                importance_buckets["low"] += 1
        
        # Access patterns
        total_accesses = sum(
            self.get_evolution_data(e.id).get("access_count", 0)
            for e in entries
        )
        
        # Cross-reference count
        total_refs = sum(
            len(self.get_evolution_data(e.id).get("cross_references", []))
            for e in entries
        )
        
        return {
            "total_entries": total,
            "archived_entries": archived,
            "active_entries": total - archived,
            "importance_distribution": importance_buckets,
            "total_accesses": total_accesses,
            "total_cross_references": total_refs // 2,  # Each ref counted twice
            "average_accesses_per_entry": total_accesses / total if total > 0 else 0,
        }
