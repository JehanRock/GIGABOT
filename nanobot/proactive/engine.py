"""
Proactive Engine for GigaBot.

Generates and manages proactive actions by:
1. Checking triggers (schedule, pattern, event)
2. Generating suggestions from patterns
3. Generating insights from memory
4. Executing approved automations
5. Learning from user feedback
"""

import json
import uuid
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, TYPE_CHECKING
from dataclasses import dataclass, field

from nanobot.proactive.actions import (
    ProactiveAction,
    ActionType,
    ActionStatus,
    TriggerSource,
    create_suggestion,
    create_insight,
    create_anticipation,
    create_reminder,
    create_automation,
)
from nanobot.proactive.triggers import (
    Trigger,
    TriggerType,
    TriggerManager,
)

if TYPE_CHECKING:
    from nanobot.intent.tracker import IntentTracker, PatternInsight, PredictedIntent
    from nanobot.memory.evolution import MemoryEvolution
    from nanobot.providers.base import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class FeedbackStats:
    """Statistics about action feedback."""
    total_delivered: int = 0
    total_accepted: int = 0
    total_dismissed: int = 0
    total_expired: int = 0
    
    # By action type
    by_type: dict[str, dict[str, int]] = field(default_factory=dict)
    
    @property
    def acceptance_rate(self) -> float:
        """Calculate overall acceptance rate."""
        resolved = self.total_accepted + self.total_dismissed
        if resolved == 0:
            return 0.5  # Default when no data
        return self.total_accepted / resolved
    
    def acceptance_rate_by_type(self, action_type: str) -> float:
        """Get acceptance rate for a specific action type."""
        type_stats = self.by_type.get(action_type, {})
        accepted = type_stats.get("accepted", 0)
        dismissed = type_stats.get("dismissed", 0)
        resolved = accepted + dismissed
        if resolved == 0:
            return 0.5
        return accepted / resolved


class ProactiveEngine:
    """
    Generates and manages proactive actions.
    
    Features:
    - Trigger-based action generation
    - Pattern-based suggestions
    - Memory-based insights
    - Intent-based anticipation
    - Feedback learning
    """
    
    def __init__(
        self,
        workspace: Path,
        intent_tracker: "IntentTracker | None" = None,
        memory_evolution: "MemoryEvolution | None" = None,
        provider: "LLMProvider | None" = None,
        max_daily_actions: int = 10,
        require_confirmation: bool = True,
        enable_reminders: bool = True,
        enable_suggestions: bool = True,
        enable_automation: bool = False,
        enable_insights: bool = True,
        enable_anticipation: bool = True,
        min_acceptance_rate: float = 0.3,
        automation_allowlist: list[str] | None = None,
    ):
        """
        Initialize the proactive engine.
        
        Args:
            workspace: Workspace path for storage
            intent_tracker: IntentTracker for patterns/predictions
            memory_evolution: MemoryEvolution for insights
            provider: LLM provider for generation
            max_daily_actions: Max actions per day per user
            require_confirmation: Default confirmation requirement
            enable_*: Enable specific action types
            min_acceptance_rate: Stop suggesting if below this
            automation_allowlist: Tasks allowed for automation
        """
        self.workspace = workspace
        self.intent_tracker = intent_tracker
        self.memory_evolution = memory_evolution
        self.provider = provider
        
        # Configuration
        self.max_daily_actions = max_daily_actions
        self.require_confirmation = require_confirmation
        self.enable_reminders = enable_reminders
        self.enable_suggestions = enable_suggestions
        self.enable_automation = enable_automation
        self.enable_insights = enable_insights
        self.enable_anticipation = enable_anticipation
        self.min_acceptance_rate = min_acceptance_rate
        self.automation_allowlist = automation_allowlist or []
        
        # Storage
        self.storage_dir = workspace / "proactive"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.actions_file = self.storage_dir / "actions.json"
        self.stats_file = self.storage_dir / "stats.json"
        
        # Trigger manager
        self.trigger_manager = TriggerManager(self.storage_dir)
        
        # In-memory state
        self._actions: dict[str, ProactiveAction] = {}
        self._stats = FeedbackStats()
        self._daily_counts: dict[str, int] = {}  # user_id -> count today
        
        self._load()
    
    def _load(self) -> None:
        """Load actions and stats from storage."""
        # Load actions
        if self.actions_file.exists():
            try:
                data = json.loads(self.actions_file.read_text())
                for action_data in data.get("actions", []):
                    action = ProactiveAction.from_dict(action_data)
                    self._actions[action.id] = action
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Load stats
        if self.stats_file.exists():
            try:
                data = json.loads(self.stats_file.read_text())
                self._stats.total_delivered = data.get("total_delivered", 0)
                self._stats.total_accepted = data.get("total_accepted", 0)
                self._stats.total_dismissed = data.get("total_dismissed", 0)
                self._stats.total_expired = data.get("total_expired", 0)
                self._stats.by_type = data.get("by_type", {})
            except (json.JSONDecodeError, KeyError):
                pass
    
    def _save(self) -> None:
        """Save actions and stats to storage."""
        # Save actions (only keep recent ones)
        recent_actions = [
            a for a in self._actions.values()
            if (datetime.now() - a.created_at).days < 30
        ]
        
        data = {
            "actions": [a.to_dict() for a in recent_actions]
        }
        self.actions_file.write_text(json.dumps(data, indent=2))
        
        # Save stats
        stats_data = {
            "total_delivered": self._stats.total_delivered,
            "total_accepted": self._stats.total_accepted,
            "total_dismissed": self._stats.total_dismissed,
            "total_expired": self._stats.total_expired,
            "by_type": self._stats.by_type,
        }
        self.stats_file.write_text(json.dumps(stats_data, indent=2))
    
    def _can_create_action(self, user_id: str, action_type: ActionType) -> bool:
        """Check if we can create more actions for this user/type."""
        # Check daily limit
        today = datetime.now().strftime("%Y-%m-%d")
        count_key = f"{user_id}:{today}"
        
        if self._daily_counts.get(count_key, 0) >= self.max_daily_actions:
            logger.debug(f"Daily action limit reached for {user_id}")
            return False
        
        # Check acceptance rate for this type
        rate = self._stats.acceptance_rate_by_type(action_type.value)
        if rate < self.min_acceptance_rate:
            logger.debug(f"Acceptance rate too low for {action_type.value}: {rate:.1%}")
            return False
        
        return True
    
    def _increment_daily_count(self, user_id: str) -> None:
        """Increment daily action count for user."""
        today = datetime.now().strftime("%Y-%m-%d")
        count_key = f"{user_id}:{today}"
        self._daily_counts[count_key] = self._daily_counts.get(count_key, 0) + 1
    
    async def check_triggers(self) -> list[ProactiveAction]:
        """
        Check all triggers and generate actions.
        
        Returns:
            List of generated actions
        """
        actions = []
        
        # Check schedule triggers
        due_triggers = self.trigger_manager.check_schedule_triggers()
        for trigger in due_triggers:
            action = self._generate_from_trigger(trigger)
            if action:
                actions.append(action)
                self.trigger_manager.mark_fired(trigger.id)
        
        return actions
    
    def _generate_from_trigger(self, trigger: Trigger) -> ProactiveAction | None:
        """Generate an action from a trigger template."""
        template = trigger.action_template
        user_id = trigger.user_id or "default"
        
        # Check if action type is enabled
        action_type_str = template.get("type", "suggestion")
        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            action_type = ActionType.SUGGESTION
        
        if not self._is_type_enabled(action_type):
            return None
        
        if not self._can_create_action(user_id, action_type):
            return None
        
        action = ProactiveAction(
            id=str(uuid.uuid4()),
            type=action_type,
            trigger_source=TriggerSource.SCHEDULE.value,
            priority=template.get("priority", 0.5),
            title=template.get("title", trigger.name),
            content=template.get("content", ""),
            user_id=user_id,
            channel=template.get("channel"),
            chat_id=template.get("chat_id"),
            requires_confirmation=template.get("requires_confirmation", self.require_confirmation),
            expires_at=datetime.now() + timedelta(hours=template.get("expires_hours", 24)),
        )
        
        self._actions[action.id] = action
        self._increment_daily_count(user_id)
        self._save()
        
        return action
    
    def _is_type_enabled(self, action_type: ActionType) -> bool:
        """Check if an action type is enabled."""
        mapping = {
            ActionType.REMINDER: self.enable_reminders,
            ActionType.SUGGESTION: self.enable_suggestions,
            ActionType.AUTOMATION: self.enable_automation,
            ActionType.INSIGHT: self.enable_insights,
            ActionType.ANTICIPATION: self.enable_anticipation,
        }
        return mapping.get(action_type, False)
    
    async def generate_suggestions(self, user_id: str = "default") -> list[ProactiveAction]:
        """
        Generate suggestions based on patterns.
        
        Args:
            user_id: User to generate for
            
        Returns:
            List of suggestion actions
        """
        if not self.enable_suggestions or not self.intent_tracker:
            return []
        
        if not self._can_create_action(user_id, ActionType.SUGGESTION):
            return []
        
        suggestions = []
        
        # Get patterns from IntentTracker
        try:
            patterns = self.intent_tracker._load_patterns()
            
            for pattern in patterns[:3]:  # Max 3 suggestions at once
                if pattern.confidence < 0.5:
                    continue
                
                # Create suggestion from pattern
                action = create_suggestion(
                    title=f"Pattern: {pattern.pattern_type}",
                    content=pattern.description,
                    user_id=user_id,
                    pattern_id=pattern.id,
                    confidence=pattern.confidence,
                )
                
                self._actions[action.id] = action
                self._increment_daily_count(user_id)
                suggestions.append(action)
        except Exception as e:
            logger.warning(f"Failed to generate suggestions: {e}")
        
        if suggestions:
            self._save()
        
        return suggestions
    
    async def generate_insights(self, user_id: str = "default") -> list[ProactiveAction]:
        """
        Generate insights from memory evolution.
        
        Args:
            user_id: User to generate for
            
        Returns:
            List of insight actions
        """
        if not self.enable_insights or not self.memory_evolution:
            return []
        
        if not self._can_create_action(user_id, ActionType.INSIGHT):
            return []
        
        insights = []
        
        try:
            stats = self.memory_evolution.get_stats()
            
            # Generate insight if there are promoted memories
            if stats.get("promoted_memories", 0) > 5:
                action = create_insight(
                    title="Memory Growth",
                    content=f"You have {stats['promoted_memories']} actively used memories. Your most important topics are being tracked.",
                    user_id=user_id,
                    insight_type="memory_growth",
                    data={"promoted": stats["promoted_memories"]},
                )
                self._actions[action.id] = action
                self._increment_daily_count(user_id)
                insights.append(action)
            
            # Generate insight if there are decayed memories
            if stats.get("decayed_memories", 0) > 10:
                action = create_insight(
                    title="Memory Cleanup",
                    content=f"{stats['decayed_memories']} memories have been deprioritized due to low access. Consider archiving old content.",
                    user_id=user_id,
                    insight_type="memory_decay",
                    data={"decayed": stats["decayed_memories"]},
                )
                self._actions[action.id] = action
                self._increment_daily_count(user_id)
                insights.append(action)
        except Exception as e:
            logger.warning(f"Failed to generate insights: {e}")
        
        if insights:
            self._save()
        
        return insights
    
    async def generate_anticipations(self, user_id: str = "default") -> list[ProactiveAction]:
        """
        Generate anticipation actions from intent predictions.
        
        Args:
            user_id: User to generate for
            
        Returns:
            List of anticipation actions
        """
        if not self.enable_anticipation or not self.intent_tracker:
            return []
        
        if not self._can_create_action(user_id, ActionType.ANTICIPATION):
            return []
        
        anticipations = []
        
        try:
            predictions = await self.intent_tracker.predict_next_intent(user_id)
            
            for pred in predictions[:2]:  # Max 2 anticipations
                if pred.confidence < 0.6:
                    continue
                
                action = create_anticipation(
                    title=f"Anticipated: {pred.predicted_goal[:50]}",
                    content=f"Based on your patterns, you might want to: {pred.predicted_goal}\n\nReasoning: {pred.reasoning}",
                    user_id=user_id,
                    predicted_intent=pred.predicted_goal,
                    confidence=pred.confidence,
                )
                
                self._actions[action.id] = action
                self._increment_daily_count(user_id)
                anticipations.append(action)
        except Exception as e:
            logger.warning(f"Failed to generate anticipations: {e}")
        
        if anticipations:
            self._save()
        
        return anticipations
    
    async def execute_automation(self, action: ProactiveAction) -> str | None:
        """
        Execute an automation action.
        
        Args:
            action: The automation action to execute
            
        Returns:
            Result of execution, or None if failed
        """
        if action.type != ActionType.AUTOMATION:
            return None
        
        if not self.enable_automation:
            return None
        
        # Check if task is in allowlist
        task = action.metadata.get("task", "")
        if task and task not in self.automation_allowlist:
            logger.warning(f"Automation task not in allowlist: {task}")
            return None
        
        # Execute (placeholder - would integrate with agent loop)
        logger.info(f"Executing automation: {action.title}")
        
        # Mark as executed
        action.mark_executed("Automation executed")
        self._update_stats(action)
        self._save()
        
        return "Automation completed"
    
    def deliver_action(
        self,
        action_id: str,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> bool:
        """
        Mark an action as delivered.
        
        Args:
            action_id: ID of action to deliver
            channel: Delivery channel
            chat_id: Delivery chat
            
        Returns:
            True if delivered
        """
        action = self._actions.get(action_id)
        if not action:
            return False
        
        action.mark_delivered()
        if channel:
            action.channel = channel
        if chat_id:
            action.chat_id = chat_id
        
        self._stats.total_delivered += 1
        self._save()
        
        return True
    
    def mark_accepted(self, action_id: str, feedback: str = "") -> bool:
        """Mark an action as accepted."""
        action = self._actions.get(action_id)
        if not action:
            return False
        
        action.mark_accepted(feedback)
        self._update_stats(action)
        self._save()
        
        return True
    
    def mark_dismissed(self, action_id: str, feedback: str = "") -> bool:
        """Mark an action as dismissed."""
        action = self._actions.get(action_id)
        if not action:
            return False
        
        action.mark_dismissed(feedback)
        self._update_stats(action)
        self._save()
        
        return True
    
    def _update_stats(self, action: ProactiveAction) -> None:
        """Update feedback statistics."""
        action_type = action.type.value
        
        if action_type not in self._stats.by_type:
            self._stats.by_type[action_type] = {
                "delivered": 0,
                "accepted": 0,
                "dismissed": 0,
                "expired": 0,
            }
        
        type_stats = self._stats.by_type[action_type]
        
        if action.status == ActionStatus.ACCEPTED:
            self._stats.total_accepted += 1
            type_stats["accepted"] += 1
        elif action.status == ActionStatus.DISMISSED:
            self._stats.total_dismissed += 1
            type_stats["dismissed"] += 1
        elif action.status == ActionStatus.EXPIRED:
            self._stats.total_expired += 1
            type_stats["expired"] += 1
    
    def expire_old_actions(self) -> int:
        """Expire actions past their expiration date."""
        expired_count = 0
        
        for action in self._actions.values():
            if action.status == ActionStatus.PENDING and action.is_expired():
                action.mark_expired()
                self._update_stats(action)
                expired_count += 1
        
        if expired_count:
            self._save()
        
        return expired_count
    
    def get_pending_actions(
        self,
        user_id: str | None = None,
        action_type: ActionType | None = None,
    ) -> list[ProactiveAction]:
        """
        Get pending actions.
        
        Args:
            user_id: Filter by user
            action_type: Filter by type
            
        Returns:
            List of pending actions
        """
        # First expire old actions
        self.expire_old_actions()
        
        actions = [
            a for a in self._actions.values()
            if a.status in (ActionStatus.PENDING, ActionStatus.DELIVERED)
        ]
        
        if user_id:
            actions = [a for a in actions if a.user_id == user_id]
        
        if action_type:
            actions = [a for a in actions if a.type == action_type]
        
        # Sort by priority
        actions.sort(key=lambda a: a.priority, reverse=True)
        
        return actions
    
    def get_action(self, action_id: str) -> ProactiveAction | None:
        """Get an action by ID."""
        return self._actions.get(action_id)
    
    def get_action_stats(self) -> dict[str, Any]:
        """Get comprehensive action statistics."""
        pending = len([a for a in self._actions.values() if a.status == ActionStatus.PENDING])
        
        return {
            "total_actions": len(self._actions),
            "pending_actions": pending,
            "total_delivered": self._stats.total_delivered,
            "total_accepted": self._stats.total_accepted,
            "total_dismissed": self._stats.total_dismissed,
            "total_expired": self._stats.total_expired,
            "acceptance_rate": f"{self._stats.acceptance_rate:.1%}",
            "by_type": {
                k: {
                    "acceptance_rate": f"{self._stats.acceptance_rate_by_type(k):.1%}",
                    **v
                }
                for k, v in self._stats.by_type.items()
            },
            "triggers": self.trigger_manager.get_stats(),
        }
    
    def get_status(self) -> dict[str, Any]:
        """Get engine status."""
        return {
            "enabled_types": {
                "reminders": self.enable_reminders,
                "suggestions": self.enable_suggestions,
                "automation": self.enable_automation,
                "insights": self.enable_insights,
                "anticipation": self.enable_anticipation,
            },
            "max_daily_actions": self.max_daily_actions,
            "require_confirmation": self.require_confirmation,
            "min_acceptance_rate": self.min_acceptance_rate,
            "automation_allowlist": self.automation_allowlist,
            "has_intent_tracker": self.intent_tracker is not None,
            "has_memory_evolution": self.memory_evolution is not None,
            "pending_actions": len(self.get_pending_actions()),
        }
