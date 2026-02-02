"""
Swarm orchestrator for GigaBot.

Manages multi-agent task execution:
- Task decomposition
- Worker coordination
- Result aggregation
- Error handling
"""

import asyncio
import json
import re
import time
from typing import Any
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from nanobot.swarm.worker import SwarmWorker, WorkerConfig, WorkerPool
from nanobot.swarm.patterns import get_pattern, list_patterns


@dataclass
class SwarmConfig:
    """Configuration for the swarm system."""
    enabled: bool = True
    max_workers: int = 5
    worker_model: str = "moonshot/kimi-k2.5"
    orchestrator_model: str = "anthropic/claude-sonnet-4-5"
    timeout_seconds: int = 300
    retry_failed: bool = True
    max_retries: int = 2


@dataclass
class SwarmTask:
    """A task to be executed by the swarm."""
    id: str
    description: str
    instructions: str
    dependencies: list[str] = field(default_factory=list)
    timeout: int = 60
    retries: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result from a swarm task."""
    task_id: str
    success: bool
    result: str
    error: str = ""
    execution_time: float = 0.0
    worker_id: str = ""


class SwarmOrchestrator:
    """
    Orchestrates multi-agent task execution.
    
    Flow:
    1. Receive complex task
    2. Decompose into subtasks (using patterns if specified)
    3. Assign to workers (respecting dependencies)
    4. Collect and aggregate results
    5. Return final response
    """
    
    def __init__(
        self,
        config: SwarmConfig,
        provider: Any,  # LLMProvider
        workspace: Path,
    ):
        self.config = config
        self.provider = provider
        self.workspace = workspace
        
        # Create worker pool
        self._worker_pool = WorkerPool(
            provider=provider,
            workspace=workspace,
            max_workers=config.max_workers,
            default_model=config.worker_model,
        )
        
        self._results: dict[str, TaskResult] = {}
        self._running_tasks: set[str] = set()
    
    async def execute(
        self,
        objective: str,
        context: str = "",
        pattern: str | None = None,
    ) -> str:
        """
        Execute a complex objective using the swarm.
        
        Args:
            objective: The main objective to accomplish.
            context: Additional context for the task.
            pattern: Optional pattern to use (research, code, review, brainstorm).
        
        Returns:
            Aggregated result from all workers.
        """
        if not self.config.enabled:
            return "Swarm system is disabled"
        
        logger.info(f"Swarm executing: {objective[:50]}...")
        
        # Decompose into tasks
        tasks = await self._decompose_task(objective, context, pattern)
        
        if not tasks:
            return "Failed to decompose task into subtasks"
        
        logger.info(f"Decomposed into {len(tasks)} tasks")
        
        # Execute tasks
        results = await self._execute_tasks(tasks)
        
        # Aggregate results
        final_result = await self._aggregate_results(objective, results)
        
        return final_result
    
    async def _decompose_task(
        self,
        objective: str,
        context: str,
        pattern: str | None,
    ) -> list[SwarmTask]:
        """Decompose objective into subtasks using patterns or LLM."""
        
        # If a pattern is specified, use it
        if pattern:
            swarm_pattern = get_pattern(pattern)
            if swarm_pattern:
                logger.info(f"Using '{pattern}' pattern for task decomposition")
                return swarm_pattern.generate_tasks(objective, context)
            else:
                logger.warning(f"Pattern '{pattern}' not found, using LLM decomposition")
        
        # Fall back to LLM-based decomposition
        prompt = f"""You are a task orchestrator. Decompose this objective into 2-5 independent subtasks.

Objective: {objective}

Context: {context or "None provided"}

Available patterns for reference: {', '.join(list_patterns())}

Return a JSON array of tasks with this structure:
[
  {{
    "id": "task_1",
    "description": "Brief task description",
    "instructions": "Detailed instructions for the worker",
    "dependencies": []  // List of task IDs this depends on
  }},
  ...
]

Focus on:
1. Making tasks as independent as possible
2. Clear, actionable instructions
3. Logical ordering of dependencies

Return ONLY the JSON array, no other text."""

        try:
            response = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.orchestrator_model,
                max_tokens=2000,
            )
            
            # Parse JSON from response
            content = response.content or ""
            
            # Extract JSON array
            json_match = re.search(r'\[[\s\S]*\]', content)
            if json_match:
                tasks_data = json.loads(json_match.group())
                
                tasks = []
                for t in tasks_data:
                    tasks.append(SwarmTask(
                        id=t.get("id", f"task_{len(tasks)}"),
                        description=t.get("description", ""),
                        instructions=t.get("instructions", ""),
                        dependencies=t.get("dependencies", []),
                    ))
                
                return tasks
                
        except Exception as e:
            logger.error(f"Task decomposition failed: {e}")
        
        return []
    
    async def _execute_tasks(self, tasks: list[SwarmTask]) -> list[TaskResult]:
        """Execute tasks respecting dependencies using worker pool."""
        results = []
        completed = set()
        pending = {t.id: t for t in tasks}
        
        while pending:
            # Find tasks with satisfied dependencies
            ready = [
                t for t in pending.values()
                if all(dep in completed for dep in t.dependencies)
            ]
            
            if not ready:
                # Deadlock or all remaining have unmet dependencies
                logger.warning("No tasks ready to execute")
                break
            
            # Execute ready tasks in parallel (up to max_workers)
            batch = ready[:self.config.max_workers]
            batch_results = await asyncio.gather(
                *[self._execute_single_task(t) for t in batch],
                return_exceptions=True
            )
            
            for task, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    result = TaskResult(
                        task_id=task.id,
                        success=False,
                        result="",
                        error=str(result),
                    )
                
                results.append(result)
                completed.add(task.id)
                del pending[task.id]
                
                # Store result for dependent tasks
                self._results[task.id] = result
        
        return results
    
    async def _execute_single_task(self, task: SwarmTask) -> TaskResult:
        """Execute a single task using a worker from the pool."""
        start_time = time.time()
        
        # Get a worker from the pool
        # Determine specialization based on task metadata or description
        specialization = task.metadata.get("specialization", "")
        if not specialization:
            # Try to infer from task description
            desc_lower = task.description.lower()
            if any(kw in desc_lower for kw in ["code", "implement", "write"]):
                specialization = "code"
            elif any(kw in desc_lower for kw in ["search", "research", "find"]):
                specialization = "research"
            elif any(kw in desc_lower for kw in ["review", "analyze", "critique"]):
                specialization = "review"
        
        worker = await self._worker_pool.get_worker(specialization=specialization)
        
        if not worker:
            return TaskResult(
                task_id=task.id,
                success=False,
                result="",
                error="No worker available",
                execution_time=time.time() - start_time,
            )
        
        # Build context from dependencies
        dep_context = ""
        for dep_id in task.dependencies:
            if dep_id in self._results:
                dep_result = self._results[dep_id]
                dep_context += f"\nResult from {dep_id}: {dep_result.result[:500]}"
        
        # Execute using worker
        task_prompt = f"""Task: {task.description}

Instructions:
{task.instructions}

{f"Context from previous tasks:{dep_context}" if dep_context else ""}

Provide a clear, actionable result."""

        self._running_tasks.add(task.id)
        
        try:
            success, result = await worker.execute(
                task=task_prompt,
                context=dep_context,
            )
            
            return TaskResult(
                task_id=task.id,
                success=success,
                result=result,
                error="" if success else result,
                execution_time=time.time() - start_time,
                worker_id=worker.config.id,
            )
            
        except asyncio.TimeoutError:
            return TaskResult(
                task_id=task.id,
                success=False,
                result="",
                error="Task timed out",
                execution_time=time.time() - start_time,
                worker_id=worker.config.id,
            )
        except Exception as e:
            return TaskResult(
                task_id=task.id,
                success=False,
                result="",
                error=str(e),
                execution_time=time.time() - start_time,
                worker_id=worker.config.id if worker else "",
            )
        finally:
            self._running_tasks.discard(task.id)
    
    async def _aggregate_results(
        self,
        objective: str,
        results: list[TaskResult],
    ) -> str:
        """Aggregate task results into final response."""
        
        # Build summary of results
        results_summary = []
        for r in results:
            status = "✓" if r.success else "✗"
            results_summary.append(f"{status} {r.task_id}: {r.result[:300] if r.success else r.error}")
        
        prompt = f"""You are aggregating results from multiple workers.

Original Objective: {objective}

Task Results:
{chr(10).join(results_summary)}

Synthesize these results into a coherent, comprehensive response that addresses the original objective.
If some tasks failed, work with what succeeded and note any gaps."""

        try:
            response = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.config.orchestrator_model,
                max_tokens=3000,
            )
            
            return response.content or "Failed to aggregate results"
            
        except Exception as e:
            # Fallback: just concatenate results
            return "\n\n".join([
                f"## {r.task_id}\n{r.result}" 
                for r in results if r.success
            ])
    
    def get_status(self) -> dict[str, Any]:
        """Get swarm status."""
        return {
            "enabled": self.config.enabled,
            "max_workers": self.config.max_workers,
            "active_tasks": len(self._running_tasks),
            "completed_tasks": len(self._results),
            "worker_stats": self._worker_pool.get_all_stats(),
            "available_patterns": list_patterns(),
        }
    
    def reset(self) -> None:
        """Reset swarm state."""
        self._results.clear()
        self._running_tasks.clear()
        self._worker_pool.reset_all_stats()
