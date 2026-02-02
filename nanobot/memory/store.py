"""
Memory storage for GigaBot.

Manages:
- Daily notes (YYYY-MM-DD.md files)
- Long-term memory (MEMORY.md)
- Memory entries with metadata
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    content: str
    source: str  # "daily", "long_term", "session"
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5  # 0.0 to 1.0
    tags: list[str] = field(default_factory=list)


class MemoryStore:
    """
    Enhanced memory store with structured storage and retrieval.
    
    Storage structure:
    - memory/MEMORY.md - Long-term important memories
    - memory/YYYY-MM-DD.md - Daily notes
    - memory/index.json - Optional metadata index
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.long_term_file = self.memory_dir / "MEMORY.md"
        
        # In-memory cache
        self._cache: dict[str, list[MemoryEntry]] = {}
        self._cache_valid = False
    
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
