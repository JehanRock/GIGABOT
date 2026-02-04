"""
Proactive Action types and data structures.

Defines the different types of proactive actions:
- Reminder: Time-based prompts
- Suggestion: Pattern-based recommendations
- Automation: Pre-approved recurring tasks
- Insight: Discovered patterns
- Anticipation: Predicted needs
"""

import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Any
from enum import Enum


class ActionType(str, Enum):
    """Types of proactive actions."""
    REMINDER = "reminder"           # Time-based prompts
    SUGGESTION = "suggestion"       # Pattern-based recommendations
    AUTOMATION = "automation"       # Pre-approved recurring tasks
    INSIGHT = "insight"             # Discovered patterns
    ANTICIPATION = "anticipation"   # Predicted needs


class ActionStatus(str, Enum):
    """Status of a proactive action."""
    PENDING = "pending"             # Created, not yet delivered
    DELIVERED = "delivered"         # Sent to user
    ACCEPTED = "accepted"           # User accepted/acted on it
    DISMISSED = "dismissed"         # User dismissed it
    EXPIRED = "expired"             # Expired before action
    EXECUTED = "executed"           # Automation was executed


class TriggerSource(str, Enum):
    """Source that triggered the action."""
    SCHEDULE = "schedule"           # Cron/time-based trigger
    PATTERN = "pattern"             # From IntentTracker patterns
    EVENT = "event"                 # Event-based (e.g., session start)
    PREDICTION = "prediction"       # From intent prediction
    MEMORY = "memory"               # From memory evolution insights
    MANUAL = "manual"               # Manually created


@dataclass
class ProactiveAction:
    """
    A proactive action to be delivered to the user.
    
    Attributes:
        id: Unique identifier
        type: Type of action (reminder, suggestion, etc.)
        trigger_source: What triggered this action
        priority: Priority level (0.0-1.0, higher = more important)
        title: Short title for the action
        content: Full content/message
        context: Additional context data
        requires_confirmation: Whether user must confirm before execution
        user_id: Target user
        channel: Target channel for delivery
        chat_id: Target chat for delivery
        created_at: When the action was created
        expires_at: When the action expires
        delivered_at: When the action was delivered
        status: Current status
        metadata: Additional metadata
    """
    id: str
    type: ActionType
    trigger_source: str
    priority: float
    title: str
    content: str
    user_id: str
    context: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = True
    channel: str | None = None
    chat_id: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    delivered_at: datetime | None = None
    resolved_at: datetime | None = None
    status: ActionStatus = ActionStatus.PENDING
    feedback: str = ""  # User feedback if any
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "trigger_source": self.trigger_source,
            "priority": self.priority,
            "title": self.title,
            "content": self.content,
            "user_id": self.user_id,
            "context": self.context,
            "requires_confirmation": self.requires_confirmation,
            "channel": self.channel,
            "chat_id": self.chat_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "status": self.status.value,
            "feedback": self.feedback,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProactiveAction":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            type=ActionType(data["type"]),
            trigger_source=data["trigger_source"],
            priority=data["priority"],
            title=data["title"],
            content=data["content"],
            user_id=data["user_id"],
            context=data.get("context", {}),
            requires_confirmation=data.get("requires_confirmation", True),
            channel=data.get("channel"),
            chat_id=data.get("chat_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None,
            delivered_at=datetime.fromisoformat(data["delivered_at"]) if data.get("delivered_at") else None,
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            status=ActionStatus(data.get("status", "pending")),
            feedback=data.get("feedback", ""),
            metadata=data.get("metadata", {}),
        )
    
    def is_expired(self) -> bool:
        """Check if action has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def mark_delivered(self) -> None:
        """Mark action as delivered."""
        self.delivered_at = datetime.now()
        self.status = ActionStatus.DELIVERED
    
    def mark_accepted(self, feedback: str = "") -> None:
        """Mark action as accepted by user."""
        self.resolved_at = datetime.now()
        self.status = ActionStatus.ACCEPTED
        self.feedback = feedback
    
    def mark_dismissed(self, feedback: str = "") -> None:
        """Mark action as dismissed by user."""
        self.resolved_at = datetime.now()
        self.status = ActionStatus.DISMISSED
        self.feedback = feedback
    
    def mark_executed(self, result: str = "") -> None:
        """Mark automation as executed."""
        self.resolved_at = datetime.now()
        self.status = ActionStatus.EXECUTED
        self.feedback = result
    
    def mark_expired(self) -> None:
        """Mark action as expired."""
        self.resolved_at = datetime.now()
        self.status = ActionStatus.EXPIRED


def create_reminder(
    title: str,
    content: str,
    user_id: str,
    remind_at: datetime,
    channel: str | None = None,
    chat_id: str | None = None,
    priority: float = 0.7,
) -> ProactiveAction:
    """
    Create a reminder action.
    
    Args:
        title: Reminder title
        content: Reminder content
        user_id: Target user
        remind_at: When to remind
        channel: Delivery channel
        chat_id: Delivery chat
        priority: Priority level
        
    Returns:
        ProactiveAction configured as a reminder
    """
    return ProactiveAction(
        id=str(uuid.uuid4()),
        type=ActionType.REMINDER,
        trigger_source=TriggerSource.SCHEDULE.value,
        priority=priority,
        title=title,
        content=content,
        user_id=user_id,
        channel=channel,
        chat_id=chat_id,
        requires_confirmation=False,  # Reminders don't need confirmation
        expires_at=remind_at + timedelta(hours=1),  # Expire 1 hour after scheduled time
        metadata={"remind_at": remind_at.isoformat()},
    )


def create_suggestion(
    title: str,
    content: str,
    user_id: str,
    pattern_id: str | None = None,
    confidence: float = 0.5,
    channel: str | None = None,
    chat_id: str | None = None,
) -> ProactiveAction:
    """
    Create a suggestion action based on patterns.
    
    Args:
        title: Suggestion title
        content: Suggestion content
        user_id: Target user
        pattern_id: ID of pattern that triggered this
        confidence: Confidence level
        channel: Delivery channel
        chat_id: Delivery chat
        
    Returns:
        ProactiveAction configured as a suggestion
    """
    return ProactiveAction(
        id=str(uuid.uuid4()),
        type=ActionType.SUGGESTION,
        trigger_source=TriggerSource.PATTERN.value,
        priority=confidence,
        title=title,
        content=content,
        user_id=user_id,
        channel=channel,
        chat_id=chat_id,
        requires_confirmation=True,
        expires_at=datetime.now() + timedelta(hours=24),  # Expire in 24 hours
        metadata={"pattern_id": pattern_id, "confidence": confidence},
    )


def create_insight(
    title: str,
    content: str,
    user_id: str,
    insight_type: str = "pattern",
    data: dict[str, Any] | None = None,
    channel: str | None = None,
    chat_id: str | None = None,
) -> ProactiveAction:
    """
    Create an insight action.
    
    Args:
        title: Insight title
        content: Insight content
        user_id: Target user
        insight_type: Type of insight
        data: Supporting data
        channel: Delivery channel
        chat_id: Delivery chat
        
    Returns:
        ProactiveAction configured as an insight
    """
    return ProactiveAction(
        id=str(uuid.uuid4()),
        type=ActionType.INSIGHT,
        trigger_source=TriggerSource.MEMORY.value,
        priority=0.5,  # Medium priority for insights
        title=title,
        content=content,
        user_id=user_id,
        channel=channel,
        chat_id=chat_id,
        requires_confirmation=False,  # Insights are informational
        expires_at=datetime.now() + timedelta(days=7),  # Expire in 7 days
        metadata={"insight_type": insight_type, "data": data or {}},
    )


def create_automation(
    title: str,
    content: str,
    user_id: str,
    task: str,
    require_confirmation: bool = True,
    channel: str | None = None,
    chat_id: str | None = None,
) -> ProactiveAction:
    """
    Create an automation action.
    
    Args:
        title: Automation title
        content: Automation description
        user_id: Target user
        task: Task identifier to execute
        require_confirmation: Whether to require user confirmation
        channel: Delivery channel
        chat_id: Delivery chat
        
    Returns:
        ProactiveAction configured as an automation
    """
    return ProactiveAction(
        id=str(uuid.uuid4()),
        type=ActionType.AUTOMATION,
        trigger_source=TriggerSource.SCHEDULE.value,
        priority=0.8,  # High priority for automations
        title=title,
        content=content,
        user_id=user_id,
        channel=channel,
        chat_id=chat_id,
        requires_confirmation=require_confirmation,
        expires_at=datetime.now() + timedelta(hours=1),  # Short expiry for automations
        metadata={"task": task},
    )


def create_anticipation(
    title: str,
    content: str,
    user_id: str,
    predicted_intent: str,
    confidence: float = 0.5,
    channel: str | None = None,
    chat_id: str | None = None,
) -> ProactiveAction:
    """
    Create an anticipation action based on predicted needs.
    
    Args:
        title: Anticipation title
        content: Anticipation content
        user_id: Target user
        predicted_intent: The predicted intent
        confidence: Prediction confidence
        channel: Delivery channel
        chat_id: Delivery chat
        
    Returns:
        ProactiveAction configured as an anticipation
    """
    return ProactiveAction(
        id=str(uuid.uuid4()),
        type=ActionType.ANTICIPATION,
        trigger_source=TriggerSource.PREDICTION.value,
        priority=confidence,
        title=title,
        content=content,
        user_id=user_id,
        channel=channel,
        chat_id=chat_id,
        requires_confirmation=True,
        expires_at=datetime.now() + timedelta(hours=12),  # Expire in 12 hours
        metadata={"predicted_intent": predicted_intent, "confidence": confidence},
    )
