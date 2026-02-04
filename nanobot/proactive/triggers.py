"""
Trigger management for Proactive Engine.

Supports different trigger types:
- Schedule: Cron expressions for time-based triggers
- Pattern: Triggered by IntentTracker patterns
- Event: Triggered by system events
"""

import json
import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any
from enum import Enum

try:
    from croniter import croniter
    HAS_CRONITER = True
except ImportError:
    HAS_CRONITER = False


class TriggerType(str, Enum):
    """Types of triggers."""
    SCHEDULE = "schedule"       # Cron-based
    PATTERN = "pattern"         # Pattern-based (from IntentTracker)
    EVENT = "event"             # Event-based


class EventType(str, Enum):
    """Types of events that can trigger actions."""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    MEMORY_ACCESS = "memory_access"
    HIGH_USAGE = "high_usage"
    LOW_ACTIVITY = "low_activity"
    PATTERN_DETECTED = "pattern_detected"


@dataclass
class Trigger:
    """
    A trigger that can generate proactive actions.
    
    Attributes:
        id: Unique identifier
        name: Human-readable name
        type: Type of trigger
        condition: The trigger condition
            - For schedule: cron expression
            - For pattern: pattern type or name
            - For event: event type
        action_template: Template for generating action
        enabled: Whether the trigger is active
        user_id: User this trigger belongs to (empty = global)
        last_fired: When the trigger last fired
        fire_count: Number of times fired
    """
    id: str
    name: str
    type: TriggerType
    condition: str
    action_template: dict[str, Any]
    enabled: bool = True
    user_id: str = ""  # Empty = global trigger
    last_fired: datetime | None = None
    fire_count: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "condition": self.condition,
            "action_template": self.action_template,
            "enabled": self.enabled,
            "user_id": self.user_id,
            "last_fired": self.last_fired.isoformat() if self.last_fired else None,
            "fire_count": self.fire_count,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Trigger":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            type=TriggerType(data["type"]),
            condition=data["condition"],
            action_template=data["action_template"],
            enabled=data.get("enabled", True),
            user_id=data.get("user_id", ""),
            last_fired=datetime.fromisoformat(data["last_fired"]) if data.get("last_fired") else None,
            fire_count=data.get("fire_count", 0),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            metadata=data.get("metadata", {}),
        )


class TriggerManager:
    """
    Manages proactive triggers.
    
    Handles:
    - Trigger storage and retrieval
    - Checking due triggers
    - Pattern and event matching
    """
    
    def __init__(self, storage_path: Path):
        """
        Initialize the trigger manager.
        
        Args:
            storage_path: Path to store triggers
        """
        self.storage_path = storage_path
        self.triggers_file = storage_path / "triggers.json"
        
        self._triggers: dict[str, Trigger] = {}
        self._load_triggers()
    
    def _load_triggers(self) -> None:
        """Load triggers from storage."""
        if not self.triggers_file.exists():
            return
        
        try:
            data = json.loads(self.triggers_file.read_text())
            for trigger_data in data.get("triggers", []):
                trigger = Trigger.from_dict(trigger_data)
                self._triggers[trigger.id] = trigger
        except (json.JSONDecodeError, KeyError):
            pass  # Start fresh on error
    
    def _save_triggers(self) -> None:
        """Save triggers to storage."""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        data = {
            "triggers": [t.to_dict() for t in self._triggers.values()]
        }
        self.triggers_file.write_text(json.dumps(data, indent=2))
    
    def add_trigger(self, trigger: Trigger) -> str:
        """
        Add a new trigger.
        
        Args:
            trigger: The trigger to add
            
        Returns:
            Trigger ID
        """
        if not trigger.id:
            trigger.id = str(uuid.uuid4())[:8]
        
        self._triggers[trigger.id] = trigger
        self._save_triggers()
        
        return trigger.id
    
    def remove_trigger(self, trigger_id: str) -> bool:
        """
        Remove a trigger.
        
        Args:
            trigger_id: ID of trigger to remove
            
        Returns:
            True if removed
        """
        if trigger_id in self._triggers:
            del self._triggers[trigger_id]
            self._save_triggers()
            return True
        return False
    
    def get_trigger(self, trigger_id: str) -> Trigger | None:
        """Get a trigger by ID."""
        return self._triggers.get(trigger_id)
    
    def list_triggers(
        self,
        user_id: str | None = None,
        trigger_type: TriggerType | None = None,
        enabled_only: bool = True,
    ) -> list[Trigger]:
        """
        List triggers with optional filtering.
        
        Args:
            user_id: Filter by user (None = all)
            trigger_type: Filter by type (None = all)
            enabled_only: Only return enabled triggers
            
        Returns:
            List of matching triggers
        """
        triggers = list(self._triggers.values())
        
        if user_id is not None:
            triggers = [t for t in triggers if t.user_id == user_id or t.user_id == ""]
        
        if trigger_type is not None:
            triggers = [t for t in triggers if t.type == trigger_type]
        
        if enabled_only:
            triggers = [t for t in triggers if t.enabled]
        
        return triggers
    
    def enable_trigger(self, trigger_id: str, enabled: bool = True) -> bool:
        """Enable or disable a trigger."""
        if trigger_id in self._triggers:
            self._triggers[trigger_id].enabled = enabled
            self._save_triggers()
            return True
        return False
    
    def check_schedule_triggers(self) -> list[Trigger]:
        """
        Check which schedule triggers are due.
        
        Returns:
            List of due triggers
        """
        if not HAS_CRONITER:
            return []
        
        due_triggers = []
        now = datetime.now()
        
        for trigger in self._triggers.values():
            if not trigger.enabled or trigger.type != TriggerType.SCHEDULE:
                continue
            
            try:
                cron = croniter(trigger.condition, trigger.last_fired or trigger.created_at)
                next_time = datetime.fromtimestamp(cron.get_next())
                
                if next_time <= now:
                    due_triggers.append(trigger)
            except Exception:
                continue  # Invalid cron expression
        
        return due_triggers
    
    def check_pattern_trigger(
        self,
        pattern_type: str,
        pattern_name: str = "",
        user_id: str = "",
    ) -> list[Trigger]:
        """
        Check which pattern triggers match.
        
        Args:
            pattern_type: Type of pattern (e.g., "recurring_task")
            pattern_name: Optional pattern name
            user_id: User ID for user-specific triggers
            
        Returns:
            List of matching triggers
        """
        matching = []
        
        for trigger in self._triggers.values():
            if not trigger.enabled or trigger.type != TriggerType.PATTERN:
                continue
            
            # Check user scope
            if trigger.user_id and trigger.user_id != user_id:
                continue
            
            # Check condition match
            condition = trigger.condition.lower()
            if condition == pattern_type.lower():
                matching.append(trigger)
            elif pattern_name and condition == pattern_name.lower():
                matching.append(trigger)
            elif condition == "*":  # Wildcard - match all patterns
                matching.append(trigger)
        
        return matching
    
    def check_event_trigger(
        self,
        event_type: str,
        user_id: str = "",
    ) -> list[Trigger]:
        """
        Check which event triggers match.
        
        Args:
            event_type: Type of event
            user_id: User ID for user-specific triggers
            
        Returns:
            List of matching triggers
        """
        matching = []
        
        for trigger in self._triggers.values():
            if not trigger.enabled or trigger.type != TriggerType.EVENT:
                continue
            
            # Check user scope
            if trigger.user_id and trigger.user_id != user_id:
                continue
            
            # Check condition match
            if trigger.condition.lower() == event_type.lower():
                matching.append(trigger)
        
        return matching
    
    def mark_fired(self, trigger_id: str) -> None:
        """Mark a trigger as having fired."""
        if trigger_id in self._triggers:
            trigger = self._triggers[trigger_id]
            trigger.last_fired = datetime.now()
            trigger.fire_count += 1
            self._save_triggers()
    
    def get_stats(self) -> dict[str, Any]:
        """Get trigger statistics."""
        triggers = list(self._triggers.values())
        
        by_type = {}
        for t in triggers:
            by_type[t.type.value] = by_type.get(t.type.value, 0) + 1
        
        enabled = sum(1 for t in triggers if t.enabled)
        total_fires = sum(t.fire_count for t in triggers)
        
        return {
            "total_triggers": len(triggers),
            "enabled_triggers": enabled,
            "by_type": by_type,
            "total_fires": total_fires,
        }


def create_schedule_trigger(
    name: str,
    cron_expr: str,
    action_template: dict[str, Any],
    user_id: str = "",
) -> Trigger:
    """
    Create a schedule-based trigger.
    
    Args:
        name: Trigger name
        cron_expr: Cron expression
        action_template: Template for action generation
        user_id: User scope (empty = global)
        
    Returns:
        Configured trigger
    """
    return Trigger(
        id=str(uuid.uuid4())[:8],
        name=name,
        type=TriggerType.SCHEDULE,
        condition=cron_expr,
        action_template=action_template,
        user_id=user_id,
    )


def create_pattern_trigger(
    name: str,
    pattern_type: str,
    action_template: dict[str, Any],
    user_id: str = "",
) -> Trigger:
    """
    Create a pattern-based trigger.
    
    Args:
        name: Trigger name
        pattern_type: Pattern type to match
        action_template: Template for action generation
        user_id: User scope (empty = global)
        
    Returns:
        Configured trigger
    """
    return Trigger(
        id=str(uuid.uuid4())[:8],
        name=name,
        type=TriggerType.PATTERN,
        condition=pattern_type,
        action_template=action_template,
        user_id=user_id,
    )


def create_event_trigger(
    name: str,
    event_type: str,
    action_template: dict[str, Any],
    user_id: str = "",
) -> Trigger:
    """
    Create an event-based trigger.
    
    Args:
        name: Trigger name
        event_type: Event type to match
        action_template: Template for action generation
        user_id: User scope (empty = global)
        
    Returns:
        Configured trigger
    """
    return Trigger(
        id=str(uuid.uuid4())[:8],
        name=name,
        type=TriggerType.EVENT,
        condition=event_type,
        action_template=action_template,
        user_id=user_id,
    )
