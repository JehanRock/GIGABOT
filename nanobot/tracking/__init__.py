"""
Token tracking and self-optimization for GigaBot.

Provides:
- Token usage tracking
- Cost estimation
- Budget management
- Optimization suggestions
"""

from nanobot.tracking.tokens import (
    TokenTracker,
    UsageStats,
    BudgetAlert,
)
from nanobot.tracking.optimizer import (
    SelfOptimizer,
    OptimizationSuggestion,
)

__all__ = [
    "TokenTracker",
    "UsageStats",
    "BudgetAlert",
    "SelfOptimizer",
    "OptimizationSuggestion",
]
