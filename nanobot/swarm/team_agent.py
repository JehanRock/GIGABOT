"""
Team agent for GigaBot's persona-based hierarchy.

A TeamAgent is a named agent with a distinct persona and role,
unlike generic SwarmWorkers. Each TeamAgent maintains their identity
across interactions and operates within their defined expertise.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
from pathlib import Path
from enum import Enum

from loguru import logger

from nanobot.swarm.roles import AgentRole

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider
    from nanobot.profiler.profile import ModelProfile


class ReviewVerdict(str, Enum):
    """Verdict from a review."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    BLOCKED = "blocked"


@dataclass
class AgentResponse:
    """Response from a team agent."""
    role_id: str
    role_title: str
    content: str
    success: bool
    execution_time: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewResult:
    """Result of a review by QA or Auditor."""
    reviewer_id: str
    reviewer_title: str
    verdict: ReviewVerdict
    summary: str
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    details: str = ""
    
    @property
    def passed(self) -> bool:
        """Check if the review passed."""
        return self.verdict in (
            ReviewVerdict.PASS,
            ReviewVerdict.APPROVED,
            ReviewVerdict.CONDITIONAL,
        )


class TeamAgent:
    """
    A named agent with persona and role.
    
    Unlike SwarmWorker, TeamAgent:
    - Has a persistent identity and persona
    - Uses role-specific model
    - Maintains conversation context within session
    - Can review other agents' work
    - Reports to hierarchy
    - Applies profile-based guardrails
    """
    
    def __init__(
        self,
        role: AgentRole,
        provider: "LLMProvider",
        workspace: Path | None = None,
        profile: "ModelProfile | None" = None,
    ):
        """
        Initialize a team agent.
        
        Args:
            role: The agent's role definition.
            provider: LLM provider for API calls.
            workspace: Optional workspace path.
            profile: Optional model profile for guardrails.
        """
        self.role = role
        self.provider = provider
        self.workspace = workspace
        self.profile = profile
        
        # Session context (conversation history within a session)
        self._context: list[dict[str, str]] = []
        
        # Statistics
        self._task_count = 0
        self._success_count = 0
        self._total_time = 0.0
        self._tool_call_successes = 0
        self._tool_call_failures = 0
    
    @property
    def id(self) -> str:
        """Get agent ID."""
        return self.role.id
    
    @property
    def title(self) -> str:
        """Get agent title."""
        return self.role.title
    
    @property
    def model(self) -> str:
        """Get the model this agent uses."""
        return self.role.model
    
    async def execute(
        self,
        task: str,
        context: str = "",
        tools: list[dict[str, Any]] | None = None,
        include_history: bool = False,
    ) -> AgentResponse:
        """
        Execute a task with this agent's persona.
        
        Args:
            task: The task to execute.
            context: Additional context for the task.
            tools: Optional tool definitions to provide.
            include_history: Whether to include session history.
        
        Returns:
            AgentResponse with result.
        """
        start_time = time.time()
        self._task_count += 1
        
        # Build system prompt with guardrails if profile available
        system_prompt = self.role.get_system_prompt()
        if self.profile:
            guardrail_prompt = self.profile.get_guardrail_prompt()
            if guardrail_prompt:
                system_prompt = f"{system_prompt}\n\n--- GUARDRAILS ---\n{guardrail_prompt}"
        
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        # Add session history if requested
        if include_history and self._context:
            messages.extend(self._context[-6:])  # Last 3 exchanges
        
        # Add context if provided
        if context:
            messages.append({
                "role": "user",
                "content": f"Context:\n{context}"
            })
        
        # Add the task
        messages.append({
            "role": "user",
            "content": task
        })
        
        # Determine temperature from profile if available
        temperature = self.role.temperature
        if self.profile and self.profile.guardrails.recommended_temperature is not None:
            temperature = self.profile.guardrails.recommended_temperature
        
        try:
            response = await asyncio.wait_for(
                self.provider.chat(
                    messages=messages,
                    model=self.role.model,
                    max_tokens=self.role.max_tokens,
                    temperature=temperature,
                    tools=tools,
                ),
                timeout=120,  # 2 minute timeout
            )
            
            content = response.content or ""
            
            # Track tool call success/failure
            tool_calls_made = bool(response.tool_calls)
            if tool_calls_made:
                # Consider it a success if we got tool calls without error
                self._tool_call_successes += 1
            
            # Update context
            self._context.append({"role": "user", "content": task})
            self._context.append({"role": "assistant", "content": content})
            
            # Trim context if too long
            if len(self._context) > 20:
                self._context = self._context[-10:]
            
            self._success_count += 1
            execution_time = time.time() - start_time
            self._total_time += execution_time
            
            return AgentResponse(
                role_id=self.role.id,
                role_title=self.role.title,
                content=content,
                success=True,
                execution_time=execution_time,
                metadata={
                    "model": self.role.model,
                    "has_profile": self.profile is not None,
                    "tool_calls_made": tool_calls_made,
                },
            )
            
        except asyncio.TimeoutError:
            logger.warning(f"Agent {self.role.id} task timed out")
            return AgentResponse(
                role_id=self.role.id,
                role_title=self.role.title,
                content="",
                success=False,
                execution_time=time.time() - start_time,
                error="Task timed out",
            )
            
        except Exception as e:
            logger.error(f"Agent {self.role.id} error: {e}")
            if tools:
                self._tool_call_failures += 1
            return AgentResponse(
                role_id=self.role.id,
                role_title=self.role.title,
                content="",
                success=False,
                execution_time=time.time() - start_time,
                error=str(e),
            )
    
    async def review(
        self,
        work: str,
        criteria: list[str] | None = None,
        context: str = "",
    ) -> ReviewResult:
        """
        Review another agent's work.
        
        This method is primarily used by QA and Auditor roles.
        
        Args:
            work: The work to review.
            criteria: Specific criteria to check.
            context: Additional context about the task.
        
        Returns:
            ReviewResult with verdict and details.
        """
        criteria = criteria or []
        
        # Build review prompt based on role
        if self.role.id == "auditor":
            review_prompt = self._build_audit_prompt(work, criteria, context)
            verdict_map = {
                "approved": ReviewVerdict.APPROVED,
                "conditional": ReviewVerdict.CONDITIONAL,
                "blocked": ReviewVerdict.BLOCKED,
            }
        else:
            review_prompt = self._build_qa_prompt(work, criteria, context)
            verdict_map = {
                "pass": ReviewVerdict.PASS,
                "warn": ReviewVerdict.WARN,
                "fail": ReviewVerdict.FAIL,
            }
        
        response = await self.execute(review_prompt)
        
        if not response.success:
            return ReviewResult(
                reviewer_id=self.role.id,
                reviewer_title=self.role.title,
                verdict=ReviewVerdict.FAIL,
                summary="Review failed to complete",
                issues=[response.error],
            )
        
        # Parse the review response
        return self._parse_review_response(response.content, verdict_map)
    
    def _build_qa_prompt(
        self,
        work: str,
        criteria: list[str],
        context: str,
    ) -> str:
        """Build QA review prompt."""
        criteria_text = ""
        if criteria:
            criteria_text = "\n\nSpecific criteria to check:\n" + "\n".join(
                f"- {c}" for c in criteria
            )
        
        return f"""Review the following work for quality.

{f"Context: {context}" if context else ""}

Work to review:
---
{work}
---
{criteria_text}

Provide your review in this format:

VERDICT: [PASS/WARN/FAIL]

SUMMARY: [Brief summary of findings]

ISSUES: (list any issues found)
- Issue 1
- Issue 2

RECOMMENDATIONS: (list any recommendations)
- Recommendation 1
- Recommendation 2

DETAILS: [Any additional details]"""
    
    def _build_audit_prompt(
        self,
        work: str,
        criteria: list[str],
        context: str,
    ) -> str:
        """Build security audit prompt."""
        criteria_text = ""
        if criteria:
            criteria_text = "\n\nSpecific security criteria:\n" + "\n".join(
                f"- {c}" for c in criteria
            )
        
        return f"""Perform a security audit on the following work.

{f"Context: {context}" if context else ""}

Work to audit:
---
{work}
---
{criteria_text}

Check for:
- Security vulnerabilities
- Authentication/authorization issues
- Data exposure risks
- Input validation issues
- Compliance concerns

Provide your audit in this format:

VERDICT: [APPROVED/CONDITIONAL/BLOCKED]

SUMMARY: [Brief summary of security assessment]

ISSUES: (list any security issues found)
- Issue 1 [SEVERITY: HIGH/MEDIUM/LOW]
- Issue 2 [SEVERITY: HIGH/MEDIUM/LOW]

RECOMMENDATIONS: (list security recommendations)
- Recommendation 1
- Recommendation 2

DETAILS: [Additional security notes]"""
    
    def _parse_review_response(
        self,
        response: str,
        verdict_map: dict[str, ReviewVerdict],
    ) -> ReviewResult:
        """Parse a review response into structured result."""
        import re
        
        # Extract verdict
        verdict = ReviewVerdict.WARN  # Default
        verdict_match = re.search(
            r'VERDICT:\s*\[?(\w+)\]?',
            response,
            re.IGNORECASE
        )
        if verdict_match:
            verdict_str = verdict_match.group(1).lower()
            verdict = verdict_map.get(verdict_str, ReviewVerdict.WARN)
        
        # Extract summary
        summary = ""
        summary_match = re.search(
            r'SUMMARY:\s*(.+?)(?=\n\n|ISSUES:|RECOMMENDATIONS:|DETAILS:|$)',
            response,
            re.IGNORECASE | re.DOTALL
        )
        if summary_match:
            summary = summary_match.group(1).strip()
        
        # Extract issues
        issues = []
        issues_match = re.search(
            r'ISSUES:(.+?)(?=\n\n|RECOMMENDATIONS:|DETAILS:|$)',
            response,
            re.IGNORECASE | re.DOTALL
        )
        if issues_match:
            issues_text = issues_match.group(1)
            issues = [
                line.strip().lstrip('- ')
                for line in issues_text.split('\n')
                if line.strip() and line.strip().startswith('-')
            ]
        
        # Extract recommendations
        recommendations = []
        rec_match = re.search(
            r'RECOMMENDATIONS:(.+?)(?=\n\n|DETAILS:|$)',
            response,
            re.IGNORECASE | re.DOTALL
        )
        if rec_match:
            rec_text = rec_match.group(1)
            recommendations = [
                line.strip().lstrip('- ')
                for line in rec_text.split('\n')
                if line.strip() and line.strip().startswith('-')
            ]
        
        # Extract details
        details = ""
        details_match = re.search(
            r'DETAILS:\s*(.+?)$',
            response,
            re.IGNORECASE | re.DOTALL
        )
        if details_match:
            details = details_match.group(1).strip()
        
        return ReviewResult(
            reviewer_id=self.role.id,
            reviewer_title=self.role.title,
            verdict=verdict,
            summary=summary or "Review completed",
            issues=issues,
            recommendations=recommendations,
            details=details,
        )
    
    async def give_opinion(
        self,
        question: str,
        context: str = "",
    ) -> AgentResponse:
        """
        Give an opinion on a question (for deliberation).
        
        Args:
            question: The question to opine on.
            context: Additional context.
        
        Returns:
            AgentResponse with the opinion.
        """
        prompt = f"""As the {self.role.title}, provide your professional opinion on:

{question}

{f"Context: {context}" if context else ""}

Consider:
- Your area of expertise
- Potential impacts in your domain
- Practical considerations
- Risks and opportunities

Provide a clear, concise opinion with:
1. Your position
2. Key reasoning (2-3 points)
3. Any concerns or caveats
4. Recommended action"""
        
        return await self.execute(prompt)
    
    def clear_context(self) -> None:
        """Clear session context."""
        self._context.clear()
    
    def get_stats(self) -> dict[str, Any]:
        """Get agent statistics."""
        total_tool_calls = self._tool_call_successes + self._tool_call_failures
        return {
            "id": self.role.id,
            "title": self.role.title,
            "model": self.role.model,
            "task_count": self._task_count,
            "success_count": self._success_count,
            "success_rate": self._success_count / max(self._task_count, 1),
            "average_time": self._total_time / max(self._task_count, 1),
            "authority_level": self.role.authority_level,
            "tool_call_successes": self._tool_call_successes,
            "tool_call_failures": self._tool_call_failures,
            "tool_accuracy": self._tool_call_successes / max(total_tool_calls, 1),
            "has_profile": self.profile is not None,
        }
    
    def reset_stats(self) -> None:
        """Reset statistics."""
        self._task_count = 0
        self._success_count = 0
        self._total_time = 0.0
        self._tool_call_successes = 0
        self._tool_call_failures = 0
    
    def set_profile(self, profile: "ModelProfile | None") -> None:
        """Set or update the model profile."""
        self.profile = profile
