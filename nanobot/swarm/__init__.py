"""
Swarm system for GigaBot.

Provides multi-agent coordination:
- Orchestrator for task decomposition
- Worker agents for parallel execution
- Patterns for common workflows
- Result aggregation
"""

from nanobot.swarm.orchestrator import (
    SwarmOrchestrator,
    SwarmConfig,
    SwarmTask,
    TaskResult,
)
from nanobot.swarm.worker import (
    SwarmWorker,
    WorkerConfig,
    WorkerPool,
)
from nanobot.swarm.patterns import (
    SwarmPattern,
    ResearchPattern,
    CodePattern,
    ReviewPattern,
    BrainstormPattern,
    PATTERNS,
    get_pattern,
    list_patterns,
)

__all__ = [
    # Orchestrator
    "SwarmOrchestrator",
    "SwarmConfig",
    "SwarmTask",
    "TaskResult",
    # Workers
    "SwarmWorker",
    "WorkerConfig",
    "WorkerPool",
    # Patterns
    "SwarmPattern",
    "ResearchPattern",
    "CodePattern",
    "ReviewPattern",
    "BrainstormPattern",
    "PATTERNS",
    "get_pattern",
    "list_patterns",
]
