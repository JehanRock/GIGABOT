"""
Token tracking and self-optimization for GigaBot.

Provides:
- Token usage tracking
- Cost estimation
- Budget management
- Response caching
- Cost optimization
"""

from nanobot.tracking.tokens import (
    TokenTracker,
    UsageStats,
    BudgetAlert,
)
from nanobot.tracking.optimizer import (
    SelfOptimizer,
    CostOptimizer,
    OptimizationSuggestion,
)
from nanobot.tracking.cache import (
    ResponseCache,
    CacheEntry,
    CacheStats,
)

__all__ = [
    "TokenTracker",
    "UsageStats",
    "BudgetAlert",
    "SelfOptimizer",
    "CostOptimizer",
    "OptimizationSuggestion",
    "ResponseCache",
    "CacheEntry",
    "CacheStats",
]
