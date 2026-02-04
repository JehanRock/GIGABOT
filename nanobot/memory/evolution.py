"""
Memory Evolution System for GigaBot.

Self-organizing memory that improves over time:
- Auto-promotion: Frequently accessed memories gain importance
- Auto-decay: Unused memories lose importance
- Cross-referencing: Link related memories automatically
- Consolidation: Merge similar memories
- Archival: Move old, unaccessed memories to archive
"""

from datetime import datetime, timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import logging

from nanobot.memory.store import MemoryStore, MemoryEntry

logger = logging.getLogger(__name__)


@dataclass
class EvolutionReport:
    """Report from an evolution cycle."""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Counts
    promoted: list[str] = field(default_factory=list)   # Entry IDs promoted
    decayed: list[str] = field(default_factory=list)    # Entry IDs decayed
    archived: list[str] = field(default_factory=list)   # Entry IDs archived
    consolidated: int = 0                                # Number of merges
    cross_refs_added: int = 0                           # Cross-references created
    
    # Timing
    duration_ms: float = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "promoted_count": len(self.promoted),
            "decayed_count": len(self.decayed),
            "archived_count": len(self.archived),
            "consolidated": self.consolidated,
            "cross_refs_added": self.cross_refs_added,
            "duration_ms": self.duration_ms,
        }


class MemoryEvolution:
    """
    Self-organizing memory management.
    
    Features:
    - Promotion: Frequently accessed memories gain importance
    - Decay: Unused memories slowly lose importance
    - Archive: Move very old/unused memories to archive
    - Cross-reference: Link related memories using vector similarity
    - Consolidation: Merge highly similar memories
    """
    
    # Evolution rules
    PROMOTION_ACCESS_THRESHOLD = 3     # Accesses needed in window for promotion
    PROMOTION_WINDOW_DAYS = 7          # Window for counting accesses
    PROMOTION_BOOST = 0.1              # Importance boost on promotion
    
    DECAY_INACTIVE_DAYS = 30           # Days of inactivity before decay
    DECAY_AMOUNT = 0.1                 # Importance reduction per decay
    
    ARCHIVE_INACTIVE_DAYS = 90         # Days of inactivity before archival
    ARCHIVE_MIN_IMPORTANCE = 0.1       # Below this, archive faster
    
    CONSOLIDATION_THRESHOLD = 0.85     # Vector similarity for merge
    
    def __init__(
        self,
        store: MemoryStore,
        vector_store: Any = None,
        config: dict[str, Any] | None = None
    ):
        """
        Initialize the evolution engine.
        
        Args:
            store: The memory store to manage
            vector_store: Optional vector store for similarity search
            config: Optional configuration overrides
        """
        self.store = store
        self.vector_store = vector_store
        
        # Apply config overrides
        if config:
            self.PROMOTION_ACCESS_THRESHOLD = config.get(
                "promotion_access_threshold", self.PROMOTION_ACCESS_THRESHOLD
            )
            self.PROMOTION_WINDOW_DAYS = config.get(
                "promotion_window_days", self.PROMOTION_WINDOW_DAYS
            )
            self.DECAY_INACTIVE_DAYS = config.get(
                "decay_inactive_days", self.DECAY_INACTIVE_DAYS
            )
            self.ARCHIVE_INACTIVE_DAYS = config.get(
                "archive_after_days", self.ARCHIVE_INACTIVE_DAYS
            )
            self.CONSOLIDATION_THRESHOLD = config.get(
                "consolidation_threshold", self.CONSOLIDATION_THRESHOLD
            )
    
    async def evolve(
        self,
        dry_run: bool = False,
        auto_promote: bool = True,
        auto_decay: bool = True,
        auto_archive: bool = True,
        auto_consolidate: bool = True
    ) -> EvolutionReport:
        """
        Run full evolution cycle.
        
        Args:
            dry_run: If True, don't make changes, just report
            auto_promote: Run promotion
            auto_decay: Run decay
            auto_archive: Run archival
            auto_consolidate: Run consolidation
            
        Returns:
            EvolutionReport with details of changes
        """
        start_time = datetime.now()
        report = EvolutionReport()
        
        try:
            # 1. Promotion - boost frequently accessed memories
            if auto_promote:
                promoted = await self._run_promotion(dry_run=dry_run)
                report.promoted = promoted
                logger.info(f"Promoted {len(promoted)} memories")
            
            # 2. Decay - reduce importance of unused memories
            if auto_decay:
                decayed = await self._run_decay(dry_run=dry_run)
                report.decayed = decayed
                logger.info(f"Decayed {len(decayed)} memories")
            
            # 3. Archive - move old/unused to archive
            if auto_archive:
                archived = await self._run_archive(dry_run=dry_run)
                report.archived = archived
                logger.info(f"Archived {len(archived)} memories")
            
            # 4. Cross-reference - link related memories
            refs_added = await self._run_cross_reference(dry_run=dry_run)
            report.cross_refs_added = refs_added
            logger.info(f"Added {refs_added} cross-references")
            
            # 5. Consolidation - merge similar memories
            if auto_consolidate and self.vector_store:
                consolidated = await self._run_consolidation(dry_run=dry_run)
                report.consolidated = consolidated
                logger.info(f"Consolidated {consolidated} memory pairs")
                
        except Exception as e:
            logger.error(f"Evolution cycle failed: {e}")
        
        # Calculate duration
        report.duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        return report
    
    async def _run_promotion(self, dry_run: bool = False) -> list[str]:
        """
        Promote frequently accessed memories.
        
        Rules:
        - Access count >= THRESHOLD in last WINDOW days: +BOOST importance
        - Referenced in agent response: +0.05 importance
        """
        promoted = []
        entries = self.store.get_all_entries()
        now = datetime.now()
        window_start = now - timedelta(days=self.PROMOTION_WINDOW_DAYS)
        
        for entry in entries:
            evo_data = self.store.get_evolution_data(entry.id)
            
            # Skip archived
            if evo_data.get("archived", False):
                continue
            
            # Check if accessed enough times recently
            access_count = evo_data.get("access_count", 0)
            last_accessed_str = evo_data.get("last_accessed")
            
            if access_count >= self.PROMOTION_ACCESS_THRESHOLD:
                if last_accessed_str:
                    last_accessed = datetime.fromisoformat(last_accessed_str)
                    if last_accessed >= window_start:
                        # Eligible for promotion
                        if not dry_run:
                            current_score = evo_data.get("promotion_score", 0.0)
                            new_score = min(current_score + self.PROMOTION_BOOST, 1.0)
                            self.store.update_evolution_data(entry.id, {
                                "promotion_score": new_score
                            })
                        promoted.append(entry.id)
        
        return promoted
    
    async def _run_decay(self, dry_run: bool = False) -> list[str]:
        """
        Apply decay to unused memories.
        
        Rules:
        - Not accessed in DECAY_INACTIVE_DAYS: -DECAY_AMOUNT importance
        """
        decayed = []
        entries = self.store.get_all_entries()
        now = datetime.now()
        decay_cutoff = now - timedelta(days=self.DECAY_INACTIVE_DAYS)
        
        for entry in entries:
            evo_data = self.store.get_evolution_data(entry.id)
            
            # Skip archived
            if evo_data.get("archived", False):
                continue
            
            # Check last access time
            last_accessed_str = evo_data.get("last_accessed")
            should_decay = False
            
            if last_accessed_str:
                last_accessed = datetime.fromisoformat(last_accessed_str)
                if last_accessed < decay_cutoff:
                    should_decay = True
            else:
                # Never accessed, use entry timestamp
                if entry.timestamp < decay_cutoff:
                    should_decay = True
            
            if should_decay:
                if not dry_run:
                    current_score = evo_data.get("promotion_score", 0.0)
                    new_score = max(current_score - self.DECAY_AMOUNT, -0.5)
                    self.store.update_evolution_data(entry.id, {
                        "promotion_score": new_score
                    })
                decayed.append(entry.id)
        
        return decayed
    
    async def _run_archive(self, dry_run: bool = False) -> list[str]:
        """
        Archive old, unused memories.
        
        Rules:
        - Not accessed in ARCHIVE_INACTIVE_DAYS: archive
        - importance + promotion_score < MIN_IMPORTANCE: archive faster (30 days)
        """
        archived = []
        entries = self.store.get_all_entries()
        now = datetime.now()
        archive_cutoff = now - timedelta(days=self.ARCHIVE_INACTIVE_DAYS)
        fast_archive_cutoff = now - timedelta(days=30)  # Faster for low importance
        
        for entry in entries:
            evo_data = self.store.get_evolution_data(entry.id)
            
            # Skip already archived
            if evo_data.get("archived", False):
                continue
            
            # Calculate effective importance
            effective_importance = entry.importance + evo_data.get("promotion_score", 0.0)
            
            # Determine which cutoff to use
            if effective_importance < self.ARCHIVE_MIN_IMPORTANCE:
                cutoff = fast_archive_cutoff
            else:
                cutoff = archive_cutoff
            
            # Check last access time
            last_accessed_str = evo_data.get("last_accessed")
            should_archive = False
            
            if last_accessed_str:
                last_accessed = datetime.fromisoformat(last_accessed_str)
                if last_accessed < cutoff:
                    should_archive = True
            else:
                # Never accessed, use entry timestamp
                if entry.timestamp < cutoff:
                    should_archive = True
            
            if should_archive:
                if not dry_run:
                    self.store.archive_entry(entry.id)
                archived.append(entry.id)
        
        return archived
    
    async def _run_cross_reference(self, dry_run: bool = False) -> int:
        """
        Create cross-references between related memories.
        
        Uses:
        - Tag overlap
        - Vector similarity (if vector_store available)
        """
        refs_added = 0
        entries = self.store.get_all_entries()
        
        # Filter out archived
        active_entries = [
            e for e in entries
            if not self.store.get_evolution_data(e.id).get("archived", False)
        ]
        
        # Simple tag-based cross-referencing
        for i, entry in enumerate(active_entries):
            if not entry.tags:
                continue
            
            entry_tags = set(entry.tags)
            evo_data = self.store.get_evolution_data(entry.id)
            existing_refs = set(evo_data.get("cross_references", []))
            
            for other in active_entries[i+1:]:
                if other.id in existing_refs:
                    continue
                
                if not other.tags:
                    continue
                
                other_tags = set(other.tags)
                overlap = len(entry_tags & other_tags)
                
                # Link if >= 2 shared tags
                if overlap >= 2:
                    if not dry_run:
                        self.store.add_cross_reference(entry.id, other.id)
                    refs_added += 1
        
        # Vector-based cross-referencing
        if self.vector_store and hasattr(self.vector_store, 'find_similar'):
            for entry in active_entries[:50]:  # Limit to recent 50
                evo_data = self.store.get_evolution_data(entry.id)
                existing_refs = set(evo_data.get("cross_references", []))
                
                try:
                    similar = await self.vector_store.find_similar(
                        entry.content,
                        k=5,
                        threshold=0.7
                    )
                    
                    for sim_entry, score in similar:
                        if sim_entry.id != entry.id and sim_entry.id not in existing_refs:
                            if not dry_run:
                                self.store.add_cross_reference(entry.id, sim_entry.id)
                            refs_added += 1
                except Exception:
                    pass
        
        return refs_added
    
    async def _run_consolidation(self, dry_run: bool = False) -> int:
        """
        Consolidate (merge) highly similar memories.
        
        Requires vector_store with similarity search.
        """
        if not self.vector_store:
            return 0
        
        consolidated = 0
        entries = self.store.get_all_entries()
        
        # Filter out archived
        active_entries = [
            e for e in entries
            if not self.store.get_evolution_data(e.id).get("archived", False)
        ]
        
        merged_ids = set()
        
        for entry in active_entries:
            if entry.id in merged_ids:
                continue
            
            try:
                similar = await self.vector_store.find_similar(
                    entry.content,
                    k=3,
                    threshold=self.CONSOLIDATION_THRESHOLD
                )
                
                for sim_entry, score in similar:
                    if sim_entry.id == entry.id or sim_entry.id in merged_ids:
                        continue
                    
                    # Found a consolidation candidate
                    if not dry_run:
                        # Keep the more detailed entry (longer content)
                        if len(sim_entry.content) > len(entry.content):
                            keeper, archived_entry = sim_entry, entry
                        else:
                            keeper, archived_entry = entry, sim_entry
                        
                        # Archive the shorter one and add cross-reference
                        self.store.archive_entry(archived_entry.id)
                        self.store.add_cross_reference(keeper.id, archived_entry.id)
                        
                        # Transfer access count
                        keeper_evo = self.store.get_evolution_data(keeper.id)
                        archived_evo = self.store.get_evolution_data(archived_entry.id)
                        combined_access = (
                            keeper_evo.get("access_count", 0) +
                            archived_evo.get("access_count", 0)
                        )
                        self.store.update_evolution_data(keeper.id, {
                            "access_count": combined_access
                        })
                        
                        merged_ids.add(archived_entry.id)
                    
                    consolidated += 1
                    
            except Exception:
                pass
        
        return consolidated
    
    async def promote_memory(self, entry_id: str, reason: str = "") -> bool:
        """
        Manually promote a specific memory.
        
        Args:
            entry_id: Memory to promote
            reason: Optional reason for promotion
            
        Returns:
            True if promoted successfully
        """
        evo_data = self.store.get_evolution_data(entry_id)
        
        if evo_data.get("archived", False):
            return False  # Can't promote archived
        
        current_score = evo_data.get("promotion_score", 0.0)
        new_score = min(current_score + self.PROMOTION_BOOST * 2, 1.0)  # Double boost
        
        self.store.update_evolution_data(entry_id, {
            "promotion_score": new_score,
            "last_accessed": datetime.now().isoformat(),
        })
        
        logger.info(f"Manually promoted memory {entry_id}: {reason}")
        return True
    
    async def archive_expired(self, days: int | None = None) -> list[str]:
        """
        Archive memories not accessed in N days.
        
        Args:
            days: Override ARCHIVE_INACTIVE_DAYS
            
        Returns:
            List of archived entry IDs
        """
        original = self.ARCHIVE_INACTIVE_DAYS
        if days is not None:
            self.ARCHIVE_INACTIVE_DAYS = days
        
        try:
            return await self._run_archive(dry_run=False)
        finally:
            self.ARCHIVE_INACTIVE_DAYS = original
    
    async def cross_reference(self, entry_id: str) -> list[str]:
        """
        Find and create cross-references for a specific entry.
        
        Args:
            entry_id: Entry to cross-reference
            
        Returns:
            List of related entry IDs
        """
        entries = self.store.get_all_entries()
        target = None
        
        for e in entries:
            if e.id == entry_id:
                target = e
                break
        
        if not target:
            return []
        
        related = []
        evo_data = self.store.get_evolution_data(entry_id)
        existing_refs = set(evo_data.get("cross_references", []))
        
        # Tag-based
        if target.tags:
            target_tags = set(target.tags)
            for other in entries:
                if other.id == entry_id or other.id in existing_refs:
                    continue
                if other.tags and len(set(other.tags) & target_tags) >= 1:
                    self.store.add_cross_reference(entry_id, other.id)
                    related.append(other.id)
        
        # Vector-based
        if self.vector_store and hasattr(self.vector_store, 'find_similar'):
            try:
                similar = await self.vector_store.find_similar(
                    target.content,
                    k=5,
                    threshold=0.6
                )
                for sim_entry, score in similar:
                    if sim_entry.id != entry_id and sim_entry.id not in existing_refs:
                        self.store.add_cross_reference(entry_id, sim_entry.id)
                        related.append(sim_entry.id)
            except Exception:
                pass
        
        return related
    
    def get_stats(self) -> dict[str, Any]:
        """Get evolution statistics."""
        store_stats = self.store.get_memory_stats()
        
        # Add evolution-specific stats
        entries = self.store.get_all_entries()
        
        promoted_count = 0
        decayed_count = 0
        
        for entry in entries:
            evo = self.store.get_evolution_data(entry.id)
            score = evo.get("promotion_score", 0.0)
            if score > 0.1:
                promoted_count += 1
            elif score < -0.1:
                decayed_count += 1
        
        return {
            **store_stats,
            "promoted_memories": promoted_count,
            "decayed_memories": decayed_count,
            "evolution_enabled": True,
        }
