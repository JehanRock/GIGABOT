"""
Swarm tool for GigaBot.

Allows the agent to trigger multi-agent swarm execution for complex tasks.
Inspired by Kimi K2.5's Agent Swarm capabilities.
"""

from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.swarm.orchestrator import SwarmOrchestrator


class SwarmTool(Tool):
    """
    Tool to trigger multi-agent swarm execution for complex tasks.
    
    The swarm orchestrator decomposes complex tasks into subtasks
    and coordinates multiple worker agents to execute them in parallel.
    
    Available patterns:
    - research: Search, analyze, summarize
    - code: Design, implement, review
    - review: Analyze, critique, suggest improvements
    - brainstorm: Generate ideas, evaluate, develop
    """
    
    def __init__(self, orchestrator: "SwarmOrchestrator"):
        """
        Initialize SwarmTool.
        
        Args:
            orchestrator: SwarmOrchestrator instance to use.
        """
        self._orchestrator = orchestrator
    
    @property
    def name(self) -> str:
        return "swarm"
    
    @property
    def description(self) -> str:
        return """Execute complex tasks using multiple worker agents in parallel.

Use this tool when you need to:
- Research a topic comprehensively from multiple angles
- Implement code with proper design, implementation, and review phases
- Analyze something from multiple perspectives
- Brainstorm ideas with generation, evaluation, and development phases

Available patterns:
- research: For information gathering and synthesis
- code: For software development tasks
- review: For analysis and critique
- brainstorm: For creative ideation

The swarm will decompose the objective into subtasks and coordinate 
multiple workers to execute them, then aggregate the results.

Example usage:
- Research: {"objective": "Analyze AI trends in 2025", "pattern": "research"}
- Code: {"objective": "Implement user authentication", "pattern": "code"}
- Review: {"objective": "Review this architecture document", "pattern": "review"}
- Brainstorm: {"objective": "Ideas for improving UX", "pattern": "brainstorm"}
"""
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "objective": {
                    "type": "string",
                    "description": "The main objective or task to accomplish",
                },
                "pattern": {
                    "type": "string",
                    "enum": ["research", "code", "review", "brainstorm"],
                    "description": "The swarm pattern to use (default: research)",
                    "default": "research",
                },
                "context": {
                    "type": "string",
                    "description": "Additional context or constraints for the task",
                },
            },
            "required": ["objective"],
        }
    
    async def execute(
        self,
        objective: str,
        pattern: str = "research",
        context: str = "",
        **kwargs: Any,
    ) -> str:
        """
        Execute a swarm task.
        
        Args:
            objective: The main objective to accomplish.
            pattern: The swarm pattern to use.
            context: Additional context for the task.
        
        Returns:
            Aggregated result from all workers.
        """
        if not self._orchestrator:
            return "Error: Swarm orchestrator not available. Enable swarm in config."
        
        try:
            result = await self._orchestrator.execute(
                objective=objective,
                context=context,
                pattern=pattern,
            )
            return result
        except Exception as e:
            return f"Swarm execution failed: {str(e)}"
    
    def get_patterns(self) -> dict[str, str]:
        """Get available patterns with descriptions."""
        from nanobot.swarm.patterns import PATTERNS
        return {
            name: pattern.description
            for name, pattern in PATTERNS.items()
        }


class SwarmStatusTool(Tool):
    """
    Tool to check swarm system status.
    """
    
    def __init__(self, orchestrator: "SwarmOrchestrator"):
        self._orchestrator = orchestrator
    
    @property
    def name(self) -> str:
        return "swarm_status"
    
    @property
    def description(self) -> str:
        return "Check the status of the swarm system including active tasks and worker stats."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Get swarm status."""
        if not self._orchestrator:
            return "Swarm system not available."
        
        status = self._orchestrator.get_status()
        
        lines = [
            "Swarm Status:",
            f"  Enabled: {status['enabled']}",
            f"  Max Workers: {status['max_workers']}",
            f"  Active Tasks: {status['active_tasks']}",
            f"  Completed Tasks: {status['completed_tasks']}",
            "",
            "Available Patterns:",
        ]
        
        for pattern in status['available_patterns']:
            lines.append(f"  - {pattern}")
        
        if status['worker_stats']:
            lines.append("")
            lines.append("Worker Stats:")
            for stat in status['worker_stats']:
                lines.append(
                    f"  - {stat['id']}: {stat['task_count']} tasks, "
                    f"{stat['success_rate']:.0%} success rate"
                )
        
        return "\n".join(lines)
