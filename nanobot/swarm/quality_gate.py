"""
Quality gate for GigaBot's persona-based hierarchy.

Implements mandatory QA review and optional audit for all work
before delivery. This ensures consistent quality and security
across all team outputs.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.swarm.team_agent import TeamAgent, ReviewResult, ReviewVerdict


class GateDecision(str, Enum):
    """Decision from the quality gate."""
    PASS = "pass"       # Work approved, ready for delivery
    REVISE = "revise"   # Work needs changes, feedback provided
    REJECT = "reject"   # Work failed, must redo


@dataclass
class WorkOutput:
    """Output from an agent to be reviewed."""
    agent_id: str
    agent_title: str
    task: str
    content: str
    context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GateResult:
    """Result from the quality gate."""
    decision: GateDecision
    qa_result: "ReviewResult | None" = None
    audit_result: "ReviewResult | None" = None
    feedback: str = ""
    must_fix: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    
    @property
    def passed(self) -> bool:
        """Check if work passed the gate."""
        return self.decision == GateDecision.PASS
    
    def get_summary(self) -> str:
        """Get a summary of the gate result."""
        lines = [f"**Quality Gate: {self.decision.value.upper()}**"]
        
        if self.qa_result:
            lines.append(f"\nQA Review: {self.qa_result.verdict.value}")
            if self.qa_result.summary:
                lines.append(f"  {self.qa_result.summary}")
        
        if self.audit_result:
            lines.append(f"\nSecurity Audit: {self.audit_result.verdict.value}")
            if self.audit_result.summary:
                lines.append(f"  {self.audit_result.summary}")
        
        if self.must_fix:
            lines.append("\n**Must Fix:**")
            for issue in self.must_fix:
                lines.append(f"  - {issue}")
        
        if self.suggestions:
            lines.append("\n**Suggestions:**")
            for suggestion in self.suggestions:
                lines.append(f"  - {suggestion}")
        
        return "\n".join(lines)


class QualityGate:
    """
    Mandatory quality review before output delivery.
    
    All work passes through:
    1. QA Review (mandatory) - checks correctness, completeness, quality
    2. Audit Review (optional) - checks security, compliance, risk
    
    The gate produces one of three decisions:
    - PASS: Work is approved
    - REVISE: Work needs changes (feedback provided)
    - REJECT: Work must be redone
    """
    
    def __init__(
        self,
        qa_agent: "TeamAgent",
        auditor_agent: "TeamAgent | None" = None,
        audit_threshold: str = "sensitive",
    ):
        """
        Initialize the quality gate.
        
        Args:
            qa_agent: QA engineer agent for reviews.
            auditor_agent: Security auditor agent (optional).
            audit_threshold: When to audit ("all", "sensitive", "none").
        """
        self.qa_agent = qa_agent
        self.auditor_agent = auditor_agent
        self.audit_threshold = audit_threshold
    
    async def review(
        self,
        work: WorkOutput,
        criteria: list[str] | None = None,
        force_audit: bool = False,
    ) -> GateResult:
        """
        Run the quality gate on work output.
        
        Args:
            work: The work to review.
            criteria: Specific criteria for review.
            force_audit: Force security audit regardless of threshold.
        
        Returns:
            GateResult with decision and feedback.
        """
        logger.info(f"Quality gate reviewing work from {work.agent_id}")
        
        # Step 1: QA Review (mandatory)
        qa_result = await self._qa_review(work, criteria)
        
        # Step 2: Audit Review (conditional)
        audit_result = None
        if self._should_audit(work, force_audit):
            audit_result = await self._audit_review(work, criteria)
        
        # Step 3: Make decision
        decision, feedback, must_fix, suggestions = self._make_decision(
            qa_result, audit_result
        )
        
        return GateResult(
            decision=decision,
            qa_result=qa_result,
            audit_result=audit_result,
            feedback=feedback,
            must_fix=must_fix,
            suggestions=suggestions,
        )
    
    async def _qa_review(
        self,
        work: WorkOutput,
        criteria: list[str] | None,
    ) -> "ReviewResult":
        """Run QA review."""
        from nanobot.swarm.team_agent import ReviewResult, ReviewVerdict
        
        logger.debug(f"Running QA review for {work.agent_id}")
        
        # Add task-specific criteria
        review_criteria = criteria or []
        review_criteria.extend([
            "Code correctness and logic",
            "Completeness of implementation",
            "Error handling",
            "Code readability",
            "Edge cases handled",
        ])
        
        try:
            result = await self.qa_agent.review(
                work=work.content,
                criteria=review_criteria,
                context=f"Task: {work.task}\n\nContext: {work.context}",
            )
            return result
        except Exception as e:
            logger.error(f"QA review failed: {e}")
            return ReviewResult(
                reviewer_id=self.qa_agent.id,
                reviewer_title=self.qa_agent.title,
                verdict=ReviewVerdict.WARN,
                summary=f"QA review error: {str(e)}",
                issues=[str(e)],
            )
    
    async def _audit_review(
        self,
        work: WorkOutput,
        criteria: list[str] | None,
    ) -> "ReviewResult":
        """Run security audit."""
        from nanobot.swarm.team_agent import ReviewResult, ReviewVerdict
        
        if not self.auditor_agent:
            return ReviewResult(
                reviewer_id="auditor",
                reviewer_title="Security Auditor",
                verdict=ReviewVerdict.APPROVED,
                summary="Audit skipped (no auditor configured)",
            )
        
        logger.debug(f"Running security audit for {work.agent_id}")
        
        # Security-specific criteria
        audit_criteria = criteria or []
        audit_criteria.extend([
            "Input validation and sanitization",
            "Authentication and authorization",
            "Sensitive data handling",
            "SQL injection / XSS prevention",
            "Error message information disclosure",
        ])
        
        try:
            result = await self.auditor_agent.review(
                work=work.content,
                criteria=audit_criteria,
                context=f"Task: {work.task}\n\nContext: {work.context}",
            )
            return result
        except Exception as e:
            logger.error(f"Audit failed: {e}")
            return ReviewResult(
                reviewer_id=self.auditor_agent.id,
                reviewer_title=self.auditor_agent.title,
                verdict=ReviewVerdict.CONDITIONAL,
                summary=f"Audit error: {str(e)}",
                issues=[str(e)],
            )
    
    def _should_audit(self, work: WorkOutput, force: bool) -> bool:
        """Determine if work should be audited."""
        if force:
            return True
        
        if self.audit_threshold == "none":
            return False
        
        if self.audit_threshold == "all":
            return True
        
        # "sensitive" threshold - check for sensitive indicators
        sensitive_indicators = [
            "auth", "login", "password", "token", "secret",
            "api_key", "credential", "session", "permission",
            "admin", "user", "security", "encrypt", "decrypt",
            "database", "sql", "query", "exec", "shell",
            "file", "path", "upload", "download",
        ]
        
        content_lower = work.content.lower()
        task_lower = work.task.lower()
        
        for indicator in sensitive_indicators:
            if indicator in content_lower or indicator in task_lower:
                return True
        
        return False
    
    def _make_decision(
        self,
        qa_result: "ReviewResult",
        audit_result: "ReviewResult | None",
    ) -> tuple[GateDecision, str, list[str], list[str]]:
        """
        Make gate decision based on reviews.
        
        Returns:
            Tuple of (decision, feedback, must_fix, suggestions).
        """
        from nanobot.swarm.team_agent import ReviewVerdict
        
        must_fix: list[str] = []
        suggestions: list[str] = []
        
        # Collect issues from QA
        if qa_result.verdict == ReviewVerdict.FAIL:
            must_fix.extend(qa_result.issues)
        elif qa_result.verdict == ReviewVerdict.WARN:
            suggestions.extend(qa_result.issues)
        
        suggestions.extend(qa_result.recommendations)
        
        # Collect issues from audit
        if audit_result:
            if audit_result.verdict == ReviewVerdict.BLOCKED:
                must_fix.extend(audit_result.issues)
            elif audit_result.verdict == ReviewVerdict.CONDITIONAL:
                # Add high-severity audit issues to must_fix
                for issue in audit_result.issues:
                    if "HIGH" in issue.upper():
                        must_fix.append(issue)
                    else:
                        suggestions.append(issue)
            
            suggestions.extend(audit_result.recommendations)
        
        # Make decision
        if qa_result.verdict == ReviewVerdict.FAIL:
            return (
                GateDecision.REJECT,
                "QA review failed. Work must be redone.",
                must_fix,
                suggestions,
            )
        
        if audit_result and audit_result.verdict == ReviewVerdict.BLOCKED:
            return (
                GateDecision.REJECT,
                "Security audit blocked. Critical security issues found.",
                must_fix,
                suggestions,
            )
        
        if must_fix:
            return (
                GateDecision.REVISE,
                "Work needs revisions before approval.",
                must_fix,
                suggestions,
            )
        
        if qa_result.verdict == ReviewVerdict.WARN:
            return (
                GateDecision.PASS,
                "Work approved with minor suggestions.",
                must_fix,
                suggestions,
            )
        
        return (
            GateDecision.PASS,
            "Work approved.",
            must_fix,
            suggestions,
        )
    
    async def quick_review(
        self,
        content: str,
        task: str = "",
    ) -> GateResult:
        """
        Quick review of content without full WorkOutput.
        
        Args:
            content: The content to review.
            task: Brief task description.
        
        Returns:
            GateResult.
        """
        work = WorkOutput(
            agent_id="unknown",
            agent_title="Unknown",
            task=task,
            content=content,
        )
        return await self.review(work)


class MultiStageGate:
    """
    Multi-stage quality gate for complex workflows.
    
    Supports multiple review stages:
    1. Peer Review (optional)
    2. QA Review (mandatory)
    3. Security Audit (conditional)
    4. Final Approval (for critical work)
    """
    
    def __init__(
        self,
        team: Any,  # AgentTeam
        qa_enabled: bool = True,
        audit_enabled: bool = True,
        audit_threshold: str = "sensitive",
    ):
        """
        Initialize multi-stage gate.
        
        Args:
            team: The agent team.
            qa_enabled: Enable QA review.
            audit_enabled: Enable security audit.
            audit_threshold: When to audit.
        """
        self.team = team
        self.qa_enabled = qa_enabled
        self.audit_enabled = audit_enabled
        self.audit_threshold = audit_threshold
        
        # Initialize inner gate
        qa_agent = team.get_qa_agent()
        auditor = team.get_auditor() if audit_enabled else None
        
        self._gate = QualityGate(
            qa_agent=qa_agent,
            auditor_agent=auditor,
            audit_threshold=audit_threshold,
        ) if qa_agent else None
    
    async def review(
        self,
        work: WorkOutput,
        criteria: list[str] | None = None,
    ) -> GateResult:
        """Run multi-stage review."""
        if not self._gate:
            # No QA configured, auto-pass
            return GateResult(
                decision=GateDecision.PASS,
                feedback="Quality gate not configured, auto-approved.",
            )
        
        return await self._gate.review(work, criteria)
