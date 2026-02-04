"""
Proactive Agent System for GigaBot.

Enables proactive AI capabilities:
- Reminders: Time-based prompts
- Suggestions: Pattern-based recommendations
- Automation: Pre-approved recurring tasks
- Insights: Discovered patterns
- Anticipation: Predicted needs
"""

from nanobot.proactive.actions import (
    ActionType,
    ProactiveAction,
    ActionStatus,
)
from nanobot.proactive.engine import (
    ProactiveEngine,
)
from nanobot.proactive.triggers import (
    Trigger,
    TriggerType,
    TriggerManager,
)

__all__ = [
    "ActionType",
    "ProactiveAction",
    "ActionStatus",
    "ProactiveEngine",
    "Trigger",
    "TriggerType",
    "TriggerManager",
]
