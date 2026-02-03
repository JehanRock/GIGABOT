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
    retry_count: int = 0


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
        """Execute tasks respecting dependencies using worker pool with retry support."""
        results = []
        completed = set()
        pending = {t.id: t for t in tasks}
        retry_counts: dict[str, int] = {t.id: 0 for t in tasks}
        
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
                *[self._execute_single_task(t, retry_counts.get(t.id, 0)) for t in batch],
                return_exceptions=True
            )
            
            for task, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    result = TaskResult(
                        task_id=task.id,
                        success=False,
                        result="",
                        error=str(result),
                        retry_count=retry_counts.get(task.id, 0),
                    )
                
                # Check if we should retry failed tasks
                if not result.success and self.config.retry_failed:
                    current_retries = retry_counts.get(task.id, 0)
                    
                    if current_retries < self.config.max_retries:
                        # Check if error is transient (worth retrying)
                        if self._is_transient_error(result.error):
                            retry_counts[task.id] = current_retries + 1
                            logger.info(
                                f"Retrying task '{task.id}' (attempt {current_retries + 2}/{self.config.max_retries + 1}): "
                                f"{result.error[:100]}"
                            )
                            # Don't mark as completed - will be retried in next iteration
                            await asyncio.sleep(1.0 * (current_retries + 1))  # Backoff
                            continue
                
                # Task completed (success or no more retries)
                result.retry_count = retry_counts.get(task.id, 0)
                results.append(result)
                completed.add(task.id)
                del pending[task.id]
                
                # Store result for dependent tasks
                self._results[task.id] = result
        
        return results
    
    def _is_transient_error(self, error: str) -> bool:
        """Check if an error is transient and worth retrying."""
        error_lower = error.lower()
        
        # Transient error patterns
        transient_patterns = [
            "timeout", "timed out", "connection", "network",
            "temporary", "unavailable", "retry", "rate limit",
            "no worker available", "busy",
        ]
        
        # Permanent error patterns (don't retry)
        permanent_patterns = [
            "not found", "invalid", "missing required",
            "permission denied", "unauthorized", "forbidden",
        ]
        
        # Check permanent first
        if any(p in error_lower for p in permanent_patterns):
            return False
        
        # Then check transient
        return any(p in error_lower for p in transient_patterns)
    
    async def _execute_single_task(self, task: SwarmTask, retry_count: int = 0) -> TaskResult:
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
        
        # On retry, try to get a different worker if possible
        preferred_worker = None
        if retry_count > 0:
            # Try to avoid the same worker that failed
            specialization = ""  # Reset to get any available worker
        
        worker = await self._worker_pool.get_worker(specialization=specialization)
        
        if not worker:
            return TaskResult(
                task_id=task.id,
                success=False,
                result="",
                error="No worker available",
                execution_time=time.time() - start_time,
                retry_count=retry_count,
            )
        
        # Build context from dependencies
        dep_context = ""
        for dep_id in task.dependencies:
            if dep_id in self._results:
                dep_result = self._results[dep_id]
                dep_context += f"\nResult from {dep_id}: {dep_result.result[:500]}"
        
        # Execute using worker
        retry_note = f"\n\n(Note: This is retry attempt {retry_count + 1})" if retry_count > 0 else ""
        task_prompt = f"""Task: {task.description}

Instructions:
{task.instructions}

{f"Context from previous tasks:{dep_context}" if dep_context else ""}

Provide a clear, actionable result.{retry_note}"""

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
                retry_count=retry_count,
            )
            
        except asyncio.TimeoutError:
            return TaskResult(
                task_id=task.id,
                success=False,
                result="",
                error="Task timed out",
                execution_time=time.time() - start_time,
                worker_id=worker.config.id,
                retry_count=retry_count,
            )
        except Exception as e:
            return TaskResult(
                task_id=task.id,
                success=False,
                result="",
                error=str(e),
                execution_time=time.time() - start_time,
                worker_id=worker.config.id if worker else "",
                retry_count=retry_count,
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


# =============================================================================
# Team Orchestrator - Persona-Based Hierarchy
# =============================================================================

class TeamOrchestrator:
    """
    Orchestrates the agent team like a Managing Director.
    
    Key differences from SwarmOrchestrator:
    - Role-based assignment instead of generic workers
    - Mandatory QA gate on all outputs
    - Optional Auditor review for sensitive tasks
    - Deliberation mode for complex decisions
    - Profile-aware model selection via ModelRegistry
    
    Supports two modes:
    - "execute" (default): Assign and complete tasks ("Get this done")
    - "deliberate": Gather opinions, present options ("Reach this goal")
    """
    
    def __init__(
        self,
        provider: Any,  # LLMProvider
        workspace: Path,
        config: Any = None,  # TeamConfig
        model_registry: Any = None,  # ModelRegistry
    ):
        """
        Initialize the team orchestrator.
        
        Args:
            provider: LLM provider for API calls.
            workspace: Workspace path.
            config: Optional TeamConfig for customization.
            model_registry: Optional ModelRegistry for profile-aware assignment.
        """
        from nanobot.swarm.team import AgentTeam
        from nanobot.swarm.quality_gate import QualityGate, MultiStageGate
        from nanobot.swarm.deliberation import DeliberationSession
        
        self.provider = provider
        self.workspace = workspace
        self.config = config
        self.model_registry = model_registry
        
        # Initialize the team with model registry
        self.team = AgentTeam(
            provider=provider,
            workspace=workspace,
            config=config,
            model_registry=model_registry,
        )
        
        # Initialize quality gate
        qa_enabled = config.qa_gate_enabled if config else True
        audit_enabled = config.audit_gate_enabled if config else True
        audit_threshold = config.audit_threshold if config else "sensitive"
        
        self.quality_gate = MultiStageGate(
            team=self.team,
            qa_enabled=qa_enabled,
            audit_enabled=audit_enabled,
            audit_threshold=audit_threshold,
        )
        
        # Deliberation settings
        self.deliberation_timeout = config.deliberation_timeout if config else 120
        self.min_opinions = config.min_opinions if config else 3
        
        # State tracking
        self._results: dict[str, TaskResult] = {}
        self._running_tasks: set[str] = set()
    
    async def execute(
        self,
        objective: str,
        mode: str = "execute",
        context: str = "",
        pattern: str | None = None,
    ) -> str:
        """
        Execute with the team.
        
        Args:
            objective: The objective to accomplish.
            mode: "execute" for tasks, "deliberate" for discussions.
            context: Additional context.
            pattern: Optional workflow pattern.
        
        Returns:
            Result string.
        """
        if mode == "deliberate":
            return await self._deliberate(objective, context)
        else:
            return await self._execute(objective, context, pattern)
    
    async def _deliberate(
        self,
        question: str,
        context: str = "",
    ) -> str:
        """
        Run deliberation mode - gather team opinions and present options.
        
        Args:
            question: The question to deliberate on.
            context: Additional context.
        
        Returns:
            Formatted deliberation result.
        """
        from nanobot.swarm.deliberation import DeliberationSession
        
        logger.info(f"Team deliberating: {question[:50]}...")
        
        session = DeliberationSession(
            team=self.team,
            provider=self.provider,
            timeout=self.deliberation_timeout,
            min_opinions=self.min_opinions,
        )
        
        result = await session.run(question, context=context)
        return result.format_for_user()
    
    async def _execute(
        self,
        objective: str,
        context: str = "",
        pattern: str | None = None,
    ) -> str:
        """
        Execute mode - delegate tasks and complete work.
        
        Args:
            objective: The objective to accomplish.
            context: Additional context.
            pattern: Optional workflow pattern.
        
        Returns:
            Result with QA review.
        """
        from nanobot.swarm.quality_gate import WorkOutput
        
        logger.info(f"Team executing: {objective[:50]}...")
        
        # Decompose into tasks
        tasks = await self._decompose_task(objective, context, pattern)
        
        if not tasks:
            return "Failed to decompose task into subtasks"
        
        logger.info(f"Decomposed into {len(tasks)} tasks")
        
        # Execute tasks with role-based assignment
        results = await self._execute_tasks(tasks)
        
        # Aggregate results
        aggregated = await self._aggregate_results(objective, results)
        
        # Run through quality gate
        work_output = WorkOutput(
            agent_id="team",
            agent_title="Team",
            task=objective,
            content=aggregated,
            context=context,
        )
        
        gate_result = await self.quality_gate.review(work_output)
        
        # Format final output
        output_lines = [aggregated]
        
        if gate_result.qa_result or gate_result.audit_result:
            output_lines.append("\n---")
            output_lines.append(gate_result.get_summary())
        
        return "\n".join(output_lines)
    
    async def _decompose_task(
        self,
        objective: str,
        context: str,
        pattern: str | None,
    ) -> list[SwarmTask]:
        """Decompose objective into tasks with role assignments."""
        
        # Use pattern if specified
        if pattern:
            swarm_pattern = get_pattern(pattern)
            if swarm_pattern:
                logger.info(f"Using '{pattern}' pattern")
                tasks = swarm_pattern.generate_tasks(objective, context)
                # Add role assignments
                for task in tasks:
                    task.metadata["assigned_role"] = self._assign_role_for_task(task)
                return tasks
        
        # LLM-based decomposition with role assignment
        prompt = f"""You are a Managing Director decomposing a task for your team.

Objective: {objective}

Context: {context or "None provided"}

Available team roles:
- architect: System design, technical decisions
- lead_dev: Complex implementation, code review
- senior_dev: Feature implementation
- junior_dev: Simple tasks, bug fixes
- qa_engineer: Testing, quality review
- auditor: Security review
- researcher: Information gathering

Decompose into 2-5 tasks and assign each to the most appropriate role.

Return a JSON array:
[
  {{
    "id": "task_1",
    "description": "Brief task description",
    "instructions": "Detailed instructions",
    "assigned_role": "role_id",
    "dependencies": []
  }}
]

Focus on:
1. Assigning to the right expertise level
2. Clear instructions for each role
3. Logical task ordering

Return ONLY the JSON array."""

        try:
            response = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model="anthropic/claude-sonnet-4-5",
                max_tokens=2000,
            )
            
            content = response.content or ""
            json_match = re.search(r'\[[\s\S]*\]', content)
            
            if json_match:
                tasks_data = json.loads(json_match.group())
                
                tasks = []
                for t in tasks_data:
                    task = SwarmTask(
                        id=t.get("id", f"task_{len(tasks)}"),
                        description=t.get("description", ""),
                        instructions=t.get("instructions", ""),
                        dependencies=t.get("dependencies", []),
                        metadata={"assigned_role": t.get("assigned_role", "senior_dev")},
                    )
                    tasks.append(task)
                
                return tasks
                
        except Exception as e:
            logger.error(f"Task decomposition failed: {e}")
        
        return []
    
    def _assign_role_for_task(self, task: SwarmTask) -> str:
        """Determine the best role for a task."""
        desc = task.description.lower()
        
        if any(kw in desc for kw in ["design", "architect", "system"]):
            return "architect"
        if any(kw in desc for kw in ["review", "test", "quality"]):
            return "qa_engineer"
        if any(kw in desc for kw in ["research", "search", "find"]):
            return "researcher"
        if any(kw in desc for kw in ["implement", "code", "write"]):
            return "senior_dev"
        
        return "senior_dev"
    
    async def _execute_tasks(self, tasks: list[SwarmTask]) -> list[TaskResult]:
        """Execute tasks using role-based agents."""
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
                logger.warning("No tasks ready to execute")
                break
            
            # Execute ready tasks in parallel
            batch_results = await asyncio.gather(
                *[self._execute_single_task(t) for t in ready],
                return_exceptions=True
            )
            
            for task, result in zip(ready, batch_results):
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
                self._results[task.id] = result
        
        return results
    
    async def _execute_single_task(self, task: SwarmTask) -> TaskResult:
        """Execute a task using the assigned role's agent."""
        start_time = time.time()
        
        # Get assigned role
        role_id = task.metadata.get("assigned_role", "senior_dev")
        agent = self.team.get_agent(role_id)
        
        if not agent:
            # Fallback to senior_dev
            agent = self.team.get_agent("senior_dev")
        
        if not agent:
            return TaskResult(
                task_id=task.id,
                success=False,
                result="",
                error="No agent available",
                execution_time=time.time() - start_time,
            )
        
        # Build context from dependencies
        dep_context = ""
        for dep_id in task.dependencies:
            if dep_id in self._results:
                dep_result = self._results[dep_id]
                dep_context += f"\nResult from {dep_id}: {dep_result.result[:500]}"
        
        # Execute
        task_prompt = f"""Task: {task.description}

Instructions:
{task.instructions}

{f"Context from previous tasks:{dep_context}" if dep_context else ""}

Provide a clear, complete result."""

        self._running_tasks.add(task.id)
        
        try:
            response = await agent.execute(task_prompt, dep_context)
            
            return TaskResult(
                task_id=task.id,
                success=response.success,
                result=response.content,
                error=response.error,
                execution_time=time.time() - start_time,
                worker_id=agent.id,
            )
            
        except Exception as e:
            return TaskResult(
                task_id=task.id,
                success=False,
                result="",
                error=str(e),
                execution_time=time.time() - start_time,
            )
        finally:
            self._running_tasks.discard(task.id)
    
    async def _aggregate_results(
        self,
        objective: str,
        results: list[TaskResult],
    ) -> str:
        """Aggregate results using a senior agent."""
        results_summary = []
        for r in results:
            status = "✓" if r.success else "✗"
            results_summary.append(
                f"{status} [{r.worker_id}] {r.task_id}: "
                f"{r.result[:300] if r.success else r.error}"
            )
        
        prompt = f"""As the Managing Director, synthesize these team results.

Objective: {objective}

Team Results:
{chr(10).join(results_summary)}

Synthesize into a coherent response addressing the original objective.
Include contributions from each team member where relevant."""

        try:
            # Use architect for synthesis
            architect = self.team.get_architect()
            if architect:
                response = await architect.execute(prompt)
                return response.content
            
            # Fallback
            response = await self.provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model="anthropic/claude-sonnet-4-5",
                max_tokens=3000,
            )
            return response.content or ""
            
        except Exception as e:
            logger.error(f"Result aggregation failed: {e}")
            return "\n\n".join([
                f"## {r.task_id} ({r.worker_id})\n{r.result}"
                for r in results if r.success
            ])
    
    def get_status(self) -> dict[str, Any]:
        """Get team orchestrator status."""
        return {
            "team_size": len(self.team.get_available_roles()),
            "available_roles": self.team.get_available_roles(),
            "active_tasks": len(self._running_tasks),
            "completed_tasks": len(self._results),
            "qa_enabled": self.quality_gate.qa_enabled if self.quality_gate else False,
            "audit_enabled": self.quality_gate.audit_enabled if self.quality_gate else False,
            "team_stats": self.team.get_team_stats(),
        }
    
    def reset(self) -> None:
        """Reset orchestrator state."""
        self._results.clear()
        self._running_tasks.clear()
        self.team.reset_all_stats()
        self.team.clear_all_context()
