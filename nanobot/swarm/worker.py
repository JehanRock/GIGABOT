"""
Swarm worker for GigaBot.

Individual workers that execute tasks assigned by the orchestrator.
"""

import asyncio
from typing import Any
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class WorkerConfig:
    """Configuration for a swarm worker."""
    id: str
    model: str = "moonshot/kimi-k2.5"
    max_tokens: int = 2000
    temperature: float = 0.7
    timeout: int = 60
    specialization: str = ""  # Optional specialization (code, research, etc.)


class SwarmWorker:
    """
    A worker agent in the swarm.
    
    Workers are lightweight agents that execute specific tasks
    assigned by the orchestrator.
    """
    
    def __init__(
        self,
        config: WorkerConfig,
        provider: Any,  # LLMProvider
        workspace: Path,
    ):
        self.config = config
        self.provider = provider
        self.workspace = workspace
        
        self._task_count = 0
        self._success_count = 0
        self._total_time = 0.0
    
    async def execute(
        self,
        task: str,
        context: str = "",
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[bool, str]:
        """
        Execute a task.
        
        Args:
            task: The task description.
            context: Additional context.
            tools: Optional tool definitions.
        
        Returns:
            Tuple of (success, result).
        """
        import time
        
        start_time = time.time()
        self._task_count += 1
        
        # Build system prompt based on specialization
        system_prompt = self._get_system_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        
        if context:
            messages.append({"role": "user", "content": f"Context:\n{context}"})
        
        messages.append({"role": "user", "content": task})
        
        try:
            response = await asyncio.wait_for(
                self.provider.chat(
                    messages=messages,
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    tools=tools,
                ),
                timeout=self.config.timeout,
            )
            
            self._success_count += 1
            self._total_time += time.time() - start_time
            
            return True, response.content or ""
            
        except asyncio.TimeoutError:
            logger.warning(f"Worker {self.config.id} task timed out")
            return False, "Task timed out"
            
        except Exception as e:
            logger.error(f"Worker {self.config.id} error: {e}")
            return False, str(e)
    
    def _get_system_prompt(self) -> str:
        """Get system prompt based on specialization."""
        base = f"You are Worker {self.config.id} in a swarm system."
        
        specializations = {
            "code": """
You specialize in code-related tasks:
- Writing clean, well-documented code
- Debugging and fixing issues
- Code review and optimization
- Following best practices""",
            
            "research": """
You specialize in research tasks:
- Finding relevant information
- Summarizing findings
- Providing accurate citations
- Synthesizing multiple sources""",
            
            "review": """
You specialize in review tasks:
- Analyzing content for quality
- Identifying issues and improvements
- Providing constructive feedback
- Suggesting alternatives""",
            
            "creative": """
You specialize in creative tasks:
- Generating original content
- Brainstorming ideas
- Writing engaging copy
- Creative problem-solving""",
        }
        
        spec_prompt = specializations.get(self.config.specialization, """
You are a general-purpose worker capable of:
- Following detailed instructions
- Producing clear, actionable output
- Asking for clarification when needed""")
        
        return f"{base}\n{spec_prompt}\n\nFocus on your assigned task and provide clear results."
    
    def get_stats(self) -> dict[str, Any]:
        """Get worker statistics."""
        return {
            "id": self.config.id,
            "specialization": self.config.specialization,
            "task_count": self._task_count,
            "success_count": self._success_count,
            "success_rate": self._success_count / max(self._task_count, 1),
            "average_time": self._total_time / max(self._task_count, 1),
        }
    
    def reset_stats(self) -> None:
        """Reset worker statistics."""
        self._task_count = 0
        self._success_count = 0
        self._total_time = 0.0


class WorkerPool:
    """
    Pool of workers for the swarm system.
    
    Manages worker lifecycle and assignment.
    """
    
    def __init__(
        self,
        provider: Any,
        workspace: Path,
        max_workers: int = 5,
        default_model: str = "moonshot/kimi-k2.5",
    ):
        self.provider = provider
        self.workspace = workspace
        self.max_workers = max_workers
        self.default_model = default_model
        
        self._workers: dict[str, SwarmWorker] = {}
        self._available: asyncio.Queue[str] = asyncio.Queue()
    
    def create_worker(
        self,
        specialization: str = "",
        model: str | None = None,
    ) -> SwarmWorker:
        """Create a new worker."""
        worker_id = f"worker_{len(self._workers) + 1}"
        
        config = WorkerConfig(
            id=worker_id,
            model=model or self.default_model,
            specialization=specialization,
        )
        
        worker = SwarmWorker(config, self.provider, self.workspace)
        self._workers[worker_id] = worker
        
        return worker
    
    async def get_worker(
        self,
        specialization: str = "",
        timeout: float = 30.0,
    ) -> SwarmWorker | None:
        """
        Get an available worker from the pool.
        
        Args:
            specialization: Preferred specialization.
            timeout: How long to wait for a worker.
        
        Returns:
            Available worker or None.
        """
        # Check for existing worker with matching specialization
        for worker in self._workers.values():
            if worker.config.specialization == specialization:
                return worker
        
        # Create new worker if under limit
        if len(self._workers) < self.max_workers:
            return self.create_worker(specialization)
        
        # Return any available worker
        if self._workers:
            return next(iter(self._workers.values()))
        
        return None
    
    def get_all_stats(self) -> list[dict[str, Any]]:
        """Get stats for all workers."""
        return [w.get_stats() for w in self._workers.values()]
    
    def reset_all_stats(self) -> None:
        """Reset stats for all workers."""
        for worker in self._workers.values():
            worker.reset_stats()
