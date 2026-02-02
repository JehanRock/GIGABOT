"""
Agent team for GigaBot's persona-based hierarchy.

AgentTeam manages a company-style team of specialized agents,
enabling role-based task assignment and collaborative workflows.
"""

import asyncio
from typing import Any, TYPE_CHECKING
from pathlib import Path
from dataclasses import dataclass, field

from loguru import logger

from nanobot.swarm.roles import (
    AgentRole,
    DEFAULT_ROLES,
    get_role,
    get_roles_for_task_type,
)
from nanobot.swarm.team_agent import TeamAgent, AgentResponse

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider
    from nanobot.config.schema import TeamConfig


@dataclass
class TaskAssignment:
    """Assignment of a task to a role."""
    task: str
    role_id: str
    reason: str
    priority: int = 1  # 1=highest


@dataclass
class TeamConsultation:
    """Result of consulting the team."""
    question: str
    responses: dict[str, AgentResponse] = field(default_factory=dict)
    summary: str = ""
    
    def get_formatted_responses(self) -> str:
        """Format all responses for display."""
        lines = []
        for role_id, response in self.responses.items():
            if response.success:
                lines.append(f"**{response.role_title}**: {response.content}")
            else:
                lines.append(f"**{response.role_title}**: (no response)")
        return "\n\n".join(lines)


class AgentTeam:
    """
    Company-style team of specialized agents.
    
    Unlike WorkerPool (generic workers), AgentTeam has:
    - Named roles with distinct personas
    - Per-role model configuration
    - Hierarchy and authority levels
    - Role-based task assignment
    - Collaborative consultation
    """
    
    def __init__(
        self,
        provider: "LLMProvider",
        workspace: Path,
        config: "TeamConfig | None" = None,
    ):
        """
        Initialize the agent team.
        
        Args:
            provider: LLM provider for API calls.
            workspace: Workspace path.
            config: Optional team configuration.
        """
        self.provider = provider
        self.workspace = workspace
        self.config = config
        
        # Initialize roles and agents
        self._roles: dict[str, AgentRole] = {}
        self._agents: dict[str, TeamAgent] = {}
        
        self._initialize_team()
    
    def _initialize_team(self) -> None:
        """Initialize team with configured roles."""
        # Start with default roles
        for role_id, role in DEFAULT_ROLES.items():
            # Apply config overrides if available
            if self.config and role_id in self.config.roles:
                role_config = self.config.roles[role_id]
                if not role_config.enabled:
                    continue
                
                # Create modified role with config overrides
                role = AgentRole(
                    id=role.id,
                    title=role.title,
                    model=role_config.model or role.model,
                    persona=(role_config.custom_persona or role.persona),
                    capabilities=role.capabilities,
                    authority_level=role.authority_level,
                    reports_to=role.reports_to,
                    tools_allowed=role.tools_allowed,
                    temperature=role_config.temperature,
                    max_tokens=role_config.max_tokens,
                )
            
            self._roles[role_id] = role
            self._agents[role_id] = TeamAgent(
                role=role,
                provider=self.provider,
                workspace=self.workspace,
            )
        
        logger.info(f"Team initialized with {len(self._agents)} agents")
    
    def get_agent(self, role_id: str) -> TeamAgent | None:
        """Get an agent by role ID."""
        return self._agents.get(role_id)
    
    def get_agent_for_task(
        self,
        task_type: str,
        complexity: str = "normal",
    ) -> TeamAgent | None:
        """
        Get the most suitable agent for a task type.
        
        Args:
            task_type: Type of task (code, research, review, etc.)
            complexity: Task complexity (simple, normal, complex)
        
        Returns:
            Most suitable TeamAgent or None.
        """
        # Get recommended roles for this task type
        recommended = get_roles_for_task_type(task_type)
        
        # Adjust based on complexity
        if complexity == "simple" and "junior_dev" in self._agents:
            # Simple tasks can go to junior
            if task_type in ("fix", "simple", "documentation"):
                return self._agents.get("junior_dev")
        
        elif complexity == "complex":
            # Complex tasks should go to senior roles
            if "architect" in self._agents and task_type in ("design", "architecture"):
                return self._agents["architect"]
            if "lead_dev" in self._agents:
                return self._agents["lead_dev"]
        
        # Find first available recommended role
        for role_id in recommended:
            if role_id in self._agents:
                return self._agents[role_id]
        
        # Fallback to senior_dev
        return self._agents.get("senior_dev")
    
    def get_qa_agent(self) -> TeamAgent | None:
        """Get the QA engineer agent."""
        return self._agents.get("qa_engineer")
    
    def get_auditor(self) -> TeamAgent | None:
        """Get the auditor agent."""
        return self._agents.get("auditor")
    
    def get_architect(self) -> TeamAgent | None:
        """Get the architect agent."""
        return self._agents.get("architect")
    
    def get_available_roles(self) -> list[str]:
        """Get list of available role IDs."""
        return list(self._agents.keys())
    
    def get_roles_info(self) -> list[dict[str, Any]]:
        """Get information about all roles."""
        return [
            {
                "id": role.id,
                "title": role.title,
                "model": role.model,
                "authority_level": role.authority_level,
                "capabilities": role.capabilities[:3],  # First 3
            }
            for role in self._roles.values()
        ]
    
    async def assign_task(self, task: str, context: str = "") -> TaskAssignment:
        """
        Intelligently assign a task to the appropriate role.
        
        Args:
            task: The task description.
            context: Additional context.
        
        Returns:
            TaskAssignment with role and reasoning.
        """
        task_lower = task.lower()
        
        # Quick keyword-based assignment
        if any(kw in task_lower for kw in ["architect", "design", "system", "scalab"]):
            return TaskAssignment(
                task=task,
                role_id="architect",
                reason="Task involves architecture or system design",
            )
        
        if any(kw in task_lower for kw in ["security", "audit", "vulnerab", "compliance"]):
            return TaskAssignment(
                task=task,
                role_id="auditor",
                reason="Task involves security or compliance",
            )
        
        if any(kw in task_lower for kw in ["test", "qa", "quality", "bug"]):
            return TaskAssignment(
                task=task,
                role_id="qa_engineer",
                reason="Task involves quality assurance or testing",
            )
        
        if any(kw in task_lower for kw in ["research", "find", "compare", "analyze"]):
            return TaskAssignment(
                task=task,
                role_id="researcher",
                reason="Task involves research or analysis",
            )
        
        if any(kw in task_lower for kw in ["complex", "refactor", "optimize"]):
            return TaskAssignment(
                task=task,
                role_id="lead_dev",
                reason="Task is complex or requires senior expertise",
            )
        
        if any(kw in task_lower for kw in ["simple", "fix", "typo", "minor"]):
            return TaskAssignment(
                task=task,
                role_id="junior_dev",
                reason="Task is simple and suitable for junior developer",
            )
        
        # Default to senior dev for code tasks
        if any(kw in task_lower for kw in ["code", "implement", "write", "create", "add"]):
            return TaskAssignment(
                task=task,
                role_id="senior_dev",
                reason="Standard development task",
            )
        
        # Default
        return TaskAssignment(
            task=task,
            role_id="senior_dev",
            reason="Default assignment for general tasks",
        )
    
    async def consult_team(
        self,
        question: str,
        participants: list[str] | None = None,
        context: str = "",
    ) -> TeamConsultation:
        """
        Consult multiple team members on a question.
        
        Args:
            question: The question to ask.
            participants: Specific roles to consult (or None for auto-select).
            context: Additional context.
        
        Returns:
            TeamConsultation with all responses.
        """
        # Auto-select participants if not specified
        if not participants:
            participants = self._select_participants_for_question(question)
        
        # Filter to available agents
        participants = [p for p in participants if p in self._agents]
        
        if not participants:
            return TeamConsultation(
                question=question,
                summary="No team members available",
            )
        
        # Gather opinions in parallel
        tasks = []
        for role_id in participants:
            agent = self._agents[role_id]
            tasks.append(agent.give_opinion(question, context))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect responses
        responses: dict[str, AgentResponse] = {}
        for role_id, result in zip(participants, results):
            if isinstance(result, Exception):
                responses[role_id] = AgentResponse(
                    role_id=role_id,
                    role_title=self._roles[role_id].title,
                    content="",
                    success=False,
                    error=str(result),
                )
            else:
                responses[role_id] = result
        
        return TeamConsultation(
            question=question,
            responses=responses,
        )
    
    def _select_participants_for_question(self, question: str) -> list[str]:
        """Select appropriate participants for a question."""
        question_lower = question.lower()
        participants = []
        
        # Always include architect for strategic questions
        if any(kw in question_lower for kw in ["should", "strategy", "approach", "design"]):
            participants.append("architect")
        
        # Include lead_dev for implementation questions
        if any(kw in question_lower for kw in ["implement", "code", "develop", "build"]):
            participants.append("lead_dev")
        
        # Include qa for quality questions
        if any(kw in question_lower for kw in ["test", "quality", "reliable", "bug"]):
            participants.append("qa_engineer")
        
        # Include auditor for security questions
        if any(kw in question_lower for kw in ["security", "safe", "risk", "compliance"]):
            participants.append("auditor")
        
        # Include researcher for research questions
        if any(kw in question_lower for kw in ["research", "find", "compare", "option"]):
            participants.append("researcher")
        
        # Default: architect, lead_dev, and one other
        if not participants:
            participants = ["architect", "lead_dev", "qa_engineer"]
        
        # Ensure minimum participation
        if len(participants) < 3:
            for role in ["architect", "lead_dev", "qa_engineer", "auditor"]:
                if role not in participants:
                    participants.append(role)
                    if len(participants) >= 3:
                        break
        
        return participants
    
    async def execute_with_agent(
        self,
        role_id: str,
        task: str,
        context: str = "",
    ) -> AgentResponse:
        """
        Execute a task with a specific agent.
        
        Args:
            role_id: The role to use.
            task: The task to execute.
            context: Additional context.
        
        Returns:
            AgentResponse from the agent.
        """
        agent = self._agents.get(role_id)
        if not agent:
            return AgentResponse(
                role_id=role_id,
                role_title="Unknown",
                content="",
                success=False,
                error=f"Agent '{role_id}' not found",
            )
        
        return await agent.execute(task, context)
    
    def get_team_stats(self) -> dict[str, Any]:
        """Get statistics for all team members."""
        return {
            "team_size": len(self._agents),
            "agents": [
                agent.get_stats() for agent in self._agents.values()
            ],
        }
    
    def reset_all_stats(self) -> None:
        """Reset statistics for all agents."""
        for agent in self._agents.values():
            agent.reset_stats()
    
    def clear_all_context(self) -> None:
        """Clear context for all agents."""
        for agent in self._agents.values():
            agent.clear_context()
