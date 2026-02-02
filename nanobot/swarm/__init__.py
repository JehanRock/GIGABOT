"""
Swarm system for GigaBot.

Provides multi-agent coordination:
- Orchestrator for task decomposition
- Worker agents for parallel execution
- Patterns for common workflows
- Result aggregation
- Persona-based team hierarchy
- Quality gates and deliberation
"""

from nanobot.swarm.orchestrator import (
    SwarmOrchestrator,
    SwarmConfig,
    SwarmTask,
    TaskResult,
    TeamOrchestrator,
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
from nanobot.swarm.roles import (
    AgentRole,
    DEFAULT_ROLES,
    get_role,
    get_all_roles,
    get_roles_for_task_type,
)
from nanobot.swarm.team_agent import (
    TeamAgent,
    AgentResponse,
    ReviewResult,
    ReviewVerdict,
)
from nanobot.swarm.team import (
    AgentTeam,
    TaskAssignment,
    TeamConsultation,
)
from nanobot.swarm.quality_gate import (
    QualityGate,
    GateDecision,
    GateResult,
    WorkOutput,
)
from nanobot.swarm.deliberation import (
    DeliberationSession,
    DeliberationResult,
    Opinion,
    Option,
)

__all__ = [
    # Orchestrator
    "SwarmOrchestrator",
    "SwarmConfig",
    "SwarmTask",
    "TaskResult",
    "TeamOrchestrator",
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
    # Roles
    "AgentRole",
    "DEFAULT_ROLES",
    "get_role",
    "get_all_roles",
    "get_roles_for_task_type",
    # Team Agent
    "TeamAgent",
    "AgentResponse",
    "ReviewResult",
    "ReviewVerdict",
    # Team
    "AgentTeam",
    "TaskAssignment",
    "TeamConsultation",
    # Quality Gate
    "QualityGate",
    "GateDecision",
    "GateResult",
    "WorkOutput",
    # Deliberation
    "DeliberationSession",
    "DeliberationResult",
    "Opinion",
    "Option",
]
