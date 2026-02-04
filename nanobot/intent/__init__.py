"""
Intent tracking module for GigaBot.

Captures and analyzes user intentions to enable:
- Pattern recognition across conversations
- Proactive suggestions
- Intent-based memory relevance
"""

from nanobot.intent.tracker import (
    IntentTracker,
    UserIntent,
    PatternInsight,
    PredictedIntent,
    IntentCategory,
)

__all__ = [
    "IntentTracker",
    "UserIntent",
    "PatternInsight",
    "PredictedIntent",
    "IntentCategory",
]
